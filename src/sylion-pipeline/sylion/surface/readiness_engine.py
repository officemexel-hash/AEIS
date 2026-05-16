"""
SYLION Surface -- Readiness Engine

Deterministic readiness + ML advisory.
Thread-safe. SQLite-backed. Emits events via EventBus.

Frozen decisions:
- Deterministic primary + ML advisory secondary
- Bootstrap bez tokena, localhost-bound
- Full event sourcing for readiness checks
- Frontend RBAC is UX only, backend enforcement required
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
from typing import Any, Callable

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.surface.readiness_engine")


@dataclass
class ReadinessCheck:
    check_id: str = ""
    module_id: str = ""
    check_type: str = "DEPENDENCY"
    status: str = "SKIP"
    message: str = ""
    details: dict = field(default_factory=dict)
    checked_at: float = 0.0

    def __post_init__(self):
        if not self.check_id:
            self.check_id = uuid.uuid4().hex
        if not self.checked_at:
            self.checked_at = time.time()


@dataclass
class ReadinessReport:
    report_id: str = ""
    module_id: str = ""
    overall_status: str = "NOT_READY"
    deterministic_score: float = 0.0
    ml_advisory: dict = field(default_factory=dict)
    generated_at: float = 0.0

    def __post_init__(self):
        if not self.report_id:
            self.report_id = uuid.uuid4().hex
        if not self.generated_at:
            self.generated_at = time.time()


class ReadinessEngine:
    """Deterministic readiness checks with ML advisory.

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
        self._check_registry: dict[str, dict[str, Callable]] = {}
        self._ml_advisories: dict[str, dict] = {}
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS readiness_checks_registry (
                check_id     TEXT PRIMARY KEY,
                module_id    TEXT NOT NULL,
                check_type   TEXT NOT NULL DEFAULT '',
                check_name   TEXT NOT NULL DEFAULT '',
                registered_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS readiness_reports (
                report_id           TEXT PRIMARY KEY,
                module_id           TEXT NOT NULL,
                overall_status      TEXT NOT NULL DEFAULT 'NOT_READY',
                deterministic_score REAL NOT NULL DEFAULT 0,
                ml_advisory         TEXT NOT NULL DEFAULT '{}',
                generated_at        REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS readiness_check_results (
                result_id  TEXT PRIMARY KEY,
                report_id  TEXT NOT NULL,
                check_type TEXT NOT NULL DEFAULT '',
                status     TEXT NOT NULL DEFAULT 'SKIP',
                message    TEXT NOT NULL DEFAULT '',
                details    TEXT NOT NULL DEFAULT '{}',
                checked_at REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rr_mod ON readiness_reports(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rcr_rep ON readiness_check_results(report_id)"
        )
        self._conn.commit()

    def register_check(self, module_id: str, check_type: str,
                       check_fn: Callable[[], tuple[str, str, dict]],
                       check_name: str = "") -> dict:
        """Register a readiness check function for a module."""
        if module_id not in self._check_registry:
            self._check_registry[module_id] = {}

        check_id = uuid.uuid4().hex
        self._check_registry[module_id][check_type] = check_fn

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO readiness_checks_registry
                    (check_id, module_id, check_type, check_name, registered_at)
                VALUES (?, ?, ?, ?, ?)
            """, (check_id, module_id, check_type, check_name or check_type, time.time()))
            self._conn.commit()

        log.info("registered check %s/%s for module %s",
                 check_type, check_id[:12], module_id)
        return {"check_id": check_id, "module_id": module_id, "check_type": check_type}

    def run_check(self, module_id: str, check_type: str) -> dict:
        """Run a specific check for a module."""
        checks = self._check_registry.get(module_id, {})
        fn = checks.get(check_type)
        if not fn:
            return {
                "module_id": module_id, "check_type": check_type,
                "status": "SKIP", "message": "check not registered",
            }

        try:
            status, message, details = fn()
        except Exception as e:
            status, message, details = "FAIL", str(e), {}

        return {
            "module_id": module_id, "check_type": check_type,
            "status": status, "message": message, "details": details,
        }

    def run_all_checks(self, module_id: str) -> list[dict]:
        """Run all registered checks for a module."""
        checks = self._check_registry.get(module_id, {})
        results = []
        for check_type in checks:
            result = self.run_check(module_id, check_type)
            results.append(result)
        return results

    def generate_report(self, module_id: str) -> dict:
        """Generate full readiness report with deterministic score."""
        check_results = self.run_all_checks(module_id)

        if not check_results:
            overall = "NOT_READY"
            score = 0.0
        else:
            pass_count = sum(1 for r in check_results if r["status"] == "PASS")
            warn_count = sum(1 for r in check_results if r["status"] == "WARN")
            total = len(check_results)
            score = round((pass_count + 0.5 * warn_count) / total, 4) if total else 0.0

            if score >= 1.0:
                overall = "READY"
            elif score >= 0.5:
                overall = "DEGRADED"
            else:
                overall = "NOT_READY"

        report = ReadinessReport(
            module_id=module_id,
            overall_status=overall,
            deterministic_score=score,
            ml_advisory=self._ml_advisories.get(module_id, {}),
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO readiness_reports
                    (report_id, module_id, overall_status,
                     deterministic_score, ml_advisory, generated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (report.report_id, module_id, overall,
                  score, json.dumps(report.ml_advisory), report.generated_at))

            for cr in check_results:
                self._conn.execute("""
                    INSERT INTO readiness_check_results
                        (result_id, report_id, check_type, status, message, details, checked_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (uuid.uuid4().hex, report.report_id, cr["check_type"],
                      cr["status"], cr["message"],
                      json.dumps(cr.get("details", {})), time.time()))
            self._conn.commit()

        self._emit("surface.readiness_engine.report_generated", {
            "report_id": report.report_id,
            "module_id": module_id,
            "overall_status": overall,
            "score": score,
        })

        log.info("generated report %s for %s: %s (%.2f)",
                 report.report_id[:12], module_id, overall, score)
        return {
            "report_id": report.report_id,
            "module_id": module_id,
            "overall_status": overall,
            "deterministic_score": score,
            "checks": len(check_results),
        }

    def get_report(self, report_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM readiness_reports WHERE report_id = ?",
            (report_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["ml_advisory"] = json.loads(d.get("ml_advisory", "{}"))

        results = self._conn.execute(
            "SELECT * FROM readiness_check_results WHERE report_id = ?",
            (report_id,),
        ).fetchall()
        d["check_results"] = []
        for r in results:
            cr = dict(r)
            cr["details"] = json.loads(cr.get("details", "{}"))
            d["check_results"].append(cr)
        return d

    def list_reports(self, module_id: str | None = None,
                     limit: int = 100) -> list[dict]:
        if module_id:
            rows = self._conn.execute(
                "SELECT * FROM readiness_reports WHERE module_id = ? ORDER BY generated_at DESC LIMIT ?",
                (module_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM readiness_reports ORDER BY generated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_report(self, module_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM readiness_reports WHERE module_id = ? ORDER BY generated_at DESC LIMIT 1",
            (module_id,),
        ).fetchone()
        if not row:
            return None
        return self.get_report(dict(row)["report_id"])

    def set_ml_advisory(self, module_id: str, advisory_data: dict) -> dict:
        """Set ML advisory data for a module (secondary signal)."""
        self._ml_advisories[module_id] = advisory_data
        log.info("set ML advisory for %s", module_id)
        return {"module_id": module_id, "advisory_set": True}

    def get_stats(self) -> dict:
        total_reports = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM readiness_reports"
        ).fetchone()["cnt"]
        total_checks = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM readiness_checks_registry"
        ).fetchone()["cnt"]
        by_status_rows = self._conn.execute(
            "SELECT overall_status, COUNT(*) as cnt FROM readiness_reports GROUP BY overall_status"
        ).fetchall()
        by_status = {r["overall_status"]: r["cnt"] for r in by_status_rows}
        return {
            "total_reports": total_reports,
            "total_registered_checks": total_checks,
            "by_status": by_status,
        }

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="surface.readiness_engine",
            ))


_engine: ReadinessEngine | None = None


def get_readiness_engine(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> ReadinessEngine:
    global _engine
    if _engine is None:
        _engine = ReadinessEngine(db_path, event_bus)
    return _engine
