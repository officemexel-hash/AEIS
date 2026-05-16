"""
Tests for sylion.efficiency.cost_monitor -- CostMonitorService

Alert generation: thresholds at 50%, 75%, 90%, 100%
Alert persistence: SQLite round-trip
Realtime summary: per-provider spend, budget remaining, health status
SSE subscribe/unsubscribe: asyncio.Queue lifecycle
Budget check trigger: manual check via routes mock
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from sylion.efficiency.cost_envelope import CostEnvelopeTracker
from sylion.efficiency.cost_monitor import (
    ALERT_TYPE_BUDGET_EXCEEDED,
    ALERT_TYPE_BUDGET_WARNING,
    CostAlert,
    CostMonitorService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def envelope():
    """Fresh in-memory CostEnvelopeTracker."""
    return CostEnvelopeTracker()


@pytest.fixture
def monitor(envelope):
    """Fresh CostMonitorService backed by an in-memory envelope and DB."""
    return CostMonitorService(envelope=envelope)


def _seed_spend(envelope: CostEnvelopeTracker, provider: str,
                cost_usd: float, model_id: str = "test-model"):
    """Record a cost entry for the given provider."""
    envelope.record(provider, model_id, input_tokens=100,
                    output_tokens=50, cost_usd=cost_usd)


# ---------------------------------------------------------------------------
# CostAlert dataclass
# ---------------------------------------------------------------------------

class TestCostAlert:
    def test_auto_id_and_timestamp(self):
        alert = CostAlert(alert_type="budget_warning", provider="openai")
        assert alert.alert_id != ""
        assert alert.timestamp > 0

    def test_to_dict(self):
        alert = CostAlert(
            alert_type="budget_exceeded",
            provider="anthropic",
            current_spend=100.0,
            limit=50.0,
            threshold_pct=1.0,
            message="Budget exceeded",
        )
        d = alert.to_dict()
        assert d["alert_type"] == "budget_exceeded"
        assert d["provider"] == "anthropic"
        assert d["current_spend"] == 100.0
        assert "alert_id" in d


# ---------------------------------------------------------------------------
# Alert generation at thresholds
# ---------------------------------------------------------------------------

class TestCheckBudgets:
    def test_no_alerts_when_under_50pct(self, monitor, envelope):
        envelope.set_budget("cheap", daily_limit=100.0, monthly_limit=1000.0)
        _seed_spend(envelope, "cheap", 10.0)
        alerts = monitor.check_budgets()
        assert len(alerts) == 0

    def test_alert_at_50pct_daily(self, monitor, envelope):
        envelope.set_budget("halfway", daily_limit=100.0, monthly_limit=10000.0)
        _seed_spend(envelope, "halfway", 55.0)
        alerts = monitor.check_budgets()
        types = [a.alert_type for a in alerts]
        assert ALERT_TYPE_BUDGET_WARNING in types
        pcts = [a.threshold_pct for a in alerts if a.provider == "halfway"]
        assert 0.50 in pcts

    def test_alert_at_75pct_daily(self, monitor, envelope):
        envelope.set_budget("ramping", daily_limit=100.0, monthly_limit=10000.0)
        _seed_spend(envelope, "ramping", 80.0)
        alerts = monitor.check_budgets()
        pcts = [a.threshold_pct for a in alerts]
        assert 0.50 in pcts
        assert 0.75 in pcts

    def test_alert_at_90pct_daily(self, monitor, envelope):
        envelope.set_budget("near_limit", daily_limit=100.0, monthly_limit=10000.0)
        _seed_spend(envelope, "near_limit", 95.0)
        alerts = monitor.check_budgets()
        pcts = [a.threshold_pct for a in alerts]
        assert 0.50 in pcts
        assert 0.75 in pcts
        assert 0.90 in pcts

    def test_budget_exceeded_at_100pct(self, monitor, envelope):
        envelope.set_budget("overspent", daily_limit=10.0, monthly_limit=10000.0)
        _seed_spend(envelope, "overspent", 12.0)
        alerts = monitor.check_budgets()
        types = [a.alert_type for a in alerts]
        assert ALERT_TYPE_BUDGET_EXCEEDED in types
        pcts = [a.threshold_pct for a in alerts]
        assert 1.00 in pcts

    def test_no_duplicate_alerts_on_recheck(self, monitor, envelope):
        envelope.set_budget("once", daily_limit=100.0, monthly_limit=10000.0)
        _seed_spend(envelope, "once", 55.0)
        first = monitor.check_budgets()
        assert len(first) > 0
        second = monitor.check_budgets()
        assert len(second) == 0

    def test_monthly_budget_alert(self, monitor, envelope):
        envelope.set_budget("monthly_check", daily_limit=100000.0,
                            monthly_limit=100.0)
        _seed_spend(envelope, "monthly_check", 55.0)
        alerts = monitor.check_budgets()
        monthly_alerts = [a for a in alerts
                          if "Monthly" in a.message]
        assert len(monthly_alerts) > 0
        assert monthly_alerts[0].threshold_pct == 0.50

    def test_no_alerts_without_budgets(self, monitor, envelope):
        _seed_spend(envelope, "nobudget", 99999.0)
        alerts = monitor.check_budgets()
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# Alert persistence
# ---------------------------------------------------------------------------

class TestAlertPersistence:
    def test_get_alerts_empty(self, monitor):
        alerts = monitor.get_alerts()
        assert alerts == []

    def test_alerts_persisted_after_check(self, monitor, envelope):
        envelope.set_budget("persist", daily_limit=100.0, monthly_limit=10000.0)
        _seed_spend(envelope, "persist", 55.0)
        monitor.check_budgets()
        alerts = monitor.get_alerts()
        assert len(alerts) > 0
        assert alerts[0]["provider"] == "persist"

    def test_get_alerts_respects_limit(self, monitor, envelope):
        envelope.set_budget("limited", daily_limit=10.0, monthly_limit=10000.0)
        _seed_spend(envelope, "limited", 12.0)
        monitor.check_budgets()
        all_alerts = monitor.get_alerts(limit=100)
        limited = monitor.get_alerts(limit=1)
        assert len(limited) <= 1
        assert len(all_alerts) >= len(limited)

    def test_alert_fields_roundtrip(self, monitor, envelope):
        envelope.set_budget("fields", daily_limit=100.0, monthly_limit=10000.0)
        _seed_spend(envelope, "fields", 55.0)
        monitor.check_budgets()
        alerts = monitor.get_alerts()
        a = alerts[0]
        assert "alert_id" in a
        assert "alert_type" in a
        assert "provider" in a
        assert "current_spend" in a
        assert "limit_value" in a
        assert "threshold_pct" in a
        assert "timestamp" in a
        assert "message" in a


# ---------------------------------------------------------------------------
# Realtime summary
# ---------------------------------------------------------------------------

class TestRealtimeSummary:
    def test_empty_summary(self, monitor):
        summary = monitor.get_realtime_summary()
        assert "providers" in summary
        assert "timestamp" in summary
        assert summary["providers"] == []

    def test_summary_with_spend_no_budget(self, monitor, envelope):
        _seed_spend(envelope, "freebie", 5.0)
        summary = monitor.get_realtime_summary()
        providers = {p["provider"]: p for p in summary["providers"]}
        assert "freebie" in providers
        assert providers["freebie"]["status"] == "healthy"
        assert providers["freebie"]["daily_limit"] is None

    def test_summary_healthy_status(self, monitor, envelope):
        envelope.set_budget("ok", daily_limit=100.0, monthly_limit=1000.0)
        _seed_spend(envelope, "ok", 5.0)
        summary = monitor.get_realtime_summary()
        providers = {p["provider"]: p for p in summary["providers"]}
        assert providers["ok"]["status"] == "healthy"
        assert providers["ok"]["daily_pct"] < 0.5

    def test_summary_warning_status(self, monitor, envelope):
        envelope.set_budget("warn", daily_limit=100.0, monthly_limit=1000.0)
        _seed_spend(envelope, "warn", 80.0)
        summary = monitor.get_realtime_summary()
        providers = {p["provider"]: p for p in summary["providers"]}
        assert providers["warn"]["status"] == "warning"

    def test_summary_critical_status(self, monitor, envelope):
        envelope.set_budget("crit", daily_limit=100.0, monthly_limit=1000.0)
        _seed_spend(envelope, "crit", 95.0)
        summary = monitor.get_realtime_summary()
        providers = {p["provider"]: p for p in summary["providers"]}
        assert providers["crit"]["status"] == "critical"

    def test_summary_over_budget_status(self, monitor, envelope):
        envelope.set_budget("over", daily_limit=100.0, monthly_limit=1000.0)
        _seed_spend(envelope, "over", 110.0)
        summary = monitor.get_realtime_summary()
        providers = {p["provider"]: p for p in summary["providers"]}
        assert providers["over"]["status"] == "over_budget"

    def test_summary_remaining_calculation(self, monitor, envelope):
        envelope.set_budget("remain", daily_limit=100.0, monthly_limit=1000.0)
        _seed_spend(envelope, "remain", 30.0)
        summary = monitor.get_realtime_summary()
        providers = {p["provider"]: p for p in summary["providers"]}
        assert providers["remain"]["daily_remaining"] == pytest.approx(70.0)
        assert providers["remain"]["monthly_remaining"] is not None


# ---------------------------------------------------------------------------
# SSE subscribe / unsubscribe
# ---------------------------------------------------------------------------

class TestSSESubscribers:
    def test_subscribe_returns_queue(self, monitor):
        queue = monitor.subscribe()
        assert isinstance(queue, asyncio.Queue)
        monitor.unsubscribe(queue)

    def test_unsubscribe_removes_queue(self, monitor):
        q1 = monitor.subscribe()
        q2 = monitor.subscribe()
        assert len(monitor._sse_subscribers) >= 2
        monitor.unsubscribe(q1)
        assert q1 not in monitor._sse_subscribers
        assert q2 in monitor._sse_subscribers
        monitor.unsubscribe(q2)

    def test_unsubscribe_idempotent(self, monitor):
        q = monitor.subscribe()
        monitor.unsubscribe(q)
        monitor.unsubscribe(q)  # should not raise

    def test_push_alert_delivers_to_subscribers(self, monitor, envelope):
        envelope.set_budget("sse_push", daily_limit=10.0, monthly_limit=10000.0)
        _seed_spend(envelope, "sse_push", 12.0)

        q = monitor.subscribe()
        try:
            monitor.check_budgets()
            # Multiple alerts are pushed (50%, 75%, 90%, 100% all crossed)
            assert not q.empty()
            import json
            all_alerts = []
            while not q.empty():
                data = q.get_nowait()
                all_alerts.append(json.loads(data))
            providers = [a["provider"] for a in all_alerts]
            assert all(p == "sse_push" for p in providers)
            types = [a["alert_type"] for a in all_alerts]
            assert ALERT_TYPE_BUDGET_EXCEEDED in types
        finally:
            monitor.unsubscribe(q)

    def test_push_to_multiple_subscribers(self, monitor, envelope):
        envelope.set_budget("multi_sub", daily_limit=10.0, monthly_limit=10000.0)
        _seed_spend(envelope, "multi_sub", 12.0)

        q1 = monitor.subscribe()
        q2 = monitor.subscribe()
        try:
            monitor.check_budgets()
            assert not q1.empty()
            assert not q2.empty()
        finally:
            monitor.unsubscribe(q1)
            monitor.unsubscribe(q2)


# ---------------------------------------------------------------------------
# Route-level mocks (efficiency_routes imports)
# ---------------------------------------------------------------------------

class TestRouteMocks:
    """Verify that the cost_monitor module can be imported and used
    from route-like contexts with mocked dependencies."""

    def test_get_cost_monitor_singleton(self):
        from sylion.efficiency.cost_monitor import get_cost_monitor
        # Reset singleton for test isolation
        import sylion.efficiency.cost_monitor as cm
        cm._monitor = None
        m = get_cost_monitor(envelope=CostEnvelopeTracker())
        assert isinstance(m, CostMonitorService)
        # Second call returns same instance
        m2 = get_cost_monitor()
        assert m2 is m
        cm._monitor = None

    def test_check_budgets_with_mock_envelope(self):
        envelope = CostEnvelopeTracker()
        monitor = CostMonitorService(envelope=envelope)
        envelope.set_budget("mockprov", daily_limit=10.0, monthly_limit=1000.0)
        _seed_spend(envelope, "mockprov", 8.0)
        alerts = monitor.check_budgets()
        assert len(alerts) > 0
        assert all(isinstance(a, CostAlert) for a in alerts)
