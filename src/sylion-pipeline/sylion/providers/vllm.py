"""vLLM provider — high-throughput local OpenAI-compatible runtime (PDF §8.1.6).

vLLM exposes an OpenAI-compatible HTTP server (``vllm serve ...``).
Default base URL is ``http://localhost:8001`` (we deliberately differ
from LM Studio's 1234 and llama.cpp's 8080 so all three can coexist on
one host). vLLM specialises in batched, GPU-accelerated, high-concurrency
serving — capability tags reflect that.
"""

from __future__ import annotations

import os
from typing import Any

from sylion.providers import BaseProvider
from sylion.providers.capabilities import (
    CAP_LONG_CONTEXT,
    CAP_STREAMING,
    LOCALITY_CONCURRENT,
    LOCALITY_GPU,
    LOCALITY_LOCAL,
    MODALITY_CODE,
    MODALITY_TEXT,
    SPEED_FAST,
    TIER_CHEAP,
)


DEFAULT_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8001")
DEFAULT_TIMEOUT_S = 60.0  # vLLM batch warm-up can be slower than LM Studio
PROBE_TIMEOUT_S = 3.0


class VLLMProvider(BaseProvider):
    """vLLM local OpenAI-compatible runtime.

    Discovery:
        ``GET {base_url}/v1/models``  → list of served models. Optional
        bearer token may be provided via ``key`` (vLLM ``--api-key``).

    Chat:
        ``POST {base_url}/v1/chat/completions`` — same envelope as OpenAI.
    """

    provider_id = "vllm"
    display_name = "vLLM (local)"
    default_model = "Qwen/Qwen2.5-72B-Instruct"
    supported_models: tuple[str, ...] = (
        "Qwen/Qwen2.5-72B-Instruct",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
    )
    locality = "local"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

    # --- BaseProvider ---------------------------------------------------

    def _capability_tags(self) -> frozenset[str]:
        return frozenset({
            MODALITY_TEXT, MODALITY_CODE,
            CAP_STREAMING, CAP_LONG_CONTEXT,
            TIER_CHEAP, SPEED_FAST,
            LOCALITY_LOCAL, LOCALITY_GPU, LOCALITY_CONCURRENT,
        })

    @staticmethod
    def _auth_headers(key: str | None) -> dict[str, str]:
        # Optional — vLLM only enforces auth when started with --api-key.
        if key and key.strip():
            return {"Authorization": f"Bearer {key.strip()}"}
        return {}

    async def chat(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Forward to ``/v1/chat/completions`` (OpenAI-compatible)."""
        import httpx  # lazy

        max_tokens = int(kwargs.pop("max_tokens", 256))
        key = kwargs.pop("key", None)
        target_model = model or self.default_model
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        for opt in ("temperature", "top_p", "stop", "stream", "n"):
            if opt in kwargs:
                payload[opt] = kwargs[opt]

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_S) as client:
            r = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=self._auth_headers(key),
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
        """Ping ``/v1/models``; vLLM auth is optional."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:
                r = await client.get(
                    f"{self.base_url}/v1/models",
                    headers=self._auth_headers(key),
                )
                if r.status_code == 401 or r.status_code == 403:
                    return {
                        "ok": False,
                        "models_count": 0,
                        "error": f"auth_failed ({r.status_code})",
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
        import httpx

        try:
            async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:
                r = await client.get(
                    f"{self.base_url}/v1/models",
                    headers=self._auth_headers(key),
                )
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


_PROVIDER: VLLMProvider | None = None


def get_provider(base_url: str | None = None) -> VLLMProvider:
    """Return a (possibly cached) :class:`VLLMProvider`."""
    global _PROVIDER
    if _PROVIDER is None or (base_url and _PROVIDER.base_url != base_url.rstrip("/")):
        _PROVIDER = VLLMProvider(base_url=base_url)
    return _PROVIDER
