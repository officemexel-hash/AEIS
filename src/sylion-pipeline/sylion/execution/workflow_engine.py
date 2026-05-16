"""
SYLION Execution — Workflow Engine

Workflow orchestration for multi-step pipelines.
Manages workflow definitions and sequential step execution.

Phase 1: SQLite-backed run ledger with deterministic local step handlers.
Phase 2: DAG-based execution with parallel branches.
"""

from __future__ import annotations

import importlib
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

log = logging.getLogger("sylion.execution.workflow_engine")


@dataclass
class WorkflowStep:
    """A single step within a workflow."""
    name: str = ""
    tool: str = ""
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    """A workflow definition."""
    workflow_id: str = ""
    name: str = ""
    description: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    status: str = "draft"
    created_at: float = 0.0
    completed_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class WorkflowRun:
    """A single execution run of a workflow."""
    run_id: str = ""
    workflow_id: str = ""
    status: str = "pending"
    current_step: int = 0
    step_results: list[dict[str, Any]] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: float = 0.0


class WorkflowEngine:
    """Workflow orchestration for multi-step pipelines.

    Thread-safe. SQLite-backed. Emits events to EventBus.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                workflow_id  TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                description  TEXT NOT NULL DEFAULT '',
                steps        TEXT NOT NULL DEFAULT '[]',
                status       TEXT NOT NULL DEFAULT 'draft',
                created_at   REAL NOT NULL,
                completed_at REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS workflow_runs (
                run_id       TEXT PRIMARY KEY,
                workflow_id  TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'pending',
                current_step INTEGER NOT NULL DEFAULT 0,
                step_results TEXT NOT NULL DEFAULT '[]',
                started_at   REAL NOT NULL,
                completed_at REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_wf_status ON workflows(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_wfr_wf ON workflow_runs(workflow_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_wfr_status ON workflow_runs(status)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Workflow CRUD
    # ------------------------------------------------------------------

    def create_workflow(self, name: str, description: str = "",
                        steps: list[dict[str, Any]] | None = None) -> dict:
        """Create a new workflow definition."""
        if steps is None:
            steps = []

        workflow_id = uuid.uuid4().hex
        created_at = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO workflows
                (workflow_id, name, description, steps, status, created_at, completed_at)
                VALUES (?, ?, ?, ?, 'draft', ?, 0)
            """, (workflow_id, name, description,
                  json.dumps(steps, default=str), created_at))
            self._conn.commit()

        self._emit("execution.workflow.created", {
            "workflow_id": workflow_id, "name": name, "step_count": len(steps),
        })

        log.info("created workflow %s (%s, %d steps)",
                 workflow_id[:12], name, len(steps))
        return {"workflow_id": workflow_id, "name": name, "status": "draft"}

    def get_workflow(self, workflow_id: str) -> dict | None:
        """Get a workflow definition by ID."""
        row = self._conn.execute(
            "SELECT * FROM workflows WHERE workflow_id = ?",
            (workflow_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["steps"] = json.loads(result.get("steps", "[]"))
        return result

    def list_workflows(self, status: str | None = None) -> list[dict]:
        """List workflows, optionally filtered by status."""
        if status:
            rows = self._conn.execute(
                "SELECT * FROM workflows WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM workflows ORDER BY created_at DESC"
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["steps"] = json.loads(d.get("steps", "[]"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Workflow execution
    # ------------------------------------------------------------------

    def run_workflow(self, workflow_id: str) -> dict:
        """Execute a workflow with sequential local step dispatch."""
        wf = self.get_workflow(workflow_id)
        if not wf:
            return {"error": "workflow not found", "workflow_id": workflow_id}

        run_id = uuid.uuid4().hex
        started_at = time.time()
        steps = wf["steps"]
        step_results: list[dict[str, Any]] = []

        with self._lock:
            self._conn.execute(
                "UPDATE workflows SET status = 'running' WHERE workflow_id = ?",
                (workflow_id,),
            )
            self._conn.execute("""
                INSERT INTO workflow_runs
                (run_id, workflow_id, status, current_step, step_results,
                 started_at, completed_at)
                VALUES (?, ?, 'running', 0, '[]', ?, 0)
            """, (run_id, workflow_id, started_at))
            self._conn.commit()

        status = "completed"
        for i, step in enumerate(steps):
            try:
                step_result = self._execute_step(i, step)
            except Exception as exc:  # noqa: BLE001 - step failure is runtime evidence
                status = "failed"
                step_result = {
                    "step": i,
                    "name": step.get("name", f"step_{i}"),
                    "tool": step.get("tool", ""),
                    "status": "failed",
                    "error": str(exc),
                }
            step_results.append(step_result)

            with self._lock:
                self._conn.execute("""
                    UPDATE workflow_runs SET current_step = ?, step_results = ?
                    WHERE run_id = ?
                """, (i, json.dumps(step_results, default=str), run_id))
                self._conn.commit()
            if status == "failed":
                break

        completed_at = time.time()

        with self._lock:
            self._conn.execute("""
                UPDATE workflow_runs
                SET status = ?, current_step = ?, step_results = ?, completed_at = ?
                WHERE run_id = ?
            """, (status, len(step_results) - 1 if step_results else 0,
                  json.dumps(step_results, default=str),
                  completed_at, run_id))
            self._conn.execute(
                "UPDATE workflows SET status = ?, completed_at = ? WHERE workflow_id = ?",
                (status, completed_at, workflow_id),
            )
            self._conn.commit()

        self._emit(f"execution.workflow.{status}", {
            "run_id": run_id, "workflow_id": workflow_id,
            "steps_executed": len(step_results),
        })

        log.info("%s workflow %s (run_id=%s, %d steps)",
                 status, workflow_id[:12], run_id[:12], len(step_results))
        return {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "status": status,
            "steps_executed": len(step_results),
        }

    def _execute_step(self, index: int, step: dict[str, Any]) -> dict[str, Any]:
        name = step.get("name", f"step_{index}")
        tool = step.get("tool", "")
        callable_path = step.get("callable") or step.get("handler")
        if callable_path:
            module_name, _, attr = str(callable_path).partition(":")
            if not module_name or not attr:
                raise ValueError("workflow step callable must use module:function syntax")
            fn = getattr(importlib.import_module(module_name), attr)
            output = fn(step.get("input", {}))
            handler = callable_path
        else:
            handler = "workflow_step_metadata"
            output = {
                "result": "executed",
                "input_keys": sorted((step.get("input") or {}).keys()),
            }
        return {
            "step": index,
            "name": name,
            "tool": tool,
            "status": "completed",
            "handler": handler,
            "output": output,
        }

    # ------------------------------------------------------------------
    # Run queries
    # ------------------------------------------------------------------

    def get_run(self, run_id: str) -> dict | None:
        """Get a workflow run by ID."""
        row = self._conn.execute(
            "SELECT * FROM workflow_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["step_results"] = json.loads(result.get("step_results", "[]"))
        return result

    def list_runs(self, workflow_id: str | None = None,
                  limit: int = 100) -> list[dict]:
        """List workflow runs, optionally filtered by workflow."""
        if workflow_id:
            rows = self._conn.execute(
                "SELECT * FROM workflow_runs WHERE workflow_id = ? ORDER BY started_at DESC LIMIT ?",
                (workflow_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM workflow_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["step_results"] = json.loads(d.get("step_results", "[]"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="execution.workflow_engine",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: WorkflowEngine | None = None


def get_workflow_engine(db_path: str | Path | None = None,
                        event_bus: EventBus | None = None) -> WorkflowEngine:
    global _engine
    if _engine is None:
        _engine = WorkflowEngine(db_path, event_bus)
    return _engine
