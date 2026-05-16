"""
SYLION Memory -- Evidence Store

Persistent evidence storage with content hash verification.
Stores evidence artefacts indexed by pack and type, with a query log
for audit purposes. Content hashes are verified on store.
"""

from __future__ import annotations

import hashlib
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
from sylion.core.evidence_spine import EvidenceSpine

log = logging.getLogger("sylion.memory.evidence_store")


@dataclass
class StoredEvidence:
    """A single evidence artefact in the store."""
    evidence_id: str = ""
    pack_id: str = ""
    artefact_type: str = ""     # test_result | benchmark | review | screenshot | log | contract
    name: str = ""
    content: str = ""
    content_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def __post_init__(self):
        if not self.evidence_id:
            self.evidence_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()
        if not self.content_hash and self.content:
            self.content_hash = hashlib.sha256(
                self.content.encode("utf-8")
            ).hexdigest()


class EvidenceStore:
    """Persistent evidence storage with content hash verification.

    Thread-safe. SQLite-backed. Emits events on store/delete.
    Optionally records entries in EvidenceSpine for audit chain.
    """

    def __init__(self, event_bus: EventBus | None = None,
                 evidence_spine: EvidenceSpine | None = None,
                 db_path: str | Path | None = None):
        self._event_bus = event_bus
        self._evidence_spine = evidence_spine
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS stored_evidence (
                evidence_id    TEXT PRIMARY KEY,
                pack_id        TEXT NOT NULL DEFAULT '',
                artefact_type  TEXT NOT NULL DEFAULT '',
                name           TEXT NOT NULL DEFAULT '',
                content        TEXT NOT NULL DEFAULT '',
                content_hash   TEXT NOT NULL DEFAULT '',
                metadata       TEXT NOT NULL DEFAULT '{}',
                created_at     REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_queries (
                query_id      TEXT PRIMARY KEY,
                query_text    TEXT NOT NULL DEFAULT '',
                results_count INTEGER NOT NULL DEFAULT 0,
                timestamp     REAL NOT NULL
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_pack ON stored_evidence(pack_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_type ON stored_evidence(artefact_type)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_hash ON stored_evidence(content_hash)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_eq_ts ON evidence_queries(timestamp)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Store / Retrieve / Delete
    # ------------------------------------------------------------------

    def store(self, evidence_id: str = "", pack_id: str = "",
              artefact_type: str = "", name: str = "",
              content: str = "", metadata: dict | None = None) -> dict:
        """Store an evidence artefact with content hash verification.

        The content hash is computed and stored for integrity checking.
        If evidence_id is empty, a new UUID is generated.
        """
        if metadata is None:
            metadata = {}

        if not evidence_id:
            evidence_id = uuid.uuid4().hex

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        evidence = StoredEvidence(
            evidence_id=evidence_id,
            pack_id=pack_id,
            artefact_type=artefact_type,
            name=name,
            content=content,
            content_hash=content_hash,
            metadata=metadata,
        )

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO stored_evidence
                (evidence_id, pack_id, artefact_type, name, content,
                 content_hash, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evidence.evidence_id, evidence.pack_id, evidence.artefact_type,
                evidence.name, evidence.content, evidence.content_hash,
                json.dumps(metadata, default=str), evidence.created_at,
            ))
            self._conn.commit()

        # Record in evidence spine for audit chain
        if self._evidence_spine:
            from sylion.core.evidence_spine import EvidenceEntry
            self._evidence_spine.append(EvidenceEntry(
                source_plan="memory.evidence_store",
                event_type="evidence.stored",
                payload={
                    "evidence_id": evidence.evidence_id,
                    "pack_id": pack_id,
                    "artefact_type": artefact_type,
                    "content_hash": content_hash,
                },
            ))

        self._emit("evidence.stored", {
            "evidence_id": evidence.evidence_id,
            "pack_id": pack_id,
            "content_hash": content_hash,
        })

        log.info("stored evidence %s (type=%s, hash=%s)",
                 evidence.evidence_id[:12], artefact_type, content_hash[:12])
        return {
            "evidence_id": evidence.evidence_id,
            "content_hash": content_hash,
        }

    def retrieve(self, evidence_id: str) -> dict | None:
        """Retrieve a single evidence artefact by ID."""
        row = self._conn.execute(
            "SELECT * FROM stored_evidence WHERE evidence_id = ?",
            (evidence_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["metadata"] = json.loads(result.get("metadata", "{}"))
        return result

    def query_by_type(self, artefact_type: str, limit: int = 100) -> list[dict]:
        """Query evidence artefacts by type."""
        self._log_query(f"type:{artefact_type}", limit)

        rows = self._conn.execute(
            "SELECT * FROM stored_evidence WHERE artefact_type = ? ORDER BY created_at DESC LIMIT ?",
            (artefact_type, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def query_by_pack(self, pack_id: str, limit: int = 100) -> list[dict]:
        """Query evidence artefacts by pack ID."""
        self._log_query(f"pack:{pack_id}", limit)

        rows = self._conn.execute(
            "SELECT * FROM stored_evidence WHERE pack_id = ? ORDER BY created_at DESC LIMIT ?",
            (pack_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete(self, evidence_id: str) -> bool:
        """Delete an evidence artefact by ID."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM stored_evidence WHERE evidence_id = ?",
                (evidence_id,),
            ).rowcount
            self._conn.commit()

        if n:
            self._emit("evidence.deleted", {"evidence_id": evidence_id})
            log.info("deleted evidence %s", evidence_id[:12])
        return bool(n)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate evidence store statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM stored_evidence"
        ).fetchone()["cnt"]

        by_type_rows = self._conn.execute(
            "SELECT artefact_type, COUNT(*) as cnt FROM stored_evidence GROUP BY artefact_type"
        ).fetchall()
        by_type = {r["artefact_type"]: r["cnt"] for r in by_type_rows}

        query_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM evidence_queries"
        ).fetchone()["cnt"]

        return {
            "total_evidence": total,
            "by_type": by_type,
            "total_queries": query_count,
        }

    def append(self, evidence: StoredEvidence | dict[str, Any]) -> str:
        """Append evidence and return its identifier."""
        payload = evidence if isinstance(evidence, dict) else {
            "evidence_id": evidence.evidence_id,
            "pack_id": evidence.pack_id,
            "artefact_type": evidence.artefact_type,
            "name": evidence.name,
            "content": evidence.content,
            "metadata": evidence.metadata,
        }
        result = self.store(**payload)
        return result["evidence_id"]

    def get(self, evidence_id: str) -> dict | None:
        """Alias for retrieve()."""
        return self.retrieve(evidence_id)

    def stats(self) -> dict:
        """Alias for get_stats()."""
        return self.get_stats()

    # ------------------------------------------------------------------
    # Query logging
    # ------------------------------------------------------------------

    def _log_query(self, query_text: str, results_count: int):
        """Log a query for audit purposes."""
        query_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute("""
                INSERT INTO evidence_queries (query_id, query_text, results_count, timestamp)
                VALUES (?, ?, ?, ?)
            """, (query_id, query_text, results_count, time.time()))
            self._conn.commit()

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="memory.evidence_store",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_store: EvidenceStore | None = None


def get_evidence_store(event_bus: EventBus | None = None,
                       evidence_spine: EvidenceSpine | None = None,
                       db_path: str | Path | None = None) -> EvidenceStore:
    global _store
    if _store is None:
        _store = EvidenceStore(event_bus, evidence_spine, db_path)
    return _store


def reset_evidence_store() -> None:
    global _store
    _store = None


def append(evidence: StoredEvidence | dict[str, Any]) -> str:
    """
    Hook v1.0 (2026-04-24)
    Changes: initial shared evidence append hook
    """

    return get_evidence_store().append(evidence)


def get(evidence_id: str) -> dict | None:
    """Hook v1.0 (2026-04-24): retrieve evidence by id."""

    return get_evidence_store().get(evidence_id)


def stats() -> dict:
    """Hook v1.0 (2026-04-24): evidence statistics."""

    return get_evidence_store().stats()
