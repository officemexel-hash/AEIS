from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sylion.aeis.advisor.subscription.quota_tracker import (
    _compute_billing_period,
    consume_quota,
    get_quota_status,
)


def test_get_quota_status_no_subscription(monkeypatch):
    monkeypatch.setattr(
        "sylion.aeis.advisor.subscription.quota_tracker.get_active_subscription_for_model",
        lambda operator_id, model_id: None,
    )

    assert get_quota_status("op-1", "claude-sonnet-4-6") is None


def test_get_quota_status_remaining(monkeypatch):
    monkeypatch.setattr(
        "sylion.aeis.advisor.subscription.quota_tracker.get_active_subscription_for_model",
        lambda operator_id, model_id: {
            "subscription_id": "sub-1",
            "plan_id": "claude-pro",
            "reset_day_of_month": 1,
            "monthly_quota_tokens": 5_000_000,
            "monthly_quota_usd": None,
        },
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.subscription.quota_tracker._db.get_quota_usage",
        lambda subscription_id, period_start: {
            "tokens_consumed": 1_250_000,
            "usd_consumed": Decimal("0"),
        },
    )

    status = get_quota_status("op-1", "claude-sonnet-4-6")
    assert status is not None
    assert status.has_quota is True
    assert status.remaining_tokens == 3_750_000
    assert status.plan_id == "claude-pro"


def test_get_quota_status_exhausted(monkeypatch):
    monkeypatch.setattr(
        "sylion.aeis.advisor.subscription.quota_tracker.get_active_subscription_for_model",
        lambda operator_id, model_id: {
            "subscription_id": "sub-2",
            "plan_id": "openrouter-credits",
            "reset_day_of_month": 1,
            "monthly_quota_tokens": 1000,
            "monthly_quota_usd": Decimal("5.00"),
        },
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.subscription.quota_tracker._db.get_quota_usage",
        lambda subscription_id, period_start: {
            "tokens_consumed": 1000,
            "usd_consumed": Decimal("5.00"),
        },
    )

    status = get_quota_status("op-1", "gpt-5")
    assert status is not None
    assert status.has_quota is False
    assert status.remaining_tokens == 0
    assert status.remaining_usd == Decimal("0")


def test_consume_quota_increments(monkeypatch):
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        "sylion.aeis.advisor.subscription.quota_tracker._db.get_subscription",
        lambda subscription_id: {
            "subscription_id": subscription_id,
            "reset_day_of_month": 15,
        },
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.subscription.quota_tracker._db.upsert_quota_usage",
        lambda subscription_id, period_start, period_end, tokens, cost_usd: calls.append(
            (subscription_id, period_start, period_end, tokens, cost_usd)
        ),
    )

    consume_quota("sub-3", 1234, Decimal("0.4567"))

    assert len(calls) == 1
    assert calls[0][0] == "sub-3"
    assert calls[0][3] == 1234
    assert calls[0][4] == Decimal("0.4567")


def test_billing_period_boundary():
    now = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
    period_start, period_end = _compute_billing_period(now, 15)
    assert period_start == datetime(2026, 3, 15, tzinfo=timezone.utc)
    assert period_end == datetime(2026, 4, 15, tzinfo=timezone.utc)

    now = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
    period_start, period_end = _compute_billing_period(now, 15)
    assert period_start == datetime(2026, 4, 15, tzinfo=timezone.utc)
    assert period_end == datetime(2026, 5, 15, tzinfo=timezone.utc)
