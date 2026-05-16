"""
SYLION Efficiency -- Memory Footprint Tracker

Memory usage tracking per module with budget enforcement.
Records RSS, heap, peak, and GC-count snapshots, stores per-module
memory budgets, and detects potential leaks via trend analysis.

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.efficiency.memory_footprint")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MemorySnapshot:
    """A single memory usage snapshot for a module."""
    snapshot_id: str = ""
    module_id: str = ""
    rss_bytes: int = 0
    heap_bytes: int = 0
    peak_bytes: int = 0
    gc_count: int = 0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.snapshot_id:
            self.snapshot_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class MemoryBudget:
    """Memory budget definition for a module."""
    module_id: str = ""
    max_rss_bytes: int = 0
    max_heap_bytes: int = 0
    description: str = ""


# ---------------------------------------------------------------------------
# Memory Footprint Tracker
# ---------------------------------------------------------------------------

class MemoryFootprintTracker:
    """Memory usage tracking per module.

    Thread-safe. SQLite-backed. Emits events on snapshot / budget operations.
    """

    def __init__(self, event_bus: EventBus | None = None,
                 db_path: str | Path | None = None):
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
            CREATE TABLE IF NOT EXISTS memory_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                module_id   TEXT    NOT NULL DEFAULT '',
                rss_bytes   INTEGER NOT NULL DEFAULT 0,
                heap_bytes  INTEGER NOT NULL DEFAULT 0,
                peak_bytes  INTEGER NOT NULL DEFAULT 0,
                gc_count    INTEGER NOT NULL DEFAULT 0,
                timestamp   REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_budgets (
                module_id      TEXT PRIMARY KEY,
                max_rss_bytes  INTEGER NOT NULL DEFAULT 0,
                max_heap_bytes INTEGER NOT NULL DEFAULT 0,
                description    TEXT    NOT NULL DEFAULT ''
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ms_module ON memory_snapshots(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ms_ts ON memory_snapshots(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(self, module_id: str, rss: int = 0, heap: int = 0,
                 peak: int = 0, gc: int = 0) -> dict:
        """Record a memory snapshot for *module_id*.

        Emits ``efficiency.memory_footprint.snapshotted``.
        """
        snap = MemorySnapshot(
            module_id=module_id,
            rss_bytes=rss,
            heap_bytes=heap,
            peak_bytes=peak,
            gc_count=gc,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO memory_snapshots
                    (snapshot_id, module_id, rss_bytes, heap_bytes,
                     peak_bytes, gc_count, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                snap.snapshot_id, snap.module_id, snap.rss_bytes,
                snap.heap_bytes, snap.peak_bytes, snap.gc_count,
                snap.timestamp,
            ))
            self._conn.commit()

        self._emit("efficiency.memory_footprint.snapshotted", {
            "module_id": module_id,
            "rss_bytes": rss,
            "heap_bytes": heap,
        })

        log.info("memory snapshot for %s: rss=%d, heap=%d",
                 module_id, rss, heap)
        return {
            "snapshot_id": snap.snapshot_id,
            "module_id": module_id,
            "timestamp": snap.timestamp,
        }

    # ------------------------------------------------------------------
    # Budget management
    # ------------------------------------------------------------------

    def set_budget(self, module_id: str, max_rss: int = 0,
                   max_heap: int = 0) -> dict:
        """Set or update the memory budget for *module_id*.

        Emits ``efficiency.memory_footprint.budget_set``.
        """
        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO memory_budgets
                    (module_id, max_rss_bytes, max_heap_bytes, description)
                VALUES (?, ?, ?, ?)
            """, (module_id, max_rss, max_heap, ""))
            self._conn.commit()

        self._emit("efficiency.memory_footprint.budget_set", {
            "module_id": module_id,
            "max_rss_bytes": max_rss,
            "max_heap_bytes": max_heap,
        })

        log.info("budget set for %s: max_rss=%d, max_heap=%d",
                 module_id, max_rss, max_heap)
        return {
            "module_id": module_id,
            "max_rss_bytes": max_rss,
            "max_heap_bytes": max_heap,
        }

    def check_budget(self, module_id: str) -> dict:
        """Check whether *module_id* is within its defined memory budget.

        Returns dict with keys: module_id, status ("within" or "over"),
        max_rss_bytes, max_heap_bytes, current_rss_bytes, current_heap_bytes.
        """
        budget_row = self._conn.execute(
            "SELECT * FROM memory_budgets WHERE module_id = ?",
            (module_id,),
        ).fetchone()

        if budget_row is None:
            return {
                "module_id": module_id,
                "status": "within",
                "max_rss_bytes": None,
                "max_heap_bytes": None,
                "current_rss_bytes": None,
                "current_heap_bytes": None,
                "reason": "no_budget_defined",
            }

        snap_row = self._conn.execute(
            "SELECT rss_bytes, heap_bytes FROM memory_snapshots "
            "WHERE module_id = ? ORDER BY timestamp DESC LIMIT 1",
            (module_id,),
        ).fetchone()

        if snap_row is None:
            return {
                "module_id": module_id,
                "status": "within",
                "max_rss_bytes": budget_row["max_rss_bytes"],
                "max_heap_bytes": budget_row["max_heap_bytes"],
                "current_rss_bytes": None,
                "current_heap_bytes": None,
                "reason": "no_snapshots",
            }

        cur_rss = snap_row["rss_bytes"]
        cur_heap = snap_row["heap_bytes"]
        over = False
        if budget_row["max_rss_bytes"] > 0 and cur_rss > budget_row["max_rss_bytes"]:
            over = True
        if budget_row["max_heap_bytes"] > 0 and cur_heap > budget_row["max_heap_bytes"]:
            over = True

        status = "over" if over else "within"
        result = {
            "module_id": module_id,
            "status": status,
            "max_rss_bytes": budget_row["max_rss_bytes"],
            "max_heap_bytes": budget_row["max_heap_bytes"],
            "current_rss_bytes": cur_rss,
            "current_heap_bytes": cur_heap,
        }

        self._emit("efficiency.memory_footprint.budget_checked", result)
        return result

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_snapshots(self, module_id: str, limit: int = 50) -> list[dict]:
        """Return recent snapshots for *module_id*."""
        rows = self._conn.execute(
            "SELECT * FROM memory_snapshots WHERE module_id = ? ORDER BY timestamp DESC LIMIT ?",
            (module_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_current(self, module_id: str) -> dict | None:
        """Return the most recent snapshot for *module_id*, or None."""
        row = self._conn.execute(
            "SELECT * FROM memory_snapshots WHERE module_id = ? ORDER BY timestamp DESC LIMIT 1",
            (module_id,),
        ).fetchone()
        return dict(row) if row else None

    def detect_leaks(self, module_id: str, window: int = 10) -> dict:
        """Detect potential memory leaks over the last *window* snapshots.

        Compares the trend of rss_bytes across the window. If the latest
        value exceeds the earliest by more than 20%, a leak is suspected.
        Returns dict with keys: module_id, leak_suspected (bool),
        trend_rss_delta, trend_heap_delta, window_size.
        """
        rows = self._conn.execute(
            "SELECT rss_bytes, heap_bytes FROM memory_snapshots "
            "WHERE module_id = ? ORDER BY timestamp DESC LIMIT ?",
            (module_id, window),
        ).fetchall()

        if len(rows) < 2:
            return {
                "module_id": module_id,
                "leak_suspected": False,
                "trend_rss_delta": 0,
                "trend_heap_delta": 0,
                "window_size": len(rows),
                "reason": "insufficient_data",
            }

        # rows are DESC, so first = newest, last = oldest
        newest = rows[0]
        oldest = rows[-1]
        rss_delta = newest["rss_bytes"] - oldest["rss_bytes"]
        heap_delta = newest["heap_bytes"] - oldest["heap_bytes"]

        # Leak suspected if RSS grew by more than 20% of the oldest value
        leak_suspected = False
        if oldest["rss_bytes"] > 0:
            leak_suspected = rss_delta > (oldest["rss_bytes"] * 0.20)
        elif newest["rss_bytes"] > 0:
            leak_suspected = True  # grew from zero

        result = {
            "module_id": module_id,
            "leak_suspected": leak_suspected,
            "trend_rss_delta": rss_delta,
            "trend_heap_delta": heap_delta,
            "window_size": len(rows),
        }

        self._emit("efficiency.memory_footprint.leak_check", result)
        log.info("leak check for %s: suspected=%s, rss_delta=%d",
                 module_id, leak_suspected, rss_delta)
        return result

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="efficiency.memory_footprint",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_tracker: MemoryFootprintTracker | None = None


def get_memory_footprint_tracker(event_bus: EventBus | None = None,
                                 db_path: str | Path | None = None) -> MemoryFootprintTracker:
    global _tracker
    if _tracker is None:
        _tracker = MemoryFootprintTracker(event_bus, db_path)
    return _tracker
