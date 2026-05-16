"""
SYLION AEIS -- Self-Observation Telemetry Collection

Collects and aggregates self-observation metrics for system introspection.
Records metric observations with optional unit, source, and tag metadata.
Maintains running aggregates (avg, min, max, count) per metric.

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

log = logging.getLogger("sylion.aeis.self_observation")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Observation:
    """A single observation data point."""
    observation_id: str = ""
    metric: str = ""
    value: float = 0.0
    unit: str = ""
    source: str = ""
    tags: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.observation_id:
            self.observation_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Self-Observation Engine
# ---------------------------------------------------------------------------

class SelfObservation:
    """Self-observation telemetry collection.

    Thread-safe. SQLite-backed. Emits events on record.
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
            CREATE TABLE IF NOT EXISTS observations (
                observation_id TEXT PRIMARY KEY,
                metric         TEXT    NOT NULL,
                value          REAL    NOT NULL,
                unit           TEXT    NOT NULL DEFAULT '',
                source         TEXT    NOT NULL DEFAULT '',
                tags           TEXT    NOT NULL DEFAULT '{}',
                timestamp      REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS observation_aggregates (
                metric       TEXT PRIMARY KEY,
                avg_value    REAL    NOT NULL DEFAULT 0,
                min_value    REAL    NOT NULL DEFAULT 0,
                max_value    REAL    NOT NULL DEFAULT 0,
                sample_count INTEGER NOT NULL DEFAULT 0,
                last_updated REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_obs_metric ON observations(metric)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_obs_ts ON observations(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record(self, metric: str, value: float, unit: str = "",
               source: str = "", tags: dict | None = None) -> dict:
        """Record a metric observation.

        Updates running aggregates for the metric. Emits
        ``aeis.self_observation.recorded``.
        """
        if tags is None:
            tags = {}

        obs = Observation(
            metric=metric,
            value=value,
            unit=unit,
            source=source,
            tags=tags,
        )

        now = obs.timestamp

        with self._lock:
            self._conn.execute("""
                INSERT INTO observations
                    (observation_id, metric, value, unit, source, tags, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                obs.observation_id, obs.metric, obs.value,
                obs.unit, obs.source, json.dumps(tags, default=str),
                obs.timestamp,
            ))

            # Update aggregates
            existing = self._conn.execute(
                "SELECT * FROM observation_aggregates WHERE metric = ?",
                (metric,),
            ).fetchone()

            if existing:
                new_count = existing["sample_count"] + 1
                new_avg = (existing["avg_value"] * existing["sample_count"] + value) / new_count
                new_min = min(existing["min_value"], value)
                new_max = max(existing["max_value"], value)
                self._conn.execute("""
                    UPDATE observation_aggregates
                    SET avg_value = ?, min_value = ?, max_value = ?,
                        sample_count = ?, last_updated = ?
                    WHERE metric = ?
                """, (new_avg, new_min, new_max, new_count, now, metric))
            else:
                self._conn.execute("""
                    INSERT INTO observation_aggregates
                        (metric, avg_value, min_value, max_value, sample_count, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (metric, value, value, value, 1, now))

            self._conn.commit()

        self._emit("aeis.self_observation.recorded", {
            "observation_id": obs.observation_id,
            "metric": metric,
            "value": value,
        })

        log.info("recorded observation %s: %s=%.4f",
                 obs.observation_id[:12], metric, value)
        return {
            "observation_id": obs.observation_id,
            "metric": metric,
            "value": value,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_observations(self, metric: str, limit: int = 100) -> list[dict]:
        """Return recent observations for a given metric."""
        rows = self._conn.execute(
            "SELECT * FROM observations WHERE metric = ? ORDER BY timestamp DESC LIMIT ?",
            (metric, limit),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["tags"] = json.loads(d.get("tags", "{}"))
            results.append(d)
        return results

    def get_aggregate(self, metric: str) -> dict | None:
        """Return aggregate stats for a given metric."""
        row = self._conn.execute(
            "SELECT * FROM observation_aggregates WHERE metric = ?",
            (metric,),
        ).fetchone()
        return dict(row) if row else None

    def get_dashboard(self) -> list[dict]:
        """Return all aggregate data for dashboard display."""
        rows = self._conn.execute(
            "SELECT * FROM observation_aggregates ORDER BY last_updated DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Aggregate observation statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM observations"
        ).fetchone()["cnt"]

        metric_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM observation_aggregates"
        ).fetchone()["cnt"]

        by_metric_rows = self._conn.execute(
            "SELECT metric, COUNT(*) as cnt FROM observations GROUP BY metric"
        ).fetchall()
        by_metric = {r["metric"]: r["cnt"] for r in by_metric_rows}

        return {
            "total_observations": total,
            "unique_metrics": metric_count,
            "by_metric": by_metric,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.self_observation",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_observer: SelfObservation | None = None


def get_self_observation(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> SelfObservation:
    global _observer
    if _observer is None:
        _observer = SelfObservation(db_path, event_bus)
    return _observer
