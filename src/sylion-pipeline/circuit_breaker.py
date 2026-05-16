"""
circuit_breaker.py — G-01 / G-06 adjacent patch: LLM API circuit breaker.

Patch target : sylion-pipeline/dashboard/ (any module calling LLM providers)
Gap addressed : Resilience gap — cascading failures when upstream LLM APIs
                are unavailable cause the entire pipeline to stall.

Provides
--------
- ``CircuitBreaker`` class with three states: CLOSED → OPEN → HALF_OPEN
- Per-provider instances: Anthropic, OpenAI, Google, DeepSeek
- Fallback to Ollama (local) when provider circuit is OPEN
- ``@with_circuit_breaker(provider)`` decorator for async LLM call functions
- Prometheus-compatible metric export: ``sylion_circuit_breaker_state``
- GET /api/circuit-breakers — status dashboard endpoint

State machine
-------------
    CLOSED    Normal operation. Failures are counted.
              After FAILURE_THRESHOLD consecutive failures within WINDOW_S,
              transition → OPEN.

    OPEN      All calls are rejected immediately (fast-fail).
              After RESET_TIMEOUT_S, one probe call is allowed → HALF_OPEN.

    HALF_OPEN One probe allowed.
              Success → CLOSED (reset failure counter).
              Failure → OPEN (restart reset timer).

Parameters (tunable per environment via env vars)
-------------------------------------------------
    CB_FAILURE_THRESHOLD  int   default 5
    CB_WINDOW_S           float default 60.0
    CB_RESET_TIMEOUT_S    float default 30.0
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import threading
from enum import Enum
from typing import Any, Callable, Coroutine

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

_log = logging.getLogger("sylion.circuit_breaker")

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

FAILURE_THRESHOLD: int   = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
WINDOW_S: float          = float(os.getenv("CB_WINDOW_S", "60.0"))
RESET_TIMEOUT_S: float   = float(os.getenv("CB_RESET_TIMEOUT_S", "30.0"))

# ---------------------------------------------------------------------------
# State enum
# ---------------------------------------------------------------------------

class State(str, Enum):
    CLOSED    = "CLOSED"
    OPEN      = "OPEN"
    HALF_OPEN = "HALF_OPEN"


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """
    Thread-safe and async-compatible circuit breaker for a single upstream
    provider.

    Example::

        cb = CircuitBreaker("openai")

        async def call_openai(prompt: str) -> str:
            async with cb:
                return await _openai_client.complete(prompt)

        # Or use the decorator:
        @cb.protect
        async def call_openai(prompt: str) -> str:
            ...
    """

    def __init__(
        self,
        provider: str,
        failure_threshold: int   = FAILURE_THRESHOLD,
        window_s: float          = WINDOW_S,
        reset_timeout_s: float   = RESET_TIMEOUT_S,
    ) -> None:
        self.provider           = provider
        self.failure_threshold  = failure_threshold
        self.window_s           = window_s
        self.reset_timeout_s    = reset_timeout_s

        self._state             = State.CLOSED
        self._failure_times:    list[float] = []   # timestamps of recent failures
        self._opened_at:        float | None = None
        self._half_open_lock    = threading.Lock()
        self._probe_in_flight   = False            # only one HALF_OPEN probe at a time
        self._lock              = threading.Lock()

        # Cumulative counters for Prometheus metrics
        self.total_calls        = 0
        self.total_failures     = 0
        self.total_short_circuits = 0

    # ------------------------------------------------------------------
    # Public state property
    # ------------------------------------------------------------------

    @property
    def state(self) -> State:
        with self._lock:
            return self._evaluated_state()

    def _evaluated_state(self) -> State:
        """
        Internal: compute effective state (may auto-transition OPEN→HALF_OPEN
        based on elapsed time).  Must be called with self._lock held.
        """
        if self._state == State.OPEN:
            if self._opened_at and (time.monotonic() - self._opened_at) >= self.reset_timeout_s:
                # Promote to HALF_OPEN; actual probe gating handled in __aenter__
                self._state = State.HALF_OPEN
                _log.info(
                    "Circuit breaker [%s] OPEN → HALF_OPEN after %.0fs reset timeout",
                    self.provider, self.reset_timeout_s,
                )
        return self._state

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "CircuitBreaker":
        with self._lock:
            effective = self._evaluated_state()
            if effective == State.OPEN:
                self.total_short_circuits += 1
                raise CircuitOpenError(
                    f"Circuit breaker for '{self.provider}' is OPEN — "
                    "request short-circuited. Fallback to Ollama local."
                )
            if effective == State.HALF_OPEN:
                if self._probe_in_flight:
                    self.total_short_circuits += 1
                    raise CircuitOpenError(
                        f"Circuit breaker for '{self.provider}' is HALF_OPEN "
                        "and probe is already in flight."
                    )
                self._probe_in_flight = True
            self.total_calls += 1
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        with self._lock:
            if exc_type is None:
                # Success
                self._on_success()
            else:
                if not issubclass(exc_type, CircuitOpenError):
                    # Only record actual upstream failures, not short-circuits
                    self._on_failure()
            if self._state == State.HALF_OPEN:
                self._probe_in_flight = False
        return False   # do not suppress exceptions

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _on_success(self) -> None:
        """Called (lock held) when a call completes without exception."""
        prev = self._state
        self._state         = State.CLOSED
        self._failure_times = []
        self._opened_at     = None
        self._probe_in_flight = False
        if prev != State.CLOSED:
            _log.info(
                "Circuit breaker [%s] %s → CLOSED after successful probe",
                self.provider, prev.value,
            )

    def _on_failure(self) -> None:
        """Called (lock held) when a call raises an exception."""
        self.total_failures += 1
        now = time.monotonic()
        # Prune failures outside the sliding window
        self._failure_times = [t for t in self._failure_times if now - t < self.window_s]
        self._failure_times.append(now)

        if len(self._failure_times) >= self.failure_threshold:
            prev = self._state
            self._state     = State.OPEN
            self._opened_at = now
            self._probe_in_flight = False
            _log.warning(
                "Circuit breaker [%s] %s → OPEN after %d failures in %.0fs",
                self.provider, prev.value,
                len(self._failure_times), self.window_s,
            )

    # ------------------------------------------------------------------
    # Decorator
    # ------------------------------------------------------------------

    def protect(self, func: Callable[..., Coroutine]) -> Callable:
        """
        Async function decorator that wraps the call with this circuit breaker.

        Example::

            @anthropic_cb.protect
            async def ask_claude(prompt: str) -> str:
                return await client.messages.create(...)
        """
        import functools

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with self:
                return await func(*args, **kwargs)
        return wrapper

    # ------------------------------------------------------------------
    # Metrics snapshot
    # ------------------------------------------------------------------

    def metrics(self) -> dict[str, Any]:
        """Return a snapshot dict suitable for JSON or Prometheus export."""
        return {
            "provider":           self.provider,
            "state":              self.state.value,
            "failure_count":      len(self._failure_times),
            "failure_threshold":  self.failure_threshold,
            "total_calls":        self.total_calls,
            "total_failures":     self.total_failures,
            "total_short_circuits": self.total_short_circuits,
            "open_since":         self._opened_at,
            "reset_timeout_s":    self.reset_timeout_s,
        }

    def __repr__(self) -> str:
        return f"<CircuitBreaker provider={self.provider!r} state={self.state.value}>"


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class CircuitOpenError(RuntimeError):
    """Raised when a call is rejected because the circuit is OPEN or HALF_OPEN."""


# ---------------------------------------------------------------------------
# Per-provider singletons
# ---------------------------------------------------------------------------

anthropic_cb  = CircuitBreaker("anthropic")
openai_cb     = CircuitBreaker("openai")
google_cb     = CircuitBreaker("google")
deepseek_cb   = CircuitBreaker("deepseek")

_ALL_BREAKERS: dict[str, CircuitBreaker] = {
    "anthropic": anthropic_cb,
    "openai":    openai_cb,
    "google":    google_cb,
    "deepseek":  deepseek_cb,
}


def get_breaker(provider: str) -> CircuitBreaker:
    """Return the circuit breaker for *provider*, creating one if unknown."""
    if provider not in _ALL_BREAKERS:
        _ALL_BREAKERS[provider] = CircuitBreaker(provider)
    return _ALL_BREAKERS[provider]


# ---------------------------------------------------------------------------
# Decorator shorthand
# ---------------------------------------------------------------------------

def with_circuit_breaker(provider: str) -> Callable:
    """
    Class/function decorator that binds a named circuit breaker.

    Usage::

        @with_circuit_breaker("anthropic")
        async def call_claude(prompt: str) -> str:
            return await _client.complete(prompt)

        # With explicit fallback handling:
        try:
            result = await call_claude(prompt)
        except CircuitOpenError:
            result = await call_ollama_local(prompt)   # fallback
    """
    def decorator(func: Callable) -> Callable:
        return get_breaker(provider).protect(func)
    return decorator


# ---------------------------------------------------------------------------
# Ollama fallback helper
# ---------------------------------------------------------------------------

async def call_with_ollama_fallback(
    provider: str,
    primary_func: Callable[..., Coroutine],
    ollama_func: Callable[..., Coroutine],
    *args,
    **kwargs,
) -> Any:
    """
    Attempt *primary_func* through the named provider's circuit breaker.
    If the circuit is OPEN (or the call fails), transparently fall back to
    *ollama_func* (local Ollama instance).

    Example::

        response = await call_with_ollama_fallback(
            provider="anthropic",
            primary_func=call_claude,
            ollama_func=call_ollama,
            prompt=user_prompt,
        )
    """
    cb = get_breaker(provider)
    try:
        async with cb:
            return await primary_func(*args, **kwargs)
    except CircuitOpenError:
        _log.warning(
            "Circuit OPEN for '%s' — falling back to Ollama local", provider
        )
        return await ollama_func(*args, **kwargs)
    except Exception as exc:
        _log.error(
            "Call to '%s' failed (%s) — falling back to Ollama local",
            provider, exc,
        )
        return await ollama_func(*args, **kwargs)


# ---------------------------------------------------------------------------
# Prometheus metric helpers
# ---------------------------------------------------------------------------

def prometheus_metrics() -> str:
    """
    Return a Prometheus text-format exposition of circuit breaker states.

    Exposes ``sylion_circuit_breaker_state`` gauge (0=CLOSED, 1=HALF_OPEN, 2=OPEN)
    with label ``provider``.

    Intended to be appended to the existing GET /api/metrics response body.
    """
    _state_value = {State.CLOSED: 0, State.HALF_OPEN: 1, State.OPEN: 2}
    lines: list[str] = [
        "# HELP sylion_circuit_breaker_state Circuit breaker state per LLM provider (0=CLOSED,1=HALF_OPEN,2=OPEN)",
        "# TYPE sylion_circuit_breaker_state gauge",
    ]
    for name, cb in _ALL_BREAKERS.items():
        s = cb.state
        lines.append(
            f'sylion_circuit_breaker_state{{provider="{name}",state="{s.value}"}} '
            f"{_state_value[s]}"
        )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# REST router
# ---------------------------------------------------------------------------

class BreakerStatus(BaseModel):
    provider: str
    state: str
    failure_count: int
    failure_threshold: int
    total_calls: int
    total_failures: int
    total_short_circuits: int


# ---------------------------------------------------------------------------
# P8-CB-RATELIMIT (Wave 8): Sliding window rate limiter for /reset endpoint.
# 10 req/min per composite key (user_id + IP).
# Follows the same pattern as FIX-01 login rate limiter in app.py.
# Inline pruning on every check — no separate cleanup timer needed.
# ---------------------------------------------------------------------------

_CB_RESET_RATE_LIMIT_MAX: int    = int(os.getenv("CB_RESET_RATE_LIMIT_MAX", "10"))
_CB_RESET_RATE_LIMIT_WINDOW: int = int(os.getenv("CB_RESET_RATE_LIMIT_WINDOW", "60"))  # seconds

_cb_reset_attempts: dict[str, list[float]] = {}  # composite_key -> [timestamps]
_cb_reset_rate_lock = threading.Lock()


def _cb_get_client_ip(request: Request) -> str:
    """Minimal IP extraction for rate limiting (no trusted-proxy logic needed here)."""
    if request.client and request.client.host:
        return request.client.host
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return "unknown"


def _cb_reset_rate_check(request: Request, user_id: str) -> tuple[bool, int]:
    """
    P8-CB-RATELIMIT: sliding window check for the /reset endpoint.

    Key: "{user_id}:{ip}" — combines authenticated identity and network address
    to prevent both per-user abuse and IP-cycling bypass.

    Returns (allowed: bool, retry_after: int seconds).
    Records the attempt on every call (not only failures) — reset is an
    operational action, not a credential probe.
    """
    ip = _cb_get_client_ip(request)
    key = f"{user_id}:{ip}"
    now = time.time()
    with _cb_reset_rate_lock:
        timestamps = _cb_reset_attempts.get(key, [])
        cutoff = now - _CB_RESET_RATE_LIMIT_WINDOW
        # Inline pruning — remove timestamps outside sliding window
        timestamps = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= _CB_RESET_RATE_LIMIT_MAX:
            # Window full — calculate seconds until oldest slot expires
            retry_after = max(1, int(_CB_RESET_RATE_LIMIT_WINDOW - (now - timestamps[0])) + 1)
            _cb_reset_attempts[key] = timestamps
            return False, retry_after
        # Record this attempt
        timestamps.append(now)
        _cb_reset_attempts[key] = timestamps
        # P9-003: remove key if list is empty after pruning to avoid memory leak
        if not _cb_reset_attempts[key]:
            del _cb_reset_attempts[key]
        return True, 0


# ---------------------------------------------------------------------------
# Auth helper — session check without importing from app.py (avoids circular import).
# Reads the user dict injected by app.py's get_current_user() into request.state.
# Falls back to 401 if no session present.
# ---------------------------------------------------------------------------

def _cb_require_auth(request: Request) -> dict:
    """
    P8-CB-AUTH + P7-001: verify that a valid session OR JWT exists.

    Priority:
    1. request.state.user (set by middleware)
    2. JWT Bearer token / sylion_jwt cookie (P7-001)
    3. Cookie session (sylion_session / X-Session-Token)

    This avoids a circular import (circuit_breaker.py ← app.py).
    """
    # Fast path: middleware already resolved the user
    user = getattr(request.state, "user", None)
    if user and isinstance(user, dict) and user.get("username"):
        return user

    # P7-001: try JWT first (Bearer header or sylion_jwt cookie)
    try:
        _jwt_mod = __import__("jwt_auth")
        raw_token = _jwt_mod.extract_token_from_request(request)
        if raw_token:
            if _jwt_mod.is_blacklisted(raw_token):
                raise HTTPException(status_code=401, detail="Token JWT unieważniony")
            payload = _jwt_mod.verify_access_token(raw_token)  # raises 401 on fail
            return {
                "user_id": payload["sub"],
                "username": payload.get("sub"),
                "role": payload.get("role", ""),
                "auth_method": "jwt",
            }
    except ImportError:
        _log.debug("CB auth: jwt_auth module not available, falling back to session")
    except HTTPException:
        raise  # propagate JWT errors (expired / blacklisted)
    except Exception as jwt_exc:
        _log.debug("CB auth: JWT check failed — %s", jwt_exc)

    # Slow path: resolve session token from header or cookie
    token = (
        request.headers.get("X-Session-Token", "")
        or request.cookies.get("sylion_session", "")
    )
    if not token:
        raise HTTPException(status_code=401, detail="Wymagane logowanie")

    # Import DB helper at call time to avoid module-level circular dependency
    try:
        import importlib
        _db_mod = importlib.import_module("db")
        get_session = getattr(_db_mod, "get_session", None)
        if get_session is None:
            # Fallback: get_conn + raw query
            import sqlite3 as _sqlite3
            import time as _time
            get_conn = getattr(_db_mod, "get_conn")
            conn = get_conn()
            try:
                sess = conn.execute(
                    "SELECT s.*, u.role FROM sessions s "
                    "JOIN users u ON s.user_id = u.id "
                    "WHERE s.token=? AND s.expires_at > ?",
                    (token, _time.time()),
                ).fetchone()
            finally:
                conn.close()
        else:
            sess = get_session(token)
    except Exception as exc:
        _log.warning("CB auth: DB lookup failed — %s", exc)
        raise HTTPException(status_code=401, detail="Wymagane logowanie") from exc

    if not sess:
        raise HTTPException(status_code=401, detail="Wymagane logowanie")

    return dict(sess)


def _cb_require_role(request: Request, *roles: str) -> dict:
    """
    P8-CB-AUTH: verify session AND role. Mirrors app.py require_role() semantics.
    Owner always has access (same as main app).
    """
    user = _cb_require_auth(request)
    role = user.get("role", "")
    if role != "owner" and role not in roles:
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: wymagana rola {', '.join(roles)}",
        )
    return user


router = APIRouter(prefix="/api/circuit-breakers", tags=["circuit-breakers"])


@router.get("", response_model=list[BreakerStatus])
async def list_circuit_breakers(request: Request):
    """
    GET /api/circuit-breakers

    Return current state of all registered LLM circuit breakers.

    P8-CB-AUTH (Wave 8): authentication required — operational data
    must not be exposed unauthenticated (P7-003 finding).
    Wymagane logowanie (dowolna rola).
    """
    _cb_require_auth(request)  # P8-CB-AUTH: require valid session
    return [
        BreakerStatus(
            provider=name,
            state=cb.state.value,
            failure_count=len(cb._failure_times),
            failure_threshold=cb.failure_threshold,
            total_calls=cb.total_calls,
            total_failures=cb.total_failures,
            total_short_circuits=cb.total_short_circuits,
        )
        for name, cb in _ALL_BREAKERS.items()
    ]


@router.post("/{provider}/reset")
async def reset_circuit_breaker(
    provider: str,
    request: Request,
):
    """
    POST /api/circuit-breakers/{provider}/reset

    Manually force a circuit breaker back to CLOSED state.
    Useful during incident recovery when the upstream service is known healthy.

    Fala 6 patch P6-05 (F-009): dodano auth guard — wcześniej DoS vector
    (każdy mógł zresetować breakery bez autoryzacji).
    Wymagana rola: owner lub operator.

    P8-CB-RATELIMIT (Wave 8): sliding window rate limiter 10 req/60s per user+IP.
    P8-CB-AUTH (Wave 8): guard migrated from X-Role header to session-based auth.
    """
    # P8-CB-AUTH: session-based role check (replaces weak X-Role header guard).
    # X-Role header was exploitable — any client could send X-Role: owner.
    user = _cb_require_role(request, "owner", "operator")
    user_id: str = str(user.get("username") or user.get("id") or "unknown")

    # P8-CB-RATELIMIT: sliding window 10/min per user_id + IP
    allowed, retry_after = _cb_reset_rate_check(request, user_id)
    if not allowed:
        _log.warning(
            "CB reset rate limit exceeded — user=%s ip=%s provider=%s",
            user_id, _cb_get_client_ip(request), provider,
        )
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    if provider not in _ALL_BREAKERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    cb = _ALL_BREAKERS[provider]
    with cb._lock:
        cb._state         = State.CLOSED
        cb._failure_times = []
        cb._opened_at     = None
        cb._probe_in_flight = False
    _log.info(
        "Circuit breaker [%s] manually reset to CLOSED by user=%s",
        provider, user_id,
    )
    return {"provider": provider, "state": "CLOSED", "message": "Circuit manually reset"}
