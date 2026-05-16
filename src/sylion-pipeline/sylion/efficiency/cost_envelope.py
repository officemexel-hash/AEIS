"""
SYLION Efficiency -- Cost Envelope Tracker

LLM cost tracking and budgeting per provider.
Records per-request token usage and cost, stores daily/monthly budgets,
and validates spending against configurable limits.

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

import calendar
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.efficiency.cost_envelope")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CostRecord:
    """A single LLM cost record."""
    record_id: str = ""
    provider: str = ""
    model_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    task_type: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.record_id:
            self.record_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class CostBudget:
    """Cost budget definition for a provider."""
    provider: str = ""
    daily_limit_usd: float = 0.0
    monthly_limit_usd: float = 0.0
    alert_threshold: float = 0.8


# ---------------------------------------------------------------------------
# Cost Envelope Tracker
# ---------------------------------------------------------------------------

class CostEnvelopeTracker:
    """LLM cost tracking and budgeting.

    Thread-safe. SQLite-backed. Emits events on record / budget operations.
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
            CREATE TABLE IF NOT EXISTS cost_records (
                record_id     TEXT PRIMARY KEY,
                provider      TEXT    NOT NULL DEFAULT '',
                model_id      TEXT    NOT NULL DEFAULT '',
                input_tokens  INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd      REAL    NOT NULL DEFAULT 0.0,
                task_type     TEXT    NOT NULL DEFAULT '',
                timestamp     REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cost_budgets (
                provider          TEXT PRIMARY KEY,
                daily_limit_usd   REAL NOT NULL DEFAULT 0.0,
                monthly_limit_usd REAL NOT NULL DEFAULT 0.0,
                alert_threshold   REAL NOT NULL DEFAULT 0.8
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cr_provider ON cost_records(provider)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cr_ts ON cost_records(timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cr_task ON cost_records(task_type)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Record cost
    # ------------------------------------------------------------------

    def record(self, provider: str, model_id: str,
               input_tokens: int, output_tokens: int,
               cost_usd: float, task_type: str = "") -> dict:
        """Record an LLM usage cost entry.

        Emits ``efficiency.cost_envelope.recorded``.
        """
        rec = CostRecord(
            provider=provider,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            task_type=task_type,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO cost_records
                    (record_id, provider, model_id, input_tokens,
                     output_tokens, cost_usd, task_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec.record_id, rec.provider, rec.model_id,
                rec.input_tokens, rec.output_tokens, rec.cost_usd,
                rec.task_type, rec.timestamp,
            ))
            self._conn.commit()

        self._emit("efficiency.cost_envelope.recorded", {
            "provider": provider,
            "model_id": model_id,
            "cost_usd": cost_usd,
        })

        log.info("cost record: %s/%s $%.6f", provider, model_id, cost_usd)
        return {
            "record_id": rec.record_id,
            "provider": provider,
            "cost_usd": cost_usd,
            "timestamp": rec.timestamp,
        }

    # ------------------------------------------------------------------
    # Budget management
    # ------------------------------------------------------------------

    def set_budget(self, provider: str, daily_limit: float = 0,
                   monthly_limit: float = 0,
                   alert_threshold: float = 0.8) -> dict:
        """Set or update cost budget for *provider*.

        Emits ``efficiency.cost_envelope.budget_set``.
        """
        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO cost_budgets
                    (provider, daily_limit_usd, monthly_limit_usd, alert_threshold)
                VALUES (?, ?, ?, ?)
            """, (provider, daily_limit, monthly_limit, alert_threshold))
            self._conn.commit()

        self._emit("efficiency.cost_envelope.budget_set", {
            "provider": provider,
            "daily_limit_usd": daily_limit,
            "monthly_limit_usd": monthly_limit,
        })

        log.info("budget set for %s: daily=$%.2f, monthly=$%.2f",
                 provider, daily_limit, monthly_limit)
        return {
            "provider": provider,
            "daily_limit_usd": daily_limit,
            "monthly_limit_usd": monthly_limit,
        }

    def check_budget(self, provider: str) -> dict:
        """Check spending against budget for *provider*.

        Returns dict with keys: provider, daily_spend, monthly_spend,
        daily_limit_usd, monthly_limit_usd, daily_pct, monthly_pct,
        alert (bool).
        """
        budget_row = self._conn.execute(
            "SELECT * FROM cost_budgets WHERE provider = ?",
            (provider,),
        ).fetchone()

        if budget_row is None:
            daily_spend = self._compute_daily_spend(provider)
            monthly_spend = self._compute_monthly_spend(provider)
            return {
                "provider": provider,
                "daily_spend": daily_spend,
                "monthly_spend": monthly_spend,
                "daily_limit_usd": None,
                "monthly_limit_usd": None,
                "daily_pct": None,
                "monthly_pct": None,
                "alert": False,
                "reason": "no_budget_defined",
            }

        daily_spend = self._compute_daily_spend(provider)
        monthly_spend = self._compute_monthly_spend(provider)
        daily_limit = budget_row["daily_limit_usd"]
        monthly_limit = budget_row["monthly_limit_usd"]
        alert_threshold = budget_row["alert_threshold"]

        daily_pct = (daily_spend / daily_limit) if daily_limit > 0 else 0.0
        monthly_pct = (monthly_spend / monthly_limit) if monthly_limit > 0 else 0.0

        alert = (daily_pct >= alert_threshold) or (monthly_pct >= alert_threshold)

        result = {
            "provider": provider,
            "daily_spend": daily_spend,
            "monthly_spend": monthly_spend,
            "daily_limit_usd": daily_limit,
            "monthly_limit_usd": monthly_limit,
            "daily_pct": daily_pct,
            "monthly_pct": monthly_pct,
            "alert": alert,
        }

        self._emit("efficiency.cost_envelope.budget_checked", result)
        log.info("budget check for %s: daily=%.1f%%, monthly=%.1f%%, alert=%s",
                 provider, daily_pct * 100, monthly_pct * 100, alert)
        return result

    # ------------------------------------------------------------------
    # Spend queries
    # ------------------------------------------------------------------

    def _day_range(self) -> tuple[float, float]:
        """Return (start_of_day, end_of_day) as Unix timestamps."""
        now = time.time()
        import datetime as _dt
        today = _dt.date.fromtimestamp(now)
        start = _dt.datetime.combine(today, _dt.time.min).timestamp()
        end = _dt.datetime.combine(today, _dt.time.max).timestamp()
        return start, end

    def _month_range(self) -> tuple[float, float]:
        """Return (start_of_month, end_of_month) as Unix timestamps."""
        import datetime as _dt
        now = time.time()
        today = _dt.date.fromtimestamp(now)
        start = _dt.datetime(today.year, today.month, 1).timestamp()
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = _dt.datetime(today.year, today.month, last_day, 23, 59, 59).timestamp()
        return start, end

    def _compute_daily_spend(self, provider: str | None) -> float:
        start, end = self._day_range()
        if provider:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) as total "
                "FROM cost_records WHERE provider = ? AND timestamp >= ? AND timestamp <= ?",
                (provider, start, end),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) as total "
                "FROM cost_records WHERE timestamp >= ? AND timestamp <= ?",
                (start, end),
            ).fetchone()
        return row["total"] if row else 0.0

    def _compute_monthly_spend(self, provider: str | None) -> float:
        start, end = self._month_range()
        if provider:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) as total "
                "FROM cost_records WHERE provider = ? AND timestamp >= ? AND timestamp <= ?",
                (provider, start, end),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) as total "
                "FROM cost_records WHERE timestamp >= ? AND timestamp <= ?",
                (start, end),
            ).fetchone()
        return row["total"] if row else 0.0

    def get_daily_spend(self, provider: str | None = None) -> float:
        """Return total spend today, optionally filtered by provider."""
        return self._compute_daily_spend(provider)

    def get_monthly_spend(self, provider: str | None = None) -> float:
        """Return total spend this month, optionally filtered by provider."""
        return self._compute_monthly_spend(provider)

    def get_records(self, provider: str | None = None,
                    limit: int = 100) -> list[dict]:
        """Return recent cost records, optionally filtered by provider."""
        if provider:
            rows = self._conn.execute(
                "SELECT * FROM cost_records WHERE provider = ? ORDER BY timestamp DESC LIMIT ?",
                (provider, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM cost_records ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def is_within_budget(self, provider: str) -> bool:
        """Return True if *provider* is within both daily and monthly limits."""
        budget_row = self._conn.execute(
            "SELECT * FROM cost_budgets WHERE provider = ?",
            (provider,),
        ).fetchone()
        if budget_row is None:
            return True

        daily_spend = self._compute_daily_spend(provider)
        monthly_spend = self._compute_monthly_spend(provider)

        if budget_row["daily_limit_usd"] > 0 and daily_spend > budget_row["daily_limit_usd"]:
            return False
        if budget_row["monthly_limit_usd"] > 0 and monthly_spend > budget_row["monthly_limit_usd"]:
            return False
        return True

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="efficiency.cost_envelope",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_tracker: CostEnvelopeTracker | None = None


def get_cost_envelope_tracker(event_bus: EventBus | None = None,
                              db_path: str | Path | None = None) -> CostEnvelopeTracker:
    global _tracker
    if _tracker is None:
        _tracker = CostEnvelopeTracker(event_bus, db_path)
    return _tracker
