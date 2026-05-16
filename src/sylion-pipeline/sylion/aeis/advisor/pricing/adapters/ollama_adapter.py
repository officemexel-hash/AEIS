"""Ollama pricing adapter."""

from __future__ import annotations

import os
from decimal import Decimal

from sylion.aeis.advisor.pricing.adapters.base import FetchedPricing, ProviderPricingAdapter

OLLAMA_DEFAULT_MODELS = [
    {
        "model_id": "qwen2.5:72b-instruct",
        "display_name": "Qwen2.5 72B Instruct",
        "context_window": 32768,
        "capabilities": ["code", "tool_use"],
        "is_default_judge": True,
        "is_default_local": True,
    },
    {
        "model_id": "qwen2.5:7b-instruct",
        "display_name": "Qwen2.5 7B Instruct",
        "context_window": 32768,
        "capabilities": ["code"],
        "is_default_judge": True,
        "is_default_local": False,
    },
    {
        "model_id": "llama3.3:70b",
        "display_name": "Llama 3.3 70B",
        "context_window": 128000,
        "capabilities": ["code", "long_context"],
        "is_default_judge": False,
        "is_default_local": False,
    },
]


class OllamaAdapter(ProviderPricingAdapter):
    """Local Ollama adapter with zero API price."""

    provider_id = "ollama_local"
    is_local = True

    def __init__(self, base_url: str | None = None):
        self._base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    def is_available(self) -> bool:
        return bool(self._base_url)

    def fetch_live_pricing(self, model_id: str) -> FetchedPricing | None:
        model_ids = {item["model_id"] for item in OLLAMA_DEFAULT_MODELS}
        if model_id not in model_ids:
            return None
        zero = Decimal("0")
        return FetchedPricing(
            model_id=model_id,
            input_tokens_usd_per_million=zero,
            output_tokens_usd_per_million=zero,
            cache_hit_tokens_usd_per_million=zero,
            source_url=self._base_url,
            raw_response={"local_compute": True},
        )

    def list_models(self) -> list[dict[str, object]]:
        return list(OLLAMA_DEFAULT_MODELS)
