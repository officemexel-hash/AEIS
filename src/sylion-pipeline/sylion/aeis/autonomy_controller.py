"""
SYLION AEIS -- Autonomy Rollout Controller

Controls AEIS autonomy level per Masterplan R7.

Five autonomy stages gated by G-AUTONOMY-1..5:
  Stage 1 (observe):       AEIS can READ system state, CANNOT modify anything
  Stage 2 (propose):       AEIS can propose changes, needs D2+ approval
  Stage 3 (sandbox):       AEIS executes in sandbox environment
  Stage 4 (limited-prod):  Limited production with guardrails
  Stage 5 (full-governed): Full autonomy under Canon (Council 4/4 + human)

Gate requirements:
  G-AUTONOMY-1 (->observe):       SelfObservation running 24h, 0 errors
  G-AUTONOMY-2 (->propose):       SelfExplanation accuracy >90%, DecisionBoundaries mapped
  G-AUTONOMY-3 (->sandbox):       ImprovementQueue with 10+ proposals, all reviewed
  G-AUTONOMY-4 (->limited):       5+ sandbox executions with 0 side-effects
  G-AUTONOMY-5 (->full):          Council 4/4 + External Review + 30d limited-prod clean

SQLite-backed. Thread-safe. Emits events via EventBus.
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

log = logging.getLogger("sylion.aeis.autonomy_controller")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AutonomyStage(str, Enum):
    """AEIS autonomy stages per Masterplan R7."""
    OBSERVE = "observe"          # Stage 1: read-only
    PROPOSE = "propose"          # Stage 2: propose + approval
    SANDBOX = "sandbox"          # Stage 3: execute in sandbox
    LIMITED_PROD = "limited"     # Stage 4: limited production
    FULL_GOVERNED = "full"       # Stage 5: full autonomy under Canon


class AutonomyAction(str, Enum):
    """Categories of actions AEIS can perform."""
    READ = "read"                # Read system state
    PROPOSE = "propose"          # Propose a change
    EXECUTE_SANDBOX = "execute_sandbox"   # Execute in sandbox
    EXECUTE_LIMITED = "execute_limited"   # Execute in limited prod
    EXECUTE_FULL = "execute_full"         # Execute in full prod


# Ordered for comparison
_STAGE_ORDER = {
    AutonomyStage.OBSERVE: 0,
    AutonomyStage.PROPOSE: 1,
    AutonomyStage.SANDBOX: 2,
    AutonomyStage.LIMITED_PROD: 3,
    AutonomyStage.FULL_GOVERNED: 4,
}

# Action -> minimum stage required
_ACTION_STAGE = {
    AutonomyAction.READ: AutonomyStage.OBSERVE,
    AutonomyAction.PROPOSE: AutonomyStage.PROPOSE,
    AutonomyAction.EXECUTE_SANDBOX: AutonomyStage.SANDBOX,
    AutonomyAction.EXECUTE_LIMITED: AutonomyStage.LIMITED_PROD,
    AutonomyAction.EXECUTE_FULL: AutonomyStage.FULL_GOVERNED,
}

# Gate -> target stage
_GATE_TARGET = {
    "G-AUTONOMY-1": AutonomyStage.OBSERVE,
    "G-AUTONOMY-2": AutonomyStage.PROPOSE,
    "G-AUTONOMY-3": AutonomyStage.SANDBOX,
    "G-AUTONOMY-4": AutonomyStage.LIMITED_PROD,
    "G-AUTONOMY-5": AutonomyStage.FULL_GOVERNED,
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class GateRequirement:
    """A single gate requirement check result."""
    gate_id: str = ""
    description: str = ""
    target_stage: str = ""
    checks: list[dict[str, Any]] = field(default_factory=list)
    satisfied: bool = False
    checked_at: float = 0.0

    def __post_init__(self):
        if not self.checked_at:
            self.checked_at = time.time()


@dataclass
class AutonomyActionRecord:
    """Record of an action attempted at a given autonomy stage."""
    record_id: str = ""
    action: str = ""
    stage: str = ""
    allowed: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.record_id:
            self.record_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Autonomy Controller
# ---------------------------------------------------------------------------

class AutonomyController:
    """Controls AEIS autonomy level per Masterplan R7.

    SQLite-backed. Thread-safe. Singleton via get_autonomy_controller().
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
        self._init_state()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS autonomy_state (
                key        TEXT PRIMARY KEY,
                value      TEXT    NOT NULL DEFAULT '',
                updated_at REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS autonomy_gate_checks (
                check_id    TEXT PRIMARY KEY,
                gate_id     TEXT    NOT NULL,
                description TEXT    NOT NULL DEFAULT '',
                target_stage TEXT   NOT NULL DEFAULT '',
                checks      TEXT    NOT NULL DEFAULT '[]',
                satisfied   INTEGER NOT NULL DEFAULT 0,
                checked_at  REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS autonomy_actions (
                record_id TEXT PRIMARY KEY,
                action    TEXT    NOT NULL,
                stage     TEXT    NOT NULL,
                allowed   INTEGER NOT NULL DEFAULT 0,
                details   TEXT    NOT NULL DEFAULT '{}',
                timestamp REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ac_gate ON autonomy_gate_checks(gate_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ac_action ON autonomy_actions(action)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ac_ts ON autonomy_actions(timestamp)"
        )
        self._conn.commit()

    def _init_state(self):
        """Initialize default autonomy state if empty."""
        with self._lock:
            existing = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM autonomy_state"
            ).fetchone()["cnt"]
            if existing == 0:
                now = time.time()
                self._conn.execute(
                    "INSERT INTO autonomy_state (key, value, updated_at) VALUES (?, ?, ?)",
                    ("current_stage", AutonomyStage.OBSERVE.value, now),
                )
                self._conn.execute(
                    "INSERT INTO autonomy_state (key, value, updated_at) VALUES (?, ?, ?)",
                    ("stage_entered_at", str(now), now),
                )
                self._conn.execute(
                    "INSERT INTO autonomy_state (key, value, updated_at) VALUES (?, ?, ?)",
                    ("initialized_at", str(now), now),
                )
                self._conn.commit()

    # ------------------------------------------------------------------
    # Stage management
    # ------------------------------------------------------------------

    def get_stage(self) -> AutonomyStage:
        """Return the current autonomy stage."""
        row = self._conn.execute(
            "SELECT value FROM autonomy_state WHERE key = 'current_stage'"
        ).fetchone()
        if row:
            return AutonomyStage(row["value"])
        return AutonomyStage.OBSERVE

    def get_stage_entered_at(self) -> float:
        """Return the timestamp when the current stage was entered."""
        row = self._conn.execute(
            "SELECT value FROM autonomy_state WHERE key = 'stage_entered_at'"
        ).fetchone()
        return float(row["value"]) if row else 0.0

    def advance_stage(self, requirements: dict[str, Any]) -> dict:
        """Attempt to advance to the next autonomy stage.

        Checks all gate requirements for the target stage.
        If all are satisfied, advances the stage.

        Args:
            requirements: dict with gate-specific evidence, e.g.:
                {
                    "observation_24h_clean": True,
                    "observation_error_count": 0,
                    "explanation_accuracy": 0.95,
                    "boundaries_mapped": True,
                    "improvement_proposals_count": 12,
                    "all_proposals_reviewed": True,
                    "sandbox_executions_count": 6,
                    "sandbox_side_effects": 0,
                    "council_approved": True,
                    "external_reviewed": True,
                    "limited_prod_days_clean": 35,
                }

        Emits ``aeis.autonomy_controller.stage_advanced`` on success,
        ``aeis.autonomy_controller.advancement_blocked`` on failure.
        """
        current = self.get_stage()
        next_stage = self._next_stage(current)

        if next_stage is None:
            return {
                "advanced": False,
                "current_stage": current.value,
                "message": "Already at maximum autonomy stage",
            }

        gate_id = self._stage_gate(next_stage)
        gate_result = self.check_gate(gate_id, requirements)

        if gate_result["satisfied"]:
            now = time.time()
            with self._lock:
                self._conn.execute(
                    "UPDATE autonomy_state SET value = ?, updated_at = ? WHERE key = 'current_stage'",
                    (next_stage.value, now),
                )
                self._conn.execute(
                    "UPDATE autonomy_state SET value = ?, updated_at = ? WHERE key = 'stage_entered_at'",
                    (str(now), now),
                )
                self._conn.commit()

            self._emit("aeis.autonomy_controller.stage_advanced", {
                "from_stage": current.value,
                "to_stage": next_stage.value,
                "gate_id": gate_id,
            })

            log.info("autonomy stage advanced: %s -> %s (gate %s)",
                     current.value, next_stage.value, gate_id)
            return {
                "advanced": True,
                "from_stage": current.value,
                "to_stage": next_stage.value,
                "gate_id": gate_id,
            }
        else:
            self._emit("aeis.autonomy_controller.advancement_blocked", {
                "current_stage": current.value,
                "target_stage": next_stage.value,
                "gate_id": gate_id,
                "missing": gate_result.get("missing", []),
            })

            log.warning("autonomy advancement blocked: %s -> %s (gate %s): %s",
                        current.value, next_stage.value, gate_id,
                        gate_result.get("missing", []))
            return {
                "advanced": False,
                "current_stage": current.value,
                "target_stage": next_stage.value,
                "gate_id": gate_id,
                "missing": gate_result.get("missing", []),
            }

    def set_stage(self, stage: AutonomyStage,
                  override_reason: str = "") -> dict:
        """Force-set the autonomy stage (for testing or admin override).

        In production, advance_stage() should be used instead.
        Emits ``aeis.autonomy_controller.stage_override``.
        """
        if not isinstance(stage, AutonomyStage):
            raise ValueError(f"Invalid stage: {stage}")

        current = self.get_stage()
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE autonomy_state SET value = ?, updated_at = ? WHERE key = 'current_stage'",
                (stage.value, now),
            )
            self._conn.execute(
                "UPDATE autonomy_state SET value = ?, updated_at = ? WHERE key = 'stage_entered_at'",
                (str(now), now),
            )
            self._conn.commit()

        self._emit("aeis.autonomy_controller.stage_override", {
            "from_stage": current.value,
            "to_stage": stage.value,
            "reason": override_reason,
        })

        log.warning("autonomy stage overridden: %s -> %s (reason: %s)",
                    current.value, stage.value, override_reason or "N/A")
        return {
            "previous_stage": current.value,
            "new_stage": stage.value,
            "reason": override_reason,
        }

    # ------------------------------------------------------------------
    # Gate checking
    # ------------------------------------------------------------------

    def check_gate(self, gate_id: str, requirements: dict[str, Any]) -> dict:
        """Check whether a gate's requirements are satisfied.

        Args:
            gate_id: One of G-AUTONOMY-1..5
            requirements: Evidence dict (see advance_stage docstring)

        Returns:
            dict with: gate_id, target_stage, satisfied, checks, missing
        """
        if gate_id not in _GATE_TARGET:
            return {
                "gate_id": gate_id,
                "target_stage": None,
                "satisfied": False,
                "checks": [],
                "missing": [f"Unknown gate: {gate_id}"],
            }

        target = _GATE_TARGET[gate_id]
        checks: list[dict[str, Any]] = []
        missing: list[str] = []

        if gate_id == "G-AUTONOMY-1":
            # SelfObservation running 24h, 0 errors
            obs_clean = requirements.get("observation_24h_clean", False)
            obs_errors = requirements.get("observation_error_count", -1)
            checks.append({
                "name": "observation_24h_clean",
                "required": True,
                "actual": obs_clean,
                "pass": obs_clean is True,
            })
            checks.append({
                "name": "observation_error_count",
                "required": 0,
                "actual": obs_errors,
                "pass": obs_errors == 0,
            })
            if not obs_clean:
                missing.append("observation_24h_clean")
            if obs_errors != 0:
                missing.append("observation_error_count == 0")

        elif gate_id == "G-AUTONOMY-2":
            # SelfExplanation accuracy >90%, DecisionBoundaries mapped
            accuracy = requirements.get("explanation_accuracy", 0.0)
            boundaries = requirements.get("boundaries_mapped", False)
            checks.append({
                "name": "explanation_accuracy",
                "required": ">0.90",
                "actual": accuracy,
                "pass": accuracy > 0.90,
            })
            checks.append({
                "name": "boundaries_mapped",
                "required": True,
                "actual": boundaries,
                "pass": boundaries is True,
            })
            if accuracy <= 0.90:
                missing.append("explanation_accuracy > 0.90")
            if not boundaries:
                missing.append("boundaries_mapped")

        elif gate_id == "G-AUTONOMY-3":
            # ImprovementQueue with 10+ proposals, all reviewed
            proposals = requirements.get("improvement_proposals_count", 0)
            reviewed = requirements.get("all_proposals_reviewed", False)
            checks.append({
                "name": "improvement_proposals_count",
                "required": ">=10",
                "actual": proposals,
                "pass": proposals >= 10,
            })
            checks.append({
                "name": "all_proposals_reviewed",
                "required": True,
                "actual": reviewed,
                "pass": reviewed is True,
            })
            if proposals < 10:
                missing.append("improvement_proposals_count >= 10")
            if not reviewed:
                missing.append("all_proposals_reviewed")

        elif gate_id == "G-AUTONOMY-4":
            # 5+ sandbox executions with 0 side-effects
            executions = requirements.get("sandbox_executions_count", 0)
            side_effects = requirements.get("sandbox_side_effects", -1)
            checks.append({
                "name": "sandbox_executions_count",
                "required": ">=5",
                "actual": executions,
                "pass": executions >= 5,
            })
            checks.append({
                "name": "sandbox_side_effects",
                "required": 0,
                "actual": side_effects,
                "pass": side_effects == 0,
            })
            if executions < 5:
                missing.append("sandbox_executions_count >= 5")
            if side_effects != 0:
                missing.append("sandbox_side_effects == 0")

        elif gate_id == "G-AUTONOMY-5":
            # Council 4/4 + External Review + 30d limited-prod clean
            council = requirements.get("council_approved", False)
            external = requirements.get("external_reviewed", False)
            days_clean = requirements.get("limited_prod_days_clean", 0)
            checks.append({
                "name": "council_approved",
                "required": True,
                "actual": council,
                "pass": council is True,
            })
            checks.append({
                "name": "external_reviewed",
                "required": True,
                "actual": external,
                "pass": external is True,
            })
            checks.append({
                "name": "limited_prod_days_clean",
                "required": ">=30",
                "actual": days_clean,
                "pass": days_clean >= 30,
            })
            if not council:
                missing.append("council_approved")
            if not external:
                missing.append("external_reviewed")
            if days_clean < 30:
                missing.append("limited_prod_days_clean >= 30")

        satisfied = len(missing) == 0

        # Persist gate check
        self._persist_gate_check(gate_id, target.value, checks, satisfied)

        return {
            "gate_id": gate_id,
            "target_stage": target.value,
            "satisfied": satisfied,
            "checks": checks,
            "missing": missing,
        }

    def _persist_gate_check(self, gate_id: str, target_stage: str,
                            checks: list[dict], satisfied: bool):
        """Persist a gate check to the database."""
        now = time.time()
        check_id = uuid.uuid4().hex
        description = f"Gate {gate_id} -> {target_stage}"
        with self._lock:
            self._conn.execute("""
                INSERT INTO autonomy_gate_checks
                    (check_id, gate_id, description, target_stage,
                     checks, satisfied, checked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                check_id, gate_id, description, target_stage,
                json.dumps(checks, default=str), 1 if satisfied else 0, now,
            ))
            self._conn.commit()

    # ------------------------------------------------------------------
    # Action authorization
    # ------------------------------------------------------------------

    def can_execute(self, action: AutonomyAction) -> bool:
        """Check if the given action is allowed at the current autonomy stage.

        Stage -> allowed actions:
            OBSERVE:       READ only
            PROPOSE:       READ, PROPOSE
            SANDBOX:       READ, PROPOSE, EXECUTE_SANDBOX
            LIMITED_PROD:  READ, PROPOSE, EXECUTE_SANDBOX, EXECUTE_LIMITED
            FULL_GOVERNED: all actions
        """
        if not isinstance(action, AutonomyAction):
            return False

        current = self.get_stage()
        required = _ACTION_STAGE[action]
        return _STAGE_ORDER[current] >= _STAGE_ORDER[required]

    def authorize(self, action: AutonomyAction,
                  details: dict | None = None) -> dict:
        """Authorize and record an action attempt.

        Returns:
            dict with: allowed, action, current_stage, record_id
        """
        allowed = self.can_execute(action)
        current = self.get_stage()

        self.record_action(action, {
            "allowed": allowed,
            "stage": current.value,
            **(details or {}),
        })

        return {
            "allowed": allowed,
            "action": action.value,
            "current_stage": current.value,
        }

    def record_action(self, action: AutonomyAction | str,
                      result: dict[str, Any]) -> dict:
        """Record an action and its result for audit.

        Emits ``aeis.autonomy_controller.action_recorded``.
        """
        action_str = action.value if isinstance(action, AutonomyAction) else action
        current = self.get_stage()
        allowed = result.get("allowed", False)

        record = AutonomyActionRecord(
            action=action_str,
            stage=current.value,
            allowed=allowed,
            details=result,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO autonomy_actions
                    (record_id, action, stage, allowed, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                record.record_id, record.action, record.stage,
                1 if record.allowed else 0,
                json.dumps(record.details, default=str),
                record.timestamp,
            ))
            self._conn.commit()

        self._emit("aeis.autonomy_controller.action_recorded", {
            "record_id": record.record_id,
            "action": action_str,
            "stage": current.value,
            "allowed": allowed,
        })

        log.info("action recorded: %s at stage %s, allowed=%s",
                 action_str, current.value, allowed)
        return {
            "record_id": record.record_id,
            "action": action_str,
            "allowed": allowed,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_gate_history(self, gate_id: str | None = None,
                         limit: int = 100) -> list[dict]:
        """Return gate check history, optionally filtered by gate_id."""
        if gate_id:
            rows = self._conn.execute(
                "SELECT * FROM autonomy_gate_checks WHERE gate_id = ? ORDER BY checked_at DESC LIMIT ?",
                (gate_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM autonomy_gate_checks ORDER BY checked_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["checks"] = json.loads(d.get("checks", "[]"))
            d["satisfied"] = bool(d["satisfied"])
            results.append(d)
        return results

    def get_action_history(self, action: str | None = None,
                           limit: int = 100) -> list[dict]:
        """Return action history, optionally filtered by action type."""
        if action:
            rows = self._conn.execute(
                "SELECT * FROM autonomy_actions WHERE action = ? ORDER BY timestamp DESC LIMIT ?",
                (action, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM autonomy_actions ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["details"] = json.loads(d.get("details", "{}"))
            d["allowed"] = bool(d["allowed"])
            results.append(d)
        return results

    def get_stats(self) -> dict:
        """Aggregate autonomy controller statistics."""
        total_actions = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM autonomy_actions"
        ).fetchone()["cnt"]

        allowed_actions = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM autonomy_actions WHERE allowed = 1"
        ).fetchone()["cnt"]

        denied_actions = total_actions - allowed_actions

        total_gate_checks = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM autonomy_gate_checks"
        ).fetchone()["cnt"]

        passed_gates = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM autonomy_gate_checks WHERE satisfied = 1"
        ).fetchone()["cnt"]

        by_action_rows = self._conn.execute(
            "SELECT action, COUNT(*) as cnt FROM autonomy_actions GROUP BY action"
        ).fetchall()
        by_action = {r["action"]: r["cnt"] for r in by_action_rows}

        by_gate_rows = self._conn.execute(
            "SELECT gate_id, COUNT(*) as cnt FROM autonomy_gate_checks GROUP BY gate_id"
        ).fetchall()
        by_gate = {r["gate_id"]: r["cnt"] for r in by_gate_rows}

        return {
            "current_stage": self.get_stage().value,
            "stage_entered_at": self.get_stage_entered_at(),
            "total_actions": total_actions,
            "allowed_actions": allowed_actions,
            "denied_actions": denied_actions,
            "total_gate_checks": total_gate_checks,
            "passed_gates": passed_gates,
            "by_action": by_action,
            "by_gate": by_gate,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _next_stage(current: AutonomyStage) -> AutonomyStage | None:
        """Return the next stage after current, or None if at max."""
        order = list(AutonomyStage)
        idx = order.index(current)
        if idx + 1 < len(order):
            return order[idx + 1]
        return None

    @staticmethod
    def _stage_gate(stage: AutonomyStage) -> str:
        """Return the gate ID that controls entry to the given stage."""
        for gate_id, target in _GATE_TARGET.items():
            if target == stage:
                return gate_id
        return ""

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.autonomy_controller",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_controller: AutonomyController | None = None


def get_autonomy_controller(db_path: str | Path | None = None,
                            event_bus: EventBus | None = None) -> AutonomyController:
    global _controller
    if _controller is None:
        _controller = AutonomyController(db_path, event_bus)
    return _controller
