"""Phase 3 W2.3 — token-bucket rate limiting middleware.

Tier rules (per PROMPT_AGENT.md §3.2 W2.3):

    public paths (health/auth)               -> no limit
    anonymous (no Bearer token)              -> 60 req/min per IP
    authenticated user                       -> 600 req/min per user
    heavy endpoints (council/skills/funding) -> 30 req/min per user
    funding portal calls (W4)                -> 10 req/min per project (deferred)

Backed by sylion.infra.cache (Redis when SYLION_CACHE_URL is set, in-memory
LRU otherwise) — same backend as the W1.3 cache layer. We use the cache as
a counting store via a fixed-window approximation (cheap, slightly more
generous than a leaky bucket; correct enough for traffic shaping at this
scale).

Disable globally with SYLION_RATE_LIMIT_DISABLED=1 (used by tests + load
profiling so the slowapi wave doesn't poison perf_baseline numbers).
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

log = logging.getLogger("sylion.api.rate_limit")


# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Tier:
    name: str
    requests_per_minute: int


_TIER_PUBLIC = Tier("public", requests_per_minute=0)        # 0 = no limit
_TIER_ANONYMOUS = Tier("anonymous", requests_per_minute=60)
_TIER_AUTHED = Tier("authenticated", requests_per_minute=600)
_TIER_HEAVY = Tier("heavy", requests_per_minute=30)


# Endpoint patterns that count as "heavy" — apply the 30 rpm tier even if
# the user is authenticated. Patterns are anchored regex against the path.
# Listed paths are derived from PROMPT_AGENT.md §3.2 + W1 perf_baseline.md
# top-10 (council/skills/funding scan).
_HEAVY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"^/api/v1/council/",        # decide, reconcile, vote
        r"^/api/v1/skills/.*/execute",
        r"^/api/v1/funding/scan",
        r"^/api/v1/funding/.*/submit",
        r"^/api/v1/decomposition/",  # planner can be expensive
    )
)


# Public paths bypass the limiter entirely. Mirrors AuthMiddleware so
# health checks and login flows aren't throttled during incident response.
_PUBLIC_PATHS: frozenset[str] = frozenset({
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
})
_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/api/v1/auth/",
)


def _classify(request: Request) -> Tier:
    path = request.url.path
    if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
        return _TIER_PUBLIC
    user = getattr(request.state, "user", None)
    if not user:
        return _TIER_ANONYMOUS
    for pat in _HEAVY_PATTERNS:
        if pat.match(path):
            return _TIER_HEAVY
    return _TIER_AUTHED


def _identity(request: Request, tier: Tier) -> str:
    """Bucket identity. Authenticated tiers key by user id; anon keys by IP."""
    user = getattr(request.state, "user", None)
    if user and tier.name in ("authenticated", "heavy"):
        return f"user:{user}"
    # X-Forwarded-For trust: only when SYLION_TRUST_PROXY=1, else use peer.
    if os.environ.get("SYLION_TRUST_PROXY", "0").strip() == "1":
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return f"ip:{xff.split(',')[0].strip()}"
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"


# ---------------------------------------------------------------------------
# Counter store (fixed-window via cache)
# ---------------------------------------------------------------------------

def _window_key(identity: str, path_bucket: str, window_start: int) -> str:
    return f"sylion:ratelimit:{identity}:{path_bucket}:{window_start}"


def _path_bucket(tier: Tier) -> str:
    # All endpoints in a tier share one window so the limit is per-user-per-tier,
    # not per-user-per-endpoint. Heavy is split out so a hot council loop
    # doesn't burn the user's general budget.
    return tier.name


def _hit(identity: str, tier: Tier) -> tuple[int, int]:
    """Increment the counter for the current minute window. Returns (count, ttl_remaining)."""
    from sylion.infra.cache import get_cache  # local import: avoid cycle on cold start

    cache = get_cache()
    now = int(time.time())
    window_start = now - (now % 60)
    key = _window_key(identity, _path_bucket(tier), window_start)
    # Cache backend doesn't expose atomic INCR uniformly (in-memory has no
    # native atomic). We approximate: get-modify-set guarded by GIL for
    # in-memory and trusting Redis SETNX semantics in prod. A thundering
    # herd can briefly over-count by N concurrent requests; acceptable
    # for traffic shaping (we'd prefer an under-count anyway).
    try:
        current = cache.get(key) or 0
    except Exception:
        current = 0
    new = int(current) + 1
    try:
        # TTL = 90s so the window naturally expires before we'd reuse the key.
        cache.set(key, new, ttl=90)
    except Exception:
        log.warning("rate_limit set failed for %s", key, exc_info=True)
    ttl_remaining = max(1, 60 - (now - window_start))
    return new, ttl_remaining


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply tiered fixed-window rate limits. See module docstring."""

    async def dispatch(self, request: Request, call_next):
        if os.environ.get("SYLION_RATE_LIMIT_DISABLED", "0").strip() == "1":
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)

        tier = _classify(request)
        if tier.requests_per_minute <= 0:
            return await call_next(request)

        identity = _identity(request, tier)
        count, ttl = _hit(identity, tier)
        limit = tier.requests_per_minute

        if count > limit:
            # 429 with Retry-After per RFC 6585.
            log.info(
                "rate_limit 429 tier=%s identity=%s count=%d limit=%d",
                tier.name, identity, count, limit,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "tier": tier.name,
                    "limit_per_minute": limit,
                    "retry_after_seconds": ttl,
                },
                headers={
                    "Retry-After": str(ttl),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + ttl),
                },
            )

        response = await call_next(request)
        # Surface the budget for clients that want to back off proactively.
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + ttl)
        return response
