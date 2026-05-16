"""llama.cpp provider — quantised CPU local OpenAI-compatible runtime (PDF §8.1.6).

Wraps the OpenAI-compatible HTTP server shipped with ``llama.cpp``
(``./server`` / ``llama-server``). Default base URL is
``http://localhost:8080``. The runtime targets quantised GGUF models
running on CPU (or partial GPU offload) — capability tags reflect that.
"""

from __future__ import annotations

import os
from typing import Any

from sylion.providers import BaseProvider
from sylion.providers.capabilities import (
    CAP_STREAMING,
    LOCALITY_CPU,
    LOCALITY_LOCAL,
    LOCALITY_QUANTIZED,
    MODALITY_CODE,
    MODALITY_TEXT,
    TIER_CHEAP,
)


DEFAULT_BASE_URL = os.environ.get("LLAMACPP_BASE_URL", "http://localhost:8080")
DEFAULT_TIMEOUT_S = 60.0
PROBE_TIMEOUT_S = 3.0


class LlamaCppProvider(BaseProvider):
    """``llama.cpp``/``llama-server`` local OpenAI-compatible runtime.

    Discovery:
        ``GET {base_url}/v1/models``  → list of loaded GGUF models. The
        ``/health`` endpoint is also probed as a fallback for older
        builds that did not implement ``/v1/models``.

    Chat:
        ``POST {base_url}/v1/chat/completions`` — same envelope as OpenAI.
    """

    provider_id = "llamacpp"
    display_name = "llama.cpp (local)"
    default_model = "ggml-org/Phi-3-mini-4k-instruct-GGUF"
    supported_models: tuple[str, ...] = (
        "ggml-org/Phi-3-mini-4k-instruct-GGUF",
        "TheBloke/Llama-2-7B-Chat-GGUF",
    )
    locality = "local"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

    # --- BaseProvider ---------------------------------------------------

    def _capability_tags(self) -> frozenset[str]:
        return frozenset({
            MODALITY_TEXT, MODALITY_CODE, CAP_STREAMING,
            TIER_CHEAP,
            LOCALITY_LOCAL, LOCALITY_CPU, LOCALITY_QUANTIZED,
        })

    async def chat(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Forward to ``/v1/chat/completions`` (OpenAI-compatible)."""
        import httpx  # lazy

        max_tokens = int(kwargs.pop("max_tokens", 256))
        target_model = model or self.default_model
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
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
        """Ping ``/v1/models``; llama.cpp does not require auth.

        Falls back to ``/health`` if the server build does not implement
        ``/v1/models`` (older revisions).
        """
        del key
        import httpx

        try:
            async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:
                r = await client.get(f"{self.base_url}/v1/models")
                if r.status_code == 404:
                    # Older llama.cpp builds: /health is the discovery probe.
                    health = await client.get(f"{self.base_url}/health")
                    if health.status_code < 400:
                        return {"ok": True, "models_count": 1, "error": None}
                    return {
                        "ok": False,
                        "models_count": 0,
                        "error": f"HTTP {health.status_code}",
                    }
                if r.status_code >= 400:
                    return {
                        "ok": False,
                        "models_count": 0,
                        "error": f"HTTP {r.status_code}",
                    }
                data = r.json() or {}
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "models_count": 0,
                "error": f"unreachable: {type(exc).__name__}",
            }
        models = data.get("data") or []
        return {"ok": True, "models_count": len(models), "error": None}

    async def enrich(self, key: str | None = None) -> dict[str, Any]:
        del key
        import httpx

        try:
            async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:
                r = await client.get(f"{self.base_url}/v1/models")
                if r.status_code == 404:
                    health = await client.get(f"{self.base_url}/health")
                    if health.status_code < 400:
                        return {
                            "plan": "local",
                            "models_count": 1,
                            "rate_limits": {},
                            "models": ["<unnamed-loaded-gguf>"],
                            "fallback": "health-probe",
                        }
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


_PROVIDER: LlamaCppProvider | None = None


def get_provider(base_url: str | None = None) -> LlamaCppProvider:
    """Return a (possibly cached) :class:`LlamaCppProvider`."""
    global _PROVIDER
    if _PROVIDER is None or (base_url and _PROVIDER.base_url != base_url.rstrip("/")):
        _PROVIDER = LlamaCppProvider(base_url=base_url)
    return _PROVIDER
