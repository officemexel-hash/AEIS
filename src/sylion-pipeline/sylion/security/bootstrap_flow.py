"""
SYLION Security -- Bootstrap Flow

Orchestrates startup / initialization sequences as ordered steps.
Each flow is a named sequence of steps; execution runs steps in order
and records per-step results in the database.

Tables:
  bootstrap_flows  -- registered flow definitions
  flow_steps       -- ordered steps within a flow
  flow_executions  -- execution records with per-step results

Singleton: get_bootstrap_flow() / reset_bootstrap_flow()
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

log = logging.getLogger("sylion.security.bootstrap_flow")


class BootstrapFlow:
    """Orchestrates startup / initialization sequences.

    Thread-safe.  SQLite-backed.  Emits events to EventBus.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
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
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS bootstrap_flows (
                flow_id     TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status      TEXT NOT NULL DEFAULT 'active',
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS flow_steps (
                step_id    TEXT PRIMARY KEY,
                flow_id    TEXT NOT NULL,
                step_name  TEXT NOT NULL,
                step_type  TEXT NOT NULL DEFAULT 'action',
                step_order INTEGER NOT NULL DEFAULT 0,
                config_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS flow_executions (
                execution_id  TEXT PRIMARY KEY,
                flow_id       TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'pending',
                step_results  TEXT NOT NULL DEFAULT '[]',
                context_json  TEXT NOT NULL DEFAULT '{}',
                started_at    REAL,
                completed_at  REAL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_flows_status "
            "ON bootstrap_flows(status)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_steps_flow "
            "ON flow_steps(flow_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_exec_flow "
            "ON flow_executions(flow_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_exec_status "
            "ON flow_executions(status)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="security.bootstrap_flow",
            ))

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _parse_json(raw: str | None, default: Any = None) -> Any:
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    # ------------------------------------------------------------------
    # Flow CRUD
    # ------------------------------------------------------------------

    def create_flow(self, name: str, description: str = "",
                    steps_list: list[dict] | None = None) -> dict:
        """Create a new bootstrap flow with optional initial steps."""
        flow_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO bootstrap_flows
                    (flow_id, name, description, status,
                     created_at, updated_at)
                VALUES (?, ?, ?, 'active', ?, ?)
            """, (flow_id, name, description, now, now))

            if steps_list:
                for idx, step in enumerate(steps_list):
                    self._conn.execute("""
                        INSERT INTO flow_steps
                            (step_id, flow_id, step_name, step_type,
                             step_order, config_json, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        self._uid(), flow_id,
                        step.get("step_name", f"step_{idx}"),
                        step.get("step_type", "action"),
                        step.get("step_order", idx),
                        json.dumps(step.get("config_json", {}), default=str),
                        now,
                    ))
            self._conn.commit()

        self._emit("flow_created", {
            "flow_id": flow_id, "name": name,
        })
        log.info("created flow %s (%s)", flow_id, name)
        return {"flow_id": flow_id, "name": name,
                "description": description, "status": "active"}

    def update_flow(self, flow_id: str, **fields) -> dict | None:
        """Update mutable flow fields (name, description, status)."""
        allowed = {"name", "description", "status"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return None

        updates["updated_at"] = time.time()
        sets = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [flow_id]

        with self._lock:
            n = self._conn.execute(
                f"UPDATE bootstrap_flows SET {sets} WHERE flow_id = ?",
                vals,
            ).rowcount
            self._conn.commit()
            if not n:
                return None
            row = self._conn.execute(
                "SELECT * FROM bootstrap_flows WHERE flow_id = ?",
                (flow_id,),
            ).fetchone()

        return dict(row)

    def delete_flow(self, flow_id: str) -> bool:
        """Delete a flow and all associated steps/executions."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM bootstrap_flows WHERE flow_id = ?",
                (flow_id,),
            ).rowcount
            if n:
                self._conn.execute(
                    "DELETE FROM flow_steps WHERE flow_id = ?",
                    (flow_id,),
                )
                self._conn.execute(
                    "DELETE FROM flow_executions WHERE flow_id = ?",
                    (flow_id,),
                )
            self._conn.commit()
        return bool(n)

    def get_flow(self, flow_id: str) -> dict | None:
        """Get a flow with its steps."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM bootstrap_flows WHERE flow_id = ?",
                (flow_id,),
            ).fetchone()
            if not row:
                return None
            steps = self._conn.execute(
                "SELECT * FROM flow_steps WHERE flow_id = ? "
                "ORDER BY step_order",
                (flow_id,),
            ).fetchall()

        result = dict(row)
        result["steps"] = [dict(s) for s in steps]
        for s in result["steps"]:
            s["config_json"] = self._parse_json(s.get("config_json"), {})
        return result

    def list_flows(self, status: str | None = None) -> list[dict]:
        """List flows, optionally filtered by status."""
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM bootstrap_flows WHERE status = ? "
                    "ORDER BY name",
                    (status,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM bootstrap_flows ORDER BY name"
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Step management
    # ------------------------------------------------------------------

    def add_step(self, flow_id: str, step_name: str,
                 step_type: str = "action",
                 config_json: dict | None = None) -> dict:
        """Add a step to a flow (appended at end)."""
        step_id = self._uid()
        now = time.time()

        with self._lock:
            max_order = self._conn.execute(
                "SELECT COALESCE(MAX(step_order), -1) as mo "
                "FROM flow_steps WHERE flow_id = ?",
                (flow_id,),
            ).fetchone()["mo"]

            self._conn.execute("""
                INSERT INTO flow_steps
                    (step_id, flow_id, step_name, step_type,
                     step_order, config_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (step_id, flow_id, step_name, step_type,
                  max_order + 1,
                  json.dumps(config_json or {}, default=str), now))
            self._conn.execute(
                "UPDATE bootstrap_flows SET updated_at = ? "
                "WHERE flow_id = ?",
                (now, flow_id),
            )
            self._conn.commit()

        return {"step_id": step_id, "flow_id": flow_id,
                "step_name": step_name, "step_type": step_type}

    def remove_step(self, step_id: str) -> bool:
        """Remove a step from a flow."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM flow_steps WHERE step_id = ?",
                (step_id,),
            ).rowcount
            self._conn.commit()
        return bool(n)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute_flow(self, flow_id: str,
                     context_json: dict | None = None) -> dict:
        """Execute a flow by running all steps in order.

        Each step is executed sequentially.  Step results are recorded.
        If any step fails, the flow is marked as failed and execution
        stops.

        Returns the execution record.
        """
        execution_id = self._uid()
        now = time.time()

        with self._lock:
            flow_row = self._conn.execute(
                "SELECT * FROM bootstrap_flows WHERE flow_id = ?",
                (flow_id,),
            ).fetchone()
            if not flow_row:
                return {"execution_id": execution_id,
                        "status": "error", "error": "flow not found"}

            steps = self._conn.execute(
                "SELECT * FROM flow_steps WHERE flow_id = ? "
                "ORDER BY step_order",
                (flow_id,),
            ).fetchall()

            # Create execution record
            self._conn.execute("""
                INSERT INTO flow_executions
                    (execution_id, flow_id, status, step_results,
                     context_json, started_at, completed_at)
                VALUES (?, ?, 'running', '[]', ?, ?, NULL)
            """, (execution_id, flow_id,
                  json.dumps(context_json or {}, default=str), now))
            self._conn.commit()

        self._emit("flow_started", {
            "execution_id": execution_id, "flow_id": flow_id,
        })

        step_results: list[dict] = []
        flow_status = "completed"

        for step in steps:
            step_result = {
                "step_id": step["step_id"],
                "step_name": step["step_name"],
                "step_type": step["step_type"],
                "status": "completed",
            }

            try:
                config = self._parse_json(step["config_json"], {})
                step_result["config"] = config
                # Simulate step execution based on step_type
                if step["step_type"] == "validate":
                    step_result["result"] = "validated"
                elif step["step_type"] == "transform":
                    step_result["result"] = "transformed"
                else:
                    step_result["result"] = "executed"
            except Exception as exc:
                step_result["status"] = "failed"
                step_result["error"] = str(exc)
                flow_status = "failed"

            self._emit("step_completed", {
                "execution_id": execution_id,
                "step_id": step["step_id"],
                "step_name": step["step_name"],
                "step_status": step_result["status"],
            })

            step_results.append(step_result)

            if flow_status == "failed":
                break

        completed_at = time.time()
        with self._lock:
            self._conn.execute("""
                UPDATE flow_executions
                SET status = ?, step_results = ?, completed_at = ?
                WHERE execution_id = ?
            """, (flow_status, json.dumps(step_results, default=str),
                  completed_at, execution_id))
            self._conn.commit()

        event_topic = "flow_completed" if flow_status == "completed" \
            else "flow_failed"
        self._emit(event_topic, {
            "execution_id": execution_id,
            "flow_id": flow_id,
            "status": flow_status,
        })

        return {
            "execution_id": execution_id,
            "flow_id": flow_id,
            "status": flow_status,
            "step_results": step_results,
        }

    def get_execution(self, execution_id: str) -> dict | None:
        """Get an execution record by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM flow_executions WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["step_results"] = self._parse_json(
            result.get("step_results"), [])
        result["context_json"] = self._parse_json(
            result.get("context_json"), {})
        return result

    def list_executions(self, flow_id: str | None = None,
                        status: str | None = None) -> list[dict]:
        """List executions, optionally filtered by flow and/or status."""
        with self._lock:
            q = "SELECT * FROM flow_executions WHERE 1=1"
            params: list[Any] = []
            if flow_id:
                q += " AND flow_id = ?"
                params.append(flow_id)
            if status:
                q += " AND status = ?"
                params.append(status)
            q += " ORDER BY started_at DESC"
            rows = self._conn.execute(q, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["step_results"] = self._parse_json(d.get("step_results"), [])
            d["context_json"] = self._parse_json(d.get("context_json"), {})
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_flow_stats(self) -> dict[str, Any]:
        """Aggregate flow statistics."""
        with self._lock:
            total_flows = self._conn.execute(
                "SELECT COUNT(*) as c FROM bootstrap_flows"
            ).fetchone()["c"]

            total_executions = self._conn.execute(
                "SELECT COUNT(*) as c FROM flow_executions"
            ).fetchone()["c"]

            by_status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as c FROM flow_executions "
                "GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["c"] for r in by_status_rows}

            total_steps = self._conn.execute(
                "SELECT COUNT(*) as c FROM flow_steps"
            ).fetchone()["c"]

        return {
            "total_flows": total_flows,
            "total_steps": total_steps,
            "total_executions": total_executions,
            "by_status": by_status,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_flow: BootstrapFlow | None = None


def get_bootstrap_flow(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> BootstrapFlow:
    global _flow
    if _flow is None:
        _flow = BootstrapFlow(db_path, event_bus)
    return _flow


def reset_bootstrap_flow(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> BootstrapFlow:
    global _flow
    _flow = BootstrapFlow(db_path, event_bus)
    return _flow
