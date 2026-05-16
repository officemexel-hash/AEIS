"""
SYLION Monitoring -- Configuration Drift Detector

Detects configuration drift between expected and actual module configurations.
Maintains baselines of expected config values, compares them against actual
values, and generates drift reports with severity classification.

Severity levels based on drift count per report:
  info     -- 1 drift
  warning  -- 2-5 drifts
  critical -- >5 drifts

SQLite-backed with WAL mode.  Thread-safe via threading.RLock().
Singleton via get_config_drift_detector() / reset_config_drift_detector().
Emits events via EventBus.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.monitoring.config_drift_detector")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SEVERITIES = ("info", "warning", "critical")
REPORT_STATUSES = ("active", "resolved", "ignored")


# ---------------------------------------------------------------------------
# ConfigDriftDetector
# ---------------------------------------------------------------------------

class ConfigDriftDetector:
    """Configuration drift detection backed by SQLite.

    Tracks expected configuration baselines per module/key, compares actual
    values against them, records individual drifts, and generates aggregate
    drift reports with severity classification.

    Thread-safe.  Event-emitting.  Singleton-capable.
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
            CREATE TABLE IF NOT EXISTS config_baselines (
                baseline_id    TEXT PRIMARY KEY,
                module_id      TEXT    NOT NULL,
                config_key     TEXT    NOT NULL,
                expected_value TEXT    NOT NULL,
                actual_value   TEXT,
                is_drift       INTEGER NOT NULL DEFAULT 0,
                detected_at    REAL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS drift_reports (
                report_id   TEXT PRIMARY KEY,
                module_id   TEXT    NOT NULL,
                drift_count INTEGER NOT NULL,
                severity    TEXT    NOT NULL,
                reported_at REAL    NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'active',
                details     TEXT
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cb_module "
            "ON config_baselines(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cb_module_key "
            "ON config_baselines(module_id, config_key)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cb_drift "
            "ON config_baselines(is_drift)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dr_module "
            "ON drift_reports(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dr_severity "
            "ON drift_reports(severity)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dr_status "
            "ON drift_reports(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dr_reported "
            "ON drift_reports(reported_at)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # set_baseline
    # ------------------------------------------------------------------

    def set_baseline(self, module_id: str, config_key: str,
                     expected_value: Any) -> dict:
        """Set or update an expected configuration baseline.

        Returns a dict with baseline details.
        """
        baseline_id = f"{module_id}:{config_key}"
        expected_str = str(expected_value)
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO config_baselines
                    (baseline_id, module_id, config_key,
                     expected_value, actual_value, is_drift, detected_at)
                VALUES (?, ?, ?, ?, NULL, 0, NULL)
            """, (baseline_id, module_id, config_key, expected_str))
            self._conn.commit()

        result = {
            "baseline_id": baseline_id,
            "module_id": module_id,
            "config_key": config_key,
            "expected_value": expected_str,
        }

        log.debug(
            "baseline set: %s/%s = %s", module_id, config_key, expected_str,
        )
        return result

    # ------------------------------------------------------------------
    # get_baselines
    # ------------------------------------------------------------------

    def get_baselines(self, module_id: str | None = None) -> list[dict]:
        """List baselines, optionally filtered by module_id."""
        with self._lock:
            if module_id is not None:
                rows = self._conn.execute(
                    "SELECT * FROM config_baselines "
                    "WHERE module_id = ? ORDER BY config_key",
                    (module_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM config_baselines ORDER BY module_id, config_key",
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # check_drift
    # ------------------------------------------------------------------

    def check_drift(self, module_id: str, config_key: str,
                    actual_value: Any) -> dict:
        """Compare an actual value against the expected baseline.

        Records a drift entry if they differ.  Returns a dict with
        baseline_id, is_drift, expected_value, actual_value.
        """
        baseline_id = f"{module_id}:{config_key}"
        actual_str = str(actual_value)
        now = time.time()

        with self._lock:
            row = self._conn.execute(
                "SELECT expected_value FROM config_baselines WHERE baseline_id = ?",
                (baseline_id,),
            ).fetchone()

        if row is None:
            return {
                "baseline_id": baseline_id,
                "module_id": module_id,
                "config_key": config_key,
                "expected_value": None,
                "actual_value": actual_str,
                "is_drift": False,
                "reason": "no_baseline",
            }

        expected_str = row["expected_value"]
        is_drift = (expected_str != actual_str)

        with self._lock:
            self._conn.execute("""
                UPDATE config_baselines
                SET actual_value = ?, is_drift = ?, detected_at = ?
                WHERE baseline_id = ?
            """, (actual_str, 1 if is_drift else 0, now, baseline_id))
            self._conn.commit()

        result = {
            "baseline_id": baseline_id,
            "module_id": module_id,
            "config_key": config_key,
            "expected_value": expected_str,
            "actual_value": actual_str,
            "is_drift": is_drift,
        }

        if is_drift:
            self._emit("config.drift_detected", {
                "baseline_id": baseline_id,
                "module_id": module_id,
                "config_key": config_key,
                "expected_value": expected_str,
                "actual_value": actual_str,
            })
            log.warning(
                "config drift: %s/%s expected=%s actual=%s",
                module_id, config_key, expected_str, actual_str,
            )

        return result

    # ------------------------------------------------------------------
    # run_full_check
    # ------------------------------------------------------------------

    def run_full_check(self, module_id: str | None = None) -> dict:
        """Check all baselines and generate a drift report.

        If module_id is provided, only checks baselines for that module.
        Returns the generated drift report dict.
        """
        with self._lock:
            if module_id is not None:
                rows = self._conn.execute(
                    "SELECT * FROM config_baselines WHERE module_id = ?",
                    (module_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM config_baselines",
                ).fetchall()

        drifts: list[dict] = []
        for row in rows:
            r = dict(row)
            # Only count entries where actual_value has been set and differs
            if r["is_drift"] == 1:
                drifts.append(r)

        drift_count = len(drifts)
        severity = self._classify_severity(drift_count)

        report_id = uuid.uuid4().hex
        now = time.time()

        # Build details JSON
        details_parts: list[str] = []
        for d in drifts:
            details_parts.append(
                f"{d['config_key']}: expected={d['expected_value']} "
                f"actual={d['actual_value']}"
            )
        details = "; ".join(details_parts) if details_parts else "no drifts"

        with self._lock:
            self._conn.execute("""
                INSERT INTO drift_reports
                    (report_id, module_id, drift_count, severity,
                     reported_at, status, details)
                VALUES (?, ?, ?, ?, ?, 'active', ?)
            """, (
                report_id,
                module_id or "__all__",
                drift_count,
                severity,
                now,
                details,
            ))
            self._conn.commit()

        report = {
            "report_id": report_id,
            "module_id": module_id or "__all__",
            "drift_count": drift_count,
            "severity": severity,
            "reported_at": now,
            "status": "active",
            "details": details,
        }

        if drift_count > 0:
            self._emit("config.drift_detected", {
                "report_id": report_id,
                "module_id": module_id or "__all__",
                "drift_count": drift_count,
                "severity": severity,
            })

        log.info(
            "drift report %s: module=%s drifts=%d severity=%s",
            report_id[:12], module_id or "__all__", drift_count, severity,
        )
        return report

    # ------------------------------------------------------------------
    # get_drift_report
    # ------------------------------------------------------------------

    def get_drift_report(self, report_id: str) -> dict | None:
        """Retrieve a single drift report by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM drift_reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # list_drift_reports
    # ------------------------------------------------------------------

    def list_drift_reports(self, module_id: str | None = None,
                           severity: str | None = None,
                           status: str | None = None,
                           limit: int = 50) -> list[dict]:
        """List drift reports with optional filters.

        Results are ordered by reported_at descending.
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
                f"SELECT * FROM drift_reports {where} "
                f"ORDER BY reported_at DESC LIMIT ?"
            )
            params.append(limit)
            rows = self._conn.execute(query, params).fetchall()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # resolve_drift
    # ------------------------------------------------------------------

    def resolve_drift(self, report_id: str) -> bool:
        """Mark a drift report as resolved.

        Returns True if the report existed and was updated.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT status FROM drift_reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()

            if row is None:
                return False

            self._conn.execute(
                "UPDATE drift_reports SET status = 'resolved' WHERE report_id = ?",
                (report_id,),
            )
            self._conn.commit()

        self._emit("config.drift_resolved", {
            "report_id": report_id,
        })
        log.info("drift report resolved: %s", report_id[:12])
        return True

    # ------------------------------------------------------------------
    # get_stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate drift detector statistics.

        Returns dict with total_baselines, total_drifts, total_reports,
        by_module, by_severity.
        """
        with self._lock:
            baseline_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM config_baselines"
            ).fetchone()["cnt"]

            drift_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM config_baselines WHERE is_drift = 1"
            ).fetchone()["cnt"]

            report_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM drift_reports"
            ).fetchone()["cnt"]

            # Drifts by module
            module_rows = self._conn.execute(
                "SELECT module_id, COUNT(*) as cnt "
                "FROM config_baselines WHERE is_drift = 1 "
                "GROUP BY module_id ORDER BY cnt DESC"
            ).fetchall()
            by_module = {r["module_id"]: r["cnt"] for r in module_rows}

            # Reports by severity
            sev_rows = self._conn.execute(
                "SELECT severity, COUNT(*) as cnt FROM drift_reports "
                "GROUP BY severity"
            ).fetchall()
            by_severity = {r["severity"]: r["cnt"] for r in sev_rows}

            # Reports by status
            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM drift_reports "
                "GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

        return {
            "total_baselines": baseline_count,
            "total_drifts": drift_count,
            "total_reports": report_count,
            "by_module": by_module,
            "by_severity": by_severity,
            "by_status": by_status,
        }

    # ------------------------------------------------------------------
    # Internal: severity classification
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_severity(drift_count: int) -> str:
        """Classify severity based on drift count.

        info     -- 1 drift
        warning  -- 2-5 drifts
        critical -- >5 drifts
        """
        if drift_count <= 0:
            return "info"
        if drift_count == 1:
            return "info"
        if drift_count <= 5:
            return "warning"
        return "critical"

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="monitoring.config_drift_detector",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: ConfigDriftDetector | None = None


def get_config_drift_detector(db_path: str | None = None,
                              event_bus: EventBus | None = None,
                              ) -> ConfigDriftDetector:
    """Get or create the global ConfigDriftDetector singleton."""
    global _instance
    if _instance is None:
        _instance = ConfigDriftDetector(db_path, event_bus)
    return _instance


def reset_config_drift_detector() -> None:
    """Reset the global singleton (for testing)."""
    global _instance
    _instance = None
