"""
SYLION Cognitive -- Agent Runtime Manager

Manages AI agent runtimes: register agents (Claude Code, Codex, custom),
configure their model, system prompt, tools, and execute tasks through them.
Records executions with token counts, cost, and latency for tracking and audit.

Tables:
  registered_agents, agent_executions, agent_logs

Singleton: get_agent_runtime() / reset_agent_runtime()
Events: agent.registered, agent.deregistered,
        agent.execution.started, agent.execution.completed,
        agent.execution.failed

Thread-safe. SQLite-backed. Emits events via EventBus.
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

log = logging.getLogger("sylion.cognitive.agent_runtime")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_STATUSES = ("active", "inactive", "error")
EXECUTION_STATUSES = ("pending", "running", "completed", "failed", "cancelled")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


# ---------------------------------------------------------------------------
# AgentRuntimeManager
# ---------------------------------------------------------------------------

class AgentRuntimeManager:
    """AI agent runtime manager.

    Thread-safe. SQLite-backed. Emits events to EventBus.
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

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS registered_agents (
                agent_id      TEXT PRIMARY KEY,
                name          TEXT NOT NULL DEFAULT '',
                description   TEXT NOT NULL DEFAULT '',
                agent_type    TEXT NOT NULL DEFAULT 'custom',
                provider      TEXT NOT NULL DEFAULT '',
                model_id      TEXT NOT NULL DEFAULT '',
                system_prompt TEXT NOT NULL DEFAULT '',
                tools         TEXT NOT NULL DEFAULT '[]',
                capabilities  TEXT NOT NULL DEFAULT '[]',
                max_tokens    INTEGER NOT NULL DEFAULT 4096,
                temperature   REAL NOT NULL DEFAULT 0.7,
                status        TEXT NOT NULL DEFAULT 'active',
                config        TEXT NOT NULL DEFAULT '{}',
                created_at    REAL NOT NULL,
                updated_at    REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_executions (
                execution_id    TEXT PRIMARY KEY,
                agent_id        TEXT NOT NULL DEFAULT '',
                task_description TEXT NOT NULL DEFAULT '',
                input_messages  TEXT NOT NULL DEFAULT '[]',
                output_text     TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'pending',
                tokens_used     INTEGER NOT NULL DEFAULT 0,
                cost            REAL NOT NULL DEFAULT 0.0,
                latency_ms      INTEGER NOT NULL DEFAULT 0,
                error_message   TEXT NOT NULL DEFAULT '',
                started_at      REAL,
                completed_at    REAL
            );
            CREATE TABLE IF NOT EXISTS agent_logs (
                log_id       TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL DEFAULT '',
                agent_id     TEXT NOT NULL DEFAULT '',
                level        TEXT NOT NULL DEFAULT 'INFO',
                message      TEXT NOT NULL DEFAULT '',
                timestamp    REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_agents_status
                ON registered_agents(status);
            CREATE INDEX IF NOT EXISTS idx_agents_type
                ON registered_agents(agent_type);
            CREATE INDEX IF NOT EXISTS idx_exec_agent
                ON agent_executions(agent_id);
            CREATE INDEX IF NOT EXISTS idx_exec_status
                ON agent_executions(status);
            CREATE INDEX IF NOT EXISTS idx_logs_exec
                ON agent_logs(execution_id);
            CREATE INDEX IF NOT EXISTS idx_logs_agent
                ON agent_logs(agent_id);
        """)
        self._conn.commit()

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cognitive.agent_runtime",
            ))

    # ------------------------------------------------------------------
    # Row parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_row(row: sqlite3.Row) -> dict:
        """Convert a Row to dict, parsing known JSON fields."""
        d = dict(row)
        for key in ("tools", "capabilities", "config", "input_messages"):
            val = d.get(key)
            if isinstance(val, str):
                try:
                    d[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def register_agent(self, name: str, agent_type: str = "custom",
                       provider: str = "", model_id: str = "",
                       system_prompt: str = "",
                       tools: list[str] | None = None,
                       capabilities: list[str] | None = None,
                       max_tokens: int = 4096,
                       temperature: float = 0.7,
                       config: dict | None = None) -> dict:
        """Register a new agent. Returns the agent descriptor dict."""
        agent_id = self._uid()
        now = time.time()
        tools_json = json.dumps(tools or [])
        caps_json = json.dumps(capabilities or [])
        config_json = json.dumps(config or {})

        with self._lock:
            self._conn.execute("""
                INSERT INTO registered_agents
                    (agent_id, name, description, agent_type, provider,
                     model_id, system_prompt, tools, capabilities,
                     max_tokens, temperature, status, config,
                     created_at, updated_at)
                VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """, (
                agent_id, name, agent_type, provider, model_id,
                system_prompt, tools_json, caps_json,
                max_tokens, temperature, config_json,
                now, now,
            ))
            self._conn.commit()

        self._emit("agent.registered", {
            "agent_id": agent_id, "name": name, "agent_type": agent_type,
        })
        log.info("register_agent %s: %s (%s)", agent_id[:12], name, agent_type)
        return self.get_agent(agent_id)

    def update_agent(self, agent_id: str, **fields) -> dict | None:
        """Update fields on an existing agent. Returns updated dict or None."""
        allowed = {
            "name", "description", "agent_type", "provider", "model_id",
            "system_prompt", "tools", "capabilities", "max_tokens",
            "temperature", "status", "config",
        }
        sets: list[str] = []
        params: list[Any] = []

        for key, value in fields.items():
            if key not in allowed:
                continue
            if key in ("tools", "capabilities"):
                sets.append(f"{key} = ?")
                params.append(json.dumps(value))
            elif key == "config":
                sets.append("config = ?")
                params.append(json.dumps(value))
            else:
                sets.append(f"{key} = ?")
                params.append(value)

        if not sets:
            return self.get_agent(agent_id)

        now = time.time()
        sets.append("updated_at = ?")
        params.append(now)
        params.append(agent_id)

        with self._lock:
            row = self._conn.execute(
                "SELECT agent_id FROM registered_agents WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
            if not row:
                return None
            self._conn.execute(
                f"UPDATE registered_agents SET {', '.join(sets)} "
                f"WHERE agent_id = ?",
                params,
            )
            self._conn.commit()

        log.info("update_agent %s", agent_id[:12])
        return self.get_agent(agent_id)

    def deregister_agent(self, agent_id: str) -> bool:
        """Deregister an agent. Returns True if found and deleted."""
        with self._lock:
            row = self._conn.execute(
                "SELECT agent_id FROM registered_agents WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
            if not row:
                return False
            self._conn.execute(
                "DELETE FROM agent_logs WHERE agent_id = ?", (agent_id,),
            )
            self._conn.execute(
                "DELETE FROM agent_executions WHERE agent_id = ?", (agent_id,),
            )
            self._conn.execute(
                "DELETE FROM registered_agents WHERE agent_id = ?",
                (agent_id,),
            )
            self._conn.commit()

        self._emit("agent.deregistered", {"agent_id": agent_id})
        log.info("deregister_agent %s", agent_id[:12])
        return True

    def get_agent(self, agent_id: str) -> dict | None:
        """Retrieve a single agent by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM registered_agents WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_row(row)

    def list_agents(self, status: str | None = None,
                    agent_type: str | None = None) -> list[dict]:
        """List registered agents, optionally filtered by status and/or type."""
        with self._lock:
            clauses: list[str] = []
            params: list[Any] = []

            if status is not None:
                clauses.append("status = ?")
                params.append(status)
            if agent_type is not None:
                clauses.append("agent_type = ?")
                params.append(agent_type)

            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = self._conn.execute(
                f"SELECT * FROM registered_agents{where} "
                f"ORDER BY created_at DESC",
                params,
            ).fetchall()

        return [self._parse_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def execute_task(self, agent_id: str, task: str,
                     context: str | None = None) -> dict:
        """Execute a task through an agent.

        Looks up the agent config, builds messages from system_prompt +
        task + context, calls LLMAdapter, and records the execution.

        Returns execution result dict.
        """
        agent = self.get_agent(agent_id)
        if agent is None:
            return {
                "execution_id": None, "agent_id": agent_id,
                "output": None, "tokens_used": 0, "cost": 0.0,
                "latency_ms": 0, "status": "failed",
                "error_message": f"Agent {agent_id} not found",
            }

        execution_id = self._uid()
        now = time.time()

        # Build messages
        messages: list[dict[str, str]] = []
        if agent.get("system_prompt"):
            messages.append({
                "role": "system",
                "content": agent["system_prompt"],
            })
        if context:
            messages.append({"role": "user", "content": context})
        messages.append({"role": "user", "content": task})

        # Record execution as running
        with self._lock:
            self._conn.execute("""
                INSERT INTO agent_executions
                    (execution_id, agent_id, task_description,
                     input_messages, output_text, status,
                     tokens_used, cost, latency_ms, error_message,
                     started_at, completed_at)
                VALUES (?, ?, ?, ?, '', 'running', 0, 0.0, 0, '', ?, NULL)
            """, (
                execution_id, agent_id, task,
                json.dumps(messages), now,
            ))
            self._conn.commit()

        self._emit("agent.execution.started", {
            "execution_id": execution_id, "agent_id": agent_id,
        })

        # Call LLM adapter
        try:
            from sylion.cognitive.llm_adapter import get_llm_adapter
            llm = get_llm_adapter()
            model_id = agent.get("model_id") or "default"
            max_tokens = agent.get("max_tokens", 4096)

            start_time = time.time()
            response = llm.call_messages(model_id, messages, max_tokens)
            latency = int((time.time() - start_time) * 1000)

            if response.get("blocked") or response.get("status") == "blocked":
                reason = (
                    response.get("policy", {}).get("reason")
                    or "Agent LLM call blocked by model runtime policy"
                )
                with self._lock:
                    self._conn.execute("""
                        UPDATE agent_executions
                        SET output_text = '', status = 'blocked',
                            tokens_used = 0, cost = 0.0, latency_ms = ?,
                            error_message = ?, completed_at = ?
                        WHERE execution_id = ?
                    """, (
                        latency, reason, time.time(), execution_id,
                    ))
                    self._conn.commit()

                self._emit("agent.execution.blocked", {
                    "execution_id": execution_id,
                    "agent_id": agent_id,
                    "model_id": model_id,
                    "reason": reason,
                    "policy": response.get("policy", {}),
                })
                return {
                    "execution_id": execution_id,
                    "agent_id": agent_id,
                    "output": None,
                    "tokens_used": 0,
                    "cost": 0.0,
                    "latency_ms": latency,
                    "status": "blocked",
                    "error_message": reason,
                    "policy": response.get("policy", {}),
                }

            output = response.get("text", "")
            tokens_used = response.get("tokens", 0)
            cost = response.get("cost", 0.0)

            with self._lock:
                self._conn.execute("""
                    UPDATE agent_executions
                    SET output_text = ?, status = 'completed',
                        tokens_used = ?, cost = ?, latency_ms = ?,
                        error_message = '', completed_at = ?
                    WHERE execution_id = ?
                """, (
                    output, tokens_used, cost, latency,
                    time.time(), execution_id,
                ))
                self._conn.commit()

            self._emit("agent.execution.completed", {
                "execution_id": execution_id, "agent_id": agent_id,
                "tokens_used": tokens_used, "cost": cost,
                "latency_ms": latency,
            })
            log.info("execute_task %s completed: %dms, %d tokens",
                     execution_id[:12], latency, tokens_used)

            return {
                "execution_id": execution_id,
                "agent_id": agent_id,
                "output": output,
                "tokens_used": tokens_used,
                "cost": cost,
                "latency_ms": latency,
                "status": "completed",
            }

        except Exception as exc:
            error_message = str(exc)
            with self._lock:
                self._conn.execute("""
                    UPDATE agent_executions
                    SET status = 'failed', error_message = ?,
                        completed_at = ?
                    WHERE execution_id = ?
                """, (error_message, time.time(), execution_id))
                self._conn.commit()

            self._emit("agent.execution.failed", {
                "execution_id": execution_id, "agent_id": agent_id,
                "error_message": error_message,
            })
            log.exception("execute_task %s failed: %s",
                          execution_id[:12], error_message)

            return {
                "execution_id": execution_id,
                "agent_id": agent_id,
                "output": None,
                "tokens_used": 0,
                "cost": 0.0,
                "latency_ms": 0,
                "status": "failed",
                "error_message": error_message,
            }

    # ------------------------------------------------------------------
    # Execution queries
    # ------------------------------------------------------------------

    def get_execution(self, execution_id: str) -> dict | None:
        """Retrieve a single execution by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM agent_executions WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_row(row)

    def list_executions(self, agent_id: str | None = None,
                        status: str | None = None,
                        limit: int = 100) -> list[dict]:
        """List executions, optionally filtered by agent and/or status."""
        with self._lock:
            clauses: list[str] = []
            params: list[Any] = []

            if agent_id is not None:
                clauses.append("agent_id = ?")
                params.append(agent_id)
            if status is not None:
                clauses.append("status = ?")
                params.append(status)

            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = self._conn.execute(
                f"SELECT * FROM agent_executions{where} "
                f"ORDER BY started_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()

        return [self._parse_row(r) for r in rows]

    def cancel_execution(self, execution_id: str) -> dict | None:
        """Cancel a pending/running execution. Returns updated dict or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM agent_executions WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()
            if not row:
                return None
            current_status = row["status"]
            if current_status not in ("pending", "running"):
                return None

            now = time.time()
            self._conn.execute("""
                UPDATE agent_executions
                SET status = 'cancelled', completed_at = ?,
                    error_message = 'Cancelled by user'
                WHERE execution_id = ?
            """, (now, execution_id))
            self._conn.commit()

        log.info("cancel_execution %s", execution_id[:12])
        return self.get_execution(execution_id)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def add_log(self, execution_id: str, level: str = "INFO",
                message: str = "") -> dict:
        """Add a log entry for an execution. Returns log dict."""
        log_id = self._uid()
        now = time.time()

        # Resolve agent_id from execution
        with self._lock:
            exec_row = self._conn.execute(
                "SELECT agent_id FROM agent_executions WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()
            agent_id = exec_row["agent_id"] if exec_row else ""

            self._conn.execute("""
                INSERT INTO agent_logs
                    (log_id, execution_id, agent_id, level, message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (log_id, execution_id, agent_id, level, message, now))
            self._conn.commit()

        return {
            "log_id": log_id,
            "execution_id": execution_id,
            "agent_id": agent_id,
            "level": level,
            "message": message,
        }

    def get_logs(self, execution_id: str) -> list[dict]:
        """Get all logs for an execution."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM agent_logs WHERE execution_id = ? "
                "ORDER BY timestamp ASC",
                (execution_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_agent_stats(self, agent_id: str) -> dict:
        """Get statistics for a specific agent."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM agent_executions "
                "WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()["cnt"]

            completed = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM agent_executions "
                "WHERE agent_id = ? AND status = 'completed'",
                (agent_id,),
            ).fetchone()["cnt"]

            avg_latency_row = self._conn.execute(
                "SELECT AVG(latency_ms) as avg_lat FROM agent_executions "
                "WHERE agent_id = ? AND status = 'completed'",
                (agent_id,),
            ).fetchone()
            avg_latency = round(avg_latency_row["avg_lat"] or 0, 2)

            total_tokens = self._conn.execute(
                "SELECT COALESCE(SUM(tokens_used), 0) as total "
                "FROM agent_executions WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()["total"]

            total_cost = self._conn.execute(
                "SELECT COALESCE(SUM(cost), 0.0) as total "
                "FROM agent_executions WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()["total"]

        success_rate = round((completed / total) * 100, 2) if total > 0 else 0.0

        return {
            "agent_id": agent_id,
            "total_executions": total,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 6),
        }

    def get_runtime_stats(self) -> dict:
        """Get aggregate runtime statistics."""
        with self._lock:
            total_agents = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM registered_agents",
            ).fetchone()["cnt"]

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM registered_agents "
                "GROUP BY status",
            ).fetchall()
            agents_by_status = {r["status"]: r["cnt"] for r in status_rows}

            type_rows = self._conn.execute(
                "SELECT agent_type, COUNT(*) as cnt FROM registered_agents "
                "GROUP BY agent_type",
            ).fetchall()
            agents_by_type = {r["agent_type"]: r["cnt"] for r in type_rows}

            total_executions = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM agent_executions",
            ).fetchone()["cnt"]

            exec_status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM agent_executions "
                "GROUP BY status",
            ).fetchall()
            executions_by_status = {
                r["status"]: r["cnt"] for r in exec_status_rows
            }

            total_tokens = self._conn.execute(
                "SELECT COALESCE(SUM(tokens_used), 0) as total "
                "FROM agent_executions",
            ).fetchone()["total"]

            total_cost = self._conn.execute(
                "SELECT COALESCE(SUM(cost), 0.0) as total "
                "FROM agent_executions",
            ).fetchone()["total"]

            total_logs = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM agent_logs",
            ).fetchone()["cnt"]

        return {
            "total_agents": total_agents,
            "agents_by_status": agents_by_status,
            "agents_by_type": agents_by_type,
            "total_executions": total_executions,
            "executions_by_status": executions_by_status,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 6),
            "total_logs": total_logs,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_runtime: AgentRuntimeManager | None = None


def get_agent_runtime(db_path: str | Path | None = None,
                      event_bus: EventBus | None = None) -> AgentRuntimeManager:
    global _runtime
    if _runtime is None:
        _runtime = AgentRuntimeManager(db_path, event_bus)
    return _runtime


def reset_agent_runtime(db_path: str | Path | None = None,
                        event_bus: EventBus | None = None) -> AgentRuntimeManager:
    global _runtime
    _runtime = AgentRuntimeManager(db_path, event_bus)
    return _runtime
