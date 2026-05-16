"""
SYLION AEIS -- Evidence Pack Collector (Phase 4)

Collects AEIS-specific evidence for decision-making from four subsystems:
  - Observation logs from self_observation
  - Proposal history from improvement_queue
  - Validation results from self_explanation
  - Boundary checks from self_limitation

Evidence packs are immutable after sealing. Each pack carries a decision_class
and optional context, and accumulates typed evidence items before verification.

SQLite-backed. Thread-safe via threading.Lock. Emits events via EventBus.
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

log = logging.getLogger("sylion.aeis.evidence_pack")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class EvidenceItem:
    """A single piece of evidence attached to a pack."""
    item_id: str = ""
    pack_id: str = ""
    evidence_type: str = ""          # observation | proposal | validation | boundary
    source: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    checksum: str = ""

    def __post_init__(self):
        if not self.item_id:
            self.item_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.checksum:
            self.checksum = _compute_checksum(self.pack_id, self.evidence_type,
                                              self.data, self.timestamp)


@dataclass
class EvidencePack:
    """Container for collected evidence bound to a decision."""
    pack_id: str = ""
    decision_class: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    sealed: int = 0                  # 0 = open, 1 = sealed (immutable)
    integrity_hash: str = ""
    created_at: float = 0.0
    sealed_at: float = 0.0

    def __post_init__(self):
        if not self.pack_id:
            self.pack_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_checksum(pack_id: str, evidence_type: str,
                      data: dict, timestamp: float) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    raw = f"{pack_id}|{evidence_type}|{canonical}|{timestamp}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _compute_integrity_hash(pack_id: str, items_json: str,
                            created_at: float) -> str:
    raw = f"{pack_id}|{items_json}|{created_at}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Evidence Pack Collector
# ---------------------------------------------------------------------------

class EvidencePackCollector:
    """Collects AEIS evidence into sealed, verifiable packs.

    Thread-safe. SQLite-backed. Emits events on create, add, seal.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_packs (
                pack_id         TEXT PRIMARY KEY,
                decision_class  TEXT    NOT NULL DEFAULT '',
                context         TEXT    NOT NULL DEFAULT '{}',
                sealed          INTEGER NOT NULL DEFAULT 0,
                integrity_hash  TEXT    NOT NULL DEFAULT '',
                created_at      REAL    NOT NULL,
                sealed_at       REAL    NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_items (
                item_id        TEXT PRIMARY KEY,
                pack_id        TEXT    NOT NULL,
                evidence_type  TEXT    NOT NULL,
                source         TEXT    NOT NULL DEFAULT '',
                data           TEXT    NOT NULL DEFAULT '{}',
                timestamp      REAL    NOT NULL,
                checksum       TEXT    NOT NULL DEFAULT '',
                FOREIGN KEY (pack_id) REFERENCES evidence_packs(pack_id)
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pack_decision "
            "ON evidence_packs(decision_class)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pack_sealed "
            "ON evidence_packs(sealed)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_item_pack "
            "ON evidence_items(pack_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_item_type "
            "ON evidence_items(evidence_type)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Create pack
    # ------------------------------------------------------------------

    def create_pack(self, decision_class: str,
                    context: dict[str, Any] | None = None) -> dict:
        """Create a new evidence pack for a decision class.

        Args:
            decision_class: Categorisation of the decision (e.g. "D3", "D4").
            context: Optional metadata dict for the pack.

        Returns:
            Dict with pack_id, decision_class, created_at.
        """
        if context is None:
            context = {}

        pack = EvidencePack(
            decision_class=decision_class,
            context=context,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO evidence_packs
                    (pack_id, decision_class, context, sealed,
                     integrity_hash, created_at, sealed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                pack.pack_id, pack.decision_class,
                json.dumps(context, default=str), pack.sealed,
                pack.integrity_hash, pack.created_at, pack.sealed_at,
            ))
            self._conn.commit()

        self._emit("aeis.evidence_pack.created", {
            "pack_id": pack.pack_id,
            "decision_class": decision_class,
        })

        log.info("created evidence pack %s for decision_class=%s",
                 pack.pack_id[:12], decision_class)
        return {
            "pack_id": pack.pack_id,
            "decision_class": decision_class,
            "created_at": pack.created_at,
        }

    # ------------------------------------------------------------------
    # Add observation evidence
    # ------------------------------------------------------------------

    def add_observation_evidence(self, pack_id: str,
                                  observation_data: dict[str, Any]) -> dict:
        """Add observation evidence from self_observation to a pack.

        Args:
            pack_id: Target pack ID.
            observation_data: Observation payload (metric, value, tags, ...).

        Returns:
            Dict with item_id, pack_id, evidence_type, checksum.
        """
        return self._add_item(pack_id, "observation",
                              source="self_observation",
                              data=observation_data)

    # ------------------------------------------------------------------
    # Add proposal evidence
    # ------------------------------------------------------------------

    def add_proposal_evidence(self, pack_id: str,
                               proposal_data: dict[str, Any]) -> dict:
        """Add proposal evidence from improvement_queue to a pack.

        Args:
            pack_id: Target pack ID.
            proposal_data: Improvement proposal payload.

        Returns:
            Dict with item_id, pack_id, evidence_type, checksum.
        """
        return self._add_item(pack_id, "proposal",
                              source="improvement_queue",
                              data=proposal_data)

    # ------------------------------------------------------------------
    # Add validation evidence
    # ------------------------------------------------------------------

    def add_validation_evidence(self, pack_id: str,
                                 validation_data: dict[str, Any]) -> dict:
        """Add validation evidence from self_explanation to a pack.

        Args:
            pack_id: Target pack ID.
            validation_data: Explanation validation payload.

        Returns:
            Dict with item_id, pack_id, evidence_type, checksum.
        """
        return self._add_item(pack_id, "validation",
                              source="self_explanation",
                              data=validation_data)

    # ------------------------------------------------------------------
    # Internal: add item
    # ------------------------------------------------------------------

    def _add_item(self, pack_id: str, evidence_type: str,
                  source: str, data: dict[str, Any]) -> dict:
        with self._lock:
            # Verify pack exists and is not sealed
            pack_row = self._conn.execute(
                "SELECT sealed FROM evidence_packs WHERE pack_id = ?",
                (pack_id,),
            ).fetchone()
            if not pack_row:
                raise ValueError(f"pack {pack_id} not found")
            if pack_row["sealed"]:
                raise ValueError(f"pack {pack_id} is sealed — cannot add items")

            item = EvidenceItem(
                pack_id=pack_id,
                evidence_type=evidence_type,
                source=source,
                data=data,
            )

            self._conn.execute("""
                INSERT INTO evidence_items
                    (item_id, pack_id, evidence_type, source, data, timestamp, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                item.item_id, item.pack_id, item.evidence_type,
                item.source, json.dumps(data, default=str),
                item.timestamp, item.checksum,
            ))
            self._conn.commit()

        topic = f"aeis.evidence_pack.item_added"
        self._emit(topic, {
            "item_id": item.item_id,
            "pack_id": pack_id,
            "evidence_type": evidence_type,
        })

        log.info("added %s evidence %s to pack %s",
                 evidence_type, item.item_id[:12], pack_id[:12])
        return {
            "item_id": item.item_id,
            "pack_id": pack_id,
            "evidence_type": evidence_type,
            "checksum": item.checksum,
        }

    # ------------------------------------------------------------------
    # Get pack
    # ------------------------------------------------------------------

    def get_pack(self, pack_id: str) -> dict | None:
        """Retrieve a full evidence pack with all its items.

        Returns:
            Dict with pack metadata and ``items`` list, or None.
        """
        pack_row = self._conn.execute(
            "SELECT * FROM evidence_packs WHERE pack_id = ?",
            (pack_id,),
        ).fetchone()
        if not pack_row:
            return None

        pack = dict(pack_row)
        pack["context"] = json.loads(pack.get("context", "{}"))

        item_rows = self._conn.execute(
            "SELECT * FROM evidence_items WHERE pack_id = ? ORDER BY timestamp ASC",
            (pack_id,),
        ).fetchall()

        items = []
        for r in item_rows:
            d = dict(r)
            d["data"] = json.loads(d.get("data", "{}"))
            items.append(d)

        pack["items"] = items
        return pack

    # ------------------------------------------------------------------
    # List packs
    # ------------------------------------------------------------------

    def list_packs(self, decision_class: str | None = None,
                   limit: int = 100) -> list[dict]:
        """List evidence packs, optionally filtered by decision class.

        Args:
            decision_class: Optional filter (e.g. "D3").
            limit: Maximum packs to return.

        Returns:
            List of pack dicts (without items).
        """
        q = "SELECT * FROM evidence_packs WHERE 1=1"
        params: list[Any] = []
        if decision_class:
            q += " AND decision_class = ?"
            params.append(decision_class)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(q, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["context"] = json.loads(d.get("context", "{}"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Verify pack integrity
    # ------------------------------------------------------------------

    def verify_pack_integrity(self, pack_id: str) -> dict:
        """Verify the integrity of a pack by recomputing checksums.

        Returns:
            Dict with valid (bool), item_count, mismatches list.
        """
        pack_row = self._conn.execute(
            "SELECT * FROM evidence_packs WHERE pack_id = ?",
            (pack_id,),
        ).fetchone()
        if not pack_row:
            return {"valid": False, "error": "pack not found"}

        item_rows = self._conn.execute(
            "SELECT * FROM evidence_items WHERE pack_id = ? ORDER BY timestamp ASC",
            (pack_id,),
        ).fetchall()

        mismatches: list[str] = []

        for row in item_rows:
            data = json.loads(row["data"])
            expected = _compute_checksum(
                row["pack_id"], row["evidence_type"],
                data, row["timestamp"],
            )
            if expected != row["checksum"]:
                mismatches.append(row["item_id"])

        if pack_row["sealed"]:
            # Verify sealed integrity hash
            items_json = json.dumps(
                [dict(r) for r in item_rows],
                sort_keys=True, separators=(",", ":"), default=str,
            )
            expected_integrity = _compute_integrity_hash(
                pack_id, items_json, pack_row["created_at"],
            )
            if expected_integrity != pack_row["integrity_hash"]:
                mismatches.append(f"integrity_hash mismatch for pack {pack_id}")

        return {
            "valid": len(mismatches) == 0,
            "pack_id": pack_id,
            "item_count": len(item_rows),
            "mismatches": mismatches,
        }

    # ------------------------------------------------------------------
    # Seal pack
    # ------------------------------------------------------------------

    def seal_pack(self, pack_id: str) -> dict:
        """Seal a pack, making it immutable.

        Computes and stores an integrity hash over all items.
        Sealed packs reject further item additions.

        Returns:
            Dict with pack_id, integrity_hash, sealed_at.
        """
        with self._lock:
            pack_row = self._conn.execute(
                "SELECT * FROM evidence_packs WHERE pack_id = ?",
                (pack_id,),
            ).fetchone()
            if not pack_row:
                raise ValueError(f"pack {pack_id} not found")
            if pack_row["sealed"]:
                raise ValueError(f"pack {pack_id} is already sealed")

            item_rows = self._conn.execute(
                "SELECT * FROM evidence_items WHERE pack_id = ? ORDER BY timestamp ASC",
                (pack_id,),
            ).fetchall()

            items_json = json.dumps(
                [dict(r) for r in item_rows],
                sort_keys=True, separators=(",", ":"), default=str,
            )
            integrity_hash = _compute_integrity_hash(
                pack_id, items_json, pack_row["created_at"],
            )
            now = time.time()

            self._conn.execute("""
                UPDATE evidence_packs
                SET sealed = 1, integrity_hash = ?, sealed_at = ?
                WHERE pack_id = ?
            """, (integrity_hash, now, pack_id))
            self._conn.commit()

        self._emit("aeis.evidence_pack.sealed", {
            "pack_id": pack_id,
            "integrity_hash": integrity_hash,
        })

        log.info("sealed evidence pack %s with integrity_hash=%s",
                 pack_id[:12], integrity_hash[:12])
        return {
            "pack_id": pack_id,
            "integrity_hash": integrity_hash,
            "sealed_at": now,
        }

    # ------------------------------------------------------------------
    # Add boundary evidence (self_limitation)
    # ------------------------------------------------------------------

    def add_boundary_evidence(self, pack_id: str,
                               boundary_data: dict[str, Any]) -> dict:
        """Add boundary-check evidence from self_limitation to a pack.

        Args:
            pack_id: Target pack ID.
            boundary_data: Rate-limit / boundary check payload.

        Returns:
            Dict with item_id, pack_id, evidence_type, checksum.
        """
        return self._add_item(pack_id, "boundary",
                              source="self_limitation",
                              data=boundary_data)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate evidence pack statistics.

        Returns:
            Dict with total_packs, total_items, by_decision_class,
            by_evidence_type, sealed_count, open_count.
        """
        total_packs = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM evidence_packs"
        ).fetchone()["cnt"]

        total_items = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM evidence_items"
        ).fetchone()["cnt"]

        sealed_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM evidence_packs WHERE sealed = 1"
        ).fetchone()["cnt"]

        dc_rows = self._conn.execute(
            "SELECT decision_class, COUNT(*) as cnt "
            "FROM evidence_packs GROUP BY decision_class"
        ).fetchall()
        by_decision_class = {r["decision_class"]: r["cnt"] for r in dc_rows}

        type_rows = self._conn.execute(
            "SELECT evidence_type, COUNT(*) as cnt "
            "FROM evidence_items GROUP BY evidence_type"
        ).fetchall()
        by_evidence_type = {r["evidence_type"]: r["cnt"] for r in type_rows}

        return {
            "total_packs": total_packs,
            "total_items": total_items,
            "sealed_count": sealed_count,
            "open_count": total_packs - sealed_count,
            "by_decision_class": by_decision_class,
            "by_evidence_type": by_evidence_type,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.evidence_pack",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_collector: EvidencePackCollector | None = None


def get_evidence_pack_collector(db_path: str | Path | None = None,
                                 event_bus: EventBus | None = None) -> EvidencePackCollector:
    """Return the global EvidencePackCollector singleton."""
    global _collector
    if _collector is None:
        _collector = EvidencePackCollector(db_path, event_bus)
    return _collector
