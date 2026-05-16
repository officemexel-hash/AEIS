"""
SYLION Pipeline -- State Machine

Tracks pipeline execution state transitions with decision-gate integration.
Enables the pipeline to respect decision changes mid-execution by rolling
back to planning when affected decisions change during generating/reviewing.

States: idle -> planning -> planned -> generating -> reviewing -> complete -> archived
Special: cancelled (from any active), paused (from any active, resumes to last state)

Tables:
  pipeline_run_states   -- current state per pipeline run
  pipeline_state_log    -- chronological transition log

Singleton: get_pipeline_state_machine() / reset_pipeline_state_machine()
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.pipeline.state_machine")

# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------

STATES = (
    "idle",
    "planning",
    "planned",
    "generating",
    "reviewing",
    "complete",
    "archived",
    "paused",
    "cancelled",
    # W14 E6 (append-only): release-rail states. Adding to the end of the
    # tuple so any external caller that relied on positional indexing
    # keeps working.
    "release_candidate",
    "production_ready",
    "blocked_by_test",
)

ACTIVE_STATES = frozenset({
    "idle", "planning", "planned", "generating", "reviewing",
    # Release states are also "active" in the sense that the run is not
    # yet archived/cancelled.
    "release_candidate", "production_ready", "blocked_by_test",
})

# Allowed transitions: {from_state: {to_state, ...}}
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "idle":       {"planning"},
    "planning":   {"planned", "cancelled", "paused"},
    "planned":    {"generating", "cancelled", "paused"},
    "generating": {"reviewing", "cancelled", "paused", "planning"},
    "reviewing":  {"complete", "generating", "cancelled", "paused", "planning"},
    # W14 E6: complete -> release_candidate (auto-trigger ReleaseRail.evaluate)
    "complete":   {"archived", "release_candidate"},
    "archived":   set(),
    "paused":     {"idle", "planning", "planned", "generating", "reviewing",
                   "cancelled"},
    "cancelled":  set(),
    # release_candidate -> production_ready (after HG approve)
    # release_candidate -> blocked_by_test (when ReleaseRail blocks)
    # release_candidate -> archived (rollback path)
    "release_candidate": {"production_ready", "blocked_by_test", "archived",
                           "cancelled"},
    # production_ready terminates into archived (PRODUCTION_RELEASED upstream)
    "production_ready":  {"archived", "blocked_by_test"},
    # blocked_by_test -> release_candidate after fix; or cancelled
    "blocked_by_test":   {"release_candidate", "cancelled"},
}

# W14 E6: states that imply a ReleaseRail re-evaluation should fire.
RELEASE_TRIGGER_STATES: frozenset[str] = frozenset({
    "complete", "release_candidate", "blocked_by_test",
})


class PipelineStateMachine:
    """State machine for pipeline run lifecycle.

    Thread-safe via RLock. SQLite-backed for persistence. Emits events on
    every transition.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        event_bus: EventBus | None = None,
    ):
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
            CREATE TABLE IF NOT EXISTS pipeline_run_states (
                run_id             TEXT PRIMARY KEY,
                current_state      TEXT NOT NULL DEFAULT 'idle',
                previous_state     TEXT,
                paused_from        TEXT,
                state_entered_at   REAL NOT NULL,
                total_revisions    INTEGER DEFAULT 0,
                cancelled          INTEGER DEFAULT 0,
                cancellation_reason TEXT,
                updated_at         REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pipeline_state_log (
                log_id       TEXT PRIMARY KEY,
                run_id       TEXT NOT NULL,
                from_state   TEXT NOT NULL,
                to_state     TEXT NOT NULL,
                trigger      TEXT NOT NULL,
                snapshot_id  TEXT,
                gate_id      TEXT,
                decision_id  TEXT,
                metadata     TEXT,
                created_at   REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_psl_run
                ON pipeline_state_log(run_id);
            CREATE INDEX IF NOT EXISTS idx_psl_trigger
                ON pipeline_state_log(trigger);
            CREATE INDEX IF NOT EXISTS idx_psl_created
                ON pipeline_state_log(created_at);
            CREATE INDEX IF NOT EXISTS idx_prs_state
                ON pipeline_run_states(current_state);
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
                event_id="",
                topic=topic,
                payload=payload,
                source_module="pipeline_state_machine",
            ))

    def _validate_transition(self, from_state: str, to_state: str) -> bool:
        allowed = ALLOWED_TRANSITIONS.get(from_state, set())
        return to_state in allowed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_run(self, run_id: str, initial_state: str = "idle") -> dict:
        """Create a new pipeline run state record.

        Raises ValueError if run_id already exists.
        """
        now = time.time()
        with self._lock:
            existing = self._conn.execute(
                "SELECT run_id FROM pipeline_run_states WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if existing:
                raise ValueError(f"run_id '{run_id}' already exists")

            self._conn.execute("""
                INSERT INTO pipeline_run_states
                    (run_id, current_state, previous_state, paused_from,
                     state_entered_at, total_revisions, cancelled,
                     cancellation_reason, updated_at)
                VALUES (?, ?, NULL, NULL, ?, 0, 0, NULL, ?)
            """, (run_id, initial_state, now, now))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM pipeline_run_states WHERE run_id = ?",
                (run_id,),
            ).fetchone()

        result = dict(row)
        self._emit("pipeline.run.created", {
            "run_id": run_id,
            "initial_state": initial_state,
        })
        log.info("created run %s in state %s", run_id[:12], initial_state)
        return result

    def transition(
        self,
        run_id: str,
        to_state: str,
        trigger: str = "auto",
        snapshot_id: str | None = None,
        gate_id: str | None = None,
        decision_id: str | None = None,
        metadata: dict | None = None,
        _cancellation_reason: str | None = None,
    ) -> dict:
        """Execute a state transition for a pipeline run.

        Validates the transition is allowed, logs it, updates run state.
        Returns the transition log record.
        Raises ValueError if the run does not exist or transition is invalid.
        """
        log_id = self._uid()
        now = time.time()

        with self._lock:
            run = self._conn.execute(
                "SELECT * FROM pipeline_run_states WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if not run:
                raise ValueError(f"run_id '{run_id}' not found")

            from_state = run["current_state"]

            if not self._validate_transition(from_state, to_state):
                raise ValueError(
                    f"invalid transition: {from_state} -> {to_state}"
                )

            # Track revision loops (reviewing -> generating)
            new_revisions = run["total_revisions"]
            if from_state == "reviewing" and to_state == "generating":
                new_revisions += 1

            # Handle pause: save current state
            new_paused_from = run["paused_from"]
            if to_state == "paused":
                new_paused_from = from_state

            # Handle resume: restore paused_from state
            new_current = to_state
            new_previous = from_state
            if from_state == "paused" and to_state not in ("cancelled",):
                # Resuming: the actual target is to_state (caller specifies)
                new_paused_from = None

            if to_state == "cancelled":
                self._conn.execute("""
                    UPDATE pipeline_run_states
                    SET current_state = ?,
                        previous_state = ?,
                        paused_from = NULL,
                        total_revisions = ?,
                        cancelled = 1,
                        cancellation_reason = ?,
                        updated_at = ?
                    WHERE run_id = ?
                """, (to_state, from_state, new_revisions,
                      _cancellation_reason, now, run_id))
            else:
                self._conn.execute("""
                    UPDATE pipeline_run_states
                    SET current_state = ?,
                        previous_state = ?,
                        paused_from = ?,
                        total_revisions = ?,
                        cancelled = 0,
                        cancellation_reason = NULL,
                        updated_at = ?
                    WHERE run_id = ?
                """, (new_current, new_previous, new_paused_from,
                      new_revisions, now, run_id))

            # Log the transition
            meta_json = json.dumps(metadata) if metadata else None
            self._conn.execute("""
                INSERT INTO pipeline_state_log
                    (log_id, run_id, from_state, to_state, trigger,
                     snapshot_id, gate_id, decision_id, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (log_id, run_id, from_state, to_state, trigger,
                  snapshot_id, gate_id, decision_id, meta_json, now))
            self._conn.commit()

            log_row = self._conn.execute(
                "SELECT * FROM pipeline_state_log WHERE log_id = ?",
                (log_id,),
            ).fetchone()

        result = dict(log_row)
        self._emit("pipeline.state.transitioned", {
            "run_id": run_id,
            "from_state": from_state,
            "to_state": to_state,
            "trigger": trigger,
        })
        log.info("run %s: %s -> %s (trigger=%s)",
                 run_id[:12], from_state, to_state, trigger)
        return result

    def get_state(self, run_id: str) -> dict | None:
        """Return current run state record, or None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM pipeline_run_states WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_history(self, run_id: str) -> list[dict]:
        """Return all state transitions for a run in chronological order."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM pipeline_state_log WHERE run_id = ? "
                "ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def pause(self, run_id: str) -> dict:
        """Pause a run, saving current state for later resume.

        Raises ValueError if run not found or already paused/cancelled.
        """
        state = self.get_state(run_id)
        if not state:
            raise ValueError(f"run_id '{run_id}' not found")
        if state["current_state"] == "paused":
            raise ValueError(f"run '{run_id}' is already paused")
        if state["current_state"] == "cancelled":
            raise ValueError(f"run '{run_id}' is cancelled")
        if state["current_state"] in ("complete", "archived"):
            raise ValueError(
                f"cannot pause run '{run_id}' in state {state['current_state']}"
            )
        return self.transition(run_id, "paused", trigger="manual")

    def resume(self, run_id: str) -> dict:
        """Resume a paused run back to its pre-pause state.

        Raises ValueError if run not found, not paused, or paused_from missing.
        """
        state = self.get_state(run_id)
        if not state:
            raise ValueError(f"run_id '{run_id}' not found")
        if state["current_state"] != "paused":
            raise ValueError(f"run '{run_id}' is not paused")
        if not state["paused_from"]:
            raise ValueError(f"run '{run_id}' has no paused_from state")

        return self.transition(
            run_id, state["paused_from"], trigger="manual",
        )

    def cancel(self, run_id: str, reason: str = "") -> dict:
        """Cancel a run from any active or paused state.

        Raises ValueError if run not found or already in terminal state.
        """
        state = self.get_state(run_id)
        if not state:
            raise ValueError(f"run_id '{run_id}' not found")
        if state["current_state"] == "cancelled":
            raise ValueError(f"run '{run_id}' is already cancelled")

        result = self.transition(
            run_id, "cancelled", trigger="manual",
            _cancellation_reason=reason or None,
        )
        log.info("run %s cancelled: %s", run_id[:12], reason)
        return result

    def handle_decision_change(
        self,
        run_id: str,
        snapshot_id: str | None = None,
        decision_id: str | None = None,
    ) -> dict:
        """Handle a decision change mid-pipeline.

        If the run is in generating or reviewing state, roll back to planning.
        Otherwise, no action needed.

        Returns {rolled_back: bool, from_state: str, to_state: str}.
        """
        state = self.get_state(run_id)
        if not state:
            raise ValueError(f"run_id '{run_id}' not found")

        current = state["current_state"]

        # Only roll back if in generating or reviewing
        if current not in ("generating", "reviewing"):
            return {
                "rolled_back": False,
                "from_state": current,
                "to_state": current,
            }

        # Transition back to planning
        meta = {
            "reason": "decision_change",
            "original_state": current,
        }
        if snapshot_id:
            meta["snapshot_id"] = snapshot_id
        if decision_id:
            meta["decision_id"] = decision_id

        self.transition(
            run_id, "planning", trigger="decision_change",
            snapshot_id=snapshot_id,
            decision_id=decision_id,
            metadata=meta,
        )

        return {
            "rolled_back": True,
            "from_state": current,
            "to_state": "planning",
        }

    def list_active_runs(self) -> list[dict]:
        """Return all runs not in complete, archived, or cancelled states."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM pipeline_run_states "
                "WHERE current_state NOT IN ('complete', 'archived', 'cancelled') "
                "ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_run_stats(self) -> dict[str, Any]:
        """Return aggregate stats: {total, by_state: {state: count}, active_count}."""
        with self._lock:
            total_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM pipeline_run_states"
            ).fetchone()
            total = total_row["cnt"] if total_row else 0

            state_rows = self._conn.execute(
                "SELECT current_state, COUNT(*) as cnt "
                "FROM pipeline_run_states GROUP BY current_state"
            ).fetchall()
            by_state = {r["current_state"]: r["cnt"] for r in state_rows}

            active_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM pipeline_run_states "
                "WHERE current_state NOT IN ('complete', 'archived', 'cancelled')"
            ).fetchone()
            active_count = active_row["cnt"] if active_row else 0

        return {
            "total": total,
            "by_state": by_state,
            "active_count": active_count,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_machine: PipelineStateMachine | None = None


def get_pipeline_state_machine(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> PipelineStateMachine:
    global _machine
    if _machine is None:
        _machine = PipelineStateMachine(db_path, event_bus)
    return _machine


def reset_pipeline_state_machine(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> PipelineStateMachine:
    global _machine
    _machine = PipelineStateMachine(db_path, event_bus)
    return _machine
