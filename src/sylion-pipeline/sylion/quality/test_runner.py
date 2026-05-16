"""
SYLION Quality — Test Runner

Test execution orchestration. Manages test suites and records
per-suite run history with pass/fail/skip counts and duration.

SQLite-backed, thread-safe, event-emitting.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.quality.test_runner")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TestSuite:
    """A test suite definition."""
    suite_id: str = ""
    name: str = ""
    description: str = ""
    test_type: str = "unit"
    module_id: str = ""
    test_count: int = 0
    active: int = 1
    created_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class TestRun:
    """A single execution of a test suite."""
    run_id: str = ""
    suite_id: str = ""
    status: str = "pending"
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_ms: int = 0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.run_id:
            self.run_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# TestRunner
# ---------------------------------------------------------------------------

class TestRunner:
    """Test execution orchestration.

    Thread-safe. SQLite-backed. Emits events on create_suite / run_suite.
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
            CREATE TABLE IF NOT EXISTS test_suites (
                suite_id    TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                test_type   TEXT NOT NULL DEFAULT 'unit',
                module_id   TEXT NOT NULL DEFAULT '',
                test_count  INTEGER NOT NULL DEFAULT 0,
                active      INTEGER NOT NULL DEFAULT 1,
                created_at  REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS test_runs (
                run_id      TEXT PRIMARY KEY,
                suite_id    TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                total       INTEGER NOT NULL DEFAULT 0,
                passed      INTEGER NOT NULL DEFAULT 0,
                failed      INTEGER NOT NULL DEFAULT 0,
                skipped     INTEGER NOT NULL DEFAULT 0,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                timestamp   REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ts_module ON test_suites(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ts_active ON test_suites(active)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tr_suite ON test_runs(suite_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tr_ts ON test_runs(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Suite management
    # ------------------------------------------------------------------

    def create_suite(self, suite_id: str, name: str, description: str = "",
                     test_type: str = "unit", module_id: str = "",
                     test_count: int = 0) -> dict:
        """Create a new test suite."""
        suite = TestSuite(
            suite_id=suite_id,
            name=name,
            description=description,
            test_type=test_type,
            module_id=module_id,
            test_count=test_count,
        )

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO test_suites
                (suite_id, name, description, test_type, module_id,
                 test_count, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                suite.suite_id, suite.name, suite.description,
                suite.test_type, suite.module_id, suite.test_count,
                suite.created_at,
            ))
            self._conn.commit()

        self._emit("test_suite.created", {
            "suite_id": suite_id, "name": name, "module_id": module_id,
        })
        log.info("created test suite %s: %s (%d tests)", suite_id, name, test_count)
        return {
            "suite_id": suite_id, "name": name, "test_count": test_count,
        }

    # ------------------------------------------------------------------
    # Run suite
    # ------------------------------------------------------------------

    def run_suite(self, suite_id: str) -> dict:
        """Execute a test suite (stub). Returns pass/fail dict."""
        row = self._conn.execute(
            "SELECT * FROM test_suites WHERE suite_id = ? AND active = 1",
            (suite_id,),
        ).fetchone()
        if not row:
            return {"run": False, "message": f"Suite {suite_id} not found or inactive"}

        test_count = row["test_count"]
        start = time.monotonic()

        # Stub execution: all tests pass for now
        total = test_count if test_count > 0 else 0
        passed = total
        failed = 0
        skipped = 0
        duration_ms = int((time.monotonic() - start) * 1000)
        status = "passed" if failed == 0 else "failed"

        run = TestRun(
            suite_id=suite_id,
            status=status,
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration_ms=duration_ms,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO test_runs
                (run_id, suite_id, status, total, passed, failed,
                 skipped, duration_ms, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.run_id, run.suite_id, run.status, run.total,
                run.passed, run.failed, run.skipped,
                run.duration_ms, run.timestamp,
            ))
            self._conn.commit()

        self._emit("test_suite.run_completed", {
            "run_id": run.run_id, "suite_id": suite_id,
            "status": status, "passed": passed, "failed": failed,
        })
        log.info("suite %s run %s: %s (%d/%d passed, %dms)",
                 suite_id, run.run_id[:12], status, passed, total, duration_ms)
        return {
            "run": True,
            "run_id": run.run_id,
            "suite_id": suite_id,
            "status": status,
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "duration_ms": duration_ms,
        }

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_run(self, run_id: str) -> dict | None:
        """Retrieve a single test run by ID."""
        row = self._conn.execute(
            "SELECT * FROM test_runs WHERE run_id = ?", (run_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_suites(self, module_id: str | None = None,
                    active_only: bool = True) -> list[dict]:
        """List test suites, optionally filtered by module and active status."""
        q = "SELECT * FROM test_suites WHERE 1=1"
        params: list[Any] = []
        if module_id:
            q += " AND module_id = ?"
            params.append(module_id)
        if active_only:
            q += " AND active = 1"
        q += " ORDER BY created_at DESC"
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def list_runs(self, suite_id: str | None = None,
                  limit: int = 100) -> list[dict]:
        """List test runs, optionally filtered by suite."""
        q = "SELECT * FROM test_runs WHERE 1=1"
        params: list[Any] = []
        if suite_id:
            q += " AND suite_id = ?"
            params.append(suite_id)
        q += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def get_latest_run(self, suite_id: str) -> dict | None:
        """Get the most recent run for a suite."""
        row = self._conn.execute(
            "SELECT * FROM test_runs WHERE suite_id = ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (suite_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_stats(self) -> dict:
        """Aggregate test runner statistics."""
        suite_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM test_suites"
        ).fetchone()["cnt"]

        run_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM test_runs"
        ).fetchone()["cnt"]

        pass_row = self._conn.execute(
            "SELECT SUM(passed) as p, SUM(failed) as f, "
            "SUM(skipped) as s, SUM(total) as t FROM test_runs"
        ).fetchone()

        total_passed = pass_row["p"] if pass_row and pass_row["p"] else 0
        total_failed = pass_row["f"] if pass_row and pass_row["f"] else 0
        total_skipped = pass_row["s"] if pass_row and pass_row["s"] else 0
        total_tests = pass_row["t"] if pass_row and pass_row["t"] else 0

        status_rows = self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM test_runs GROUP BY status"
        ).fetchall()
        by_status = {r["status"]: r["cnt"] for r in status_rows}

        return {
            "suite_count": suite_count,
            "run_count": run_count,
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_skipped": total_skipped,
            "by_status": by_status,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="quality.test_runner",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_runner: TestRunner | None = None


def get_test_runner(event_bus: EventBus | None = None,
                    db_path: str | Path | None = None) -> TestRunner:
    global _runner
    if _runner is None:
        _runner = TestRunner(event_bus, db_path)
    return _runner
