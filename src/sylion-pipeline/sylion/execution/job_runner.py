"""
SYLION Execution — Job Runner

Job queue and execution engine. Supports priority-based job
scheduling with submit/get_next/complete/fail lifecycle.

Phase 1: SQLite-backed priority queue.
Phase 2: Distributed job scheduling via gRPC.
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

log = logging.getLogger("sylion.execution.job_runner")


@dataclass
class Job:
    """A queued job."""
    job_id: str = ""
    job_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "queued"
    priority: int = 0
    assigned_to: str = ""
    result: str = ""
    error: str = ""
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()


class JobRunner:
    """Job queue and execution engine.

    Thread-safe. SQLite-backed. Emits events to EventBus.
    Priority ordering: higher priority value = processed first.
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
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id       TEXT PRIMARY KEY,
                job_type     TEXT NOT NULL,
                payload      TEXT NOT NULL DEFAULT '{}',
                status       TEXT NOT NULL DEFAULT 'queued',
                priority     INTEGER NOT NULL DEFAULT 0,
                assigned_to  TEXT NOT NULL DEFAULT '',
                result       TEXT NOT NULL DEFAULT '',
                error        TEXT NOT NULL DEFAULT '',
                created_at   REAL NOT NULL,
                started_at   REAL NOT NULL DEFAULT 0,
                completed_at REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_job_status ON jobs(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_job_type ON jobs(job_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_job_priority ON jobs(priority DESC)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def submit(self, job_type: str, payload: dict[str, Any] | None = None,
               priority: int = 0) -> dict:
        """Submit a new job to the queue."""
        if payload is None:
            payload = {}

        job_id = uuid.uuid4().hex
        created_at = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO jobs
                (job_id, job_type, payload, status, priority,
                 assigned_to, result, error, created_at, started_at, completed_at)
                VALUES (?, ?, ?, 'queued', ?, '', '', '', ?, 0, 0)
            """, (job_id, job_type, json.dumps(payload, default=str),
                  priority, created_at))
            self._conn.commit()

        self._emit("execution.job.submitted", {
            "job_id": job_id, "job_type": job_type, "priority": priority,
        })

        log.info("submitted job %s (type=%s, priority=%d)",
                 job_id[:12], job_type, priority)
        return {"job_id": job_id, "status": "queued"}

    def get_next(self) -> dict | None:
        """Get the highest-priority queued job and mark it running.

        Returns the job dict or None if no queued jobs.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE status = 'queued' ORDER BY priority DESC, created_at ASC LIMIT 1"
            ).fetchone()

            if not row:
                return None

            job_id = row["job_id"]
            started_at = time.time()
            self._conn.execute(
                "UPDATE jobs SET status = 'running', started_at = ? WHERE job_id = ?",
                (started_at, job_id),
            )
            self._conn.commit()

        result = dict(row)
        result["status"] = "running"
        result["started_at"] = started_at
        result["payload"] = json.loads(result.get("payload", "{}"))

        self._emit("execution.job.started", {"job_id": job_id})
        log.info("picked up job %s", job_id[:12])
        return result

    def complete(self, job_id: str, result: str = "") -> bool:
        """Mark a job as completed."""
        completed_at = time.time()

        with self._lock:
            n = self._conn.execute(
                "UPDATE jobs SET status = 'completed', result = ?, completed_at = ? WHERE job_id = ?",
                (result, completed_at, job_id),
            ).rowcount
            self._conn.commit()

        if n:
            self._emit("execution.job.completed", {
                "job_id": job_id, "result": result[:200],
            })
            log.info("completed job %s", job_id[:12])

        return bool(n)

    def fail(self, job_id: str, error: str = "") -> bool:
        """Mark a job as failed."""
        completed_at = time.time()

        with self._lock:
            n = self._conn.execute(
                "UPDATE jobs SET status = 'failed', error = ?, completed_at = ? WHERE job_id = ?",
                (error, completed_at, job_id),
            ).rowcount
            self._conn.commit()

        if n:
            self._emit("execution.job.failed", {
                "job_id": job_id, "error": error[:200],
            })
            log.warning("failed job %s: %s", job_id[:12], error[:100])

        return bool(n)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_job(self, job_id: str) -> dict | None:
        """Get a single job by ID."""
        row = self._conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.get("payload", "{}"))
        return result

    def list_jobs(self, status: str | None = None,
                  limit: int = 100) -> list[dict]:
        """List jobs, optionally filtered by status."""
        if status:
            rows = self._conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d.get("payload", "{}"))
            results.append(d)
        return results

    def get_stats(self) -> dict:
        """Get job queue statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM jobs"
        ).fetchone()["cnt"]

        by_status_rows = self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status"
        ).fetchall()
        by_status = {r["status"]: r["cnt"] for r in by_status_rows}

        return {
            "total_jobs": total,
            "by_status": by_status,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="execution.job_runner",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_runner: JobRunner | None = None


def get_job_runner(db_path: str | Path | None = None,
                   event_bus: EventBus | None = None) -> JobRunner:
    global _runner
    if _runner is None:
        _runner = JobRunner(db_path, event_bus)
    return _runner
