"""LM Studio provider — OpenAI-compatible local runtime (PDF §8.1.6).

LM Studio runs an OpenAI-compatible server, by default on
``http://localhost:1234``. No auth required for the local socket; the
``key`` argument is accepted only to preserve the :class:`BaseProvider`
contract. Capability tags reflect a CPU-or-GPU local runtime that is
typically used for quantised consumer models.
"""

from __future__ import annotations

import os
from typing import Any

from sylion.providers import BaseProvider
from sylion.providers.capabilities import (
    CAP_STREAMING,
    LOCALITY_CPU,
    LOCALITY_GPU,
    LOCALITY_LOCAL,
    LOCALITY_QUANTIZED,
    MODALITY_CODE,
    MODALITY_TEXT,
    TIER_CHEAP,
)


DEFAULT_BASE_URL = os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234")
DEFAULT_TIMEOUT_S = 30.0
PROBE_TIMEOUT_S = 3.0


class LMStudioProvider(BaseProvider):
    """LM Studio local OpenAI-compatible runtime.

    Discovery:
        ``GET {base_url}/v1/models``  → list of installed models. No auth.

    Chat:
        ``POST {base_url}/v1/chat/completions`` — same envelope as OpenAI.
    """

    provider_id = "lmstudio"
    display_name = "LM Studio (local)"
    default_model = "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF"
    supported_models: tuple[str, ...] = (
        "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
    )
    locality = "local"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

    # --- BaseProvider ---------------------------------------------------

    def _capability_tags(self) -> frozenset[str]:
        return frozenset({
            MODALITY_TEXT, MODALITY_CODE, CAP_STREAMING,
            TIER_CHEAP,
            LOCALITY_LOCAL, LOCALITY_CPU, LOCALITY_GPU, LOCALITY_QUANTIZED,
        })

    async def chat(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Forward to ``/v1/chat/completions`` (OpenAI-compatible)."""
        import httpx  # lazy import — keeps server startup unaffected when LM Studio offline

        max_tokens = int(kwargs.pop("max_tokens", 256))
        target_model = model or self.default_model
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        # Pass through optional OpenAI fields when caller supplied them.
        for opt in ("temperature", "top_p", "stop", "stream"):
            if opt in kwargs:
                payload[opt] = kwargs[opt]

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_S) as client:
            r = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            )
            r.raise_for_status()
            data = r.json()

        choices = data.get("choices") or []
        text = (
            choices[0].get("message", {}).get("content", "")
            if choices
            else ""
        )
        usage = data.get("usage") or {}
        return {
            "text": text or "",
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "model_used": data.get("model", target_model),
        }

    async def validate_key(self, key: str | None = None) -> dict[str, Any]:
        """Ping ``/v1/models``; LM Studio needs no auth.

        Returns ``{ok, models_count, error}``. The ``key`` argument is
        ignored — accepted for :class:`BaseProvider` compatibility.
        """
        del key  # explicitly unused; never log it either way
        import httpx

        try:
            async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:
                r = await client.get(f"{self.base_url}/v1/models")
                if r.status_code >= 400:
                    return {
                        "ok": False,
                        "models_count": 0,
                        "error": f"HTTP {r.status_code}",
                    }
                data = r.json() or {}
        except Exception as exc:  # noqa: BLE001 — surface net/proto errors uniformly
            return {
                "ok": False,
                "models_count": 0,
                "error": f"unreachable: {type(exc).__name__}",
            }
        models = data.get("data") or []
        return {"ok": True, "models_count": len(models), "error": None}

    async def enrich(self, key: str | None = None) -> dict[str, Any]:
        """Return ``{plan, models_count, rate_limits, models}``.

        For local runtimes ``plan`` is fixed at ``"local"`` and
        ``rate_limits`` is empty.
        """
        del key
        import httpx

        try:
            async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:
                r = await client.get(f"{self.base_url}/v1/models")
                if r.status_code >= 400:
                    return {
                        "plan": "local",
                        "models_count": 0,
                        "rate_limits": {},
                        "models": [],
                        "error": f"HTTP {r.status_code}",
                    }
                data = r.json() or {}
        except Exception as exc:  # noqa: BLE001
            return {
                "plan": "local",
                "models_count": 0,
                "rate_limits": {},
                "models": [],
                "error": f"unreachable: {type(exc).__name__}",
            }
        models = [m.get("id", "") for m in (data.get("data") or []) if m.get("id")]
        return {
            "plan": "local",
            "models_count": len(models),
            "rate_limits": {},
            "models": models,
        }


# Module-level singleton for cheap reuse from route handlers.
_PROVIDER: LMStudioProvider | None = None


def get_provider(base_url: str | None = None) -> LMStudioProvider:
    """Return a (possibly cached) :class:`LMStudioProvider`."""
    global _PROVIDER
    if _PROVIDER is None or (base_url and _PROVIDER.base_url != base_url.rstrip("/")):
        _PROVIDER = LMStudioProvider(base_url=base_url)
    return _PROVIDER
