"""
SYLION SDR -- SDRGateway (N1)

Central registry for SDR devices. Tracks device capabilities,
availability status, and driver configuration.
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

log = logging.getLogger("sylion.sdr.sdr_gateway")


class SDRGateway:
    """Central registry for SDR devices."""

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
                CREATE TABLE IF NOT EXISTS sdr_devices (
                    sdr_id          TEXT PRIMARY KEY,
                    device_type     TEXT NOT NULL DEFAULT '',
                    driver          TEXT NOT NULL DEFAULT 'soapysdr',
                    freq_min        REAL NOT NULL DEFAULT 0,
                    freq_max        REAL NOT NULL DEFAULT 6e9,
                    sample_rate_max REAL NOT NULL DEFAULT 2e6,
                    tx_capable      INTEGER NOT NULL DEFAULT 0,
                    status          TEXT NOT NULL DEFAULT 'available'
                )
            """)
            self._conn.commit()

    def register_sdr(self, sdr_id: str, device_type: str,
                     driver: str = "soapysdr", freq_min: float = 0,
                     freq_max: float = 6e9, sample_rate_max: float = 2e6,
                     tx_capable: bool = False) -> dict:
        """Register a new SDR device. Returns device record."""
        now = time.time()
        tx_int = 1 if tx_capable else 0
        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO sdr_devices
                    (sdr_id, device_type, driver, freq_min, freq_max,
                     sample_rate_max, tx_capable, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'available')
            """, (sdr_id, device_type, driver, freq_min, freq_max,
                  sample_rate_max, tx_int))
            self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM sdr_devices WHERE sdr_id = ?", (sdr_id,)
        ).fetchone()

        result = dict(row)
        self._emit("sdr.device.registered", {"sdr_id": sdr_id, "device_type": device_type})
        log.info("registered SDR: %s (%s)", sdr_id, device_type)
        return result

    def get_capabilities(self, sdr_id: str) -> dict | None:
        """Get capabilities of a specific SDR device."""
        row = self._conn.execute(
            "SELECT * FROM sdr_devices WHERE sdr_id = ?", (sdr_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_sdrs(self, status: str | None = None) -> list[dict]:
        """List SDR devices, optionally filtered by status."""
        if status:
            rows = self._conn.execute(
                "SELECT * FROM sdr_devices WHERE status = ? ORDER BY sdr_id",
                (status,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM sdr_devices ORDER BY sdr_id"
            ).fetchall()
        return [dict(r) for r in rows]

    def check_available(self, sdr_id: str) -> bool:
        """Check if an SDR device is available."""
        row = self._conn.execute(
            "SELECT status FROM sdr_devices WHERE sdr_id = ?", (sdr_id,)
        ).fetchone()
        return row is not None and row["status"] == "available"

    def update_status(self, sdr_id: str, status: str) -> dict | None:
        """Update SDR device status. Returns updated record or None."""
        with self._lock:
            existing = self._conn.execute(
                "SELECT sdr_id FROM sdr_devices WHERE sdr_id = ?", (sdr_id,)
            ).fetchone()
            if not existing:
                return None
            self._conn.execute(
                "UPDATE sdr_devices SET status = ? WHERE sdr_id = ?",
                (status, sdr_id)
            )
            self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM sdr_devices WHERE sdr_id = ?", (sdr_id,)
        ).fetchone()
        self._emit("sdr.device.status_changed", {"sdr_id": sdr_id, "status": status})
        return dict(row) if row else None

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="sdr.sdr_gateway",
            ))


_var: SDRGateway | None = None


def get_sdr_gateway(db_path=None, event_bus=None):
    global _var
    if _var is None:
        _var = SDRGateway(db_path, event_bus)
    return _var
