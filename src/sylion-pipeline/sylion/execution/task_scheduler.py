"""
SYLION Execution -- Task Scheduler

Manages scheduled task execution with dependency tracking.
SQLite-backed, thread-safe.

Tables:
  - scheduled_tasks: task definitions with cron expressions
  - task_executions: execution history records
  - task_dependencies: dependency graph between tasks
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

log = logging.getLogger("sylion.execution.task_scheduler")


class TaskScheduler:
    """Manages scheduled task execution and dependencies.
    SQLite-backed, thread-safe."""

    def __init__(self, db_path: str | Path | None = None, event_bus: Any = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                task_id     TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                task_type   TEXT NOT NULL,
                cron_expr   TEXT NOT NULL,
                config_json TEXT NOT NULL DEFAULT '{}',
                status      TEXT NOT NULL DEFAULT 'active',
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS task_executions (
                execution_id TEXT PRIMARY KEY,
                task_id      TEXT NOT NULL,
                status       TEXT NOT NULL,
                result_json  TEXT,
                duration_ms  INTEGER,
                created_at   REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS task_dependencies (
                dependency_id       TEXT PRIMARY KEY,
                task_id             TEXT NOT NULL,
                depends_on_task_id  TEXT NOT NULL,
                created_at          REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_st_status
                ON scheduled_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_st_type
                ON scheduled_tasks(task_type);
            CREATE INDEX IF NOT EXISTS idx_te_task
                ON task_executions(task_id);
            CREATE INDEX IF NOT EXISTS idx_te_status
                ON task_executions(status);
            CREATE INDEX IF NOT EXISTS idx_td_task
                ON task_dependencies(task_id);
            CREATE INDEX IF NOT EXISTS idx_td_dep
                ON task_dependencies(depends_on_task_id);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Task CRUD
    # ------------------------------------------------------------------

    def schedule_task(self, name: str, task_type: str, cron_expr: str,
                      config_json: str = "{}") -> dict:
        task_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO scheduled_tasks
                    (task_id, name, task_type, cron_expr, config_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            """, (task_id, name, task_type, cron_expr, config_json, now, now))
            self._conn.commit()

        self._emit("execution.task_scheduled", {
            "task_id": task_id, "name": name, "task_type": task_type,
        })
        log.info("scheduled task %s (%s / %s) cron=%s",
                 task_id[:12], name, task_type, cron_expr)
        return {
            "task_id": task_id,
            "name": name,
            "task_type": task_type,
            "cron_expr": cron_expr,
            "config_json": config_json,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }

    def update_task(self, task_id: str, **kwargs: Any) -> dict | None:
        allowed = {"name", "task_type", "cron_expr", "config_json", "status"}
        updates: dict[str, Any] = {}
        for k, v in kwargs.items():
            if k not in allowed:
                raise ValueError(f"unknown field: {k}")
            updates[k] = v

        if not updates:
            return self.get_task(task_id)

        updates["updated_at"] = time.time()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [task_id]

        with self._lock:
            n = self._conn.execute(
                f"UPDATE scheduled_tasks SET {set_clause} WHERE task_id = ?",
                values,
            ).rowcount
            self._conn.commit()

        if not n:
            return None

        self._emit("execution.task_updated", {
            "task_id": task_id, "fields": list(kwargs.keys()),
        })
        return self.get_task(task_id)

    def cancel_task(self, task_id: str) -> dict | None:
        with self._lock:
            n = self._conn.execute(
                "UPDATE scheduled_tasks SET status = 'cancelled', updated_at = ? "
                "WHERE task_id = ?",
                (time.time(), task_id),
            ).rowcount
            self._conn.commit()
        if not n:
            return None
        return {"task_id": task_id, "status": "cancelled"}

    def get_task(self, task_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM scheduled_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_tasks(self, status: str | None = None,
                   task_type: str | None = None) -> list[dict]:
        conds: list[str] = []
        params: list[Any] = []
        if status:
            conds.append("status = ?")
            params.append(status)
        if task_type:
            conds.append("task_type = ?")
            params.append(task_type)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM scheduled_tasks{where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Executions
    # ------------------------------------------------------------------

    def record_execution(self, task_id: str, status: str,
                         result_json: str | None = None,
                         duration_ms: int | None = None) -> dict:
        execution_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO task_executions
                    (execution_id, task_id, status, result_json, duration_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (execution_id, task_id, status, result_json, duration_ms, now))
            self._conn.commit()

        event_topic = (
            "execution.task_failed" if status == "failed"
            else "execution.task_executed"
        )
        self._emit(event_topic, {
            "execution_id": execution_id,
            "task_id": task_id,
            "status": status,
            "duration_ms": duration_ms,
        })
        log.info("execution %s for task %s: %s (%dms)",
                 execution_id[:12], task_id[:12], status, duration_ms or 0)
        return {
            "execution_id": execution_id,
            "task_id": task_id,
            "status": status,
            "result_json": result_json,
            "duration_ms": duration_ms,
            "created_at": now,
        }

    def get_executions(self, task_id: str | None = None,
                       limit: int = 100) -> list[dict]:
        with self._lock:
            if task_id:
                rows = self._conn.execute(
                    "SELECT * FROM task_executions WHERE task_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (task_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM task_executions ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def add_dependency(self, task_id: str, depends_on_task_id: str) -> dict:
        dependency_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO task_dependencies
                    (dependency_id, task_id, depends_on_task_id, created_at)
                VALUES (?, ?, ?, ?)
            """, (dependency_id, task_id, depends_on_task_id, now))
            self._conn.commit()

        self._emit("execution.dependency_added", {
            "dependency_id": dependency_id,
            "task_id": task_id,
            "depends_on_task_id": depends_on_task_id,
        })
        log.info("dependency: %s depends on %s", task_id[:12], depends_on_task_id[:12])
        return {
            "dependency_id": dependency_id,
            "task_id": task_id,
            "depends_on_task_id": depends_on_task_id,
            "created_at": now,
        }

    def remove_dependency(self, dependency_id: str) -> dict | None:
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM task_dependencies WHERE dependency_id = ?",
                (dependency_id,),
            ).rowcount
            self._conn.commit()
        if not n:
            return None
        return {"dependency_id": dependency_id, "removed": True}

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_task_stats(self) -> dict:
        with self._lock:
            total_tasks = self._conn.execute(
                "SELECT COUNT(*) as c FROM scheduled_tasks"
            ).fetchone()["c"]
            active_tasks = self._conn.execute(
                "SELECT COUNT(*) as c FROM scheduled_tasks WHERE status = 'active'"
            ).fetchone()["c"]
            total_executions = self._conn.execute(
                "SELECT COUNT(*) as c FROM task_executions"
            ).fetchone()["c"]
            failed_executions = self._conn.execute(
                "SELECT COUNT(*) as c FROM task_executions WHERE status = 'failed'"
            ).fetchone()["c"]
            total_deps = self._conn.execute(
                "SELECT COUNT(*) as c FROM task_dependencies"
            ).fetchone()["c"]

            # By task type
            type_rows = self._conn.execute(
                "SELECT task_type, COUNT(*) as c FROM scheduled_tasks GROUP BY task_type"
            ).fetchall()
            by_task_type = {r["task_type"]: r["c"] for r in type_rows}

        fail_rate = round(failed_executions / total_executions * 100, 2) if total_executions else 0.0
        return {
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "total_executions": total_executions,
            "failed_executions": failed_executions,
            "failure_rate": fail_rate,
            "total_dependencies": total_deps,
            "by_task_type": by_task_type,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="execution.task_scheduler",
            ))

    def close(self):
        self._conn.close()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_scheduler: TaskScheduler | None = None


def get_task_scheduler(db_path: str | Path | None = None,
                       event_bus: Any = None) -> TaskScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler(db_path=db_path, event_bus=event_bus)
    return _scheduler


def reset_task_scheduler() -> None:
    global _scheduler
    _scheduler = None
