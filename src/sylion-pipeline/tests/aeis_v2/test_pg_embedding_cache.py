"""Tests for ``sylion.aeis_v2.embeddings.pg_cache.PgEmbeddingCache``.

Mocks psycopg at the connection-factory level — no live Postgres needed.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from sylion.aeis_v2.embeddings.cache import (
    CachingEmbeddingProvider,
    EmbeddingProvider,
)
from sylion.aeis_v2.embeddings.pg_cache import (
    PG_EMBEDDING_DDL,
    PgEmbeddingCache,
)


# ---------------------------------------------------------------------------
# Fake psycopg connection — backed by an in-memory dict.
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self, conn: "_FakeConn") -> None:
        self._conn = conn
        self._fetchone_result: Any = None
        self.last_executed: list[tuple[str, tuple]] = []

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.last_executed.append((sql, params))
        self._conn._handle(self, sql, params)

    def fetchone(self) -> Any:
        return self._fetchone_result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeConn:
    def __init__(self) -> None:
        self.rows: dict[tuple[bytes, str], dict[str, Any]] = {}
        self.committed = 0

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)

    def commit(self) -> None:
        self.committed += 1

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def _handle(self, cur: _FakeCursor, sql: str, params: tuple) -> None:
        sql_n = " ".join(sql.split()).strip().lower()
        if "create table" in sql_n or "create index" in sql_n:
            return
        if sql_n.startswith("select vector_json"):
            text_hash, model = params
            row = self.rows.get((text_hash, model))
            cur._fetchone_result = (row["vector_json"],) if row else None
            return
        if sql_n.startswith("update embedding_cache"):
            text_hash, model = params
            row = self.rows.get((text_hash, model))
            if row is not None:
                row["hit_count"] = row.get("hit_count", 0) + 1
            return
        if sql_n.startswith("insert into embedding_cache"):
            text_hash, model, vector_json = params
            self.rows[(text_hash, model)] = {
                "vector_json": vector_json, "hit_count": 0,
            }
            return
        if sql_n.startswith("select count(*)"):
            cur._fetchone_result = (len(self.rows),)
            return


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


def test_pg_embedding_ddl_is_idempotent() -> None:
    assert "CREATE TABLE IF NOT EXISTS embedding_cache" in PG_EMBEDDING_DDL
    assert "CREATE INDEX IF NOT EXISTS embedding_cache_last_hit_at_idx" in (
        PG_EMBEDDING_DDL
    )


# ---------------------------------------------------------------------------
# PgEmbeddingCache — get / put / stats
# ---------------------------------------------------------------------------


def test_get_miss_returns_none() -> None:
    conn = _FakeConn()
    cache = PgEmbeddingCache(connection_factory=lambda: conn)
    assert cache.get("ollama:m", "abcdef0123456789") is None
    assert cache.stats().misses == 1


def test_put_then_get_hits() -> None:
    conn = _FakeConn()
    cache = PgEmbeddingCache(connection_factory=lambda: conn)
    cache.put("ollama:m", "abcdef0123456789", [0.1, 0.2, 0.3])
    got = cache.get("ollama:m", "abcdef0123456789")
    assert got == [0.1, 0.2, 0.3]
    assert cache.stats().hits == 1


def test_put_overwrite_same_key_preserves_size() -> None:
    conn = _FakeConn()
    cache = PgEmbeddingCache(connection_factory=lambda: conn)
    cache.put("m", "ff" * 8, [1.0])
    cache.put("m", "ff" * 8, [9.9])
    assert cache.stats().size == 1
    assert cache.get("m", "ff" * 8) == [9.9]


def test_separate_models_share_table() -> None:
    """Composite PK keeps different backends isolated."""
    conn = _FakeConn()
    cache = PgEmbeddingCache(connection_factory=lambda: conn)
    cache.put("m1", "aa" * 8, [1.0])
    cache.put("m2", "aa" * 8, [2.0])
    assert cache.get("m1", "aa" * 8) == [1.0]
    assert cache.get("m2", "aa" * 8) == [2.0]
    assert cache.stats().size == 2


def test_empty_vector_skipped() -> None:
    conn = _FakeConn()
    cache = PgEmbeddingCache(connection_factory=lambda: conn)
    cache.put("m", "00" * 8, [])
    assert cache.stats().size == 0


def test_stats_counters_independent_of_size() -> None:
    conn = _FakeConn()
    cache = PgEmbeddingCache(connection_factory=lambda: conn)
    cache.put("m", "ab" * 8, [1.0])
    cache.get("m", "ab" * 8)        # +1 hit
    cache.get("m", "missing0000000000")  # +1 miss
    s = cache.stats()
    assert s.hits == 1
    assert s.misses == 1
    assert s.size == 1


def test_reset_counters_keeps_rows() -> None:
    conn = _FakeConn()
    cache = PgEmbeddingCache(connection_factory=lambda: conn)
    cache.put("m", "cd" * 8, [1.0])
    cache.get("m", "cd" * 8)
    cache.reset_counters()
    assert cache.stats().hits == 0
    assert cache.stats().misses == 0
    assert cache.stats().size == 1


def test_ensure_schema_runs_ddl_once() -> None:
    conn = _FakeConn()
    cache = PgEmbeddingCache(connection_factory=lambda: conn)
    cache.ensure_schema()
    cache.ensure_schema()
    # idempotent (second call is no-op).
    assert cache._init_done is True


def test_non_hex_key_falls_back_to_sha256_bytes() -> None:
    """Defensive: 16-char-non-hex still produces a stable bytea."""
    conn = _FakeConn()
    cache = PgEmbeddingCache(connection_factory=lambda: conn)
    cache.put("m", "not-hex-at-all!!", [0.5])
    assert cache.get("m", "not-hex-at-all!!") == [0.5]


# ---------------------------------------------------------------------------
# Integration with CachingEmbeddingProvider
# ---------------------------------------------------------------------------


class _RecProvider(EmbeddingProvider):
    """Minimal provider for the integration round-trip."""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def name(self) -> str:
        return "ollama:test"

    @property
    def dim(self) -> int:
        return 3

    def embed_one(self, text: str) -> list[float] | None:
        self.calls += 1
        return [0.1, 0.2, 0.3]


def test_pg_cache_works_as_caching_provider_backend() -> None:
    """The provider routes its idea-text reads through PgEmbeddingCache."""
    conn = _FakeConn()
    backend = PgEmbeddingCache(connection_factory=lambda: conn)
    underlying = _RecProvider()
    p = CachingEmbeddingProvider(underlying, backend)

    p.embed_one("idea-text")
    p.embed_one("idea-text")  # hits cache → underlying called once
    assert underlying.calls == 1
    s = p.stats
    assert s.hits == 1
    assert s.misses == 1


def test_pg_cache_caches_distinct_texts_separately() -> None:
    conn = _FakeConn()
    backend = PgEmbeddingCache(connection_factory=lambda: conn)
    underlying = _RecProvider()
    p = CachingEmbeddingProvider(underlying, backend)
    p.embed_one("idea A")
    p.embed_one("idea B")
    assert backend.stats().size == 2


# ---------------------------------------------------------------------------
# Defensive: corrupt vector_json
# ---------------------------------------------------------------------------


def test_get_corrupt_vector_json_treated_as_miss() -> None:
    conn = _FakeConn()
    cache = PgEmbeddingCache(connection_factory=lambda: conn)
    # Hand-write a corrupt row.
    bytea_key = bytes.fromhex("aa" * 8)
    conn.rows[(bytea_key, "m")] = {"vector_json": "not-json"}
    assert cache.get("m", "aa" * 8) is None
    assert cache.stats().misses == 1
