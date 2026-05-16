"""Engine DB layer — uses shared PG pool from `sylion.aeis.advisor._db`.

Per `08_audit_revisions.md` Revision 2 the advisor layer is PG-only. The
canonical schema lives in `sylion/db/advisor_layer.sql` (Alembic revision
`20260425_0002_advisor_layer.py`). This module reads/writes pre-existing PG
tables; it does NOT create them. SQLite remains permitted only as in-memory
test fixture (see `tests/aeis/advisor/engine/_pg_test_pool.py`).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from typing import Any

from psycopg.rows import dict_row

from sylion.aeis.advisor import _db as shared_db
from sylion.aeis.advisor.engine._models import (
    AdvisorCardEnvelope,
    EvidencePack,
    Rule,
    RuleFiring,
)

log = logging.getLogger("sylion.aeis.advisor.engine._db")

_sqlite_conn: sqlite3.Connection | None = None
_sqlite_lock = threading.RLock()


def _use_sqlite_store() -> bool:
    """Use a real audit-local SQLite store when AEIS runs without PG.

    Advisor was originally PG-only, but the dashboard audit profile is explicitly
    a clean local distribution run. In that mode silently swallowing
    ``PGUnreachable`` hides defects, so advisor.engine persists to its own
    audit-isolated SQLite DB instead of emitting demo data or empty fallbacks.
    The same rule applies to normal local first-run mode where the FastAPI app
    reports ``db_mode=sqlite`` and no PostgreSQL DSN is configured.
    """
    if str(os.environ.get("SYLION_ADVISOR_FORCE_PG", "")).lower() in {"1", "true", "yes"}:
        return False
    try:
        from sylion.aeis_v2.audit_profile import is_audit_mode

        if is_audit_mode():
            return True
    except Exception:
        pass
    db_mode = str(os.environ.get("SYLION_DB_MODE", "sqlite")).strip().lower()
    has_pg_dsn = bool(os.environ.get("SYLION_DB_URL") or os.environ.get("SYLION_PG_DSN"))
    return db_mode != "postgres" or not has_pg_dsn


def _sqlite_db_path() -> str:
    from sylion.aeis_v2.audit_profile import resolve_db_path

    return str(resolve_db_path("advisor_engine.db"))


def _get_sqlite_conn() -> sqlite3.Connection:
    global _sqlite_conn
    if _sqlite_conn is None:
        with _sqlite_lock:
            if _sqlite_conn is None:
                conn = sqlite3.connect(_sqlite_db_path(), check_same_thread=False, timeout=30.0)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                _sqlite_conn = conn
                _init_sqlite_schema(conn)
    return _sqlite_conn


def _init_sqlite_schema(conn: sqlite3.Connection) -> None:
    with _sqlite_lock:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS advisor_engine_recommendations (
              card_id TEXT PRIMARY KEY,
              envelope_version TEXT NOT NULL,
              schema_version TEXT NOT NULL,
              card_type TEXT NOT NULL,
              parent_card_id TEXT,
              title TEXT NOT NULL,
              rationale TEXT NOT NULL,
              confidence_score REAL NOT NULL,
              confidence_label TEXT NOT NULL,
              sources TEXT NOT NULL,
              risk_level TEXT NOT NULL,
              risk_explanation TEXT,
              project_domain TEXT,
              project_type TEXT,
              project_id TEXT,
              idea_id TEXT,
              d_level TEXT NOT NULL,
              evidence_pack_id TEXT,
              history_based INTEGER NOT NULL DEFAULT 0,
              related_history_card_ids TEXT NOT NULL DEFAULT '[]',
              historical_acceptance_rate REAL,
              expires_at REAL,
              priority TEXT NOT NULL DEFAULT 'normal',
              tags TEXT NOT NULL DEFAULT '[]',
              dont_learn INTEGER NOT NULL DEFAULT 0,
              human_gate_required INTEGER NOT NULL DEFAULT 0,
              mobile_allowed INTEGER NOT NULL DEFAULT 1,
              requires_biometric INTEGER NOT NULL DEFAULT 0,
              push_priority TEXT NOT NULL DEFAULT 'normal',
              used_local_fallback INTEGER NOT NULL DEFAULT 0,
              local_fallback_reason TEXT,
              audit_trail_id TEXT NOT NULL,
              llm_judge_audit_id TEXT,
              operator_id TEXT NOT NULL,
              emitting_module TEXT NOT NULL,
              body_jsonb TEXT NOT NULL DEFAULT '{}',
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS advisor_engine_llm_judge_audit (
              audit_id TEXT PRIMARY KEY,
              card_id TEXT,
              operator_id TEXT NOT NULL,
              judge_purpose TEXT NOT NULL,
              model_id TEXT NOT NULL,
              prompt_full TEXT NOT NULL,
              response_full TEXT NOT NULL,
              prompt_tokens INTEGER NOT NULL,
              response_tokens INTEGER NOT NULL,
              cost_usd REAL NOT NULL DEFAULT 0,
              latency_ms INTEGER NOT NULL DEFAULT 0,
              was_local_fallback INTEGER NOT NULL DEFAULT 0,
              fallback_reason TEXT,
              parent_audit_id TEXT,
              created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS advisor_engine_rule_definitions (
              rule_id TEXT PRIMARY KEY,
              version INTEGER NOT NULL DEFAULT 1,
              description TEXT NOT NULL,
              hook_event_pattern TEXT NOT NULL,
              precondition TEXT NOT NULL DEFAULT '{}',
              recommendation_type TEXT NOT NULL,
              default_d_level TEXT NOT NULL DEFAULT 'D1',
              is_active INTEGER NOT NULL DEFAULT 1,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS advisor_engine_rule_firing_history (
              firing_id TEXT PRIMARY KEY,
              rule_id TEXT NOT NULL,
              rule_version INTEGER NOT NULL,
              triggering_event_id TEXT,
              context_jsonb TEXT NOT NULL DEFAULT '{}',
              produced_card_id TEXT,
              decision_taken TEXT NOT NULL,
              fired_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS advisor_evidence_packs (
              evidence_pack_id TEXT PRIMARY KEY,
              card_id TEXT,
              d_level TEXT NOT NULL,
              pack_template TEXT NOT NULL,
              decision_class TEXT NOT NULL,
              domain TEXT NOT NULL,
              rationale TEXT NOT NULL,
              rollback_plan TEXT NOT NULL,
              fidelity_test TEXT NOT NULL,
              confidence_breakdown TEXT NOT NULL DEFAULT '{}',
              historical_acceptance_rate REAL,
              llm_judge_audit_ids TEXT NOT NULL DEFAULT '[]',
              simulation_results TEXT NOT NULL DEFAULT '[]',
              council_vote_id TEXT,
              risk_analysis TEXT NOT NULL DEFAULT '{}',
              compliance_check TEXT NOT NULL DEFAULT '{}',
              sentinel_signoffs TEXT NOT NULL DEFAULT '{}',
              attachments TEXT NOT NULL DEFAULT '[]',
              created_by TEXT NOT NULL,
              created_at REAL NOT NULL,
              finalized_at REAL,
              status TEXT NOT NULL DEFAULT 'draft'
            );

            CREATE TABLE IF NOT EXISTS advisor_evidence_pack_signatures (
              signature_id TEXT PRIMARY KEY,
              evidence_pack_id TEXT NOT NULL,
              signer_id TEXT NOT NULL,
              signer_role TEXT NOT NULL,
              signature_payload TEXT NOT NULL,
              signed_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_adv_rec_operator_created
              ON advisor_engine_recommendations(operator_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_adv_rec_project
              ON advisor_engine_recommendations(project_id);
            CREATE INDEX IF NOT EXISTS idx_adv_audit_card
              ON advisor_engine_llm_judge_audit(card_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_adv_rule_active
              ON advisor_engine_rule_definitions(is_active);
            """
        )
        conn.commit()


def _row_to_dict(row: sqlite3.Row | dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return {key: row[key] for key in row.keys()}


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [_row_to_dict(row) or {} for row in rows]


def init_engine_schema() -> None:
    """No-op in PG-only mode. Schema lives in Alembic migration."""
    if _use_sqlite_store():
        _get_sqlite_conn()
        return None
    return None


def reset_engine_db() -> None:
    """No-op in PG-only mode. Test fixtures own per-test reset."""
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            for table in (
                "advisor_evidence_pack_signatures",
                "advisor_evidence_packs",
                "advisor_engine_rule_firing_history",
                "advisor_engine_llm_judge_audit",
                "advisor_engine_recommendations",
                "advisor_engine_rule_definitions",
            ):
                conn.execute(f"DELETE FROM {table}")
            conn.commit()
        return None
    return None


def get_engine_conn():
    """Return a pooled PG connection (context manager).

    Kept for backward compat with tests that call `get_engine_conn().execute(...)`.
    Prefer using `shared_db.get_pool().connection()` directly.
    """
    return shared_db.get_pool().connection()


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def insert_recommendation(env: AdvisorCardEnvelope) -> None:
    h = env.header
    body = env.body()
    body_jsonb = json.dumps(_to_serializable(body)) if body is not None else "{}"

    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            conn.execute(
                """INSERT OR REPLACE INTO advisor_engine_recommendations
                   (card_id, envelope_version, schema_version, card_type, parent_card_id,
                    title, rationale, confidence_score, confidence_label, sources,
                    risk_level, risk_explanation, project_domain, project_type,
                    project_id, idea_id, d_level, evidence_pack_id, history_based,
                    related_history_card_ids, historical_acceptance_rate, expires_at,
                    priority, tags, dont_learn, human_gate_required, mobile_allowed,
                    requires_biometric, push_priority, used_local_fallback,
                    local_fallback_reason, audit_trail_id, llm_judge_audit_id,
                    operator_id, emitting_module, body_jsonb, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    h.card_id, env.envelope_version, h.schema_version, h.card_type,
                    h.parent_card_id or None, h.title, h.rationale,
                    float(h.confidence_score), h.confidence_label,
                    json.dumps(h.sources), h.risk_level, h.risk_explanation or None,
                    h.project_domain, h.project_type or None, h.project_id or None,
                    h.idea_id or None, h.d_level, h.evidence_pack_id or None,
                    int(bool(h.history_based)), json.dumps(h.related_history_card_ids),
                    h.historical_acceptance_rate, h.expires_at or None, h.priority,
                    json.dumps(h.tags), int(bool(h.dont_learn)),
                    int(bool(h.human_gate_required)), int(bool(h.mobile_allowed)),
                    int(bool(h.requires_biometric)), h.push_priority,
                    int(bool(h.used_local_fallback)), h.local_fallback_reason or None,
                    h.audit_trail_id, h.llm_judge_audit_id or None, h.operator_id,
                    h.emitting_module, body_jsonb, float(h.created_at), float(h.updated_at),
                ),
            )
            conn.commit()
        return

    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_engine.recommendations
               (card_id, envelope_version, schema_version, card_type, parent_card_id,
                title, rationale, confidence_score, confidence_label, sources,
                risk_level, risk_explanation, project_domain, project_type,
                project_id, idea_id, d_level, evidence_pack_id, history_based,
                related_history_card_ids, historical_acceptance_rate, expires_at,
                priority, tags, dont_learn, human_gate_required, mobile_allowed,
                requires_biometric, push_priority, used_local_fallback,
                local_fallback_reason, audit_trail_id, llm_judge_audit_id,
                operator_id, emitting_module, body_jsonb, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                h.card_id, env.envelope_version, h.schema_version, h.card_type,
                h.parent_card_id or None,
                h.title, h.rationale, h.confidence_score, h.confidence_label,
                json.dumps(h.sources), h.risk_level, h.risk_explanation or None,
                h.project_domain, h.project_type or None, h.project_id or None,
                h.idea_id or None, h.d_level, h.evidence_pack_id or None,
                bool(h.history_based), json.dumps(h.related_history_card_ids),
                h.historical_acceptance_rate, h.expires_at or None, h.priority,
                json.dumps(h.tags), bool(h.dont_learn), bool(h.human_gate_required),
                bool(h.mobile_allowed), bool(h.requires_biometric), h.push_priority,
                bool(h.used_local_fallback), h.local_fallback_reason or None,
                h.audit_trail_id, h.llm_judge_audit_id or None, h.operator_id,
                h.emitting_module, body_jsonb, h.created_at, h.updated_at,
            ),
        )


def fetch_recommendations(operator_id: str, limit: int = 50) -> list[dict[str, Any]]:
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            rows = conn.execute(
                "SELECT * FROM advisor_engine_recommendations WHERE operator_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (operator_id, int(limit)),
            ).fetchall()
        return _rows_to_dicts(rows)

    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_engine.recommendations WHERE operator_id = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (operator_id, limit),
        )
        return cur.fetchall()


def fetch_recommendation_by_id(card_id: str) -> dict[str, Any] | None:
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            row = conn.execute(
                "SELECT * FROM advisor_engine_recommendations WHERE card_id = ?",
                (card_id,),
            ).fetchone()
        return _row_to_dict(row)

    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_engine.recommendations WHERE card_id = %s",
            (card_id,),
        )
        return cur.fetchone()


# ---------------------------------------------------------------------------
# LLM judge audit
# ---------------------------------------------------------------------------


def insert_llm_judge_audit(
    *,
    audit_id: str,
    card_id: str | None,
    operator_id: str,
    judge_purpose: str,
    model_id: str,
    prompt_full: str,
    response_full: str,
    prompt_tokens: int,
    response_tokens: int,
    cost_usd: float,
    latency_ms: int,
    was_local_fallback: bool = False,
    fallback_reason: str | None = None,
    parent_audit_id: str | None = None,
) -> None:
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            conn.execute(
                """INSERT OR REPLACE INTO advisor_engine_llm_judge_audit
                   (audit_id, card_id, operator_id, judge_purpose, model_id,
                    prompt_full, response_full, prompt_tokens, response_tokens,
                    cost_usd, latency_ms, was_local_fallback, fallback_reason,
                    parent_audit_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    audit_id, card_id, operator_id, judge_purpose, model_id,
                    prompt_full, response_full, int(prompt_tokens), int(response_tokens),
                    float(cost_usd), int(latency_ms), int(bool(was_local_fallback)),
                    fallback_reason, parent_audit_id, time.time(),
                ),
            )
            conn.commit()
        return

    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_engine.llm_judge_audit
               (audit_id, card_id, operator_id, judge_purpose, model_id, prompt_full,
                response_full, prompt_tokens, response_tokens, cost_usd, latency_ms,
                was_local_fallback, fallback_reason, parent_audit_id, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                audit_id, card_id, operator_id, judge_purpose, model_id, prompt_full,
                response_full, prompt_tokens, response_tokens, cost_usd, latency_ms,
                bool(was_local_fallback), fallback_reason, parent_audit_id, time.time(),
            ),
        )


def fetch_llm_judge_audits(card_id: str) -> list[dict[str, Any]]:
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            rows = conn.execute(
                "SELECT * FROM advisor_engine_llm_judge_audit WHERE card_id = ? "
                "ORDER BY created_at ASC",
                (card_id,),
            ).fetchall()
        return _rows_to_dicts(rows)

    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_engine.llm_judge_audit WHERE card_id = %s "
            "ORDER BY created_at ASC",
            (card_id,),
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def upsert_rule(rule: Rule) -> None:
    now = time.time()
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            conn.execute(
                """INSERT INTO advisor_engine_rule_definitions
                   (rule_id, version, description, hook_event_pattern, precondition,
                    recommendation_type, default_d_level, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(rule_id) DO UPDATE SET
                     version = excluded.version,
                     description = excluded.description,
                     hook_event_pattern = excluded.hook_event_pattern,
                     precondition = excluded.precondition,
                     recommendation_type = excluded.recommendation_type,
                     default_d_level = excluded.default_d_level,
                     is_active = excluded.is_active,
                     updated_at = excluded.updated_at""",
                (
                    rule.rule_id, int(rule.version), rule.description,
                    rule.hook_event_pattern, json.dumps(rule.precondition),
                    rule.recommendation_type, rule.default_d_level,
                    int(bool(rule.is_active)), now, now,
                ),
            )
            conn.commit()
        return

    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_engine.rule_definitions
               (rule_id, version, description, hook_event_pattern, precondition,
                recommendation_type, default_d_level, is_active, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (rule_id) DO UPDATE SET
                 version = EXCLUDED.version,
                 description = EXCLUDED.description,
                 hook_event_pattern = EXCLUDED.hook_event_pattern,
                 precondition = EXCLUDED.precondition,
                 recommendation_type = EXCLUDED.recommendation_type,
                 default_d_level = EXCLUDED.default_d_level,
                 is_active = EXCLUDED.is_active,
                 updated_at = EXCLUDED.updated_at""",
            (
                rule.rule_id, rule.version, rule.description, rule.hook_event_pattern,
                json.dumps(rule.precondition), rule.recommendation_type,
                rule.default_d_level, bool(rule.is_active), now, now,
            ),
        )


def fetch_rules(active_only: bool = True) -> list[Rule]:
    if _use_sqlite_store():
        sql = "SELECT * FROM advisor_engine_rule_definitions"
        params: tuple[Any, ...] = ()
        if active_only:
            sql += " WHERE is_active = 1"
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            rows = conn.execute(sql, params).fetchall()
        return [
            Rule(
                rule_id=str(r["rule_id"]),
                description=str(r["description"]),
                hook_event_pattern=str(r["hook_event_pattern"]),
                precondition=json.loads(r["precondition"] or "{}"),
                recommendation_type=str(r["recommendation_type"]),
                default_d_level=str(r["default_d_level"]),
                is_active=bool(r["is_active"]),
                version=int(r["version"]),
            )
            for r in rows
        ]

    sql = "SELECT * FROM advisor_engine.rule_definitions"
    if active_only:
        sql += " WHERE is_active = 1"
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return [
        Rule(
            rule_id=r["rule_id"],
            description=r["description"],
            hook_event_pattern=r["hook_event_pattern"],
            precondition=json.loads(r["precondition"]) if isinstance(r["precondition"], str) else r["precondition"],
            recommendation_type=r["recommendation_type"],
            default_d_level=r["default_d_level"],
            is_active=bool(r["is_active"]),
            version=r["version"],
        )
        for r in rows
    ]


def insert_rule_firing(firing: RuleFiring) -> None:
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            conn.execute(
                """INSERT OR REPLACE INTO advisor_engine_rule_firing_history
                   (firing_id, rule_id, rule_version, triggering_event_id, context_jsonb,
                    produced_card_id, decision_taken, fired_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    firing.firing_id, firing.rule_id, int(firing.rule_version),
                    firing.triggering_event_id, json.dumps(firing.context),
                    firing.produced_card_id or None, firing.decision_taken,
                    float(firing.fired_at),
                ),
            )
            conn.commit()
        return

    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_engine.rule_firing_history
               (firing_id, rule_id, rule_version, triggering_event_id, context_jsonb,
                produced_card_id, decision_taken, fired_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                firing.firing_id, firing.rule_id, firing.rule_version,
                firing.triggering_event_id, json.dumps(firing.context),
                firing.produced_card_id or None, firing.decision_taken, firing.fired_at,
            ),
        )


# ---------------------------------------------------------------------------
# Evidence Packs
# ---------------------------------------------------------------------------


def insert_evidence_pack(pack: EvidencePack) -> None:
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            conn.execute(
                """INSERT OR REPLACE INTO advisor_evidence_packs
                   (evidence_pack_id, card_id, d_level, pack_template, decision_class,
                    domain, rationale, rollback_plan, fidelity_test, confidence_breakdown,
                    historical_acceptance_rate, llm_judge_audit_ids, simulation_results,
                    council_vote_id, risk_analysis, compliance_check, sentinel_signoffs,
                    attachments, created_by, created_at, finalized_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pack.evidence_pack_id, pack.card_id or None, pack.d_level,
                    pack.pack_template, pack.decision_class, pack.domain,
                    pack.rationale, pack.rollback_plan, pack.fidelity_test,
                    json.dumps(pack.confidence_breakdown),
                    pack.historical_acceptance_rate,
                    json.dumps(pack.llm_judge_audit_ids),
                    json.dumps(pack.simulation_results), pack.council_vote_id or None,
                    json.dumps(pack.risk_analysis), json.dumps(pack.compliance_check),
                    json.dumps(pack.sentinel_signoffs), json.dumps(pack.attachments),
                    pack.created_by, float(pack.created_at),
                    pack.finalized_at or None, pack.status,
                ),
            )
            conn.commit()
        return

    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_evidence.evidence_packs
               (evidence_pack_id, card_id, d_level, pack_template, decision_class,
                domain, rationale, rollback_plan, fidelity_test, confidence_breakdown,
                historical_acceptance_rate, llm_judge_audit_ids, simulation_results,
                council_vote_id, risk_analysis, compliance_check, sentinel_signoffs,
                attachments, created_by, created_at, finalized_at, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, %s, %s)""",
            (
                pack.evidence_pack_id, pack.card_id, pack.d_level, pack.pack_template,
                pack.decision_class, pack.domain, pack.rationale, pack.rollback_plan,
                pack.fidelity_test, json.dumps(pack.confidence_breakdown),
                pack.historical_acceptance_rate,
                json.dumps(pack.llm_judge_audit_ids),
                json.dumps(pack.simulation_results), pack.council_vote_id or None,
                json.dumps(pack.risk_analysis), json.dumps(pack.compliance_check),
                json.dumps(pack.sentinel_signoffs), json.dumps(pack.attachments),
                pack.created_by, pack.created_at, pack.finalized_at or None, pack.status,
            ),
        )


def fetch_evidence_pack(pack_id: str) -> dict[str, Any] | None:
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            row = conn.execute(
                "SELECT * FROM advisor_evidence_packs WHERE evidence_pack_id = ?",
                (pack_id,),
            ).fetchone()
        pack = _row_to_dict(row)
        if pack:
            for key, default in (
                ("confidence_breakdown", {}),
                ("llm_judge_audit_ids", []),
                ("simulation_results", []),
                ("risk_analysis", {}),
                ("compliance_check", {}),
                ("sentinel_signoffs", {}),
                ("attachments", []),
            ):
                value = pack.get(key)
                if isinstance(value, str):
                    try:
                        pack[key] = json.loads(value)
                    except Exception:
                        pack[key] = default
        return pack

    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_evidence.evidence_packs WHERE evidence_pack_id = %s",
            (pack_id,),
        )
        return cur.fetchone()


def update_evidence_pack_status(pack_id: str, status: str, finalized: bool = False) -> None:
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            if finalized:
                conn.execute(
                    "UPDATE advisor_evidence_packs SET status = ?, finalized_at = ? "
                    "WHERE evidence_pack_id = ?",
                    (status, time.time(), pack_id),
                )
            else:
                conn.execute(
                    "UPDATE advisor_evidence_packs SET status = ? WHERE evidence_pack_id = ?",
                    (status, pack_id),
                )
            conn.commit()
        return

    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        if finalized:
            cur.execute(
                "UPDATE advisor_evidence.evidence_packs SET status = %s, finalized_at = %s "
                "WHERE evidence_pack_id = %s",
                (status, time.time(), pack_id),
            )
        else:
            cur.execute(
                "UPDATE advisor_evidence.evidence_packs SET status = %s "
                "WHERE evidence_pack_id = %s",
                (status, pack_id),
            )


def insert_evidence_signature(
    *, evidence_pack_id: str, signer_id: str, signer_role: str, signature_payload: str
) -> str:
    sig_id = str(uuid.uuid4())
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            conn.execute(
                """INSERT INTO advisor_evidence_pack_signatures
                   (signature_id, evidence_pack_id, signer_id, signer_role,
                    signature_payload, signed_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (sig_id, evidence_pack_id, signer_id, signer_role, signature_payload, time.time()),
            )
            conn.commit()
        return sig_id

    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_evidence.evidence_pack_signatures
               (signature_id, evidence_pack_id, signer_id, signer_role,
                signature_payload, signed_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (sig_id, evidence_pack_id, signer_id, signer_role, signature_payload, time.time()),
        )
    return sig_id


def fetch_evidence_signatures(pack_id: str) -> list[dict[str, Any]]:
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            rows = conn.execute(
                "SELECT * FROM advisor_evidence_pack_signatures "
                "WHERE evidence_pack_id = ? ORDER BY signed_at ASC",
                (pack_id,),
            ).fetchall()
        return _rows_to_dicts(rows)

    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_evidence.evidence_pack_signatures "
            "WHERE evidence_pack_id = %s ORDER BY signed_at ASC",
            (pack_id,),
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Monitoring / audit helpers
# ---------------------------------------------------------------------------


def fetch_recent_audit_entries(limit: int = 5) -> list[dict[str, Any]]:
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            rows = conn.execute(
                """
                SELECT audit_id AS id, created_at AS timestamp, operator_id AS actor,
                       'llm_judge.' || judge_purpose AS action, model_id AS target,
                       response_full AS result
                FROM advisor_engine_llm_judge_audit
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "actor": row["actor"],
                "action": row["action"],
                "target": row["target"],
                "payload": {"result": row["result"][:500] if row["result"] else ""},
                "signature": "",
            }
            for row in rows
        ]

    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                log_id::text AS id,
                timestamp,
                actor,
                action,
                resource AS target,
                result
            FROM audit_log
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return [
        {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "actor": row.get("actor") or "",
            "action": row.get("action") or "",
            "target": row.get("target") or "",
            "payload": {"result": row.get("result")} if row.get("result") is not None else {},
            "signature": "",
        }
        for row in rows
    ]


def fetch_avg_confidence(operator_id: str, limit: int = 20) -> float:
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            row = conn.execute(
                """
                SELECT AVG(confidence_score) AS avg_confidence
                FROM (
                    SELECT confidence_score
                    FROM advisor_engine_recommendations
                    WHERE operator_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                )
                """,
                (operator_id, int(limit)),
            ).fetchone()
        return float(row["avg_confidence"] if row and row["avg_confidence"] is not None else 0.0)

    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            WITH recent AS (
                SELECT confidence_score
                FROM advisor_engine.recommendations
                WHERE operator_id = %s::uuid
                ORDER BY created_at DESC
                LIMIT %s
            )
            SELECT AVG(confidence_score) AS avg_confidence
            FROM recent
            """,
            (operator_id, limit),
        )
        row = cur.fetchone() or {}
    return float(row.get("avg_confidence") or 0.0)


def fetch_human_gate_metrics(operator_id: str) -> dict[str, Any]:
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            rows = conn.execute(
                """
                SELECT COALESCE(NULLIF(project_domain, ''), NULLIF(card_type, ''), 'other') AS bucket,
                       COUNT(*) AS count
                FROM advisor_engine_recommendations
                WHERE operator_id = ? AND human_gate_required = 1
                GROUP BY bucket
                ORDER BY count DESC, bucket ASC
                """,
                (operator_id,),
            ).fetchall()
        total = sum(int(row["count"] or 0) for row in rows)
        parts = [f"{int(row['count'] or 0)} {row['bucket'] or 'other'}" for row in rows]
        return {"pending_hg": total, "hg_breakdown": " · ".join(parts)}

    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            WITH unresolved AS (
                SELECT
                    r.card_id,
                    COALESCE(NULLIF(r.project_domain, ''), NULLIF(r.card_type::text, ''), 'other') AS bucket
                FROM advisor_engine.recommendations r
                WHERE r.operator_id = %s::uuid
                  AND r.human_gate_required = true
                  AND NOT EXISTS (
                      SELECT 1
                      FROM advisor_history.card_actions a
                      WHERE a.card_id = r.card_id
                  )
            )
            SELECT
                (SELECT COUNT(*)::int FROM unresolved) AS pending_hg,
                COALESCE(
                    json_agg(
                        json_build_object('bucket', bucket, 'count', bucket_count)
                        ORDER BY bucket_count DESC, bucket ASC
                    ) FILTER (WHERE bucket IS NOT NULL),
                    '[]'::json
                ) AS breakdown
            FROM (
                SELECT bucket, COUNT(*)::int AS bucket_count
                FROM unresolved
                GROUP BY bucket
            ) grouped
            """,
            (operator_id,),
        )
        row = cur.fetchone() or {}
    breakdown = row.get("breakdown") or []
    if isinstance(breakdown, str):
        try:
            breakdown = json.loads(breakdown)
        except Exception:
            breakdown = []
    parts = [
        f"{int(item.get('count') or 0)} {str(item.get('bucket') or 'other')}"
        for item in breakdown
        if int(item.get("count") or 0) > 0
    ]
    return {
        "pending_hg": int(row.get("pending_hg") or 0),
        "hg_breakdown": " · ".join(parts),
    }


def fetch_configuration_counts() -> dict[str, int]:
    counts = {
        "api_keys": 0,
        "local_models": 0,
        "routing_rules": 0,
        "skills": 0,
    }
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM advisor_engine_rule_definitions WHERE is_active = 1"
            ).fetchone()
        counts["routing_rules"] = int(row["count"] if row and row["count"] is not None else 0)
        try:
            from sylion.security.key_vault import get_key_vault

            counts["api_keys"] = sum(
                1 for key in get_key_vault().list_keys()
                if bool(key.get("is_active", True))
            )
        except Exception:
            counts["api_keys"] = 0
        try:
            from sylion.cognitive.llm_runtime import installed_ollama_models

            counts["local_models"] = len(installed_ollama_models())
        except Exception:
            counts["local_models"] = 0
        try:
            from sylion.skills.registry import get_skills_registry

            counts["skills"] = len(get_skills_registry().list_skills(limit=1000))
        except Exception:
            counts["skills"] = 0
        return counts

    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT COUNT(*)::int AS count
            FROM advisor_pricing.provider_models
            WHERE is_local = true AND is_deprecated = false
            """
        )
        counts["local_models"] = int((cur.fetchone() or {}).get("count") or 0)

        cur.execute(
            """
            SELECT COUNT(*)::int AS count
            FROM advisor_engine.rule_definitions
            WHERE is_active = true
            """
        )
        counts["routing_rules"] = int((cur.fetchone() or {}).get("count") or 0)

        cur.execute("SELECT COUNT(*)::int AS count FROM skills")
        counts["skills"] = int((cur.fetchone() or {}).get("count") or 0)
    return counts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_serializable(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_serializable(getattr(obj, k)) for k in obj.__dataclass_fields__}
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(v) for v in obj]
    return obj


def envelope_to_dict(env: AdvisorCardEnvelope) -> dict[str, Any]:
    return _to_serializable(env)


def envelope_from_row(row: dict[str, Any]) -> dict[str, Any]:
    def _maybe_load(value: Any, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                return default
        return value

    return {
        "envelope_version": row["envelope_version"],
        "header": {
            "card_id": row["card_id"],
            "schema_version": row["schema_version"],
            "card_type": row["card_type"],
            "parent_card_id": row["parent_card_id"] or "",
            "title": row["title"],
            "rationale": row["rationale"],
            "confidence_score": row["confidence_score"],
            "confidence_label": row["confidence_label"],
            "sources": _maybe_load(row["sources"], []),
            "risk_level": row["risk_level"],
            "risk_explanation": row["risk_explanation"] or "",
            "project_domain": row["project_domain"],
            "project_type": row["project_type"] or "",
            "project_id": row["project_id"] or "",
            "idea_id": row["idea_id"] or "",
            "d_level": row["d_level"],
            "evidence_pack_id": row["evidence_pack_id"] or "",
            "history_based": bool(row["history_based"]),
            "related_history_card_ids": _maybe_load(row["related_history_card_ids"], []),
            "historical_acceptance_rate": row["historical_acceptance_rate"] or 0.0,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "expires_at": row["expires_at"] or 0,
            "priority": row["priority"],
            "tags": _maybe_load(row["tags"], []),
            "dont_learn": bool(row["dont_learn"]),
            "human_gate_required": bool(row["human_gate_required"]),
            "mobile_allowed": bool(row["mobile_allowed"]),
            "requires_biometric": bool(row["requires_biometric"]),
            "push_priority": row["push_priority"],
            "used_local_fallback": bool(row["used_local_fallback"]),
            "local_fallback_reason": row["local_fallback_reason"] or "",
            "audit_trail_id": row["audit_trail_id"],
            "llm_judge_audit_id": row["llm_judge_audit_id"] or "",
            "operator_id": row["operator_id"],
            "emitting_module": row["emitting_module"],
        },
        "body": _maybe_load(row["body_jsonb"], {}),
    }
