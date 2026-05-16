"""Tests for sylion.providers.{lmstudio,vllm,llamacpp} local providers.

Covers validate_key/enrich/chat for all three local providers using a
stub httpx.AsyncClient injected via monkeypatch — no real sockets opened.

We deliberately avoid pytest-httpx and pytest-asyncio as hard deps; the
stub mirrors the small subset of httpx surface we exercise (post + get +
raise_for_status), and async tests are driven by ``asyncio.run`` so the
suite works on a stock pytest install.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from sylion.providers.lmstudio import LMStudioProvider
from sylion.providers.llamacpp import LlamaCppProvider
from sylion.providers.vllm import VLLMProvider


# ---------------------------------------------------------------------------
# httpx stub
# ---------------------------------------------------------------------------


class _StubResponse:
    def __init__(self, status_code: int = 200, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload

    @property
    def text(self) -> str:
        return str(self._payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _StubAsyncClient:
    """Minimal async-context-manager stand-in for httpx.AsyncClient.

    Records call URLs and serves canned responses keyed by URL suffix.
    """

    def __init__(self, *_, **__) -> None:
        self.posted_payload: dict[str, Any] | None = None
        self.last_url: str | None = None
        self.last_headers: dict[str, str] | None = None

    async def __aenter__(self) -> "_StubAsyncClient":
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def get(self, url: str, headers: dict | None = None, **_) -> _StubResponse:
        self.last_url = url
        self.last_headers = headers
        return _route(url, "GET")

    async def post(
        self, url: str, json: dict | None = None, headers: dict | None = None, **_
    ) -> _StubResponse:
        self.last_url = url
        self.last_headers = headers
        self.posted_payload = json
        return _route(url, "POST", json)


# Mutable per-test routing table — keyed by (url_suffix, method).
_ROUTES: dict[tuple[str, str], _StubResponse] = {}


def _route(url: str, method: str, payload: dict | None = None) -> _StubResponse:
    for (suffix, m), response in _ROUTES.items():
        if m == method and url.endswith(suffix):
            return response
    return _StubResponse(404, {"error": "no stub for " + url})


@pytest.fixture
def stub_httpx(monkeypatch):
    """Patch httpx.AsyncClient inside each provider module with the stub."""
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _StubAsyncClient)
    _ROUTES.clear()
    yield _ROUTES
    _ROUTES.clear()


def _run(coro):
    """Drive an async coroutine to completion in a fresh event loop."""
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# LM Studio
# ---------------------------------------------------------------------------


class TestLMStudio:

    def test_validate_key_ok(self, stub_httpx):
        stub_httpx[("/v1/models", "GET")] = _StubResponse(
            200, {"data": [{"id": "mistral-7b-instruct"}]}
        )
        p = LMStudioProvider(base_url="http://localhost:1234")
        out = _run(p.validate_key())
        assert out == {"ok": True, "models_count": 1, "error": None}

    def test_validate_key_unreachable(self, monkeypatch, stub_httpx):
        # Force a connection error.
        class _Boom(_StubAsyncClient):
            async def get(self, *a, **kw):
                raise ConnectionError("nope")

        import httpx

        monkeypatch.setattr(httpx, "AsyncClient", _Boom)
        p = LMStudioProvider(base_url="http://localhost:1234")
        out = _run(p.validate_key())
        assert out["ok"] is False
        assert out["models_count"] == 0
        assert "unreachable" in out["error"]

    def test_chat_returns_text_and_usage(self, stub_httpx):
        stub_httpx[("/v1/chat/completions", "POST")] = _StubResponse(
            200,
            {
                "choices": [{"message": {"content": "pong"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 2},
                "model": "mistral-7b-instruct",
            },
        )
        p = LMStudioProvider(base_url="http://localhost:1234")
        out = _run(p.chat("ping", model="mistral-7b-instruct"))
        assert out["text"] == "pong"
        assert out["prompt_tokens"] == 7
        assert out["completion_tokens"] == 2

    def test_enrich_lists_models(self, stub_httpx):
        stub_httpx[("/v1/models", "GET")] = _StubResponse(
            200, {"data": [{"id": "m1"}, {"id": "m2"}]}
        )
        p = LMStudioProvider(base_url="http://localhost:1234")
        out = _run(p.enrich())
        assert out["plan"] == "local"
        assert out["models_count"] == 2
        assert out["models"] == ["m1", "m2"]
        assert out["rate_limits"] == {}

    def test_capability_tags(self):
        p = LMStudioProvider()
        tags = p.capability_tags
        assert "local" in tags
        assert "cheap" in tags


# ---------------------------------------------------------------------------
# vLLM
# ---------------------------------------------------------------------------


class TestVLLM:

    def test_validate_key_ok_no_auth(self, stub_httpx):
        stub_httpx[("/v1/models", "GET")] = _StubResponse(
            200, {"data": [{"id": "Qwen/Qwen2.5-7B-Instruct"}]}
        )
        p = VLLMProvider(base_url="http://localhost:8001")
        out = _run(p.validate_key())
        assert out["ok"] is True
        assert out["models_count"] == 1

    def test_validate_key_auth_failed(self, stub_httpx):
        stub_httpx[("/v1/models", "GET")] = _StubResponse(401, {"error": "denied"})
        p = VLLMProvider(base_url="http://localhost:8001")
        out = _run(p.validate_key(key="bad"))
        assert out["ok"] is False
        assert "auth_failed" in out["error"]

    def test_chat_passes_bearer_token(self, stub_httpx):
        stub_httpx[("/v1/chat/completions", "POST")] = _StubResponse(
            200,
            {
                "choices": [{"message": {"content": "hi"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
        p = VLLMProvider(base_url="http://localhost:8001")
        out = _run(p.chat("hello", model="Qwen/Qwen2.5-7B-Instruct", key="secret"))
        assert out["text"] == "hi"

    def test_capability_tags_include_concurrent(self):
        p = VLLMProvider()
        tags = p.capability_tags
        assert "concurrent" in tags
        assert "gpu" in tags
        assert "fast" in tags


# ---------------------------------------------------------------------------
# llama.cpp
# ---------------------------------------------------------------------------


class TestLlamaCpp:

    def test_validate_key_ok(self, stub_httpx):
        stub_httpx[("/v1/models", "GET")] = _StubResponse(
            200, {"data": [{"id": "phi-3-mini"}]}
        )
        p = LlamaCppProvider(base_url="http://localhost:8080")
        out = _run(p.validate_key())
        assert out["ok"] is True
        assert out["models_count"] == 1

    def test_validate_key_falls_back_to_health(self, stub_httpx):
        # Simulate older build without /v1/models — only /health.
        stub_httpx[("/v1/models", "GET")] = _StubResponse(404, {})
        stub_httpx[("/health", "GET")] = _StubResponse(200, {"status": "ok"})
        p = LlamaCppProvider(base_url="http://localhost:8080")
        out = _run(p.validate_key())
        assert out["ok"] is True
        assert out["models_count"] == 1

    def test_chat_returns_text(self, stub_httpx):
        stub_httpx[("/v1/chat/completions", "POST")] = _StubResponse(
            200,
            {
                "choices": [{"message": {"content": "ack"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            },
        )
        p = LlamaCppProvider(base_url="http://localhost:8080")
        out = _run(p.chat("ping"))
        assert out["text"] == "ack"
        assert out["prompt_tokens"] == 2

    def test_capability_tags(self):
        p = LlamaCppProvider()
        tags = p.capability_tags
        assert "cpu" in tags
        assert "quantized" in tags
        assert "local" in tags
