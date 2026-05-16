"""
SYLION Skills -- SkillDemandAnalyzer

Analyses demand for skills based on recorded demand signals.
Tracks signal scores per skill, computes trending, gap analysis,
and simple linear demand prediction.

SQLite-backed. Thread-safe. Singleton. Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.skills.demand_analyzer")


# ---------------------------------------------------------------------------
# SkillDemandAnalyzer
# ---------------------------------------------------------------------------

class SkillDemandAnalyzer:
    """Analyse skill demand from accumulated signals.

    Thread-safe. SQLite-backed. Emits events on record and analysis.
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

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_demand_signals (
                signal_id    TEXT PRIMARY KEY,
                skill_id     TEXT    NOT NULL,
                source       TEXT    NOT NULL DEFAULT '',
                demand_score REAL    NOT NULL DEFAULT 0.0,
                context      TEXT    NOT NULL DEFAULT '{}',
                recorded_at  REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_skill_demand (
                skill_id       TEXT PRIMARY KEY,
                total_score    REAL    NOT NULL DEFAULT 0.0,
                signal_count   INTEGER NOT NULL DEFAULT 0,
                avg_score      REAL    NOT NULL DEFAULT 0.0,
                first_seen     REAL    NOT NULL DEFAULT 0.0,
                last_seen      REAL    NOT NULL DEFAULT 0.0,
                published_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ds_skill ON sylion_demand_signals(skill_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ds_source ON sylion_demand_signals(source)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ds_recorded ON sylion_demand_signals(recorded_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sd_score ON sylion_skill_demand(total_score DESC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sd_last ON sylion_skill_demand(last_seen DESC)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Record a signal
    # ------------------------------------------------------------------

    def record_signal(self, skill_id: str, source: str = "",
                      demand_score: float = 1.0,
                      context: dict | None = None) -> dict:
        """Record a demand signal for *skill_id*.

        Updates both ``sylion_demand_signals`` (append) and
        ``sylion_skill_demand`` (upsert aggregate).

        Emits ``skill.demand.signal_recorded``.
        """
        if context is None:
            context = {}
        now = time.time()
        signal_id = f"{skill_id}:{source}:{now:.6f}"

        with self._lock:
            # Append signal
            self._conn.execute("""
                INSERT INTO sylion_demand_signals
                    (signal_id, skill_id, source, demand_score, context, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                signal_id, skill_id, source, demand_score,
                json.dumps(context, default=str), now,
            ))

            # Upsert aggregate using a single atomic statement
            # First try to update; if no row exists, insert.
            updated = self._conn.execute("""
                UPDATE sylion_skill_demand
                SET total_score = total_score + ?,
                    signal_count = signal_count + 1,
                    avg_score = (total_score + ?) / (signal_count + 1),
                    last_seen = ?
                WHERE skill_id = ?
            """, (demand_score, demand_score, now, skill_id)).rowcount

            if updated == 0:
                self._conn.execute("""
                    INSERT INTO sylion_skill_demand
                        (skill_id, total_score, signal_count, avg_score,
                         first_seen, last_seen, published_count)
                    VALUES (?, ?, 1, ?, ?, ?, 0)
                """, (skill_id, demand_score, demand_score, now, now))

            self._conn.commit()

        self._emit("skill.demand.signal_recorded", {
            "skill_id": skill_id,
            "source": source,
            "demand_score": demand_score,
        })

        log.info("recorded demand signal for %s from %s (score=%.2f)",
                 skill_id, source, demand_score)
        return {
            "signal_id": signal_id,
            "skill_id": skill_id,
            "demand_score": demand_score,
        }

    # ------------------------------------------------------------------
    # Aggregated demand for a single skill
    # ------------------------------------------------------------------

    def get_demand(self, skill_id: str) -> dict | None:
        """Return aggregated demand for *skill_id*, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sylion_skill_demand WHERE skill_id = ?",
                (skill_id,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    # ------------------------------------------------------------------
    # Trending skills
    # ------------------------------------------------------------------

    def get_trending_skills(self, limit: int = 10) -> list[dict]:
        """Skills with highest demand growth (recent vs older signals).

        Compares signal count in the last 7 days to the prior 7 days.
        Returns skills sorted by growth rate descending.
        """
        now = time.time()
        seven_days = 7 * 86400
        recent_start = now - seven_days
        older_start = now - 2 * seven_days

        with self._lock:
            rows = self._conn.execute("""
                SELECT
                    recent.skill_id,
                    COALESCE(recent.cnt, 0) AS recent_count,
                    COALESCE(older.cnt, 0)  AS older_count,
                    COALESCE(recent.sum_score, 0.0) AS recent_score,
                    COALESCE(older.sum_score, 0.0)   AS older_score
                FROM (
                    SELECT skill_id, COUNT(*) AS cnt, SUM(demand_score) AS sum_score
                    FROM sylion_demand_signals
                    WHERE recorded_at >= ?
                    GROUP BY skill_id
                ) recent
                LEFT JOIN (
                    SELECT skill_id, COUNT(*) AS cnt, SUM(demand_score) AS sum_score
                    FROM sylion_demand_signals
                    WHERE recorded_at >= ? AND recorded_at < ?
                    GROUP BY skill_id
                ) older ON recent.skill_id = older.skill_id
                ORDER BY (COALESCE(recent.cnt, 0) - COALESCE(older.cnt, 0)) DESC
                LIMIT ?
            """, (recent_start, older_start, recent_start, limit)).fetchall()

        results = []
        for r in rows:
            recent_c = r["recent_count"]
            older_c = r["older_count"]
            growth = recent_c - older_c
            growth_rate = (growth / older_c) if older_c > 0 else float("inf")
            results.append({
                "skill_id": r["skill_id"],
                "recent_count": recent_c,
                "older_count": older_c,
                "growth": growth,
                "growth_rate": round(growth_rate, 4),
                "recent_score": round(r["recent_score"], 4),
                "older_score": round(r["older_score"], 4),
            })
        return results

    # ------------------------------------------------------------------
    # Gap analysis
    # ------------------------------------------------------------------

    def get_gap_analysis(self) -> list[dict]:
        """Skills with high demand but low supply (published_count).

        Returns list sorted by (demand_score / max(published_count,1)) desc.
        """
        with self._lock:
            rows = self._conn.execute("""
                SELECT skill_id, total_score, signal_count, avg_score,
                       published_count
                FROM sylion_skill_demand
                ORDER BY (total_score / MAX(published_count, 1)) DESC
            """).fetchall()

        results = []
        for r in rows:
            pub = r["published_count"]
            gap_ratio = r["total_score"] / max(pub, 1)
            results.append({
                "skill_id": r["skill_id"],
                "total_score": round(r["total_score"], 4),
                "signal_count": r["signal_count"],
                "avg_score": round(r["avg_score"], 4),
                "published_count": pub,
                "gap_ratio": round(gap_ratio, 4),
            })
        return results

    # ------------------------------------------------------------------
    # Set published count (used by gap analysis)
    # ------------------------------------------------------------------

    def set_published_count(self, skill_id: str, count: int):
        """Set published_count for a skill (used in gap analysis)."""
        with self._lock:
            self._conn.execute(
                "UPDATE sylion_skill_demand SET published_count = ? WHERE skill_id = ?",
                (count, skill_id),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Simple linear demand prediction
    # ------------------------------------------------------------------

    def predict_demand(self, skill_id: str, horizon_days: int = 30) -> dict:
        """Simple linear prediction based on recent signals.

        Fits a line through daily signal counts and extrapolates.
        Returns predicted total score for the next *horizon_days*.
        """
        now = time.time()
        window_days = 30
        window_start = now - window_days * 86400

        with self._lock:
            rows = self._conn.execute(
                "SELECT recorded_at, demand_score FROM sylion_demand_signals "
                "WHERE skill_id = ? AND recorded_at >= ? ORDER BY recorded_at",
                (skill_id, window_start),
            ).fetchall()

        if not rows:
            return {
                "skill_id": skill_id,
                "horizon_days": horizon_days,
                "predicted_score": 0.0,
                "current_daily_avg": 0.0,
                "slope": 0.0,
                "data_points": 0,
            }

        # Bucket by day
        day_buckets: dict[int, float] = {}
        for r in rows:
            day = int((r["recorded_at"] - window_start) / 86400)
            day_buckets[day] = day_buckets.get(day, 0) + r["demand_score"]

        if not day_buckets:
            return {
                "skill_id": skill_id,
                "horizon_days": horizon_days,
                "predicted_score": 0.0,
                "current_daily_avg": 0.0,
                "slope": 0.0,
                "data_points": len(rows),
            }

        # Simple linear regression: y = a + b*x
        # x = day index, y = daily score
        xs = sorted(day_buckets.keys())
        ys = [day_buckets[x] for x in xs]
        n = len(xs)

        if n == 1:
            predicted = ys[0] * horizon_days
            return {
                "skill_id": skill_id,
                "horizon_days": horizon_days,
                "predicted_score": round(predicted, 4),
                "current_daily_avg": round(ys[0], 4),
                "slope": 0.0,
                "data_points": len(rows),
            }

        sum_x = sum(xs)
        sum_y = sum(ys)
        sum_xy = sum(x * y for x, y in zip(xs, ys))
        sum_x2 = sum(x * x for x in xs)

        denom = n * sum_x2 - sum_x * sum_x
        if denom == 0:
            slope = 0.0
            intercept = sum_y / n
        else:
            slope = (n * sum_xy - sum_x * sum_y) / denom
            intercept = (sum_y - slope * sum_x) / n

        # Predict for horizon_days starting after last data point
        last_day = max(xs)
        future_days = list(range(last_day + 1, last_day + 1 + horizon_days))
        predicted = sum(intercept + slope * d for d in future_days)
        predicted = max(predicted, 0.0)

        current_daily_avg = sum_y / n

        return {
            "skill_id": skill_id,
            "horizon_days": horizon_days,
            "predicted_score": round(predicted, 4),
            "current_daily_avg": round(current_daily_avg, 4),
            "slope": round(slope, 4),
            "data_points": len(rows),
        }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate demand analyzer statistics."""
        with self._lock:
            total_signals = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM sylion_demand_signals"
            ).fetchone()["cnt"]

            unique_skills = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM sylion_skill_demand"
            ).fetchone()["cnt"]

            avg_row = self._conn.execute(
                "SELECT COALESCE(AVG(avg_score), 0.0) AS avg FROM sylion_skill_demand"
            ).fetchone()
            avg_demand = avg_row["avg"]

            by_source_rows = self._conn.execute(
                "SELECT source, COUNT(*) AS cnt, SUM(demand_score) AS total "
                "FROM sylion_demand_signals GROUP BY source"
            ).fetchall()
            by_source = {r["source"]: {"count": r["cnt"], "total_score": r["total"]}
                         for r in by_source_rows}

            total_score_row = self._conn.execute(
                "SELECT COALESCE(SUM(total_score), 0.0) AS total FROM sylion_skill_demand"
            ).fetchone()
            total_demand_score = total_score_row["total"]

        return {
            "total_signals": total_signals,
            "unique_skills": unique_skills,
            "average_demand": round(avg_demand, 4),
            "total_demand_score": round(total_demand_score, 4),
            "by_source": by_source,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="skills.demand_analyzer",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_analyzer: SkillDemandAnalyzer | None = None


def get_skill_demand_analyzer(db_path: str | Path | None = None,
                              event_bus: EventBus | None = None) -> SkillDemandAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SkillDemandAnalyzer(db_path, event_bus)
    return _analyzer
