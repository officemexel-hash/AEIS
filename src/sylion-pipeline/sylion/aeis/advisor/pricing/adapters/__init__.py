"""Pricing adapter registry."""

from __future__ import annotations

from threading import Lock

from sylion.aeis.advisor.pricing.adapters.anthropic_adapter import AnthropicAdapter
from sylion.aeis.advisor.pricing.adapters.base import FetchedPricing, ProviderPricingAdapter
from sylion.aeis.advisor.pricing.adapters.google_adapter import GoogleAdapter
from sylion.aeis.advisor.pricing.adapters.manual_table_adapter import ManualTableAdapter
from sylion.aeis.advisor.pricing.adapters.moonshot_adapter import MoonshotAdapter
from sylion.aeis.advisor.pricing.adapters.ollama_adapter import OllamaAdapter
from sylion.aeis.advisor.pricing.adapters.openai_adapter import OpenAIAdapter
from sylion.aeis.advisor.pricing.adapters.xai_adapter import XaiAdapter
from sylion.aeis.advisor.pricing.adapters.zai_adapter import ZaiAdapter

_ADAPTERS: dict[str, ProviderPricingAdapter] = {}
_LOCK = Lock()


def register_adapter(provider_id: str, adapter: ProviderPricingAdapter) -> None:
    """Register or replace an adapter."""
    with _LOCK:
        _ADAPTERS[provider_id] = adapter


def get_adapter(provider_id: str) -> ProviderPricingAdapter | None:
    """Return the adapter for a provider."""
    return _ADAPTERS.get(provider_id)


def list_registered_adapters() -> dict[str, ProviderPricingAdapter]:
    """Return the adapter registry snapshot."""
    return dict(_ADAPTERS)


def initialize_default_adapters(api_keys: dict[str, str | None] | None = None) -> None:
    """Ensure the default adapter set is registered."""
    api_keys = api_keys or {}
    defaults = {
        "anthropic": AnthropicAdapter(api_keys.get("anthropic")),
        "openai": OpenAIAdapter(api_keys.get("openai")),
        "google": GoogleAdapter(api_keys.get("google")),
        "ollama_local": OllamaAdapter(),
        "moonshot": MoonshotAdapter(api_keys.get("moonshot")),
        "zai": ZaiAdapter(api_keys.get("zai")),
        "xai": XaiAdapter(api_keys.get("xai")),
    }
    with _LOCK:
        for provider_id, adapter in defaults.items():
            _ADAPTERS.setdefault(provider_id, adapter)


__all__ = [
    "FetchedPricing",
    "ManualTableAdapter",
    "ProviderPricingAdapter",
    "get_adapter",
    "initialize_default_adapters",
    "list_registered_adapters",
    "register_adapter",
]
