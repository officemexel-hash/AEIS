"""
SYLION Governance — Evidence Packs

Enhanced evidence pack management for D3+ decisions.
Evidence Packs are required for every D3+ decision and anchor to the
Evidence Spine via hash-chain for tamper-evident immutability.

Schema: pack_id, proposal_id, decision_class, status, artefacts,
        fidelity_score, created_at, validated_at, validation_hash

Lifecycle: draft -> submitted -> validated -> archived
- Packs can only be submitted when they have >= 1 artefact.
- Packs can only be validated when status is "submitted".
- Validation anchors the pack to the EvidenceSpine.
- Once validated, the pack is immutable (status -> archived).

Fidelity = (artefacts_present / artefacts_expected) * hash_chain_integrity
- D3 decisions need >= 3 artefacts, D4 >= 5, D5 >= 7
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
from sylion.core.evidence_spine import EvidenceSpine, EvidenceEntry

log = logging.getLogger("sylion.governance.evidence_packs")

# Minimum artefact counts by decision class
ARTEFACTS_REQUIRED: dict[str, int] = {
    "D0": 0,
    "D1": 0,
    "D2": 1,
    "D3": 3,
    "D4": 5,
    "D5": 7,
}

VALID_STATUSES = ("draft", "submitted", "validated", "archived")

ARTEFACT_TYPES = (
    "test_result",
    "metric_snapshot",
    "contract_snapshot",
    "log_excerpt",
    "decision_record",
)

# Status transition map: current_status -> set of allowed next statuses
_TRANSITIONS: dict[str, set[str]] = {
    "draft":     {"submitted"},
    "submitted": {"validated"},
    "validated": {"archived"},
    "archived":  set(),  # immutable
}


@dataclass
class EvidenceArtefact:
    artefact_id: str = ""
    pack_id: str = ""
    name: str = ""
    type: str = ""  # test_result, metric_snapshot, contract_snapshot, log_excerpt, decision_record
    content_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.artefact_id:
            self.artefact_id = uuid.uuid4().hex


@dataclass
class EvidencePack:
    pack_id: str = ""
    proposal_id: str = ""
    decision_class: str = ""  # D0-D5
    status: str = "draft"  # draft, submitted, validated, archived
    artefacts: list[EvidenceArtefact] = field(default_factory=list)
    fidelity_score: float = 0.0  # 0.0-1.0
    created_at: float = 0.0
    validated_at: float = 0.0
    validation_hash: str = ""  # hash-chain anchor

    def __post_init__(self):
        if not self.pack_id:
            self.pack_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


class EvidencePackManager:
    """Manages evidence packs for governance decisions.

    SQLite-backed, thread-safe. Integrates with EvidenceSpine for
    hash-chain anchoring upon validation.
    """

    def __init__(self, evidence_spine: EvidenceSpine | None = None,
                 event_bus: EventBus | None = None,
                 db_path: str | Path | None = None):
        self._spine = evidence_spine
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS evidence_packs_v2 (
                pack_id         TEXT PRIMARY KEY,
                proposal_id     TEXT NOT NULL,
                decision_class  TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'draft',
                fidelity_score  REAL NOT NULL DEFAULT 0.0,
                created_at      REAL NOT NULL,
                validated_at    REAL NOT NULL DEFAULT 0.0,
                validation_hash TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS evidence_artefacts_v2 (
                artefact_id  TEXT PRIMARY KEY,
                pack_id      TEXT NOT NULL,
                name         TEXT NOT NULL,
                type         TEXT NOT NULL,
                content_hash TEXT NOT NULL DEFAULT '',
                metadata     TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (pack_id) REFERENCES evidence_packs_v2(pack_id)
            );
            CREATE INDEX IF NOT EXISTS idx_epv2_proposal ON evidence_packs_v2(proposal_id);
            CREATE INDEX IF NOT EXISTS idx_epv2_status  ON evidence_packs_v2(status);
            CREATE INDEX IF NOT EXISTS idx_epv2_class   ON evidence_packs_v2(decision_class);
            CREATE INDEX IF NOT EXISTS idx_eav2_pack    ON evidence_artefacts_v2(pack_id);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def create_pack(self, proposal_id: str, decision_class: str) -> EvidencePack:
        """Create a new evidence pack in draft status."""
        if decision_class not in ARTEFACTS_REQUIRED:
            raise ValueError(f"Invalid decision_class: {decision_class}")

        pack = EvidencePack(
            proposal_id=proposal_id,
            decision_class=decision_class,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO evidence_packs_v2
                    (pack_id, proposal_id, decision_class, status, fidelity_score,
                     created_at, validated_at, validation_hash)
                VALUES (?,?,?,?,?,?,?,?)
            """, (pack.pack_id, pack.proposal_id, pack.decision_class,
                  pack.status, pack.fidelity_score,
                  pack.created_at, pack.validated_at, pack.validation_hash))
            self._conn.commit()

        self._emit("evidence_pack.created", {
            "pack_id": pack.pack_id,
            "proposal_id": proposal_id,
            "decision_class": decision_class,
        })

        log.info("pack created: %s (proposal=%s, class=%s)",
                 pack.pack_id[:12], proposal_id, decision_class)
        return pack

    def add_artefact(self, pack_id: str, name: str, type: str,
                     content_hash: str, metadata: dict[str, Any] | None = None) -> EvidenceArtefact:
        """Add an artefact to a pack. Only allowed in draft status."""
        with self._lock:
            row = self._conn.execute(
                "SELECT status FROM evidence_packs_v2 WHERE pack_id = ?", (pack_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Pack not found: {pack_id}")
            if row["status"] != "draft":
                raise RuntimeError(
                    f"Cannot add artefact to pack in '{row['status']}' status; must be 'draft'"
                )

        if type not in ARTEFACT_TYPES:
            raise ValueError(f"Invalid artefact type: {type}. Must be one of {ARTEFACT_TYPES}")

        artefact = EvidenceArtefact(
            pack_id=pack_id,
            name=name,
            type=type,
            content_hash=content_hash,
            metadata=metadata or {},
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO evidence_artefacts_v2
                    (artefact_id, pack_id, name, type, content_hash, metadata)
                VALUES (?,?,?,?,?,?)
            """, (artefact.artefact_id, pack_id, name, type,
                  content_hash, json.dumps(artefact.metadata, sort_keys=True, default=str)))
            self._conn.commit()

        self._emit("evidence_pack.artefact_added", {
            "pack_id": pack_id,
            "artefact_id": artefact.artefact_id,
        })

        log.info("artefact added: %s to pack %s (type=%s)",
                 artefact.artefact_id[:12], pack_id[:12], type)
        return artefact

    def submit_pack(self, pack_id: str) -> dict:
        """Freeze a pack: transition draft -> submitted. Computes fidelity."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM evidence_packs_v2 WHERE pack_id = ?", (pack_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Pack not found: {pack_id}")

            current_status = row["status"]
            if current_status != "draft":
                raise RuntimeError(
                    f"Cannot submit pack in '{current_status}' status; must be 'draft'"
                )

        # Count artefacts
        with self._lock:
            count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM evidence_artefacts_v2 WHERE pack_id = ?",
                (pack_id,)
            ).fetchone()["cnt"]

        if count < 1:
            raise RuntimeError(
                f"Cannot submit pack with {count} artefacts; minimum is 1"
            )

        fidelity = self._compute_fidelity_internal(pack_id)

        with self._lock:
            self._conn.execute("""
                UPDATE evidence_packs_v2
                SET status = 'submitted', fidelity_score = ?
                WHERE pack_id = ?
            """, (fidelity, pack_id))
            self._conn.commit()

        self._emit("evidence_pack.submitted", {
            "pack_id": pack_id,
            "fidelity_score": fidelity,
        })

        log.info("pack submitted: %s (fidelity=%.3f, artefacts=%d)",
                 pack_id[:12], fidelity, count)
        return {"pack_id": pack_id, "status": "submitted", "fidelity_score": fidelity}

    def validate_pack(self, pack_id: str, spine: EvidenceSpine | None = None) -> dict:
        """Validate a submitted pack and anchor it to the Evidence Spine.

        On success, transitions submitted -> archived (immutable).
        """
        spine = spine or self._spine

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM evidence_packs_v2 WHERE pack_id = ?", (pack_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Pack not found: {pack_id}")

            current_status = row["status"]
            if current_status != "submitted":
                raise RuntimeError(
                    f"Cannot validate pack in '{current_status}' status; must be 'submitted'"
                )

        # Fetch artefacts for hash computation
        with self._lock:
            artefact_rows = self._conn.execute(
                "SELECT * FROM evidence_artefacts_v2 WHERE pack_id = ? ORDER BY artefact_id",
                (pack_id,)
            ).fetchall()

        # Compute validation hash from all artefact content hashes
        hashes = sorted(r["content_hash"] for r in artefact_rows if r["content_hash"])
        hash_material = "|".join(hashes)
        validation_hash = hashlib.sha256(hash_material.encode("utf-8")).hexdigest()

        # Anchor to evidence spine
        spine_entry_id = ""
        spine_hash = ""
        now = time.time()

        if spine:
            entry = EvidenceEntry(
                source_plan="governance.evidence_packs",
                event_type="evidence_pack.validated",
                payload={
                    "pack_id": pack_id,
                    "proposal_id": row["proposal_id"],
                    "decision_class": row["decision_class"],
                    "artefact_count": len(artefact_rows),
                    "validation_hash": validation_hash,
                    "fidelity_score": row["fidelity_score"],
                },
            )
            result = spine.append(entry)
            spine_entry_id = result["entry_id"]
            spine_hash = result["hash"]

        # Transition to archived (immutable)
        with self._lock:
            self._conn.execute("""
                UPDATE evidence_packs_v2
                SET status = 'archived',
                    validated_at = ?,
                    validation_hash = ?
                WHERE pack_id = ?
            """, (now, validation_hash, pack_id))
            self._conn.commit()

        self._emit("evidence_pack.validated", {
            "pack_id": pack_id,
            "validation_hash": validation_hash,
            "spine_entry_id": spine_entry_id,
            "spine_hash": spine_hash,
        })

        log.info("pack validated & archived: %s (hash=%s, spine=%s)",
                 pack_id[:12], validation_hash[:16], spine_entry_id[:12] if spine_entry_id else "N/A")

        return {
            "pack_id": pack_id,
            "status": "archived",
            "validation_hash": validation_hash,
            "spine_entry_id": spine_entry_id,
            "spine_hash": spine_hash,
            "artefact_count": len(artefact_rows),
        }

    def get_pack(self, pack_id: str) -> dict | None:
        """Retrieve a pack with its artefacts."""
        row = self._conn.execute(
            "SELECT * FROM evidence_packs_v2 WHERE pack_id = ?", (pack_id,)
        ).fetchone()
        if not row:
            return None

        pack = dict(row)

        artefact_rows = self._conn.execute(
            "SELECT * FROM evidence_artefacts_v2 WHERE pack_id = ? ORDER BY artefact_id",
            (pack_id,)
        ).fetchall()
        pack["artefacts"] = [
            {
                "artefact_id": r["artefact_id"],
                "pack_id": r["pack_id"],
                "name": r["name"],
                "type": r["type"],
                "content_hash": r["content_hash"],
                "metadata": json.loads(r["metadata"]),
            }
            for r in artefact_rows
        ]
        return pack

    def list_packs(self, status: str | None = None,
                   decision_class: str | None = None) -> list[dict]:
        """List packs, optionally filtered by status and/or decision class."""
        q = """SELECT pack_id, proposal_id, decision_class, status,
                      fidelity_score, created_at, validated_at, validation_hash
               FROM evidence_packs_v2 WHERE 1=1"""
        params: list[Any] = []
        if status:
            q += " AND status = ?"
            params.append(status)
        if decision_class:
            q += " AND decision_class = ?"
            params.append(decision_class)
        q += " ORDER BY created_at DESC"
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def compute_fidelity(self, pack_id: str) -> float:
        """Public fidelity computation for a pack."""
        return self._compute_fidelity_internal(pack_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_fidelity_internal(self, pack_id: str) -> float:
        """Compute fidelity = (artefacts_present / artefacts_expected) * hash_integrity.

        hash_integrity = 1.0 if all artefacts have non-empty content_hash, else 0.5.
        """
        row = self._conn.execute(
            "SELECT decision_class FROM evidence_packs_v2 WHERE pack_id = ?", (pack_id,)
        ).fetchone()
        if not row:
            return 0.0

        expected = ARTEFACTS_REQUIRED.get(row["decision_class"], 1)
        if expected == 0:
            return 1.0  # No artefacts needed -> perfect fidelity

        artefact_rows = self._conn.execute(
            "SELECT content_hash FROM evidence_artefacts_v2 WHERE pack_id = ?",
            (pack_id,)
        ).fetchall()

        present = len(artefact_rows)
        with_hash = sum(1 for r in artefact_rows if r["content_hash"])

        completeness = min(present / expected, 1.0)
        hash_integrity = 1.0 if present == with_hash and with_hash > 0 else (0.5 if with_hash > 0 else 0.0)

        return round(completeness * hash_integrity, 6)

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="governance.evidence_packs",
            ))
