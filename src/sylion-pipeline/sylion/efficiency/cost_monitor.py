"""
SYLION Efficiency -- Live Cost Monitor with SSE push

Real-time budget alerting layer on top of CostEnvelopeTracker.
Generates alerts at 50%, 75%, 90%, 100% spend thresholds and pushes
them to SSE subscriber queues.

SQLite-backed. Thread-safe. Async-compatible via asyncio.Queue.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sylion.efficiency.cost_envelope import CostEnvelopeTracker, get_cost_envelope_tracker

log = logging.getLogger("sylion.efficiency.cost_monitor")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

ALERT_THRESHOLDS = [0.50, 0.75, 0.90, 1.00]

ALERT_TYPE_BUDGET_WARNING = "budget_warning"
ALERT_TYPE_BUDGET_EXCEEDED = "budget_exceeded"
ALERT_TYPE_RATE_SPIKE = "rate_spike"


@dataclass
class CostAlert:
    """A single cost alert event."""

    alert_id: str = ""
    alert_type: str = ""          # budget_warning | budget_exceeded | rate_spike
    provider: str = ""
    model_id: str = ""
    current_spend: float = 0.0
    limit: float = 0.0
    threshold_pct: float = 0.0
    timestamp: float = 0.0
    message: str = ""

    def __post_init__(self):
        if not self.alert_id:
            self.alert_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Cost Monitor Service
# ---------------------------------------------------------------------------

class CostMonitorService:
    """Real-time budget alerting with SSE subscriber management.

    Checks active budgets in CostEnvelopeTracker, generates alerts when
    spend crosses configured thresholds, persists alerts to SQLite, and
    pushes new alerts to SSE subscriber queues.

    Thread-safe. SQLite-backed.
    """

    def __init__(self, envelope: CostEnvelopeTracker | None = None,
                 db_path: str | Path | None = None):
        self._envelope = envelope
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

        # SSE subscriber management
        self._sse_subscribers: list[asyncio.Queue] = []
        self._sub_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Table setup
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cost_alerts (
                alert_id       TEXT PRIMARY KEY,
                alert_type     TEXT    NOT NULL DEFAULT '',
                provider       TEXT    NOT NULL DEFAULT '',
                model_id       TEXT    NOT NULL DEFAULT '',
                current_spend  REAL    NOT NULL DEFAULT 0.0,
                limit_value    REAL    NOT NULL DEFAULT 0.0,
                threshold_pct  REAL    NOT NULL DEFAULT 0.0,
                timestamp      REAL    NOT NULL,
                message        TEXT    NOT NULL DEFAULT ''
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ca_provider ON cost_alerts(provider)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ca_ts ON cost_alerts(timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ca_type ON cost_alerts(alert_type)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Envelope access
    # ------------------------------------------------------------------

    @property
    def envelope(self) -> CostEnvelopeTracker:
        if self._envelope is None:
            self._envelope = get_cost_envelope_tracker()
        return self._envelope

    # ------------------------------------------------------------------
    # Budget checking
    # ------------------------------------------------------------------

    def check_budgets(self) -> list[CostAlert]:
        """Check all active budgets and generate alerts for crossed thresholds.

        For each provider with a defined budget, looks at daily and monthly
        spend. Generates alerts at 50%, 75%, 90%, 100% thresholds, but only
        if an alert at that exact threshold has not already been fired for
        the current budget period.

        Returns list of newly generated alerts.
        """
        new_alerts: list[CostAlert] = []

        # Get all providers with budgets from the envelope tracker
        rows = self.envelope._conn.execute(
            "SELECT provider, daily_limit_usd, monthly_limit_usd, alert_threshold "
            "FROM cost_budgets"
        ).fetchall()

        for row in rows:
            provider = row["provider"]
            daily_limit = row["daily_limit_usd"]
            monthly_limit = row["monthly_limit_usd"]

            # Check daily budget
            if daily_limit and daily_limit > 0:
                daily_spend = self.envelope.get_daily_spend(provider)
                daily_pct = daily_spend / daily_limit
                daily_alerts = self._check_thresholds(
                    provider=provider,
                    spend=daily_spend,
                    limit=daily_limit,
                    pct=daily_pct,
                    period="daily",
                )
                new_alerts.extend(daily_alerts)

            # Check monthly budget
            if monthly_limit and monthly_limit > 0:
                monthly_spend = self.envelope.get_monthly_spend(provider)
                monthly_pct = monthly_spend / monthly_limit
                monthly_alerts = self._check_thresholds(
                    provider=provider,
                    spend=monthly_spend,
                    limit=monthly_limit,
                    pct=monthly_pct,
                    period="monthly",
                )
                new_alerts.extend(monthly_alerts)

        # Persist and push all new alerts
        for alert in new_alerts:
            self._persist_alert(alert)
            self._push_alert(alert)

        if new_alerts:
            log.info("check_budgets: generated %d new alerts", len(new_alerts))

        return new_alerts

    def _check_thresholds(self, provider: str, spend: float,
                          limit: float, pct: float,
                          period: str) -> list[CostAlert]:
        """Check spend against all thresholds and return new alerts."""
        alerts: list[CostAlert] = []

        for threshold in ALERT_THRESHOLDS:
            if pct < threshold:
                continue

            # Check if we already fired an alert at this threshold
            if self._already_alerted(provider, threshold, period):
                continue

            alert_type = (
                ALERT_TYPE_BUDGET_EXCEEDED
                if threshold >= 1.0
                else ALERT_TYPE_BUDGET_WARNING
            )

            message = (
                f"{period.capitalize()} budget {threshold:.0%} reached for "
                f"{provider}: ${spend:.2f} of ${limit:.2f}"
            )

            alert = CostAlert(
                alert_type=alert_type,
                provider=provider,
                model_id="",
                current_spend=round(spend, 6),
                limit=round(limit, 2),
                threshold_pct=threshold,
                message=message,
            )
            alerts.append(alert)

        return alerts

    def _already_alerted(self, provider: str, threshold: float,
                         period: str) -> bool:
        """Check if an alert was already fired for this threshold in this period."""
        period_seconds = 86400 if period == "daily" else 86400 * 31
        cutoff = time.time() - period_seconds

        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM cost_alerts "
                "WHERE provider = ? AND threshold_pct = ? AND timestamp >= ? "
                "AND message LIKE ?",
                (provider, threshold, cutoff, f"{period.capitalize()}%"),
            ).fetchone()
            return row["cnt"] > 0

    def _persist_alert(self, alert: CostAlert):
        """Write alert to SQLite."""
        with self._lock:
            self._conn.execute("""
                INSERT INTO cost_alerts
                    (alert_id, alert_type, provider, model_id,
                     current_spend, limit_value, threshold_pct,
                     timestamp, message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id, alert.alert_type, alert.provider,
                alert.model_id, alert.current_spend, alert.limit,
                alert.threshold_pct, alert.timestamp, alert.message,
            ))
            self._conn.commit()

    # ------------------------------------------------------------------
    # Alert queries
    # ------------------------------------------------------------------

    def get_alerts(self, limit: int = 50) -> list[dict]:
        """Return recent alerts, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM cost_alerts ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Realtime summary
    # ------------------------------------------------------------------

    def get_realtime_summary(self) -> dict:
        """Return per-provider current spend, budget remaining, and health status.

        Returns:
            {
                "providers": [
                    {
                        "provider": str,
                        "daily_spend": float,
                        "monthly_spend": float,
                        "daily_limit": float | None,
                        "monthly_limit": float | None,
                        "daily_remaining": float | None,
                        "monthly_remaining": float | None,
                        "daily_pct": float,
                        "monthly_pct": float,
                        "status": "healthy" | "warning" | "critical" | "over_budget"
                    },
                    ...
                ],
                "timestamp": float
            }
        """
        providers_map: dict[str, dict] = {}

        # Collect all providers that have records or budgets
        record_rows = self.envelope._conn.execute(
            "SELECT DISTINCT provider FROM cost_records"
        ).fetchall()
        budget_rows = self.envelope._conn.execute(
            "SELECT provider, daily_limit_usd, monthly_limit_usd FROM cost_budgets"
        ).fetchall()

        for row in record_rows:
            providers_map[row["provider"]] = {
                "daily_limit": None,
                "monthly_limit": None,
            }

        budget_lookup: dict[str, dict] = {}
        for row in budget_rows:
            budget_lookup[row["provider"]] = {
                "daily_limit": row["daily_limit_usd"],
                "monthly_limit": row["monthly_limit_usd"],
            }
            providers_map.setdefault(row["provider"], {
                "daily_limit": None,
                "monthly_limit": None,
            })

        provider_list: list[dict] = []
        for provider in sorted(providers_map.keys()):
            daily_spend = self.envelope.get_daily_spend(provider)
            monthly_spend = self.envelope.get_monthly_spend(provider)
            daily_limit = budget_lookup.get(provider, {}).get("daily_limit")
            monthly_limit = budget_lookup.get(provider, {}).get("monthly_limit")

            daily_pct = (daily_spend / daily_limit) if daily_limit and daily_limit > 0 else 0.0
            monthly_pct = (monthly_spend / monthly_limit) if monthly_limit and monthly_limit > 0 else 0.0

            daily_remaining = (daily_limit - daily_spend) if daily_limit is not None else None
            monthly_remaining = (monthly_limit - monthly_spend) if monthly_limit is not None else None

            max_pct = max(daily_pct, monthly_pct)
            if max_pct >= 1.0:
                status = "over_budget"
            elif max_pct >= 0.9:
                status = "critical"
            elif max_pct >= 0.75:
                status = "warning"
            else:
                status = "healthy"

            provider_list.append({
                "provider": provider,
                "daily_spend": round(daily_spend, 6),
                "monthly_spend": round(monthly_spend, 6),
                "daily_limit": daily_limit,
                "monthly_limit": monthly_limit,
                "daily_remaining": round(daily_remaining, 6) if daily_remaining is not None else None,
                "monthly_remaining": round(monthly_remaining, 6) if monthly_remaining is not None else None,
                "daily_pct": round(daily_pct, 4),
                "monthly_pct": round(monthly_pct, 4),
                "status": status,
            })

        return {
            "providers": provider_list,
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------
    # SSE subscriber management
    # ------------------------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        """Create a new SSE subscriber queue and return it."""
        queue: asyncio.Queue = asyncio.Queue()
        with self._sub_lock:
            self._sse_subscribers.append(queue)
        log.info("SSE subscriber added (total: %d)", len(self._sse_subscribers))
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Remove a subscriber queue."""
        with self._sub_lock:
            try:
                self._sse_subscribers.remove(queue)
            except ValueError:
                pass
        log.info("SSE subscriber removed (total: %d)", len(self._sse_subscribers))

    def _push_alert(self, alert: CostAlert):
        """Push alert JSON to all SSE subscriber queues."""
        data = json.dumps(alert.to_dict())
        with self._sub_lock:
            dead: list[asyncio.Queue] = []
            for q in self._sse_subscribers:
                try:
                    q.put_nowait(data)
                except asyncio.QueueFull:
                    dead.append(q)
            # Remove queues that are full (stale subscribers)
            for q in dead:
                self._sse_subscribers.remove(q)


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_monitor: CostMonitorService | None = None


def get_cost_monitor(
    envelope: CostEnvelopeTracker | None = None,
    db_path: str | Path | None = None,
) -> CostMonitorService:
    """Return the global CostMonitorService singleton."""
    global _monitor
    if _monitor is None:
        _monitor = CostMonitorService(envelope=envelope, db_path=db_path)
    return _monitor
