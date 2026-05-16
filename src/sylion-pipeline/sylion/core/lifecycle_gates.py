"""
SYLION Core -- Lifecycle Gates

Manages module lifecycle stage transitions with configurable gate checks.
Each stage has ordered gates that must pass before promotion.

Tables:
  lifecycle_stages  -- ordered stage definitions (draft, build, validate, ...)
  stage_gates       -- gates attached to stages with criteria as JSON
  gate_evaluations  -- evaluation results (pass/fail) for gate checks

Events:
  stage_defined     -- emitted when define_stage() creates a new stage
  gate_created      -- emitted when create_gate() attaches a gate to a stage
  gate_evaluated    -- emitted when evaluate_gate() runs a gate check
  promoted          -- emitted when promote() transitions a target to a new stage

Singleton: get_lifecycle_gates() / reset_lifecycle_gates()
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

log = logging.getLogger("sylion.core.lifecycle_gates")


@dataclass(frozen=True)
class GateRequirement:
    min_heartbeat_age_hours: float | None = None
    requires_evidence: bool = False
    evidence_type: str = ""
    evidence_aliases: list[str] = field(default_factory=list)
    min_duration_hours: float | None = None
    duration_from_stage: str = ""
    requires_council_approval: bool = False
    decision_class: str = ""


GATE_RULES: dict[str, GateRequirement] = {
    "validate": GateRequirement(min_heartbeat_age_hours=1),
    "shadow": GateRequirement(requires_evidence=True, evidence_type="validation_report"),
    "dual": GateRequirement(min_duration_hours=72, duration_from_stage="shadow"),
    "cutover": GateRequirement(
        min_duration_hours=48,
        duration_from_stage="dual",
        requires_council_approval=True,
        decision_class="D3",
    ),
    "stable": GateRequirement(
        min_duration_hours=24,
        duration_from_stage="cutover",
        requires_evidence=True,
        evidence_type="cutover_report",
        evidence_aliases=["cutover_complete"],
    ),
    "deprecated": GateRequirement(requires_council_approval=True, decision_class="D4"),
}


class LifecycleGateEnforcer:
    """Runtime enforcer for module lifecycle transitions.

    This complements the SQLite CRUD-oriented LifecycleGates service with the
    canonical gate policy expected by the module registry tests.
    """

    def __init__(self, council: Any | None = None, spine: Any | None = None):
        self._council = council
        self._spine = spine
        self._stage_entries: dict[tuple[str, str], float] = {}

    def record_stage_entry(
        self,
        module_id: str,
        stage: str,
        timestamp: float | None = None,
        *,
        entered_at: float | None = None,
    ) -> None:
        self._stage_entries[(module_id, stage)] = float(entered_at or timestamp or time.time())

    def get_stage_entry_time(self, module_id: str, stage: str) -> float | None:
        return self._stage_entries.get((module_id, stage))

    def get_hours_in_stage(self, module_id: str, stage: str) -> float | None:
        entered = self.get_stage_entry_time(module_id, stage)
        if entered is None:
            return None
        return (time.time() - entered) / 3600

    def _has_evidence(self, rule: GateRequirement) -> bool:
        if not self._spine:
            return False
        event_types = [rule.evidence_type, *rule.evidence_aliases]
        for event_type in [item for item in event_types if item]:
            try:
                if self._spine.query(event_type=event_type, limit=1):
                    return True
            except TypeError:
                if self._spine.query(None, event_type, None, 1):
                    return True
        return False

    def _has_council_approval(self, module_id: str, decision_class: str) -> bool:
        if not self._council:
            return False
        sessions = self._council.list_sessions() if hasattr(self._council, "list_sessions") else []
        for session in sessions:
            searchable = " ".join(str(session.get(key) or "") for key in ("proposal_id", "title", "description"))
            if session.get("proposal_id") != module_id and module_id not in searchable:
                continue
            if str(session.get("decision_class")) != decision_class:
                continue
            session_id = str(session.get("session_id") or "")
            if session_id and session.get("status") not in {"closed_approved", "closed_rejected"} and hasattr(self._council, "tally"):
                self._council.tally(session_id)
                session = self._council.get_session(session_id) or session
            if session.get("status") != "closed_approved":
                continue
            return True
        return False

    def check_gate(self, module_id: str, target_stage: str, registry: Any) -> dict[str, Any]:
        module = registry.get(module_id) if hasattr(registry, "get") else None
        if not module:
            return {"allowed": False, "module_id": module_id, "stage": target_stage, "reasons": [f"Module {module_id} not found"]}

        rule = GATE_RULES.get(target_stage)
        if not rule:
            return {"allowed": True, "module_id": module_id, "stage": target_stage, "reasons": []}

        reasons: list[str] = []
        if rule.min_heartbeat_age_hours is not None:
            last_heartbeat = float(module.get("last_heartbeat") or 0)
            heartbeat_age_hours = (time.time() - last_heartbeat) / 3600 if last_heartbeat else 999999
            if heartbeat_age_hours > rule.min_heartbeat_age_hours:
                reasons.append(f"Heartbeat is older than {rule.min_heartbeat_age_hours:g}h")

        if rule.min_duration_hours is not None and rule.duration_from_stage:
            hours = self.get_hours_in_stage(module_id, rule.duration_from_stage)
            if hours is None:
                reasons.append(f"No record of entering {rule.duration_from_stage}")
            elif hours < rule.min_duration_hours:
                reasons.append(f"{rule.duration_from_stage} duration {hours:.1f}h is below {rule.min_duration_hours:g}h")

        if rule.requires_evidence and not self._has_evidence(rule):
            expected = ", ".join([rule.evidence_type, *rule.evidence_aliases]).strip(", ")
            reasons.append(f"Required evidence missing: {expected}")

        if rule.requires_council_approval and not self._has_council_approval(module_id, rule.decision_class):
            reasons.append(f"Council approval {rule.decision_class} required")

        return {
            "allowed": not reasons,
            "module_id": module_id,
            "stage": target_stage,
            "reasons": reasons,
        }

    def enforce(self, module_id: str, target_stage: str, registry: Any) -> None:
        result = self.check_gate(module_id, target_stage, registry)
        if not result["allowed"]:
            raise ValueError(f"Lifecycle gate blocked: {'; '.join(result['reasons'])}")


class LifecycleGates:
    """Manages module lifecycle stage transitions with gate checks.

    SQLite-backed. Thread-safe via RLock. EventBus integration.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS lifecycle_stages (
                stage_id     TEXT PRIMARY KEY,
                name         TEXT NOT NULL UNIQUE,
                stage_order  INTEGER NOT NULL,
                description  TEXT NOT NULL DEFAULT '',
                created_at   REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS stage_gates (
                gate_id      TEXT PRIMARY KEY,
                stage_id     TEXT NOT NULL,
                gate_name    TEXT NOT NULL,
                criteria_json TEXT NOT NULL DEFAULT '{}',
                created_at   REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS gate_evaluations (
                eval_id      TEXT PRIMARY KEY,
                gate_id      TEXT NOT NULL,
                passed       INTEGER NOT NULL,
                context_json TEXT NOT NULL DEFAULT '{}',
                result_json  TEXT NOT NULL DEFAULT '{}',
                evaluated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_stages_order ON lifecycle_stages(stage_order);
            CREATE INDEX IF NOT EXISTS idx_gates_stage ON stage_gates(stage_id);
            CREATE INDEX IF NOT EXISTS idx_evals_gate ON gate_evaluations(gate_id);
            CREATE INDEX IF NOT EXISTS idx_evals_time ON gate_evaluations(evaluated_at);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="core.lifecycle_gates",
            ))

    # ------------------------------------------------------------------
    # Stage CRUD
    # ------------------------------------------------------------------

    def define_stage(self, name: str, order: int,
                     description: str = "") -> dict:
        """Define a lifecycle stage. Returns the stage record."""
        if not name:
            raise ValueError("name must be non-empty")

        sid = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO lifecycle_stages (stage_id, name, stage_order, description, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (sid, name, order, description, now))
            self._conn.commit()

        log.info("defined stage %s (order=%d)", name, order)
        self._emit("stage_defined", {"stage_id": sid, "name": name, "order": order})
        return {
            "stage_id": sid, "name": name, "stage_order": order,
            "description": description, "created_at": now,
        }

    def list_stages(self) -> list[dict]:
        """List all stages ordered by stage_order."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM lifecycle_stages ORDER BY stage_order"
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Gate CRUD
    # ------------------------------------------------------------------

    def create_gate(self, stage_id: str, gate_name: str,
                    criteria_json: dict | str | None = None) -> dict:
        """Create a gate attached to a stage. Returns the gate record."""
        if not gate_name:
            raise ValueError("gate_name must be non-empty")

        gate_id = self._uid()
        now = time.time()

        if criteria_json is None:
            criteria = {}
        elif isinstance(criteria_json, str):
            criteria = json.loads(criteria_json)
        else:
            criteria = criteria_json
        criteria_str = json.dumps(criteria, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO stage_gates (gate_id, stage_id, gate_name, criteria_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (gate_id, stage_id, gate_name, criteria_str, now))
            self._conn.commit()

        log.info("created gate %s for stage %s", gate_name, stage_id)
        self._emit("gate_created", {
            "gate_id": gate_id, "stage_id": stage_id, "gate_name": gate_name,
        })
        return {
            "gate_id": gate_id, "stage_id": stage_id,
            "gate_name": gate_name, "criteria_json": criteria,
            "created_at": now,
        }

    def list_gates(self, stage_id: str | None = None) -> list[dict]:
        """List gates, optionally filtered by stage."""
        with self._lock:
            if stage_id:
                rows = self._conn.execute(
                    "SELECT * FROM stage_gates WHERE stage_id = ? ORDER BY created_at",
                    (stage_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM stage_gates ORDER BY created_at"
                ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["criteria_json"] = json.loads(d["criteria_json"])
            except (json.JSONDecodeError, TypeError):
                pass
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Gate Evaluation
    # ------------------------------------------------------------------

    def evaluate_gate(self, gate_id: str,
                      context_json: dict | str | None = None) -> dict:
        """Evaluate a gate against a context. Returns eval result."""
        gate_row = None
        with self._lock:
            gate_row = self._conn.execute(
                "SELECT * FROM stage_gates WHERE gate_id = ?", (gate_id,),
            ).fetchone()

        if not gate_row:
            return {"eval_id": None, "passed": False, "error": "Gate not found"}

        if context_json is None:
            context = {}
        elif isinstance(context_json, str):
            context = json.loads(context_json)
        else:
            context = context_json

        # Evaluate: check if all criteria keys are present and truthy in context
        criteria = {}
        try:
            criteria = json.loads(gate_row["criteria_json"])
        except (json.JSONDecodeError, TypeError):
            pass

        passed = True
        reasons: list[str] = []
        if criteria:
            for key, expected in criteria.items():
                actual = context.get(key)
                if expected is True:
                    if not actual:
                        passed = False
                        reasons.append(f"Missing or falsy: {key}")
                elif actual != expected:
                    passed = False
                    reasons.append(
                        f"{key}: expected {expected}, got {actual}"
                    )

        eval_id = self._uid()
        now = time.time()
        result_data = {"passed": passed, "reasons": reasons}
        result_str = json.dumps(result_data, default=str)
        context_str = json.dumps(context, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO gate_evaluations (eval_id, gate_id, passed, context_json, result_json, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (eval_id, gate_id, int(passed), context_str, result_str, now))
            self._conn.commit()

        self._emit("gate_evaluated", {
            "eval_id": eval_id, "gate_id": gate_id, "passed": passed,
        })
        return {
            "eval_id": eval_id, "gate_id": gate_id,
            "passed": passed, "reasons": reasons, "evaluated_at": now,
        }

    def get_evaluation_history(self, gate_id: str,
                               limit: int = 50) -> list[dict]:
        """Get evaluation history for a gate, most recent first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM gate_evaluations WHERE gate_id = ? "
                "ORDER BY evaluated_at DESC LIMIT ?",
                (gate_id, limit),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["passed"] = bool(d["passed"])
            try:
                d["context_json"] = json.loads(d["context_json"])
            except (json.JSONDecodeError, TypeError):
                pass
            try:
                d["result_json"] = json.loads(d["result_json"])
            except (json.JSONDecodeError, TypeError):
                pass
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Promotion
    # ------------------------------------------------------------------

    def promote(self, target_id: str, from_stage: str, to_stage: str,
                evaluation_data: dict | None = None) -> dict:
        """Promote a target from one stage to another after gate checks.

        Checks all gates for the target stage. If any gate fails, promotion
        is blocked. Returns result dict with success flag.
        """
        # Find the target stage
        with self._lock:
            stage = self._conn.execute(
                "SELECT * FROM lifecycle_stages WHERE name = ?", (to_stage,),
            ).fetchone()

        if not stage:
            return {"promoted": False, "target_id": target_id,
                    "error": f"Stage '{to_stage}' not defined"}

        stage_id = stage["stage_id"]

        # Get all gates for target stage
        with self._lock:
            gates = self._conn.execute(
                "SELECT * FROM stage_gates WHERE stage_id = ?", (stage_id,),
            ).fetchall()

        # Evaluate each gate
        all_passed = True
        eval_results: list[dict] = []
        context = evaluation_data or {}

        for gate in gates:
            eval_result = self.evaluate_gate(gate["gate_id"], context)
            eval_results.append(eval_result)
            if not eval_result["passed"]:
                all_passed = False

        if not all_passed:
            return {
                "promoted": False, "target_id": target_id,
                "from_stage": from_stage, "to_stage": to_stage,
                "evaluations": eval_results,
            }

        self._emit("promoted", {
            "target_id": target_id, "from_stage": from_stage,
            "to_stage": to_stage,
        })
        log.info("promoted %s: %s -> %s", target_id, from_stage, to_stage)
        return {
            "promoted": True, "target_id": target_id,
            "from_stage": from_stage, "to_stage": to_stage,
            "evaluations": eval_results,
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_lifecycle_stats(self) -> dict[str, Any]:
        """Return aggregate lifecycle statistics."""
        with self._lock:
            stages = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM lifecycle_stages"
            ).fetchone()["cnt"]
            gates = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM stage_gates"
            ).fetchone()["cnt"]
            evals = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM gate_evaluations"
            ).fetchone()["cnt"]
            passed = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM gate_evaluations WHERE passed = 1"
            ).fetchone()["cnt"]
            failed = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM gate_evaluations WHERE passed = 0"
            ).fetchone()["cnt"]

        return {
            "total_stages": stages,
            "total_gates": gates,
            "total_evaluations": evals,
            "passed_evaluations": passed,
            "failed_evaluations": failed,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: LifecycleGates | None = None


def get_lifecycle_gates(db_path: str | Path | None = None,
                        event_bus: EventBus | None = None) -> LifecycleGates:
    global _instance
    if _instance is None:
        _instance = LifecycleGates(db_path, event_bus)
    return _instance


def reset_lifecycle_gates() -> None:
    global _instance
    _instance = None
