"""
SYLION Rebuild -- Orchestrator

Manages full system rebuild plans and their execution steps.
Tracks plan lifecycle from draft through execution to completion.

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

log = logging.getLogger("sylion.rebuild.orchestrator")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RebuildPlan:
    """A rebuild plan descriptor."""
    plan_id: str = ""
    name: str = ""
    description: str = ""
    status: str = "draft"
    modules: list[str] = field(default_factory=list)
    strategy: str = "progressive"
    created_at: float = 0.0
    completed_at: float = 0.0

    def __post_init__(self):
        if not self.plan_id:
            self.plan_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class RebuildStep:
    """A single step within a rebuild plan."""
    step_id: str = ""
    plan_id: str = ""
    module_id: str = ""
    action: str = "rebuild"
    status: str = "pending"
    order_num: int = 0
    started_at: float = 0.0
    completed_at: float = 0.0

    def __post_init__(self):
        if not self.step_id:
            self.step_id = uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Rebuild Orchestrator
# ---------------------------------------------------------------------------

class RebuildOrchestrator:
    """Manage full system rebuild plans and steps.

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
            CREATE TABLE IF NOT EXISTS rebuild_plans (
                plan_id      TEXT PRIMARY KEY,
                name         TEXT NOT NULL DEFAULT '',
                description  TEXT NOT NULL DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'draft',
                modules      TEXT NOT NULL DEFAULT '[]',
                strategy     TEXT NOT NULL DEFAULT 'progressive',
                created_at   REAL NOT NULL,
                completed_at REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS rebuild_steps (
                step_id      TEXT PRIMARY KEY,
                plan_id      TEXT NOT NULL,
                module_id    TEXT NOT NULL DEFAULT '',
                action       TEXT NOT NULL DEFAULT 'rebuild',
                status       TEXT NOT NULL DEFAULT 'pending',
                order_num    INTEGER NOT NULL DEFAULT 0,
                started_at   REAL NOT NULL DEFAULT 0,
                completed_at REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rsteps_plan ON rebuild_steps(plan_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rplans_status ON rebuild_plans(status)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Plan management
    # ------------------------------------------------------------------

    def create_plan(self, name: str, description: str = "",
                    modules: list[str] | None = None,
                    strategy: str = "progressive") -> dict:
        """Create a new rebuild plan. Returns plan descriptor dict."""
        if modules is None:
            modules = []

        plan = RebuildPlan(
            name=name,
            description=description,
            modules=modules,
            strategy=strategy,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO rebuild_plans
                    (plan_id, name, description, status, modules, strategy,
                     created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                plan.plan_id, plan.name, plan.description, plan.status,
                json.dumps(modules), plan.strategy, plan.created_at,
            ))
            self._conn.commit()

        self._emit("rebuild.orchestrator.plan_created", {
            "plan_id": plan.plan_id, "name": name, "strategy": strategy,
        })

        log.info("created rebuild plan %s (%s)", plan.plan_id[:12], name)
        return {"plan_id": plan.plan_id, "name": name, "status": plan.status}

    def add_step(self, plan_id: str, module_id: str,
                 action: str = "rebuild", order_num: int = 0) -> dict:
        """Add a step to a rebuild plan. Returns step descriptor dict."""
        step = RebuildStep(
            plan_id=plan_id,
            module_id=module_id,
            action=action,
            order_num=order_num,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO rebuild_steps
                    (step_id, plan_id, module_id, action, status,
                     order_num, started_at, completed_at)
                VALUES (?, ?, ?, ?, 'pending', ?, 0, 0)
            """, (
                step.step_id, step.plan_id, step.module_id,
                step.action, step.order_num,
            ))
            self._conn.commit()

        self._emit("rebuild.orchestrator.step_added", {
            "step_id": step.step_id, "plan_id": plan_id,
            "module_id": module_id, "action": action,
        })

        log.info("added step %s to plan %s (module=%s)",
                 step.step_id[:12], plan_id[:12], module_id)
        return {"step_id": step.step_id, "plan_id": plan_id, "status": "pending"}

    def execute_plan(self, plan_id: str) -> dict:
        """Execute a rebuild plan (stub: marks all steps completed).

        Returns summary with count of steps executed.
        """
        rows = self._conn.execute(
            "SELECT * FROM rebuild_steps WHERE plan_id = ? ORDER BY order_num",
            (plan_id,),
        ).fetchall()

        if not rows:
            log.warning("no steps found for plan %s", plan_id[:12])
            return {"plan_id": plan_id, "steps_executed": 0, "status": "completed"}

        now = time.time()

        with self._lock:
            for row in rows:
                self._conn.execute("""
                    UPDATE rebuild_steps
                    SET status = 'completed', started_at = ?, completed_at = ?
                    WHERE step_id = ?
                """, (now, now, row["step_id"]))

            self._conn.execute("""
                UPDATE rebuild_plans
                SET status = 'completed', completed_at = ?
                WHERE plan_id = ?
            """, (now, plan_id))
            self._conn.commit()

        self._emit("rebuild.orchestrator.plan_executed", {
            "plan_id": plan_id, "steps_executed": len(rows),
        })

        log.info("executed plan %s (%d steps)", plan_id[:12], len(rows))
        return {
            "plan_id": plan_id,
            "steps_executed": len(rows),
            "status": "completed",
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_plan(self, plan_id: str) -> dict | None:
        """Get a single rebuild plan by ID."""
        row = self._conn.execute(
            "SELECT * FROM rebuild_plans WHERE plan_id = ?", (plan_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["modules"] = json.loads(result.get("modules", "[]"))
        return result

    def list_plans(self, status: str | None = None,
                   limit: int = 100) -> list[dict]:
        """List rebuild plans, optionally filtered by status."""
        if status:
            rows = self._conn.execute(
                "SELECT * FROM rebuild_plans WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM rebuild_plans ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["modules"] = json.loads(d.get("modules", "[]"))
            results.append(d)
        return results

    def get_steps(self, plan_id: str) -> list[dict]:
        """Get all steps for a plan, ordered by order_num."""
        rows = self._conn.execute(
            "SELECT * FROM rebuild_steps WHERE plan_id = ? ORDER BY order_num",
            (plan_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="rebuild.orchestrator",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_orchestrator: RebuildOrchestrator | None = None


def get_rebuild_orchestrator(db_path: str | Path | None = None,
                             event_bus: EventBus | None = None) -> RebuildOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = RebuildOrchestrator(db_path, event_bus)
    return _orchestrator
