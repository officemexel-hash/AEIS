"""
SYLION SDR -- CaptureOrchestrator (N2)

Manages SDR capture sessions: creation, start, stop lifecycle.
Validates TX mode against RF Safety Governor.
SQLite-backed. Thread-safe. Emits events via EventBus.
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

log = logging.getLogger("sylion.sdr.capture_orchestrator")


class CaptureOrchestrator:
    """Manages SDR capture sessions."""

    def __init__(self, db_path: str | Path | None = None, event_bus=None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS captures (
                    capture_id   TEXT PRIMARY KEY,
                    sdr_id       TEXT NOT NULL,
                    frequency    REAL NOT NULL,
                    sample_rate  REAL NOT NULL DEFAULT 2e6,
                    mode         TEXT NOT NULL DEFAULT 'RX',
                    status       TEXT NOT NULL DEFAULT 'created',
                    sigmf_data   TEXT NOT NULL DEFAULT '',
                    sigmf_meta   TEXT NOT NULL DEFAULT '{}',
                    duration_s   REAL NOT NULL DEFAULT 0,
                    created_at   REAL NOT NULL
                )
            """)
            self._conn.commit()

    def create_capture(self, sdr_id: str, frequency: float,
                       sample_rate: float = 2e6, mode: str = "RX",
                       duration_s: float = 60) -> dict:
        """Create a new capture session. Returns capture record."""
        capture_id = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO captures
                    (capture_id, sdr_id, frequency, sample_rate, mode,
                     status, sigmf_data, sigmf_meta, duration_s, created_at)
                VALUES (?, ?, ?, ?, ?, 'created', '', '{}', ?, ?)
            """, (capture_id, sdr_id, frequency, sample_rate, mode,
                  duration_s, now))
            self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM captures WHERE capture_id = ?", (capture_id,)
        ).fetchone()
        result = dict(row)

        self._emit("sdr.capture.created", {
            "capture_id": capture_id, "sdr_id": sdr_id,
            "frequency": frequency, "mode": mode,
        })
        log.info("created capture %s on SDR %s @ %.0f Hz", capture_id, sdr_id, frequency)
        return result

    def start(self, capture_id: str) -> dict:
        """Start a capture. Validates TX mode against RF Safety Governor."""
        row = self._conn.execute(
            "SELECT * FROM captures WHERE capture_id = ?", (capture_id,)
        ).fetchone()
        if not row:
            return {"error": "capture not found", "capture_id": capture_id}

        capture = dict(row)
        if capture["status"] not in ("created", "stopped"):
            return {"error": f"cannot start capture in status '{capture['status']}'",
                    "capture_id": capture_id}

        # RF safety check for TX mode
        if capture["mode"] == "TX":
            try:
                from sylion.sdr.rf_safety_governor import get_rf_safety_governor
                gov = get_rf_safety_governor()
                if not gov.is_tx_enabled():
                    return {"error": "TX blocked by RF Safety Governor (TX globally disabled)",
                            "capture_id": capture_id}
                tx_check = gov.check_tx_allowed(capture["frequency"], 0)
                if not tx_check.get("allowed", False):
                    return {"error": f"TX blocked: {tx_check.get('reason', 'policy denial')}",
                            "capture_id": capture_id}
            except Exception:
                # If governor is not available, block TX by default (safe fail)
                return {"error": "TX blocked: RF Safety Governor unavailable",
                        "capture_id": capture_id}

        with self._lock:
            self._conn.execute(
                "UPDATE captures SET status = 'running' WHERE capture_id = ?",
                (capture_id,)
            )
            self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM captures WHERE capture_id = ?", (capture_id,)
        ).fetchone()
        result = dict(row)
        self._emit("sdr.capture.started", {"capture_id": capture_id})
        log.info("started capture %s", capture_id)
        return result

    def stop(self, capture_id: str) -> dict:
        """Stop a running capture."""
        row = self._conn.execute(
            "SELECT * FROM captures WHERE capture_id = ?", (capture_id,)
        ).fetchone()
        if not row:
            return {"error": "capture not found", "capture_id": capture_id}

        capture = dict(row)
        if capture["status"] != "running":
            return {"error": f"cannot stop capture in status '{capture['status']}'",
                    "capture_id": capture_id}

        with self._lock:
            self._conn.execute(
                "UPDATE captures SET status = 'stopped' WHERE capture_id = ?",
                (capture_id,)
            )
            self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM captures WHERE capture_id = ?", (capture_id,)
        ).fetchone()
        result = dict(row)

        self._emit("sdr.capture.completed", {"capture_id": capture_id})
        log.info("stopped capture %s", capture_id)
        return result

    def get(self, capture_id: str) -> dict | None:
        """Get a capture by ID."""
        row = self._conn.execute(
            "SELECT * FROM captures WHERE capture_id = ?", (capture_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_captures(self, sdr_id: str | None = None,
                      limit: int = 100) -> list[dict]:
        """List captures, optionally filtered by SDR."""
        if sdr_id:
            rows = self._conn.execute(
                "SELECT * FROM captures WHERE sdr_id = ? ORDER BY created_at DESC LIMIT ?",
                (sdr_id, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM captures ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="sdr.capture_orchestrator",
            ))


_var: CaptureOrchestrator | None = None


def get_capture_orchestrator(db_path=None, event_bus=None):
    global _var
    if _var is None:
        _var = CaptureOrchestrator(db_path, event_bus)
    return _var
