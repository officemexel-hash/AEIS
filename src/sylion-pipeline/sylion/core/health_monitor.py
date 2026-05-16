"""
SYLION Core -- Module Health Monitor

Monitors module health based on heartbeats sent to the ModuleRegistry.
SQLite-backed, thread-safe.

Health status:
  - healthy:   last heartbeat < 60 seconds ago
  - degraded:  last heartbeat 60-300 seconds ago
  - unhealthy: last heartbeat > 300 seconds ago
  - unknown:   module registered but never sent heartbeat
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.core.health_monitor")

# Default thresholds (seconds)
DEFAULT_HEALTHY_THRESHOLD = 60
DEFAULT_DEGRADED_THRESHOLD = 300


class ModuleHealthMonitor:
    """Monitors module health based on heartbeats. SQLite-backed."""

    def __init__(self, registry: Any, event_bus: Any = None, db_path: str | Path | None = None):
        self._registry = registry
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def _create_tables(self):
        """Create heartbeat log and per-module alert threshold tables."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_heartbeat_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id   TEXT NOT NULL,
                timestamp   REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_hb_log_module_ts
                ON sylion_heartbeat_log(module_id, timestamp)
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_health_thresholds (
                module_id       TEXT PRIMARY KEY,
                max_age_seconds REAL NOT NULL DEFAULT 300
            )
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_threshold(self, module_id: str) -> float:
        """Return per-module unhealthy threshold, or the default (300s)."""
        row = self._conn.execute(
            "SELECT max_age_seconds FROM sylion_health_thresholds WHERE module_id=?",
            (module_id,),
        ).fetchone()
        return float(row["max_age_seconds"]) if row else DEFAULT_DEGRADED_THRESHOLD

    @staticmethod
    def _classify_status(age_seconds: float, max_age: float) -> str:
        """Classify a module's health from heartbeat age."""
        if age_seconds < 0:
            return "unknown"
        if age_seconds < DEFAULT_HEALTHY_THRESHOLD:
            return "healthy"
        if age_seconds < max_age:
            return "degraded"
        return "unhealthy"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_health(self, module_id: str) -> dict:
        """Returns {module_id, status, last_heartbeat, age_seconds, healthy}"""
        mod = self._registry.get(module_id)
        if mod is None:
            return {
                "module_id": module_id,
                "status": "unknown",
                "last_heartbeat": None,
                "age_seconds": -1,
                "healthy": False,
            }

        last_hb = mod.get("last_heartbeat", 0)
        registered_at = mod.get("registered_at", 0)

        if last_hb <= 0 and registered_at <= 0:
            age = -1.0
        else:
            age = time.time() - (last_hb if last_hb > 0 else registered_at)

        max_age = self._get_threshold(module_id)
        status = self._classify_status(age, max_age)

        return {
            "module_id": module_id,
            "status": status,
            "last_heartbeat": last_hb,
            "age_seconds": round(age, 3),
            "healthy": status == "healthy",
        }

    def check_all(self) -> list[dict]:
        """Check health of all registered modules."""
        modules = self._registry.list_modules()
        results = []
        for mod in modules:
            results.append(self.check_health(mod["module_id"]))
        return results

    def get_stats(self) -> dict:
        """Returns {total, healthy, degraded, unhealthy, unknown, avg_age_seconds}"""
        all_health = self.check_all()
        counts = {"healthy": 0, "degraded": 0, "unhealthy": 0, "unknown": 0}
        total_age = 0.0
        age_count = 0

        for h in all_health:
            status = h["status"]
            counts[status] = counts.get(status, 0) + 1
            if h["age_seconds"] >= 0:
                total_age += h["age_seconds"]
                age_count += 1

        avg_age = round(total_age / age_count, 3) if age_count > 0 else -1.0

        return {
            "total": len(all_health),
            "healthy": counts["healthy"],
            "degraded": counts["degraded"],
            "unhealthy": counts["unhealthy"],
            "unknown": counts["unknown"],
            "avg_age_seconds": avg_age,
        }

    def record_heartbeat(self, module_id: str) -> dict:
        """Record a heartbeat. Updates registry + monitor tables."""
        mod = self._registry.get(module_id)
        if mod is None:
            log.warning("heartbeat for unregistered module %s", module_id)
            return {
                "module_id": module_id,
                "status": "unknown",
                "last_heartbeat": None,
                "age_seconds": -1,
                "healthy": False,
                "error": "module not registered",
            }

        now = time.time()

        # Update the registry's last_heartbeat
        self._registry.heartbeat(module_id)

        # Log the heartbeat in the monitor table
        with self._lock:
            self._conn.execute(
                "INSERT INTO sylion_heartbeat_log (module_id, timestamp) VALUES (?, ?)",
                (module_id, now),
            )
            self._conn.commit()

        # Emit event if event bus is available
        if self._event_bus is not None:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic="module.heartbeat",
                payload={"module_id": module_id, "timestamp": now},
                source_module=module_id,
            ))

        health = self.check_health(module_id)
        log.debug("heartbeat recorded for %s -> %s", module_id, health["status"])
        return health

    def set_alert_threshold(self, module_id: str, max_age_seconds: float) -> dict:
        """Set per-module alert threshold (seconds before marked unhealthy)."""
        with self._lock:
            self._conn.execute(
                """INSERT INTO sylion_health_thresholds (module_id, max_age_seconds)
                   VALUES (?, ?)
                   ON CONFLICT(module_id) DO UPDATE SET max_age_seconds=excluded.max_age_seconds""",
                (module_id, max_age_seconds),
            )
            self._conn.commit()

        return {
            "module_id": module_id,
            "max_age_seconds": max_age_seconds,
        }

    def get_heartbeat_history(self, module_id: str, limit: int = 100) -> list[dict]:
        """Get recent heartbeat timestamps for a module."""
        rows = self._conn.execute(
            "SELECT * FROM sylion_heartbeat_log WHERE module_id=? ORDER BY timestamp DESC LIMIT ?",
            (module_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        """Close the database connection."""
        self._conn.close()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_monitor: ModuleHealthMonitor | None = None


def get_health_monitor(
    registry: Any = None,
    event_bus: Any = None,
    db_path: str | Path | None = None,
) -> ModuleHealthMonitor:
    global _monitor
    if _monitor is None:
        if registry is None:
            from sylion.core.module_registry import get_registry
            registry = get_registry()
        _monitor = ModuleHealthMonitor(registry=registry, event_bus=event_bus, db_path=db_path)
    return _monitor
