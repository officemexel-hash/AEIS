"""z.ai / GLM pricing adapter scaffold."""

from __future__ import annotations

from sylion.aeis.advisor.pricing.adapters.base import FetchedPricing, ProviderPricingAdapter


class ZaiAdapter(ProviderPricingAdapter):
    """Scaffold adapter for z.ai / GLM."""

    provider_id = "zai"
    is_local = False

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    def is_available(self) -> bool:
        return self._api_key is not None

    def fetch_live_pricing(self, model_id: str) -> FetchedPricing | None:
        _ = model_id
        return None

    def list_models(self) -> list[dict[str, object]]:
        return []
