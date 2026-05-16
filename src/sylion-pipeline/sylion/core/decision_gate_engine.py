"""
SYLION Core — Decision Gate Engine

Classifies changes to D0–D5 and evaluates gates (G-*).
Foundation of the governance layer.

Decision ladder:
  D0 Informational  — auto, no human, no evidence
  D1 Trivial        — 1 agent, no human, no evidence
  D2 Standard       — 3/4 Board, no human, evidence recommended
  D3 Significant    — 4/4 Council, no human, evidence REQUIRED
  D4 Critical       — 4/4 + Human Gate, evidence REQUIRED + LPW
  D5 Greenfield     — 4/4 + Human + External, evidence REQUIRED + CFT

gRPC planned: EvaluateDecision, EvaluateGate, RegisterGate
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.core.decision_gate_engine")


class DecisionClass(str, Enum):
    D0 = "D0"  # Informational — auto
    D1 = "D1"  # Trivial — 1 agent
    D2 = "D2"  # Standard — 3/4 Board
    D3 = "D3"  # Significant — 4/4 Council
    D4 = "D4"  # Critical — Council + Human
    D5 = "D5"  # Greenfield — Council + Human + External


class GateResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    CONDITIONAL = "conditional"


# Decision requirements matrix
DECISION_REQUIREMENTS: dict[DecisionClass, dict[str, Any]] = {
    DecisionClass.D0: {"human": False, "council": False, "evidence": False, "retention_hot": "90d", "retention_cold": "2y"},
    DecisionClass.D1: {"human": False, "council": False, "evidence": False, "retention_hot": "90d", "retention_cold": "2y"},
    DecisionClass.D2: {"human": False, "council": "3/4", "evidence": "recommended", "retention_hot": "2y", "retention_cold": "infinite"},
    DecisionClass.D3: {"human": False, "council": "4/4", "evidence": "required", "retention_hot": "2y", "retention_cold": "infinite"},
    DecisionClass.D4: {"human": True, "council": "4/4", "evidence": "required", "retention_hot": "infinite", "retention_cold": "infinite"},
    DecisionClass.D5: {"human": True, "council": "4/4", "evidence": "required", "retention_hot": "infinite", "retention_cold": "infinite", "external": True},
}


@dataclass
class DecisionRequest:
    """Request to classify a decision."""
    description: str
    source_plan: str                     # e.g. "P06"
    module_id: str = ""                  # affected module
    change_type: str = ""                # config | contract | module | architecture | system
    blast_radius: str = "low"            # low | medium | high | critical
    reversible: bool = True
    affects_contracts: bool = False
    affects_kernel: bool = False
    proposed_by: str = ""


@dataclass
class DecisionRecord:
    """Recorded decision with classification."""
    decision_id: str
    decision_class: DecisionClass
    description: str
    source_plan: str
    module_id: str
    change_type: str
    blast_radius: str
    reversible: bool
    affects_contracts: bool
    affects_kernel: bool
    requirements: dict[str, Any]
    timestamp: float = 0.0
    status: str = "proposed"             # proposed → approved → executed

    def __post_init__(self):
        if not self.decision_id:
            self.decision_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class GateDefinition:
    """A registered gate (G-xxx)."""
    gate_id: str                         # e.g. "G-CUT-01"
    name: str
    description: str
    fail_condition: str                  # Human-readable
    blocks: str                          # What this gate blocks
    decision_class_min: DecisionClass = DecisionClass.D2
    owner_plan: str = ""
    enabled: bool = True


class DecisionGateEngine:
    """Classifies decisions D0–D5 and evaluates gates."""

    def __init__(self, db_path: str | Path | None = None, event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._gates: dict[str, GateDefinition] = {}
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()
        self._load_gates()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS decision_records (
                decision_id       TEXT PRIMARY KEY,
                decision_class    TEXT NOT NULL,
                description       TEXT NOT NULL,
                source_plan       TEXT NOT NULL,
                module_id         TEXT NOT NULL DEFAULT '',
                change_type       TEXT NOT NULL DEFAULT '',
                blast_radius      TEXT NOT NULL DEFAULT 'low',
                reversible        INTEGER NOT NULL DEFAULT 1,
                affects_contracts INTEGER NOT NULL DEFAULT 0,
                affects_kernel    INTEGER NOT NULL DEFAULT 0,
                requirements      TEXT NOT NULL DEFAULT '{}',
                timestamp         REAL NOT NULL,
                status            TEXT NOT NULL DEFAULT 'proposed'
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_class ON decision_records(decision_class)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_plan ON decision_records(source_plan)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_ts ON decision_records(timestamp)")

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS gate_definitions (
                gate_id           TEXT PRIMARY KEY,
                name              TEXT NOT NULL,
                description       TEXT NOT NULL DEFAULT '',
                fail_condition    TEXT NOT NULL DEFAULT '',
                blocks            TEXT NOT NULL DEFAULT '',
                decision_class_min TEXT NOT NULL DEFAULT 'D2',
                owner_plan        TEXT NOT NULL DEFAULT '',
                enabled           INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.commit()

    def _load_gates(self):
        rows = self._conn.execute("SELECT * FROM gate_definitions WHERE enabled = 1").fetchall()
        for r in rows:
            self._gates[r["gate_id"]] = GateDefinition(
                gate_id=r["gate_id"],
                name=r["name"],
                description=r["description"],
                fail_condition=r["fail_condition"],
                blocks=r["blocks"],
                decision_class_min=DecisionClass(r["decision_class_min"]),
                owner_plan=r["owner_plan"],
            )

    # --- Classification ---

    def classify(self, request: DecisionRequest) -> DecisionRecord:
        """Classify a decision request to D0–D5 based on rules."""
        dc = self._apply_rules(request)
        reqs = DECISION_REQUIREMENTS[dc]

        record = DecisionRecord(
            decision_id=uuid.uuid4().hex,
            decision_class=dc,
            description=request.description,
            source_plan=request.source_plan,
            module_id=request.module_id,
            change_type=request.change_type,
            blast_radius=request.blast_radius,
            reversible=request.reversible,
            affects_contracts=request.affects_contracts,
            affects_kernel=request.affects_kernel,
            requirements=reqs,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO decision_records
                (decision_id, decision_class, description, source_plan, module_id,
                 change_type, blast_radius, reversible, affects_contracts, affects_kernel,
                 requirements, timestamp, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                record.decision_id, record.decision_class.value, record.description,
                record.source_plan, record.module_id, record.change_type,
                record.blast_radius, int(record.reversible), int(record.affects_contracts),
                int(record.affects_kernel), json.dumps(reqs), record.timestamp, record.status,
            ))
            self._conn.commit()

        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic="decision.classified",
                payload={"decision_id": record.decision_id, "class": dc.value},
                source_module="core.decision_gate_engine",
            ))

        log.info("classified %s as %s", record.decision_id[:12], dc.value)
        return record

    def _apply_rules(self, req: DecisionRequest) -> DecisionClass:
        """Apply decision classification rules."""
        if req.affects_kernel:
            return DecisionClass.D5
        if req.affects_contracts:
            if req.blast_radius in ("high", "critical"):
                return DecisionClass.D4
            return DecisionClass.D3
        if req.blast_radius == "critical":
            return DecisionClass.D4 if not req.reversible else DecisionClass.D3
        if req.blast_radius == "high":
            return DecisionClass.D3 if not req.reversible else DecisionClass.D2
        if req.change_type == "architecture":
            return DecisionClass.D3
        if req.change_type == "module":
            return DecisionClass.D2
        if req.change_type == "config":
            return DecisionClass.D1
        return DecisionClass.D0

    # --- Gate management ---

    def register_gate(self, gate: GateDefinition) -> dict:
        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO gate_definitions
                (gate_id, name, description, fail_condition, blocks, decision_class_min, owner_plan, enabled)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                gate.gate_id, gate.name, gate.description, gate.fail_condition,
                gate.blocks, gate.decision_class_min.value, gate.owner_plan, int(gate.enabled),
            ))
            self._conn.commit()

        self._gates[gate.gate_id] = gate
        log.info("registered gate %s: %s", gate.gate_id, gate.name)
        return {"gate_id": gate.gate_id, "name": gate.name}

    def evaluate_gate(self, gate_id: str, context: dict | None = None) -> dict:
        """Evaluate a gate. Returns pass/fail with evidence."""
        gate = self._gates.get(gate_id)
        if not gate:
            return {"gate_id": gate_id, "result": GateResult.FAIL, "message": f"Gate {gate_id} not registered"}

        # Default pass — specific gate logic overrides in subclass or callback
        result = GateResult.PASS
        message = f"Gate {gate_id} ({gate.name}) passed"

        eval_result = {
            "gate_id": gate_id,
            "name": gate.name,
            "result": result,
            "message": message,
            "blocks": gate.blocks,
            "timestamp": time.time(),
        }

        # Capture snapshot after evaluation
        try:
            from sylion.governance.decision_snapshot import get_decision_snapshot
            snap = get_decision_snapshot()
            snap.capture_snapshot(
                decision_id=f"gate-{gate_id}-{eval_result['timestamp']:.0f}",
                gate_id=gate_id,
                choice_made=str(result),
                consequences={"evaluation": eval_result},
            )
        except Exception:
            pass

        return eval_result

    def get_decisions(self, decision_class: str | None = None,
                      source_plan: str | None = None) -> list[dict]:
        q = "SELECT * FROM decision_records WHERE 1=1"
        params: list[Any] = []
        if decision_class:
            q += " AND decision_class = ?"
            params.append(decision_class)
        if source_plan:
            q += " AND source_plan = ?"
            params.append(source_plan)
        q += " ORDER BY timestamp DESC"
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: DecisionGateEngine | None = None

def get_decision_engine(db_path: str | Path | None = None,
                        event_bus: EventBus | None = None) -> DecisionGateEngine:
    global _engine
    if _engine is None:
        _engine = DecisionGateEngine(db_path, event_bus)
    return _engine
