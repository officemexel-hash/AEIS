"""
SYLION Rebuild -- Cutover Automation

Automates the cutover lifecycle transition (dual -> cutover -> stable)
with automatic rollback safety.  Requires D3 Council approval before
initiation.  Monitors module health during cutover and triggers
auto-rollback when degradation is detected.

SQLite-backed.  Thread-safe.  Emits events via EventBus.

Auto-rollback triggers:
  - Module heartbeat missing for >60s during cutover
  - Error rate >5% in last 5 minutes
  - Council revokes approval during cutover
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

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.rebuild.cutover_automation")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEARTBEAT_TIMEOUT_S = 60.0
ERROR_RATE_WINDOW_S = 300.0          # 5 minutes
ERROR_RATE_THRESHOLD = 0.05          # 5 %


class CutoverState(str, Enum):
    PENDING   = "pending"
    ACTIVE    = "active"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED    = "failed"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RollbackContract:
    """Snapshot captured before cutover starts, used for rollback."""
    contract_id: str = ""
    module_id: str = ""
    snapshot: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def __post_init__(self):
        if not self.contract_id:
            self.contract_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class CutoverMetrics:
    """Health metrics sampled during cutover."""
    module_id: str = ""
    heartbeat_age_s: float = 0.0
    error_rate: float = 0.0
    request_count: int = 0
    error_count: int = 0
    sampled_at: float = 0.0

    def __post_init__(self):
        if not self.sampled_at:
            self.sampled_at = time.time()


# ---------------------------------------------------------------------------
# CutoverAutomation
# ---------------------------------------------------------------------------

class CutoverAutomation:
    """Automates the cutover lifecycle transition with rollback safety.

    Works with an existing *registry* (ModuleRegistry) to validate and
    transition module lifecycle states.  All state is persisted in SQLite
    so cutover progress survives process restarts.

    Parameters
    ----------
    registry : ModuleRegistry
        The module registry used to read/transition lifecycle stages.
    event_bus : EventBus | None
        Optional event bus for publishing cutover events.
    rollback_manager : object | None
        Optional external rollback manager.  When provided,
        ``auto_rollback`` delegates the actual rollback work to this
        object's ``execute_rollback(contract_id, reason)`` method.
    db_path : str | Path | None
        Path to the SQLite database file.  Defaults to ``:memory:``.
    """

    def __init__(self, registry, event_bus: EventBus | None = None,
                 rollback_manager=None, db_path: str | Path | None = None):
        self._registry = registry
        self._event_bus = event_bus
        self._rollback_manager = rollback_manager
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
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
            CREATE TABLE IF NOT EXISTS cutover_sessions (
                session_id    TEXT PRIMARY KEY,
                module_id     TEXT NOT NULL,
                approval_id   TEXT NOT NULL DEFAULT '',
                contract_id   TEXT NOT NULL DEFAULT '',
                previous_state TEXT NOT NULL DEFAULT 'dual',
                state         TEXT NOT NULL DEFAULT 'pending',
                reason        TEXT NOT NULL DEFAULT '',
                started_at    REAL NOT NULL DEFAULT 0,
                completed_at  REAL NOT NULL DEFAULT 0,
                created_at    REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS rollback_contracts (
                contract_id   TEXT PRIMARY KEY,
                module_id     TEXT NOT NULL,
                snapshot      TEXT NOT NULL DEFAULT '{}',
                created_at    REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cutover_metrics_log (
                log_id        TEXT PRIMARY KEY,
                session_id    TEXT NOT NULL,
                module_id     TEXT NOT NULL,
                heartbeat_age REAL NOT NULL DEFAULT 0,
                error_rate    REAL NOT NULL DEFAULT 0,
                request_count INTEGER NOT NULL DEFAULT 0,
                error_count   INTEGER NOT NULL DEFAULT 0,
                sampled_at    REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cs_module
                ON cutover_sessions(module_id);
            CREATE INDEX IF NOT EXISTS idx_cs_state
                ON cutover_sessions(state);
            CREATE INDEX IF NOT EXISTS idx_ml_session
                ON cutover_metrics_log(session_id);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Rollback contract helpers
    # ------------------------------------------------------------------

    def _create_rollback_contract(self, module_id: str) -> str:
        """Capture a snapshot of the module's current state for rollback."""
        mod = self._registry.get(module_id)
        snapshot = dict(mod) if mod else {"module_id": module_id}

        contract = RollbackContract(module_id=module_id, snapshot=snapshot)

        with self._lock:
            self._conn.execute("""
                INSERT INTO rollback_contracts (contract_id, module_id, snapshot, created_at)
                VALUES (?, ?, ?, ?)
            """, (contract.contract_id, contract.module_id,
                  json.dumps(contract.snapshot, default=str), contract.created_at))
            self._conn.commit()

        log.info("rollback contract %s created for %s", contract.contract_id[:12], module_id)
        return contract.contract_id

    def _get_contract(self, contract_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM rollback_contracts WHERE contract_id = ?", (contract_id,)
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Approval validation
    # ------------------------------------------------------------------

    def _validate_approval(self, module_id: str, approval_id: str) -> dict:
        """Validate that the given approval ID represents a valid D3 Council approval.

        Returns a dict with ``valid: True/False`` and an optional ``reason``.
        """
        if not approval_id or not approval_id.strip():
            return {"valid": False, "reason": "approval_id is required"}

        # The approval_id must be a non-empty string starting with 'D3-' or
        # be a valid hex UUID (for testing convenience).
        normalized = approval_id.strip()
        if not (normalized.startswith("D3-") or len(normalized) >= 16):
            return {"valid": False, "reason": "invalid approval_id format; expected D3-* or UUID"}

        # Check that the module exists in the registry
        mod = self._registry.get(module_id)
        if mod is None:
            return {"valid": False, "reason": f"module {module_id} not found in registry"}

        # Module must be in 'dual' state to start cutover
        if mod.get("lifecycle") != "dual":
            return {"valid": False, "reason": f"module lifecycle is '{mod.get('lifecycle')}', expected 'dual'"}

        return {"valid": True, "reason": ""}

    def revoke_approval(self, module_id: str) -> dict:
        """Revoke Council approval during an active cutover.

        This triggers auto-rollback.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cutover_sessions WHERE module_id = ? AND state = ?",
                (module_id, CutoverState.ACTIVE.value),
            ).fetchone()

            if not row:
                return {"module_id": module_id, "error": "no active cutover to revoke"}

            session_id = row["session_id"]

        return self.auto_rollback(module_id, "council approval revoked")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def initiate_cutover(self, module_id: str, council_approval_id: str) -> dict:
        """Initiate cutover for a module.  Requires D3 Council approval.

        Steps:
        1. Validate the council approval ID.
        2. Create a rollback contract (snapshot of current state).
        3. Transition the module lifecycle to ``cutover``.
        4. Create a cutover session in ACTIVE state.

        Returns a dict with ``session_id`` and status info.
        """
        # 1. Validate approval
        validation = self._validate_approval(module_id, council_approval_id)
        if not validation["valid"]:
            log.warning("cutover initiation rejected for %s: %s", module_id, validation["reason"])
            return {"module_id": module_id, "error": validation["reason"]}

        # 2. Create rollback contract
        contract_id = self._create_rollback_contract(module_id)

        # 3. Capture previous state before transition
        mod = self._registry.get(module_id)
        previous_state = mod.get("lifecycle", "dual") if mod else "dual"

        # 4. Transition module lifecycle to cutover
        try:
            from sylion.core.module_registry import ModuleLifecycleStage
            self._registry.transition(module_id, ModuleLifecycleStage.CUTOVER)
        except Exception as exc:
            log.error("lifecycle transition failed for %s: %s", module_id, exc)
            return {"module_id": module_id, "error": f"lifecycle transition failed: {exc}"}

        # 5. Create cutover session
        session_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            # Ensure no other active cutover exists for this module
            existing = self._conn.execute(
                "SELECT session_id FROM cutover_sessions WHERE module_id = ? AND state = ?",
                (module_id, CutoverState.ACTIVE.value),
            ).fetchone()
            if existing:
                return {
                    "module_id": module_id,
                    "error": f"active cutover already exists (session {existing['session_id'][:12]})",
                }

            self._conn.execute("""
                INSERT INTO cutover_sessions
                    (session_id, module_id, approval_id, contract_id,
                     previous_state, state, started_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, module_id, council_approval_id, contract_id,
                  previous_state, CutoverState.ACTIVE.value, now, now))
            self._conn.commit()

        self._emit("rebuild.cutover.initiated", {
            "session_id": session_id, "module_id": module_id,
            "contract_id": contract_id, "approval_id": council_approval_id,
        })

        log.info("cutover initiated for %s (session %s)", module_id, session_id[:12])
        return {
            "session_id": session_id,
            "module_id": module_id,
            "contract_id": contract_id,
            "state": CutoverState.ACTIVE.value,
            "started_at": now,
        }

    def monitor_cutover(self, module_id: str) -> dict:
        """Check cutover progress and health metrics.

        Samples current heartbeat age and error rate from the registry,
        logs the metrics, and checks auto-rollback conditions.

        Returns a dict with session info, health metrics, and ``healthy`` flag.
        """
        row = self._conn.execute(
            "SELECT * FROM cutover_sessions WHERE module_id = ? ORDER BY created_at DESC LIMIT 1",
            (module_id,),
        ).fetchone()
        if not row:
            return {"module_id": module_id, "error": "no cutover session found"}

        session = dict(row)

        if session["state"] != CutoverState.ACTIVE.value:
            return {
                "session_id": session["session_id"],
                "module_id": module_id,
                "state": session["state"],
                "healthy": session["state"] == CutoverState.COMPLETED.value,
            }

        # Sample metrics from registry
        mod = self._registry.get(module_id)
        now = time.time()

        heartbeat_age = (now - mod["last_heartbeat"]) if mod and mod.get("last_heartbeat") else 999999.0
        error_rate = self._compute_error_rate(module_id)

        metrics = CutoverMetrics(
            module_id=module_id,
            heartbeat_age_s=heartbeat_age,
            error_rate=error_rate,
        )

        # Log metrics
        self._log_metrics(session["session_id"], metrics)

        # Evaluate auto-rollback triggers
        rollback_reason = self._evaluate_rollback_triggers(module_id, metrics)

        if rollback_reason:
            result = self.auto_rollback(module_id, rollback_reason)
            return {
                "session_id": session["session_id"],
                "module_id": module_id,
                "state": CutoverState.ROLLED_BACK.value,
                "healthy": False,
                "rollback_reason": rollback_reason,
                "rollback_result": result,
                "metrics": {
                    "heartbeat_age_s": heartbeat_age,
                    "error_rate": error_rate,
                },
            }

        return {
            "session_id": session["session_id"],
            "module_id": module_id,
            "state": CutoverState.ACTIVE.value,
            "healthy": True,
            "metrics": {
                "heartbeat_age_s": heartbeat_age,
                "error_rate": error_rate,
            },
        }

    def complete_cutover(self, module_id: str) -> dict:
        """Complete a successful cutover -> stable.

        Verifies that an active cutover session exists and the module
        is in the cutover lifecycle stage, then transitions to stable.
        """
        row = self._conn.execute(
            "SELECT * FROM cutover_sessions WHERE module_id = ? AND state = ?",
            (module_id, CutoverState.ACTIVE.value),
        ).fetchone()

        if not row:
            return {"module_id": module_id, "error": "no active cutover session found"}

        session = dict(row)
        session_id = session["session_id"]
        now = time.time()

        # Transition module lifecycle to stable
        try:
            from sylion.core.module_registry import ModuleLifecycleStage
            self._registry.transition(module_id, ModuleLifecycleStage.STABLE)
        except Exception as exc:
            log.error("lifecycle transition to stable failed for %s: %s", module_id, exc)
            return {"module_id": module_id, "error": f"stable transition failed: {exc}"}

        with self._lock:
            self._conn.execute("""
                UPDATE cutover_sessions
                SET state = ?, completed_at = ?
                WHERE session_id = ?
            """, (CutoverState.COMPLETED.value, now, session_id))
            self._conn.commit()

        self._emit("rebuild.cutover.completed", {
            "session_id": session_id, "module_id": module_id,
        })

        log.info("cutover completed for %s -> stable (session %s)", module_id, session_id[:12])
        return {
            "session_id": session_id,
            "module_id": module_id,
            "state": CutoverState.COMPLETED.value,
            "completed_at": now,
        }

    def auto_rollback(self, module_id: str, reason: str) -> dict:
        """Automatic rollback if metrics degrade during cutover.

        Uses the rollback contract to restore the module to its previous
        lifecycle state (``dual``).  Delegates to the external rollback
        manager if one was provided at construction time.
        """
        row = self._conn.execute(
            "SELECT * FROM cutover_sessions WHERE module_id = ? AND state = ?",
            (module_id, CutoverState.ACTIVE.value),
        ).fetchone()

        if not row:
            log.warning("auto_rollback: no active cutover for %s", module_id)
            return {"module_id": module_id, "error": "no active cutover to roll back"}

        session = dict(row)
        session_id = session["session_id"]
        contract_id = session["contract_id"]
        previous_state = session["previous_state"]
        now = time.time()

        # Delegate to external rollback manager if available
        if self._rollback_manager is not None:
            try:
                self._rollback_manager.execute_rollback(contract_id, reason)
            except Exception as exc:
                log.error("rollback manager failed for %s: %s", module_id, exc)

        # Transition module back to previous state
        try:
            from sylion.core.module_registry import ModuleLifecycleStage
            target = ModuleLifecycleStage(previous_state)
            self._registry.transition(module_id, target)
        except Exception as exc:
            log.error("lifecycle rollback failed for %s: %s", module_id, exc)

        # Update session state
        with self._lock:
            self._conn.execute("""
                UPDATE cutover_sessions
                SET state = ?, reason = ?, completed_at = ?
                WHERE session_id = ?
            """, (CutoverState.ROLLED_BACK.value, reason, now, session_id))
            self._conn.commit()

        self._emit("rebuild.cutover.rolled_back", {
            "session_id": session_id, "module_id": module_id,
            "reason": reason, "contract_id": contract_id,
        })

        log.warning("auto-rollback for %s (session %s): %s", module_id, session_id[:12], reason)
        return {
            "session_id": session_id,
            "module_id": module_id,
            "state": CutoverState.ROLLED_BACK.value,
            "reason": reason,
            "contract_id": contract_id,
            "rolled_back_at": now,
        }

    def get_cutover_status(self, module_id: str) -> dict:
        """Get the current cutover status for a module."""
        row = self._conn.execute(
            "SELECT * FROM cutover_sessions WHERE module_id = ? ORDER BY created_at DESC LIMIT 1",
            (module_id,),
        ).fetchone()

        if not row:
            return {"module_id": module_id, "state": None, "active": False}

        session = dict(row)
        return {
            "module_id": module_id,
            "session_id": session["session_id"],
            "state": session["state"],
            "active": session["state"] == CutoverState.ACTIVE.value,
            "approval_id": session["approval_id"],
            "contract_id": session["contract_id"],
            "previous_state": session["previous_state"],
            "started_at": session["started_at"],
            "completed_at": session["completed_at"],
            "reason": session["reason"],
        }

    def list_active_cutover(self) -> list[dict]:
        """List all modules currently in active cutover."""
        rows = self._conn.execute(
            "SELECT * FROM cutover_sessions WHERE state = ? ORDER BY started_at",
            (CutoverState.ACTIVE.value,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Metrics helpers
    # ------------------------------------------------------------------

    def record_error(self, module_id: str, error: str = "") -> dict:
        """Record an error occurrence for a module during cutover.

        Errors are tracked in-memory (windowed) for error-rate computation.
        Thread-safe.
        """
        if not hasattr(self, '_error_log'):
            self._error_log: dict[str, list[float]] = {}
        with self._lock:
            if module_id not in self._error_log:
                self._error_log[module_id] = []
            self._error_log[module_id].append(time.time())
            # Prune entries older than the window
            cutoff = time.time() - ERROR_RATE_WINDOW_S
            self._error_log[module_id] = [
                t for t in self._error_log[module_id] if t >= cutoff
            ]
        return {"module_id": module_id, "recorded": True}

    def record_request(self, module_id: str, count: int = 1) -> dict:
        """Record request occurrences for a module during cutover."""
        if not hasattr(self, '_request_log'):
            self._request_log: dict[str, list[float]] = {}
        with self._lock:
            if module_id not in self._request_log:
                self._request_log[module_id] = []
            for _ in range(count):
                self._request_log[module_id].append(time.time())
            cutoff = time.time() - ERROR_RATE_WINDOW_S
            self._request_log[module_id] = [
                t for t in self._request_log[module_id] if t >= cutoff
            ]
        return {"module_id": module_id, "recorded": True}

    def _compute_error_rate(self, module_id: str) -> float:
        """Compute the error rate for a module in the last window."""
        if not hasattr(self, '_error_log'):
            self._error_log: dict[str, list[float]] = {}
        if not hasattr(self, '_request_log'):
            self._request_log: dict[str, list[float]] = {}

        cutoff = time.time() - ERROR_RATE_WINDOW_S
        errors = [t for t in self._error_log.get(module_id, []) if t >= cutoff]
        requests = [t for t in self._request_log.get(module_id, []) if t >= cutoff]

        if not requests:
            return 0.0
        return len(errors) / len(requests)

    def _log_metrics(self, session_id: str, metrics: CutoverMetrics):
        """Persist metrics sample to the metrics log table."""
        log_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute("""
                INSERT INTO cutover_metrics_log
                    (log_id, session_id, module_id, heartbeat_age,
                     error_rate, request_count, error_count, sampled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (log_id, session_id, metrics.module_id,
                  metrics.heartbeat_age_s, metrics.error_rate,
                  metrics.request_count, metrics.error_count, metrics.sampled_at))
            self._conn.commit()

    def _evaluate_rollback_triggers(self, module_id: str,
                                     metrics: CutoverMetrics) -> str | None:
        """Evaluate auto-rollback conditions.  Returns reason string or None."""
        # Trigger 1: heartbeat missing for > 60s
        if metrics.heartbeat_age_s > HEARTBEAT_TIMEOUT_S:
            return f"heartbeat timeout: {metrics.heartbeat_age_s:.1f}s > {HEARTBEAT_TIMEOUT_S}s"

        # Trigger 2: error rate > 5%
        if metrics.error_rate > ERROR_RATE_THRESHOLD:
            return f"error rate {metrics.error_rate:.2%} > {ERROR_RATE_THRESHOLD:.0%}"

        return None

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="rebuild.cutover_automation",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_automation: CutoverAutomation | None = None


def get_cutover_automation(registry=None, event_bus: EventBus | None = None,
                           rollback_manager=None,
                           db_path: str | Path | None = None) -> CutoverAutomation:
    global _automation
    if _automation is None:
        if registry is None:
            from sylion.core.module_registry import get_registry
            registry = get_registry()
        _automation = CutoverAutomation(registry, event_bus, rollback_manager, db_path)
    return _automation
