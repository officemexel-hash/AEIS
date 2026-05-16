"""
SYLION Monitoring -- Model Budget Manager

Tracks LLM API costs and enforces spending limits per model.
Supports daily and monthly budgets with configurable alert thresholds.
When usage exceeds the alert threshold, an alert is generated.
When usage exceeds the budget, further API calls are denied.

SQLite-backed with WAL mode.  Thread-safe via threading.RLock().
Singleton via get_model_budget() / reset_model_budget().
Emits events via EventBus.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.monitoring.model_budget")

# ---------------------------------------------------------------------------
# Period durations in seconds
# ---------------------------------------------------------------------------

DAILY_SECONDS = 86400       # 24 * 60 * 60
MONTHLY_SECONDS = 2592000   # 30 * 24 * 60 * 60


# ---------------------------------------------------------------------------
# ModelBudgetManager
# ---------------------------------------------------------------------------

class ModelBudgetManager:
    """Per-model budget manager backed by SQLite.

    Tracks daily and monthly spending with alert thresholds and budget
    enforcement.  Thread-safe via RLock.  Singleton-capable.
    EventBus-integrated.
    """

    def __init__(self, db_path: str = ":memory:",
                 event_bus: EventBus | None = None):
        self._db_path = db_path
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            timeout=30.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS model_budgets (
                model_id           TEXT PRIMARY KEY,
                daily_limit        REAL    NOT NULL DEFAULT 0,
                monthly_limit      REAL    NOT NULL DEFAULT 0,
                alert_threshold_pct REAL   NOT NULL DEFAULT 80.0,
                spent_today        REAL    NOT NULL DEFAULT 0,
                spent_this_month   REAL    NOT NULL DEFAULT 0,
                last_daily_reset   REAL    NOT NULL DEFAULT 0,
                last_monthly_reset REAL    NOT NULL DEFAULT 0,
                provider           TEXT    NOT NULL DEFAULT '',
                fallback_model_id  TEXT    NOT NULL DEFAULT '',
                created_at         REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS budget_usage (
                usage_id    TEXT PRIMARY KEY,
                model_id    TEXT    NOT NULL,
                tokens      INTEGER NOT NULL DEFAULT 0,
                cost        REAL    NOT NULL DEFAULT 0,
                tokens_in   INTEGER NOT NULL DEFAULT 0,
                tokens_out  INTEGER NOT NULL DEFAULT 0,
                task_type   TEXT    NOT NULL DEFAULT '',
                session_id  TEXT    NOT NULL DEFAULT '',
                created_at  REAL    NOT NULL
            )
        """)
        self._ensure_column("model_budgets", "provider", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("model_budgets", "fallback_model_id", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("budget_usage", "tokens_in", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("budget_usage", "tokens_out", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("budget_usage", "task_type", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("budget_usage", "session_id", "TEXT NOT NULL DEFAULT ''")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS budget_alerts (
                alert_id      TEXT PRIMARY KEY,
                model_id      TEXT    NOT NULL,
                alert_type    TEXT    NOT NULL,
                message       TEXT    NOT NULL DEFAULT '',
                acknowledged  INTEGER NOT NULL DEFAULT 0,
                created_at    REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bu_model "
            "ON budget_usage(model_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bu_ts "
            "ON budget_usage(created_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ba_model "
            "ON budget_alerts(model_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ba_ack "
            "ON budget_alerts(acknowledged)"
        )
        self._conn.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="monitoring.model_budget",
            ))

    def _auto_reset_periods(self, model_id: str, now: float) -> None:
        """Reset period counters whose time window has elapsed.

        Must be called while holding self._lock.
        """
        row = self._conn.execute(
            "SELECT last_daily_reset, last_monthly_reset "
            "FROM model_budgets WHERE model_id = ?",
            (model_id,),
        ).fetchone()
        if row is None:
            return

        if now - row["last_daily_reset"] > DAILY_SECONDS:
            self._conn.execute(
                "UPDATE model_budgets SET spent_today = 0, "
                "last_daily_reset = ? WHERE model_id = ?",
                (now, model_id),
            )
        if now - row["last_monthly_reset"] > MONTHLY_SECONDS:
            self._conn.execute(
                "UPDATE model_budgets SET spent_this_month = 0, "
                "last_monthly_reset = ? WHERE model_id = ?",
                (now, model_id),
            )

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        return dict(row)

    # ------------------------------------------------------------------
    # Budget configuration
    # ------------------------------------------------------------------

    def set_budget(self, model_id: str, daily_limit: float = 0,
                   monthly_limit: float = 0,
                   alert_threshold_pct: float = 80.0,
                   provider: str = "",
                   fallback_model_id: str = "") -> dict:
        """Set or update the budget for a model.

        Args:
            model_id: Model identifier.
            daily_limit: Maximum daily spend (0 = unlimited).
            monthly_limit: Maximum monthly spend (0 = unlimited).
            alert_threshold_pct: Percentage (0-100) to trigger alert.

        Returns:
            Dict with budget configuration.
        """
        now = time.time()

        with self._lock:
            existing = self._conn.execute(
                "SELECT model_id FROM model_budgets WHERE model_id = ?",
                (model_id,),
            ).fetchone()

            if existing:
                self._conn.execute("""
                    UPDATE model_budgets
                    SET daily_limit = ?, monthly_limit = ?,
                        alert_threshold_pct = ?, provider = ?,
                        fallback_model_id = ?
                    WHERE model_id = ?
                """, (daily_limit, monthly_limit, alert_threshold_pct,
                      provider, fallback_model_id, model_id))
            else:
                self._conn.execute("""
                    INSERT INTO model_budgets
                        (model_id, daily_limit, monthly_limit,
                         alert_threshold_pct, spent_today, spent_this_month,
                         last_daily_reset, last_monthly_reset, provider,
                         fallback_model_id, created_at)
                    VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?)
                """, (model_id, daily_limit, monthly_limit,
                      alert_threshold_pct, now, now, provider,
                      fallback_model_id, now))
            self._conn.commit()

        result = {
            "model_id": model_id,
            "daily_limit": daily_limit,
            "monthly_limit": monthly_limit,
            "alert_threshold_pct": alert_threshold_pct,
            "provider": provider,
            "fallback_model_id": fallback_model_id,
        }

        self._emit("budget_set", result)
        log.info("budget set for %s: daily=%.4f monthly=%.4f alert=%.1f%%",
                 model_id, daily_limit, monthly_limit, alert_threshold_pct)
        return result

    def get_budget(self, model_id: str) -> dict | None:
        """Get budget configuration for a model, or None."""
        now = time.time()
        with self._lock:
            try:
                self._auto_reset_periods(model_id, now)
                row = self._conn.execute(
                    "SELECT * FROM model_budgets WHERE model_id = ?",
                    (model_id,),
                ).fetchone()
                self._conn.commit()
            except sqlite3.Error:
                self._conn.rollback()
                raise
        if row is None:
            return None
        return self._budget_to_api_dict(row)

    def list_budgets(self) -> list[dict]:
        """List all configured budgets."""
        now = time.time()
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT * FROM model_budgets ORDER BY model_id"
                ).fetchall()
                result = []
                for row in rows:
                    self._auto_reset_periods(row["model_id"], now)
                    row = self._conn.execute(
                        "SELECT * FROM model_budgets WHERE model_id = ?",
                        (row["model_id"],),
                    ).fetchone()
                    result.append(self._budget_to_api_dict(row))
                self._conn.commit()
            except sqlite3.Error:
                self._conn.rollback()
                raise
        return result

    # ------------------------------------------------------------------
    # Usage recording
    # ------------------------------------------------------------------

    def record_usage(self, model_id: str, tokens: int,
                     cost: float, *, tokens_in: int = 0,
                     tokens_out: int = 0, task_type: str = "",
                     session_id: str = "") -> dict:
        """Record token usage and cost against a model's budget.

        Auto-creates the model budget if it does not exist.
        Triggers alerts when threshold is crossed.
        Returns usage record dict.
        """
        usage_id = self._uid()
        now = time.time()

        with self._lock:
            # Ensure budget row exists
            existing = self._conn.execute(
                "SELECT * FROM model_budgets WHERE model_id = ?",
                (model_id,),
            ).fetchone()
            if existing is None:
                self._conn.execute("""
                    INSERT INTO model_budgets
                        (model_id, daily_limit, monthly_limit,
                         alert_threshold_pct, spent_today, spent_this_month,
                         last_daily_reset, last_monthly_reset, created_at)
                    VALUES (?, 0, 0, 80.0, 0, 0, ?, ?, ?)
                """, (model_id, now, now, now))
                existing = self._conn.execute(
                    "SELECT * FROM model_budgets WHERE model_id = ?",
                    (model_id,),
                ).fetchone()

            self._auto_reset_periods(model_id, now)

            # Re-fetch after potential reset
            existing = self._conn.execute(
                "SELECT * FROM model_budgets WHERE model_id = ?",
                (model_id,),
            ).fetchone()

            new_daily = existing["spent_today"] + cost
            new_monthly = existing["spent_this_month"] + cost

            self._conn.execute("""
                UPDATE model_budgets
                SET spent_today = ?, spent_this_month = ?
                WHERE model_id = ?
            """, (new_daily, new_monthly, model_id))

            # Insert usage record
            self._conn.execute("""
                INSERT INTO budget_usage
                    (usage_id, model_id, tokens, cost, tokens_in, tokens_out,
                     task_type, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                usage_id,
                model_id,
                tokens,
                cost,
                tokens_in,
                tokens_out,
                task_type,
                session_id,
                now,
            ))

            # Check alert threshold
            daily_limit = existing["daily_limit"]
            monthly_limit = existing["monthly_limit"]
            threshold_pct = existing["alert_threshold_pct"]

            alert_triggered = False
            if daily_limit > 0 and not alert_triggered:
                pct = (new_daily / daily_limit) * 100
                if pct >= threshold_pct and cost > 0:
                    old_pct = (existing["spent_today"] / daily_limit) * 100
                    if old_pct < threshold_pct:
                        alert_triggered = True
                        self._create_alert(model_id, "daily_threshold",
                                           f"Daily spend at {pct:.1f}% of limit")

            if monthly_limit > 0 and not alert_triggered:
                pct = (new_monthly / monthly_limit) * 100
                if pct >= threshold_pct and cost > 0:
                    old_pct = (existing["spent_this_month"] / monthly_limit) * 100
                    if old_pct < threshold_pct:
                        alert_triggered = True
                        self._create_alert(model_id, "monthly_threshold",
                                           f"Monthly spend at {pct:.1f}% of limit")

            self._conn.commit()

        result = {
            "usage_id": usage_id,
            "model_id": model_id,
            "tokens": tokens,
            "cost": cost,
            "amount": cost,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "task_type": task_type,
            "session_id": session_id,
            "spent_today": new_daily,
            "spent_this_month": new_monthly,
            "daily_limit": daily_limit,
            "monthly_limit": monthly_limit,
        }

        self._emit("usage_recorded", {
            "usage_id": usage_id, "model_id": model_id,
            "tokens": tokens, "cost": cost,
        })

        # Check budget exceeded
        if (daily_limit > 0 and new_daily >= daily_limit) or \
           (monthly_limit > 0 and new_monthly >= monthly_limit):
            exceeded_period = ""
            if daily_limit > 0 and new_daily >= daily_limit:
                exceeded_period = "daily"
            elif monthly_limit > 0 and new_monthly >= monthly_limit:
                exceeded_period = "monthly"

            self._emit("budget_exceeded", {
                "model_id": model_id,
                "period": exceeded_period,
                "spent_daily": new_daily,
                "spent_monthly": new_monthly,
            })
            with self._lock:
                self._create_alert(model_id, "budget_exceeded",
                                   f"Budget exceeded ({exceeded_period})")
                self._conn.commit()

        if alert_triggered:
            self._emit("budget_alert", {
                "model_id": model_id,
            })

        return result

    def _create_alert(self, model_id: str, alert_type: str,
                      message: str) -> str:
        """Create a budget alert. Must be called under lock."""
        alert_id = self._uid()
        now = time.time()
        self._conn.execute("""
            INSERT INTO budget_alerts
                (alert_id, model_id, alert_type, message,
                 acknowledged, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
        """, (alert_id, model_id, alert_type, message, now))
        return alert_id

    # ------------------------------------------------------------------
    # Budget check
    # ------------------------------------------------------------------

    def check_budget(self, model_id: str) -> dict:
        """Check if a model is within its budget.

        Returns dict with:
          allowed: bool - whether API calls are permitted
          remaining_daily: float
          remaining_monthly: float
          spent_today: float
          spent_this_month: float
          daily_limit: float
          monthly_limit: float
        """
        now = time.time()
        with self._lock:
            try:
                self._auto_reset_periods(model_id, now)
                row = self._conn.execute(
                    "SELECT * FROM model_budgets WHERE model_id = ?",
                    (model_id,),
                ).fetchone()
                self._conn.commit()
            except sqlite3.Error:
                self._conn.rollback()
                raise

        if row is None:
            return {
                "model_id": model_id,
                "allowed": True,
                "remaining_daily": None,
                "remaining_monthly": None,
                "spent_today": 0,
                "spent_this_month": 0,
                "daily_limit": 0,
                "monthly_limit": 0,
                "unlimited": True,
            }

        daily_limit = row["daily_limit"]
        monthly_limit = row["monthly_limit"]
        spent_today = row["spent_today"]
        spent_monthly = row["spent_this_month"]

        remaining_daily = (daily_limit - spent_today
                           if daily_limit > 0 else None)
        remaining_monthly = (monthly_limit - spent_monthly
                             if monthly_limit > 0 else None)

        allowed = True
        if daily_limit > 0 and spent_today >= daily_limit:
            allowed = False
        if monthly_limit > 0 and spent_monthly >= monthly_limit:
            allowed = False

        return {
            "model_id": model_id,
            "allowed": allowed,
            "remaining_daily": remaining_daily,
            "remaining_monthly": remaining_monthly,
            "spent_today": spent_today,
            "spent_this_month": spent_monthly,
            "daily_limit": daily_limit,
            "monthly_limit": monthly_limit,
            "unlimited": daily_limit <= 0 and monthly_limit <= 0,
        }

    def _budget_to_api_dict(self, row: sqlite3.Row) -> dict:
        item = self._row_to_dict(row)
        monthly_limit = float(item.get("monthly_limit") or 0.0)
        spent_monthly = float(item.get("spent_this_month") or 0.0)
        item["budget_limit"] = monthly_limit
        item["spent"] = spent_monthly
        item["remaining"] = (
            monthly_limit - spent_monthly
            if monthly_limit > 0
            else None
        )
        item["period_budget"] = {
            "daily": float(item.get("daily_limit") or 0.0),
            "monthly": monthly_limit,
        }
        item["period_spend"] = {
            "daily": float(item.get("spent_today") or 0.0),
            "monthly": spent_monthly,
        }
        return item

    # ------------------------------------------------------------------
    # Usage queries
    # ------------------------------------------------------------------

    def get_usage(self, model_id: str,
                  period: str = "all") -> list[dict]:
        """Get usage records for a model.

        Args:
            model_id: Model to query.
            period: 'daily', 'monthly', or 'all'.

        Returns:
            List of usage record dicts.
        """
        now = time.time()
        clauses = ["model_id = ?"]
        params: list[Any] = [model_id]

        if period == "daily":
            clauses.append("created_at >= ?")
            params.append(now - DAILY_SECONDS)
        elif period == "monthly":
            clauses.append("created_at >= ?")
            params.append(now - MONTHLY_SECONDS)

        where = " WHERE " + " AND ".join(clauses)
        sql = (f"SELECT * FROM budget_usage{where} "
               f"ORDER BY created_at DESC")

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def list_alerts(self, model_id: str | None = None,
                    acknowledged: bool | None = None) -> list[dict]:
        """List budget alerts with optional filters."""
        clauses: list[str] = []
        params: list[Any] = []

        if model_id is not None:
            clauses.append("model_id = ?")
            params.append(model_id)
        if acknowledged is not None:
            clauses.append("acknowledged = ?")
            params.append(1 if acknowledged else 0)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (f"SELECT * FROM budget_alerts{where} "
               f"ORDER BY created_at DESC")

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def acknowledge_alert(self, alert_id: str) -> dict | None:
        """Acknowledge a budget alert.

        Returns updated alert dict, or None if not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM budget_alerts WHERE alert_id = ?",
                (alert_id,),
            ).fetchone()
            if row is None:
                return None

            self._conn.execute(
                "UPDATE budget_alerts SET acknowledged = 1 "
                "WHERE alert_id = ?",
                (alert_id,),
            )
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM budget_alerts WHERE alert_id = ?",
                (alert_id,),
            ).fetchone()

        return self._row_to_dict(row)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_budget_summary(self) -> dict:
        """Aggregate budget summary across all models."""
        now = time.time()

        with self._lock:
            try:
                models = self._conn.execute(
                    "SELECT * FROM model_budgets ORDER BY model_id"
                ).fetchall()

                total_spent_daily = 0.0
                total_spent_monthly = 0.0
                total_daily_limit = 0.0
                total_monthly_limit = 0.0

                model_summaries = []
                for row in models:
                    mid = row["model_id"]
                    self._auto_reset_periods(mid, now)
                    row = self._conn.execute(
                        "SELECT * FROM model_budgets WHERE model_id = ?",
                        (mid,),
                    ).fetchone()

                    sd = row["spent_today"]
                    sm = row["spent_this_month"]
                    dl = row["daily_limit"]
                    ml = row["monthly_limit"]

                    total_spent_daily += sd
                    total_spent_monthly += sm
                    total_daily_limit += dl
                    total_monthly_limit += ml

                    model_summaries.append({
                        "model_id": mid,
                        "provider": row["provider"],
                        "fallback_model_id": row["fallback_model_id"],
                        "daily_limit": dl,
                        "monthly_limit": ml,
                        "budget_limit": ml,
                        "spent": sm,
                        "remaining": (ml - sm if ml > 0 else None),
                        "spent_today": sd,
                        "spent_this_month": sm,
                        "period_budget": {"daily": dl, "monthly": ml},
                        "period_spend": {"daily": sd, "monthly": sm},
                    })

                total_alerts = self._conn.execute(
                    "SELECT COUNT(*) as cnt FROM budget_alerts"
                ).fetchone()["cnt"]

                unacknowledged = self._conn.execute(
                    "SELECT COUNT(*) as cnt FROM budget_alerts "
                    "WHERE acknowledged = 0"
                ).fetchone()["cnt"]
                self._conn.commit()
            except sqlite3.Error:
                self._conn.rollback()
                raise

        return {
            "total_models": len(models),
            "total_spent_daily": total_spent_daily,
            "total_spent_monthly": total_spent_monthly,
            "total_daily_limit": total_daily_limit,
            "total_monthly_limit": total_monthly_limit,
            "models": model_summaries,
            "total_alerts": total_alerts,
            "unacknowledged_alerts": unacknowledged,
            "total_budget": total_monthly_limit,
            "total_spent": total_spent_monthly,
            "total_remaining": (
                total_monthly_limit - total_spent_monthly
                if total_monthly_limit > 0
                else None
            ),
            "by_model": model_summaries,
            "generated_at": now,
        }

    # ------------------------------------------------------------------
    # Bridge methods kept for ``sylion.api.monitoring_budget_routes`` —
    # the route layer was authored against a slightly different
    # vocabulary (``configure``, ``get_all_budgets``, ``resolve``,
    # ``reset``, ``get_transactions``, ``get_spending_summary``). These
    # thin wrappers map onto the canonical methods above.
    # ------------------------------------------------------------------

    def configure(self, model_id: str, budget_limit: float,
                  *, provider: str = "", fallback_model_id: str = "") -> dict:
        # Treat ``budget_limit`` as the monthly limit; daily defaults to 0.
        result = self.set_budget(
            model_id=model_id,
            monthly_limit=float(budget_limit),
            provider=provider,
            fallback_model_id=fallback_model_id,
        )
        result["budget_limit"] = float(budget_limit)
        result["provider"] = provider
        result["fallback_model_id"] = fallback_model_id
        return result

    def record_transaction(self, model_id: str, amount: float, *,
                           tokens_in: int = 0, tokens_out: int = 0,
                           task_type: str = "",
                           session_id: str = "") -> dict:
        transaction = self.record_usage(
            model_id,
            int(tokens_in) + int(tokens_out),
            float(amount),
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            task_type=task_type,
            session_id=session_id,
        )
        return {"recorded": True, "transaction": transaction}

    def get_all_budgets(self) -> list[dict]:
        return self.list_budgets()

    def resolve(self, model_id: str, *, task_type: str = "") -> dict:
        budget = self.check_budget(model_id)
        if budget is None:
            raise ValueError(f"unknown model: {model_id}")
        return {"model_id": model_id, "task_type": task_type, "budget": budget}

    def reset(self, model_id: str) -> dict:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE model_budgets SET spent_today = 0, spent_this_month = 0 "
                "WHERE model_id = ?",
                (model_id,),
            )
            self._conn.execute(
                "DELETE FROM budget_usage WHERE model_id = ?",
                (model_id,),
            )
            self._conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"unknown model: {model_id}")
        return {"model_id": model_id, "reset": True}

    def get_transactions(self, *, model_id: str | None = None,
                         limit: int = 100) -> list[dict]:
        with self._lock:
            if model_id:
                rows = self._conn.execute(
                    "SELECT *, cost as amount FROM budget_usage WHERE model_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (model_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT *, cost as amount FROM budget_usage ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_spending_summary(self) -> dict:
        return self.get_budget_summary()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: ModelBudgetManager | None = None


def _audit_redirect(db_path: str | Path | None) -> str | Path | None:
    if db_path is None or str(db_path) == ":memory:":
        env_path = os.getenv("SYLION_DB_PATH")
        if env_path:
            return env_path
    if db_path is None or str(db_path) == ":memory:":
        return db_path
    from sylion.aeis_v2.audit_profile import is_audit_mode, resolve_db_path
    if not is_audit_mode():
        return db_path
    return resolve_db_path(Path(db_path))


def get_model_budget(db_path: str = ":memory:",
                     event_bus: EventBus | None = None) -> ModelBudgetManager:
    """Get or create the global ModelBudgetManager singleton."""
    global _instance
    if _instance is None:
        _instance = ModelBudgetManager(str(_audit_redirect(db_path)), event_bus)
    return _instance


def reset_model_budget(
    db_path: str = ":memory:",
    event_bus: EventBus | None = None,
) -> ModelBudgetManager:
    """Reset the global singleton (for testing)."""
    global _instance
    _instance = ModelBudgetManager(str(_audit_redirect(db_path)), event_bus)
    return _instance


def get_model_budget_tracker(db_path: str = ":memory:",
                             event_bus: EventBus | None = None) -> ModelBudgetManager:
    """Alias kept for ``sylion.api.monitoring_budget_routes`` which imports
    by this name. Returns the same singleton as :func:`get_model_budget`."""
    return get_model_budget(db_path, event_bus)
