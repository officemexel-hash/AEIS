"""
SYLION Execution — Execution Planner

Plans, orders, and tracks multi-step execution workflows.
Each plan contains steps (tool_call, api_request, script, decision,
parallel_group) with optional dependency edges.  Execution order is
resolved via topological sort.

Tables:
  execution_plans   -- plan-level metadata + status
  plan_steps        -- individual steps inside a plan
  plan_dependencies -- directed edges between steps

Singleton: get_execution_planner() / reset_execution_planner()
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

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.execution.execution_planner")

VALID_STEP_TYPES = ("tool_call", "api_request", "script", "decision", "parallel_group")
VALID_PLAN_STATUSES = ("pending", "running", "completed", "cancelled", "failed")
VALID_STEP_STATUSES = ("pending", "running", "completed", "failed", "skipped")


class ExecutionPlanner:
    """Plan-based execution orchestrator backed by SQLite.

    Plans contain ordered steps with optional dependency edges.
    Steps execute in topological order respecting dependencies.
    Thread-safe via RLock; emits events through EventBus.
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
            CREATE TABLE IF NOT EXISTS execution_plans (
                plan_id      TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                description  TEXT,
                status       TEXT NOT NULL DEFAULT 'pending',
                created_by   TEXT,
                created_at   REAL NOT NULL,
                updated_at   REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS plan_steps (
                step_id     TEXT PRIMARY KEY,
                plan_id     TEXT NOT NULL,
                name        TEXT NOT NULL,
                step_type   TEXT NOT NULL,
                config      TEXT,
                step_order  INTEGER NOT NULL DEFAULT 0,
                status      TEXT NOT NULL DEFAULT 'pending',
                result      TEXT,
                error       TEXT,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL,
                FOREIGN KEY (plan_id) REFERENCES execution_plans(plan_id)
            );

            CREATE TABLE IF NOT EXISTS plan_dependencies (
                dependency_id    TEXT PRIMARY KEY,
                step_id          TEXT NOT NULL,
                depends_on_step_id TEXT NOT NULL,
                created_at       REAL NOT NULL,
                FOREIGN KEY (step_id)          REFERENCES plan_steps(step_id),
                FOREIGN KEY (depends_on_step_id) REFERENCES plan_steps(step_id),
                UNIQUE(step_id, depends_on_step_id)
            );

            CREATE INDEX IF NOT EXISTS idx_steps_plan
                ON plan_steps(plan_id);
            CREATE INDEX IF NOT EXISTS idx_steps_status
                ON plan_steps(status);
            CREATE INDEX IF NOT EXISTS idx_steps_order
                ON plan_steps(plan_id, step_order);
            CREATE INDEX IF NOT EXISTS idx_deps_step
                ON plan_dependencies(step_id);
            CREATE INDEX IF NOT EXISTS idx_deps_depends
                ON plan_dependencies(depends_on_step_id);
            CREATE INDEX IF NOT EXISTS idx_plans_status
                ON execution_plans(status);
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
                source_module="execution.execution_planner",
            ))

    @staticmethod
    def _parse_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        for key in ("config", "result", "error"):
            if d.get(key) is not None:
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    @staticmethod
    def _now() -> float:
        return time.time()

    def _validate_step_type(self, step_type: str):
        if step_type not in VALID_STEP_TYPES:
            raise ValueError(
                f"Invalid step_type '{step_type}', "
                f"must be one of {VALID_STEP_TYPES}"
            )

    def _validate_plan_status(self, status: str):
        if status not in VALID_PLAN_STATUSES:
            raise ValueError(
                f"Invalid plan status '{status}', "
                f"must be one of {VALID_PLAN_STATUSES}"
            )

    def _validate_step_status(self, status: str):
        if status not in VALID_STEP_STATUSES:
            raise ValueError(
                f"Invalid step status '{status}', "
                f"must be one of {VALID_STEP_STATUSES}"
            )

    # ------------------------------------------------------------------
    # Plan CRUD
    # ------------------------------------------------------------------

    def create_plan(self, name: str, description: str | None = None,
                    created_by: str | None = None) -> dict:
        """Create a new execution plan."""
        plan_id = self._uid()
        now = self._now()

        with self._lock:
            self._conn.execute("""
                INSERT INTO execution_plans
                    (plan_id, name, description, status, created_by,
                     created_at, updated_at)
                VALUES (?, ?, ?, 'pending', ?, ?, ?)
            """, (plan_id, name, description, created_by, now, now))
            self._conn.commit()

        result = {
            "plan_id": plan_id,
            "name": name,
            "description": description,
            "status": "pending",
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
        }

        self._emit("plan.created", {
            "plan_id": plan_id,
            "name": name,
            "created_by": created_by,
        })
        log.info("plan created: %s (%s)", plan_id, name)
        return result

    def get_plan(self, plan_id: str) -> dict | None:
        """Get plan with its steps."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM execution_plans WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
            if not row:
                return None

            plan = self._parse_row(row)

            steps = self._conn.execute(
                "SELECT * FROM plan_steps WHERE plan_id = ? ORDER BY step_order ASC",
                (plan_id,),
            ).fetchall()
            plan["steps"] = [self._parse_row(s) for s in steps]

        return plan

    def list_plans(self, status: str | None = None,
                   limit: int = 50, offset: int = 0) -> list[dict]:
        """List plans, optionally filtered by status."""
        with self._lock:
            q = "SELECT * FROM execution_plans WHERE 1=1"
            params: list[Any] = []
            if status is not None:
                q += " AND status = ?"
                params.append(status)
            q += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = self._conn.execute(q, params).fetchall()
        return [self._parse_row(r) for r in rows]

    def delete_plan(self, plan_id: str) -> bool:
        """Delete a plan and all its steps and dependencies."""
        with self._lock:
            row = self._conn.execute(
                "SELECT plan_id FROM execution_plans WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
            if not row:
                return False

            # Get step ids for dependency cleanup
            step_ids = self._conn.execute(
                "SELECT step_id FROM plan_steps WHERE plan_id = ?",
                (plan_id,),
            ).fetchall()
            step_id_list = [s["step_id"] for s in step_ids]

            # Delete dependencies referencing these steps
            if step_id_list:
                placeholders = ",".join("?" * len(step_id_list))
                self._conn.execute(
                    f"DELETE FROM plan_dependencies WHERE step_id IN ({placeholders})",
                    step_id_list,
                )
                self._conn.execute(
                    f"DELETE FROM plan_dependencies WHERE depends_on_step_id IN ({placeholders})",
                    step_id_list,
                )

            self._conn.execute(
                "DELETE FROM plan_steps WHERE plan_id = ?", (plan_id,))
            self._conn.execute(
                "DELETE FROM execution_plans WHERE plan_id = ?", (plan_id,))
            self._conn.commit()

        log.info("plan deleted: %s", plan_id)
        return True

    # ------------------------------------------------------------------
    # Step CRUD
    # ------------------------------------------------------------------

    def add_step(self, plan_id: str, name: str, step_type: str,
                 config: dict | None = None,
                 order: int | None = None) -> dict:
        """Add a step to a plan."""
        self._validate_step_type(step_type)

        step_id = self._uid()
        now = self._now()
        config_json = (
            json.dumps(config, sort_keys=True, default=str)
            if config is not None else None
        )

        with self._lock:
            # Verify plan exists
            plan_row = self._conn.execute(
                "SELECT plan_id FROM execution_plans WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
            if not plan_row:
                raise ValueError(f"Plan '{plan_id}' not found")

            # Determine order: max + 1 if not specified
            if order is None:
                max_row = self._conn.execute(
                    "SELECT MAX(step_order) as max_o FROM plan_steps WHERE plan_id = ?",
                    (plan_id,),
                ).fetchone()
                order = (max_row["max_o"] + 1) if max_row["max_o"] is not None else 0

            self._conn.execute("""
                INSERT INTO plan_steps
                    (step_id, plan_id, name, step_type, config,
                     step_order, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """, (step_id, plan_id, name, step_type, config_json,
                  order, now, now))
            self._conn.commit()

        result = {
            "step_id": step_id,
            "plan_id": plan_id,
            "name": name,
            "step_type": step_type,
            "config": config,
            "step_order": order,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        }
        log.info("step added: %s (%s) to plan %s", step_id, name, plan_id)
        return result

    def update_step(self, step_id: str, **kwargs) -> dict | None:
        """Update step fields (name, step_type, config, step_order, status)."""
        allowed = {"name", "step_type", "config", "step_order", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return None

        if "step_type" in updates:
            self._validate_step_type(updates["step_type"])
        if "status" in updates:
            self._validate_step_status(updates["status"])

        now = self._now()

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM plan_steps WHERE step_id = ?",
                (step_id,),
            ).fetchone()
            if not row:
                return None

            set_clauses = []
            values: list[Any] = []
            for k, v in updates.items():
                if k == "config":
                    set_clauses.append(f"{k} = ?")
                    values.append(
                        json.dumps(v, sort_keys=True, default=str)
                        if v is not None else None
                    )
                else:
                    set_clauses.append(f"{k} = ?")
                    values.append(v)

            set_clauses.append("updated_at = ?")
            values.append(now)
            values.append(step_id)

            self._conn.execute(
                f"UPDATE plan_steps SET {', '.join(set_clauses)} WHERE step_id = ?",
                values,
            )
            self._conn.commit()

            updated = self._conn.execute(
                "SELECT * FROM plan_steps WHERE step_id = ?",
                (step_id,),
            ).fetchone()

        return self._parse_row(updated)

    def remove_step(self, step_id: str) -> bool:
        """Remove a step and its dependencies."""
        with self._lock:
            row = self._conn.execute(
                "SELECT step_id FROM plan_steps WHERE step_id = ?",
                (step_id,),
            ).fetchone()
            if not row:
                return False

            self._conn.execute(
                "DELETE FROM plan_dependencies WHERE step_id = ? OR depends_on_step_id = ?",
                (step_id, step_id),
            )
            self._conn.execute(
                "DELETE FROM plan_steps WHERE step_id = ?", (step_id,))
            self._conn.commit()

        log.info("step removed: %s", step_id)
        return True

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def add_dependency(self, step_id: str, depends_on_step_id: str) -> dict:
        """Add a dependency edge: step_id depends on depends_on_step_id."""
        dep_id = self._uid()
        now = self._now()

        with self._lock:
            # Verify both steps exist
            s1 = self._conn.execute(
                "SELECT step_id, plan_id FROM plan_steps WHERE step_id = ?",
                (step_id,),
            ).fetchone()
            s2 = self._conn.execute(
                "SELECT step_id, plan_id FROM plan_steps WHERE step_id = ?",
                (depends_on_step_id,),
            ).fetchone()
            if not s1:
                raise ValueError(f"Step '{step_id}' not found")
            if not s2:
                raise ValueError(f"Step '{depends_on_step_id}' not found")
            if s1["plan_id"] != s2["plan_id"]:
                raise ValueError("Cannot add dependency between steps in different plans")
            if step_id == depends_on_step_id:
                raise ValueError("A step cannot depend on itself")

            # Check for existing dependency (UNIQUE constraint will also catch this)
            existing = self._conn.execute(
                "SELECT dependency_id FROM plan_dependencies "
                "WHERE step_id = ? AND depends_on_step_id = ?",
                (step_id, depends_on_step_id),
            ).fetchone()
            if existing:
                raise ValueError(
                    f"Dependency already exists: {step_id} -> {depends_on_step_id}"
                )

            # Check for cycle: would adding this edge create a cycle?
            if self._would_create_cycle(step_id, depends_on_step_id):
                raise ValueError(
                    f"Adding dependency {step_id} -> {depends_on_step_id} would create a cycle"
                )

            self._conn.execute("""
                INSERT INTO plan_dependencies
                    (dependency_id, step_id, depends_on_step_id, created_at)
                VALUES (?, ?, ?, ?)
            """, (dep_id, step_id, depends_on_step_id, now))
            self._conn.commit()

        result = {
            "dependency_id": dep_id,
            "step_id": step_id,
            "depends_on_step_id": depends_on_step_id,
            "created_at": now,
        }
        log.info("dependency added: %s -> %s", step_id, depends_on_step_id)
        return result

    def remove_dependency(self, dependency_id: str) -> bool:
        """Remove a dependency edge."""
        with self._lock:
            row = self._conn.execute(
                "SELECT dependency_id FROM plan_dependencies WHERE dependency_id = ?",
                (dependency_id,),
            ).fetchone()
            if not row:
                return False

            self._conn.execute(
                "DELETE FROM plan_dependencies WHERE dependency_id = ?",
                (dependency_id,),
            )
            self._conn.commit()

        log.info("dependency removed: %s", dependency_id)
        return True

    def get_dependencies(self, step_id: str) -> list[dict]:
        """Get all dependencies for a step (what it depends on)."""
        with self._lock:
            rows = self._conn.execute("""
                SELECT d.* FROM plan_dependencies d
                WHERE d.step_id = ?
                ORDER BY d.created_at ASC
            """, (step_id,)).fetchall()
        return [self._parse_row(r) for r in rows]

    def _would_create_cycle(self, step_id: str, depends_on_step_id: str) -> bool:
        """Check if adding step_id -> depends_on_step_id would create a cycle.

        A cycle exists if depends_on_step_id can already reach step_id
        through the dependency graph.
        """
        visited = set()
        stack = [depends_on_step_id]
        while stack:
            current = stack.pop()
            if current == step_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            # Find what `current` depends on
            deps = self._conn.execute(
                "SELECT depends_on_step_id FROM plan_dependencies WHERE step_id = ?",
                (current,),
            ).fetchall()
            for d in deps:
                stack.append(d["depends_on_step_id"])
        return False

    # ------------------------------------------------------------------
    # Execution order (topological sort)
    # ------------------------------------------------------------------

    def get_execution_order(self, plan_id: str) -> list[dict]:
        """Return steps in topologically sorted order.

        Steps with no dependencies come first, then steps whose
        dependencies are all satisfied.  Within the same dependency
        level, steps are ordered by step_order.
        """
        with self._lock:
            steps = self._conn.execute(
                "SELECT * FROM plan_steps WHERE plan_id = ? ORDER BY step_order ASC",
                (plan_id,),
            ).fetchall()

            if not steps:
                return []

            step_map = {s["step_id"]: self._parse_row(s) for s in steps}

            # Build adjacency list: step -> set of steps it depends on
            deps_rows = self._conn.execute("""
                SELECT d.step_id, d.depends_on_step_id FROM plan_dependencies d
                INNER JOIN plan_steps s ON d.step_id = s.step_id
                WHERE s.plan_id = ?
            """, (plan_id,)).fetchall()

            # in_degree: how many dependencies each step has
            in_degree: dict[str, int] = {s["step_id"]: 0 for s in steps}
            # reverse adjacency: what steps depend on this step
            dependents: dict[str, list[str]] = {s["step_id"]: [] for s in steps}

            for d in deps_rows:
                in_degree[d["step_id"]] += 1
                dependents[d["depends_on_step_id"]].append(d["step_id"])

            # Kahn's algorithm
            queue: list[str] = sorted(
                [sid for sid, deg in in_degree.items() if deg == 0],
                key=lambda sid: step_map[sid].get("step_order", 0),
            )
            result: list[dict] = []

            while queue:
                # Pick the one with lowest step_order among zero in-degree
                queue.sort(key=lambda sid: step_map[sid].get("step_order", 0))
                current = queue.pop(0)
                result.append(step_map[current])

                for dep_step in dependents[current]:
                    in_degree[dep_step] -= 1
                    if in_degree[dep_step] == 0:
                        queue.append(dep_step)

            # If not all steps are in result, there is a cycle
            # (shouldn't happen due to add_dependency check, but handle gracefully)
            if len(result) < len(step_map):
                # Append remaining steps in order
                seen = {r["step_id"] for r in result}
                for sid in sorted(
                    step_map.keys() - seen,
                    key=lambda s: step_map[s].get("step_order", 0),
                ):
                    result.append(step_map[sid])

        return result

    # ------------------------------------------------------------------
    # Execution lifecycle
    # ------------------------------------------------------------------

    def start_plan(self, plan_id: str) -> dict:
        """Set plan status to running."""
        now = self._now()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM execution_plans WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Plan '{plan_id}' not found")

            plan = self._parse_row(row)
            if plan["status"] not in ("pending", "running"):
                raise ValueError(
                    f"Cannot start plan in status '{plan['status']}'"
                )

            self._conn.execute(
                "UPDATE execution_plans SET status = 'running', updated_at = ? "
                "WHERE plan_id = ?",
                (now, plan_id),
            )
            self._conn.commit()

        self._emit("plan.started", {
            "plan_id": plan_id,
        })
        log.info("plan started: %s", plan_id)
        return {"plan_id": plan_id, "status": "running", "updated_at": now}

    def complete_step(self, step_id: str, result: Any = None) -> dict:
        """Mark a step as completed."""
        now = self._now()
        result_json = (
            json.dumps(result, sort_keys=True, default=str)
            if result is not None else None
        )

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM plan_steps WHERE step_id = ?",
                (step_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Step '{step_id}' not found")

            step = self._parse_row(row)

            self._conn.execute(
                "UPDATE plan_steps SET status = 'completed', result = ?, "
                "updated_at = ? WHERE step_id = ?",
                (result_json, now, step_id),
            )

            # Check if all steps in the plan are completed
            plan_id = step["plan_id"]
            pending = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM plan_steps "
                "WHERE plan_id = ? AND status NOT IN ('completed', 'failed', 'skipped')",
                (plan_id,),
            ).fetchone()

            if pending["cnt"] == 0:
                # All steps done -- mark plan completed
                self._conn.execute(
                    "UPDATE execution_plans SET status = 'completed', "
                    "updated_at = ? WHERE plan_id = ?",
                    (now, plan_id),
                )
                plan_completed = True
            else:
                plan_completed = False

            self._conn.commit()

        self._emit("step.completed", {
            "step_id": step_id,
            "plan_id": plan_id,
        })
        log.info("step completed: %s", step_id)

        if plan_completed:
            self._emit("plan.completed", {
                "plan_id": plan_id,
            })
            log.info("plan completed: %s", plan_id)

        return {
            "step_id": step_id,
            "status": "completed",
            "plan_completed": plan_completed,
            "updated_at": now,
        }

    def fail_step(self, step_id: str, error: Any = None) -> dict:
        """Mark a step as failed."""
        now = self._now()
        error_json = (
            json.dumps(error, sort_keys=True, default=str)
            if error is not None else None
        )

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM plan_steps WHERE step_id = ?",
                (step_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Step '{step_id}' not found")

            step = self._parse_row(row)

            self._conn.execute(
                "UPDATE plan_steps SET status = 'failed', error = ?, "
                "updated_at = ? WHERE step_id = ?",
                (error_json, now, step_id),
            )

            plan_id = step["plan_id"]
            self._conn.commit()

        self._emit("step.failed", {
            "step_id": step_id,
            "plan_id": plan_id,
        })
        log.info("step failed: %s", step_id)

        return {
            "step_id": step_id,
            "status": "failed",
            "updated_at": now,
        }

    def get_plan_progress(self, plan_id: str) -> dict:
        """Get progress summary for a plan."""
        with self._lock:
            row = self._conn.execute(
                "SELECT plan_id FROM execution_plans WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Plan '{plan_id}' not found")

            counts = self._conn.execute("""
                SELECT status, COUNT(*) as cnt FROM plan_steps
                WHERE plan_id = ?
                GROUP BY status
            """, (plan_id,)).fetchall()

        total = sum(r["cnt"] for r in counts) if counts else 0
        by_status = {r["status"]: r["cnt"] for r in counts}

        return {
            "plan_id": plan_id,
            "total": total,
            "completed": by_status.get("completed", 0),
            "failed": by_status.get("failed", 0),
            "running": by_status.get("running", 0),
            "pending": by_status.get("pending", 0),
        }

    def cancel_plan(self, plan_id: str) -> dict:
        """Cancel a plan (sets plan and all pending/running steps to skipped/cancelled)."""
        now = self._now()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM execution_plans WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Plan '{plan_id}' not found")

            plan = self._parse_row(row)
            if plan["status"] not in ("pending", "running"):
                raise ValueError(
                    f"Cannot cancel plan in status '{plan['status']}'"
                )

            # Mark all pending/running steps as skipped
            self._conn.execute(
                "UPDATE plan_steps SET status = 'skipped', updated_at = ? "
                "WHERE plan_id = ? AND status IN ('pending', 'running')",
                (now, plan_id),
            )
            self._conn.execute(
                "UPDATE execution_plans SET status = 'cancelled', "
                "updated_at = ? WHERE plan_id = ?",
                (now, plan_id),
            )
            self._conn.commit()

        self._emit("plan.cancelled", {
            "plan_id": plan_id,
        })
        log.info("plan cancelled: %s", plan_id)

        return {"plan_id": plan_id, "status": "cancelled", "updated_at": now}


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_planner: ExecutionPlanner | None = None


def get_execution_planner(db_path: str | Path | None = None,
                          event_bus: EventBus | None = None) -> ExecutionPlanner:
    global _planner
    if _planner is None:
        _planner = ExecutionPlanner(db_path, event_bus)
    return _planner


def reset_execution_planner(db_path: str | Path | None = None,
                            event_bus: EventBus | None = None) -> ExecutionPlanner:
    global _planner
    _planner = ExecutionPlanner(db_path, event_bus)
    return _planner
