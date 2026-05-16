"""
SYLION Efficiency -- Performance Budget Manager

Per-module performance budgeting across 4 efficiency dimensions:
code bloat (lines), runtime performance (ms), memory footprint (MB),
and cost envelope (USD per call).

Budgets are assigned by module class (A=Core, B-I=Standard, M-O=Devices)
and enforced before lifecycle transitions via LifecycleGateEnforcer.

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.efficiency.performance_budget")


# ---------------------------------------------------------------------------
# Default budgets by module class
# ---------------------------------------------------------------------------

CLASS_DEFAULTS: dict[str, dict[str, float]] = {
    "A": {"max_code_lines": 500, "max_runtime_ms": 50.0, "max_memory_mb": 20.0, "max_cost_per_call": 0.01},
    "B": {"max_code_lines": 300, "max_runtime_ms": 100.0, "max_memory_mb": 50.0, "max_cost_per_call": 0.01},
    "C": {"max_code_lines": 300, "max_runtime_ms": 100.0, "max_memory_mb": 50.0, "max_cost_per_call": 0.01},
    "D": {"max_code_lines": 300, "max_runtime_ms": 100.0, "max_memory_mb": 50.0, "max_cost_per_call": 0.01},
    "E": {"max_code_lines": 300, "max_runtime_ms": 100.0, "max_memory_mb": 50.0, "max_cost_per_call": 0.01},
    "F": {"max_code_lines": 300, "max_runtime_ms": 100.0, "max_memory_mb": 50.0, "max_cost_per_call": 0.01},
    "G": {"max_code_lines": 300, "max_runtime_ms": 100.0, "max_memory_mb": 50.0, "max_cost_per_call": 0.01},
    "H": {"max_code_lines": 300, "max_runtime_ms": 100.0, "max_memory_mb": 50.0, "max_cost_per_call": 0.01},
    "I": {"max_code_lines": 300, "max_runtime_ms": 100.0, "max_memory_mb": 50.0, "max_cost_per_call": 0.01},
    "M": {"max_code_lines": 400, "max_runtime_ms": 200.0, "max_memory_mb": 100.0, "max_cost_per_call": 0.01},
    "N": {"max_code_lines": 400, "max_runtime_ms": 200.0, "max_memory_mb": 100.0, "max_cost_per_call": 0.01},
    "O": {"max_code_lines": 400, "max_runtime_ms": 200.0, "max_memory_mb": 100.0, "max_cost_per_call": 0.01},
}


def _defaults_for_class(module_class: str) -> dict[str, float]:
    """Return default budget dict for a module class letter."""
    return CLASS_DEFAULTS.get(
        module_class.upper(),
        CLASS_DEFAULTS["B"],
    ).copy()


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PerformanceBudget:
    """Per-module performance budget across 4 dimensions."""
    module_id: str = ""
    module_class: str = ""
    max_code_lines: int = 500
    max_runtime_ms: float = 100.0
    max_memory_mb: float = 50.0
    max_cost_per_call: float = 0.01
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class Measurement:
    """A recorded measurement for a single metric of a module."""
    measurement_id: str = ""
    module_id: str = ""
    metric: str = ""           # code_lines | runtime_ms | memory_mb | cost_per_call
    value: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.measurement_id:
            self.measurement_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Performance Budget Manager
# ---------------------------------------------------------------------------

class PerformanceBudgetManager:
    """Per-module performance budget manager.

    Thread-safe. SQLite-backed. Emits events on budget / check / measurement
    operations.
    """

    VALID_METRICS = {"code_lines", "runtime_ms", "memory_mb", "cost_per_call"}

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
            CREATE TABLE IF NOT EXISTS performance_budgets (
                module_id        TEXT PRIMARY KEY,
                module_class     TEXT    NOT NULL DEFAULT '',
                max_code_lines   INTEGER NOT NULL DEFAULT 500,
                max_runtime_ms   REAL    NOT NULL DEFAULT 100.0,
                max_memory_mb    REAL    NOT NULL DEFAULT 50.0,
                max_cost_per_call REAL   NOT NULL DEFAULT 0.01,
                created_at       REAL    NOT NULL DEFAULT 0.0,
                updated_at       REAL    NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS performance_measurements (
                measurement_id TEXT PRIMARY KEY,
                module_id      TEXT    NOT NULL DEFAULT '',
                metric         TEXT    NOT NULL DEFAULT '',
                value          REAL    NOT NULL DEFAULT 0.0,
                timestamp      REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pm_budget_class ON performance_budgets(module_class)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pmeasure_mod ON performance_measurements(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pmeasure_metric ON performance_measurements(metric)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pmeasure_ts ON performance_measurements(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Budget management
    # ------------------------------------------------------------------

    def set_budget(self, module_id: str, code_lines: int = 0,
                   runtime_ms: float = 0.0, memory_mb: float = 0.0,
                   cost: float = 0.0, module_class: str = "") -> dict:
        """Set or update the performance budget for *module_id*.

        If all dimension params are zero (or omitted), the defaults for
        *module_class* are applied. Emits
        ``efficiency.performance_budget.budget_set``.
        """
        now = time.time()

        # Resolve module class from existing budget if not provided
        if not module_class:
            existing = self._conn.execute(
                "SELECT module_class FROM performance_budgets WHERE module_id = ?",
                (module_id,),
            ).fetchone()
            if existing:
                module_class = existing["module_class"] or "B"

        if not module_class:
            module_class = "B"

        defaults = _defaults_for_class(module_class)

        max_code_lines = code_lines if code_lines > 0 else int(defaults["max_code_lines"])
        max_runtime_ms = runtime_ms if runtime_ms > 0.0 else defaults["max_runtime_ms"]
        max_memory_mb = memory_mb if memory_mb > 0.0 else defaults["max_memory_mb"]
        max_cost = cost if cost > 0.0 else defaults["max_cost_per_call"]

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO performance_budgets
                    (module_id, module_class, max_code_lines, max_runtime_ms,
                     max_memory_mb, max_cost_per_call, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                module_id, module_class, max_code_lines, max_runtime_ms,
                max_memory_mb, max_cost, now, now,
            ))
            self._conn.commit()

        result = {
            "module_id": module_id,
            "module_class": module_class,
            "max_code_lines": max_code_lines,
            "max_runtime_ms": max_runtime_ms,
            "max_memory_mb": max_memory_mb,
            "max_cost_per_call": max_cost,
        }

        self._emit("efficiency.performance_budget.budget_set", result)
        log.info("budget set for %s (class %s): lines=%d, runtime=%.1fms, "
                 "memory=%.1fMB, cost=$%.4f",
                 module_id, module_class, max_code_lines,
                 max_runtime_ms, max_memory_mb, max_cost)
        return result

    def get_budget(self, module_id: str) -> dict | None:
        """Return the budget for *module_id*, or None if not defined."""
        row = self._conn.execute(
            "SELECT * FROM performance_budgets WHERE module_id = ?",
            (module_id,),
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Budget checking
    # ------------------------------------------------------------------

    def check_budget(self, module_id: str,
                     actuals: dict[str, float] | None = None) -> dict:
        """Check whether *module_id* is within its performance budget.

        If *actuals* is provided, uses those values directly. Otherwise
        pulls the latest recorded measurements from the database.

        Returns dict with keys: module_id, within_budget (bool),
        violations (list of violation dicts), budget (dict of limits),
        actuals (dict of measured values).
        """
        budget_row = self._conn.execute(
            "SELECT * FROM performance_budgets WHERE module_id = ?",
            (module_id,),
        ).fetchone()

        if budget_row is None:
            return {
                "module_id": module_id,
                "within_budget": True,
                "violations": [],
                "budget": None,
                "actuals": actuals or {},
                "reason": "no_budget_defined",
            }

        budget = dict(budget_row)

        # Use provided actuals or fetch latest from DB
        if actuals is None:
            actuals = self._latest_measurements(module_id)

        violations: list[dict[str, Any]] = []
        dims = [
            ("code_lines", "max_code_lines", "Code Bloat"),
            ("runtime_ms", "max_runtime_ms", "Runtime Performance"),
            ("memory_mb", "max_memory_mb", "Memory Footprint"),
            ("cost_per_call", "max_cost_per_call", "Cost Envelope"),
        ]
        for metric_key, budget_key, label in dims:
            if metric_key in actuals:
                actual_val = actuals[metric_key]
                budget_val = budget[budget_key]
                if actual_val > budget_val:
                    violations.append({
                        "dimension": label,
                        "metric": metric_key,
                        "budget": budget_val,
                        "actual": actual_val,
                        "over_by": actual_val - budget_val,
                        "over_pct": ((actual_val - budget_val) / budget_val * 100)
                                    if budget_val > 0 else float("inf"),
                    })

        within = len(violations) == 0
        result = {
            "module_id": module_id,
            "within_budget": within,
            "violations": violations,
            "budget": budget,
            "actuals": actuals,
        }

        self._emit("efficiency.performance_budget.budget_checked", result)
        log.info("budget check for %s: within=%s, violations=%d",
                 module_id, within, len(violations))
        return result

    def list_over_budget(self) -> list[dict]:
        """Return all modules that exceed their budget.

        Uses the latest recorded measurements for each module.
        """
        budgets = self._conn.execute(
            "SELECT * FROM performance_budgets ORDER BY module_id"
        ).fetchall()

        over: list[dict] = []
        for row in budgets:
            mid = row["module_id"]
            actuals = self._latest_measurements(mid)
            check = self.check_budget(mid, actuals)
            if not check["within_budget"]:
                over.append(check)

        return over

    # ------------------------------------------------------------------
    # Measurement recording
    # ------------------------------------------------------------------

    def record_measurement(self, module_id: str, metric: str,
                           value: float) -> dict:
        """Record a measurement for a single metric of *module_id*.

        *metric* must be one of: code_lines, runtime_ms, memory_mb,
        cost_per_call.

        Returns dict with measurement details.
        Emits ``efficiency.performance_budget.measurement_recorded``.
        """
        if metric not in self.VALID_METRICS:
            raise ValueError(
                f"Invalid metric '{metric}'. Must be one of: {sorted(self.VALID_METRICS)}"
            )

        m = Measurement(
            module_id=module_id,
            metric=metric,
            value=value,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO performance_measurements
                    (measurement_id, module_id, metric, value, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                m.measurement_id, m.module_id, m.metric,
                m.value, m.timestamp,
            ))
            self._conn.commit()

        result = {
            "measurement_id": m.measurement_id,
            "module_id": module_id,
            "metric": metric,
            "value": value,
            "timestamp": m.timestamp,
        }

        self._emit("efficiency.performance_budget.measurement_recorded", result)
        log.info("recorded %s=%s for %s", metric, value, module_id)
        return result

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_measurements(self, module_id: str,
                         metric: str | None = None,
                         limit: int = 100) -> list[dict]:
        """Return recent measurements for *module_id*.

        Optionally filter by *metric*.
        """
        if metric:
            rows = self._conn.execute(
                "SELECT * FROM performance_measurements "
                "WHERE module_id = ? AND metric = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (module_id, metric, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM performance_measurements "
                "WHERE module_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (module_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_budgets(self, module_class: str | None = None) -> list[dict]:
        """Return all budgets, optionally filtered by *module_class*."""
        if module_class:
            rows = self._conn.execute(
                "SELECT * FROM performance_budgets WHERE module_class = ? ORDER BY module_id",
                (module_class.upper(),),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM performance_budgets ORDER BY module_id"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_actuals(self, module_id: str) -> dict[str, float]:
        """Return the latest recorded measurement per metric for *module_id*."""
        return self._latest_measurements(module_id)

    def remove_budget(self, module_id: str) -> bool:
        """Remove the budget for *module_id*. Returns True if deleted."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM performance_budgets WHERE module_id = ?",
                (module_id,),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _latest_measurements(self, module_id: str) -> dict[str, float]:
        """Return the most recent value per metric for *module_id*."""
        actuals: dict[str, float] = {}
        for metric in self.VALID_METRICS:
            row = self._conn.execute(
                "SELECT value FROM performance_measurements "
                "WHERE module_id = ? AND metric = ? "
                "ORDER BY timestamp DESC LIMIT 1",
                (module_id, metric),
            ).fetchone()
            if row:
                actuals[metric] = row["value"]
        return actuals

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="efficiency.performance_budget",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: PerformanceBudgetManager | None = None


def get_performance_budget_manager(event_bus: EventBus | None = None,
                                   db_path: str | Path | None = None) -> PerformanceBudgetManager:
    global _manager
    if _manager is None:
        _manager = PerformanceBudgetManager(event_bus, db_path)
    return _manager
