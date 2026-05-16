"""
SYLION Quality -- Golden Set Runner

Executes golden test sets against a runner function, records per-case
pass/fail results, and provides run comparison and aggregate statistics.

SQLite tables: golden_runs, golden_run_results
Thread-safe via RLock.  EventBus integration via _emit().

Singleton: get_golden_set_runner() / reset_golden_set_runner()
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.quality.golden_set_runner")


class GoldenSetRunner:
    """Executes golden test sets and records results.

    Each run executes all cases from a golden set via a caller-supplied
    executor function, comparing actual output against expected output.
    Results are stored per-case with pass/fail status.

    Thread-safe. SQLite-backed. Emits events on run lifecycle.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS golden_runs (
                run_id        TEXT PRIMARY KEY,
                set_id        TEXT NOT NULL,
                runner_config TEXT NOT NULL DEFAULT '{}',
                total_cases   INTEGER NOT NULL DEFAULT 0,
                passed        INTEGER NOT NULL DEFAULT 0,
                failed        INTEGER NOT NULL DEFAULT 0,
                status        TEXT NOT NULL DEFAULT 'pending',
                started_at    REAL NOT NULL,
                completed_at  REAL,
                duration_ms   INTEGER NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS golden_run_results (
                result_id     TEXT PRIMARY KEY,
                run_id        TEXT NOT NULL,
                case_id       TEXT NOT NULL,
                input_json    TEXT NOT NULL DEFAULT '{}',
                expected_json TEXT NOT NULL DEFAULT '{}',
                actual_json   TEXT NOT NULL DEFAULT '',
                passed        INTEGER NOT NULL DEFAULT 0,
                error_message TEXT NOT NULL DEFAULT '',
                duration_ms   INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (run_id) REFERENCES golden_runs(run_id)
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gr_set "
            "ON golden_runs(set_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gr_status "
            "ON golden_runs(status)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_grr_run "
            "ON golden_run_results(run_id)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="quality.golden_set_runner",
            ))

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _parse_json(raw: str | None, default: Any = None) -> Any:
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    def _get_cases_from_registry(self, set_id: str) -> list[dict]:
        """Lazy load cases from GoldenSetRegistry."""
        from sylion.quality.golden_set_registry import get_golden_set_registry
        registry = get_golden_set_registry()
        return registry.get_cases(set_id)

    def _compare_values(self, expected: Any, actual: Any) -> bool:
        """Compare expected vs actual using JSON normalisation."""
        try:
            exp_norm = json.dumps(expected, sort_keys=True, default=str)
        except (TypeError, ValueError):
            exp_norm = str(expected)
        try:
            act_norm = json.dumps(actual, sort_keys=True, default=str)
        except (TypeError, ValueError):
            act_norm = str(actual)
        return exp_norm == act_norm

    # ------------------------------------------------------------------
    # Run execution
    # ------------------------------------------------------------------

    def start_run(self, set_id: str,
                  runner_config_json: Any = None,
                  executor_fn: Callable[[Any], Any] | None = None,
                  cases: list[dict] | None = None) -> dict:
        """Execute all cases in a golden set and record results.

        Args:
            set_id: The golden set to run.
            runner_config_json: Configuration stored with the run.
            executor_fn: Callable receiving each case's input_json, returns output.
            cases: Optional explicit case list; if None, loaded from registry.
        Returns:
            Run summary dict with pass/fail counts.
        """
        if cases is None:
            cases = self._get_cases_from_registry(set_id)

        run_id = self._uid()
        now = time.time()
        config_s = json.dumps(runner_config_json, default=str) \
            if runner_config_json is not None else "{}"

        with self._lock:
            self._conn.execute("""
                INSERT INTO golden_runs
                    (run_id, set_id, runner_config, total_cases, passed, failed,
                     status, started_at)
                VALUES (?, ?, ?, ?, 0, 0, 'running', ?)
            """, (run_id, set_id, config_s, len(cases), now))
            self._conn.commit()

        self._emit("golden_set.run_started", {
            "run_id": run_id, "set_id": set_id,
            "total_cases": len(cases),
        })

        if not cases:
            with self._lock:
                self._conn.execute(
                    "UPDATE golden_runs SET status = 'completed', "
                    "completed_at = ? WHERE run_id = ?",
                    (time.time(), run_id),
                )
                self._conn.commit()
            return {
                "run_id": run_id, "set_id": set_id,
                "status": "completed", "total_cases": 0,
                "passed": 0, "failed": 0,
            }

        passed = 0
        failed = 0
        start = time.monotonic()

        for case in cases:
            case_id = case.get("case_id", "unknown")
            input_val = case.get("input_json")
            expected_val = case.get("expected_output_json")
            actual_val = None
            error_msg = ""
            case_start = time.monotonic()

            if executor_fn:
                try:
                    actual_val = executor_fn(input_val)
                except Exception as exc:
                    error_msg = str(exc)
                    actual_val = None

            is_pass = (error_msg == "" and
                       self._compare_values(expected_val, actual_val))
            if is_pass:
                passed += 1
            else:
                failed += 1

            case_dur = int((time.monotonic() - case_start) * 1000)
            result_id = self._uid()

            with self._lock:
                self._conn.execute("""
                    INSERT INTO golden_run_results
                        (result_id, run_id, case_id, input_json,
                         expected_json, actual_json, passed,
                         error_message, duration_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result_id, run_id, case_id,
                    json.dumps(input_val, default=str),
                    json.dumps(expected_val, default=str),
                    json.dumps(actual_val, default=str),
                    1 if is_pass else 0,
                    error_msg,
                    case_dur,
                ))
                self._conn.commit()

            self._emit(
                "golden_set.case_passed" if is_pass else "golden_set.case_failed",
                {"run_id": run_id, "case_id": case_id},
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        status = "completed"

        with self._lock:
            self._conn.execute("""
                UPDATE golden_runs
                SET passed = ?, failed = ?, status = ?,
                    completed_at = ?, duration_ms = ?
                WHERE run_id = ?
            """, (passed, failed, status, time.time(), duration_ms, run_id))
            self._conn.commit()

        self._emit("golden_set.run_completed", {
            "run_id": run_id, "set_id": set_id,
            "passed": passed, "failed": failed,
        })
        log.info("run %s completed: %d/%d passed (%dms)",
                 run_id, passed, len(cases), duration_ms)
        return {
            "run_id": run_id, "set_id": set_id,
            "status": status,
            "total_cases": len(cases),
            "passed": passed, "failed": failed,
            "duration_ms": duration_ms,
        }

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_run(self, run_id: str) -> dict | None:
        """Return a single run record."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM golden_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["runner_config"] = self._parse_json(d.get("runner_config"), {})
        return d

    def list_runs(self, set_id: str | None = None,
                  status: str | None = None) -> list[dict]:
        """List runs with optional filters."""
        with self._lock:
            q = "SELECT * FROM golden_runs WHERE 1=1"
            params: list[Any] = []
            if set_id:
                q += " AND set_id = ?"
                params.append(set_id)
            if status:
                q += " AND status = ?"
                params.append(status)
            q += " ORDER BY started_at DESC"
            rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def get_results(self, run_id: str) -> list[dict]:
        """Return all case results for a run, with JSON parsed."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM golden_run_results WHERE run_id = ? "
                "ORDER BY result_id",
                (run_id,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["input_json"] = self._parse_json(d.get("input_json"), {})
            d["expected_json"] = self._parse_json(d.get("expected_json"), {})
            d["actual_json"] = self._parse_json(d.get("actual_json"))
            d["passed"] = bool(d["passed"])
            results.append(d)
        return results

    def get_run_summary(self, run_id: str) -> dict | None:
        """Return a run summary with pass rate."""
        run = self.get_run(run_id)
        if not run:
            return None
        total = run["total_cases"]
        p = run["passed"]
        f = run["failed"]
        return {
            "run_id": run_id,
            "set_id": run["set_id"],
            "status": run["status"],
            "total_cases": total,
            "passed": p,
            "failed": f,
            "pass_rate": round(p / total, 4) if total > 0 else 0.0,
            "duration_ms": run["duration_ms"],
        }

    def compare_runs(self, run_id_1: str, run_id_2: str) -> dict | None:
        """Compare two runs, showing per-case diffs.

        Returns {run_1, run_2, diffs} where diffs is a list of
        {case_id, run_1_passed, run_2_passed, changed}.
        """
        run1 = self.get_run(run_id_1)
        run2 = self.get_run(run_id_2)
        if not run1 or not run2:
            return None

        results1 = {r["case_id"]: r for r in self.get_results(run_id_1)}
        results2 = {r["case_id"]: r for r in self.get_results(run_id_2)}

        all_case_ids = set(results1.keys()) | set(results2.keys())
        diffs = []
        for cid in sorted(all_case_ids):
            p1 = results1.get(cid, {}).get("passed", False)
            p2 = results2.get(cid, {}).get("passed", False)
            diffs.append({
                "case_id": cid,
                "run_1_passed": p1,
                "run_2_passed": p2,
                "changed": p1 != p2,
            })

        return {
            "run_1": {"run_id": run_id_1, "passed": run1["passed"],
                      "failed": run1["failed"]},
            "run_2": {"run_id": run_id_2, "passed": run2["passed"],
                      "failed": run2["failed"]},
            "diffs": diffs,
        }

    def get_stats(self) -> dict[str, Any]:
        """Aggregate statistics across all runs."""
        with self._lock:
            total_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM golden_runs"
            ).fetchone()
            total = total_row["cnt"] if total_row else 0

            pass_row = self._conn.execute(
                "SELECT SUM(passed) as p, SUM(failed) as f, "
                "SUM(total_cases) as t FROM golden_runs"
            ).fetchone()
            total_passed = pass_row["p"] if pass_row and pass_row["p"] else 0
            total_failed = pass_row["f"] if pass_row and pass_row["f"] else 0
            total_cases = pass_row["t"] if pass_row and pass_row["t"] else 0

        pass_rate = total_passed / total_cases if total_cases > 0 else 0.0
        return {
            "total_runs": total,
            "total_cases": total_cases,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "pass_rate": round(pass_rate, 4),
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_runner: GoldenSetRunner | None = None


def get_golden_set_runner(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> GoldenSetRunner:
    global _runner
    if _runner is None:
        _runner = GoldenSetRunner(db_path, event_bus)
    return _runner


def reset_golden_set_runner(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> GoldenSetRunner:
    global _runner
    _runner = GoldenSetRunner(db_path, event_bus)
    return _runner
