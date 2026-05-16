"""
SYLION AEIS -- Self-Improvement Queue

Manages a prioritized queue of self-improvement items.
Items progress through: queued -> in_progress -> completed/rejected.

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

log = logging.getLogger("sylion.aeis.improvement_queue")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Improvement:
    """A single improvement item in the queue."""
    improvement_id: str = ""
    title: str = ""
    description: str = ""
    category: str = "performance"
    priority: int = 0
    status: str = "queued"
    source: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0

    def __post_init__(self):
        if not self.improvement_id:
            self.improvement_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


# ---------------------------------------------------------------------------
# Improvement Queue
# ---------------------------------------------------------------------------

class ImprovementQueue:
    """Self-improvement queue with priority ordering.

    Thread-safe. SQLite-backed. Emits events on state transitions.
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
            CREATE TABLE IF NOT EXISTS improvements (
                improvement_id TEXT PRIMARY KEY,
                title          TEXT    NOT NULL,
                description    TEXT    NOT NULL DEFAULT '',
                category       TEXT    NOT NULL DEFAULT 'performance',
                priority       INTEGER NOT NULL DEFAULT 0,
                status         TEXT    NOT NULL DEFAULT 'queued',
                source         TEXT    NOT NULL DEFAULT '',
                evidence       TEXT    NOT NULL DEFAULT '{}',
                created_at     REAL    NOT NULL,
                started_at     REAL    NOT NULL DEFAULT 0,
                completed_at   REAL    NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_imp_status ON improvements(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_imp_category ON improvements(category)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_imp_priority ON improvements(priority DESC)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit(self, title: str, description: str = "",
               category: str = "performance", priority: int = 0,
               source: str = "", evidence: dict | None = None) -> dict:
        """Submit a new improvement to the queue.

        Emits ``aeis.improvement_queue.submitted``.
        """
        if evidence is None:
            evidence = {}

        imp = Improvement(
            title=title,
            description=description,
            category=category,
            priority=priority,
            source=source,
            evidence=evidence,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO improvements
                    (improvement_id, title, description, category, priority,
                     status, source, evidence, created_at, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                imp.improvement_id, imp.title, imp.description,
                imp.category, imp.priority, imp.status, imp.source,
                json.dumps(evidence, default=str), imp.created_at,
                imp.started_at, imp.completed_at,
            ))
            self._conn.commit()

        self._emit("aeis.improvement_queue.submitted", {
            "improvement_id": imp.improvement_id,
            "title": title,
            "priority": priority,
        })

        log.info("submitted improvement %s: %s (pri=%d)",
                 imp.improvement_id[:12], title, priority)
        return {
            "improvement_id": imp.improvement_id,
            "title": title,
            "status": imp.status,
        }

    # ------------------------------------------------------------------
    # Get next (highest priority queued)
    # ------------------------------------------------------------------

    def get_next(self) -> dict | None:
        """Return the highest-priority queued improvement."""
        row = self._conn.execute(
            "SELECT * FROM improvements WHERE status = 'queued' ORDER BY priority DESC, created_at ASC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["evidence"] = json.loads(d.get("evidence", "{}"))
        return d

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def start(self, improvement_id: str) -> dict:
        """Mark an improvement as in_progress.

        Emits ``aeis.improvement_queue.started``.
        """
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE improvements SET status = 'in_progress', started_at = ? WHERE improvement_id = ?",
                (now, improvement_id),
            )
            self._conn.commit()

        self._emit("aeis.improvement_queue.started", {
            "improvement_id": improvement_id,
        })

        log.info("started improvement %s", improvement_id[:12])
        return {"improvement_id": improvement_id, "status": "in_progress"}

    def complete(self, improvement_id: str, result: str = "") -> dict:
        """Mark an improvement as completed.

        Emits ``aeis.improvement_queue.completed``.
        """
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE improvements SET status = 'completed', completed_at = ? WHERE improvement_id = ?",
                (now, improvement_id),
            )
            self._conn.commit()

        self._emit("aeis.improvement_queue.completed", {
            "improvement_id": improvement_id,
            "result": result,
        })

        log.info("completed improvement %s", improvement_id[:12])
        return {"improvement_id": improvement_id, "status": "completed"}

    def reject(self, improvement_id: str, reason: str = "") -> dict:
        """Mark an improvement as rejected.

        Emits ``aeis.improvement_queue.rejected``.
        """
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE improvements SET status = 'rejected', completed_at = ? WHERE improvement_id = ?",
                (now, improvement_id),
            )
            self._conn.commit()

        self._emit("aeis.improvement_queue.rejected", {
            "improvement_id": improvement_id,
            "reason": reason,
        })

        log.info("rejected improvement %s: %s", improvement_id[:12], reason)
        return {"improvement_id": improvement_id, "status": "rejected"}

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_improvements(self, status: str | None = None,
                          category: str | None = None,
                          limit: int = 100) -> list[dict]:
        """List improvements with optional status/category filters."""
        q = "SELECT * FROM improvements WHERE 1=1"
        params: list[Any] = []
        if status:
            q += " AND status = ?"
            params.append(status)
        if category:
            q += " AND category = ?"
            params.append(category)
        q += " ORDER BY priority DESC, created_at ASC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(q, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["evidence"] = json.loads(d.get("evidence", "{}"))
            results.append(d)
        return results

    def get_stats(self) -> dict:
        """Aggregate improvement queue statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM improvements"
        ).fetchone()["cnt"]

        by_status_rows = self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM improvements GROUP BY status"
        ).fetchall()
        by_status = {r["status"]: r["cnt"] for r in by_status_rows}

        by_category_rows = self._conn.execute(
            "SELECT category, COUNT(*) as cnt FROM improvements GROUP BY category"
        ).fetchall()
        by_category = {r["category"]: r["cnt"] for r in by_category_rows}

        return {
            "total": total,
            "by_status": by_status,
            "by_category": by_category,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.improvement_queue",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_queue: ImprovementQueue | None = None


def get_improvement_queue(db_path: str | Path | None = None,
                          event_bus: EventBus | None = None) -> ImprovementQueue:
    global _queue
    if _queue is None:
        _queue = ImprovementQueue(db_path, event_bus)
    return _queue
