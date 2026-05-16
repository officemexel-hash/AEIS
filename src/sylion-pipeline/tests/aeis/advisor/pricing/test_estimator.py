"""Estimator tests for advisor pricing."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sylion.aeis.advisor.pricing.estimator import estimate_cost
from sylion.aeis.advisor.pricing._models import Source


def test_cost_estimate_correctness(monkeypatch):
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.estimator._db.get_active_pricing",
        lambda model_id: {
            "pricing_id": "price-1",
            "input_tokens_usd_per_million": Decimal("3.00"),
            "output_tokens_usd_per_million": Decimal("15.00"),
            "cache_hit_tokens_usd_per_million": Decimal("0.30"),
            "source": "profile",
            "is_assumption": False,
            "assumption_note": None,
            "effective_from": datetime.now(timezone.utc),
        },
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.estimator._db.get_model",
        lambda model_id: {"provider_id": "anthropic"},
    )

    estimate = estimate_cost("claude-sonnet-4-6", 1000, 1000)
    assert estimate.total_cost_usd == Decimal("0.018000")
    assert estimate.source == Source.PROFILE
    assert estimate.is_assumption is False


def test_assumption_flag_when_unknown_model(monkeypatch):
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.estimator._db.get_active_pricing",
        lambda model_id: None,
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.estimator._db.get_model",
        lambda model_id: None,
    )

    estimate = estimate_cost("missing-model", 100, 200)
    assert estimate.is_assumption is True
    assert estimate.provider_id == "unknown"
    assert "No pricing data" in estimate.assumption_note
