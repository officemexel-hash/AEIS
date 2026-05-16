"""
SYLION Execution — Tool Runner

Tool execution engine. Registers tools, records executions,
and dispatches configured handlers for pipeline integration.

Phase 1: SQLite-backed execution ledger with local dispatch.
Phase 2: gRPC tool invocation (same interface, config swap).
"""

from __future__ import annotations

import importlib
import json
import logging
import sqlite3
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.execution.tool_runner")


@dataclass
class Tool:
    """Registered tool descriptor."""
    tool_id: str = ""
    name: str = ""
    description: str = ""
    tool_type: str = "python"
    config: dict[str, Any] = field(default_factory=dict)
    active: int = 1


@dataclass
class ToolExecution:
    """A single tool execution record."""
    exec_id: str = ""
    tool_id: str = ""
    input_hash: str = ""
    result: str = ""
    status: str = "pending"
    started_at: float = 0.0
    completed_at: float = 0.0
    error: str = ""


class ToolRunner:
    """Tool registration and execution engine.

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
            CREATE TABLE IF NOT EXISTS tools (
                tool_id      TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                description  TEXT NOT NULL DEFAULT '',
                tool_type    TEXT NOT NULL DEFAULT 'python',
                config       TEXT NOT NULL DEFAULT '{}',
                active       INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tool_executions (
                exec_id      TEXT PRIMARY KEY,
                tool_id      TEXT NOT NULL,
                input_hash   TEXT NOT NULL DEFAULT '',
                result       TEXT NOT NULL DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'pending',
                started_at   REAL NOT NULL,
                completed_at REAL NOT NULL DEFAULT 0,
                error        TEXT NOT NULL DEFAULT ''
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_texec_tool ON tool_executions(tool_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_texec_status ON tool_executions(status)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_tool(self, tool_id: str, name: str, description: str = "",
                      tool_type: str = "python",
                      config: dict[str, Any] | None = None) -> dict:
        """Register a new tool. Returns tool descriptor dict."""
        if config is None:
            config = {}

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO tools
                (tool_id, name, description, tool_type, config, active)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (tool_id, name, description, tool_type,
                  json.dumps(config, default=str)))
            self._conn.commit()

        self._emit("execution.tool.registered", {
            "tool_id": tool_id, "name": name, "tool_type": tool_type,
        })

        log.info("registered tool %s (%s)", tool_id, name)
        return {"tool_id": tool_id, "name": name}

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, tool_id: str, input_data: dict | None = None) -> dict:
        """Execute a registered tool and persist the execution result."""
        if input_data is None:
            input_data = {}

        exec_id = uuid.uuid4().hex
        input_hash = str(hash(json.dumps(input_data, sort_keys=True, default=str)))
        started_at = time.time()

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tools WHERE tool_id = ? AND active = 1",
                (tool_id,),
            ).fetchone()
        if not row:
            log.warning("tool not found or inactive: %s", tool_id)
            return {"result": "error", "tool_id": tool_id, "error": "tool not found or inactive"}

        status = "completed"
        error = ""
        try:
            output = self._dispatch_tool(dict(row), input_data)
            result = json.dumps(output, default=str)
        except Exception as exc:  # noqa: BLE001 - execution errors are recorded, not hidden
            status = "failed"
            error = str(exc)
            result = json.dumps({"result": "error", "tool_id": tool_id, "error": error}, default=str)
            log.exception("tool execution failed: %s", tool_id)
        completed_at = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO tool_executions
                (exec_id, tool_id, input_hash, result, status, started_at, completed_at, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (exec_id, tool_id, input_hash, result, status, started_at, completed_at, error))
            self._conn.commit()

        self._emit("execution.tool.executed", {
            "exec_id": exec_id, "tool_id": tool_id, "status": status,
        })

        log.info("executed tool %s (exec_id=%s)", tool_id, exec_id[:12])
        if status != "completed":
            return {"result": "error", "tool_id": tool_id, "exec_id": exec_id, "error": error}
        return {"result": "executed", "tool_id": tool_id, "exec_id": exec_id}

    def _dispatch_tool(self, row: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        tool_id = str(row.get("tool_id") or "")
        tool_type = str(row.get("tool_type") or "python").lower()
        config = json.loads(row.get("config") or "{}")

        callable_path = config.get("callable") or config.get("handler")
        if callable_path:
            module_name, _, attr = str(callable_path).partition(":")
            if not module_name or not attr:
                raise ValueError("tool callable must use module:function syntax")
            fn = getattr(importlib.import_module(module_name), attr)
            value = fn(input_data)
            return {"result": "executed", "tool_id": tool_id, "handler": callable_path, "output": value}

        command = config.get("command")
        if tool_type == "shell" and command:
            if isinstance(command, str):
                raise ValueError("shell tool command must be an argv list; string commands are disabled")
            if (
                not isinstance(command, list)
                or not command
                or not all(isinstance(part, str) and part for part in command)
            ):
                raise ValueError("shell tool command must be a non-empty argv list of strings")
            timeout = float(config.get("timeout_sec") or 30)
            completed = subprocess.run(
                list(command),
                input=json.dumps(input_data, default=str),
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or f"shell tool exited with {completed.returncode}")
            return {
                "result": "executed",
                "tool_id": tool_id,
                "handler": "shell",
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }

        return {
            "result": "executed",
            "tool_id": tool_id,
            "handler": "registered_tool_metadata",
            "input_keys": sorted(input_data.keys()),
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_tool(self, tool_id: str) -> dict | None:
        """Get a single tool by ID."""
        row = self._conn.execute(
            "SELECT * FROM tools WHERE tool_id = ?", (tool_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["config"] = json.loads(result.get("config", "{}"))
        return result

    def get_execution(self, exec_id: str) -> dict | None:
        """Get a single execution record by ID."""
        row = self._conn.execute(
            "SELECT * FROM tool_executions WHERE exec_id = ?", (exec_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_tools(self, active_only: bool = True) -> list[dict]:
        """List all registered tools."""
        if active_only:
            rows = self._conn.execute(
                "SELECT * FROM tools WHERE active = 1 ORDER BY name"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tools ORDER BY name"
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["config"] = json.loads(d.get("config", "{}"))
            results.append(d)
        return results

    def list_executions(self, tool_id: str | None = None,
                        limit: int = 100) -> list[dict]:
        """List execution records, optionally filtered by tool."""
        if tool_id:
            rows = self._conn.execute(
                "SELECT * FROM tool_executions WHERE tool_id = ? ORDER BY started_at DESC LIMIT ?",
                (tool_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tool_executions ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="execution.tool_runner",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_runner: ToolRunner | None = None


def get_tool_runner(db_path: str | Path | None = None,
                    event_bus: EventBus | None = None) -> ToolRunner:
    global _runner
    if _runner is None:
        _runner = ToolRunner(db_path, event_bus)
    return _runner
