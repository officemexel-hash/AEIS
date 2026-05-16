"""
SYLION Cognitive -- Planner

Task decomposition and plan management. Supports hierarchical plans
with dependent tasks, priority ordering, and status tracking.

Thread-safe. SQLite-backed. Emits events on plan/task mutations.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.cognitive.planner")


def _allow_llm_fallback() -> bool:
    return os.environ.get("SYLION_ALLOW_LLM_STUB") == "1"


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class PlanStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Plan:
    """A plan containing tasks."""
    plan_id: str = ""
    title: str = ""
    description: str = ""
    status: str = "pending"
    parent_plan: str = ""
    created_at: float = 0.0
    completed_at: float = 0.0

    def __post_init__(self):
        if not self.plan_id:
            self.plan_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class Task:
    """A task within a plan."""
    task_id: str = ""
    plan_id: str = ""
    title: str = ""
    description: str = ""
    status: str = "pending"
    priority: int = 0
    depends_on: str = "[]"
    assigned_to: str = ""
    created_at: float = 0.0
    completed_at: float = 0.0

    def __post_init__(self):
        if not self.task_id:
            self.task_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class Planner:
    """Task decomposition and plan management.

    Thread-safe. SQLite-backed. Emits events on plan/task mutations.
    """

    def __init__(self, event_bus: EventBus | None = None,
                 db_path: str | Path | None = None,
                 llm_adapter=None):
        self._event_bus = event_bus
        self._llm_adapter = llm_adapter
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                plan_id      TEXT PRIMARY KEY,
                title        TEXT NOT NULL DEFAULT '',
                description  TEXT NOT NULL DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'pending',
                parent_plan  TEXT NOT NULL DEFAULT '',
                created_at   REAL NOT NULL,
                completed_at REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id      TEXT PRIMARY KEY,
                plan_id      TEXT NOT NULL DEFAULT '',
                title        TEXT NOT NULL DEFAULT '',
                description  TEXT NOT NULL DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'pending',
                priority     INTEGER NOT NULL DEFAULT 0,
                depends_on   TEXT NOT NULL DEFAULT '[]',
                assigned_to  TEXT NOT NULL DEFAULT '',
                created_at   REAL NOT NULL,
                completed_at REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_plan ON tasks(plan_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_plans_parent ON plans(parent_plan)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Plan operations
    # ------------------------------------------------------------------

    def create_plan(self, title: str, description: str = "",
                    parent_plan: str = "") -> dict:
        """Create a new plan. Returns plan dict."""
        plan = Plan(title=title, description=description,
                    parent_plan=parent_plan)

        with self._lock:
            self._conn.execute("""
                INSERT INTO plans (plan_id, title, description, status,
                                   parent_plan, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                plan.plan_id, plan.title, plan.description, plan.status,
                plan.parent_plan, plan.created_at, plan.completed_at,
            ))
            self._conn.commit()

        self._emit("plan.created", {
            "plan_id": plan.plan_id,
            "title": title,
            "parent_plan": parent_plan,
        })
        log.info("created plan %s: %s", plan.plan_id[:12], title)
        return {
            "plan_id": plan.plan_id,
            "title": plan.title,
            "status": plan.status,
            "created_at": plan.created_at,
        }

    def get_plan(self, plan_id: str) -> dict | None:
        """Retrieve a plan by ID."""
        row = self._conn.execute(
            "SELECT * FROM plans WHERE plan_id = ?", (plan_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_plans(self, status: str | None = None) -> list[dict]:
        """List plans, optionally filtered by status."""
        if status:
            rows = self._conn.execute(
                "SELECT * FROM plans WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM plans ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    def add_task(self, plan_id: str, title: str, description: str = "",
                 priority: int = 0, depends_on: list | None = None) -> dict:
        """Add a task to a plan. Returns task dict."""
        if depends_on is None:
            depends_on = []

        task = Task(
            plan_id=plan_id,
            title=title,
            description=description,
            priority=priority,
            depends_on=json.dumps(depends_on),
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO tasks (task_id, plan_id, title, description, status,
                                   priority, depends_on, assigned_to,
                                   created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id, task.plan_id, task.title, task.description,
                task.status, task.priority, task.depends_on, task.assigned_to,
                task.created_at, task.completed_at,
            ))
            self._conn.commit()

        self._emit("task.added", {
            "task_id": task.task_id,
            "plan_id": plan_id,
            "title": title,
        })
        log.info("added task %s to plan %s", task.task_id[:12], plan_id[:12])
        return {
            "task_id": task.task_id,
            "plan_id": plan_id,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
        }

    def decompose(self, plan_id: str, subtasks: list[dict]) -> list[dict]:
        """Create multiple tasks for a plan at once.

        Each subtask dict may contain: title, description, priority, depends_on.
        Returns list of task dicts.
        """
        results: list[dict] = []
        for sub in subtasks:
            result = self.add_task(
                plan_id=plan_id,
                title=sub.get("title", ""),
                description=sub.get("description", ""),
                priority=sub.get("priority", 0),
                depends_on=sub.get("depends_on", []),
            )
            results.append(result)

        self._emit("plan.decomposed", {
            "plan_id": plan_id,
            "task_count": len(results),
        })
        log.info("decomposed plan %s into %d tasks", plan_id[:12], len(results))
        return results

    def _artifact_steps_for_idea(self, idea: str) -> list[dict]:
        """Build deterministic, domain-bound AEIS product steps in Polish."""
        return [
            {
                "step_id": "artifact_contract",
                "name": "Kontrakt artefaktu",
                "description": (
                    "Zdefiniuj kontrakt produktu dla pomysłu. Wypisz domenę, użytkowników, funkcje, "
                    "zakazane generyczne fallbacki, wymagane artefakty, testy akceptacyjne i bramki Human Gate/Guard. "
                    f"Pomysł: {idea}"
                ),
                "priority": 10,
            },
            {
                "step_id": "product_design",
                "name": "Projekt produktu",
                "description": (
                    "Zaprojektuj konkretny produkt zgodny z pomysłem. Opisz dane, ekrany/API, przepływy człowieka, "
                    "decyzje Rady, pamięć, skille, funding i guardy tylko wtedy, gdy wynikają z domeny. "
                    f"Pomysł: {idea}"
                ),
                "priority": 9,
            },
            {
                "step_id": "implementation_artifact",
                "name": "Artefakt implementacyjny",
                "description": (
                    "Wytwórz główny artefakt implementacyjny dopasowany do domeny. Nie wolno używać Hello World, "
                    "losowych usług chmurowych, example.com, Slack ani przykładu edukacyjnego. "
                    f"Pomysł: {idea}"
                ),
                "priority": 8,
            },
            {
                "step_id": "acceptance_tests",
                "name": "Testy akceptacyjne",
                "description": (
                    "Napisz testy akceptacyjne produktu i testy guardów. Każdy test musi sprawdzać realną funkcję "
                    "z pomysłu oraz wskazywać dane wejściowe, oczekiwany wynik i kryterium zaliczenia. "
                    f"Pomysł: {idea}"
                ),
                "priority": 7,
            },
            {
                "step_id": "final_quality_report",
                "name": "Raport jakości",
                "description": (
                    "Oceń gotowość produktu, wskaż braki, ryzyka, decyzje Human Gate, wynik guardów i czy produkt "
                    "może zostać uznany za zaliczony. Nie wolno oznaczać produktu jako gotowego bez artefaktu i testów. "
                    f"Pomysł: {idea}"
                ),
                "priority": 6,
            },
        ]

    def decompose_idea(self, idea: str) -> dict:
        """Decompose an idea string into a structured plan with steps.

        Used by the pipeline controller to convert a user idea into
        actionable plan steps. Returns dict with plan_id, title, and steps.
        If an llm_adapter is available, uses it for intelligent decomposition;
        otherwise falls back to heuristic decomposition.
        """
        plan_dict = self.create_plan(title=idea[:80], description=idea)

        steps = self._artifact_steps_for_idea(idea)

        if os.environ.get("SYLION_USE_LLM_PLANNER") == "1" and self._llm_adapter is not None:
            try:
                prompt = (
                    f"Decompose this software idea into implementation steps.\n"
                    f"Idea: {idea}\n\n"
                    f"Return a JSON array of objects with fields: step_id, name, description, priority.\n"
                    f"Use standard phases: analyze, design, implement, test, review."
                )
                response = self._llm_adapter.call("", prompt)
                status = response.get("status")
                if status in {"stub", "fallback", "blocked"} and not _allow_llm_fallback():
                    raise RuntimeError(f"LLM planner returned disabled status={status}")
                text = response.get("text", "")
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\[.*\]', text, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    if isinstance(parsed, list) and len(parsed) > 0:
                        steps = parsed
            except Exception:
                if not _allow_llm_fallback():
                    raise
                log.exception("LLM decomposition failed, using heuristic steps")
        # Add tasks to the plan
        for step in steps:
            self.add_task(
                plan_id=plan_dict["plan_id"],
                title=step.get("name", ""),
                description=step.get("description", ""),
                priority=step.get("priority", 0),
            )

        return {
            "plan_id": plan_dict["plan_id"],
            "title": idea[:80],
            "steps": steps,
        }

    def complete_task(self, task_id: str) -> dict | None:
        """Mark a task as completed. Returns updated task dict or None."""
        now = time.time()
        with self._lock:
            updated = self._conn.execute("""
                UPDATE tasks SET status = ?, completed_at = ?
                WHERE task_id = ?
            """, (PlanStatus.COMPLETED.value, now, task_id)).rowcount
            self._conn.commit()

        if not updated:
            return None

        self._emit("task.completed", {"task_id": task_id})
        log.info("completed task %s", task_id[:12])

        row = self._conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_tasks(self, plan_id: str, status: str | None = None) -> list[dict]:
        """Get tasks for a plan, optionally filtered by status."""
        if status:
            rows = self._conn.execute("""
                SELECT * FROM tasks
                WHERE plan_id = ? AND status = ?
                ORDER BY priority DESC, created_at ASC
            """, (plan_id, status)).fetchall()
        else:
            rows = self._conn.execute("""
                SELECT * FROM tasks
                WHERE plan_id = ?
                ORDER BY priority DESC, created_at ASC
            """, (plan_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_next_task(self, plan_id: str) -> dict | None:
        """Return the highest-priority pending task whose dependencies are met.

        A dependency is met when the depended-on task has status 'completed'.
        Returns None if no eligible task is found.
        """
        rows = self._conn.execute("""
            SELECT * FROM tasks
            WHERE plan_id = ? AND status = ?
            ORDER BY priority DESC, created_at ASC
        """, (plan_id, PlanStatus.PENDING.value)).fetchall()

        for row in rows:
            depends_on: list[str] = json.loads(row["depends_on"])
            if not depends_on:
                return dict(row)

            # Check that all dependencies are completed
            all_met = True
            for dep_id in depends_on:
                dep = self._conn.execute(
                    "SELECT status FROM tasks WHERE task_id = ?", (dep_id,)
                ).fetchone()
                if not dep or dep["status"] != PlanStatus.COMPLETED.value:
                    all_met = False
                    break

            if all_met:
                return dict(row)

        return None

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cognitive.planner",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_planner: Planner | None = None


def get_planner(event_bus: EventBus | None = None,
                db_path: str | Path | None = None,
                llm_adapter=None) -> Planner:
    global _planner
    if _planner is None:
        _planner = Planner(event_bus, db_path, llm_adapter)
    return _planner
