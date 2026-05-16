"""SYLION W11 Adapter Bus — Provider abstraction (PDF §8.1).

Plug-and-play directory of pluggable LLM providers. Each provider exposes a
narrow contract (chat / validate_key / enrich) plus capability-tag metadata
shared across W7 (Skills/Role Catalog), W11 (Adapter Bus routing) and W13
(Task-to-Role Suggester).

This module hosts:
  - :class:`BaseProvider` — abstract base for all new providers.
  - :class:`ProviderInfo`  — lightweight discovery descriptor.
  - capability tag re-exports from :mod:`sylion.providers.capabilities`.

Existing providers in :mod:`sylion.api.ai_providers_routes` (Anthropic,
OpenAI, Perplexity, Google, Z.AI, OpenRouter, Moonshot, DeepSeek, xAI,
Mistral, Groq, Cohere, Fireworks, Together, Ollama) remain untouched —
the new abstraction is opt-in for the local providers added in PDF §8.1
point 6 (LM Studio, vLLM, llama.cpp).

Constraints (PDF §8.1):
  - Imports of provider HTTP clients must stay lazy so they do not block
    server startup when a backend is offline.
  - API keys MUST NOT be logged. Only ``_mask`` previews allowed.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderInfo:
    """Discovery descriptor returned by :meth:`BaseProvider.info`.

    Used by the W11 routing layer to pick a provider based on capability
    tags without instantiating its full HTTP client.
    """

    provider_id: str
    display_name: str
    capability_tags: frozenset[str]
    default_model: str
    supported_models: tuple[str, ...] = ()
    base_url: str | None = None
    locality: str = "cloud"  # "cloud" | "local"

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "capability_tags": sorted(self.capability_tags),
            "default_model": self.default_model,
            "supported_models": list(self.supported_models),
            "base_url": self.base_url,
            "locality": self.locality,
        }


class BaseProvider(abc.ABC):
    """Abstract base for SYLION LLM providers (W11 §8.1.1).

    Subclasses must declare :attr:`provider_id`, :attr:`display_name`,
    :attr:`default_model`, :attr:`supported_models` and override
    :meth:`_capability_tags` plus the three async methods
    :meth:`chat`, :meth:`validate_key`, :meth:`enrich`.

    The abstraction is intentionally narrow — it does not replace the
    monolithic dispatch in ``sylion.api.ai_providers_routes`` (existing
    providers stay as-is). New local providers (LM Studio, vLLM,
    llama.cpp) use this base for testability and capability tagging.
    """

    provider_id: str = ""
    display_name: str = ""
    default_model: str = ""
    supported_models: tuple[str, ...] = ()
    base_url: str | None = None
    locality: str = "cloud"

    # ----- Class-level introspection ------------------------------------

    @property
    def capability_tags(self) -> frozenset[str]:
        """Return tags from :mod:`sylion.providers.capabilities`."""
        return self._capability_tags()

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            capability_tags=self.capability_tags,
            default_model=self.default_model,
            supported_models=tuple(self.supported_models),
            base_url=self.base_url,
            locality=self.locality,
        )

    # ----- Hooks subclasses must implement ------------------------------

    @abc.abstractmethod
    def _capability_tags(self) -> frozenset[str]:
        """Return the capability tags this provider/runtime supports."""

    @abc.abstractmethod
    async def chat(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run a single-turn chat completion. Returns provider-shaped dict
        with at minimum ``{"text": str, "prompt_tokens": int,
        "completion_tokens": int}``.
        """

    @abc.abstractmethod
    async def validate_key(self, key: str | None = None) -> dict[str, Any]:
        """Verify connectivity / authentication.

        Returns a probe descriptor:
            ``{"ok": bool, "models_count": int, "error": str | None}``

        Local providers ignore ``key`` (no auth needed); cloud providers
        treat empty/missing ``key`` as a 4xx-equivalent failure.
        """

    @abc.abstractmethod
    async def enrich(self, key: str | None = None) -> dict[str, Any]:
        """Return ``{plan, models_count, rate_limits, ...}`` metadata.

        For local providers ``plan`` is ``"local"`` and ``rate_limits``
        is empty.
        """


__all__ = [
    "BaseProvider",
    "ProviderInfo",
]
