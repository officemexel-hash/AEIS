"""
SYLION Efficiency -- Code Bloat Tracker

Code size and complexity tracking per module.
Computes bloat scores from complexity and dependency counts, records
historical deltas, and validates against configurable budgets.

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

log = logging.getLogger("sylion.efficiency.code_bloat")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ModuleMetric:
    """Snapshot of code bloat metrics for a single module."""
    module_id: str = ""
    lines_of_code: int = 0
    complexity: int = 0
    file_count: int = 0
    dependency_count: int = 0
    bloat_score: float = 0.0
    measured_at: float = 0.0

    def __post_init__(self):
        if not self.measured_at:
            self.measured_at = time.time()


@dataclass
class BloatDelta:
    """Recorded change in module lines of code."""
    record_id: str = ""
    module_id: str = ""
    lines_before: int = 0
    lines_after: int = 0
    delta_percent: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.record_id:
            self.record_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Code Bloat Tracker
# ---------------------------------------------------------------------------

class CodeBloatTracker:
    """Code size and complexity tracking.

    Thread-safe. SQLite-backed. Emits events on measure / delta operations.
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
            CREATE TABLE IF NOT EXISTS module_metrics (
                module_id        TEXT PRIMARY KEY,
                lines_of_code    INTEGER NOT NULL DEFAULT 0,
                complexity       INTEGER NOT NULL DEFAULT 0,
                file_count       INTEGER NOT NULL DEFAULT 0,
                dependency_count INTEGER NOT NULL DEFAULT 0,
                bloat_score      REAL    NOT NULL DEFAULT 0.0,
                measured_at      REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS bloat_history (
                record_id     TEXT PRIMARY KEY,
                module_id     TEXT    NOT NULL DEFAULT '',
                lines_before  INTEGER NOT NULL DEFAULT 0,
                lines_after   INTEGER NOT NULL DEFAULT 0,
                delta_percent REAL    NOT NULL DEFAULT 0.0,
                timestamp     REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bh_module ON bloat_history(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bh_ts ON bloat_history(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Measure
    # ------------------------------------------------------------------

    def measure(self, module_id: str, loc: int, complexity: int,
                files: int = 0, deps: int = 0) -> dict:
        """Measure and persist code bloat metrics for *module_id*.

        Bloat score = (complexity * deps) / max(loc, 1).
        Emits ``efficiency.code_bloat.measured``.
        """
        bloat_score = (complexity * deps) / max(loc, 1)
        now = time.time()

        metric = ModuleMetric(
            module_id=module_id,
            lines_of_code=loc,
            complexity=complexity,
            file_count=files,
            dependency_count=deps,
            bloat_score=bloat_score,
            measured_at=now,
        )

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO module_metrics
                    (module_id, lines_of_code, complexity, file_count,
                     dependency_count, bloat_score, measured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.module_id,
                metric.lines_of_code,
                metric.complexity,
                metric.file_count,
                metric.dependency_count,
                metric.bloat_score,
                metric.measured_at,
            ))
            self._conn.commit()

        self._emit("efficiency.code_bloat.measured", {
            "module_id": module_id,
            "bloat_score": bloat_score,
        })

        log.info("measured module %s: bloat_score=%.2f", module_id, bloat_score)
        return {
            "module_id": module_id,
            "bloat_score": bloat_score,
            "measured_at": now,
        }

    # ------------------------------------------------------------------
    # Delta recording
    # ------------------------------------------------------------------

    def record_delta(self, module_id: str, before: int, after: int) -> dict:
        """Record a lines-of-code delta for *module_id*.

        Computes delta_percent = ((after - before) / max(before, 1)) * 100.
        Emits ``efficiency.code_bloat.delta_recorded``.
        """
        delta_pct = ((after - before) / max(before, 1)) * 100.0
        delta = BloatDelta(
            module_id=module_id,
            lines_before=before,
            lines_after=after,
            delta_percent=delta_pct,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO bloat_history
                    (record_id, module_id, lines_before, lines_after,
                     delta_percent, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                delta.record_id,
                delta.module_id,
                delta.lines_before,
                delta.lines_after,
                delta.delta_percent,
                delta.timestamp,
            ))
            self._conn.commit()

        self._emit("efficiency.code_bloat.delta_recorded", {
            "module_id": module_id,
            "delta_percent": delta_pct,
        })

        log.info("recorded delta for %s: %.1f%%", module_id, delta_pct)
        return {
            "record_id": delta.record_id,
            "module_id": module_id,
            "delta_percent": delta_pct,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_module(self, module_id: str) -> dict | None:
        """Return current metrics for *module_id*, or None."""
        row = self._conn.execute(
            "SELECT * FROM module_metrics WHERE module_id = ?",
            (module_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_modules(self, bloat_threshold: float | None = None) -> list[dict]:
        """List all modules, optionally filtered by bloat_score >= threshold."""
        if bloat_threshold is not None:
            rows = self._conn.execute(
                "SELECT * FROM module_metrics WHERE bloat_score >= ? ORDER BY bloat_score DESC",
                (bloat_threshold,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM module_metrics ORDER BY bloat_score DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_history(self, module_id: str, limit: int = 20) -> list[dict]:
        """Return recent delta history for *module_id*."""
        rows = self._conn.execute(
            "SELECT * FROM bloat_history WHERE module_id = ? ORDER BY timestamp DESC LIMIT ?",
            (module_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def is_within_budget(self, module_id: str, budget_percent: float = 20.0) -> bool:
        """Return True if the last recorded delta is within *budget_percent*."""
        row = self._conn.execute(
            "SELECT delta_percent FROM bloat_history WHERE module_id = ? ORDER BY timestamp DESC LIMIT 1",
            (module_id,),
        ).fetchone()
        if row is None:
            return True
        return abs(row["delta_percent"]) < budget_percent

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="efficiency.code_bloat",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_tracker: CodeBloatTracker | None = None


def get_code_bloat_tracker(event_bus: EventBus | None = None,
                           db_path: str | Path | None = None) -> CodeBloatTracker:
    global _tracker
    if _tracker is None:
        _tracker = CodeBloatTracker(event_bus, db_path)
    return _tracker
