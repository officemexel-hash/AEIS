"""Tests for sylion.api.rate_limit (Phase 3 W2.3).

Token-bucket / fixed-window rate-limit middleware. We mount it on a
disposable Starlette app with a stub auth middleware that lets each test
inject ``request.state.user`` directly — that way we don't depend on the
full SYLION app, which would also wire in the real auth provider, audit
chain, etc.

We `reset_cache()` between tests so counters don't bleed across cases.
"""
from __future__ import annotations

import os

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from sylion.api.rate_limit import RateLimitMiddleware
from sylion.infra.cache import reset_cache


# ---------------------------------------------------------------------------
# Stub auth middleware — injects request.state.user from a header so each
# test can flip identity without spinning up real auth.
# ---------------------------------------------------------------------------

class _StubAuth(BaseHTTPMiddleware):
    """Sets request.state.user from X-Test-User. No header = anonymous."""
    async def dispatch(self, request, call_next):
        user = request.headers.get("x-test-user")
        request.state.user = user if user else None
        return await call_next(request)


async def _ok(request):
    return JSONResponse({"ok": True, "path": request.url.path})


def _build_app() -> Starlette:
    routes = [
        Route("/health", _ok),
        Route("/api/v1/auth/login", _ok, methods=["GET", "POST"]),
        Route("/api/v1/projects", _ok),
        Route("/api/v1/council/decide", _ok, methods=["GET", "POST"]),
        Route("/api/v1/skills/x/execute", _ok, methods=["GET", "POST"]),
        Route("/api/v1/funding/scan", _ok),
    ]
    # Starlette(middleware=[...]) makes the FIRST-listed item the outermost
    # (whereas FastAPI's add_middleware() makes the LAST-added the outermost).
    # We need StubAuth outermost so request.state.user is set before the
    # limiter classifies the tier — hence StubAuth listed first here.
    middleware = [
        Middleware(_StubAuth),
        Middleware(RateLimitMiddleware),
    ]
    return Starlette(routes=routes, middleware=middleware)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    # Each test gets a fresh in-memory cache backend.
    monkeypatch.delenv("SYLION_CACHE_URL", raising=False)
    monkeypatch.delenv("SYLION_RATE_LIMIT_DISABLED", raising=False)
    monkeypatch.delenv("SYLION_TRUST_PROXY", raising=False)
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def client():
    return TestClient(_build_app())


# ---------------------------------------------------------------------------
# Public-path bypass
# ---------------------------------------------------------------------------


class TestPublicPathsBypass:
    def test_health_never_limited(self, client):
        # Way past any tier's budget — must still 200 every time.
        for _ in range(100):
            r = client.get("/health")
            assert r.status_code == 200
        # No rate-limit headers on bypassed paths (sanity: middleware
        # short-circuits before computing a budget).
        assert "x-ratelimit-limit" not in {k.lower() for k in r.headers}

    def test_auth_prefix_never_limited(self, client):
        for _ in range(100):
            r = client.post("/api/v1/auth/login")
            assert r.status_code == 200


# ---------------------------------------------------------------------------
# Anonymous tier — 60/min keyed by IP
# ---------------------------------------------------------------------------


class TestAnonymousTier:
    def test_under_budget_passes(self, client):
        r = client.get("/api/v1/projects")
        assert r.status_code == 200
        assert r.headers["X-RateLimit-Limit"] == "60"
        assert int(r.headers["X-RateLimit-Remaining"]) == 59

    def test_remaining_decrements(self, client):
        client.get("/api/v1/projects")
        r2 = client.get("/api/v1/projects")
        assert int(r2.headers["X-RateLimit-Remaining"]) == 58

    def test_429_after_budget_exhausted(self, client):
        # 60 anon hits should pass, the 61st must 429.
        for i in range(60):
            r = client.get("/api/v1/projects")
            assert r.status_code == 200, f"hit {i} unexpectedly 429"
        r = client.get("/api/v1/projects")
        assert r.status_code == 429
        assert r.headers["Retry-After"]
        assert int(r.headers["Retry-After"]) >= 1
        body = r.json()
        assert body["error"] == "rate_limited"
        assert body["tier"] == "anonymous"
        assert body["limit_per_minute"] == 60


# ---------------------------------------------------------------------------
# Authenticated tier — 600/min keyed by user
# ---------------------------------------------------------------------------


class TestAuthenticatedTier:
    def test_user_gets_higher_budget(self, client):
        r = client.get("/api/v1/projects", headers={"X-Test-User": "alice"})
        assert r.status_code == 200
        assert r.headers["X-RateLimit-Limit"] == "600"

    def test_users_have_separate_buckets(self, client):
        # Alice burns through 5 hits — Bob's first hit must show fresh budget.
        for _ in range(5):
            client.get("/api/v1/projects", headers={"X-Test-User": "alice"})
        r = client.get("/api/v1/projects", headers={"X-Test-User": "bob"})
        assert int(r.headers["X-RateLimit-Remaining"]) == 599


# ---------------------------------------------------------------------------
# Heavy tier — 30/min keyed by user, applies to council/skills/funding
# ---------------------------------------------------------------------------


class TestHeavyTier:
    @pytest.mark.parametrize("path", [
        "/api/v1/council/decide",
        "/api/v1/skills/x/execute",
        "/api/v1/funding/scan",
    ])
    def test_heavy_endpoints_get_30_budget(self, client, path):
        r = client.get(path, headers={"X-Test-User": "alice"})
        assert r.status_code == 200
        assert r.headers["X-RateLimit-Limit"] == "30"

    def test_heavy_429_after_30(self, client):
        for _ in range(30):
            r = client.get("/api/v1/council/decide",
                           headers={"X-Test-User": "alice"})
            assert r.status_code == 200
        r = client.get("/api/v1/council/decide",
                       headers={"X-Test-User": "alice"})
        assert r.status_code == 429
        assert r.json()["tier"] == "heavy"

    def test_heavy_separate_from_general_budget(self, client):
        # Burning the heavy budget must not affect the general /projects budget.
        for _ in range(30):
            client.get("/api/v1/council/decide",
                       headers={"X-Test-User": "alice"})
        r = client.get("/api/v1/projects",
                       headers={"X-Test-User": "alice"})
        assert r.status_code == 200
        # alice's general bucket is fresh.
        assert int(r.headers["X-RateLimit-Remaining"]) == 599


# ---------------------------------------------------------------------------
# OPTIONS (CORS preflight) — bypassed
# ---------------------------------------------------------------------------


class TestOptionsBypass:
    def test_options_never_429s(self, client):
        # Way past the anon budget.
        for _ in range(120):
            r = client.options("/api/v1/projects")
            # Starlette returns 405 for OPTIONS on unhandled routes — what
            # matters is we never see 429.
            assert r.status_code != 429


# ---------------------------------------------------------------------------
# Disable flag
# ---------------------------------------------------------------------------


class TestDisabled:
    def test_disable_flag_skips_limiter(self, monkeypatch):
        monkeypatch.setenv("SYLION_RATE_LIMIT_DISABLED", "1")
        reset_cache()
        c = TestClient(_build_app())
        # 200 hits — anon would normally cap at 60. With limiter disabled
        # the response carries no X-RateLimit-* headers either.
        for _ in range(200):
            r = c.get("/api/v1/projects")
            assert r.status_code == 200
        assert "x-ratelimit-limit" not in {k.lower() for k in r.headers}


# ---------------------------------------------------------------------------
# X-Forwarded-For trust
# ---------------------------------------------------------------------------


class TestProxyTrust:
    def test_xff_ignored_by_default(self, client):
        # Without SYLION_TRUST_PROXY=1, two anon clients claiming different
        # XFF values should still share a bucket (TestClient peer is constant).
        for _ in range(60):
            client.get("/api/v1/projects",
                       headers={"X-Forwarded-For": "203.0.113.1"})
        r = client.get("/api/v1/projects",
                       headers={"X-Forwarded-For": "203.0.113.2"})
        assert r.status_code == 429

    def test_xff_honored_when_trust_set(self, monkeypatch):
        monkeypatch.setenv("SYLION_TRUST_PROXY", "1")
        reset_cache()
        c = TestClient(_build_app())
        # Burn 60 anon hits as 203.0.113.1, then a 61st as a different XFF
        # must still 200 because the buckets are separate.
        for _ in range(60):
            c.get("/api/v1/projects",
                  headers={"X-Forwarded-For": "203.0.113.1"})
        r = c.get("/api/v1/projects",
                  headers={"X-Forwarded-For": "203.0.113.2"})
        assert r.status_code == 200
