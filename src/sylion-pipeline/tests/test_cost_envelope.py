"""
Tests for sylion.efficiency.cost_envelope — CostEnvelopeTracker

CRUD: record, set_budget, check_budget
Queries: get_records, get_daily_spend, get_monthly_spend, is_within_budget
Budget logic: alert threshold, daily/monthly percentage tracking
Events: verify EventBus emissions
"""

from __future__ import annotations

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.efficiency.cost_envelope import CostEnvelopeTracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
def tracker(bus):
    return CostEnvelopeTracker(event_bus=bus)


# ---------------------------------------------------------------------------
# Record cost
# ---------------------------------------------------------------------------

class TestRecord:
    def test_record_returns_expected_fields(self, tracker):
        result = tracker.record("openai", "gpt-4", input_tokens=100,
                                output_tokens=50, cost_usd=0.012,
                                task_type="summarize")
        assert result["provider"] == "openai"
        assert result["cost_usd"] == pytest.approx(0.012)
        assert "record_id" in result
        assert "timestamp" in result

    def test_record_stores_all_fields(self, tracker):
        tracker.record("anthropic", "claude-3", input_tokens=200,
                       output_tokens=100, cost_usd=0.025,
                       task_type="translate")
        records = tracker.get_records("anthropic")
        assert len(records) == 1
        r = records[0]
        assert r["provider"] == "anthropic"
        assert r["model_id"] == "claude-3"
        assert r["input_tokens"] == 200
        assert r["output_tokens"] == 100
        assert r["cost_usd"] == pytest.approx(0.025)
        assert r["task_type"] == "translate"

    def test_record_multiple_entries(self, tracker):
        for i in range(5):
            tracker.record("openai", "gpt-4", input_tokens=100,
                           output_tokens=50, cost_usd=0.01 * (i + 1))
        records = tracker.get_records("openai")
        assert len(records) == 5

    def test_record_default_task_type(self, tracker):
        tracker.record("openai", "gpt-3.5", input_tokens=10,
                       output_tokens=5, cost_usd=0.001)
        records = tracker.get_records("openai")
        assert records[0]["task_type"] == ""


# ---------------------------------------------------------------------------
# Budget management
# ---------------------------------------------------------------------------

class TestBudget:
    def test_set_budget_returns_fields(self, tracker):
        result = tracker.set_budget("openai", daily_limit=10.0,
                                    monthly_limit=200.0,
                                    alert_threshold=0.9)
        assert result["provider"] == "openai"
        assert result["daily_limit_usd"] == 10.0
        assert result["monthly_limit_usd"] == 200.0

    def test_check_budget_no_budget_defined(self, tracker):
        tracker.record("newprov", "model-1", 100, 50, 0.05)
        result = tracker.check_budget("newprov")
        assert result["alert"] is False
        assert result["reason"] == "no_budget_defined"
        assert result["daily_spend"] >= 0

    def test_check_budget_within_limits(self, tracker):
        tracker.set_budget("safe", daily_limit=100.0, monthly_limit=1000.0,
                           alert_threshold=0.8)
        tracker.record("safe", "m1", 100, 50, 0.50)
        result = tracker.check_budget("safe")
        assert result["alert"] is False
        assert result["daily_pct"] < 0.8

    def test_check_budget_alert_triggered(self, tracker):
        tracker.set_budget("spendy", daily_limit=1.0, monthly_limit=100.0,
                           alert_threshold=0.5)
        tracker.record("spendy", "m1", 100, 50, 0.80)
        result = tracker.check_budget("spendy")
        assert result["alert"] is True
        assert result["daily_pct"] >= 0.5

    def test_check_budget_pct_calculation(self, tracker):
        tracker.set_budget("exact", daily_limit=10.0, monthly_limit=100.0)
        tracker.record("exact", "m1", 100, 50, 1.0)
        result = tracker.check_budget("exact")
        assert result["daily_pct"] == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# Spend queries
# ---------------------------------------------------------------------------

class TestSpendQueries:
    def test_get_daily_spend_empty(self, tracker):
        assert tracker.get_daily_spend("nobody") == 0.0

    def test_get_daily_spend_with_records(self, tracker):
        tracker.record("prov_a", "m1", 100, 50, 0.10)
        tracker.record("prov_a", "m2", 100, 50, 0.20)
        total = tracker.get_daily_spend("prov_a")
        assert total == pytest.approx(0.30)

    def test_get_monthly_spend_with_records(self, tracker):
        tracker.record("prov_b", "m1", 100, 50, 0.50)
        tracker.record("prov_b", "m2", 100, 50, 0.30)
        total = tracker.get_monthly_spend("prov_b")
        assert total == pytest.approx(0.80)

    def test_get_daily_spend_all_providers(self, tracker):
        tracker.record("p1", "m1", 100, 50, 0.10)
        tracker.record("p2", "m1", 100, 50, 0.20)
        total = tracker.get_daily_spend()
        assert total == pytest.approx(0.30)

    def test_get_records_filtered_by_provider(self, tracker):
        tracker.record("openai", "gpt-4", 100, 50, 0.01)
        tracker.record("anthropic", "claude-3", 100, 50, 0.02)
        records = tracker.get_records("openai")
        assert all(r["provider"] == "openai" for r in records)

    def test_get_records_all_providers(self, tracker):
        tracker.record("p1", "m1", 100, 50, 0.01)
        tracker.record("p2", "m1", 100, 50, 0.02)
        records = tracker.get_records()
        assert len(records) == 2

    def test_get_records_respects_limit(self, tracker):
        for i in range(10):
            tracker.record("lim", "m1", 100, 50, 0.01)
        records = tracker.get_records("lim", limit=3)
        assert len(records) == 3


# ---------------------------------------------------------------------------
# is_within_budget
# ---------------------------------------------------------------------------

class TestIsWithinBudget:
    def test_within_when_no_budget(self, tracker):
        tracker.record("free", "m1", 100, 50, 100.0)
        assert tracker.is_within_budget("free") is True

    def test_within_when_under_limit(self, tracker):
        tracker.set_budget("ok", daily_limit=10.0, monthly_limit=100.0)
        tracker.record("ok", "m1", 100, 50, 0.50)
        assert tracker.is_within_budget("ok") is True

    def test_over_daily_limit(self, tracker):
        tracker.set_budget("over_daily", daily_limit=0.50, monthly_limit=1000.0)
        tracker.record("over_daily", "m1", 100, 50, 1.00)
        assert tracker.is_within_budget("over_daily") is False

    def test_over_monthly_limit(self, tracker):
        tracker.set_budget("over_monthly", daily_limit=1000.0, monthly_limit=0.50)
        tracker.record("over_monthly", "m1", 100, 50, 1.00)
        assert tracker.is_within_budget("over_monthly") is False


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

class TestCostEnvelopeEvents:
    def test_record_emits_event(self, tracker, bus):
        tracker.record("ev_prov", "m1", 100, 50, 0.01)
        topics = [e.topic for e in bus._captured]
        assert "efficiency.cost_envelope.recorded" in topics

    def test_set_budget_emits_event(self, tracker, bus):
        tracker.set_budget("ev_bud", daily_limit=10.0)
        topics = [e.topic for e in bus._captured]
        assert "efficiency.cost_envelope.budget_set" in topics

    def test_check_budget_emits_event_when_budget_exists(self, tracker, bus):
        tracker.set_budget("ev_chk", daily_limit=10.0, monthly_limit=100.0)
        tracker.record("ev_chk", "m1", 100, 50, 0.50)
        tracker.check_budget("ev_chk")
        topics = [e.topic for e in bus._captured]
        assert "efficiency.cost_envelope.budget_checked" in topics

    def test_record_event_payload(self, tracker, bus):
        tracker.record("ev_pay", "model-x", 200, 100, 0.05)
        ev = [e for e in bus._captured
              if e.topic == "efficiency.cost_envelope.recorded"][0]
        assert ev.payload["provider"] == "ev_pay"
        assert ev.payload["model_id"] == "model-x"
        assert ev.payload["cost_usd"] == pytest.approx(0.05)
