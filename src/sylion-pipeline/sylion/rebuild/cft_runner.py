"""
SYLION Rebuild -- Canonical Fidelity Test (CFT) Runner

Runs canonical fidelity tests comparing golden hashes against actual outputs.
Tracks suite definitions and test results with fidelity scoring.

SQLite-backed. Thread-safe. Emits events via EventBus.
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

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.rebuild.cft_runner")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CFTSuite:
    """A canonical fidelity test suite."""
    suite_id: str = ""
    name: str = ""
    description: str = ""
    module_id: str = ""
    active: int = 1
    created_at: float = 0.0

    def __post_init__(self):
        if not self.suite_id:
            self.suite_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class CFTResult:
    """A single CFT test result."""
    result_id: str = ""
    suite_id: str = ""
    golden_hash: str = ""
    actual_hash: str = ""
    fidelity_score: float = 0.0
    passed: int = 0
    duration_ms: int = 0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.result_id:
            self.result_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# CFT Runner
# ---------------------------------------------------------------------------

class CFTRunner:
    """Canonical Fidelity Test runner.

    Thread-safe. SQLite-backed. Emits events to EventBus.
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

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cft_suites (
                suite_id    TEXT PRIMARY KEY,
                name        TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                module_id   TEXT NOT NULL DEFAULT '',
                active      INTEGER NOT NULL DEFAULT 1,
                created_at  REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cft_results (
                result_id      TEXT PRIMARY KEY,
                suite_id       TEXT NOT NULL,
                golden_hash    TEXT NOT NULL DEFAULT '',
                actual_hash    TEXT NOT NULL DEFAULT '',
                fidelity_score REAL NOT NULL DEFAULT 0.0,
                passed         INTEGER NOT NULL DEFAULT 0,
                duration_ms    INTEGER NOT NULL DEFAULT 0,
                timestamp      REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cftres_suite ON cft_results(suite_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cftsuites_mod ON cft_suites(module_id)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Suite management
    # ------------------------------------------------------------------

    def create_suite(self, name: str, description: str = "",
                     module_id: str = "") -> dict:
        """Create a new CFT suite. Returns suite descriptor dict."""
        suite = CFTSuite(
            name=name,
            description=description,
            module_id=module_id,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO cft_suites
                    (suite_id, name, description, module_id, active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (
                suite.suite_id, suite.name, suite.description,
                suite.module_id, suite.created_at,
            ))
            self._conn.commit()

        self._emit("rebuild.cft.suite_created", {
            "suite_id": suite.suite_id, "name": name, "module_id": module_id,
        })

        log.info("created CFT suite %s (%s)", suite.suite_id[:12], name)
        return {"suite_id": suite.suite_id, "name": name}

    # ------------------------------------------------------------------
    # Test execution
    # ------------------------------------------------------------------

    def run_test(self, suite_id: str, golden_hash: str,
                 actual_hash: str = "", duration_ms: int = 0) -> dict:
        """Run a CFT test (stub). Compares hashes and records the result.

        If actual_hash is not provided, generates a stub that matches,
        resulting in fidelity_score=1.0.
        """
        if not actual_hash:
            actual_hash = golden_hash

        passed = 1 if golden_hash == actual_hash else 0
        fidelity_score = 1.0 if passed else 0.0

        result = CFTResult(
            suite_id=suite_id,
            golden_hash=golden_hash,
            actual_hash=actual_hash,
            fidelity_score=fidelity_score,
            passed=passed,
            duration_ms=duration_ms,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO cft_results
                    (result_id, suite_id, golden_hash, actual_hash,
                     fidelity_score, passed, duration_ms, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.result_id, result.suite_id, result.golden_hash,
                result.actual_hash, result.fidelity_score, result.passed,
                result.duration_ms, result.timestamp,
            ))
            self._conn.commit()

        self._emit("rebuild.cft.test_completed", {
            "result_id": result.result_id, "suite_id": suite_id,
            "passed": bool(passed), "fidelity_score": fidelity_score,
        })

        log.info("CFT test %s: passed=%s fidelity=%.2f",
                 result.result_id[:12], bool(passed), fidelity_score)
        return {
            "result_id": result.result_id,
            "suite_id": suite_id,
            "passed": bool(passed),
            "fidelity_score": fidelity_score,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_results(self, suite_id: str, limit: int = 100) -> list[dict]:
        """Get test results for a suite."""
        rows = self._conn.execute(
            "SELECT * FROM cft_results WHERE suite_id = ? ORDER BY timestamp DESC LIMIT ?",
            (suite_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_pass_rate(self, suite_id: str) -> dict:
        """Calculate pass rate for a suite."""
        row = self._conn.execute(
            "SELECT COUNT(*) as total, SUM(passed) as passed FROM cft_results WHERE suite_id = ?",
            (suite_id,),
        ).fetchone()
        if not row or row["total"] == 0:
            return {"suite_id": suite_id, "total": 0, "passed": 0, "pass_rate": 0.0}
        total = row["total"]
        passed = row["passed"] or 0
        return {
            "suite_id": suite_id,
            "total": total,
            "passed": passed,
            "pass_rate": round(passed / total, 4),
        }

    def list_suites(self, module_id: str | None = None,
                    active_only: bool = True,
                    limit: int = 100) -> list[dict]:
        """List CFT suites, optionally filtered by module and/or active status."""
        query = "SELECT * FROM cft_suites WHERE 1=1"
        params: list[Any] = []
        if module_id:
            query += " AND module_id = ?"
            params.append(module_id)
        if active_only:
            query += " AND active = 1"
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="rebuild.cft_runner",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_runner: CFTRunner | None = None


def get_cft_runner(db_path: str | Path | None = None,
                   event_bus: EventBus | None = None) -> CFTRunner:
    global _runner
    if _runner is None:
        _runner = CFTRunner(db_path, event_bus)
    return _runner
