"""Cost estimation logic for advisor pricing."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sylion.aeis.advisor.pricing import _db
from sylion.aeis.advisor.pricing._models import CostEstimate, Source

_MICRO = Decimal("0.000001")


def estimate_cost(
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    cache_hit_tokens: int = 0,
) -> CostEstimate:
    """Compute a cost estimate for one model call."""
    pricing = _db.get_active_pricing(model_id)
    provider_id = _lookup_provider(model_id)
    if pricing is None:
        return CostEstimate(
            model_id=model_id,
            provider_id=provider_id,
            total_cost_usd=Decimal("0"),
            input_cost_usd=Decimal("0"),
            output_cost_usd=Decimal("0"),
            cache_cost_usd=Decimal("0"),
            source=Source.ASSUMPTION,
            is_assumption=True,
            assumption_note="No pricing data available for this model",
            pricing_effective_from=datetime.now(timezone.utc),
            pricing_id="",
        )

    input_cost = _per_call_cost(input_tokens, pricing["input_tokens_usd_per_million"])
    output_cost = _per_call_cost(output_tokens, pricing["output_tokens_usd_per_million"])
    cache_cost = _per_call_cost(cache_hit_tokens, pricing["cache_hit_tokens_usd_per_million"])
    total_cost = (input_cost + output_cost + cache_cost).quantize(_MICRO, rounding=ROUND_HALF_UP)
    return CostEstimate(
        model_id=model_id,
        provider_id=provider_id,
        total_cost_usd=total_cost,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        cache_cost_usd=cache_cost,
        source=Source(str(pricing["source"])),
        is_assumption=bool(pricing["is_assumption"]),
        assumption_note=pricing.get("assumption_note"),
        pricing_effective_from=pricing["effective_from"],
        pricing_id=str(pricing["pricing_id"]),
    )


def effective_cost_estimate(
    operator_id: str,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    cache_hit_tokens: int = 0,
) -> tuple[CostEstimate, bool]:
    """Return the effective call cost after subscription-first routing."""
    from sylion.aeis.advisor.subscription.quota_tracker import get_quota_status

    quota = get_quota_status(operator_id, model_id)
    if quota and quota.has_quota:
        now = datetime.now(timezone.utc)
        return (
            CostEstimate(
                model_id=model_id,
                provider_id=_lookup_provider(model_id),
                total_cost_usd=Decimal("0"),
                input_cost_usd=Decimal("0"),
                output_cost_usd=Decimal("0"),
                cache_cost_usd=Decimal("0"),
                source=Source.SUBSCRIPTION,
                is_assumption=False,
                assumption_note=(
                    f"Subscription {quota.plan_id} "
                    f"(remaining: {quota.remaining_tokens} tokens, {quota.remaining_usd} USD)"
                ),
                pricing_effective_from=now,
                pricing_id=f"sub:{quota.subscription_id}",
            ),
            True,
        )

    return estimate_cost(model_id, input_tokens, output_tokens, cache_hit_tokens), False


def _lookup_provider(model_id: str) -> str:
    model = _db.get_model(model_id)
    if model is None:
        return "unknown"
    return str(model["provider_id"])


def _per_call_cost(tokens: int, per_million: Decimal | None) -> Decimal:
    if tokens <= 0 or per_million is None:
        return Decimal("0")
    cost = (Decimal(tokens) / Decimal("1000000")) * Decimal(per_million)
    return cost.quantize(_MICRO, rounding=ROUND_HALF_UP)
