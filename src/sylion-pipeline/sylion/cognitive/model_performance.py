"""
SYLION Cognitive -- Model Performance Tracker

Tracks LLM model performance metrics across calls: accuracy, latency,
cost, token usage. Computes periodic summaries and maintains a ranked
leaderboard.

SQLite-backed with WAL mode. Thread-safe via threading.RLock.
Singleton via get_model_performance_tracker()/reset_model_performance_tracker().
Emits events via EventBus.

Tables:
  model_metrics      -- individual metric observations per model call
  model_summaries    -- precomputed period summaries (hourly/daily/weekly/monthly)
  model_leaderboard  -- ranked model entries by metric type
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

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.cognitive.model_performance")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_METRIC_TYPES = ("accuracy", "latency", "cost", "tokens", "overall")
VALID_PERIODS = ("hourly", "daily", "weekly", "monthly")


# ---------------------------------------------------------------------------
# ModelPerformanceTracker
# ---------------------------------------------------------------------------

class ModelPerformanceTracker:
    """LLM model performance tracker backed by SQLite.

    Records per-call metrics, computes period summaries, and maintains a
    leaderboard ranking models by metric type.

    Thread-safe via threading.RLock. SQLite-backed with WAL mode.
    Emits events on metric recording and leaderboard updates.
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

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS model_metrics (
                metric_id    TEXT PRIMARY KEY,
                model_id     TEXT NOT NULL,
                metric_type  TEXT NOT NULL,
                metric_value REAL NOT NULL,
                tokens_used  INTEGER NOT NULL DEFAULT 0,
                latency_ms   REAL NOT NULL DEFAULT 0.0,
                timestamp    REAL NOT NULL,
                metadata     TEXT
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS model_summaries (
                summary_id  TEXT PRIMARY KEY,
                model_id    TEXT NOT NULL,
                period      TEXT NOT NULL,
                avg_latency REAL NOT NULL DEFAULT 0.0,
                avg_score   REAL NOT NULL DEFAULT 0.0,
                total_calls INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                total_cost  REAL NOT NULL DEFAULT 0.0,
                computed_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS model_leaderboard (
                entry_id    TEXT PRIMARY KEY,
                model_id    TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                rank        INTEGER NOT NULL,
                score       REAL NOT NULL DEFAULT 0.0,
                updated_at  REAL NOT NULL
            )
        """)

        # Indexes
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mp_metrics_model "
            "ON model_metrics(model_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mp_metrics_type "
            "ON model_metrics(metric_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mp_metrics_model_type "
            "ON model_metrics(model_id, metric_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mp_metrics_ts "
            "ON model_metrics(timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mp_sum_model_period "
            "ON model_summaries(model_id, period)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mp_sum_period "
            "ON model_summaries(period)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mp_lb_type "
            "ON model_leaderboard(metric_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mp_lb_model_type "
            "ON model_leaderboard(model_id, metric_type)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:16]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="cognitive.model_performance",
            ))

    # ------------------------------------------------------------------
    # Record metric
    # ------------------------------------------------------------------

    def record_metric(
        self,
        model_id: str,
        metric_type: str,
        metric_value: float,
        tokens_used: int = 0,
        latency_ms: float = 0.0,
        metadata: dict | None = None,
    ) -> dict:
        """Record a performance metric for *model_id*.

        Parameters
        ----------
        model_id : str
            Identifier of the model.
        metric_type : str
            One of VALID_METRIC_TYPES.
        metric_value : float
            Numeric value of the metric.
        tokens_used : int
            Tokens consumed in the call.
        latency_ms : float
            Call latency in milliseconds.
        metadata : dict | None
            Optional extra metadata stored as JSON.

        Returns
        -------
        dict with metric_id, model_id, metric_type, metric_value,
        tokens_used, latency_ms, timestamp.

        Raises
        ------
        ValueError
            If metric_type is not in VALID_METRIC_TYPES.
        """
        if metric_type not in VALID_METRIC_TYPES:
            raise ValueError(
                f"Invalid metric_type '{metric_type}', "
                f"must be one of {VALID_METRIC_TYPES}"
            )

        metric_id = self._uid()
        now = time.time()
        meta_json = json.dumps(metadata) if metadata else None

        with self._lock:
            self._conn.execute("""
                INSERT INTO model_metrics
                    (metric_id, model_id, metric_type, metric_value,
                     tokens_used, latency_ms, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric_id, model_id, metric_type, metric_value,
                tokens_used, latency_ms, now, meta_json,
            ))
            self._conn.commit()

        result = {
            "metric_id": metric_id,
            "model_id": model_id,
            "metric_type": metric_type,
            "metric_value": metric_value,
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
            "timestamp": now,
            "metadata": metadata,
        }

        self._emit("performance.metric_recorded", {
            "metric_id": metric_id,
            "model_id": model_id,
            "metric_type": metric_type,
            "metric_value": metric_value,
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
        })
        log.info(
            "metric recorded: model=%s type=%s value=%.4f tokens=%d latency=%.1fms",
            model_id, metric_type, metric_value, tokens_used, latency_ms,
        )
        return result

    # ------------------------------------------------------------------
    # Get metrics (filtered query)
    # ------------------------------------------------------------------

    def get_metrics(
        self,
        model_id: str | None = None,
        metric_type: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Return metrics matching the given filters.

        Ordered by timestamp descending.

        Parameters
        ----------
        model_id : str | None
            Filter by model identifier.
        metric_type : str | None
            Filter by metric type.
        since : float | None
            Only metrics with timestamp >= since.
        limit : int
            Maximum number of results.

        Returns
        -------
        list of dicts representing metric rows.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if model_id is not None:
            clauses.append("model_id = ?")
            params.append(model_id)
        if metric_type is not None:
            clauses.append("metric_type = ?")
            params.append(metric_type)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            f"SELECT * FROM model_metrics{where} "
            f"ORDER BY timestamp DESC LIMIT ?"
        )
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            if d.get("metadata") is not None:
                try:
                    d["metadata"] = json.loads(d["metadata"])
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Compute summary
    # ------------------------------------------------------------------

    def compute_summary(
        self,
        model_id: str,
        period: str = "daily",
    ) -> dict:
        """Compute and store a summary for *model_id* over the given period.

        Parameters
        ----------
        model_id : str
            Model to summarise.
        period : str
            One of VALID_PERIODS.

        Returns
        -------
        dict with summary fields.

        Raises
        ------
        ValueError
            If period is not in VALID_PERIODS.
        """
        if period not in VALID_PERIODS:
            raise ValueError(
                f"Invalid period '{period}', must be one of {VALID_PERIODS}"
            )

        now = time.time()
        period_seconds = {
            "hourly": 3600,
            "daily": 86400,
            "weekly": 604800,
            "monthly": 2592000,
        }
        cutoff = now - period_seconds[period]

        with self._lock:
            # Aggregate metrics in the period window
            agg = self._conn.execute(
                "SELECT "
                "  AVG(latency_ms) as avg_latency, "
                "  AVG(metric_value) as avg_score, "
                "  COUNT(*) as total_calls, "
                "  SUM(tokens_used) as total_tokens, "
                "  SUM(metric_value) as total_cost "
                "FROM model_metrics "
                "WHERE model_id = ? AND timestamp >= ?",
                (model_id, cutoff),
            ).fetchone()

            avg_latency = agg["avg_latency"] or 0.0
            avg_score = agg["avg_score"] or 0.0
            total_calls = agg["total_calls"] or 0
            total_tokens = agg["total_tokens"] or 0
            # For cost, use metric_value where metric_type == 'cost'
            cost_row = self._conn.execute(
                "SELECT SUM(metric_value) as total_cost "
                "FROM model_metrics "
                "WHERE model_id = ? AND metric_type = 'cost' "
                "AND timestamp >= ?",
                (model_id, cutoff),
            ).fetchone()
            total_cost = cost_row["total_cost"] or 0.0

            summary_id = self._uid()

            # Insert new summary (keep historical records)
            self._conn.execute("""
                INSERT INTO model_summaries
                    (summary_id, model_id, period, avg_latency, avg_score,
                     total_calls, total_tokens, total_cost, computed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                summary_id, model_id, period,
                round(avg_latency, 4), round(avg_score, 6),
                total_calls, total_tokens, round(total_cost, 6), now,
            ))
            self._conn.commit()

        result = {
            "summary_id": summary_id,
            "model_id": model_id,
            "period": period,
            "avg_latency": round(avg_latency, 4),
            "avg_score": round(avg_score, 6),
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 6),
            "computed_at": now,
        }
        log.info(
            "computed %s summary for %s: calls=%d avg_latency=%.1f avg_score=%.4f",
            period, model_id, total_calls, avg_latency, avg_score,
        )
        return result

    # ------------------------------------------------------------------
    # Get latest summary
    # ------------------------------------------------------------------

    def get_summary(
        self,
        model_id: str,
        period: str = "daily",
    ) -> dict | None:
        """Get the latest summary for *model_id* and *period*.

        Returns None if no summary exists.
        """
        if period not in VALID_PERIODS:
            raise ValueError(
                f"Invalid period '{period}', must be one of {VALID_PERIODS}"
            )

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM model_summaries "
                "WHERE model_id = ? AND period = ? "
                "ORDER BY computed_at DESC LIMIT 1",
                (model_id, period),
            ).fetchone()

        return dict(row) if row else None

    # ------------------------------------------------------------------
    # List summaries
    # ------------------------------------------------------------------

    def list_summaries(
        self,
        period: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List summaries, optionally filtered by period.

        Returns the most recent summary per (model_id, period), ordered by
        computed_at descending.
        """
        with self._lock:
            if period is not None:
                rows = self._conn.execute(
                    "SELECT * FROM model_summaries "
                    "WHERE period = ? "
                    "ORDER BY computed_at DESC LIMIT ?",
                    (period, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM model_summaries "
                    "ORDER BY computed_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Update leaderboard
    # ------------------------------------------------------------------

    def update_leaderboard(self, metric_type: str = "overall") -> list[dict]:
        """Recompute and store leaderboard rankings for *metric_type*.

        Deletes old entries for the given metric_type, computes new rankings
        from model_metrics, and inserts fresh leaderboard rows.

        Emits ``performance.leaderboard_updated``.

        Parameters
        ----------
        metric_type : str
            One of VALID_METRIC_TYPES. ``overall`` uses all metric types.

        Returns
        -------
        list of leaderboard entry dicts ordered by rank.
        """
        if metric_type not in VALID_METRIC_TYPES:
            raise ValueError(
                f"Invalid metric_type '{metric_type}', "
                f"must be one of {VALID_METRIC_TYPES}"
            )

        now = time.time()

        with self._lock:
            # Clear old entries for this metric_type
            self._conn.execute(
                "DELETE FROM model_leaderboard WHERE metric_type = ?",
                (metric_type,),
            )

            # Compute average metric_value per model
            if metric_type == "overall":
                rows = self._conn.execute(
                    "SELECT model_id, AVG(metric_value) as score "
                    "FROM model_metrics "
                    "GROUP BY model_id "
                    "ORDER BY score DESC"
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT model_id, AVG(metric_value) as score "
                    "FROM model_metrics "
                    "WHERE metric_type = ? "
                    "GROUP BY model_id "
                    "ORDER BY score DESC",
                    (metric_type,),
                ).fetchall()

            entries = []
            for rank, row in enumerate(rows, start=1):
                entry_id = self._uid()
                self._conn.execute("""
                    INSERT INTO model_leaderboard
                        (entry_id, model_id, metric_type, rank, score, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (entry_id, row["model_id"], metric_type, rank,
                      round(row["score"], 6), now))
                entries.append({
                    "entry_id": entry_id,
                    "model_id": row["model_id"],
                    "metric_type": metric_type,
                    "rank": rank,
                    "score": round(row["score"], 6),
                    "updated_at": now,
                })

            self._conn.commit()

        self._emit("performance.leaderboard_updated", {
            "metric_type": metric_type,
            "entries_count": len(entries),
        })
        log.info(
            "updated leaderboard for %s: %d models ranked",
            metric_type, len(entries),
        )
        return entries

    # ------------------------------------------------------------------
    # Get leaderboard
    # ------------------------------------------------------------------

    def get_leaderboard(
        self,
        metric_type: str = "overall",
    ) -> list[dict]:
        """Get current leaderboard rankings for *metric_type*.

        Returns list of entry dicts ordered by rank ascending.
        """
        if metric_type not in VALID_METRIC_TYPES:
            raise ValueError(
                f"Invalid metric_type '{metric_type}', "
                f"must be one of {VALID_METRIC_TYPES}"
            )

        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM model_leaderboard "
                "WHERE metric_type = ? "
                "ORDER BY rank ASC",
                (metric_type,),
            ).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Aggregate stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Aggregate statistics across all models.

        Returns total metrics, unique models, total tokens, total cost,
        average latency, average score, and per-model breakdown.
        """
        with self._lock:
            agg = self._conn.execute("""
                SELECT
                    COUNT(*) as total_metrics,
                    COUNT(DISTINCT model_id) as unique_models,
                    SUM(tokens_used) as total_tokens,
                    AVG(latency_ms) as avg_latency,
                    AVG(metric_value) as avg_score
                FROM model_metrics
            """).fetchone()

            cost_row = self._conn.execute(
                "SELECT SUM(metric_value) as total_cost "
                "FROM model_metrics WHERE metric_type = 'cost'"
            ).fetchone()

            # Per-model breakdown
            model_rows = self._conn.execute("""
                SELECT
                    model_id,
                    COUNT(*) as metric_count,
                    AVG(latency_ms) as avg_latency,
                    AVG(metric_value) as avg_score,
                    SUM(tokens_used) as total_tokens
                FROM model_metrics
                GROUP BY model_id
                ORDER BY model_id
            """).fetchall()

        total_metrics = agg["total_metrics"] or 0
        unique_models = agg["unique_models"] or 0
        total_tokens = agg["total_tokens"] or 0
        avg_latency = agg["avg_latency"] or 0.0
        avg_score = agg["avg_score"] or 0.0
        total_cost = cost_row["total_cost"] or 0.0 if cost_row else 0.0

        by_model: dict[str, dict[str, Any]] = {}
        for r in model_rows:
            mid = r["model_id"]
            by_model[mid] = {
                "metric_count": r["metric_count"],
                "avg_latency": round(r["avg_latency"] or 0.0, 4),
                "avg_score": round(r["avg_score"] or 0.0, 6),
                "total_tokens": r["total_tokens"] or 0,
            }

        return {
            "total_metrics": total_metrics,
            "unique_models": unique_models,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 6),
            "avg_latency": round(avg_latency, 4),
            "avg_score": round(avg_score, 6),
            "by_model": by_model,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_tracker: ModelPerformanceTracker | None = None


def get_model_performance_tracker(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ModelPerformanceTracker:
    """Get or create the global ModelPerformanceTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = ModelPerformanceTracker(db_path=db_path, event_bus=event_bus)
    return _tracker


def reset_model_performance_tracker(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ModelPerformanceTracker:
    """Reset the global singleton. Returns a fresh instance."""
    global _tracker
    _tracker = ModelPerformanceTracker(db_path=db_path, event_bus=event_bus)
    return _tracker
