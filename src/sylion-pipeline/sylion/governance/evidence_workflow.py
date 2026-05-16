"""
SYLION Governance — Evidence Workflow

Evidence pack assembly, validation, and lifecycle management.
Evidence packs are required for D2+ decisions and are stored in Evidence Spine.

Evidence pack = collection of artefacts with hash chain integrity.
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

log = logging.getLogger("sylion.governance.evidence_workflow")


@dataclass
class EvidenceArtefact:
    artefact_id: str = ""
    name: str = ""
    artefact_type: str = ""      # test_result | benchmark | review | screenshot | log | contract
    content_hash: str = ""
    description: str = ""
    source: str = ""
    created_at: float = 0.0

    def __post_init__(self):
        if not self.artefact_id:
            self.artefact_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()

    def compute_hash(self, content: str) -> str:
        self.content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return self.content_hash


@dataclass
class EvidencePack:
    pack_id: str = ""
    proposal_id: str = ""
    decision_class: str = ""      # D0-D5
    artefacts: list[EvidenceArtefact] = field(default_factory=list)
    pack_hash: str = ""
    status: str = "draft"         # draft → validated → submitted → archived
    created_by: str = ""
    created_at: float = 0.0

    def __post_init__(self):
        if not self.pack_id:
            self.pack_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()

    def compute_pack_hash(self) -> str:
        hashes = sorted(a.content_hash for a in self.artefacts if a.content_hash)
        raw = "|".join(hashes)
        self.pack_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.pack_hash


class EvidenceWorkflow:
    """Evidence pack assembly and validation workflow."""

    REQUIRED_BY_CLASS = {
        "D2": ["test_result"],
        "D3": ["test_result", "benchmark", "review"],
        "D4": ["test_result", "benchmark", "review", "contract"],
        "D5": ["test_result", "benchmark", "review", "contract", "log"],
    }

    def __init__(self, evidence_spine: EvidenceSpine | None = None,
                 event_bus: EventBus | None = None,
                 db_path: str | Path | None = None):
        self._evidence_spine = evidence_spine
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_packs (
                pack_id        TEXT PRIMARY KEY,
                proposal_id    TEXT NOT NULL,
                decision_class TEXT NOT NULL DEFAULT '',
                pack_hash      TEXT NOT NULL DEFAULT '',
                status         TEXT NOT NULL DEFAULT 'draft',
                created_by     TEXT NOT NULL DEFAULT '',
                created_at     REAL NOT NULL,
                validated_at   REAL NOT NULL DEFAULT 0,
                artefacts_json TEXT NOT NULL DEFAULT '[]'
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_packs_proposal ON evidence_packs(proposal_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_packs_status ON evidence_packs(status)")
        self._conn.commit()

    def create_pack(self, proposal_id: str, decision_class: str,
                    created_by: str = "") -> dict:
        pack = EvidencePack(proposal_id=proposal_id, decision_class=decision_class,
                            created_by=created_by)
        with self._lock:
            self._conn.execute("""
                INSERT INTO evidence_packs (pack_id, proposal_id, decision_class, pack_hash,
                                            status, created_by, created_at, artefacts_json)
                VALUES (?,?,?,?,?,?,?,?)
            """, (pack.pack_id, pack.proposal_id, pack.decision_class, "",
                  pack.status, pack.created_by, pack.created_at, "[]"))
            self._conn.commit()

        self._emit("evidence.pack_created", {"pack_id": pack.pack_id, "proposal_id": proposal_id})
        return {"pack_id": pack.pack_id, "status": pack.status}

    def add_artefact(self, pack_id: str, artefact: EvidenceArtefact) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT artefacts_json FROM evidence_packs WHERE pack_id = ?", (pack_id,)
            ).fetchone()
            if not row:
                return {"added": False, "message": "Pack not found"}

            artefacts = json.loads(row["artefacts_json"])
            artefacts.append({
                "artefact_id": artefact.artefact_id,
                "name": artefact.name,
                "type": artefact.artefact_type,
                "hash": artefact.content_hash,
                "description": artefact.description,
            })

            # Recompute pack hash
            hashes = sorted(a["hash"] for a in artefacts if a["hash"])
            pack_hash = hashlib.sha256("|".join(hashes).encode("utf-8")).hexdigest() if hashes else ""

            self._conn.execute(
                "UPDATE evidence_packs SET artefacts_json = ?, pack_hash = ? WHERE pack_id = ?",
                (json.dumps(artefacts), pack_hash, pack_id)
            )
            self._conn.commit()

        return {"added": True, "artefact_id": artefact.artefact_id, "pack_hash": pack_hash}

    def validate_pack(self, pack_id: str) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM evidence_packs WHERE pack_id = ?", (pack_id,)
            ).fetchone()
        if not row:
            return {"valid": False, "message": "Pack not found"}

        artefacts = json.loads(row["artefacts_json"])
        decision_class = row["decision_class"]
        required = self.REQUIRED_BY_CLASS.get(decision_class, [])
        present_types = {a["type"] for a in artefacts}
        missing = [t for t in required if t not in present_types]

        # All artefacts must have content hashes
        no_hash = [a["name"] for a in artefacts if not a["hash"]]

        valid = len(missing) == 0 and len(no_hash) == 0

        if valid:
            with self._lock:
                self._conn.execute(
                    "UPDATE evidence_packs SET status = 'validated', validated_at = ? WHERE pack_id = ?",
                    (time.time(), pack_id)
                )
                self._conn.commit()

        return {
            "pack_id": pack_id,
            "valid": valid,
            "artefacts_count": len(artefacts),
            "missing_types": missing,
            "no_hash": no_hash,
            "status": "validated" if valid else row["status"],
        }

    def submit_pack(self, pack_id: str) -> dict:
        validation = self.validate_pack(pack_id)
        if not validation["valid"]:
            return {"submitted": False, "message": "Pack validation failed", "details": validation}

        with self._lock:
            self._conn.execute(
                "UPDATE evidence_packs SET status = 'submitted' WHERE pack_id = ?",
                (pack_id,)
            )
            self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM evidence_packs WHERE pack_id = ?", (pack_id,)
        ).fetchone()

        if self._evidence_spine:
            self._evidence_spine.append(EvidenceEntry(
                source_plan="governance.evidence_workflow",
                event_type="evidence_pack.submitted",
                payload={"pack_id": pack_id, "pack_hash": row["pack_hash"],
                         "artefacts_count": len(json.loads(row["artefacts_json"]))},
            ))

        self._emit("evidence.pack_submitted", {"pack_id": pack_id})
        return {"submitted": True, "pack_id": pack_id}

    def get_pack(self, pack_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM evidence_packs WHERE pack_id = ?", (pack_id,)
        ).fetchone()
        result = dict(row) if row else None
        if result:
            result["artefacts"] = json.loads(result.pop("artefacts_json", "[]"))
        return result

    def list_packs(self, proposal_id: str | None = None,
                   status: str | None = None) -> list[dict]:
        q = "SELECT pack_id, proposal_id, decision_class, pack_hash, status, created_by, created_at FROM evidence_packs WHERE 1=1"
        params: list[Any] = []
        if proposal_id:
            q += " AND proposal_id = ?"; params.append(proposal_id)
        if status:
            q += " AND status = ?"; params.append(status)
        q += " ORDER BY created_at DESC"
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="governance.evidence_workflow",
            ))


_evidence_wf: EvidenceWorkflow | None = None

def get_evidence_workflow(evidence_spine: EvidenceSpine | None = None,
                          event_bus: EventBus | None = None,
                          db_path: str | Path | None = None) -> EvidenceWorkflow:
    global _evidence_wf
    if _evidence_wf is None:
        _evidence_wf = EvidenceWorkflow(evidence_spine, event_bus, db_path)
    return _evidence_wf
