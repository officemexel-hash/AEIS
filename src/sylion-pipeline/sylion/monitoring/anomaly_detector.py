"""
SYLION Monitoring -- Anomaly Detector

Detects anomalies in system metrics and module behavior by establishing
statistical baselines (mean / stddev) from recent observations and flagging
values that deviate beyond configurable thresholds.

Severity levels are determined by how many standard deviations the observed
value strays from the mean:

  low      -- 2-3x stddev
  medium   -- 3-5x stddev
  high     -- 5-10x stddev
  critical -- >10x stddev

An anomaly is only raised when at least 100 observations have been recorded
for a given (metric_name, module_id) pair so the baseline is statistically
meaningful.

SQLite-backed with WAL mode.  Thread-safe via threading.RLock().
Singleton via get_anomaly_detector() / reset_anomaly_detector().
Emits events via EventBus.
"""

from __future__ import annotations

import logging
import math
import sqlite3
import threading
import time
import uuid
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.monitoring.anomaly_detector")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_SAMPLES_FOR_BASELINE: int = 100

VALID_SEVERITIES = ("low", "medium", "high", "critical")
VALID_STATUSES = ("active", "resolved", "ignored")


# ---------------------------------------------------------------------------
# AnomalyDetector
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """Statistical anomaly detection for system metrics and module behaviour.

    Thread-safe.  SQLite-backed.  Emits events on anomaly detection /
    resolution.
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
            CREATE TABLE IF NOT EXISTS observations (
                obs_id      TEXT PRIMARY KEY,
                metric_name TEXT    NOT NULL,
                module_id   TEXT    NOT NULL,
                value       REAL    NOT NULL,
                recorded_at REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS metric_baselines (
                baseline_id   TEXT PRIMARY KEY,
                metric_name   TEXT    NOT NULL,
                module_id     TEXT    NOT NULL,
                mean          REAL    NOT NULL,
                stddev        REAL    NOT NULL,
                sample_count  INTEGER NOT NULL,
                computed_at   REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                anomaly_id     TEXT PRIMARY KEY,
                metric_name    TEXT    NOT NULL,
                module_id      TEXT    NOT NULL,
                observed_value REAL    NOT NULL,
                expected_value REAL    NOT NULL,
                deviation      REAL    NOT NULL,
                severity       TEXT    NOT NULL,
                detected_at    REAL    NOT NULL,
                status         TEXT    NOT NULL DEFAULT 'active'
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_obs_metric_mod "
            "ON observations(metric_name, module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bl_metric_mod "
            "ON metric_baselines(metric_name, module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_anom_module "
            "ON anomalies(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_anom_severity "
            "ON anomalies(severity)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_anom_status "
            "ON anomalies(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_anom_detected "
            "ON anomalies(detected_at)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # record_observation
    # ------------------------------------------------------------------

    def record_observation(self, metric_name: str, module_id: str,
                           value: float) -> dict:
        """Record a metric value, update the baseline, and detect anomalies.

        The anomaly check uses the baseline computed *before* the current
        observation is inserted so that outlier values do not skew the
        comparison mean.

        Returns a dict with keys:
          obs_id, metric_name, module_id, value, anomaly (dict | None)
        """
        obs_id = uuid.uuid4().hex
        now = time.time()

        # Snapshot the current baseline (from prior observations only)
        baseline_before = self.get_baseline(metric_name, module_id)

        # Insert the new observation
        with self._lock:
            self._conn.execute("""
                INSERT INTO observations (obs_id, metric_name, module_id, value, recorded_at)
                VALUES (?, ?, ?, ?, ?)
            """, (obs_id, metric_name, module_id, value, now))
            self._conn.commit()

        # Recompute baseline (now includes the new observation)
        self.compute_baseline(metric_name, module_id)

        # Check for anomaly using the pre-insertion baseline
        anomaly_result = self._check_anomaly(
            metric_name, module_id, value, now, baseline=baseline_before,
        )

        return {
            "obs_id": obs_id,
            "metric_name": metric_name,
            "module_id": module_id,
            "value": value,
            "anomaly": anomaly_result,
        }

    # ------------------------------------------------------------------
    # compute_baseline
    # ------------------------------------------------------------------

    def compute_baseline(self, metric_name: str, module_id: str) -> dict | None:
        """Compute mean and stddev from recent observations.

        Requires at least MIN_SAMPLES_FOR_BASELINE observations to produce
        a meaningful baseline.  Returns the baseline dict or None if there
        are not enough samples.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT value FROM observations "
                "WHERE metric_name = ? AND module_id = ? "
                "ORDER BY recorded_at DESC LIMIT 1000",
                (metric_name, module_id),
            ).fetchall()

        if len(rows) < MIN_SAMPLES_FOR_BASELINE:
            return None

        values = [r["value"] for r in rows]
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        stddev = math.sqrt(variance)

        baseline_id = f"{metric_name}:{module_id}"
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO metric_baselines
                    (baseline_id, metric_name, module_id, mean, stddev,
                     sample_count, computed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (baseline_id, metric_name, module_id, mean, stddev, n, now))
            self._conn.commit()

        log.debug(
            "baseline computed for %s/%s: mean=%.4f stddev=%.4f n=%d",
            metric_name, module_id, mean, stddev, n,
        )
        return {
            "baseline_id": baseline_id,
            "metric_name": metric_name,
            "module_id": module_id,
            "mean": mean,
            "stddev": stddev,
            "sample_count": n,
            "computed_at": now,
        }

    # ------------------------------------------------------------------
    # get_baseline / list_baselines
    # ------------------------------------------------------------------

    def get_baseline(self, metric_name: str, module_id: str) -> dict | None:
        """Retrieve the current baseline for a metric / module pair."""
        baseline_id = f"{metric_name}:{module_id}"
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM metric_baselines WHERE baseline_id = ?",
                (baseline_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_baselines(self, module_id: str | None = None) -> list[dict]:
        """List all baselines, optionally filtered by module_id."""
        with self._lock:
            if module_id:
                rows = self._conn.execute(
                    "SELECT * FROM metric_baselines WHERE module_id = ? ORDER BY computed_at DESC",
                    (module_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM metric_baselines ORDER BY computed_at DESC",
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # get_anomaly / list_anomalies
    # ------------------------------------------------------------------

    def get_anomaly(self, anomaly_id: str) -> dict | None:
        """Retrieve a single anomaly by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM anomalies WHERE anomaly_id = ?",
                (anomaly_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_anomalies(self, module_id: str | None = None,
                       severity: str | None = None,
                       status: str | None = None,
                       limit: int = 100) -> list[dict]:
        """List anomalies with optional filters.

        Results are ordered by detected_at descending.
        """
        with self._lock:
            conditions: list[str] = []
            params: list[Any] = []

            if module_id is not None:
                conditions.append("module_id = ?")
                params.append(module_id)
            if severity is not None:
                conditions.append("severity = ?")
                params.append(severity)
            if status is not None:
                conditions.append("status = ?")
                params.append(status)

            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)

            query = (
                f"SELECT * FROM anomalies {where} "
                f"ORDER BY detected_at DESC LIMIT ?"
            )
            params.append(limit)
            rows = self._conn.execute(query, params).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # resolve_anomaly
    # ------------------------------------------------------------------

    def resolve_anomaly(self, anomaly_id: str) -> bool:
        """Mark an anomaly as resolved.

        Returns True if the anomaly existed and was resolved.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT status FROM anomalies WHERE anomaly_id = ?",
                (anomaly_id,),
            ).fetchone()

            if row is None:
                return False

            self._conn.execute(
                "UPDATE anomalies SET status = 'resolved' WHERE anomaly_id = ?",
                (anomaly_id,),
            )
            self._conn.commit()

        self._emit("anomaly.resolved", {
            "anomaly_id": anomaly_id,
        })
        log.info("anomaly resolved: %s", anomaly_id[:12])
        return True

    # ------------------------------------------------------------------
    # get_stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate anomaly detector statistics.

        Returns dict with:
          total_baselines, total_observations, total_anomalies,
          by_severity, by_metric, by_status
        """
        with self._lock:
            baseline_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM metric_baselines"
            ).fetchone()["cnt"]

            obs_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM observations"
            ).fetchone()["cnt"]

            anomaly_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM anomalies"
            ).fetchone()["cnt"]

            sev_rows = self._conn.execute(
                "SELECT severity, COUNT(*) as cnt FROM anomalies "
                "GROUP BY severity"
            ).fetchall()
            by_severity = {r["severity"]: r["cnt"] for r in sev_rows}

            metric_rows = self._conn.execute(
                "SELECT metric_name, COUNT(*) as cnt FROM anomalies "
                "GROUP BY metric_name ORDER BY cnt DESC"
            ).fetchall()
            by_metric = {r["metric_name"]: r["cnt"] for r in metric_rows}

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM anomalies "
                "GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

        return {
            "total_baselines": baseline_count,
            "total_observations": obs_count,
            "total_anomalies": anomaly_count,
            "by_severity": by_severity,
            "by_metric": by_metric,
            "by_status": by_status,
        }

    # ------------------------------------------------------------------
    # Internal: anomaly check
    # ------------------------------------------------------------------

    def _check_anomaly(self, metric_name: str, module_id: str,
                       value: float, detected_at: float,
                       baseline: dict | None = None) -> dict | None:
        """Check whether *value* is anomalous against the stored baseline.

        If *baseline* is provided, it is used directly (avoids a re-read
        and lets callers pass a snapshot taken before the observation was
        inserted).  Otherwise the current stored baseline is read.

        Returns an anomaly dict if an anomaly was detected, else None.
        """
        if baseline is None:
            baseline = self.get_baseline(metric_name, module_id)
        if baseline is None:
            return None

        mean = baseline["mean"]
        stddev = baseline["stddev"]

        # Avoid division by zero for constant-value metrics
        if stddev == 0.0:
            if value == mean:
                return None
            # Everything is anomalous if stddev is zero and value differs
            deviation_multiple = float("inf")
        else:
            deviation_multiple = abs(value - mean) / stddev

        if deviation_multiple <= 2.0:
            return None

        severity = self._classify_severity(deviation_multiple)
        anomaly_id = uuid.uuid4().hex
        deviation = abs(value - mean)

        with self._lock:
            self._conn.execute("""
                INSERT INTO anomalies
                    (anomaly_id, metric_name, module_id, observed_value,
                     expected_value, deviation, severity, detected_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """, (
                anomaly_id, metric_name, module_id, value,
                mean, deviation, severity, detected_at,
            ))
            self._conn.commit()

        self._emit("anomaly.detected", {
            "anomaly_id": anomaly_id,
            "metric_name": metric_name,
            "module_id": module_id,
            "severity": severity,
            "observed_value": value,
            "expected_value": mean,
            "deviation_multiple": round(deviation_multiple, 4),
        })
        log.warning(
            "anomaly detected: %s/%s value=%.4f expected=%.4f "
            "deviation=%.2fx severity=%s",
            metric_name, module_id, value, mean,
            deviation_multiple, severity,
        )
        return {
            "anomaly_id": anomaly_id,
            "metric_name": metric_name,
            "module_id": module_id,
            "observed_value": value,
            "expected_value": mean,
            "deviation": deviation,
            "deviation_multiple": round(deviation_multiple, 4),
            "severity": severity,
            "detected_at": detected_at,
            "status": "active",
        }

    # ------------------------------------------------------------------
    # Internal: severity classification
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_severity(deviation_multiple: float) -> str:
        """Classify anomaly severity based on deviation in stddev multiples."""
        if deviation_multiple > 10.0:
            return "critical"
        if deviation_multiple > 5.0:
            return "high"
        if deviation_multiple > 3.0:
            return "medium"
        return "low"

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="monitoring.anomaly_detector",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: AnomalyDetector | None = None


def get_anomaly_detector(db_path: str | None = None,
                         event_bus: EventBus | None = None) -> AnomalyDetector:
    """Get or create the global AnomalyDetector singleton."""
    global _instance
    if _instance is None:
        _instance = AnomalyDetector(db_path, event_bus)
    return _instance


def reset_anomaly_detector() -> None:
    """Reset the global singleton (for testing)."""
    global _instance
    _instance = None
