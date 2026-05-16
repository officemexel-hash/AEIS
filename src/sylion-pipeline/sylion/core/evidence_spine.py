"""
SYLION Core — Evidence Spine

Immutable, append-only audit log with hash chain.
Every D2+ decision leaves a permanent, tamper-evident trace.

Chain: SHA-256(prev_hash | event_id | canonical_json(payload) | timestamp)
Genesis: prev_hash = "0" * 64
Signing: Ed25519 planned (SHA-256 for now).

gRPC planned: AppendEvidence, QueryEvidence, ReplayToCheckpoint
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.core.evidence_spine")

GENESIS_PREV_HASH = "0" * 64


@dataclass
class EvidenceEntry:
    entry_id: str = ""
    source_plan: str = ""
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""
    hash: str = ""
    timestamp: float = 0.0
    actor_id: str = ""
    signature: str = ""

    def __post_init__(self):
        if not self.entry_id:
            self.entry_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


def _compute_chain_hash(entry_id: str, payload_json: str, prev_hash: str, timestamp: float) -> str:
    import hashlib
    raw = f"{prev_hash}|{entry_id}|{payload_json}|{timestamp}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


class EvidenceSpine:
    """Immutable hash-chain audit log.

    Thread-safe. SQLite-backed. Emits events to EventBus.
    """

    def __init__(self, db_path: str | Path | None = None, event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path) if db_path else ":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_spine (
                entry_id    TEXT PRIMARY KEY,
                source_plan TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                payload     TEXT NOT NULL DEFAULT '{}',
                prev_hash   TEXT NOT NULL,
                hash        TEXT NOT NULL,
                timestamp   REAL NOT NULL,
                actor_id    TEXT NOT NULL DEFAULT '',
                signature   TEXT NOT NULL DEFAULT ''
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_plan ON evidence_spine(source_plan)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence_spine(event_type)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_ts ON evidence_spine(timestamp)")
        self._conn.commit()

    def _get_last_hash(self) -> str:
        row = self._conn.execute(
            "SELECT hash FROM evidence_spine ORDER BY timestamp DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return row["hash"] if row else GENESIS_PREV_HASH

    def append(self, entry: EvidenceEntry) -> dict:
        payload_json = _canonical_json(entry.payload)

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            prev_hash = self._get_last_hash()
            chain_hash = _compute_chain_hash(entry.entry_id, payload_json, prev_hash, entry.timestamp)

            self._conn.execute("""
                INSERT INTO evidence_spine
                (entry_id, source_plan, event_type, payload, prev_hash, hash, timestamp, actor_id, signature)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (entry.entry_id, entry.source_plan, entry.event_type, payload_json,
                  prev_hash, chain_hash, entry.timestamp, entry.actor_id, entry.signature))
            self._conn.commit()

        entry.prev_hash = prev_hash
        entry.hash = chain_hash

        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic="evidence.appended",
                payload={"entry_id": entry.entry_id, "hash": chain_hash},
                source_module="core.evidence_spine",
            ))

        log.info("evidence appended: %s (plan=%s, type=%s)", entry.entry_id[:12], entry.source_plan, entry.event_type)
        return {"entry_id": entry.entry_id, "hash": chain_hash, "prev_hash": prev_hash}

    def query(self, source_plan: str | None = None, event_type: str | None = None,
              since: float | None = None, limit: int = 100) -> list[dict]:
        q = "SELECT * FROM evidence_spine WHERE 1=1"
        params: list[Any] = []
        if source_plan: q += " AND source_plan = ?"; params.append(source_plan)
        if event_type:  q += " AND event_type = ?";  params.append(event_type)
        if since:       q += " AND timestamp >= ?";  params.append(since)
        q += " ORDER BY timestamp ASC LIMIT ?"; params.append(limit)
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def verify_chain(self) -> tuple[bool, str]:
        rows = self._conn.execute(
            "SELECT entry_id, payload, prev_hash, hash, timestamp FROM evidence_spine ORDER BY timestamp ASC, rowid ASC"
        ).fetchall()

        if not rows:
            return True, "empty spine — valid"

        expected_prev = GENESIS_PREV_HASH
        for i, row in enumerate(rows):
            if row["prev_hash"] != expected_prev:
                return False, f"chain break at entry {row['entry_id'][:12]} (index {i}): expected prev={expected_prev[:12]}, got {row['prev_hash'][:12]}"

            computed = _compute_chain_hash(row["entry_id"], row["payload"], row["prev_hash"], row["timestamp"])
            if computed != row["hash"]:
                return False, f"hash mismatch at entry {row['entry_id'][:12]} (index {i})"

            expected_prev = row["hash"]

        return True, f"chain valid ({len(rows)} entries)"

    def replay(self, since: float | None = None) -> list[dict]:
        """Replay evidence entries since timestamp."""
        return self.query(since=since, limit=100000)


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_spine: EvidenceSpine | None = None

def get_evidence_spine(db_path: str | Path | None = None,
                       event_bus: EventBus | None = None) -> EvidenceSpine:
    global _spine
    if _spine is None:
        _spine = EvidenceSpine(db_path, event_bus)
    return _spine
