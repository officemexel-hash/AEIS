from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sylion.aeis.advisor.pricing._models import CostEstimate, Source
from sylion.aeis.advisor.pricing.estimator import effective_cost_estimate


def test_effective_cost_with_subscription_returns_zero(monkeypatch):
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.estimator._db.get_model",
        lambda model_id: {"provider_id": "anthropic"},
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.subscription.quota_tracker.get_quota_status",
        lambda operator_id, model_id: type(
            "Quota",
            (),
            {
                "has_quota": True,
                "plan_id": "claude-pro",
                "remaining_tokens": 4_000_000,
                "remaining_usd": Decimal("0"),
                "subscription_id": "sub-1",
            },
        )(),
    )

    estimate, used_subscription = effective_cost_estimate("op-1", "claude-sonnet-4-6", 2000, 1000)
    assert used_subscription is True
    assert estimate.total_cost_usd == Decimal("0")
    assert estimate.source == Source.SUBSCRIPTION
    assert estimate.pricing_id == "sub:sub-1"


def test_effective_cost_falls_back_to_payg(monkeypatch):
    fallback = CostEstimate(
        model_id="gpt-5",
        provider_id="openai",
        total_cost_usd=Decimal("0.123456"),
        input_cost_usd=Decimal("0.023456"),
        output_cost_usd=Decimal("0.100000"),
        cache_cost_usd=Decimal("0"),
        source=Source.MEASURED,
        is_assumption=False,
        assumption_note=None,
        pricing_effective_from=datetime.now(timezone.utc),
        pricing_id="price-123",
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.subscription.quota_tracker.get_quota_status",
        lambda operator_id, model_id: None,
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.estimator.estimate_cost",
        lambda model_id, input_tokens, output_tokens, cache_hit_tokens=0: fallback,
    )

    estimate, used_subscription = effective_cost_estimate("op-1", "gpt-5", 2000, 1000)
    assert used_subscription is False
    assert estimate == fallback
