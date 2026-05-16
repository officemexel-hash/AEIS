"""
SYLION Governance — Decision Ladder

D0-D5 classification pipeline with evidence tracking.
Orchestrates the full decision lifecycle: propose → classify → review → approve → execute.

Decision classes:
  D0 Informational  — auto, no human, no evidence
  D1 Trivial        — 1 agent, no human, no evidence
  D2 Standard       — 3/4 Board, no human, evidence recommended
  D3 Significant    — 4/4 Council, no human, evidence REQUIRED
  D4 Critical       — 4/4 + Human Gate, evidence REQUIRED + LPW
  D5 Greenfield     — 4/4 + Human + External, evidence REQUIRED + CFT
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from sylion.core.decision_gate_engine import (
    DecisionClass, DecisionGateEngine, DecisionRequest, GateDefinition,
)
from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus
from sylion.core.evidence_spine import EvidenceSpine, EvidenceEntry

log = logging.getLogger("sylion.governance.decision_ladder")


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    CLASSIFIED = "classified"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DecisionProposal:
    proposal_id: str = ""
    title: str = ""
    description: str = ""
    source_plan: str = ""
    module_id: str = ""
    change_type: str = ""          # config | contract | module | architecture | system
    blast_radius: str = "low"      # low | medium | high | critical
    reversible: bool = True
    affects_contracts: bool = False
    affects_kernel: bool = False
    proposed_by: str = ""
    evidence_artefacts: list[str] = field(default_factory=list)
    rollback_plan: str = ""
    created_at: float = 0.0

    def __post_init__(self):
        if not self.proposal_id:
            self.proposal_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()

    def to_decision_request(self) -> DecisionRequest:
        return DecisionRequest(
            description=self.description,
            source_plan=self.source_plan,
            module_id=self.module_id,
            change_type=self.change_type,
            blast_radius=self.blast_radius,
            reversible=self.reversible,
            affects_contracts=self.affects_contracts,
            affects_kernel=self.affects_kernel,
            proposed_by=self.proposed_by,
        )


class DecisionLadder:
    """Full D0-D5 decision lifecycle manager.

    Uses DecisionGateEngine for classification, EvidenceSpine for audit,
    and EventBus for notifications.
    """

    def __init__(self, gate_engine: DecisionGateEngine | None = None,
                 evidence_spine: EvidenceSpine | None = None,
                 event_bus: EventBus | None = None,
                 db_path: str | Path | None = None):
        self._gate_engine = gate_engine or DecisionGateEngine()
        self._evidence_spine = evidence_spine
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS decision_proposals (
                proposal_id  TEXT PRIMARY KEY,
                title        TEXT NOT NULL DEFAULT '',
                description  TEXT NOT NULL,
                source_plan  TEXT NOT NULL,
                module_id    TEXT NOT NULL DEFAULT '',
                change_type  TEXT NOT NULL DEFAULT '',
                blast_radius TEXT NOT NULL DEFAULT 'low',
                reversible   INTEGER NOT NULL DEFAULT 1,
                affects_contracts INTEGER NOT NULL DEFAULT 0,
                affects_kernel    INTEGER NOT NULL DEFAULT 0,
                proposed_by  TEXT NOT NULL DEFAULT '',
                decision_class TEXT NOT NULL DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'proposed',
                evidence     TEXT NOT NULL DEFAULT '[]',
                rollback_plan TEXT NOT NULL DEFAULT '',
                created_at   REAL NOT NULL,
                classified_at REAL NOT NULL DEFAULT 0,
                resolved_at  REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_proposals_status ON decision_proposals(status)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_proposals_class ON decision_proposals(decision_class)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_proposals_plan ON decision_proposals(source_plan)")
        self._conn.commit()

    def propose(self, proposal: DecisionProposal) -> dict:
        """Submit a new decision proposal. Classifies and records it."""
        # Classify via gate engine
        request = proposal.to_decision_request()
        record = self._gate_engine.classify(request)
        decision_class = record.decision_class

        with self._lock:
            self._conn.execute("""
                INSERT INTO decision_proposals
                (proposal_id, title, description, source_plan, module_id, change_type,
                 blast_radius, reversible, affects_contracts, affects_kernel, proposed_by,
                 decision_class, status, evidence, rollback_plan, created_at, classified_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                proposal.proposal_id, proposal.title, proposal.description,
                proposal.source_plan, proposal.module_id, proposal.change_type,
                proposal.blast_radius, int(proposal.reversible),
                int(proposal.affects_contracts), int(proposal.affects_kernel),
                proposal.proposed_by, decision_class.value, DecisionStatus.CLASSIFIED.value,
                "[]", proposal.rollback_plan, proposal.created_at, time.time(),
            ))
            self._conn.commit()

        # Record in evidence spine
        if self._evidence_spine:
            self._evidence_spine.append(EvidenceEntry(
                source_plan=proposal.source_plan,
                event_type="decision.proposed",
                payload={
                    "proposal_id": proposal.proposal_id,
                    "decision_class": decision_class.value,
                    "title": proposal.title,
                },
            ))

        self._emit("decision.proposed", {
            "proposal_id": proposal.proposal_id,
            "decision_class": decision_class.value,
        })

        log.info("proposed %s: class=%s (%s)", proposal.proposal_id[:12], decision_class.value, proposal.title)
        return {
            "proposal_id": proposal.proposal_id,
            "decision_class": decision_class.value,
            "status": DecisionStatus.CLASSIFIED.value,
            "requirements": record.requirements,
        }

    def approve(self, proposal_id: str, approved_by: str = "", notes: str = "") -> dict:
        """Approve a classified proposal."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM decision_proposals WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
            if not row:
                return {"approved": False, "message": f"Proposal {proposal_id} not found"}
            if row["status"] != DecisionStatus.CLASSIFIED.value:
                return {"approved": False, "message": f"Proposal status is {row['status']}, not classified"}

            self._conn.execute(
                "UPDATE decision_proposals SET status = ?, resolved_at = ? WHERE proposal_id = ?",
                (DecisionStatus.APPROVED.value, time.time(), proposal_id),
            )
            self._conn.commit()

        if self._evidence_spine:
            self._evidence_spine.append(EvidenceEntry(
                source_plan=row["source_plan"],
                event_type="decision.approved",
                payload={"proposal_id": proposal_id, "approved_by": approved_by, "notes": notes},
            ))

        self._emit("decision.approved", {"proposal_id": proposal_id, "approved_by": approved_by})
        log.info("approved %s by %s", proposal_id[:12], approved_by)
        return {"approved": True, "proposal_id": proposal_id, "status": DecisionStatus.APPROVED.value}

    def reject(self, proposal_id: str, rejected_by: str = "", reason: str = "") -> dict:
        """Reject a classified proposal."""
        with self._lock:
            n = self._conn.execute(
                "UPDATE decision_proposals SET status = ?, resolved_at = ? WHERE proposal_id = ? AND status = ?",
                (DecisionStatus.REJECTED.value, time.time(), proposal_id, DecisionStatus.CLASSIFIED.value),
            ).rowcount
            self._conn.commit()

        if n == 0:
            return {"rejected": False, "message": f"Proposal {proposal_id} not found or not in classified state"}

        self._emit("decision.rejected", {"proposal_id": proposal_id, "rejected_by": rejected_by, "reason": reason})
        log.info("rejected %s by %s: %s", proposal_id[:12], rejected_by, reason)
        return {"rejected": True, "proposal_id": proposal_id}

    def execute(self, proposal_id: str) -> dict:
        """Mark an approved proposal as executed."""
        with self._lock:
            n = self._conn.execute(
                "UPDATE decision_proposals SET status = ?, resolved_at = ? WHERE proposal_id = ? AND status = ?",
                (DecisionStatus.EXECUTED.value, time.time(), proposal_id, DecisionStatus.APPROVED.value),
            ).rowcount
            self._conn.commit()

        if n == 0:
            return {"executed": False, "message": f"Proposal {proposal_id} not approved"}

        self._emit("decision.executed", {"proposal_id": proposal_id})
        return {"executed": True, "proposal_id": proposal_id}

    def get_proposal(self, proposal_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM decision_proposals WHERE proposal_id = ?", (proposal_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_proposals(self, status: str | None = None,
                       decision_class: str | None = None,
                       source_plan: str | None = None) -> list[dict]:
        q = "SELECT * FROM decision_proposals WHERE 1=1"
        params: list[Any] = []
        if status:
            q += " AND status = ?"; params.append(status)
        if decision_class:
            q += " AND decision_class = ?"; params.append(decision_class)
        if source_plan:
            q += " AND source_plan = ?"; params.append(source_plan)
        q += " ORDER BY created_at DESC"
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="governance.decision_ladder",
            ))


_ladder: DecisionLadder | None = None

def _audit_redirect(db_path: str | Path | None) -> str | Path | None:
    """Redirect persistent governance decisions into the active audit profile."""
    if db_path is not None and str(db_path) == ":memory:":
        return db_path
    from sylion.aeis_v2.audit_profile import is_audit_mode, resolve_db_path
    if not is_audit_mode():
        return db_path
    return resolve_db_path(Path(db_path) if db_path is not None else None)


def get_decision_ladder(gate_engine: DecisionGateEngine | None = None,
                        evidence_spine: EvidenceSpine | None = None,
                        event_bus: EventBus | None = None,
                        db_path: str | Path | None = None) -> DecisionLadder:
    global _ladder
    if _ladder is None:
        _ladder = DecisionLadder(gate_engine, evidence_spine, event_bus, _audit_redirect(db_path))
    return _ladder


def reset_decision_ladder(gate_engine: DecisionGateEngine | None = None,
                          evidence_spine: EvidenceSpine | None = None,
                          event_bus: EventBus | None = None,
                          db_path: str | Path | None = None) -> DecisionLadder:
    """Replace the process-wide ladder, used by app startup and audit tests."""
    global _ladder
    _ladder = DecisionLadder(gate_engine, evidence_spine, event_bus, _audit_redirect(db_path))
    return _ladder
