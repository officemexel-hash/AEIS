"""
SYLION Monitoring -- Pipeline Monitor

Tracks pipeline execution health: runs, metrics, and alerts.
SQLite-backed, thread-safe.

Tables:
  - pipeline_runs: individual pipeline run records
  - pipeline_metrics: numeric metrics per run
  - pipeline_alerts: alerts for pipeline health issues
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

log = logging.getLogger("sylion.monitoring.pipeline_monitor")


class PipelineMonitor:
    """Tracks pipeline execution health. SQLite-backed, thread-safe."""

    def __init__(self, db_path: str | Path | None = None, event_bus: Any = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id      TEXT PRIMARY KEY,
                pipeline_id TEXT NOT NULL,
                config_json TEXT NOT NULL DEFAULT '{}',
                status      TEXT NOT NULL DEFAULT 'running',
                result_json TEXT,
                started_at  REAL NOT NULL,
                ended_at    REAL
            );

            CREATE TABLE IF NOT EXISTS pipeline_metrics (
                metric_id    TEXT PRIMARY KEY,
                run_id       TEXT NOT NULL,
                metric_name  TEXT NOT NULL,
                value        REAL NOT NULL,
                created_at   REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pipeline_alerts (
                alert_id      TEXT PRIMARY KEY,
                pipeline_id   TEXT NOT NULL,
                alert_type    TEXT NOT NULL,
                message       TEXT NOT NULL,
                acknowledged  INTEGER NOT NULL DEFAULT 0,
                created_at    REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pr_pipeline
                ON pipeline_runs(pipeline_id);
            CREATE INDEX IF NOT EXISTS idx_pr_status
                ON pipeline_runs(status);
            CREATE INDEX IF NOT EXISTS idx_pm_run
                ON pipeline_metrics(run_id);
            CREATE INDEX IF NOT EXISTS idx_pm_name
                ON pipeline_metrics(metric_name);
            CREATE INDEX IF NOT EXISTS idx_pa_pipeline
                ON pipeline_alerts(pipeline_id);
            CREATE INDEX IF NOT EXISTS idx_pa_ack
                ON pipeline_alerts(acknowledged);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def start_run(self, pipeline_id: str, config_json: str = "{}") -> dict:
        run_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO pipeline_runs
                    (run_id, pipeline_id, config_json, status, result_json, started_at, ended_at)
                VALUES (?, ?, ?, 'running', NULL, ?, NULL)
            """, (run_id, pipeline_id, config_json, now))
            self._conn.commit()

        self._emit("pipeline.run_started", {
            "run_id": run_id, "pipeline_id": pipeline_id,
        })
        log.info("pipeline run %s started for %s", run_id[:12], pipeline_id)
        return {
            "run_id": run_id,
            "pipeline_id": pipeline_id,
            "config_json": config_json,
            "status": "running",
            "started_at": now,
        }

    def end_run(self, run_id: str, status: str = "completed",
                result_json: str | None = None) -> dict | None:
        now = time.time()

        with self._lock:
            n = self._conn.execute("""
                UPDATE pipeline_runs
                SET status = ?, result_json = ?, ended_at = ?
                WHERE run_id = ?
            """, (status, result_json, now, run_id)).rowcount
            self._conn.commit()

        if not n:
            return None

        self._emit("pipeline.run_completed", {
            "run_id": run_id, "status": status,
        })
        log.info("pipeline run %s ended with status %s", run_id[:12], status)
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM pipeline_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_runs(self, pipeline_id: str | None = None,
                  status: str | None = None) -> list[dict]:
        conds: list[str] = []
        params: list[Any] = []
        if pipeline_id:
            conds.append("pipeline_id = ?")
            params.append(pipeline_id)
        if status:
            conds.append("status = ?")
            params.append(status)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM pipeline_runs{where} ORDER BY started_at DESC",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def record_metric(self, run_id: str, metric_name: str,
                      value: float) -> dict:
        metric_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO pipeline_metrics
                    (metric_id, run_id, metric_name, value, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (metric_id, run_id, metric_name, value, now))
            self._conn.commit()

        self._emit("pipeline.metric_recorded", {
            "metric_id": metric_id, "run_id": run_id,
            "metric_name": metric_name, "value": value,
        })
        return {
            "metric_id": metric_id,
            "run_id": run_id,
            "metric_name": metric_name,
            "value": value,
            "created_at": now,
        }

    def get_metrics(self, run_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM pipeline_metrics WHERE run_id = ? ORDER BY created_at DESC",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def create_alert(self, pipeline_id: str, alert_type: str,
                     message: str) -> dict:
        alert_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO pipeline_alerts
                    (alert_id, pipeline_id, alert_type, message, acknowledged, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
            """, (alert_id, pipeline_id, alert_type, message, now))
            self._conn.commit()

        self._emit("pipeline.alert_created", {
            "alert_id": alert_id, "pipeline_id": pipeline_id,
            "alert_type": alert_type,
        })
        log.warning("pipeline alert %s: [%s] %s", alert_id[:12], alert_type, message)
        return {
            "alert_id": alert_id,
            "pipeline_id": pipeline_id,
            "alert_type": alert_type,
            "message": message,
            "acknowledged": 0,
            "created_at": now,
        }

    def list_alerts(self, pipeline_id: str | None = None,
                    acknowledged: bool | None = None) -> list[dict]:
        conds: list[str] = []
        params: list[Any] = []
        if pipeline_id:
            conds.append("pipeline_id = ?")
            params.append(pipeline_id)
        if acknowledged is not None:
            conds.append("acknowledged = ?")
            params.append(1 if acknowledged else 0)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM pipeline_alerts{where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def acknowledge_alert(self, alert_id: str) -> dict | None:
        with self._lock:
            n = self._conn.execute(
                "UPDATE pipeline_alerts SET acknowledged = 1 WHERE alert_id = ?",
                (alert_id,),
            ).rowcount
            self._conn.commit()
        if not n:
            return None
        return {"alert_id": alert_id, "acknowledged": 1}

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_pipeline_stats(self) -> dict:
        with self._lock:
            total_runs = self._conn.execute(
                "SELECT COUNT(*) as c FROM pipeline_runs"
            ).fetchone()["c"]
            completed_runs = self._conn.execute(
                "SELECT COUNT(*) as c FROM pipeline_runs WHERE status = 'completed'"
            ).fetchone()["c"]
            failed_runs = self._conn.execute(
                "SELECT COUNT(*) as c FROM pipeline_runs WHERE status = 'failed'"
            ).fetchone()["c"]
            running_runs = self._conn.execute(
                "SELECT COUNT(*) as c FROM pipeline_runs WHERE status = 'running'"
            ).fetchone()["c"]
            total_metrics = self._conn.execute(
                "SELECT COUNT(*) as c FROM pipeline_metrics"
            ).fetchone()["c"]
            unack_alerts = self._conn.execute(
                "SELECT COUNT(*) as c FROM pipeline_alerts WHERE acknowledged = 0"
            ).fetchone()["c"]
            total_alerts = self._conn.execute(
                "SELECT COUNT(*) as c FROM pipeline_alerts"
            ).fetchone()["c"]

        success_rate = round(completed_runs / total_runs * 100, 2) if total_runs else 0.0
        return {
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "failed_runs": failed_runs,
            "running_runs": running_runs,
            "success_rate": success_rate,
            "total_metrics": total_metrics,
            "total_alerts": total_alerts,
            "unacknowledged_alerts": unack_alerts,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="monitoring.pipeline_monitor",
            ))

    def close(self):
        self._conn.close()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_monitor: PipelineMonitor | None = None


def get_pipeline_monitor(db_path: str | Path | None = None,
                         event_bus: Any = None) -> PipelineMonitor:
    global _monitor
    if _monitor is None:
        _monitor = PipelineMonitor(db_path=db_path, event_bus=event_bus)
    return _monitor


def reset_pipeline_monitor() -> None:
    global _monitor
    _monitor = None
