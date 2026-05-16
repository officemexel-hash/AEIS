"""
SYLION Monitoring -- SLA Monitor

SLA compliance monitoring for API endpoints and services.
Tracks SLA definitions, performs compliance checks, and records breaches.

SQLite-backed with WAL mode. Thread-safe via threading.RLock.
Singleton via get_sla_monitor() / reset_sla_monitor(). Emits events via EventBus.
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

log = logging.getLogger("sylion.monitoring.sla_monitor")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TARGET_METRICS = (
    "latency_p50",
    "latency_p99",
    "availability",
    "error_rate",
    "throughput",
)

BREACH_STATUSES = ("active", "resolved", "escalated")


# ---------------------------------------------------------------------------
# SLA Monitor
# ---------------------------------------------------------------------------

class SLAMonitor:
    """SLA compliance monitor backed by SQLite.

    Manages SLA definitions, performs compliance checks against actual
    values, and records breaches when thresholds are exceeded.

    Thread-safe via RLock. Singleton-capable. EventBus-integrated.
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
            CREATE TABLE IF NOT EXISTS sla_definitions (
                sla_id          TEXT PRIMARY KEY,
                name            TEXT    NOT NULL,
                target_metric   TEXT    NOT NULL,
                target_value    REAL    NOT NULL,
                threshold       REAL    NOT NULL,
                window_seconds  INTEGER NOT NULL DEFAULT 300,
                enabled         INTEGER NOT NULL DEFAULT 1,
                created_at      REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sla_checks (
                check_id    TEXT PRIMARY KEY,
                sla_id      TEXT    NOT NULL,
                actual_value REAL   NOT NULL,
                target_value REAL   NOT NULL,
                compliant   INTEGER NOT NULL,
                checked_at  REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sla_breaches (
                breach_id           TEXT PRIMARY KEY,
                sla_id              TEXT    NOT NULL,
                actual_value        REAL    NOT NULL,
                threshold           REAL    NOT NULL,
                duration_seconds    REAL    NOT NULL DEFAULT 0.0,
                detected_at         REAL    NOT NULL,
                status              TEXT    NOT NULL DEFAULT 'active'
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sd_metric "
            "ON sla_definitions(target_metric)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sd_enabled "
            "ON sla_definitions(enabled)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sc_sla "
            "ON sla_checks(sla_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sc_compliant "
            "ON sla_checks(compliant)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sc_checked "
            "ON sla_checks(checked_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sb_sla "
            "ON sla_breaches(sla_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sb_status "
            "ON sla_breaches(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sb_detected "
            "ON sla_breaches(detected_at)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # SLA Definitions
    # ------------------------------------------------------------------

    def define_sla(self, name: str, target_metric: str,
                   target_value: float, threshold: float,
                   window_seconds: int = 300) -> dict:
        """Create an SLA definition.

        Returns dict with sla_id and configuration.
        Raises ValueError for invalid target_metric.
        """
        if target_metric not in TARGET_METRICS:
            raise ValueError(
                f"Invalid target_metric '{target_metric}'. "
                f"Must be one of {TARGET_METRICS}"
            )

        sla_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO sla_definitions
                    (sla_id, name, target_metric, target_value,
                     threshold, window_seconds, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """, (sla_id, name, target_metric, target_value,
                  threshold, window_seconds, now))
            self._conn.commit()

        result = {
            "sla_id": sla_id,
            "name": name,
            "target_metric": target_metric,
            "target_value": target_value,
            "threshold": threshold,
            "window_seconds": window_seconds,
            "enabled": True,
            "created_at": now,
        }

        self._emit("monitoring.sla_monitor.defined", result)
        log.info("SLA defined: %s (%s) metric=%s target=%.4f threshold=%.4f",
                 sla_id, name, target_metric, target_value, threshold)
        return result

    def get_sla(self, sla_id: str) -> dict | None:
        """Get a single SLA definition by ID.

        Returns dict or None if not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sla_definitions WHERE sla_id = ?",
                (sla_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_sla(row)

    def list_slas(self, target_metric: str | None = None,
                  enabled: bool | None = None) -> list[dict]:
        """List SLA definitions, optionally filtered by metric and/or enabled."""
        with self._lock:
            conditions: list[str] = []
            params: list[Any] = []

            if target_metric is not None:
                conditions.append("target_metric = ?")
                params.append(target_metric)
            if enabled is not None:
                conditions.append("enabled = ?")
                params.append(1 if enabled else 0)

            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)

            query = (
                f"SELECT * FROM sla_definitions {where} "
                f"ORDER BY created_at DESC"
            )
            rows = self._conn.execute(query, params).fetchall()

        return [self._row_to_sla(r) for r in rows]

    def update_sla(self, sla_id: str, enabled: bool | None = None) -> dict | None:
        """Update an SLA definition. Currently supports toggling enabled.

        Returns updated SLA dict, or None if not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sla_definitions WHERE sla_id = ?",
                (sla_id,),
            ).fetchone()

            if row is None:
                return None

            if enabled is not None:
                self._conn.execute(
                    "UPDATE sla_definitions SET enabled = ? WHERE sla_id = ?",
                    (1 if enabled else 0, sla_id),
                )
                self._conn.commit()

        result = self.get_sla(sla_id)
        self._emit("monitoring.sla_monitor.updated", {
            "sla_id": sla_id,
            "enabled": enabled,
        })
        log.info("SLA updated: %s enabled=%s", sla_id, enabled)
        return result

    # ------------------------------------------------------------------
    # SLA Checks
    # ------------------------------------------------------------------

    def check_sla(self, sla_id: str, actual_value: float) -> dict:
        """Perform an SLA compliance check.

        Records the check result. If non-compliant (actual_value exceeds
        threshold), creates a breach record.

        Returns dict with check_id, sla_id, actual_value, target_value,
        compliant, and breach_id (if applicable).
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sla_definitions WHERE sla_id = ?",
                (sla_id,),
            ).fetchone()

            if row is None:
                raise ValueError(f"SLA '{sla_id}' not found")

            if not row["enabled"]:
                raise ValueError(f"SLA '{sla_id}' is disabled")

        target_value = row["target_value"]
        threshold = row["threshold"]
        metric = row["target_metric"]

        # Compliance: actual_value must not exceed threshold
        # For latency/error_rate: lower is better (actual <= threshold)
        # For availability/throughput: higher is better (actual >= target)
        if metric in ("availability", "throughput"):
            compliant = 1 if actual_value >= target_value else 0
        else:
            compliant = 1 if actual_value <= threshold else 0

        check_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO sla_checks
                    (check_id, sla_id, actual_value, target_value, compliant, checked_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (check_id, sla_id, actual_value, target_value, compliant, now))
            self._conn.commit()

        result: dict[str, Any] = {
            "check_id": check_id,
            "sla_id": sla_id,
            "actual_value": actual_value,
            "target_value": target_value,
            "compliant": bool(compliant),
            "checked_at": now,
        }

        if not compliant:
            # Calculate breach duration from window
            window_seconds = row["window_seconds"]
            breach = self._create_breach(
                sla_id, actual_value, threshold, float(window_seconds), now,
            )
            result["breach_id"] = breach["breach_id"]
            self._emit("sla.breach", {
                "breach_id": breach["breach_id"],
                "sla_id": sla_id,
                "actual_value": actual_value,
                "threshold": threshold,
            })
            log.warning(
                "SLA breach: %s actual=%.4f threshold=%.4f",
                sla_id, actual_value, threshold,
            )
        else:
            log.debug("SLA check passed: %s actual=%.4f", sla_id, actual_value)

        return result

    def _create_breach(self, sla_id: str, actual_value: float,
                       threshold: float, duration_seconds: float,
                       detected_at: float) -> dict:
        """Create a breach record. Must be called under lock context."""
        breach_id = uuid.uuid4().hex

        with self._lock:
            self._conn.execute("""
                INSERT INTO sla_breaches
                    (breach_id, sla_id, actual_value, threshold,
                     duration_seconds, detected_at, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
            """, (breach_id, sla_id, actual_value, threshold,
                  duration_seconds, detected_at))
            self._conn.commit()

        return {
            "breach_id": breach_id,
            "sla_id": sla_id,
            "actual_value": actual_value,
            "threshold": threshold,
            "duration_seconds": duration_seconds,
            "detected_at": detected_at,
            "status": "active",
        }

    def list_checks(self, sla_id: str | None = None,
                    compliant: bool | None = None,
                    limit: int = 100) -> list[dict]:
        """List SLA checks, optionally filtered by sla_id and/or compliant."""
        with self._lock:
            conditions: list[str] = []
            params: list[Any] = []

            if sla_id is not None:
                conditions.append("sla_id = ?")
                params.append(sla_id)
            if compliant is not None:
                conditions.append("compliant = ?")
                params.append(1 if compliant else 0)

            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)

            query = (
                f"SELECT * FROM sla_checks {where} "
                f"ORDER BY checked_at DESC LIMIT ?"
            )
            params.append(limit)
            rows = self._conn.execute(query, params).fetchall()

        return [self._row_to_check(r) for r in rows]

    # ------------------------------------------------------------------
    # Breaches
    # ------------------------------------------------------------------

    def list_breaches(self, sla_id: str | None = None,
                      status: str | None = None,
                      limit: int = 100) -> list[dict]:
        """List SLA breaches, optionally filtered by sla_id and/or status."""
        if status is not None and status not in BREACH_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of {BREACH_STATUSES}"
            )

        with self._lock:
            conditions: list[str] = []
            params: list[Any] = []

            if sla_id is not None:
                conditions.append("sla_id = ?")
                params.append(sla_id)
            if status is not None:
                conditions.append("status = ?")
                params.append(status)

            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)

            query = (
                f"SELECT * FROM sla_breaches {where} "
                f"ORDER BY detected_at DESC LIMIT ?"
            )
            params.append(limit)
            rows = self._conn.execute(query, params).fetchall()

        return [self._row_to_breach(r) for r in rows]

    def resolve_breach(self, breach_id: str) -> dict | None:
        """Resolve an active breach.

        Sets status to 'resolved'. Returns updated breach dict or None.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sla_breaches WHERE breach_id = ?",
                (breach_id,),
            ).fetchone()

            if row is None:
                return None

            self._conn.execute(
                "UPDATE sla_breaches SET status = 'resolved' WHERE breach_id = ?",
                (breach_id,),
            )
            self._conn.commit()

        result = self._row_to_breach(row)
        result["status"] = "resolved"

        self._emit("sla.breach_resolved", {
            "breach_id": breach_id,
            "sla_id": row["sla_id"],
        })
        log.info("SLA breach resolved: %s", breach_id)
        return result

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate SLA compliance statistics.

        Returns dict with:
            total_slas, enabled_slas, total_checks, compliant_checks,
            compliance_rate, total_breaches, active_breaches,
            resolved_breaches, escalated_breaches.
        """
        with self._lock:
            total_slas = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sla_definitions"
            ).fetchone()["cnt"]

            enabled_slas = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sla_definitions WHERE enabled = 1"
            ).fetchone()["cnt"]

            total_checks = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sla_checks"
            ).fetchone()["cnt"]

            compliant_checks = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sla_checks WHERE compliant = 1"
            ).fetchone()["cnt"]

            total_breaches = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sla_breaches"
            ).fetchone()["cnt"]

            active_breaches = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sla_breaches WHERE status = 'active'"
            ).fetchone()["cnt"]

            resolved_breaches = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sla_breaches WHERE status = 'resolved'"
            ).fetchone()["cnt"]

            escalated_breaches = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sla_breaches WHERE status = 'escalated'"
            ).fetchone()["cnt"]

        compliance_rate = (
            compliant_checks / total_checks if total_checks > 0 else 1.0
        )

        return {
            "total_slas": total_slas,
            "enabled_slas": enabled_slas,
            "total_checks": total_checks,
            "compliant_checks": compliant_checks,
            "compliance_rate": compliance_rate,
            "total_breaches": total_breaches,
            "active_breaches": active_breaches,
            "resolved_breaches": resolved_breaches,
            "escalated_breaches": escalated_breaches,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_sla(row: sqlite3.Row) -> dict:
        """Convert a sla_definitions row to a dict."""
        return {
            "sla_id": row["sla_id"],
            "name": row["name"],
            "target_metric": row["target_metric"],
            "target_value": row["target_value"],
            "threshold": row["threshold"],
            "window_seconds": row["window_seconds"],
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
        }

    @staticmethod
    def _row_to_check(row: sqlite3.Row) -> dict:
        """Convert a sla_checks row to a dict."""
        return {
            "check_id": row["check_id"],
            "sla_id": row["sla_id"],
            "actual_value": row["actual_value"],
            "target_value": row["target_value"],
            "compliant": bool(row["compliant"]),
            "checked_at": row["checked_at"],
        }

    @staticmethod
    def _row_to_breach(row: sqlite3.Row) -> dict:
        """Convert a sla_breaches row to a dict."""
        return {
            "breach_id": row["breach_id"],
            "sla_id": row["sla_id"],
            "actual_value": row["actual_value"],
            "threshold": row["threshold"],
            "duration_seconds": row["duration_seconds"],
            "detected_at": row["detected_at"],
            "status": row["status"],
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="monitoring.sla_monitor",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: SLAMonitor | None = None


def get_sla_monitor(db_path: str | Path | None = None,
                    event_bus: EventBus | None = None) -> SLAMonitor:
    """Get or create the global SLAMonitor singleton."""
    global _instance
    if _instance is None:
        _instance = SLAMonitor(db_path, event_bus)
    return _instance


def reset_sla_monitor() -> None:
    """Reset the global singleton (for testing)."""
    global _instance
    _instance = None
