"""gRPC wrapper tests for advisor pricing."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from sylion.aeis.advisor.pricing._models import CostEstimate, Source
from sylion.aeis.advisor.pricing.grpc_server import PricingServicer


def test_get_cost_maps_to_proto():
    service = SimpleNamespace(
        get_cost=lambda **kwargs: CostEstimate(
            model_id="claude-sonnet-4-6",
            provider_id="anthropic",
            total_cost_usd=Decimal("0.018000"),
            input_cost_usd=Decimal("0.003000"),
            output_cost_usd=Decimal("0.015000"),
            cache_cost_usd=Decimal("0"),
            source=Source.PROFILE,
            is_assumption=False,
            assumption_note=None,
            pricing_effective_from=datetime.now(timezone.utc),
            pricing_id="price-1",
        )
    )
    servicer = PricingServicer(service=service)
    response = servicer.GetCost(
        SimpleNamespace(
            model_id="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=1000,
            cache_hit_tokens=0,
        ),
        None,
    )
    assert response.model_id == "claude-sonnet-4-6"
    assert response.provider_id == "anthropic"
    assert response.total_cost_usd == "0.018000"
