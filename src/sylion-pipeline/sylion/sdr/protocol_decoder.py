"""
SYLION SDR -- ProtocolDecoder (N4)

Decodes captured SDR data into protocol-specific messages.
Supported protocols: ADS-B, POCSAG, LoRa, APRS, RDS, WiFi, BLE.
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

log = logging.getLogger("sylion.sdr.protocol_decoder")

SUPPORTED_PROTOCOLS = ["adsb", "pocsag", "lora", "aprs", "rds", "wifi", "ble"]

# Stub decoded messages per protocol for testing
_STUB_MESSAGES = {
    "adsb": [
        {"icao": "4D2235", "callsign": "RYR1234", "altitude_ft": 35000,
         "speed_kts": 450, "lat": 52.0, "lon": 21.0},
    ],
    "pocsag": [
        {"address": 1234567, "function": 0, "message": "TEST PAGE", "alpha": True},
    ],
    "lora": [
        {"spreading_factor": 7, "bandwidth": 125, "payload_hex": "AABBCCDD",
         "rssi": -45, "snr": 8.2},
    ],
    "aprs": [
        {"source": "SP5ABC", "destination": "APRS", "path": "WIDE1-1",
         "data_type": "position", "lat": 52.2297, "lon": 21.0122},
    ],
    "rds": [
        {"station_name": "PR1", "program_type": "Pop Music",
         "frequency_khz": 87500, "pi_code": "P2001"},
    ],
    "wifi": [
        {"bssid": "AA:BB:CC:DD:EE:FF", "ssid": "TestNetwork",
         "channel": 6, "encryption": "WPA2", "rssi": -55},
    ],
    "ble": [
        {"address": "11:22:33:44:55:66", "name": "BLE_Device",
         "rssi": -60, "service_uuid": "180F"},
    ],
}


class ProtocolDecoder:
    """Decodes captured SDR data into protocol-specific messages."""

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
                CREATE TABLE IF NOT EXISTS decoded_protocols (
                    decode_id  TEXT PRIMARY KEY,
                    capture_id TEXT NOT NULL,
                    protocol   TEXT NOT NULL,
                    messages   TEXT NOT NULL DEFAULT '[]',
                    stats      TEXT NOT NULL DEFAULT '{}',
                    decoded_at REAL NOT NULL
                )
            """)
            self._conn.commit()

    def decode(self, capture_id: str, protocol: str) -> dict:
        """Decode captured data for a given protocol. Returns stub result."""
        protocol = protocol.lower()
        if protocol not in SUPPORTED_PROTOCOLS:
            return {"error": f"unsupported protocol: {protocol}",
                    "supported": SUPPORTED_PROTOCOLS}

        decode_id = uuid.uuid4().hex
        now = time.time()

        messages = _STUB_MESSAGES.get(protocol, [])
        stats = {
            "total_messages": len(messages),
            "protocol": protocol,
            "status": "stub",
            "decode_time_ms": 42,
        }

        with self._lock:
            self._conn.execute("""
                INSERT INTO decoded_protocols
                    (decode_id, capture_id, protocol, messages, stats, decoded_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (decode_id, capture_id, protocol,
                  json.dumps(messages), json.dumps(stats), now))
            self._conn.commit()

        result = {
            "decode_id": decode_id,
            "capture_id": capture_id,
            "protocol": protocol,
            "messages": messages,
            "stats": stats,
            "decoded_at": now,
        }

        self._emit("sdr.protocol.decoded", {
            "decode_id": decode_id, "capture_id": capture_id,
            "protocol": protocol, "message_count": len(messages),
        })
        log.info("decoded %s from capture %s: %d messages",
                 protocol, capture_id, len(messages))
        return result

    def get(self, decode_id: str) -> dict | None:
        """Get a decode result by ID."""
        row = self._conn.execute(
            "SELECT * FROM decoded_protocols WHERE decode_id = ?", (decode_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["messages"] = json.loads(result["messages"])
        result["stats"] = json.loads(result["stats"])
        return result

    def list_decodes(self, capture_id: str | None = None,
                     limit: int = 100) -> list[dict]:
        """List decode results, optionally filtered by capture."""
        if capture_id:
            rows = self._conn.execute(
                "SELECT * FROM decoded_protocols WHERE capture_id = ? ORDER BY decoded_at DESC LIMIT ?",
                (capture_id, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM decoded_protocols ORDER BY decoded_at DESC LIMIT ?",
                (limit,)
            ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["messages"] = json.loads(d["messages"])
            d["stats"] = json.loads(d["stats"])
            results.append(d)
        return results

    def list_protocols(self) -> list[str]:
        """Return list of supported protocols."""
        return list(SUPPORTED_PROTOCOLS)

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="sdr.protocol_decoder",
            ))


_var: ProtocolDecoder | None = None


def get_protocol_decoder(db_path=None, event_bus=None):
    global _var
    if _var is None:
        _var = ProtocolDecoder(db_path, event_bus)
    return _var
