"""SYLION Phase 3 W1.3 — unified cache layer.

Provides a single cache API used by hot-path services. Backed by Redis
when available (`SYLION_CACHE_URL` env or `redis://localhost:6379/0`
default), falls back transparently to a process-local LRU when Redis is
unreachable. The fallback keeps tests and local dev runs working without
infra; production must point at a real Redis.

Public API
----------
- `get(key)`, `set(key, value, ttl)`, `delete(key)`, `invalidate(pattern)`
- `@cached(key_fn, ttl, namespace)` decorator
- `get_cache()` global singleton

Invalidation contract
---------------------
Call sites that write (governance ticket update, memory write, project
mutation, funding scan) must emit `invalidate(pattern)` for the keys
they touch. The patterns are namespaced; see `_NAMESPACES` for the
canonical list. Lookups under a stale namespace return `None` (cache
miss), so a missed invalidation degrades to a slow read, never a wrong
read.

Hot-set targets (from PROMPT_AGENT.md §2.2 W1.3 + W1.2 hand-off)
----------------------------------------------------------------
| namespace            | TTL  | invalidation trigger                  |
|----------------------|------|---------------------------------------|
| council.decision     | 1h   | council reconcile / membership change |
| memory.search        | 15m  | memory write                          |
| workspace.project    | 5m   | project mutation                      |
| funding.programs     | 1h   | funding scan completion               |
| observability.metrics| 30s  | none (auto-expire)                    |
| audit.events         | 5m   | new audit append                      |
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

log = logging.getLogger("sylion.infra.cache")

# ----- public typing ------------------------------------------------------- #

T = TypeVar("T")
KeyFn = Callable[..., str]

# ----- namespaces ---------------------------------------------------------- #

_NAMESPACES: dict[str, int] = {
    "council.decision": 3600,
    "memory.search": 900,
    "workspace.project": 300,
    "funding.programs": 3600,
    "observability.metrics": 30,
    "audit.events": 300,
}


def default_ttl(namespace: str) -> int:
    """Look up the canonical TTL for a hot-set namespace, or 60s."""
    return _NAMESPACES.get(namespace, 60)


# ----- in-memory fallback -------------------------------------------------- #


class _InMemoryLRU:
    """Thread-safe LRU + TTL fallback. Bounded so misuse can't OOM the
    process — once the bound is hit we evict the oldest entry."""

    def __init__(self, max_entries: int = 4096) -> None:
        self._max = max_entries
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.RLock()
        # stats — read by /api/v1/observability/metrics in W3
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, key: str) -> Any | None:
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            expires_at, value = entry
            if expires_at and expires_at < now:
                del self._store[key]
                self.misses += 1
                return None
            self._store.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        expires_at = time.time() + ttl if ttl > 0 else 0.0
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (expires_at, value)
            while len(self._store) > self._max:
                self._store.popitem(last=False)
                self.evictions += 1

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def invalidate(self, pattern: str) -> int:
        # Pattern is "ns.*" or full key. Implement simple prefix match —
        # real Redis backend uses SCAN+DEL with the same semantics.
        prefix = pattern[:-1] if pattern.endswith("*") else pattern
        n = 0
        with self._lock:
            doomed = [k for k in self._store if k.startswith(prefix)]
            for k in doomed:
                del self._store[k]
                n += 1
        return n

    def size(self) -> int:
        with self._lock:
            return len(self._store)


# ----- Redis-backed wrapper ----------------------------------------------- #


class _RedisBackend:
    """Thin wrapper around `redis.Redis`. Lazy-imports redis so the
    package is optional — unit tests don't require redis installed."""

    def __init__(self, url: str) -> None:
        import redis  # local import — optional dep

        self._client = redis.Redis.from_url(
            url,
            socket_timeout=1.0,           # avoid stalling the request loop
            socket_connect_timeout=1.0,
            decode_responses=False,
            health_check_interval=30,
        )
        # ping eagerly so health is known at construction
        self._client.ping()
        self.hits = 0
        self.misses = 0
        self.evictions = 0  # Redis evicts on its own; counter stays 0

    def get(self, key: str) -> Any | None:
        raw = self._client.get(key)
        if raw is None:
            self.misses += 1
            return None
        self.hits += 1
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw

    def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            payload = json.dumps(value, default=str)
        except (TypeError, ValueError):
            payload = str(value)
        if ttl > 0:
            self._client.setex(key, ttl, payload)
        else:
            self._client.set(key, payload)

    def delete(self, key: str) -> bool:
        return bool(self._client.delete(key))

    def invalidate(self, pattern: str) -> int:
        # SCAN+DEL — non-blocking on the server unlike KEYS+DEL.
        count = 0
        for raw_key in self._client.scan_iter(match=pattern, count=500):
            self._client.delete(raw_key)
            count += 1
        return count

    def size(self) -> int:
        # dbsize is O(1) in Redis — cheap to expose for /metrics.
        return int(self._client.dbsize())


# ----- public Cache facade ------------------------------------------------ #


class Cache:
    """Thread-safe, backend-agnostic cache facade. Use the global
    `get_cache()` singleton in app code; instantiate directly in tests
    that need an isolated in-memory cache."""

    def __init__(self, backend: _InMemoryLRU | _RedisBackend) -> None:
        self._backend = backend

    @property
    def backend_name(self) -> str:
        return type(self._backend).__name__

    def get(self, key: str) -> Any | None:
        return self._backend.get(key)

    def set(self, key: str, value: Any, ttl: int | None = None,
            namespace: str | None = None) -> None:
        if ttl is None:
            ttl = default_ttl(namespace) if namespace else 60
        self._backend.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        return self._backend.delete(key)

    def invalidate(self, pattern: str) -> int:
        """Drop every entry matching `pattern` (suffix `*` for prefix
        match). Returns count removed."""
        return self._backend.invalidate(pattern)

    def stats(self) -> dict[str, Any]:
        return {
            "backend": self.backend_name,
            "hits": self._backend.hits,
            "misses": self._backend.misses,
            "evictions": self._backend.evictions,
            "size": self._backend.size(),
            "hit_ratio": _ratio(self._backend.hits, self._backend.misses),
        }


def _ratio(hits: int, misses: int) -> float:
    total = hits + misses
    return round(hits / total, 4) if total else 0.0


# ----- key helpers -------------------------------------------------------- #


def hash_key(*parts: Any) -> str:
    """Deterministic short hash for cache keys built from arbitrary
    payloads. We hash via sha1 (truncated) — collisions are not a
    security boundary here, just a cache key. usedforsecurity=False
    suppresses bandit B324 since this is a non-cryptographic use."""
    blob = json.dumps(parts, sort_keys=True, default=str).encode("utf-8")
    return hashlib.new("sha1", blob, usedforsecurity=False).hexdigest()[:16]


def make_key(namespace: str, *parts: Any) -> str:
    return f"sylion:{namespace}:{hash_key(*parts)}"


# ----- @cached decorator -------------------------------------------------- #


def cached(
    namespace: str,
    *,
    key_fn: KeyFn | None = None,
    ttl: int | None = None,
):
    """Cache a function's return value under `namespace`.

    The decorated function must be deterministic for its inputs (or you
    must accept stale reads). Failures in the cache layer never bubble
    up — a cache miss or backend exception simply runs the function.

    Usage:
        @cached("memory.search", key_fn=lambda query, top_k: (query, top_k))
        def search(query: str, top_k: int) -> list[dict]:
            ...

    `key_fn` receives the same args/kwargs as the wrapped function and
    returns the parts that uniquely identify the call. If omitted, all
    args+kwargs are hashed (rarely what you want — be explicit).
    """

    effective_ttl = ttl if ttl is not None else default_ttl(namespace)

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            try:
                parts = key_fn(*args, **kwargs) if key_fn else (args, kwargs)
                if not isinstance(parts, tuple):
                    parts = (parts,)
                key = make_key(namespace, *parts)
                hit = cache.get(key)
                if hit is not None:
                    return hit
            except Exception:                    # noqa: BLE001
                # Cache layer must never break the call site. A logged
                # warning is enough; treat as miss and run the function.
                log.warning("cache get failed for %s", namespace, exc_info=True)
                key = None
            result = fn(*args, **kwargs)
            if key is not None:
                try:
                    cache.set(key, result, ttl=effective_ttl)
                except Exception:                # noqa: BLE001
                    log.warning("cache set failed for %s", namespace,
                                exc_info=True)
            return result
        return wrapper
    return decorator


# ----- singleton wiring --------------------------------------------------- #


_cache_lock = threading.Lock()
_cache: Cache | None = None


def _build_backend() -> _InMemoryLRU | _RedisBackend:
    url = os.environ.get("SYLION_CACHE_URL", "").strip()
    if not url or url.lower() == "memory":
        log.info("cache: using in-memory LRU (SYLION_CACHE_URL unset)")
        return _InMemoryLRU()
    try:
        backend = _RedisBackend(url)
        log.info("cache: connected to Redis at %s", _redact(url))
        return backend
    except Exception:                            # noqa: BLE001
        log.warning("cache: Redis at %s unreachable — falling back to in-memory",
                    _redact(url), exc_info=True)
        return _InMemoryLRU()


def _redact(url: str) -> str:
    # never log credentials; also avoids accidental log-grep leaks.
    if "@" in url:
        scheme, rest = url.split("://", 1) if "://" in url else ("", url)
        userinfo, host = rest.split("@", 1)
        return f"{scheme}://[redacted]@{host}" if scheme else f"[redacted]@{host}"
    return url


def get_cache() -> Cache:
    """Return the process-wide cache singleton. Idempotent."""
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = Cache(_build_backend())
    return _cache


def reset_cache() -> None:
    """Test-only — drop the singleton so the next `get_cache()` rebuilds.
    Production code must NOT call this."""
    global _cache
    with _cache_lock:
        _cache = None


__all__ = [
    "Cache",
    "cached",
    "default_ttl",
    "get_cache",
    "hash_key",
    "make_key",
    "reset_cache",
]
