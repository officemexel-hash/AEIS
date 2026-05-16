"""Base classes for pricing adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class FetchedPricing:
    """Result from a provider pricing fetch."""

    model_id: str
    input_tokens_usd_per_million: Decimal | None
    output_tokens_usd_per_million: Decimal | None
    cache_hit_tokens_usd_per_million: Decimal | None
    source_url: str | None
    raw_response: dict[str, Any] | None


class ProviderPricingAdapter(ABC):
    """Abstract base class for provider pricing adapters."""

    provider_id: str = ""
    is_local: bool = False

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the adapter can be used in the current environment."""

    @abstractmethod
    def fetch_live_pricing(self, model_id: str) -> FetchedPricing | None:
        """Return pricing for a model or None when not available."""

    @abstractmethod
    def list_models(self) -> list[dict[str, Any]]:
        """Return known models and metadata for the provider."""
