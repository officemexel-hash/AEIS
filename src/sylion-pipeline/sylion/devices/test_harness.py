"""
SYLION Devices -- On-Device Test Harness (M4)

Runs test suites on devices and tracks pass/fail results.
Supports contract, integration, and e2e test suites.
"""

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.devices.test_harness")


class OnDeviceTestHarness:
    """Runs and tracks on-device test suites."""

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
                CREATE TABLE IF NOT EXISTS device_tests (
                    test_id      TEXT PRIMARY KEY,
                    device_id    TEXT NOT NULL,
                    suite        TEXT NOT NULL DEFAULT 'contract',
                    status       TEXT NOT NULL DEFAULT 'running',
                    pass_rate    REAL NOT NULL DEFAULT 0.0,
                    logs_hash    TEXT NOT NULL DEFAULT '',
                    duration_ms  INTEGER NOT NULL DEFAULT 0,
                    ran_at       REAL NOT NULL
                )
            """)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Run test
    # ------------------------------------------------------------------

    def run_test(self, device_id: str, suite: str = "contract") -> dict:
        """Run a test suite on a device. Creates a stub PASS result.

        In production this would dispatch to the device; here it
        simulates a passing test with 100% pass rate.
        """
        test_id = f"tst-{uuid.uuid4().hex[:12]}"
        now = time.time()
        # Simulate test execution
        duration_ms = 150  # stub: 150ms
        status = "passed"
        pass_rate = 1.0
        logs_hash = uuid.uuid4().hex

        with self._lock:
            self._conn.execute("""
                INSERT INTO device_tests
                (test_id, device_id, suite, status, pass_rate,
                 logs_hash, duration_ms, ran_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (test_id, device_id, suite, status, pass_rate,
                  logs_hash, duration_ms, now))
            self._conn.commit()

        self._emit("device.test.completed", {
            "test_id": test_id,
            "device_id": device_id,
            "suite": suite,
            "status": status,
            "pass_rate": pass_rate,
        })

        log.info("test %s completed on device %s (suite=%s, status=%s)",
                 test_id, device_id, suite, status)
        return self.get_results(test_id)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_results(self, test_id: str) -> dict | None:
        """Get results for a single test by ID."""
        row = self._conn.execute(
            "SELECT * FROM device_tests WHERE test_id = ?",
            (test_id,),
        ).fetchone()
        if not row:
            return None
        return dict(row)

    def list_tests(self, device_id: str | None = None,
                   limit: int = 100) -> list[dict]:
        """List tests, optionally filtered by device_id."""
        query = "SELECT * FROM device_tests WHERE 1=1"
        params: list[Any] = []
        if device_id is not None:
            query += " AND device_id = ?"
            params.append(device_id)
        query += " ORDER BY ran_at DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self, device_id: str) -> dict:
        """Aggregate test statistics for a device."""
        total_row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM device_tests WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        total = total_row["cnt"] if total_row else 0

        passed_row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM device_tests WHERE device_id = ? AND status = 'passed'",
            (device_id,),
        ).fetchone()
        passed = passed_row["cnt"] if passed_row else 0

        failed = total - passed
        pass_rate = (passed / total) if total > 0 else 0.0

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="devices.test_harness",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_var: OnDeviceTestHarness | None = None


def get_on_device_test_harness(db_path=None, event_bus=None):
    global _var
    if _var is None:
        _var = OnDeviceTestHarness(db_path, event_bus)
    return _var
