"""Tests for sylion.infra.cache (Phase 3 W1.3)."""

from __future__ import annotations

import time

import pytest

from sylion.infra.cache import (
    Cache,
    cached,
    default_ttl,
    get_cache,
    hash_key,
    make_key,
    reset_cache,
)
from sylion.infra.cache import _InMemoryLRU


@pytest.fixture(autouse=True)
def _clean_singleton(monkeypatch):
    monkeypatch.setenv("SYLION_CACHE_URL", "memory")
    reset_cache()
    yield
    reset_cache()


# ---------------------------------------------------------------- LRU primitive

def test_lru_basic_set_get():
    lru = _InMemoryLRU(max_entries=3)
    lru.set("a", 1, ttl=60)
    assert lru.get("a") == 1
    assert lru.hits == 1
    assert lru.misses == 0


def test_lru_miss_increments_misses():
    lru = _InMemoryLRU()
    assert lru.get("nope") is None
    assert lru.misses == 1


def test_lru_ttl_expires():
    lru = _InMemoryLRU()
    lru.set("k", "v", ttl=1)
    assert lru.get("k") == "v"
    time.sleep(1.1)
    assert lru.get("k") is None


def test_lru_evicts_when_full():
    lru = _InMemoryLRU(max_entries=2)
    lru.set("a", 1, ttl=60)
    lru.set("b", 2, ttl=60)
    lru.set("c", 3, ttl=60)             # evicts "a"
    assert lru.get("a") is None
    assert lru.get("b") == 2
    assert lru.get("c") == 3
    assert lru.evictions == 1


def test_lru_invalidate_prefix():
    lru = _InMemoryLRU()
    lru.set("ns.alpha", 1, ttl=60)
    lru.set("ns.beta", 2, ttl=60)
    lru.set("other.gamma", 3, ttl=60)
    n = lru.invalidate("ns.*")
    assert n == 2
    assert lru.get("ns.alpha") is None
    assert lru.get("other.gamma") == 3


# -------------------------------------------------------------------- Cache facade

def test_singleton_idempotent():
    a = get_cache()
    b = get_cache()
    assert a is b


def test_cache_uses_namespace_default_ttl(monkeypatch):
    cache = get_cache()
    cache.set("sylion:memory.search:abc", {"x": 1}, namespace="memory.search")
    assert cache.get("sylion:memory.search:abc") == {"x": 1}


def test_default_ttl_known_namespace():
    assert default_ttl("memory.search") == 900
    assert default_ttl("council.decision") == 3600
    assert default_ttl("nope") == 60


def test_stats_reports_backend_and_ratio():
    cache = get_cache()
    cache.set("k", 1, ttl=60)
    cache.get("k")          # hit
    cache.get("missing")    # miss
    s = cache.stats()
    assert s["backend"] == "_InMemoryLRU"
    assert s["hits"] == 1
    assert s["misses"] == 1
    assert s["hit_ratio"] == 0.5


# ------------------------------------------------------------------- key helpers

def test_hash_key_is_deterministic():
    assert hash_key("foo", 1) == hash_key("foo", 1)
    assert hash_key("foo", 1) != hash_key("foo", 2)


def test_make_key_includes_namespace_and_prefix():
    k = make_key("memory.search", "hello", 10)
    assert k.startswith("sylion:memory.search:")


# ---------------------------------------------------------------- @cached decorator

def test_cached_returns_first_call_value():
    calls = {"n": 0}

    @cached("memory.search", key_fn=lambda q, top_k: (q, top_k), ttl=60)
    def search(q, top_k):
        calls["n"] += 1
        return [{"q": q, "top_k": top_k, "n": calls["n"]}]

    a = search("kpi", 10)
    b = search("kpi", 10)
    assert a == b
    assert calls["n"] == 1


def test_cached_keys_off_kwargs():
    @cached("memory.search", key_fn=lambda q, top_k: (q, top_k), ttl=60)
    def search(q, top_k):
        return (q, top_k)

    assert search("kpi", 10) == ("kpi", 10)
    assert search("kpi", 20) == ("kpi", 20)
    assert get_cache().stats()["misses"] == 2  # both first-time


def test_cached_invalidation_drops_namespace():
    @cached("memory.search", key_fn=lambda q: (q,), ttl=60)
    def search(q):
        return f"result:{q}:{time.time_ns()}"

    a = search("kpi")
    assert search("kpi") == a
    get_cache().invalidate("sylion:memory.search:*")
    b = search("kpi")
    assert b != a


def test_cached_swallows_backend_exceptions(monkeypatch):
    """If the cache backend explodes, the wrapped function still runs."""
    @cached("memory.search", key_fn=lambda q: (q,), ttl=60)
    def search(q):
        return f"value:{q}"

    cache = get_cache()
    # poison the backend
    def boom(*a, **k):
        raise RuntimeError("redis dead")
    monkeypatch.setattr(cache._backend, "get", boom)
    monkeypatch.setattr(cache._backend, "set", boom)

    # must not raise; must return the function value
    assert search("ok") == "value:ok"


# --------------------------------------------------------------- isolation contract

def test_isolated_cache_does_not_leak_into_singleton():
    """Direct construction (used in tests) is isolated from get_cache()."""
    isolated = Cache(_InMemoryLRU())
    isolated.set("k", "v", ttl=60)
    assert get_cache().get("k") is None
