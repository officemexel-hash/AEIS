"""
Tests for sylion.monitoring.model_budget -- ModelBudgetManager

~40 tests covering budget configuration, usage recording, budget checks,
alert generation, alert acknowledgement, usage queries, budget summary,
edge cases, EventBus emissions, concurrency, and singleton lifecycle.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.monitoring.model_budget import (
    ModelBudgetManager,
    get_model_budget,
    reset_model_budget,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_model_budget()
    yield
    reset_model_budget()


@pytest.fixture
def bus():
    eb = EventBus()
    eb._captured: list[SylionEvent] = []
    _orig = eb.publish

    def _capture(event: SylionEvent):
        eb._captured.append(event)
        return _orig(event)

    eb.publish = _capture
    return eb


@pytest.fixture
def mgr(bus):
    return ModelBudgetManager(event_bus=bus)


@pytest.fixture
def plain_mgr():
    return ModelBudgetManager()


# ===========================================================================
# 1. Set budget
# ===========================================================================

class TestSetBudget:
    def test_returns_model_id(self, mgr):
        r = mgr.set_budget("gpt-4", daily_limit=10.0, monthly_limit=100.0)
        assert r["model_id"] == "gpt-4"

    def test_returns_daily_limit(self, mgr):
        r = mgr.set_budget("gpt-4", daily_limit=10.0, monthly_limit=100.0)
        assert r["daily_limit"] == 10.0

    def test_returns_monthly_limit(self, mgr):
        r = mgr.set_budget("gpt-4", daily_limit=10.0, monthly_limit=100.0)
        assert r["monthly_limit"] == 100.0

    def test_returns_alert_threshold(self, mgr):
        r = mgr.set_budget("gpt-4", monthly_limit=100.0,
                           alert_threshold_pct=90.0)
        assert r["alert_threshold_pct"] == 90.0

    def test_default_alert_threshold_80(self, mgr):
        r = mgr.set_budget("gpt-4", monthly_limit=100.0)
        assert r["alert_threshold_pct"] == 80.0

    def test_update_existing_budget(self, mgr):
        mgr.set_budget("gpt-4", daily_limit=10.0, monthly_limit=100.0)
        r = mgr.set_budget("gpt-4", daily_limit=20.0, monthly_limit=200.0)
        assert r["daily_limit"] == 20.0
        assert r["monthly_limit"] == 200.0

    def test_update_preserves_spending(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        mgr.record_usage("gpt-4", 1000, 30.0)
        mgr.set_budget("gpt-4", monthly_limit=200.0)
        budget = mgr.get_budget("gpt-4")
        assert budget["spent_this_month"] == 30.0

    def test_emits_budget_set(self, mgr, bus):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        topics = [e.topic for e in bus._captured]
        assert "budget_set" in topics


# ===========================================================================
# 2. Get budget
# ===========================================================================

class TestGetBudget:
    def test_get_existing(self, mgr):
        mgr.set_budget("gpt-4", daily_limit=10.0, monthly_limit=100.0)
        b = mgr.get_budget("gpt-4")
        assert b is not None
        assert b["model_id"] == "gpt-4"
        assert b["daily_limit"] == 10.0

    def test_get_nonexistent(self, mgr):
        assert mgr.get_budget("nonexistent") is None

    def test_get_reflects_spending(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        mgr.record_usage("gpt-4", 1000, 25.0)
        b = mgr.get_budget("gpt-4")
        assert b["spent_this_month"] == 25.0


# ===========================================================================
# 3. List budgets
# ===========================================================================

class TestListBudgets:
    def test_empty_list(self, plain_mgr):
        assert plain_mgr.list_budgets() == []

    def test_lists_all(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        mgr.set_budget("claude-3", monthly_limit=200.0)
        result = mgr.list_budgets()
        assert len(result) == 2

    def test_sorted_by_model_id(self, mgr):
        mgr.set_budget("claude-3", monthly_limit=200.0)
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        result = mgr.list_budgets()
        assert result[0]["model_id"] == "claude-3"
        assert result[1]["model_id"] == "gpt-4"


# ===========================================================================
# 4. Record usage
# ===========================================================================

class TestRecordUsage:
    def test_returns_usage_id(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        r = mgr.record_usage("gpt-4", 1000, 5.0)
        assert isinstance(r["usage_id"], str) and len(r["usage_id"]) > 0

    def test_returns_tokens(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        r = mgr.record_usage("gpt-4", 500, 2.0)
        assert r["tokens"] == 500

    def test_returns_cost(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        r = mgr.record_usage("gpt-4", 1000, 5.0)
        assert r["cost"] == 5.0

    def test_updates_spent_today(self, mgr):
        mgr.set_budget("gpt-4", daily_limit=50.0)
        mgr.record_usage("gpt-4", 1000, 10.0)
        r = mgr.record_usage("gpt-4", 1000, 5.0)
        assert r["spent_today"] == 15.0

    def test_updates_spent_this_month(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        mgr.record_usage("gpt-4", 1000, 10.0)
        r = mgr.record_usage("gpt-4", 1000, 5.0)
        assert r["spent_this_month"] == 15.0

    def test_auto_creates_budget_if_missing(self, mgr):
        r = mgr.record_usage("unknown-model", 1000, 5.0)
        assert r["model_id"] == "unknown-model"
        assert r["spent_this_month"] == 5.0

    def test_multiple_accumulates(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        for _ in range(5):
            mgr.record_usage("gpt-4", 1000, 10.0)
        budget = mgr.get_budget("gpt-4")
        assert budget["spent_this_month"] == 50.0

    def test_emits_usage_recorded(self, mgr, bus):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        mgr.record_usage("gpt-4", 1000, 5.0)
        topics = [e.topic for e in bus._captured]
        assert "usage_recorded" in topics


# ===========================================================================
# 5. Check budget
# ===========================================================================

class TestCheckBudget:
    def test_allowed_when_under_limit(self, mgr):
        mgr.set_budget("gpt-4", daily_limit=50.0, monthly_limit=100.0)
        mgr.record_usage("gpt-4", 1000, 10.0)
        result = mgr.check_budget("gpt-4")
        assert result["allowed"] is True

    def test_denied_when_daily_exceeded(self, mgr):
        mgr.set_budget("gpt-4", daily_limit=10.0, monthly_limit=1000.0)
        mgr.record_usage("gpt-4", 1000, 15.0)
        result = mgr.check_budget("gpt-4")
        assert result["allowed"] is False

    def test_denied_when_monthly_exceeded(self, mgr):
        mgr.set_budget("gpt-4", daily_limit=1000.0, monthly_limit=10.0)
        mgr.record_usage("gpt-4", 1000, 15.0)
        result = mgr.check_budget("gpt-4")
        assert result["allowed"] is False

    def test_remaining_daily(self, mgr):
        mgr.set_budget("gpt-4", daily_limit=100.0)
        mgr.record_usage("gpt-4", 1000, 30.0)
        result = mgr.check_budget("gpt-4")
        assert result["remaining_daily"] == pytest.approx(70.0)

    def test_remaining_monthly(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=200.0)
        mgr.record_usage("gpt-4", 1000, 50.0)
        result = mgr.check_budget("gpt-4")
        assert result["remaining_monthly"] == pytest.approx(150.0)

    def test_unlimited_when_zero(self, mgr):
        mgr.set_budget("gpt-4", daily_limit=0, monthly_limit=0)
        mgr.record_usage("gpt-4", 1000, 50.0)
        result = mgr.check_budget("gpt-4")
        assert result["remaining_daily"] == float("inf")
        assert result["remaining_monthly"] == float("inf")
        assert result["allowed"] is True

    def test_nonexistent_model_allowed(self, mgr):
        result = mgr.check_budget("unknown")
        assert result["allowed"] is True
        assert result["remaining_daily"] == float("inf")
        assert result["remaining_monthly"] == float("inf")

    def test_denied_emits_budget_exceeded(self, mgr, bus):
        mgr.set_budget("gpt-4", monthly_limit=10.0)
        mgr.record_usage("gpt-4", 1000, 15.0)
        topics = [e.topic for e in bus._captured]
        assert "budget_exceeded" in topics


# ===========================================================================
# 6. Get usage
# ===========================================================================

class TestGetUsage:
    def test_empty_usage(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        assert mgr.get_usage("gpt-4") == []

    def test_returns_usage_records(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        mgr.record_usage("gpt-4", 500, 2.0)
        mgr.record_usage("gpt-4", 1000, 5.0)
        usage = mgr.get_usage("gpt-4")
        assert len(usage) == 2

    def test_period_daily(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=1000.0)
        mgr.record_usage("gpt-4", 1000, 5.0)
        usage = mgr.get_usage("gpt-4", period="daily")
        assert len(usage) == 1

    def test_period_all(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=1000.0)
        mgr.record_usage("gpt-4", 1000, 5.0)
        usage = mgr.get_usage("gpt-4", period="all")
        assert len(usage) == 1


# ===========================================================================
# 7. Alerts
# ===========================================================================

class TestAlerts:
    def test_alert_generated_on_threshold(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0,
                       alert_threshold_pct=80.0)
        mgr.record_usage("gpt-4", 1000, 85.0)
        alerts = mgr.list_alerts(model_id="gpt-4")
        assert len(alerts) >= 1
        assert alerts[0]["alert_type"] == "monthly_threshold"

    def test_no_alert_below_threshold(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0,
                       alert_threshold_pct=80.0)
        mgr.record_usage("gpt-4", 1000, 50.0)
        alerts = mgr.list_alerts(model_id="gpt-4")
        assert len(alerts) == 0

    def test_alert_on_exceeded(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=10.0)
        mgr.record_usage("gpt-4", 1000, 15.0)
        alerts = mgr.list_alerts(model_id="gpt-4")
        exceeded = [a for a in alerts if a["alert_type"] == "budget_exceeded"]
        assert len(exceeded) >= 1

    def test_daily_threshold_alert(self, mgr):
        mgr.set_budget("gpt-4", daily_limit=100.0,
                       alert_threshold_pct=80.0)
        mgr.record_usage("gpt-4", 1000, 85.0)
        alerts = mgr.list_alerts(model_id="gpt-4")
        daily_alerts = [a for a in alerts if a["alert_type"] == "daily_threshold"]
        assert len(daily_alerts) >= 1

    def test_emits_budget_alert(self, mgr, bus):
        mgr.set_budget("gpt-4", monthly_limit=100.0,
                       alert_threshold_pct=80.0)
        mgr.record_usage("gpt-4", 1000, 85.0)
        topics = [e.topic for e in bus._captured]
        assert "budget_alert" in topics

    def test_alert_not_duplicated(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0,
                       alert_threshold_pct=50.0)
        mgr.record_usage("gpt-4", 1000, 60.0)
        mgr.record_usage("gpt-4", 1000, 10.0)
        alerts = mgr.list_alerts(model_id="gpt-4")
        threshold_alerts = [a for a in alerts
                            if a["alert_type"] == "monthly_threshold"]
        assert len(threshold_alerts) == 1


# ===========================================================================
# 8. List alerts
# ===========================================================================

class TestListAlerts:
    def test_empty_list(self, plain_mgr):
        assert plain_mgr.list_alerts() == []

    def test_filter_by_model_id(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=10.0)
        mgr.set_budget("claude-3", monthly_limit=10.0)
        mgr.record_usage("gpt-4", 1000, 15.0)
        mgr.record_usage("claude-3", 1000, 15.0)
        alerts = mgr.list_alerts(model_id="gpt-4")
        assert all(a["model_id"] == "gpt-4" for a in alerts)

    def test_filter_unacknowledged(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=10.0)
        mgr.record_usage("gpt-4", 1000, 15.0)
        alerts = mgr.list_alerts(acknowledged=False)
        assert len(alerts) >= 1
        assert all(a["acknowledged"] == 0 for a in alerts)


# ===========================================================================
# 9. Acknowledge alert
# ===========================================================================

class TestAcknowledgeAlert:
    def test_acknowledge_existing(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=10.0)
        mgr.record_usage("gpt-4", 1000, 15.0)
        alerts = mgr.list_alerts(model_id="gpt-4")
        alert_id = alerts[0]["alert_id"]
        result = mgr.acknowledge_alert(alert_id)
        assert result["acknowledged"] == 1

    def test_acknowledge_nonexistent(self, mgr):
        assert mgr.acknowledge_alert("nonexistent") is None

    def test_acknowledge_removes_from_unacknowledged(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=10.0)
        mgr.record_usage("gpt-4", 1000, 15.0)
        alerts = mgr.list_alerts(model_id="gpt-4")
        for a in alerts:
            mgr.acknowledge_alert(a["alert_id"])
        unacked = mgr.list_alerts(acknowledged=False)
        assert len(unacked) == 0


# ===========================================================================
# 10. Budget summary
# ===========================================================================

class TestGetBudgetSummary:
    def test_empty_summary(self, plain_mgr):
        s = plain_mgr.get_budget_summary()
        assert s["total_models"] == 0
        assert s["total_spent_daily"] == 0.0
        assert s["total_spent_monthly"] == 0.0
        assert s["total_alerts"] == 0

    def test_counts_models(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        mgr.set_budget("claude-3", monthly_limit=200.0)
        s = mgr.get_budget_summary()
        assert s["total_models"] == 2

    def test_totals_spending(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        mgr.set_budget("claude-3", monthly_limit=200.0)
        mgr.record_usage("gpt-4", 1000, 10.0)
        mgr.record_usage("claude-3", 1000, 20.0)
        s = mgr.get_budget_summary()
        assert s["total_spent_monthly"] == pytest.approx(30.0)

    def test_per_model_breakdown(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        mgr.record_usage("gpt-4", 1000, 25.0)
        s = mgr.get_budget_summary()
        assert len(s["models"]) == 1
        assert s["models"][0]["model_id"] == "gpt-4"
        assert s["models"][0]["spent_this_month"] == 25.0

    def test_alert_counts(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=10.0)
        mgr.record_usage("gpt-4", 1000, 15.0)
        s = mgr.get_budget_summary()
        assert s["total_alerts"] >= 1

    def test_unacknowledged_count(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=10.0)
        mgr.record_usage("gpt-4", 1000, 15.0)
        s = mgr.get_budget_summary()
        assert s["unacknowledged_alerts"] >= 1


# ===========================================================================
# 11. Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_zero_budget_unlimited(self, mgr):
        mgr.set_budget("gpt-4", daily_limit=0, monthly_limit=0)
        mgr.record_usage("gpt-4", 1000, 50.0)
        result = mgr.check_budget("gpt-4")
        assert result["allowed"] is True

    def test_exact_limit_denied(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        mgr.record_usage("gpt-4", 1000, 100.0)
        result = mgr.check_budget("gpt-4")
        assert result["allowed"] is False

    def test_just_under_limit_allowed(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=100.0)
        mgr.record_usage("gpt-4", 1000, 99.99)
        result = mgr.check_budget("gpt-4")
        assert result["allowed"] is True

    def test_multiple_models_independent(self, mgr):
        mgr.set_budget("gpt-4", monthly_limit=10.0)
        mgr.set_budget("claude-3", monthly_limit=1000.0)
        mgr.record_usage("gpt-4", 1000, 15.0)
        mgr.record_usage("claude-3", 1000, 5.0)
        assert mgr.check_budget("gpt-4")["allowed"] is False
        assert mgr.check_budget("claude-3")["allowed"] is True


# ===========================================================================
# 12. Concurrency
# ===========================================================================

class TestConcurrency:
    def test_concurrent_record_usage(self, plain_mgr):
        plain_mgr.set_budget("gpt-4", daily_limit=10000.0,
                             monthly_limit=100000.0)
        errors = []

        def worker():
            try:
                for _ in range(50):
                    plain_mgr.record_usage("gpt-4", 100, 1.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        budget = plain_mgr.get_budget("gpt-4")
        assert budget["spent_this_month"] == 200.0


# ===========================================================================
# 13. Singleton
# ===========================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        inst = get_model_budget()
        assert isinstance(inst, ModelBudgetManager)

    def test_get_is_idempotent(self):
        a = get_model_budget()
        b = get_model_budget()
        assert a is b

    def test_reset_clears_singleton(self):
        a = get_model_budget()
        reset_model_budget()
        b = get_model_budget()
        assert a is not b

    def test_double_reset_safe(self):
        reset_model_budget()
        reset_model_budget()
        inst = get_model_budget()
        assert isinstance(inst, ModelBudgetManager)
