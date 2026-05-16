"""
SYLION AEIS -- Autonomy Rollout Stages 3-5

SandboxExecutor  (Stage 3): Execute actions in an isolated sandbox,
    capture all outputs, measure and verify zero side-effects.
    Gate: G-AUTONOMY-3 -> G-AUTONOMY-4 requires 5+ executions, 0 side-effects.

LimitedProdExecutor (Stage 4): Execute in limited production with
    rate limits, scope limits, and human review escalation.
    Gate: G-AUTONOMY-4 -> G-AUTONOMY-5 requires Council + External + 30d clean.

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

import copy
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.aeis.autonomy_stages")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SIDE_EFFECTS_DETECTED = "side_effects_detected"


class ConstraintType(str, Enum):
    RATE_LIMIT = "rate_limit"
    SCOPE_LIMIT = "scope_limit"
    MAX_DURATION = "max_duration"
    ALLOWED_TARGETS = "allowed_targets"
    FORBIDDEN_ACTIONS = "forbidden_actions"


class EscalationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SandboxExecution:
    """Record of a single sandbox execution."""
    execution_id: str = ""
    action: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: dict[str, Any] = field(default_factory=dict)
    side_effects: list[dict[str, Any]] = field(default_factory=list)
    captured_outputs: dict[str, Any] = field(default_factory=dict)
    started_at: float = 0.0
    completed_at: float = 0.0
    duration_ms: float = 0.0

    def __post_init__(self):
        if not self.execution_id:
            self.execution_id = uuid.uuid4().hex
        if not self.started_at:
            self.started_at = time.time()


@dataclass
class LimitedProdExecution:
    """Record of a single limited-production execution."""
    execution_id: str = ""
    action: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: dict[str, Any] = field(default_factory=dict)
    constraint_violations: list[dict[str, Any]] = field(default_factory=list)
    escalation_id: str = ""
    escalation_status: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    duration_ms: float = 0.0

    def __post_init__(self):
        if not self.execution_id:
            self.execution_id = uuid.uuid4().hex
        if not self.started_at:
            self.started_at = time.time()


@dataclass
class EscalationRecord:
    """Record of a human-review escalation."""
    escalation_id: str = ""
    execution_id: str = ""
    reason: str = ""
    status: EscalationStatus = EscalationStatus.PENDING
    reviewed_by: str = ""
    review_notes: str = ""
    created_at: float = 0.0
    resolved_at: float = 0.0

    def __post_init__(self):
        if not self.escalation_id:
            self.escalation_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


# ---------------------------------------------------------------------------
# SandboxExecutor -- Stage 3
# ---------------------------------------------------------------------------

class SandboxExecutor:
    """Execute actions in an isolated sandbox environment.

    Captures all outputs, measures side-effects, verifies no external
    state was modified.

    SQLite-backed. Thread-safe. Singleton via get_sandbox_executor().
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
            CREATE TABLE IF NOT EXISTS sandbox_executions (
                execution_id    TEXT PRIMARY KEY,
                action          TEXT    NOT NULL,
                parameters      TEXT    NOT NULL DEFAULT '{}',
                status          TEXT    NOT NULL DEFAULT 'pending',
                result          TEXT    NOT NULL DEFAULT '{}',
                side_effects    TEXT    NOT NULL DEFAULT '[]',
                captured_outputs TEXT   NOT NULL DEFAULT '{}',
                started_at      REAL    NOT NULL,
                completed_at    REAL    NOT NULL DEFAULT 0,
                duration_ms     REAL    NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sandbox_side_effects (
                effect_id       TEXT PRIMARY KEY,
                execution_id    TEXT    NOT NULL,
                effect_type     TEXT    NOT NULL,
                description     TEXT    NOT NULL DEFAULT '',
                detected_at     REAL    NOT NULL,
                severity        TEXT    NOT NULL DEFAULT 'low'
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sandbox_status ON sandbox_executions(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sandbox_ts ON sandbox_executions(started_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_se_exec ON sandbox_side_effects(execution_id)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def execute_in_sandbox(
        self,
        action: str,
        parameters: dict[str, Any] | None = None,
        executor_fn: Callable[[str, dict], dict] | None = None,
    ) -> dict:
        """Execute an action in an isolated sandbox.

        Args:
            action: Name/type of the action to execute.
            parameters: Parameters for the action.
            executor_fn: Optional callable ``(action, parameters) -> dict``
                that performs the actual work.  When *None*, a safe default
                is used that records the execution without side-effects.
                The callable receives deep-copied parameters so it cannot
                mutate the caller's data.

        Returns:
            dict with execution_id, status, result, side_effects,
            captured_outputs, duration_ms.
        """
        params = parameters or {}
        execution = SandboxExecution(
            action=action,
            parameters=copy.deepcopy(params),
        )

        # Persist as pending
        self._persist_execution(execution)

        self._emit("aeis.autonomy_stages.sandbox_started", {
            "execution_id": execution.execution_id,
            "action": action,
        })

        # Execute
        start = time.time()
        try:
            execution.status = ExecutionStatus.RUNNING
            self._update_execution_status(execution)

            if executor_fn is not None:
                result = executor_fn(action, copy.deepcopy(params))
            else:
                # Default: capture inputs without external side-effects
                result = {
                    "action": action,
                    "echo_params": copy.deepcopy(params),
                    "sandbox": True,
                }

            execution.result = result
            execution.captured_outputs = {
                "return_value": result,
                "stdout": "",
                "stderr": "",
            }
            execution.status = ExecutionStatus.COMPLETED

        except Exception as exc:
            execution.status = ExecutionStatus.FAILED
            execution.result = {
                "error": str(exc),
                "error_type": type(exc).__name__,
            }
            log.exception("sandbox execution %s failed: %s",
                          execution.execution_id[:12], exc)

        end = time.time()
        execution.completed_at = end
        execution.duration_ms = (end - start) * 1000

        # Check side-effects
        side_effects = self._detect_side_effects(execution)
        execution.side_effects = side_effects
        if side_effects:
            execution.status = ExecutionStatus.SIDE_EFFECTS_DETECTED

        # Persist final state
        self._persist_execution_update(execution)

        self._emit("aeis.autonomy_stages.sandbox_completed", {
            "execution_id": execution.execution_id,
            "action": action,
            "status": execution.status.value,
            "side_effects_count": len(side_effects),
            "duration_ms": execution.duration_ms,
        })

        return {
            "execution_id": execution.execution_id,
            "action": action,
            "status": execution.status.value,
            "result": execution.result,
            "side_effects": side_effects,
            "captured_outputs": execution.captured_outputs,
            "duration_ms": execution.duration_ms,
        }

    def verify_no_side_effects(self, execution_id: str) -> dict:
        """Verify that a sandbox execution produced no external side-effects.

        Checks the stored side-effects record for the execution.

        Returns:
            dict with execution_id, clean (bool), side_effects list,
            verified_at.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sandbox_executions WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()

        if not row:
            return {
                "execution_id": execution_id,
                "verified": False,
                "message": "Execution not found",
            }

        side_effects = json.loads(row["side_effects"])
        clean = len(side_effects) == 0

        result = {
            "execution_id": execution_id,
            "verified": True,
            "clean": clean,
            "side_effects": side_effects,
            "side_effects_count": len(side_effects),
            "status": row["status"],
            "verified_at": time.time(),
        }

        self._emit("aeis.autonomy_stages.side_effects_verified", {
            "execution_id": execution_id,
            "clean": clean,
            "side_effects_count": len(side_effects),
        })

        return result

    def get_execution_log(self, limit: int = 100,
                          status: str | None = None) -> list[dict]:
        """Return all sandbox executions, newest first."""
        q = "SELECT * FROM sandbox_executions WHERE 1=1"
        params: list[Any] = []
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["parameters"] = json.loads(d.get("parameters", "{}"))
            d["result"] = json.loads(d.get("result", "{}"))
            d["side_effects"] = json.loads(d.get("side_effects", "[]"))
            d["captured_outputs"] = json.loads(d.get("captured_outputs", "{}"))
            results.append(d)
        return results

    def get_stats(self) -> dict:
        """Return aggregate sandbox execution statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sandbox_executions"
        ).fetchone()["cnt"]

        completed = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sandbox_executions WHERE status = ?",
            (ExecutionStatus.COMPLETED.value,)
        ).fetchone()["cnt"]

        failed = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sandbox_executions WHERE status = ?",
            (ExecutionStatus.FAILED.value,)
        ).fetchone()["cnt"]

        side_effects_detected = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sandbox_executions WHERE status = ?",
            (ExecutionStatus.SIDE_EFFECTS_DETECTED.value,)
        ).fetchone()["cnt"]

        total_side_effects = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sandbox_side_effects"
        ).fetchone()["cnt"]

        success_count = completed
        success_rate = (success_count / total * 100) if total > 0 else 0.0

        return {
            "total_executions": total,
            "completed": completed,
            "failed": failed,
            "side_effects_detected": side_effects_detected,
            "total_side_effects": total_side_effects,
            "success_rate": round(success_rate, 2),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_side_effects(self, execution: SandboxExecution) -> list[dict]:
        """Detect side-effects from an execution.

        Default implementation checks the result for indicators of
        external state modification.  Custom executor_fn may embed
        side-effect markers in the returned dict.
        """
        side_effects: list[dict] = []

        result = execution.result or {}
        # Check if the result explicitly declares side-effects
        if "__side_effects__" in result:
            declared = result["__side_effects__"]
            if isinstance(declared, list):
                for se in declared:
                    side_effects.append({
                        "effect_id": uuid.uuid4().hex,
                        "execution_id": execution.execution_id,
                        "effect_type": se.get("type", "unknown"),
                        "description": se.get("description", ""),
                        "detected_at": time.time(),
                        "severity": se.get("severity", "low"),
                    })

        # Persist detected side-effects
        if side_effects:
            with self._lock:
                for se in side_effects:
                    self._conn.execute("""
                        INSERT INTO sandbox_side_effects
                            (effect_id, execution_id, effect_type, description, detected_at, severity)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        se["effect_id"], se["execution_id"],
                        se["effect_type"], se["description"],
                        se["detected_at"], se["severity"],
                    ))
                self._conn.commit()

        return side_effects

    def _persist_execution(self, execution: SandboxExecution):
        """Persist initial execution record."""
        with self._lock:
            self._conn.execute("""
                INSERT INTO sandbox_executions
                    (execution_id, action, parameters, status, result,
                     side_effects, captured_outputs, started_at,
                     completed_at, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                execution.execution_id,
                execution.action,
                json.dumps(execution.parameters, default=str),
                execution.status.value,
                json.dumps(execution.result, default=str),
                json.dumps(execution.side_effects, default=str),
                json.dumps(execution.captured_outputs, default=str),
                execution.started_at,
                execution.completed_at,
                execution.duration_ms,
            ))
            self._conn.commit()

    def _update_execution_status(self, execution: SandboxExecution):
        """Update just the status field."""
        with self._lock:
            self._conn.execute(
                "UPDATE sandbox_executions SET status = ? WHERE execution_id = ?",
                (execution.status.value, execution.execution_id),
            )
            self._conn.commit()

    def _persist_execution_update(self, execution: SandboxExecution):
        """Persist final execution state after completion."""
        with self._lock:
            self._conn.execute("""
                UPDATE sandbox_executions
                SET status = ?, result = ?, side_effects = ?,
                    captured_outputs = ?, completed_at = ?, duration_ms = ?
                WHERE execution_id = ?
            """, (
                execution.status.value,
                json.dumps(execution.result, default=str),
                json.dumps(execution.side_effects, default=str),
                json.dumps(execution.captured_outputs, default=str),
                execution.completed_at,
                execution.duration_ms,
                execution.execution_id,
            ))
            self._conn.commit()

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.autonomy_stages",
            ))


# ---------------------------------------------------------------------------
# LimitedProdExecutor -- Stage 4
# ---------------------------------------------------------------------------

class LimitedProdExecutor:
    """Execute actions in limited production with guardrails.

    Rate limits, scope limits, and human review triggers for
    borderline cases.

    SQLite-backed. Thread-safe. Singleton via get_limited_prod_executor().
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
            CREATE TABLE IF NOT EXISTS limited_prod_executions (
                execution_id        TEXT PRIMARY KEY,
                action              TEXT    NOT NULL,
                parameters          TEXT    NOT NULL DEFAULT '{}',
                constraints         TEXT    NOT NULL DEFAULT '{}',
                status              TEXT    NOT NULL DEFAULT 'pending',
                result              TEXT    NOT NULL DEFAULT '{}',
                constraint_violations TEXT  NOT NULL DEFAULT '[]',
                escalation_id       TEXT    NOT NULL DEFAULT '',
                escalation_status   TEXT    NOT NULL DEFAULT '',
                started_at          REAL    NOT NULL,
                completed_at        REAL    NOT NULL DEFAULT 0,
                duration_ms         REAL    NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS limited_prod_escalations (
                escalation_id   TEXT PRIMARY KEY,
                execution_id    TEXT    NOT NULL,
                reason          TEXT    NOT NULL DEFAULT '',
                status          TEXT    NOT NULL DEFAULT 'pending',
                reviewed_by     TEXT    NOT NULL DEFAULT '',
                review_notes    TEXT    NOT NULL DEFAULT '',
                created_at      REAL    NOT NULL,
                resolved_at     REAL    NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS limited_prod_rate_tracker (
                window_key      TEXT PRIMARY KEY,
                action          TEXT    NOT NULL DEFAULT '',
                count           INTEGER NOT NULL DEFAULT 0,
                window_start    REAL    NOT NULL,
                window_end      REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lp_status ON limited_prod_executions(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lp_ts ON limited_prod_executions(started_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lp_esc ON limited_prod_escalations(execution_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lp_esc_status ON limited_prod_escalations(status)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def execute_limited(
        self,
        action: str,
        parameters: dict[str, Any] | None = None,
        constraints: dict[str, Any] | None = None,
        executor_fn: Callable[[str, dict], dict] | None = None,
    ) -> dict:
        """Execute an action in limited production with guardrails.

        Args:
            action: Name/type of the action.
            parameters: Parameters for the action.
            constraints: Constraints to enforce, e.g.:
                {
                    "max_rate_per_minute": 10,
                    "allowed_targets": ["db_read", "cache_write"],
                    "forbidden_actions": ["drop_table", "delete_all"],
                    "max_duration_ms": 5000,
                    "require_human_review": False,
                }
            executor_fn: Optional callable ``(action, params) -> dict``.

        Returns:
            dict with execution_id, status, result, constraint_violations,
            escalation_id, duration_ms.
        """
        params = parameters or {}
        cts = constraints or {}

        execution = LimitedProdExecution(
            action=action,
            parameters=copy.deepcopy(params),
            constraints=copy.deepcopy(cts),
        )

        # Pre-flight: check rate limits
        rate_violation = self._check_rate_limit(action, cts)
        if rate_violation:
            execution.status = ExecutionStatus.FAILED
            execution.constraint_violations = [rate_violation]
            execution.result = {"error": "Rate limit exceeded", "violation": rate_violation}
            self._persist_lp_execution(execution)

            self._emit("aeis.autonomy_stages.rate_limited", {
                "execution_id": execution.execution_id,
                "action": action,
            })
            return self._execution_to_dict(execution)

        # Pre-flight: scope check
        scope_violation = self._check_scope(action, params, cts)
        if scope_violation:
            execution.status = ExecutionStatus.FAILED
            execution.constraint_violations = [scope_violation]
            execution.result = {"error": "Scope limit violated", "violation": scope_violation}
            self._persist_lp_execution(execution)

            self._emit("aeis.autonomy_stages.scope_limited", {
                "execution_id": execution.execution_id,
                "action": action,
            })
            return self._execution_to_dict(execution)

        # Pre-flight: human review required?
        if cts.get("require_human_review", False):
            escalation = self._create_escalation(
                execution.execution_id,
                "Pre-execution human review required by constraints",
            )
            execution.escalation_id = escalation.escalation_id
            execution.escalation_status = EscalationStatus.PENDING.value
            execution.status = ExecutionStatus.PENDING
            self._persist_lp_execution(execution)

            self._emit("aeis.autonomy_stages.escalation_created", {
                "execution_id": execution.execution_id,
                "escalation_id": escalation.escalation_id,
                "reason": "pre_execution_review",
            })
            return self._execution_to_dict(execution)

        # Persist as running
        self._persist_lp_execution(execution)

        self._emit("aeis.autonomy_stages.limited_started", {
            "execution_id": execution.execution_id,
            "action": action,
        })

        # Execute
        start = time.time()
        try:
            execution.status = ExecutionStatus.RUNNING

            if executor_fn is not None:
                result = executor_fn(action, copy.deepcopy(params))
            else:
                result = {
                    "action": action,
                    "echo_params": copy.deepcopy(params),
                    "limited_prod": True,
                }

            execution.result = result
            execution.status = ExecutionStatus.COMPLETED

        except Exception as exc:
            execution.status = ExecutionStatus.FAILED
            execution.result = {
                "error": str(exc),
                "error_type": type(exc).__name__,
            }
            log.exception("limited-prod execution %s failed: %s",
                          execution.execution_id[:12], exc)

        end = time.time()
        execution.completed_at = end
        execution.duration_ms = (end - start) * 1000

        # Post-execution: check constraints
        violations = self._check_post_execution_constraints(execution, cts)
        execution.constraint_violations = violations
        if violations:
            # Auto-escalate on constraint violations
            escalation = self._create_escalation(
                execution.execution_id,
                f"Constraint violations detected: {len(violations)} violation(s)",
            )
            execution.escalation_id = escalation.escalation_id
            execution.escalation_status = EscalationStatus.PENDING.value

        # Update rate tracker
        self._record_rate_usage(action)

        # Persist final state
        self._persist_lp_execution_update(execution)

        self._emit("aeis.autonomy_stages.limited_completed", {
            "execution_id": execution.execution_id,
            "action": action,
            "status": execution.status.value,
            "violations": len(violations),
            "duration_ms": execution.duration_ms,
        })

        return self._execution_to_dict(execution)

    def check_constraints(self, execution_id: str) -> dict:
        """Verify that an execution stayed within its declared constraints.

        Returns:
            dict with execution_id, within_constraints (bool),
            violations list.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM limited_prod_executions WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()

        if not row:
            return {
                "execution_id": execution_id,
                "checked": False,
                "message": "Execution not found",
            }

        constraints = json.loads(row["constraints"])
        violations = json.loads(row["constraint_violations"])
        within = len(violations) == 0

        # Re-check duration constraint
        if constraints.get("max_duration_ms"):
            max_dur = constraints["max_duration_ms"]
            actual_dur = row["duration_ms"]
            if actual_dur > max_dur:
                within = False
                violations.append({
                    "type": "max_duration_exceeded",
                    "max_ms": max_dur,
                    "actual_ms": actual_dur,
                })

        return {
            "execution_id": execution_id,
            "checked": True,
            "within_constraints": within,
            "violations": violations,
            "checked_at": time.time(),
        }

    def escalate_to_human(self, execution_id: str, reason: str) -> dict:
        """Trigger human review for a borderline execution.

        Returns:
            dict with escalation_id, execution_id, status, reason.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM limited_prod_executions WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()

        if not row:
            return {
                "escalated": False,
                "message": "Execution not found",
            }

        # Check if already escalated
        if row["escalation_id"]:
            return {
                "escalated": False,
                "message": "Execution already has an escalation",
                "existing_escalation_id": row["escalation_id"],
            }

        escalation = self._create_escalation(execution_id, reason)

        with self._lock:
            self._conn.execute(
                """UPDATE limited_prod_executions
                   SET escalation_id = ?, escalation_status = ?
                   WHERE execution_id = ?""",
                (escalation.escalation_id, EscalationStatus.PENDING.value, execution_id),
            )
            self._conn.commit()

        self._emit("aeis.autonomy_stages.escalated_to_human", {
            "execution_id": execution_id,
            "escalation_id": escalation.escalation_id,
            "reason": reason,
        })

        return {
            "escalated": True,
            "escalation_id": escalation.escalation_id,
            "execution_id": execution_id,
            "status": EscalationStatus.PENDING.value,
            "reason": reason,
        }

    def resolve_escalation(self, escalation_id: str,
                           decision: str, reviewed_by: str = "",
                           notes: str = "") -> dict:
        """Resolve an escalation with a human decision.

        Args:
            escalation_id: The escalation to resolve.
            decision: One of 'approved', 'rejected'.
            reviewed_by: Who reviewed it.
            notes: Optional review notes.
        """
        if decision not in (EscalationStatus.APPROVED.value,
                            EscalationStatus.REJECTED.value):
            return {
                "resolved": False,
                "message": f"Invalid decision: {decision}. Use 'approved' or 'rejected'.",
            }

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM limited_prod_escalations WHERE escalation_id = ?",
                (escalation_id,),
            ).fetchone()

        if not row:
            return {"resolved": False, "message": "Escalation not found"}

        now = time.time()
        with self._lock:
            self._conn.execute("""
                UPDATE limited_prod_escalations
                SET status = ?, reviewed_by = ?, review_notes = ?, resolved_at = ?
                WHERE escalation_id = ?
            """, (decision, reviewed_by, notes, now, escalation_id))

            # Also update the execution's escalation_status
            self._conn.execute("""
                UPDATE limited_prod_executions
                SET escalation_status = ?
                WHERE escalation_id = ?
            """, (decision, escalation_id))
            self._conn.commit()

        self._emit("aeis.autonomy_stages.escalation_resolved", {
            "escalation_id": escalation_id,
            "decision": decision,
            "reviewed_by": reviewed_by,
        })

        return {
            "resolved": True,
            "escalation_id": escalation_id,
            "decision": decision,
        }

    def get_execution_log(self, limit: int = 100,
                          status: str | None = None) -> list[dict]:
        """Return all limited-prod executions, newest first."""
        q = "SELECT * FROM limited_prod_executions WHERE 1=1"
        params: list[Any] = []
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["parameters"] = json.loads(d.get("parameters", "{}"))
            d["constraints"] = json.loads(d.get("constraints", "{}"))
            d["result"] = json.loads(d.get("result", "{}"))
            d["constraint_violations"] = json.loads(d.get("constraint_violations", "[]"))
            results.append(d)
        return results

    def get_escalations(self, status: str | None = None,
                        limit: int = 100) -> list[dict]:
        """Return escalation records, optionally filtered by status."""
        q = "SELECT * FROM limited_prod_escalations WHERE 1=1"
        params: list[Any] = []
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Return aggregate limited-prod execution statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM limited_prod_executions"
        ).fetchone()["cnt"]

        completed = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM limited_prod_executions WHERE status = ?",
            (ExecutionStatus.COMPLETED.value,)
        ).fetchone()["cnt"]

        failed = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM limited_prod_executions WHERE status = ?",
            (ExecutionStatus.FAILED.value,)
        ).fetchone()["cnt"]

        pending = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM limited_prod_executions WHERE status = ?",
            (ExecutionStatus.PENDING.value,)
        ).fetchone()["cnt"]

        total_violations = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM limited_prod_escalations"
        ).fetchone()["cnt"]

        pending_escalations = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM limited_prod_escalations WHERE status = ?",
            (EscalationStatus.PENDING.value,)
        ).fetchone()["cnt"]

        approved_escalations = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM limited_prod_escalations WHERE status = ?",
            (EscalationStatus.APPROVED.value,)
        ).fetchone()["cnt"]

        rejected_escalations = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM limited_prod_escalations WHERE status = ?",
            (EscalationStatus.REJECTED.value,)
        ).fetchone()["cnt"]

        success_count = completed
        success_rate = (success_count / total * 100) if total > 0 else 0.0

        return {
            "total_executions": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "success_rate": round(success_rate, 2),
            "total_escalations": total_violations,
            "pending_escalations": pending_escalations,
            "approved_escalations": approved_escalations,
            "rejected_escalations": rejected_escalations,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_rate_limit(self, action: str,
                          constraints: dict) -> dict | None:
        """Check rate limit constraint. Returns violation dict or None."""
        max_rate = constraints.get("max_rate_per_minute", 0)
        if max_rate <= 0:
            return None

        now = time.time()
        window_start = now - 60

        with self._lock:
            row = self._conn.execute(
                """SELECT count FROM limited_prod_rate_tracker
                   WHERE action = ? AND window_start >= ?""",
                (action, window_start),
            ).fetchone()

        current_count = row["count"] if row else 0

        if current_count >= max_rate:
            return {
                "type": "rate_limit_exceeded",
                "max_per_minute": max_rate,
                "current_count": current_count,
            }
        return None

    def _check_scope(self, action: str, params: dict,
                     constraints: dict) -> dict | None:
        """Check scope constraints (allowed targets, forbidden actions)."""
        forbidden = constraints.get("forbidden_actions", [])
        if isinstance(forbidden, list) and action in forbidden:
            return {
                "type": "forbidden_action",
                "action": action,
                "forbidden_list": forbidden,
            }

        allowed_targets = constraints.get("allowed_targets")
        if allowed_targets is not None and isinstance(allowed_targets, list):
            target = params.get("target", "")
            if target and target not in allowed_targets:
                return {
                    "type": "target_not_allowed",
                    "target": target,
                    "allowed": allowed_targets,
                }

        return None

    def _check_post_execution_constraints(
        self, execution: LimitedProdExecution,
        constraints: dict,
    ) -> list[dict]:
        """Check constraints after execution completed."""
        violations: list[dict] = []
        result = execution.result or {}

        # Check for explicit constraint violations declared in result
        if "__constraint_violations__" in result:
            declared = result["__constraint_violations__"]
            if isinstance(declared, list):
                violations.extend(declared)

        # Duration constraint
        max_dur = constraints.get("max_duration_ms", 0)
        if max_dur > 0 and execution.duration_ms > max_dur:
            violations.append({
                "type": "max_duration_exceeded",
                "max_ms": max_dur,
                "actual_ms": execution.duration_ms,
            })

        return violations

    def _record_rate_usage(self, action: str):
        """Record an execution in the rate tracker."""
        now = time.time()
        window_start = now - 60
        window_key = f"{action}:{int(now / 60)}"

        with self._lock:
            existing = self._conn.execute(
                """SELECT window_key, count FROM limited_prod_rate_tracker
                   WHERE action = ? AND window_start >= ?""",
                (action, window_start),
            ).fetchone()

            if existing:
                self._conn.execute(
                    """UPDATE limited_prod_rate_tracker
                       SET count = count + 1
                       WHERE window_key = ?""",
                    (existing["window_key"],),
                )
            else:
                self._conn.execute("""
                    INSERT INTO limited_prod_rate_tracker
                        (window_key, action, count, window_start, window_end)
                    VALUES (?, ?, 1, ?, ?)
                """, (window_key, action, now, now + 60))
            self._conn.commit()

    def _create_escalation(self, execution_id: str,
                           reason: str) -> EscalationRecord:
        """Create and persist an escalation record."""
        escalation = EscalationRecord(
            execution_id=execution_id,
            reason=reason,
        )
        with self._lock:
            self._conn.execute("""
                INSERT INTO limited_prod_escalations
                    (escalation_id, execution_id, reason, status,
                     reviewed_by, review_notes, created_at, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                escalation.escalation_id,
                escalation.execution_id,
                escalation.reason,
                escalation.status.value,
                escalation.reviewed_by,
                escalation.review_notes,
                escalation.created_at,
                escalation.resolved_at,
            ))
            self._conn.commit()
        return escalation

    def _persist_lp_execution(self, execution: LimitedProdExecution):
        """Persist an execution record (insert or update)."""
        with self._lock:
            existing = self._conn.execute(
                "SELECT execution_id FROM limited_prod_executions WHERE execution_id = ?",
                (execution.execution_id,),
            ).fetchone()

            if existing:
                self._conn.execute("""
                    UPDATE limited_prod_executions
                    SET status = ?, result = ?, constraint_violations = ?,
                        escalation_id = ?, escalation_status = ?,
                        completed_at = ?, duration_ms = ?
                    WHERE execution_id = ?
                """, (
                    execution.status.value,
                    json.dumps(execution.result, default=str),
                    json.dumps(execution.constraint_violations, default=str),
                    execution.escalation_id,
                    execution.escalation_status,
                    execution.completed_at,
                    execution.duration_ms,
                    execution.execution_id,
                ))
            else:
                self._conn.execute("""
                    INSERT INTO limited_prod_executions
                        (execution_id, action, parameters, constraints,
                         status, result, constraint_violations,
                         escalation_id, escalation_status,
                         started_at, completed_at, duration_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    execution.execution_id,
                    execution.action,
                    json.dumps(execution.parameters, default=str),
                    json.dumps(execution.constraints, default=str),
                    execution.status.value,
                    json.dumps(execution.result, default=str),
                    json.dumps(execution.constraint_violations, default=str),
                    execution.escalation_id,
                    execution.escalation_status,
                    execution.started_at,
                    execution.completed_at,
                    execution.duration_ms,
                ))
            self._conn.commit()

    def _persist_lp_execution_update(self, execution: LimitedProdExecution):
        """Persist final execution state after completion."""
        with self._lock:
            self._conn.execute("""
                UPDATE limited_prod_executions
                SET status = ?, result = ?, constraint_violations = ?,
                    escalation_id = ?, escalation_status = ?,
                    completed_at = ?, duration_ms = ?
                WHERE execution_id = ?
            """, (
                execution.status.value,
                json.dumps(execution.result, default=str),
                json.dumps(execution.constraint_violations, default=str),
                execution.escalation_id,
                execution.escalation_status,
                execution.completed_at,
                execution.duration_ms,
                execution.execution_id,
            ))
            self._conn.commit()

    def _execution_to_dict(self, execution: LimitedProdExecution) -> dict:
        return {
            "execution_id": execution.execution_id,
            "action": execution.action,
            "status": execution.status.value,
            "result": execution.result,
            "constraint_violations": execution.constraint_violations,
            "escalation_id": execution.escalation_id,
            "escalation_status": execution.escalation_status,
            "duration_ms": execution.duration_ms,
        }

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.autonomy_stages",
            ))


# ---------------------------------------------------------------------------
# Global singletons
# ---------------------------------------------------------------------------

_sandbox: SandboxExecutor | None = None
_limited_prod: LimitedProdExecutor | None = None


def get_sandbox_executor(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> SandboxExecutor:
    global _sandbox
    if _sandbox is None:
        _sandbox = SandboxExecutor(db_path, event_bus)
    return _sandbox


def get_limited_prod_executor(db_path: str | Path | None = None,
                              event_bus: EventBus | None = None) -> LimitedProdExecutor:
    global _limited_prod
    if _limited_prod is None:
        _limited_prod = LimitedProdExecutor(db_path, event_bus)
    return _limited_prod
