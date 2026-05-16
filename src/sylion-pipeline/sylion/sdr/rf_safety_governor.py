"""
SYLION SDR -- RFSafetyGovernor (N5)  [SAFETY CRITICAL]

RF transmission safety governor. Enforces band policies, TX permissions,
and regulatory compliance. DEFAULT: TX DISABLED everywhere until explicitly
enabled by Council approval.

SAFETY INVARIANT: is_tx_enabled() returns False until enable_tx_global()
is called with a valid Council approval string.

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

log = logging.getLogger("sylion.sdr.rf_safety_governor")


class RFSafetyGovernor:
    """RF transmission safety governor.

    SAFETY CRITICAL: TX is DISABLED by default. Only explicit Council
    approval via enable_tx_global() can enable transmission.
    """

    def __init__(self, db_path: str | Path | None = None, event_bus=None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._tx_enabled = False  # SAFETY: default OFF
        self._create_tables()

    def _create_tables(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS rf_policies (
                    policy_id       TEXT PRIMARY KEY,
                    jurisdiction    TEXT NOT NULL,
                    band_start      REAL NOT NULL,
                    band_end        REAL NOT NULL,
                    max_power_dbm   REAL NOT NULL DEFAULT -10,
                    tx_allowed      INTEGER NOT NULL DEFAULT 0,
                    requires_council INTEGER NOT NULL DEFAULT 1
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS rf_events (
                    event_id     TEXT PRIMARY KEY,
                    sdr_id       TEXT NOT NULL,
                    mode         TEXT NOT NULL,
                    frequency    REAL NOT NULL,
                    power_dbm    REAL NOT NULL DEFAULT 0,
                    approved_by  TEXT NOT NULL DEFAULT '',
                    timestamp    REAL NOT NULL
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rf_policies_jur ON rf_policies(jurisdiction)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rf_policies_band ON rf_policies(band_start, band_end)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rf_events_sdr ON rf_events(sdr_id)"
            )
            self._conn.commit()

    def add_band_policy(self, policy_id: str, jurisdiction: str,
                        band_start: float, band_end: float,
                        max_power_dbm: float = -10,
                        tx_allowed: bool = False,
                        requires_council: bool = True) -> dict:
        """Add or replace an RF band policy."""
        tx_int = 1 if tx_allowed else 0
        council_int = 1 if requires_council else 0

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO rf_policies
                    (policy_id, jurisdiction, band_start, band_end,
                     max_power_dbm, tx_allowed, requires_council)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (policy_id, jurisdiction, band_start, band_end,
                  max_power_dbm, tx_int, council_int))
            self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM rf_policies WHERE policy_id = ?", (policy_id,)
        ).fetchone()
        result = dict(row)

        self._emit("sdr.rf.policy_added", {
            "policy_id": policy_id, "jurisdiction": jurisdiction,
            "band_start": band_start, "band_end": band_end,
        })
        log.info("added RF policy %s for %s (%.0f-%.0f Hz)",
                 policy_id, jurisdiction, band_start, band_end)
        return result

    def check_tx_allowed(self, frequency: float, power_dbm: float,
                         jurisdiction: str = "PL") -> dict:
        """Check if TX is allowed at given frequency/power in jurisdiction.

        Returns {"allowed": bool, "reason": str}.
        """
        # First check global TX gate
        if not self._tx_enabled:
            return {"allowed": False, "reason": "TX globally disabled"}

        # Find matching band policies
        rows = self._conn.execute("""
            SELECT * FROM rf_policies
            WHERE jurisdiction = ? AND band_start <= ? AND band_end >= ?
        """, (jurisdiction, frequency, frequency)).fetchall()

        if not rows:
            return {"allowed": False,
                    "reason": f"no policy for {frequency} Hz in {jurisdiction}"}

        # Check all matching policies
        for row in rows:
            policy = dict(row)
            if not policy["tx_allowed"]:
                return {"allowed": False,
                        "reason": f"TX not allowed in this band (policy {policy['policy_id']})"}
            if power_dbm > policy["max_power_dbm"]:
                return {"allowed": False,
                        "reason": f"power {power_dbm} dBm exceeds limit {policy['max_power_dbm']} dBm"}

        return {"allowed": True, "reason": "permitted by band policy"}

    def record_tx(self, sdr_id: str, frequency: float, power_dbm: float,
                  approved_by: str = "") -> dict:
        """Record a TX event. Returns event record."""
        event_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO rf_events
                    (event_id, sdr_id, mode, frequency, power_dbm, approved_by, timestamp)
                VALUES (?, ?, 'TX', ?, ?, ?, ?)
            """, (event_id, sdr_id, frequency, power_dbm, approved_by, now))
            self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM rf_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        result = dict(row)

        self._emit("sdr.rf.tx", {
            "event_id": event_id, "sdr_id": sdr_id,
            "frequency": frequency, "power_dbm": power_dbm,
            "approved_by": approved_by,
        })
        log.warning("RF TX recorded: sdr=%s freq=%.0f power=%.1f dBm approved=%s",
                     sdr_id, frequency, power_dbm, approved_by or "NONE")
        return result

    def enable_tx_global(self, enabled_by: str) -> dict:
        """Enable global TX. Requires Council approval string.

        SAFETY: enabled_by must be a non-empty Council approval identifier.
        """
        if not enabled_by or not enabled_by.strip():
            return {"error": "Council approval required to enable TX",
                    "enabled": False}

        self._tx_enabled = True
        self._emit("sdr.rf.tx_enabled", {
            "enabled": True, "enabled_by": enabled_by,
        })
        log.warning("RF TX GLOBALLY ENABLED by: %s", enabled_by)
        return {"enabled": True, "enabled_by": enabled_by}

    def is_tx_enabled(self) -> bool:
        """Check if global TX is enabled.

        SAFETY INVARIANT: Returns False by default.
        """
        return self._tx_enabled

    def get_policies(self, jurisdiction: str | None = None) -> list[dict]:
        """Get RF band policies, optionally filtered by jurisdiction."""
        if jurisdiction:
            rows = self._conn.execute(
                "SELECT * FROM rf_policies WHERE jurisdiction = ? ORDER BY band_start",
                (jurisdiction,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM rf_policies ORDER BY jurisdiction, band_start"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_events(self, sdr_id: str | None = None,
                   limit: int = 100) -> list[dict]:
        """Get TX events, optionally filtered by SDR."""
        if sdr_id:
            rows = self._conn.execute(
                "SELECT * FROM rf_events WHERE sdr_id = ? ORDER BY timestamp DESC LIMIT ?",
                (sdr_id, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM rf_events ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="sdr.rf_safety_governor",
            ))


_var: RFSafetyGovernor | None = None


def get_rf_safety_governor(db_path=None, event_bus=None):
    global _var
    if _var is None:
        _var = RFSafetyGovernor(db_path, event_bus)
    return _var
