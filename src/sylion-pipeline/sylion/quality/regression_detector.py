"""
SYLION Quality — Regression Detector

Regression detection between test runs. Establishes per-module baselines
and raises alerts when pass rates drop below the established baseline.

SQLite-backed, thread-safe, event-emitting.
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

log = logging.getLogger("sylion.quality.regression_detector")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Baseline:
    """A module's baseline performance metrics."""
    module_id: str = ""
    suite_id: str = ""
    run_id: str = ""
    pass_rate: float = 1.0
    avg_duration_ms: int = 0
    established_at: float = 0.0

    def __post_init__(self):
        if not self.established_at:
            self.established_at = time.time()


@dataclass
class RegressionAlert:
    """An alert raised when regression is detected."""
    alert_id: str = ""
    module_id: str = ""
    suite_id: str = ""
    baseline_pass_rate: float = 1.0
    current_pass_rate: float = 1.0
    severity: str = "warning"
    details: str = "{}"
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.alert_id:
            self.alert_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# RegressionDetector
# ---------------------------------------------------------------------------

class RegressionDetector:
    """Regression detection between test runs.

    Thread-safe. SQLite-backed. Emits events on baseline set / regression detected.
    """

    # Thresholds for severity classification
    _WARNING_THRESHOLD: float = 0.05   # 5% drop
    _CRITICAL_THRESHOLD: float = 0.15  # 15% drop

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
            CREATE TABLE IF NOT EXISTS baselines (
                module_id       TEXT PRIMARY KEY,
                suite_id        TEXT NOT NULL DEFAULT '',
                run_id          TEXT NOT NULL DEFAULT '',
                pass_rate       REAL NOT NULL DEFAULT 1.0,
                avg_duration_ms INTEGER NOT NULL DEFAULT 0,
                established_at  REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS regression_alerts (
                alert_id            TEXT PRIMARY KEY,
                module_id           TEXT NOT NULL,
                suite_id            TEXT NOT NULL DEFAULT '',
                baseline_pass_rate  REAL NOT NULL,
                current_pass_rate   REAL NOT NULL,
                severity            TEXT NOT NULL DEFAULT 'warning',
                details             TEXT NOT NULL DEFAULT '{}',
                timestamp           REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bl_suite ON baselines(suite_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ra_module ON regression_alerts(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ra_severity ON regression_alerts(severity)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ra_ts ON regression_alerts(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Baseline management
    # ------------------------------------------------------------------

    def set_baseline(self, module_id: str, suite_id: str, run_id: str,
                     pass_rate: float = 1.0, avg_duration: int = 0) -> dict:
        """Set (or update) the baseline for a module."""
        baseline = Baseline(
            module_id=module_id,
            suite_id=suite_id,
            run_id=run_id,
            pass_rate=pass_rate,
            avg_duration_ms=avg_duration,
        )

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO baselines
                (module_id, suite_id, run_id, pass_rate,
                 avg_duration_ms, established_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                baseline.module_id, baseline.suite_id, baseline.run_id,
                baseline.pass_rate, baseline.avg_duration_ms,
                baseline.established_at,
            ))
            self._conn.commit()

        self._emit("regression.baseline_set", {
            "module_id": module_id, "suite_id": suite_id,
            "pass_rate": pass_rate,
        })
        log.info("baseline set for %s: pass_rate=%.4f avg_duration=%dms",
                 module_id, pass_rate, avg_duration)
        return {
            "module_id": module_id, "suite_id": suite_id,
            "pass_rate": pass_rate, "avg_duration_ms": avg_duration,
        }

    # ------------------------------------------------------------------
    # Regression check
    # ------------------------------------------------------------------

    def check_regression(self, module_id: str, suite_id: str,
                         current_pass_rate: float) -> dict:
        """Compare current pass rate to baseline. Raises alert on regression."""
        row = self._conn.execute(
            "SELECT * FROM baselines WHERE module_id = ?", (module_id,),
        ).fetchone()

        if not row:
            return {
                "checked": False,
                "message": f"No baseline for module {module_id}",
            }

        baseline_pass_rate = row["pass_rate"]
        drop = baseline_pass_rate - current_pass_rate

        if drop <= 0:
            # No regression
            return {
                "checked": True,
                "regression": False,
                "module_id": module_id,
                "baseline_pass_rate": baseline_pass_rate,
                "current_pass_rate": current_pass_rate,
                "drop": drop,
            }

        # Determine severity
        if drop >= self._CRITICAL_THRESHOLD:
            severity = "critical"
        elif drop >= self._WARNING_THRESHOLD:
            severity = "warning"
        else:
            severity = "info"

        details = {
            "baseline_run_id": row["run_id"],
            "baseline_pass_rate": baseline_pass_rate,
            "current_pass_rate": current_pass_rate,
            "drop": round(drop, 4),
        }

        alert = RegressionAlert(
            module_id=module_id,
            suite_id=suite_id,
            baseline_pass_rate=baseline_pass_rate,
            current_pass_rate=current_pass_rate,
            severity=severity,
            details=json.dumps(details),
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO regression_alerts
                (alert_id, module_id, suite_id, baseline_pass_rate,
                 current_pass_rate, severity, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id, alert.module_id, alert.suite_id,
                alert.baseline_pass_rate, alert.current_pass_rate,
                alert.severity, alert.details, alert.timestamp,
            ))
            self._conn.commit()

        self._emit("regression.detected", {
            "alert_id": alert.alert_id, "module_id": module_id,
            "severity": severity, "drop": round(drop, 4),
        })
        log.warning("regression detected for %s: %.4f -> %.4f (%s)",
                    module_id, baseline_pass_rate, current_pass_rate, severity)
        return {
            "checked": True,
            "regression": True,
            "alert_id": alert.alert_id,
            "module_id": module_id,
            "baseline_pass_rate": baseline_pass_rate,
            "current_pass_rate": current_pass_rate,
            "drop": round(drop, 4),
            "severity": severity,
        }

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_baseline(self, module_id: str) -> dict | None:
        """Retrieve baseline for a module."""
        row = self._conn.execute(
            "SELECT * FROM baselines WHERE module_id = ?", (module_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_alerts(self, module_id: str | None = None,
                    severity: str | None = None,
                    limit: int = 100) -> list[dict]:
        """List regression alerts with optional filters."""
        q = "SELECT * FROM regression_alerts WHERE 1=1"
        params: list[Any] = []
        if module_id:
            q += " AND module_id = ?"
            params.append(module_id)
        if severity:
            q += " AND severity = ?"
            params.append(severity)
        q += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge (delete) a regression alert."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM regression_alerts WHERE alert_id = ?",
                (alert_id,),
            ).rowcount
            self._conn.commit()

        if n:
            self._emit("regression.alert_acknowledged", {"alert_id": alert_id})
            log.info("acknowledged alert %s", alert_id[:12])
        return bool(n)

    def list_baselines(self, status: str | None = None) -> list[dict]:
        """List all baselines (status filter is post-hoc — no status column).

        ``status`` is accepted for route-signature parity; if provided, results
        are filtered by a synthetic ``status`` derived from pass_rate >= 0.95.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM baselines ORDER BY established_at DESC"
            ).fetchall()
        out: list[dict] = []
        for r in rows:
            d = dict(r)
            d["status"] = "active" if d.get("pass_rate", 0) >= 0.95 else "degraded"
            if status is not None and d["status"] != status:
                continue
            out.append(d)
        return out

    def get_test_results(self, baseline_id: str | None = None,
                         status: str | None = None,
                         limit: int = 100) -> list[dict]:
        """Return regression alerts as test-result records.

        Each alert is a recorded regression check; we surface them through the
        workspace ``/regression/tests`` and ``/regression/results`` routes.
        ``baseline_id`` is treated as ``module_id`` for filtering since
        baselines are keyed on module_id.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if baseline_id is not None:
            clauses.append("module_id = ?")
            params.append(baseline_id)
        if status is not None:
            clauses.append("severity = ?")
            params.append(status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM regression_alerts {where} "
                "ORDER BY timestamp DESC LIMIT ?",
                tuple(params),
            ).fetchall()
        results: list[dict] = []
        for r in rows:
            d = dict(r)
            try:
                d["details"] = json.loads(d.get("details") or "{}")
            except (TypeError, ValueError):
                d["details"] = {}
            results.append(d)
        return results

    def get_regression_stats(self) -> dict:
        """Workspace-vocabulary alias for :meth:`get_stats`."""
        return self.get_stats()

    def get_stats(self) -> dict:
        """Aggregate regression detector statistics."""
        baseline_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM baselines"
        ).fetchone()["cnt"]

        alert_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM regression_alerts"
        ).fetchone()["cnt"]

        sev_rows = self._conn.execute(
            "SELECT severity, COUNT(*) as cnt FROM regression_alerts "
            "GROUP BY severity"
        ).fetchall()
        by_severity = {r["severity"]: r["cnt"] for r in sev_rows}

        module_rows = self._conn.execute(
            "SELECT module_id, COUNT(*) as cnt FROM regression_alerts "
            "GROUP BY module_id ORDER BY cnt DESC"
        ).fetchall()
        by_module = {r["module_id"]: r["cnt"] for r in module_rows}

        return {
            "baseline_count": baseline_count,
            "alert_count": alert_count,
            "by_severity": by_severity,
            "by_module": by_module,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="quality.regression_detector",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_detector: RegressionDetector | None = None


def get_regression_detector(event_bus: EventBus | None = None,
                            db_path: str | Path | None = None) -> RegressionDetector:
    global _detector
    if _detector is None:
        _detector = RegressionDetector(event_bus, db_path)
    return _detector
