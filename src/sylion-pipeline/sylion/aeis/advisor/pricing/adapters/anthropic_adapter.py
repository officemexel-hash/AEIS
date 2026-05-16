"""Anthropic pricing adapter."""

from __future__ import annotations

from decimal import Decimal

from sylion.aeis.advisor.pricing.adapters.base import FetchedPricing, ProviderPricingAdapter

ANTHROPIC_PROFILE = {
    "claude-opus-4-7": {"input": Decimal("15.00"), "output": Decimal("75.00"), "cache": Decimal("1.50")},
    "claude-sonnet-4-6": {"input": Decimal("3.00"), "output": Decimal("15.00"), "cache": Decimal("0.30")},
    "claude-haiku-4-5": {"input": Decimal("0.80"), "output": Decimal("4.00"), "cache": Decimal("0.08")},
}


class AnthropicAdapter(ProviderPricingAdapter):
    """Profile-backed Anthropic adapter."""

    provider_id = "anthropic"
    is_local = False

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    def is_available(self) -> bool:
        return self._api_key is not None

    def fetch_live_pricing(self, model_id: str) -> FetchedPricing | None:
        pricing = ANTHROPIC_PROFILE.get(model_id)
        if not pricing:
            return None
        return FetchedPricing(
            model_id=model_id,
            input_tokens_usd_per_million=pricing["input"],
            output_tokens_usd_per_million=pricing["output"],
            cache_hit_tokens_usd_per_million=pricing["cache"],
            source_url="https://www.anthropic.com/pricing",
            raw_response={"profile_used": True, "as_of": "2026-04-25"},
        )

    def list_models(self) -> list[dict[str, object]]:
        return [
            {
                "model_id": "claude-opus-4-7",
                "display_name": "Claude Opus 4.7",
                "context_window": 200000,
                "capabilities": ["code", "long_context", "vision", "tool_use"],
                "is_default_judge": True,
            },
            {
                "model_id": "claude-sonnet-4-6",
                "display_name": "Claude Sonnet 4.6",
                "context_window": 200000,
                "capabilities": ["code", "long_context", "tool_use"],
                "is_default_judge": True,
            },
            {
                "model_id": "claude-haiku-4-5",
                "display_name": "Claude Haiku 4.5",
                "context_window": 100000,
                "capabilities": ["code", "tool_use"],
                "is_default_judge": True,
            },
        ]
