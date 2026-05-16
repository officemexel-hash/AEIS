"""
SYLION Monitoring -- Metric Aggregator

Aggregates and time-buckets metrics for dashboard display.
Records raw metric data points, computes period-based aggregates
(avg, min, max, count), and exposes query APIs for dashboard
consumption.

Time periods: 1m, 5m, 15m, 1h, 6h, 1d, 7d.

SQLite-backed with WAL mode.  Thread-safe via threading.RLock().
Singleton via get_metric_aggregator() / reset_metric_aggregator().
Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.monitoring.metric_aggregator")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_PERIODS = ("1m", "5m", "15m", "1h", "6h", "1d", "7d")

PERIOD_SECONDS: dict[str, float] = {
    "1m":  60.0,
    "5m":  300.0,
    "15m": 900.0,
    "1h":  3600.0,
    "6h":  21600.0,
    "1d":  86400.0,
    "7d":  604800.0,
}


# ---------------------------------------------------------------------------
# MetricAggregator
# ---------------------------------------------------------------------------

class MetricAggregator:
    """Aggregate and time-bucket metrics for dashboard display.

    Thread-safe.  SQLite-backed.  Emits events on record / aggregate.
    """

    def __init__(self, db_path: str | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
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
            CREATE TABLE IF NOT EXISTS metric_points (
                point_id     TEXT PRIMARY KEY,
                metric_name  TEXT    NOT NULL,
                source       TEXT    NOT NULL DEFAULT '',
                value        REAL    NOT NULL,
                tags         TEXT    NOT NULL DEFAULT '{}',
                timestamp    REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS metric_aggregates (
                aggregate_id TEXT    PRIMARY KEY,
                metric_name  TEXT    NOT NULL,
                source       TEXT    NOT NULL DEFAULT '',
                period       TEXT    NOT NULL,
                avg_value    REAL    NOT NULL,
                min_value    REAL    NOT NULL,
                max_value    REAL    NOT NULL,
                count        INTEGER NOT NULL,
                period_start REAL    NOT NULL,
                period_end   REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mp_name ON metric_points(metric_name)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mp_source ON metric_points(source)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mp_ts ON metric_points(timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mp_name_source_ts "
            "ON metric_points(metric_name, source, timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ma_name ON metric_aggregates(metric_name)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ma_period ON metric_aggregates(period)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ma_source ON metric_aggregates(source)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ma_name_period_source "
            "ON metric_aggregates(metric_name, period, source)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # record
    # ------------------------------------------------------------------

    def record(self, metric_name: str, value: float, source: str = "",
               tags: dict[str, str] | None = None) -> dict:
        """Record a metric data point.

        Returns a dict with point_id, metric_name, source, value, timestamp.
        Emits ``metric.recorded`` on the EventBus.
        """
        point_id = uuid.uuid4().hex
        now = time.time()
        tags_json = json.dumps(tags, default=str) if tags else "{}"

        with self._lock:
            self._conn.execute("""
                INSERT INTO metric_points
                    (point_id, metric_name, source, value, tags, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (point_id, metric_name, source, value, tags_json, now))
            self._conn.commit()

        self._emit("metric.recorded", {
            "point_id": point_id,
            "metric_name": metric_name,
            "source": source,
            "value": value,
            "timestamp": now,
        })
        log.info(
            "recorded metric %s=%.4f source=%s", metric_name, value, source,
        )
        return {
            "point_id": point_id,
            "metric_name": metric_name,
            "source": source,
            "value": value,
            "timestamp": now,
        }

    # ------------------------------------------------------------------
    # get_points
    # ------------------------------------------------------------------

    def get_points(self, metric_name: str, source: str | None = None,
                   since: float | None = None, until: float | None = None,
                   limit: int = 1000) -> list[dict]:
        """List raw metric points with optional filters.

        Results are ordered by timestamp ascending.
        """
        with self._lock:
            conditions: list[str] = ["metric_name = ?"]
            params: list[Any] = [metric_name]

            if source is not None:
                conditions.append("source = ?")
                params.append(source)
            if since is not None:
                conditions.append("timestamp >= ?")
                params.append(since)
            if until is not None:
                conditions.append("timestamp <= ?")
                params.append(until)

            where = " AND ".join(conditions)
            query = (
                f"SELECT * FROM metric_points WHERE {where} "
                f"ORDER BY timestamp ASC LIMIT ?"
            )
            params.append(limit)
            rows = self._conn.execute(query, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["tags"] = json.loads(d.get("tags", "{}"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # aggregate
    # ------------------------------------------------------------------

    def aggregate(self, metric_name: str, period: str = "1h",
                  source: str | None = None) -> list[dict]:
        """Compute aggregates for a metric over the given period.

        Time-buckets all matching points by the period duration,
        computes avg / min / max / count per bucket, and upserts
        into ``metric_aggregates``.

        Returns a list of aggregate dicts.
        """
        if period not in VALID_PERIODS:
            raise ValueError(
                f"Invalid period '{period}'. Must be one of {VALID_PERIODS}"
            )

        period_secs = PERIOD_SECONDS[period]

        with self._lock:
            conditions: list[str] = ["metric_name = ?"]
            params: list[Any] = [metric_name]
            if source is not None:
                conditions.append("source = ?")
                params.append(source)

            where = " AND ".join(conditions)
            rows = self._conn.execute(
                f"SELECT point_id, value, timestamp FROM metric_points "
                f"WHERE {where} ORDER BY timestamp ASC",
                params,
            ).fetchall()

        if not rows:
            return []

        # Bucket the points
        buckets: dict[int, list[tuple[float, float]]] = {}
        for r in rows:
            ts = r["timestamp"]
            bucket_start = int(ts // period_secs) * period_secs
            if bucket_start not in buckets:
                buckets[bucket_start] = []
            buckets[bucket_start].append((r["value"], ts))

        aggregates: list[dict] = []

        with self._lock:
            for bucket_start, points in sorted(buckets.items()):
                values = [v for v, _ in points]
                bucket_end = bucket_start + period_secs
                aggregate_id = f"{metric_name}:{source or '*'}:{period}:{int(bucket_start)}"

                avg_val = sum(values) / len(values)
                min_val = min(values)
                max_val = max(values)
                count_val = len(values)

                self._conn.execute("""
                    INSERT OR REPLACE INTO metric_aggregates
                        (aggregate_id, metric_name, source, period,
                         avg_value, min_value, max_value, count,
                         period_start, period_end)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    aggregate_id, metric_name, source or "", period,
                    avg_val, min_val, max_val, count_val,
                    bucket_start, bucket_end,
                ))

                aggregates.append({
                    "aggregate_id": aggregate_id,
                    "metric_name": metric_name,
                    "source": source or "",
                    "period": period,
                    "avg_value": avg_val,
                    "min_value": min_val,
                    "max_value": max_val,
                    "count": count_val,
                    "period_start": bucket_start,
                    "period_end": bucket_end,
                })

            self._conn.commit()

        self._emit("metric.aggregated", {
            "metric_name": metric_name,
            "period": period,
            "source": source or "",
            "bucket_count": len(aggregates),
        })
        log.info(
            "aggregated %s (%s, source=%s): %d buckets",
            metric_name, period, source, len(aggregates),
        )
        return aggregates

    # ------------------------------------------------------------------
    # get_aggregates
    # ------------------------------------------------------------------

    def get_aggregates(self, metric_name: str, period: str | None = None,
                       source: str | None = None,
                       limit: int = 100) -> list[dict]:
        """List stored aggregates with optional filters.

        Results are ordered by period_start descending.
        """
        with self._lock:
            conditions: list[str] = ["metric_name = ?"]
            params: list[Any] = [metric_name]

            if period is not None:
                conditions.append("period = ?")
                params.append(period)
            if source is not None:
                conditions.append("source = ?")
                params.append(source)

            where = " AND ".join(conditions)
            query = (
                f"SELECT * FROM metric_aggregates WHERE {where} "
                f"ORDER BY period_start DESC LIMIT ?"
            )
            params.append(limit)
            rows = self._conn.execute(query, params).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # get_latest
    # ------------------------------------------------------------------

    def get_latest(self, metric_name: str,
                   source: str | None = None) -> dict | None:
        """Return the most recent data point for a metric.

        Optionally filtered by source.
        """
        with self._lock:
            conditions: list[str] = ["metric_name = ?"]
            params: list[Any] = [metric_name]
            if source is not None:
                conditions.append("source = ?")
                params.append(source)

            where = " AND ".join(conditions)
            row = self._conn.execute(
                f"SELECT * FROM metric_points WHERE {where} "
                f"ORDER BY timestamp DESC LIMIT 1",
                params,
            ).fetchone()

        if not row:
            return None

        d = dict(row)
        d["tags"] = json.loads(d.get("tags", "{}"))
        return d

    # ------------------------------------------------------------------
    # get_stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate statistics about the metric store.

        Returns dict with:
          total_points, total_aggregates, metric_count,
          by_metric (point counts per metric),
          by_source (point counts per source)
        """
        with self._lock:
            total_points = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM metric_points"
            ).fetchone()["cnt"]

            total_aggregates = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM metric_aggregates"
            ).fetchone()["cnt"]

            distinct_metrics = self._conn.execute(
                "SELECT COUNT(DISTINCT metric_name) as cnt FROM metric_points"
            ).fetchone()["cnt"]

            metric_rows = self._conn.execute(
                "SELECT metric_name, COUNT(*) as cnt FROM metric_points "
                "GROUP BY metric_name ORDER BY cnt DESC"
            ).fetchall()
            by_metric = {r["metric_name"]: r["cnt"] for r in metric_rows}

            source_rows = self._conn.execute(
                "SELECT source, COUNT(*) as cnt FROM metric_points "
                "GROUP BY source ORDER BY cnt DESC"
            ).fetchall()
            by_source = {r["source"]: r["cnt"] for r in source_rows}

        return {
            "total_points": total_points,
            "total_aggregates": total_aggregates,
            "metric_count": distinct_metrics,
            "by_metric": by_metric,
            "by_source": by_source,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="monitoring.metric_aggregator",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: MetricAggregator | None = None


def get_metric_aggregator(db_path: str | None = None,
                          event_bus: EventBus | None = None) -> MetricAggregator:
    """Get or create the global MetricAggregator singleton."""
    global _instance
    if _instance is None:
        _instance = MetricAggregator(db_path, event_bus)
    return _instance


def reset_metric_aggregator() -> None:
    """Reset the global singleton (for testing)."""
    global _instance
    _instance = None
