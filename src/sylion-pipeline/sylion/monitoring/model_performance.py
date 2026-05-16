"""
SYLION Monitoring -- Model Performance Tracker

Tracks individual model performance metrics (response time, quality scores,
error rates, token efficiency, task completion) and integrates with the
budget monitoring system.

Maintains a rolling summary per model that is incrementally updated on each
metric recording, avoiding full recomputation. Provides leaderboard ranking,
model comparison, anomaly detection, and trend data for charting.

SQLite-backed with WAL mode. Thread-safe via threading.RLock.
Singleton via get_model_performance(). Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import threading
import time
import uuid
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.monitoring.model_performance")

# ---------------------------------------------------------------------------
# Valid metric types and units
# ---------------------------------------------------------------------------

METRIC_TYPES = {
    "response_time",
    "quality_score",
    "error_rate",
    "token_efficiency",
    "task_completion",
}

UNITS = {
    "ms",
    "score",
    "percent",
    "tokens",
    "ratio",
}

TASK_TYPES = {
    "chat",
    "code_generation",
    "analysis",
    "review",
    "planning",
}


# ---------------------------------------------------------------------------
# Model Performance Tracker
# ---------------------------------------------------------------------------

class ModelPerformanceTracker:
    """Per-model performance tracker backed by SQLite.

    Each metric recording updates an incremental summary row so that
    queries for aggregates (avg, p95, best/worst task) are O(1).

    Thread-safe. Event-emitting. Singleton-capable.
    """

    def __init__(self, db_path: str = ":memory:",
                 event_bus: EventBus | None = None):
        self._db_path = db_path
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
            CREATE TABLE IF NOT EXISTS model_metrics (
                metric_id       TEXT PRIMARY KEY,
                model_id        TEXT NOT NULL,
                metric_type     TEXT NOT NULL,
                value           REAL NOT NULL,
                unit            TEXT NOT NULL,

                task_type       TEXT,
                session_id      TEXT,
                pipeline_run_id TEXT,

                metadata        TEXT,

                created_at      REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS model_performance_summary (
                model_id        TEXT PRIMARY KEY,
                avg_response_time_ms  REAL DEFAULT 0,
                p95_response_time_ms  REAL DEFAULT 0,
                avg_quality_score     REAL DEFAULT 0,
                error_rate            REAL DEFAULT 0,
                total_requests        INTEGER DEFAULT 0,
                successful_requests   INTEGER DEFAULT 0,
                failed_requests       INTEGER DEFAULT 0,

                best_task_type        TEXT,
                worst_task_type       TEXT,

                updated_at      REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_model "
            "ON model_metrics(model_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_type "
            "ON model_metrics(metric_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_model_type "
            "ON model_metrics(model_id, metric_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_created "
            "ON model_metrics(created_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_task "
            "ON model_metrics(task_type)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Record metric
    # ------------------------------------------------------------------

    def record_metric(self, model_id: str, metric_type: str, value: float,
                      unit: str, task_type: str | None = None,
                      session_id: str | None = None,
                      pipeline_run_id: str | None = None,
                      metadata: dict | None = None) -> dict:
        """Record a performance metric for *model_id*.

        Insert the raw metric row and incrementally update the summary.
        Emits ``monitoring.performance.metric_recorded``.
        """
        metric_id = uuid.uuid4().hex
        now = time.time()

        meta_json = json.dumps(metadata) if metadata else None

        with self._lock:
            self._conn.execute("""
                INSERT INTO model_metrics
                    (metric_id, model_id, metric_type, value, unit,
                     task_type, session_id, pipeline_run_id,
                     metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (metric_id, model_id, metric_type, value, unit,
                  task_type, session_id, pipeline_run_id,
                  meta_json, now))

            self._update_summary(model_id, now)
            self._conn.commit()

        result = {
            "metric_id": metric_id,
            "model_id": model_id,
            "metric_type": metric_type,
            "value": value,
            "unit": unit,
            "task_type": task_type,
            "session_id": session_id,
            "pipeline_run_id": pipeline_run_id,
            "recorded_at": now,
        }

        self._emit("monitoring.performance.metric_recorded", result)
        log.info(
            "metric recorded: model=%s type=%s value=%.4f unit=%s task=%s",
            model_id, metric_type, value, unit, task_type,
        )
        return result

    # ------------------------------------------------------------------
    # Incremental summary update
    # ------------------------------------------------------------------

    def _update_summary(self, model_id: str, now: float) -> None:
        """Incrementally update the summary row for *model_id*.

        Must be called while holding ``self._lock``.
        Recomputes aggregates from raw metrics for accuracy (the dataset
        per model is expected to be manageable in size).
        """
        # --- response time aggregates ---
        rt_rows = self._conn.execute(
            "SELECT value FROM model_metrics "
            "WHERE model_id = ? AND metric_type = 'response_time' "
            "ORDER BY value",
            (model_id,),
        ).fetchall()
        rt_values = [r["value"] for r in rt_rows]

        avg_rt = 0.0
        p95_rt = 0.0
        if rt_values:
            avg_rt = sum(rt_values) / len(rt_values)
            idx = int(math.ceil(len(rt_values) * 0.95)) - 1
            idx = max(0, min(idx, len(rt_values) - 1))
            p95_rt = rt_values[idx]

        # --- quality score average ---
        qs_rows = self._conn.execute(
            "SELECT AVG(value) as avg_q FROM model_metrics "
            "WHERE model_id = ? AND metric_type = 'quality_score'",
            (model_id,),
        ).fetchone()
        avg_qs = qs_rows["avg_q"] if qs_rows["avg_q"] is not None else 0.0

        # --- error rate ---
        er_rows = self._conn.execute(
            "SELECT AVG(value) as avg_e FROM model_metrics "
            "WHERE model_id = ? AND metric_type = 'error_rate'",
            (model_id,),
        ).fetchone()
        error_rate = er_rows["avg_e"] if er_rows["avg_e"] is not None else 0.0

        # --- request counts ---
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM model_metrics "
            "WHERE model_id = ? AND metric_type = 'response_time'",
            (model_id,),
        ).fetchone()["cnt"]

        error_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM model_metrics "
            "WHERE model_id = ? AND metric_type = 'error_rate' AND value > 0",
            (model_id,),
        ).fetchone()["cnt"]

        failed = error_count
        successful = total - failed
        if successful < 0:
            successful = 0

        # --- best / worst task type ---
        best_task = self._best_task_type(model_id)
        worst_task = self._worst_task_type(model_id)

        # --- upsert summary ---
        existing = self._conn.execute(
            "SELECT model_id FROM model_performance_summary WHERE model_id = ?",
            (model_id,),
        ).fetchone()

        if existing:
            self._conn.execute("""
                UPDATE model_performance_summary
                SET avg_response_time_ms = ?,
                    p95_response_time_ms = ?,
                    avg_quality_score = ?,
                    error_rate = ?,
                    total_requests = ?,
                    successful_requests = ?,
                    failed_requests = ?,
                    best_task_type = ?,
                    worst_task_type = ?,
                    updated_at = ?
                WHERE model_id = ?
            """, (avg_rt, p95_rt, avg_qs, error_rate,
                  total, successful, failed,
                  best_task, worst_task, now, model_id))
        else:
            self._conn.execute("""
                INSERT INTO model_performance_summary
                    (model_id, avg_response_time_ms, p95_response_time_ms,
                     avg_quality_score, error_rate,
                     total_requests, successful_requests, failed_requests,
                     best_task_type, worst_task_type, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (model_id, avg_rt, p95_rt, avg_qs, error_rate,
                  total, successful, failed,
                  best_task, worst_task, now))

    def _best_task_type(self, model_id: str) -> str | None:
        """Return the task type with the highest average quality score.

        Must be called while holding ``self._lock``.
        """
        row = self._conn.execute(
            "SELECT task_type, AVG(value) as avg_score "
            "FROM model_metrics "
            "WHERE model_id = ? AND metric_type = 'quality_score' "
            "AND task_type IS NOT NULL "
            "GROUP BY task_type "
            "ORDER BY avg_score DESC LIMIT 1",
            (model_id,),
        ).fetchone()
        return row["task_type"] if row else None

    def _worst_task_type(self, model_id: str) -> str | None:
        """Return the task type with the lowest average quality score.

        Must be called while holding ``self._lock``.
        """
        row = self._conn.execute(
            "SELECT task_type, AVG(value) as avg_score "
            "FROM model_metrics "
            "WHERE model_id = ? AND metric_type = 'quality_score' "
            "AND task_type IS NOT NULL "
            "GROUP BY task_type "
            "ORDER BY avg_score ASC LIMIT 1",
            (model_id,),
        ).fetchone()
        return row["task_type"] if row else None

    # ------------------------------------------------------------------
    # Get metrics (filtered query)
    # ------------------------------------------------------------------

    def get_metrics(self, model_id: str | None = None,
                    metric_type: str | None = None,
                    task_type: str | None = None,
                    from_time: float | None = None,
                    to_time: float | None = None,
                    limit: int = 100) -> list[dict]:
        """Return metrics matching the given filters.

        Ordered by created_at descending.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if model_id is not None:
            clauses.append("model_id = ?")
            params.append(model_id)
        if metric_type is not None:
            clauses.append("metric_type = ?")
            params.append(metric_type)
        if task_type is not None:
            clauses.append("task_type = ?")
            params.append(task_type)
        if from_time is not None:
            clauses.append("created_at >= ?")
            params.append(from_time)
        if to_time is not None:
            clauses.append("created_at <= ?")
            params.append(to_time)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (f"SELECT * FROM model_metrics{where} "
               f"ORDER BY created_at DESC LIMIT ?")
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Get model summary
    # ------------------------------------------------------------------

    def get_model_summary(self, model_id: str) -> dict | None:
        """Return the performance summary for *model_id*, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM model_performance_summary WHERE model_id = ?",
                (model_id,),
            ).fetchone()

        if row is None:
            return None
        return dict(row)

    # ------------------------------------------------------------------
    # Get all summaries
    # ------------------------------------------------------------------

    def get_all_summaries(self) -> list[dict]:
        """Return performance summaries for all models."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM model_performance_summary ORDER BY model_id"
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Leaderboard
    # ------------------------------------------------------------------

    def get_leaderboard(self, metric_type: str = "quality_score",
                        task_type: str | None = None,
                        limit: int = 10) -> list[dict]:
        """Rank models by average value of *metric_type*, descending.

        If *task_type* is given, only metrics for that task are considered.
        Returns list of dicts with model_id, avg_value, metric_count.
        """
        clauses: list[str] = ["metric_type = ?"]
        params: list[Any] = [metric_type]

        if task_type is not None:
            clauses.append("task_type = ?")
            params.append(task_type)

        where = " WHERE " + " AND ".join(clauses)

        sql = (f"SELECT model_id, AVG(value) as avg_value, "
               f"COUNT(*) as metric_count "
               f"FROM model_metrics{where} "
               f"GROUP BY model_id "
               f"ORDER BY avg_value DESC LIMIT ?")
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Model comparison
    # ------------------------------------------------------------------

    def get_model_comparison(self, model_ids: list[str],
                             metric_type: str,
                             from_time: float | None = None,
                             to_time: float | None = None) -> list[dict]:
        """Compare models side by side on *metric_type*.

        Returns list of dicts with model_id, avg_value, min_value,
        max_value, metric_count.
        """
        if not model_ids:
            return []

        placeholders = ",".join("?" for _ in model_ids)
        clauses: list[str] = [
            f"model_id IN ({placeholders})",
            "metric_type = ?",
        ]
        params: list[Any] = list(model_ids) + [metric_type]

        if from_time is not None:
            clauses.append("created_at >= ?")
            params.append(from_time)
        if to_time is not None:
            clauses.append("created_at <= ?")
            params.append(to_time)

        where = " WHERE " + " AND ".join(clauses)

        sql = (f"SELECT model_id, "
               f"AVG(value) as avg_value, "
               f"MIN(value) as min_value, "
               f"MAX(value) as max_value, "
               f"COUNT(*) as metric_count "
               f"FROM model_metrics{where} "
               f"GROUP BY model_id "
               f"ORDER BY avg_value DESC")

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Anomaly detection
    # ------------------------------------------------------------------

    def detect_anomalies(self, model_id: str | None = None,
                         window_seconds: float = 3600) -> list[dict]:
        """Find unusual metric values within the last *window_seconds*.

        Detects values that are more than 2 standard deviations from
        the mean for each (model_id, metric_type) pair. If *model_id*
        is given, only that model is checked.

        Returns list of anomaly dicts: model_id, metric_type, metric_id,
        value, mean, std_dev, z_score.
        """
        now = time.time()
        window_start = now - window_seconds

        anomalies: list[dict] = []

        with self._lock:
            # Determine which (model, type) pairs to check
            if model_id is not None:
                pairs = self._conn.execute(
                    "SELECT DISTINCT model_id, metric_type "
                    "FROM model_metrics "
                    "WHERE model_id = ? AND created_at >= ?",
                    (model_id, window_start),
                ).fetchall()
            else:
                pairs = self._conn.execute(
                    "SELECT DISTINCT model_id, metric_type "
                    "FROM model_metrics "
                    "WHERE created_at >= ?",
                    (window_start,),
                ).fetchall()

            for pair in pairs:
                mid = pair["model_id"]
                mtype = pair["metric_type"]

                # Compute mean and std dev for this pair
                stats = self._conn.execute(
                    "SELECT AVG(value) as mean_val, "
                    "       ((SELECT SUM(value*value) FROM model_metrics "
                    "         WHERE model_id = ? AND metric_type = ? "
                    "         AND created_at >= ?)) as sum_sq, "
                    "       COUNT(*) as cnt "
                    "FROM model_metrics "
                    "WHERE model_id = ? AND metric_type = ? "
                    "AND created_at >= ?",
                    (mid, mtype, window_start,
                     mid, mtype, window_start),
                ).fetchone()

                if stats is None or stats["cnt"] < 3:
                    continue

                mean_val = stats["mean_val"]
                cnt = stats["cnt"]
                sum_sq = stats["sum_sq"] if stats["sum_sq"] is not None else 0.0
                variance = (sum_sq / cnt) - (mean_val * mean_val)
                if variance < 0:
                    variance = 0.0
                std_dev = math.sqrt(variance)

                if std_dev < 1e-9:
                    continue

                # Find individual metrics with |z-score| > 2
                metric_rows = self._conn.execute(
                    "SELECT metric_id, value FROM model_metrics "
                    "WHERE model_id = ? AND metric_type = ? "
                    "AND created_at >= ?",
                    (mid, mtype, window_start),
                ).fetchall()

                for mrow in metric_rows:
                    z = (mrow["value"] - mean_val) / std_dev
                    if abs(z) > 2.0:
                        anomalies.append({
                            "model_id": mid,
                            "metric_type": mtype,
                            "metric_id": mrow["metric_id"],
                            "value": mrow["value"],
                            "mean": mean_val,
                            "std_dev": std_dev,
                            "z_score": z,
                        })

        return anomalies

    # ------------------------------------------------------------------
    # Trend data
    # ------------------------------------------------------------------

    def get_trend(self, model_id: str, metric_type: str,
                  hours: float = 24) -> list[dict]:
        """Return time-series data for charting.

        Returns list of dicts with timestamp and value, ordered by
        created_at ascending.
        """
        cutoff = time.time() - (hours * 3600)

        with self._lock:
            rows = self._conn.execute(
                "SELECT created_at as timestamp, value "
                "FROM model_metrics "
                "WHERE model_id = ? AND metric_type = ? "
                "AND created_at >= ? "
                "ORDER BY created_at ASC",
                (model_id, metric_type, cutoff),
            ).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="monitoring.model_performance",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: ModelPerformanceTracker | None = None


def get_model_performance(db_path: str = ":memory:",
                          event_bus: EventBus | None = None
                          ) -> ModelPerformanceTracker:
    """Get or create the global ModelPerformanceTracker singleton."""
    global _instance
    if _instance is None:
        _instance = ModelPerformanceTracker(db_path, event_bus)
    return _instance


def reset_model_performance() -> None:
    """Reset the global singleton (for testing)."""
    global _instance
    _instance = None
