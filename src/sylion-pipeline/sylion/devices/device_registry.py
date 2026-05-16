"""
SYLION Devices -- Device Registry (M2)

Manages the device lifecycle: attached -> identified -> quarantined ->
authorized -> provisioned -> active -> released.

Validates lifecycle transitions and emits events on state changes.
"""

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.devices.device_registry")

# Valid lifecycle states in order
LIFECYCLE_STATES = [
    "attached", "identified", "quarantined", "authorized",
    "provisioned", "active", "released",
]

# Valid forward transitions: state -> set of allowed next states
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "attached":    {"identified", "released"},
    "identified":  {"quarantined", "released"},
    "quarantined": {"authorized", "released"},
    "authorized":  {"provisioned", "released"},
    "provisioned": {"active", "released"},
    "active":      {"released"},
    "released":    set(),  # terminal state
}


class DeviceRegistry:
    """Device lifecycle registry with transition validation."""

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
                CREATE TABLE IF NOT EXISTS devices (
                    device_id      TEXT PRIMARY KEY,
                    transport      TEXT NOT NULL DEFAULT '',
                    model          TEXT NOT NULL DEFAULT '',
                    firmware       TEXT NOT NULL DEFAULT '',
                    capabilities   TEXT NOT NULL DEFAULT '{}',
                    lifecycle      TEXT NOT NULL DEFAULT 'attached',
                    authorized_by  TEXT NOT NULL DEFAULT '',
                    registered_at  REAL NOT NULL
                )
            """)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Register / Get
    # ------------------------------------------------------------------

    def register(self, device_id: str, transport: str, model: str,
                 firmware: str = "", capabilities: dict | None = None) -> dict:
        """Register a new device. Initial lifecycle is 'attached'."""
        if capabilities is None:
            capabilities = {}
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO devices
                (device_id, transport, model, firmware, capabilities,
                 lifecycle, authorized_by, registered_at)
                VALUES (?, ?, ?, ?, ?, 'attached', '', ?)
            """, (device_id, transport, model, firmware,
                  json.dumps(capabilities), now))
            self._conn.commit()

        self._emit("device.registered", {
            "device_id": device_id,
            "transport": transport,
            "model": model,
        })

        log.info("registered device %s (transport=%s, model=%s)",
                 device_id, transport, model)
        return self.get(device_id)

    def get(self, device_id: str) -> dict | None:
        """Get a single device by ID."""
        row = self._conn.execute(
            "SELECT * FROM devices WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["capabilities"] = json.loads(result.get("capabilities", "{}"))
        return result

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def transition(self, device_id: str, lifecycle: str) -> dict:
        """Transition a device to a new lifecycle state.

        Validates that the transition is allowed.
        Raises ValueError for invalid transitions or unknown devices.
        """
        if lifecycle not in LIFECYCLE_STATES:
            raise ValueError(f"Unknown lifecycle state: {lifecycle}")

        device = self.get(device_id)
        if not device:
            raise ValueError(f"Device not found: {device_id}")

        current = device["lifecycle"]
        if lifecycle not in _VALID_TRANSITIONS.get(current, set()):
            raise ValueError(
                f"Invalid transition: {current} -> {lifecycle}"
            )

        with self._lock:
            self._conn.execute(
                "UPDATE devices SET lifecycle = ? WHERE device_id = ?",
                (lifecycle, device_id),
            )
            self._conn.commit()

        self._emit("device.lifecycle.changed", {
            "device_id": device_id,
            "from": current,
            "to": lifecycle,
        })

        log.info("device %s transitioned: %s -> %s", device_id, current, lifecycle)
        return self.get(device_id)

    # ------------------------------------------------------------------
    # Authorize
    # ------------------------------------------------------------------

    def authorize(self, device_id: str, authorized_by: str) -> dict:
        """Authorize a quarantined device. Transitions quarantined -> authorized."""
        device = self.get(device_id)
        if not device:
            raise ValueError(f"Device not found: {device_id}")
        if device["lifecycle"] != "quarantined":
            raise ValueError(
                f"Device must be quarantined to authorize, got: {device['lifecycle']}"
            )

        with self._lock:
            self._conn.execute(
                "UPDATE devices SET lifecycle = 'authorized', authorized_by = ? WHERE device_id = ?",
                (authorized_by, device_id),
            )
            self._conn.commit()

        self._emit("device.authorized", {
            "device_id": device_id,
            "authorized_by": authorized_by,
        })

        log.info("device %s authorized by %s", device_id, authorized_by)
        return self.get(device_id)

    # ------------------------------------------------------------------
    # List / Stats
    # ------------------------------------------------------------------

    def list_devices(self, lifecycle: str | None = None) -> list[dict]:
        """List devices, optionally filtered by lifecycle state."""
        query = "SELECT * FROM devices WHERE 1=1"
        params: list[Any] = []
        if lifecycle is not None:
            query += " AND lifecycle = ?"
            params.append(lifecycle)
        query += " ORDER BY registered_at DESC"

        rows = self._conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["capabilities"] = json.loads(d.get("capabilities", "{}"))
            results.append(d)
        return results

    def get_stats(self) -> dict:
        """Count devices by lifecycle state."""
        rows = self._conn.execute(
            "SELECT lifecycle, COUNT(*) as cnt FROM devices GROUP BY lifecycle"
        ).fetchall()
        counts = {r["lifecycle"]: r["cnt"] for r in rows}

        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM devices"
        ).fetchone()["cnt"]

        return {
            "total": total,
            "by_lifecycle": counts,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="devices.device_registry",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_var: DeviceRegistry | None = None


def get_device_registry(db_path=None, event_bus=None):
    global _var
    if _var is None:
        _var = DeviceRegistry(db_path, event_bus)
    return _var
