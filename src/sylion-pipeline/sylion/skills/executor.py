"""
SYLION Skills -- Execution Engine

Executes registered skills and tracks execution history.
Delegates execution to the runtime skill engine and tracks execution history.

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

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.skills.executor")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Execution:
    """A single skill execution record."""
    exec_id: str = ""
    skill_id: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    duration_ms: int = 0
    error: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.exec_id:
            self.exec_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Skills Executor
# ---------------------------------------------------------------------------

class SkillsExecutor:
    """Skills execution engine.

    Thread-safe. SQLite-backed. Emits events on execution.
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
            CREATE TABLE IF NOT EXISTS executions (
                exec_id     TEXT PRIMARY KEY,
                skill_id    TEXT    NOT NULL,
                input_data  TEXT    NOT NULL DEFAULT '{}',
                output_data TEXT    NOT NULL DEFAULT '{}',
                status      TEXT    NOT NULL DEFAULT 'pending',
                duration_ms INTEGER NOT NULL DEFAULT 0,
                error       TEXT    NOT NULL DEFAULT '',
                timestamp   REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_exec_skill ON executions(skill_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_exec_status ON executions(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_exec_ts ON executions(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, skill_id: str, input_data: dict | None = None) -> dict:
        """Execute a registered skill through the runtime engine.

        This method intentionally fails closed for missing, retired, or
        deprecated skills. Earlier builds returned a synthetic success for any
        ``skill_id``; that made dashboard tests pass while no runtime skill was
        actually executed.
        """
        if input_data is None:
            input_data = {}

        start = time.time()
        status = "completed"
        error = ""
        output_data: dict[str, Any]
        try:
            from sylion.skills.registry import get_skills_registry
            from sylion.skills.runtime import get_skills_runtime

            registry = get_skills_registry()
            skill = registry.get(skill_id)
            if not skill:
                raise ValueError(f"Skill {skill_id} is not registered")
            lifecycle = str(skill.get("lifecycle") or "DRAFT").upper()
            if lifecycle in {"DEPRECATED", "RETIRED"} and not input_data.get("allow_inactive"):
                raise ValueError(f"Skill {skill_id} cannot execute in lifecycle {lifecycle}")

            runtime = get_skills_runtime()
            if not runtime.get_loaded_skill(skill_id):
                runtime.bootstrap_one(skill.get("runtime_spec") or {})
            runtime_result = runtime.execute(skill_id, inputs=input_data)
            if not runtime_result.get("ok"):
                raise RuntimeError(str(runtime_result.get("error") or "runtime execution failed"))
            output_data = {
                "result": "executed",
                "execution_engine": "skills.runtime",
                "runtime_exec_id": runtime_result.get("exec_id"),
                "skill_id": skill_id,
                "lifecycle": lifecycle,
                "runtime_output": runtime_result.get("output"),
                "steps_completed": runtime_result.get("steps_completed", 0),
                "duration_ms": runtime_result.get("duration_ms", 0),
            }
        except Exception as exc:  # noqa: BLE001 - execution must be recorded
            status = "failed"
            error = str(exc)
            output_data = {
                "result": "failed",
                "execution_engine": "skills.runtime",
                "skill_id": skill_id,
                "error": error,
            }

        duration_ms = int((time.time() - start) * 1000)

        ex = Execution(
            skill_id=skill_id,
            input_data=input_data,
            output_data=output_data,
            status=status,
            duration_ms=duration_ms,
            error=error,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO executions
                    (exec_id, skill_id, input_data, output_data, status, duration_ms, error, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ex.exec_id, ex.skill_id,
                json.dumps(input_data, default=str),
                json.dumps(output_data, default=str),
                ex.status, ex.duration_ms, ex.error, ex.timestamp,
            ))
            self._conn.commit()

        event_topic = "skill.executor.executed" if status == "completed" else "skill.executor.failed"
        self._emit(event_topic, {
            "exec_id": ex.exec_id,
            "skill_id": skill_id,
            "status": status,
            "duration_ms": duration_ms,
            "error": error,
        })

        log.info("skill execution %s: exec_id=%s status=%s (%dms)",
                 skill_id, ex.exec_id[:12], status, duration_ms)
        return {
            "exec_id": ex.exec_id,
            "skill_id": skill_id,
            "status": status,
            "output": output_data,
            "error": error,
            "duration_ms": duration_ms,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_execution(self, exec_id: str) -> dict | None:
        """Return a single execution by ID."""
        row = self._conn.execute(
            "SELECT * FROM executions WHERE exec_id = ?",
            (exec_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["input_data"] = json.loads(d.get("input_data", "{}"))
        d["output_data"] = json.loads(d.get("output_data", "{}"))
        return d

    def list_executions(self, skill_id: str | None = None,
                        status: str | None = None,
                        limit: int = 100) -> list[dict]:
        """List executions with optional skill/status filters."""
        q = "SELECT * FROM executions WHERE 1=1"
        params: list[Any] = []
        if skill_id:
            q += " AND skill_id = ?"
            params.append(skill_id)
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(q, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["input_data"] = json.loads(d.get("input_data", "{}"))
            d["output_data"] = json.loads(d.get("output_data", "{}"))
            results.append(d)
        return results

    def get_stats(self) -> dict:
        """Aggregate execution statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM executions"
        ).fetchone()["cnt"]

        by_status_rows = self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM executions GROUP BY status"
        ).fetchall()
        by_status = {r["status"]: r["cnt"] for r in by_status_rows}

        avg_duration_row = self._conn.execute(
            "SELECT AVG(duration_ms) as avg_ms FROM executions WHERE status = 'completed'"
        ).fetchone()
        avg_duration = avg_duration_row["avg_ms"] if avg_duration_row["avg_ms"] is not None else 0.0

        by_skill_rows = self._conn.execute(
            "SELECT skill_id, COUNT(*) as cnt FROM executions GROUP BY skill_id"
        ).fetchall()
        by_skill = {r["skill_id"]: r["cnt"] for r in by_skill_rows}

        return {
            "total_executions": total,
            "by_status": by_status,
            "avg_duration_ms": round(avg_duration, 2),
            "by_skill": by_skill,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="skills.executor",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_executor: SkillsExecutor | None = None


def _default_executor_db_path() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / "data" / "sylion_skills_executor.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_skills_executor(db_path: str | Path | None = None,
                        event_bus: EventBus | None = None) -> SkillsExecutor:
    global _executor
    target_db_path = db_path or _default_executor_db_path()
    if _executor is None:
        _executor = SkillsExecutor(target_db_path, event_bus)
    elif db_path is not None and str(target_db_path) != _executor._db_path:
        _executor = SkillsExecutor(target_db_path, event_bus)
    return _executor


def reset_skills_executor(db_path: str | Path | None = None,
                          event_bus: EventBus | None = None) -> SkillsExecutor:
    global _executor
    _executor = SkillsExecutor(db_path or _default_executor_db_path(), event_bus)
    return _executor
