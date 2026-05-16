"""
SYLION AEIS -- Self-Preservation and Safety Shutdown

Monitors system health and manages preservation modes:
normal, caution, critical, shutdown.

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.aeis.self_preservation")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class HealthCheck:
    """A single component health check result."""
    check_id: str = ""
    component: str = ""
    status: str = "healthy"
    message: str = ""
    score: float = 1.0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.check_id:
            self.check_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Self-Preservation Engine
# ---------------------------------------------------------------------------

class SelfPreservationEngine:
    """Self-preservation and safety shutdown.

    Thread-safe. SQLite-backed. Emits events on mode changes and health checks.
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
        self._init_state()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS preservation_state (
                key        TEXT PRIMARY KEY,
                value      TEXT    NOT NULL DEFAULT '',
                updated_at REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS health_checks (
                check_id   TEXT PRIMARY KEY,
                component  TEXT    NOT NULL,
                status     TEXT    NOT NULL DEFAULT 'healthy',
                message    TEXT    NOT NULL DEFAULT '',
                score      REAL    NOT NULL DEFAULT 1.0,
                timestamp  REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hc_component ON health_checks(component)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hc_ts ON health_checks(timestamp)"
        )
        self._conn.commit()

    def _init_state(self):
        """Initialize default preservation state if empty."""
        with self._lock:
            existing = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM preservation_state"
            ).fetchone()["cnt"]
            if existing == 0:
                now = time.time()
                self._conn.execute(
                    "INSERT INTO preservation_state (key, value, updated_at) VALUES (?, ?, ?)",
                    ("mode", "normal", now),
                )
                self._conn.execute(
                    "INSERT INTO preservation_state (key, value, updated_at) VALUES (?, ?, ?)",
                    ("health_score", "1.0", now),
                )
                self._conn.execute(
                    "INSERT INTO preservation_state (key, value, updated_at) VALUES (?, ?, ?)",
                    ("last_check", str(now), now),
                )
                self._conn.commit()

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    def check_health(self, component: str, status: str = "healthy",
                     message: str = "", score: float = 1.0) -> dict:
        """Record a component health check.

        Updates the last_check state. Emits
        ``aeis.self_preservation.health_checked``.
        """
        hc = HealthCheck(
            component=component,
            status=status,
            message=message,
            score=score,
        )

        now = hc.timestamp

        with self._lock:
            self._conn.execute("""
                INSERT INTO health_checks
                    (check_id, component, status, message, score, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                hc.check_id, hc.component, hc.status,
                hc.message, hc.score, hc.timestamp,
            ))

            # Update last_check
            self._conn.execute(
                "UPDATE preservation_state SET value = ?, updated_at = ? WHERE key = 'last_check'",
                (str(now), now),
            )
            self._conn.commit()

        # Recalculate health score
        self._update_health_score()

        self._emit("aeis.self_preservation.health_checked", {
            "check_id": hc.check_id,
            "component": component,
            "status": status,
            "score": score,
        })

        log.info("health check: %s status=%s score=%.2f", component, status, score)
        return {
            "check_id": hc.check_id,
            "component": component,
            "status": status,
            "score": score,
        }

    def _update_health_score(self):
        """Recalculate the overall health score from recent checks."""
        # Average of the most recent check per component
        rows = self._conn.execute("""
            SELECT component, score FROM health_checks h1
            WHERE timestamp = (
                SELECT MAX(timestamp) FROM health_checks h2
                WHERE h2.component = h1.component
            )
        """).fetchall()

        if rows:
            avg = sum(r["score"] for r in rows) / len(rows)
        else:
            avg = 1.0

        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE preservation_state SET value = ?, updated_at = ? WHERE key = 'health_score'",
                (str(round(avg, 4)), now),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Mode management
    # ------------------------------------------------------------------

    def get_mode(self) -> str:
        """Return the current preservation mode."""
        row = self._conn.execute(
            "SELECT value FROM preservation_state WHERE key = 'mode'"
        ).fetchone()
        return row["value"] if row else "normal"

    def set_mode(self, mode: str) -> dict:
        """Set the preservation mode.

        Valid modes: normal, caution, critical, shutdown.
        Emits ``aeis.self_preservation.mode_changed``.
        """
        valid_modes = ("normal", "caution", "critical", "shutdown")
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode '{mode}'. Must be one of {valid_modes}")

        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE preservation_state SET value = ?, updated_at = ? WHERE key = 'mode'",
                (mode, now),
            )
            self._conn.commit()

        self._emit("aeis.self_preservation.mode_changed", {
            "mode": mode,
        })

        log.warning("preservation mode changed to: %s", mode)
        return {"mode": mode}

    # ------------------------------------------------------------------
    # Health score
    # ------------------------------------------------------------------

    def get_health_score(self) -> float:
        """Return the average health score from recent checks."""
        # Average the most recent check per component
        rows = self._conn.execute("""
            SELECT component, score FROM health_checks h1
            WHERE timestamp = (
                SELECT MAX(timestamp) FROM health_checks h2
                WHERE h2.component = h1.component
            )
        """).fetchall()

        if not rows:
            return 1.0

        return round(sum(r["score"] for r in rows) / len(rows), 4)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_checks(self, component: str | None = None,
                   limit: int = 50) -> list[dict]:
        """Return health checks, optionally filtered by component."""
        if component:
            rows = self._conn.execute(
                "SELECT * FROM health_checks WHERE component = ? ORDER BY timestamp DESC LIMIT ?",
                (component, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM health_checks ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def should_shutdown(self) -> bool:
        """Return True if system should initiate safety shutdown.

        Triggers when mode is 'critical' or health score < 0.3.
        """
        mode = self.get_mode()
        if mode in ("critical", "shutdown"):
            return True

        health = self.get_health_score()
        if health < 0.3:
            return True

        return False

    def get_stats(self) -> dict:
        """Aggregate preservation statistics."""
        total_checks = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM health_checks"
        ).fetchone()["cnt"]

        by_status_rows = self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM health_checks GROUP BY status"
        ).fetchall()
        by_status = {r["status"]: r["cnt"] for r in by_status_rows}

        by_component_rows = self._conn.execute(
            "SELECT component, COUNT(*) as cnt FROM health_checks GROUP BY component"
        ).fetchall()
        by_component = {r["component"]: r["cnt"] for r in by_component_rows}

        return {
            "mode": self.get_mode(),
            "health_score": self.get_health_score(),
            "should_shutdown": self.should_shutdown(),
            "total_checks": total_checks,
            "by_status": by_status,
            "by_component": by_component,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.self_preservation",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: SelfPreservationEngine | None = None


def get_self_preservation_engine(db_path: str | Path | None = None,
                                 event_bus: EventBus | None = None) -> SelfPreservationEngine:
    global _engine
    if _engine is None:
        _engine = SelfPreservationEngine(db_path, event_bus)
    return _engine
