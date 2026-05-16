"""OpenAI pricing adapter."""

from __future__ import annotations

from decimal import Decimal

from sylion.aeis.advisor.pricing.adapters.base import FetchedPricing, ProviderPricingAdapter

OPENAI_PROFILE = {
    "gpt-5": {"input": Decimal("10.00"), "output": Decimal("30.00"), "cache": Decimal("1.00")},
    "gpt-5-mini": {"input": Decimal("0.50"), "output": Decimal("2.00"), "cache": Decimal("0.05")},
    "gpt-5-nano": {"input": Decimal("0.10"), "output": Decimal("0.40"), "cache": Decimal("0.01")},
}


class OpenAIAdapter(ProviderPricingAdapter):
    """Profile-backed OpenAI adapter."""

    provider_id = "openai"
    is_local = False

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    def is_available(self) -> bool:
        return self._api_key is not None

    def fetch_live_pricing(self, model_id: str) -> FetchedPricing | None:
        pricing = OPENAI_PROFILE.get(model_id)
        if not pricing:
            return None
        return FetchedPricing(
            model_id=model_id,
            input_tokens_usd_per_million=pricing["input"],
            output_tokens_usd_per_million=pricing["output"],
            cache_hit_tokens_usd_per_million=pricing["cache"],
            source_url="https://openai.com/api/pricing",
            raw_response={"profile_used": True, "as_of": "2026-04-25"},
        )

    def list_models(self) -> list[dict[str, object]]:
        return [
            {
                "model_id": "gpt-5",
                "display_name": "GPT-5",
                "context_window": 256000,
                "capabilities": ["code", "long_context", "tool_use", "vision"],
                "is_default_judge": True,
            },
            {
                "model_id": "gpt-5-mini",
                "display_name": "GPT-5 Mini",
                "context_window": 128000,
                "capabilities": ["code", "tool_use"],
                "is_default_judge": False,
            },
            {
                "model_id": "gpt-5-nano",
                "display_name": "GPT-5 Nano",
                "context_window": 64000,
                "capabilities": ["code"],
                "is_default_judge": False,
            },
        ]
