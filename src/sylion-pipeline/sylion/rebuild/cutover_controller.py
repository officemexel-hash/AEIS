"""
SYLION Rebuild -- Cutover Controller

Manages shadow -> dual -> cutover state transitions for module deployments.
Supports automatic rollback and transition event tracking.

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
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.rebuild.cutover_controller")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CutoverPlan:
    """A cutover transition plan."""
    plan_id: str = ""
    module_id: str = ""
    current_state: str = "shadow"
    target_state: str = "cutover"
    auto_rollback: int = 0
    status: str = "pending"
    created_at: float = 0.0
    executed_at: float = 0.0

    def __post_init__(self):
        if not self.plan_id:
            self.plan_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class CutoverEvent:
    """A cutover transition event."""
    event_id: str = ""
    plan_id: str = ""
    event_type: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.event_id:
            self.event_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Cutover Controller
# ---------------------------------------------------------------------------

class CutoverController:
    """Shadow -> dual -> cutover transition controller.

    Thread-safe. SQLite-backed. Emits events to EventBus.
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
            CREATE TABLE IF NOT EXISTS cutover_plans (
                plan_id       TEXT PRIMARY KEY,
                module_id     TEXT NOT NULL DEFAULT '',
                current_state TEXT NOT NULL DEFAULT 'shadow',
                target_state  TEXT NOT NULL DEFAULT 'cutover',
                auto_rollback INTEGER NOT NULL DEFAULT 0,
                status        TEXT NOT NULL DEFAULT 'pending',
                created_at    REAL NOT NULL,
                executed_at   REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cutover_events (
                event_id   TEXT PRIMARY KEY,
                plan_id    TEXT NOT NULL,
                event_type TEXT NOT NULL DEFAULT '',
                details    TEXT NOT NULL DEFAULT '{}',
                timestamp  REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cplan_mod ON cutover_plans(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cevt_plan ON cutover_events(plan_id)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Plan management
    # ------------------------------------------------------------------

    def create_plan(self, module_id: str,
                    current_state: str = "shadow",
                    target_state: str = "cutover",
                    auto_rollback: bool = False) -> dict:
        """Create a cutover transition plan."""
        plan = CutoverPlan(
            module_id=module_id,
            current_state=current_state,
            target_state=target_state,
            auto_rollback=1 if auto_rollback else 0,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO cutover_plans
                    (plan_id, module_id, current_state, target_state,
                     auto_rollback, status, created_at, executed_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, 0)
            """, (
                plan.plan_id, plan.module_id, plan.current_state,
                plan.target_state, plan.auto_rollback, plan.created_at,
            ))
            self._conn.commit()

        self._emit("rebuild.cutover.plan_created", {
            "plan_id": plan.plan_id, "module_id": module_id,
            "current_state": current_state, "target_state": target_state,
        })

        log.info("created cutover plan %s for %s (%s -> %s)",
                 plan.plan_id[:12], module_id, current_state, target_state)
        return {"plan_id": plan.plan_id, "module_id": module_id, "status": "pending"}

    def execute(self, plan_id: str) -> dict:
        """Execute a cutover plan (stub: marks as completed).

        Transitions the plan status to 'completed' and records the event.
        """
        row = self._conn.execute(
            "SELECT * FROM cutover_plans WHERE plan_id = ?", (plan_id,),
        ).fetchone()
        if not row:
            log.warning("cutover plan %s not found", plan_id[:12])
            return {"plan_id": plan_id, "error": "plan not found"}

        now = time.time()

        with self._lock:
            self._conn.execute("""
                UPDATE cutover_plans
                SET status = 'completed', executed_at = ?, current_state = target_state
                WHERE plan_id = ?
            """, (now, plan_id))
            self._conn.commit()

        self.record_event(plan_id, "cutover.executed", {
            "previous_state": row["current_state"],
            "new_state": row["target_state"],
        })

        self._emit("rebuild.cutover.executed", {
            "plan_id": plan_id, "module_id": row["module_id"],
        })

        log.info("executed cutover plan %s", plan_id[:12])
        return {"plan_id": plan_id, "status": "completed", "executed_at": now}

    def rollback(self, plan_id: str) -> dict:
        """Rollback a cutover plan to its previous state."""
        row = self._conn.execute(
            "SELECT * FROM cutover_plans WHERE plan_id = ?", (plan_id,),
        ).fetchone()
        if not row:
            log.warning("cutover plan %s not found for rollback", plan_id[:12])
            return {"plan_id": plan_id, "error": "plan not found"}

        now = time.time()

        with self._lock:
            self._conn.execute("""
                UPDATE cutover_plans
                SET status = 'rolled_back', executed_at = ?,
                    target_state = current_state
                WHERE plan_id = ?
            """, (now, plan_id))
            self._conn.commit()

        self.record_event(plan_id, "cutover.rolled_back", {
            "rolled_back_to": row["current_state"],
        })

        self._emit("rebuild.cutover.rolled_back", {
            "plan_id": plan_id, "module_id": row["module_id"],
        })

        log.info("rolled back cutover plan %s", plan_id[:12])
        return {"plan_id": plan_id, "status": "rolled_back", "executed_at": now}

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def record_event(self, plan_id: str, event_type: str,
                     details: dict | None = None) -> dict:
        """Record a cutover transition event."""
        if details is None:
            details = {}

        evt = CutoverEvent(
            plan_id=plan_id,
            event_type=event_type,
            details=details,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO cutover_events
                    (event_id, plan_id, event_type, details, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                evt.event_id, evt.plan_id, evt.event_type,
                json.dumps(details, default=str), evt.timestamp,
            ))
            self._conn.commit()

        log.info("recorded cutover event %s: %s", evt.event_id[:12], event_type)
        return {
            "event_id": evt.event_id,
            "plan_id": plan_id,
            "event_type": event_type,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_plan(self, plan_id: str) -> dict | None:
        """Get a single cutover plan by ID."""
        row = self._conn.execute(
            "SELECT * FROM cutover_plans WHERE plan_id = ?", (plan_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_plans(self, status: str | None = None,
                   module_id: str | None = None,
                   limit: int = 100) -> list[dict]:
        """List cutover plans, optionally filtered by status and/or module."""
        query = "SELECT * FROM cutover_plans WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if module_id:
            query += " AND module_id = ?"
            params.append(module_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="rebuild.cutover_controller",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_controller: CutoverController | None = None


def get_cutover_controller(db_path: str | Path | None = None,
                           event_bus: EventBus | None = None) -> CutoverController:
    global _controller
    if _controller is None:
        _controller = CutoverController(db_path, event_bus)
    return _controller
