"""Google pricing adapter."""

from __future__ import annotations

from decimal import Decimal

from sylion.aeis.advisor.pricing.adapters.base import FetchedPricing, ProviderPricingAdapter

GOOGLE_PROFILE = {
    "gemini-2.5-pro": {"input": Decimal("3.50"), "output": Decimal("10.50"), "cache": Decimal("0.35")},
    "gemini-2.5-flash": {"input": Decimal("0.30"), "output": Decimal("1.20"), "cache": Decimal("0.03")},
}


class GoogleAdapter(ProviderPricingAdapter):
    """Profile-backed Google adapter."""

    provider_id = "google"
    is_local = False

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    def is_available(self) -> bool:
        return self._api_key is not None

    def fetch_live_pricing(self, model_id: str) -> FetchedPricing | None:
        pricing = GOOGLE_PROFILE.get(model_id)
        if not pricing:
            return None
        return FetchedPricing(
            model_id=model_id,
            input_tokens_usd_per_million=pricing["input"],
            output_tokens_usd_per_million=pricing["output"],
            cache_hit_tokens_usd_per_million=pricing["cache"],
            source_url="https://ai.google.dev/pricing",
            raw_response={"profile_used": True, "as_of": "2026-04-25"},
        )

    def list_models(self) -> list[dict[str, object]]:
        return [
            {
                "model_id": "gemini-2.5-pro",
                "display_name": "Gemini 2.5 Pro",
                "context_window": 2000000,
                "capabilities": ["code", "long_context", "vision", "tool_use"],
                "is_default_judge": True,
            },
            {
                "model_id": "gemini-2.5-flash",
                "display_name": "Gemini 2.5 Flash",
                "context_window": 1000000,
                "capabilities": ["long_context", "vision"],
                "is_default_judge": True,
            },
        ]
