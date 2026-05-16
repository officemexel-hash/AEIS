"""
SYLION Execution -- Capacity Planner

Plans resource capacity based on usage patterns and forecasts.
Records resource usage metrics, computes linear extrapolation
forecasts, and detects bottlenecks when headroom drops below
a threshold.

Tables:
  resource_usage     -- raw usage samples per resource
  capacity_forecasts -- computed forecasts with headroom

Singleton: get_capacity_planner() / reset_capacity_planner()
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.execution.capacity_planner")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESOURCE_TYPES = ("compute", "memory", "storage", "network", "api_calls", "tokens")
FORECAST_PERIODS = ("1d", "7d", "30d", "90d")

# Mapping from forecast period label to lookback window in seconds.
_PERIOD_SECONDS: dict[str, float] = {
    "1d": 86400.0,
    "7d": 86400.0 * 7,
    "30d": 86400.0 * 30,
    "90d": 86400.0 * 90,
}


# ---------------------------------------------------------------------------
# Capacity Planner
# ---------------------------------------------------------------------------

class CapacityPlanner:
    """Resource capacity planner backed by SQLite.

    Records usage samples, extrapolates demand forecasts, and raises
    bottleneck events when headroom is low.

    Thread-safe via RLock. Emits events through EventBus.
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
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS resource_usage (
                usage_id      TEXT PRIMARY KEY,
                resource_type TEXT NOT NULL,
                resource_id   TEXT NOT NULL,
                metric        TEXT NOT NULL,
                value         REAL NOT NULL,
                unit          TEXT NOT NULL DEFAULT 'units',
                recorded_at   REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS capacity_forecasts (
                forecast_id       TEXT PRIMARY KEY,
                resource_type     TEXT NOT NULL,
                resource_id       TEXT NOT NULL,
                forecast_period   TEXT NOT NULL,
                current_capacity  REAL NOT NULL,
                projected_demand  REAL NOT NULL,
                headroom          REAL NOT NULL,
                computed_at       REAL NOT NULL
            );
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_type_id "
            "ON resource_usage(resource_type, resource_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_metric "
            "ON resource_usage(metric)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_recorded "
            "ON resource_usage(recorded_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_forecast_type_id "
            "ON capacity_forecasts(resource_type, resource_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_forecast_period "
            "ON capacity_forecasts(forecast_period)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_forecast_headroom "
            "ON capacity_forecasts(headroom)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _now() -> float:
        return time.time()

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="execution.capacity_planner",
            ))

    @staticmethod
    def _validate_resource_type(resource_type: str):
        if resource_type not in RESOURCE_TYPES:
            raise ValueError(
                f"Invalid resource_type '{resource_type}', "
                f"must be one of {RESOURCE_TYPES}"
            )

    @staticmethod
    def _validate_forecast_period(forecast_period: str):
        if forecast_period not in FORECAST_PERIODS:
            raise ValueError(
                f"Invalid forecast_period '{forecast_period}', "
                f"must be one of {FORECAST_PERIODS}"
            )

    @staticmethod
    def _period_to_seconds(forecast_period: str) -> float:
        return _PERIOD_SECONDS[forecast_period]

    # ------------------------------------------------------------------
    # Usage recording
    # ------------------------------------------------------------------

    def record_usage(self, resource_type: str, resource_id: str,
                     metric: str, value: float,
                     unit: str = "units") -> dict:
        """Record a resource usage sample.

        Returns the recorded usage dict.
        """
        self._validate_resource_type(resource_type)

        usage_id = self._uid()
        now = self._now()

        with self._lock:
            self._conn.execute("""
                INSERT INTO resource_usage
                    (usage_id, resource_type, resource_id, metric,
                     value, unit, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (usage_id, resource_type, resource_id, metric,
                  value, unit, now))
            self._conn.commit()

        result = {
            "usage_id": usage_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "metric": metric,
            "value": value,
            "unit": unit,
            "recorded_at": now,
        }

        self._emit("capacity.usage_recorded", {
            "usage_id": usage_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "metric": metric,
            "value": value,
        })
        log.info("usage recorded: %s %s/%s %s=%s%s",
                 resource_type, resource_id, metric, value, unit,
                 usage_id[:12])
        return result

    def get_usage(self, resource_type: str | None = None,
                  resource_id: str | None = None,
                  metric: str | None = None,
                  since: float | None = None,
                  limit: int = 1000) -> list[dict]:
        """Query usage samples with optional filters.

        Returns a list of usage dicts ordered by recorded_at DESC.
        """
        conds: list[str] = []
        params: list[Any] = []

        if resource_type is not None:
            self._validate_resource_type(resource_type)
            conds.append("resource_type = ?")
            params.append(resource_type)
        if resource_id is not None:
            conds.append("resource_id = ?")
            params.append(resource_id)
        if metric is not None:
            conds.append("metric = ?")
            params.append(metric)
        if since is not None:
            conds.append("recorded_at >= ?")
            params.append(since)

        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM resource_usage{where} "
                f"ORDER BY recorded_at DESC LIMIT ?",
                params,
            ).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Forecast computation
    # ------------------------------------------------------------------

    def compute_forecast(self, resource_type: str, resource_id: str,
                         forecast_period: str = "7d") -> dict:
        """Compute a capacity forecast from recent usage data.

        Uses simple linear extrapolation: fits a line to the usage
        samples within the lookback window and projects demand forward.
        Current capacity is estimated as the peak observed value scaled
        up by a safety factor.  Headroom = (capacity - demand) / capacity.

        Returns the forecast dict.
        """
        self._validate_resource_type(resource_type)
        self._validate_forecast_period(forecast_period)

        period_seconds = self._period_to_seconds(forecast_period)
        now = self._now()
        since = now - period_seconds

        # Gather usage samples in the lookback window
        with self._lock:
            rows = self._conn.execute(
                "SELECT value, recorded_at FROM resource_usage "
                "WHERE resource_type = ? AND resource_id = ? "
                "AND recorded_at >= ? "
                "ORDER BY recorded_at ASC",
                (resource_type, resource_id, since),
            ).fetchall()

        if not rows:
            # No usage data: capacity=1.0, demand=0.0, headroom=1.0
            current_capacity = 1.0
            projected_demand = 0.0
            headroom = 1.0
        else:
            values = [r["value"] for r in rows]
            timestamps = [r["recorded_at"] for r in rows]

            # Peak observed value is the base for current capacity
            peak = max(values)

            # Linear extrapolation: least-squares slope
            projected_demand = self._linear_extrapolate(
                timestamps, values, now, now + period_seconds,
            )

            # Current capacity is peak * 1.5 safety margin
            current_capacity = peak * 1.5

            # Guard: capacity must be > 0
            if current_capacity <= 0:
                current_capacity = 1.0

            headroom = (current_capacity - projected_demand) / current_capacity

        # Upsert forecast
        forecast_id = self._uid()
        with self._lock:
            # Delete any existing forecast for this key
            self._conn.execute(
                "DELETE FROM capacity_forecasts "
                "WHERE resource_type = ? AND resource_id = ? "
                "AND forecast_period = ?",
                (resource_type, resource_id, forecast_period),
            )
            self._conn.execute("""
                INSERT INTO capacity_forecasts
                    (forecast_id, resource_type, resource_id,
                     forecast_period, current_capacity,
                     projected_demand, headroom, computed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (forecast_id, resource_type, resource_id,
                  forecast_period, current_capacity,
                  projected_demand, headroom, now))
            self._conn.commit()

        result = {
            "forecast_id": forecast_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "forecast_period": forecast_period,
            "current_capacity": current_capacity,
            "projected_demand": projected_demand,
            "headroom": headroom,
            "computed_at": now,
        }

        # Check for bottleneck (headroom < 0.2)
        if headroom < 0.2:
            self._emit("capacity.bottleneck_detected", {
                "forecast_id": forecast_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "forecast_period": forecast_period,
                "headroom": headroom,
                "current_capacity": current_capacity,
                "projected_demand": projected_demand,
            })
            log.warning(
                "bottleneck detected: %s/%s headroom=%.2f (%s)",
                resource_type, resource_id, headroom, forecast_period,
            )

        self._emit("capacity.forecast_computed", {
            "forecast_id": forecast_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "forecast_period": forecast_period,
            "headroom": headroom,
        })
        log.info("forecast computed: %s/%s %s headroom=%.2f",
                 resource_type, resource_id, forecast_period, headroom)
        return result

    @staticmethod
    def _linear_extrapolate(timestamps: list[float], values: list[float],
                            t_now: float, t_future: float) -> float:
        """Simple linear extrapolation from (timestamps, values).

        Fits a least-squares line y = a + b*t and evaluates at t_future.
        If only one sample, returns that value.  If slope is negative,
        clamps projected demand to max observed (no negative growth).
        """
        n = len(timestamps)
        if n == 0:
            return 0.0
        if n == 1:
            return values[0]

        # Center timestamps near the forecast origin to avoid floating-point issues.
        t0 = t_now
        t_sum = sum(t - t0 for t in timestamps)
        t2_sum = sum((t - t0) ** 2 for t in timestamps)
        y_sum = sum(values)
        ty_sum = sum((timestamps[i] - t0) * values[i] for i in range(n))

        denom = n * t2_sum - t_sum ** 2
        if denom == 0:
            # All timestamps identical
            return sum(values) / n

        # Least squares: y = a + b * (t - t0)
        b = (n * ty_sum - t_sum * y_sum) / denom
        a = (y_sum - b * t_sum) / n

        projected = a + b * (t_future - t0)

        # Clamp: projected demand cannot be negative
        if projected < 0:
            projected = max(values)

        return projected

    def get_forecast(self, resource_type: str, resource_id: str,
                     forecast_period: str = "7d") -> dict | None:
        """Get the latest forecast for a resource.

        Returns the forecast dict or None if not found.
        """
        self._validate_resource_type(resource_type)
        self._validate_forecast_period(forecast_period)

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM capacity_forecasts "
                "WHERE resource_type = ? AND resource_id = ? "
                "AND forecast_period = ? "
                "ORDER BY computed_at DESC LIMIT 1",
                (resource_type, resource_id, forecast_period),
            ).fetchone()

        return dict(row) if row else None

    def list_forecasts(self, resource_type: str | None = None,
                       forecast_period: str | None = None,
                       limit: int = 100) -> list[dict]:
        """List forecasts with optional filters.

        Returns a list of forecast dicts ordered by computed_at DESC.
        """
        if resource_type is not None:
            self._validate_resource_type(resource_type)
        if forecast_period is not None:
            self._validate_forecast_period(forecast_period)

        conds: list[str] = []
        params: list[Any] = []

        if resource_type is not None:
            conds.append("resource_type = ?")
            params.append(resource_type)
        if forecast_period is not None:
            conds.append("forecast_period = ?")
            params.append(forecast_period)

        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM capacity_forecasts{where} "
                f"ORDER BY computed_at DESC LIMIT ?",
                params,
            ).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Bottleneck detection
    # ------------------------------------------------------------------

    def get_bottlenecks(self, headroom_threshold: float = 0.2) -> list[dict]:
        """Return resources whose headroom is below the threshold.

        Queries the latest forecast for each (resource_type, resource_id,
        forecast_period) combination and returns those with headroom
        below the threshold.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM capacity_forecasts "
                "WHERE headroom < ? "
                "ORDER BY headroom ASC",
                (headroom_threshold,),
            ).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return aggregate statistics: usage counts, forecast counts."""
        with self._lock:
            total_usage = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM resource_usage"
            ).fetchone()["cnt"]

            total_forecasts = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM capacity_forecasts"
            ).fetchone()["cnt"]

            # Usage by resource type
            type_rows = self._conn.execute(
                "SELECT resource_type, COUNT(*) as cnt FROM resource_usage "
                "GROUP BY resource_type"
            ).fetchall()
            usage_by_type = {r["resource_type"]: r["cnt"] for r in type_rows}

            # Usage by metric
            metric_rows = self._conn.execute(
                "SELECT metric, COUNT(*) as cnt FROM resource_usage "
                "GROUP BY metric"
            ).fetchall()
            usage_by_metric = {r["metric"]: r["cnt"] for r in metric_rows}

            # Forecasts by period
            period_rows = self._conn.execute(
                "SELECT forecast_period, COUNT(*) as cnt FROM capacity_forecasts "
                "GROUP BY forecast_period"
            ).fetchall()
            forecasts_by_period = {r["forecast_period"]: r["cnt"] for r in period_rows}

            # Bottleneck count
            bottleneck_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM capacity_forecasts "
                "WHERE headroom < 0.2"
            ).fetchone()["cnt"]

        # Fill in zero-count resource types
        for rt in RESOURCE_TYPES:
            usage_by_type.setdefault(rt, 0)
        for fp in FORECAST_PERIODS:
            forecasts_by_period.setdefault(fp, 0)

        return {
            "total_usage": total_usage,
            "total_forecasts": total_forecasts,
            "bottleneck_count": bottleneck_count,
            "usage_by_type": usage_by_type,
            "usage_by_metric": usage_by_metric,
            "forecasts_by_period": forecasts_by_period,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_planner: CapacityPlanner | None = None


def get_capacity_planner(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> CapacityPlanner:
    global _planner
    if _planner is None:
        _planner = CapacityPlanner(db_path, event_bus)
    return _planner


def reset_capacity_planner(db_path: str | Path | None = None,
                           event_bus: EventBus | None = None) -> CapacityPlanner:
    global _planner
    _planner = CapacityPlanner(db_path, event_bus)
    return _planner
