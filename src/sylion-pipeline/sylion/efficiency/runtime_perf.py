"""
SYLION Efficiency -- Runtime Performance Tracker

Performance monitoring and SLO tracking per endpoint.
Records latency measurements and percentile breakpoints, stores SLO
definitions, and validates observed performance against targets.

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.efficiency.runtime_perf")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PerfMeasurement:
    """A single performance measurement for an endpoint."""
    measurement_id: str = ""
    endpoint: str = ""
    latency_ms: int = 0
    p50_ms: int = 0
    p95_ms: int = 0
    p99_ms: int = 0
    error_rate: float = 0.0
    throughput_rps: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.measurement_id:
            self.measurement_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class SLODefinition:
    """Service-Level Objective for an endpoint."""
    slo_id: str = ""
    endpoint: str = ""
    target_p95_ms: int = 100
    target_error_rate: float = 0.01
    description: str = ""

    def __post_init__(self):
        if not self.slo_id:
            self.slo_id = uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Runtime Performance Tracker
# ---------------------------------------------------------------------------

class RuntimePerfTracker:
    """Performance monitoring and SLO tracking.

    Thread-safe. SQLite-backed. Emits events on record / SLO-check operations.
    """

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
            CREATE TABLE IF NOT EXISTS perf_measurements (
                measurement_id TEXT PRIMARY KEY,
                endpoint       TEXT    NOT NULL DEFAULT '',
                latency_ms     INTEGER NOT NULL DEFAULT 0,
                p50_ms         INTEGER NOT NULL DEFAULT 0,
                p95_ms         INTEGER NOT NULL DEFAULT 0,
                p99_ms         INTEGER NOT NULL DEFAULT 0,
                error_rate     REAL    NOT NULL DEFAULT 0.0,
                throughput_rps REAL    NOT NULL DEFAULT 0.0,
                timestamp      REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS slo_definitions (
                slo_id             TEXT PRIMARY KEY,
                endpoint           TEXT    NOT NULL DEFAULT '',
                target_p95_ms      INTEGER NOT NULL DEFAULT 100,
                target_error_rate  REAL    NOT NULL DEFAULT 0.01,
                description        TEXT    NOT NULL DEFAULT ''
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pm_endpoint ON perf_measurements(endpoint)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pm_ts ON perf_measurements(timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_slo_endpoint ON slo_definitions(endpoint)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Record measurement
    # ------------------------------------------------------------------

    def record(self, endpoint: str, latency_ms: int,
               p50: int = 0, p95: int = 0, p99: int = 0,
               error_rate: float = 0.0, throughput: float = 0.0) -> dict:
        """Record a performance measurement for *endpoint*.

        Emits ``efficiency.runtime_perf.recorded``.
        """
        m = PerfMeasurement(
            endpoint=endpoint,
            latency_ms=latency_ms,
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99,
            error_rate=error_rate,
            throughput_rps=throughput,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO perf_measurements
                    (measurement_id, endpoint, latency_ms, p50_ms, p95_ms,
                     p99_ms, error_rate, throughput_rps, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m.measurement_id, m.endpoint, m.latency_ms, m.p50_ms,
                m.p95_ms, m.p99_ms, m.error_rate, m.throughput_rps,
                m.timestamp,
            ))
            self._conn.commit()

        self._emit("efficiency.runtime_perf.recorded", {
            "endpoint": endpoint,
            "latency_ms": latency_ms,
        })

        log.info("recorded perf for %s: latency=%dms", endpoint, latency_ms)
        return {
            "measurement_id": m.measurement_id,
            "endpoint": endpoint,
            "timestamp": m.timestamp,
        }

    # ------------------------------------------------------------------
    # SLO management
    # ------------------------------------------------------------------

    def define_slo(self, endpoint: str, target_p95_ms: int = 100,
                   target_error_rate: float = 0.01,
                   description: str = "") -> dict:
        """Define or replace the SLO for *endpoint*.

        Emits ``efficiency.runtime_perf.slo_defined``.
        """
        slo = SLODefinition(
            endpoint=endpoint,
            target_p95_ms=target_p95_ms,
            target_error_rate=target_error_rate,
            description=description,
        )

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO slo_definitions
                    (slo_id, endpoint, target_p95_ms, target_error_rate, description)
                VALUES (?, ?, ?, ?, ?)
            """, (
                slo.slo_id, slo.endpoint, slo.target_p95_ms,
                slo.target_error_rate, slo.description,
            ))
            self._conn.commit()

        self._emit("efficiency.runtime_perf.slo_defined", {
            "endpoint": endpoint,
            "target_p95_ms": target_p95_ms,
        })

        log.info("defined SLO for %s: p95<=%dms, err<=%.2f%%",
                 endpoint, target_p95_ms, target_error_rate * 100)
        return {
            "slo_id": slo.slo_id,
            "endpoint": endpoint,
        }

    def check_slo(self, endpoint: str) -> dict:
        """Check whether *endpoint* passes its defined SLO.

        Returns dict with keys: endpoint, pass (bool), target_p95_ms,
        target_error_rate, latest_p95_ms, latest_error_rate.
        """
        slo_row = self._conn.execute(
            "SELECT * FROM slo_definitions WHERE endpoint = ?",
            (endpoint,),
        ).fetchone()

        if slo_row is None:
            return {
                "endpoint": endpoint,
                "pass": True,
                "target_p95_ms": None,
                "target_error_rate": None,
                "latest_p95_ms": None,
                "latest_error_rate": None,
                "reason": "no_slo_defined",
            }

        perf_row = self._conn.execute(
            "SELECT p95_ms, error_rate FROM perf_measurements WHERE endpoint = ? ORDER BY timestamp DESC LIMIT 1",
            (endpoint,),
        ).fetchone()

        if perf_row is None:
            return {
                "endpoint": endpoint,
                "pass": True,
                "target_p95_ms": slo_row["target_p95_ms"],
                "target_error_rate": slo_row["target_error_rate"],
                "latest_p95_ms": None,
                "latest_error_rate": None,
                "reason": "no_measurements",
            }

        latest_p95 = perf_row["p95_ms"]
        latest_err = perf_row["error_rate"]
        passed = (latest_p95 <= slo_row["target_p95_ms"]
                  and latest_err <= slo_row["target_error_rate"])

        result = {
            "endpoint": endpoint,
            "pass": passed,
            "target_p95_ms": slo_row["target_p95_ms"],
            "target_error_rate": slo_row["target_error_rate"],
            "latest_p95_ms": latest_p95,
            "latest_error_rate": latest_err,
        }

        self._emit("efficiency.runtime_perf.slo_checked", result)
        log.info("SLO check %s: pass=%s (p95=%d, err=%.2f%%)",
                 endpoint, passed, latest_p95, latest_err * 100)
        return result

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_measurements(self, endpoint: str, limit: int = 100) -> list[dict]:
        """Return recent measurements for *endpoint*."""
        rows = self._conn.execute(
            "SELECT * FROM perf_measurements WHERE endpoint = ? ORDER BY timestamp DESC LIMIT ?",
            (endpoint, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_slos(self) -> list[dict]:
        """Return all defined SLOs."""
        rows = self._conn.execute(
            "SELECT * FROM slo_definitions ORDER BY endpoint"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self, endpoint: str) -> dict:
        """Return aggregate stats for *endpoint*."""
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt, AVG(latency_ms) as avg_latency, "
            "MIN(latency_ms) as min_latency, MAX(latency_ms) as max_latency, "
            "AVG(error_rate) as avg_error_rate, AVG(throughput_rps) as avg_throughput "
            "FROM perf_measurements WHERE endpoint = ?",
            (endpoint,),
        ).fetchone()
        if row is None or row["cnt"] == 0:
            return {"endpoint": endpoint, "count": 0}
        return {"endpoint": endpoint, **dict(row)}

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="efficiency.runtime_perf",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_tracker: RuntimePerfTracker | None = None


def get_runtime_perf_tracker(event_bus: EventBus | None = None,
                             db_path: str | Path | None = None) -> RuntimePerfTracker:
    global _tracker
    if _tracker is None:
        _tracker = RuntimePerfTracker(event_bus, db_path)
    return _tracker
