"""Tests for ``sylion.aeis_v2.embeddings.cache`` — sprint 2 day 4.

Covers the read-through cache wrapper around any EmbeddingProvider
plus the SQLite reference backend that mirrors the production PG schema.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from sylion.aeis_v2.embeddings.cache import (
    HASH_KEY_LEN,
    CacheStats,
    CachingEmbeddingProvider,
    SqliteEmbeddingCache,
    text_hash,
)
from sylion.aeis_v2.embeddings.provider import (
    EmbeddingProvider,
    StubEmbeddingProvider,
)


# ---------------------------------------------------------------------------
# Helpers — minimal recording provider so we can count delegations.
# ---------------------------------------------------------------------------


class _RecordingProvider(EmbeddingProvider):
    """Tracks how many times the underlying ``embed_one`` was called."""

    def __init__(
        self, vector: list[float] | None, name: str = "recording",
    ) -> None:
        self.calls = 0
        self._vector = vector
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def dim(self) -> int:
        return 4

    def embed_one(self, text: str) -> list[float] | None:
        self.calls += 1
        return self._vector


# ---------------------------------------------------------------------------
# text_hash + HASH_KEY_LEN sanity.
# ---------------------------------------------------------------------------


def test_text_hash_is_stable() -> None:
    """Same input → same hash across calls."""
    assert text_hash("idea about audyt") == text_hash("idea about audyt")


def test_text_hash_length() -> None:
    """Truncation length matches HASH_KEY_LEN."""
    assert len(text_hash("anything")) == HASH_KEY_LEN


def test_text_hash_different_inputs_diverge() -> None:
    """Distinct inputs map to distinct hashes (best-effort, not a guarantee)."""
    assert text_hash("a") != text_hash("b")


# ---------------------------------------------------------------------------
# SqliteEmbeddingCache backend.
# ---------------------------------------------------------------------------


def test_sqlite_cache_get_miss_returns_none() -> None:
    cache = SqliteEmbeddingCache()
    assert cache.get("ollama:m", "missing") is None
    assert cache.stats().misses == 1
    assert cache.stats().hits == 0


def test_sqlite_cache_put_then_get_hits() -> None:
    cache = SqliteEmbeddingCache()
    cache.put("ollama:m", "k1", [0.1, 0.2, 0.3])
    got = cache.get("ollama:m", "k1")
    assert got == [0.1, 0.2, 0.3]
    assert cache.stats().hits == 1


def test_sqlite_cache_size_increments() -> None:
    cache = SqliteEmbeddingCache()
    cache.put("m", "k1", [0.1])
    cache.put("m", "k2", [0.2])
    assert cache.stats().size == 2


def test_sqlite_cache_overwrite_same_key_preserves_size() -> None:
    cache = SqliteEmbeddingCache()
    cache.put("m", "k1", [0.1])
    cache.put("m", "k1", [0.99])
    assert cache.stats().size == 1
    assert cache.get("m", "k1") == [0.99]


def test_sqlite_cache_separates_models_by_pk() -> None:
    """Same key under two models is two rows — no cross-model leakage."""
    cache = SqliteEmbeddingCache()
    cache.put("m1", "k", [1.0])
    cache.put("m2", "k", [2.0])
    assert cache.get("m1", "k") == [1.0]
    assert cache.get("m2", "k") == [2.0]
    assert cache.stats().size == 2


def test_sqlite_cache_persists_to_disk(tmp_path: Path) -> None:
    db = tmp_path / "embeddings.db"
    c1 = SqliteEmbeddingCache(db_path=db)
    c1.put("m", "k", [0.5, 0.6])
    # New connection — same file, should see the row.
    c2 = SqliteEmbeddingCache(db_path=db)
    assert c2.get("m", "k") == [0.5, 0.6]


def test_sqlite_cache_skips_empty_vector() -> None:
    """Empty vectors are not persisted — keep the fallback live."""
    cache = SqliteEmbeddingCache()
    cache.put("m", "k", [])
    assert cache.stats().size == 0


def test_sqlite_cache_handles_corrupted_row() -> None:
    """Bad JSON in the vector column counts as miss + leaves DB intact."""
    cache = SqliteEmbeddingCache()
    cache.put("m", "k", [0.1])
    # Corrupt directly via the underlying connection.
    cache._conn.execute(
        "UPDATE embedding_cache SET vector = ? WHERE text_hash = ? AND model = ?",
        ("not-json", "k", "m"),
    )
    assert cache.get("m", "k") is None
    assert cache.stats().misses == 1


def test_sqlite_cache_reset_counters() -> None:
    cache = SqliteEmbeddingCache()
    cache.put("m", "k", [0.1])
    cache.get("m", "k")          # +1 hit
    cache.get("m", "missing")    # +1 miss
    cache.reset_counters()
    s = cache.stats()
    assert s.hits == 0 and s.misses == 0
    assert s.size == 1  # rows survived


# ---------------------------------------------------------------------------
# CacheStats.
# ---------------------------------------------------------------------------


def test_cache_stats_hit_rate() -> None:
    s = CacheStats(hits=3, misses=1, size=5)
    assert s.hit_rate == 0.75
    d = s.to_dict()
    assert d["hit_rate"] == 0.75
    assert d["hits"] == 3
    assert d["misses"] == 1


def test_cache_stats_zero_total_hit_rate_zero() -> None:
    s = CacheStats(hits=0, misses=0, size=0)
    assert s.hit_rate == 0.0


# ---------------------------------------------------------------------------
# CachingEmbeddingProvider — read-through behaviour.
# ---------------------------------------------------------------------------


def test_caching_provider_first_call_misses_then_hits() -> None:
    underlying = _RecordingProvider([0.1, 0.2, 0.3, 0.4])
    cache = SqliteEmbeddingCache()
    p = CachingEmbeddingProvider(underlying, cache)

    # First call: miss, delegate.
    v1 = p.embed_one("inspekcja")
    assert v1 == [0.1, 0.2, 0.3, 0.4]
    assert underlying.calls == 1

    # Second call (same text): hit, no further delegation.
    v2 = p.embed_one("inspekcja")
    assert v2 == [0.1, 0.2, 0.3, 0.4]
    assert underlying.calls == 1

    s = p.stats
    assert s.hits == 1
    assert s.misses == 1


def test_caching_provider_none_results_not_cached() -> None:
    """When underlying returns None we MUST NOT cache that — fallback live."""
    underlying = _RecordingProvider(None)
    cache = SqliteEmbeddingCache()
    p = CachingEmbeddingProvider(underlying, cache)

    assert p.embed_one("x") is None
    assert p.embed_one("x") is None
    # Both calls reached the underlying provider.
    assert underlying.calls == 2
    assert cache.stats().size == 0


def test_caching_provider_empty_text_returns_none() -> None:
    underlying = _RecordingProvider([0.1])
    cache = SqliteEmbeddingCache()
    p = CachingEmbeddingProvider(underlying, cache)

    assert p.embed_one("") is None
    assert p.embed_one("   ") is None
    assert underlying.calls == 0


def test_caching_provider_name_decorates() -> None:
    """name() exposes the wrapping for audit clarity."""
    underlying = _RecordingProvider([0.1])
    cache = SqliteEmbeddingCache()
    p = CachingEmbeddingProvider(underlying, cache)
    assert "caching" in p.name
    assert "recording" in p.name


def test_caching_provider_dim_passes_through() -> None:
    underlying = _RecordingProvider([0.1])
    cache = SqliteEmbeddingCache()
    p = CachingEmbeddingProvider(underlying, cache)
    assert p.dim == underlying.dim


def test_caching_provider_distinct_models_cache_separately() -> None:
    """Two providers with different names share the cache backend safely."""
    cache = SqliteEmbeddingCache()
    p1 = CachingEmbeddingProvider(_RecordingProvider([1.0], name="m1"), cache)
    p2 = CachingEmbeddingProvider(_RecordingProvider([2.0], name="m2"), cache)

    p1.embed_one("same text")
    p2.embed_one("same text")
    # Both providers populate the cache under their own name → 2 rows.
    assert cache.stats().size == 2


def test_caching_provider_with_stub_provider_works() -> None:
    """End-to-end smoke with the deterministic StubEmbeddingProvider."""
    cache = SqliteEmbeddingCache()
    p = CachingEmbeddingProvider(StubEmbeddingProvider(), cache)
    v = p.embed_one("audyt")
    assert v is not None
    assert len(v) == p.dim
    # Second call hits cache.
    v2 = p.embed_one("audyt")
    assert v2 == v
    assert cache.stats().hits == 1


def test_caching_provider_embed_many_routes_through_embed_one() -> None:
    underlying = _RecordingProvider([0.5, 0.5, 0.5, 0.5])
    cache = SqliteEmbeddingCache()
    p = CachingEmbeddingProvider(underlying, cache)
    out = p.embed_many(["a", "b", "a"])
    # 3 results, but only 2 underlying calls because "a" cached on second hit.
    assert len(out) == 3
    assert underlying.calls == 2
