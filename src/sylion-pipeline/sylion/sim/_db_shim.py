"""Standalone SQLite-backed PG pool shim for simulator use (no pytest needed).

Mirrors tests/aeis/advisor/engine/_pg_test_pool.py but usable outside pytest.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterable

_PG_PARAM_RE = re.compile(r"%s")
_TYPE_TRANSLATIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bJSONB\b", re.IGNORECASE), "TEXT"),
    (re.compile(r"\bJSON\b(?![A-Z])", re.IGNORECASE), "TEXT"),
    (re.compile(r"\bUUID\b", re.IGNORECASE), "TEXT"),
    (re.compile(r"\bTIMESTAMPTZ\b", re.IGNORECASE), "REAL"),
    (re.compile(r"\bTIMESTAMP\b", re.IGNORECASE), "REAL"),
    (re.compile(r"\bBOOLEAN\b", re.IGNORECASE), "INTEGER"),
    (re.compile(r"\bDOUBLE PRECISION\b", re.IGNORECASE), "REAL"),
    (re.compile(r"\bSERIAL PRIMARY KEY\b", re.IGNORECASE), "INTEGER PRIMARY KEY AUTOINCREMENT"),
    (re.compile(r"\bgen_random_uuid\(\)", re.IGNORECASE), "lower(hex(randomblob(16)))"),
    (re.compile(r"\bnow\(\)", re.IGNORECASE), "CURRENT_TIMESTAMP"),
]

_NAME_REWRITES: dict[str, str] = {
    "advisor_engine.recommendations": "advisor_engine_recommendations",
    "advisor_engine.llm_judge_audit": "advisor_engine_llm_judge_audit",
    "advisor_engine.rule_definitions": "advisor_engine_rule_definitions",
    "advisor_engine.rule_firing_history": "advisor_engine_rule_firing_history",
    "advisor_evidence.evidence_packs": "advisor_evidence_packs",
    "advisor_evidence.evidence_pack_signatures": "advisor_evidence_pack_signatures",
}


_ENGINE_TEST_SCHEMA = """
CREATE TABLE advisor_engine_recommendations (
  card_id              UUID PRIMARY KEY,
  envelope_version     TEXT NOT NULL,
  schema_version       TEXT NOT NULL,
  card_type            TEXT NOT NULL,
  parent_card_id       UUID,
  title                TEXT NOT NULL,
  rationale            TEXT NOT NULL,
  confidence_score     DOUBLE PRECISION NOT NULL,
  confidence_label     TEXT NOT NULL,
  sources              JSONB NOT NULL,
  risk_level           TEXT NOT NULL,
  risk_explanation     TEXT,
  project_domain       TEXT NOT NULL,
  project_type         TEXT,
  project_id           UUID,
  idea_id              UUID,
  d_level              TEXT NOT NULL,
  evidence_pack_id     UUID,
  history_based        BOOLEAN NOT NULL DEFAULT 0,
  related_history_card_ids JSONB,
  historical_acceptance_rate DOUBLE PRECISION,
  expires_at           TIMESTAMPTZ,
  priority             TEXT NOT NULL DEFAULT 'normal',
  tags                 JSONB,
  dont_learn           BOOLEAN NOT NULL DEFAULT 0,
  human_gate_required  BOOLEAN NOT NULL DEFAULT 0,
  mobile_allowed       BOOLEAN NOT NULL DEFAULT 1,
  requires_biometric   BOOLEAN NOT NULL DEFAULT 0,
  push_priority        TEXT NOT NULL DEFAULT 'normal',
  used_local_fallback  BOOLEAN NOT NULL DEFAULT 0,
  local_fallback_reason TEXT,
  audit_trail_id       UUID NOT NULL,
  llm_judge_audit_id   UUID,
  operator_id          UUID NOT NULL,
  emitting_module      TEXT NOT NULL,
  body_jsonb           JSONB NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL,
  updated_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_engine_llm_judge_audit (
  audit_id             UUID PRIMARY KEY,
  card_id              UUID,
  operator_id          UUID NOT NULL,
  judge_purpose        TEXT NOT NULL,
  model_id             TEXT NOT NULL,
  prompt_full          TEXT NOT NULL,
  response_full        TEXT NOT NULL,
  prompt_tokens        INTEGER NOT NULL,
  response_tokens      INTEGER NOT NULL,
  cost_usd             DOUBLE PRECISION NOT NULL,
  latency_ms           INTEGER NOT NULL,
  was_local_fallback   BOOLEAN NOT NULL DEFAULT 0,
  fallback_reason      TEXT,
  parent_audit_id      UUID,
  created_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_engine_rule_definitions (
  rule_id              TEXT PRIMARY KEY,
  version              INTEGER NOT NULL DEFAULT 1,
  description          TEXT NOT NULL,
  hook_event_pattern   TEXT NOT NULL,
  precondition         JSONB NOT NULL,
  recommendation_type  TEXT NOT NULL,
  default_d_level      TEXT NOT NULL,
  is_active            BOOLEAN NOT NULL DEFAULT 1,
  created_at           TIMESTAMPTZ NOT NULL,
  updated_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_engine_rule_firing_history (
  firing_id            UUID PRIMARY KEY,
  rule_id              TEXT NOT NULL,
  rule_version         INTEGER NOT NULL,
  triggering_event_id  UUID NOT NULL,
  context_jsonb        JSONB NOT NULL,
  produced_card_id     UUID,
  decision_taken       TEXT NOT NULL,
  fired_at             TIMESTAMPTZ NOT NULL
);

CREATE TABLE advisor_evidence_packs (
  evidence_pack_id     UUID PRIMARY KEY,
  card_id              UUID NOT NULL,
  d_level              TEXT NOT NULL,
  pack_template        TEXT NOT NULL,
  decision_class       TEXT NOT NULL,
  domain               TEXT NOT NULL,
  rationale            TEXT NOT NULL,
  rollback_plan        TEXT NOT NULL,
  fidelity_test        TEXT NOT NULL,
  confidence_breakdown JSONB NOT NULL,
  historical_acceptance_rate DOUBLE PRECISION,
  llm_judge_audit_ids  JSONB,
  simulation_results   JSONB,
  council_vote_id      UUID,
  risk_analysis        JSONB,
  compliance_check     JSONB,
  sentinel_signoffs    JSONB,
  attachments          JSONB,
  created_by           UUID NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL,
  finalized_at         TIMESTAMPTZ,
  status               TEXT NOT NULL DEFAULT 'draft'
);

CREATE TABLE advisor_evidence_pack_signatures (
  signature_id         UUID PRIMARY KEY,
  evidence_pack_id     UUID NOT NULL,
  signer_id            UUID NOT NULL,
  signer_role          TEXT NOT NULL,
  signature_payload    TEXT NOT NULL,
  signed_at            TIMESTAMPTZ NOT NULL
);
"""


def translate_pg_to_sqlite(sql: str) -> str:
    out = sql
    for pattern, replacement in _TYPE_TRANSLATIONS:
        out = pattern.sub(replacement, out)
    return out


def translate_query(query: str) -> str:
    out = _PG_PARAM_RE.sub("?", query)
    for fq, flat in _NAME_REWRITES.items():
        out = out.replace(fq, flat)
    return out


class _CursorShim:
    def __init__(self, conn: sqlite3.Connection, lock: threading.RLock, *, dict_rows: bool):
        self._lock = lock
        self._conn = conn
        self._dict_rows = dict_rows
        self._cur: sqlite3.Cursor | None = None

    def __enter__(self) -> "_CursorShim":
        with self._lock:
            self._cur = self._conn.cursor()
        if self._dict_rows:
            self._cur.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._cur is not None:
            self._cur.close()
            self._cur = None

    def execute(self, query: str, params: Iterable[Any] | None = None) -> "_CursorShim":
        assert self._cur is not None
        with self._lock:
            self._cur.execute(translate_query(query), tuple(params) if params else ())
        return self

    def fetchone(self) -> Any:
        assert self._cur is not None
        with self._lock:
            row = self._cur.fetchone()
        if row is None:
            return None
        return dict(row) if self._dict_rows else tuple(row)

    def fetchall(self) -> list[Any]:
        assert self._cur is not None
        with self._lock:
            rows = self._cur.fetchall()
        if self._dict_rows:
            return [dict(r) for r in rows]
        return [tuple(r) for r in rows]

    @property
    def description(self):
        return self._cur.description if self._cur else None

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount if self._cur else -1


class _ConnectionShim:
    def __init__(self, conn: sqlite3.Connection, lock: threading.RLock):
        self._conn = conn
        self._lock = lock

    def cursor(self, *, row_factory: Any = None) -> _CursorShim:
        return _CursorShim(self._conn, self._lock, dict_rows=row_factory is not None)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def rollback(self) -> None:
        with self._lock:
            self._conn.rollback()


class SimTestPool:
    """In-memory SQLite-backed pool that quacks like psycopg_pool.ConnectionPool."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(":memory:", check_same_thread=False, timeout=30.0)
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute("PRAGMA foreign_keys = ON")

    @contextmanager
    def connection(self):
        conn_shim = _ConnectionShim(self._conn, self._lock)
        try:
            yield conn_shim
            conn_shim.commit()
        except Exception:
            conn_shim.rollback()
            raise

    def execute_script(self, script: str) -> None:
        translated = translate_pg_to_sqlite(script)
        with self._lock:
            self._conn.executescript(translated)
            self._conn.commit()


def install_sim_pool() -> SimTestPool:
    """Replace sylion.aeis.advisor._db._pool with a fresh SQLite-backed shim."""
    from sylion.aeis.advisor import _db as shared_db

    pool = SimTestPool()
    pool.execute_script(_ENGINE_TEST_SCHEMA)
    shared_db._pool = pool
    return pool
