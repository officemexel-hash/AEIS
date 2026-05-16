"""W13/W16 G1 — Embedding cache abstraction + provider wrapper.

Sprint 2 day 4 deliverable per ADR-001 #5 (W7→W13 hybrid) and the
embeddings-PG-schema reservoir item.

Three components:

* :class:`EmbeddingCacheBackend` — abstract interface (get/put/stats).
* :class:`SqliteEmbeddingCache` — reference impl backed by SQLite. Used
  in dev/CI; the same schema mirrors the production Postgres layout
  (``aeis_v2/embeddings/pg_schema.sql``).
* :class:`CachingEmbeddingProvider` — decorates any
  :class:`EmbeddingProvider` with read-through caching keyed by
  ``(model, sha256(text)[:16])``. Cache miss falls through to the
  underlying provider; on success the vector is persisted before being
  returned.

Cache misses for ``None`` results are NOT persisted — keeping the
fallback path live (per ADR-001 #5 the matcher falls back to Jaccard
when the provider returns None).
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from sylion.aeis_v2.embeddings.provider import EmbeddingProvider

log = logging.getLogger(__name__)

#: Truncation length for hash keys. 16 hex chars = 8 bytes ~ 2^64
#: collision space — well below birthday-bound for our scale (≤1M items).
HASH_KEY_LEN: int = 16


def text_hash(text: str) -> str:
    """Stable cache key for a piece of text. SHA-256 truncated to 16 chars."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:HASH_KEY_LEN]


@dataclass(frozen=True, slots=True)
class CacheStats:
    """Snapshot of cache hit/miss counters."""

    hits: int
    misses: int
    size: int

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return 0.0 if total == 0 else self.hits / total

    def to_dict(self) -> dict[str, float | int]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "size": self.size,
            "hit_rate": round(self.hit_rate, 4),
        }


class EmbeddingCacheBackend(ABC):
    """Abstract cache backend.

    Implementations need not be thread-safe at the SQL layer — wrappers
    handle locking. They MUST be safe to call from multiple threads as
    long as the caller serialises access via the bundled lock.
    """

    @abstractmethod
    def get(self, model: str, key: str) -> list[float] | None:
        """Return cached vector or None on miss."""

    @abstractmethod
    def put(self, model: str, key: str, vector: list[float]) -> None:
        """Persist a vector under (model, key). Overwrites existing."""

    @abstractmethod
    def stats(self) -> CacheStats:
        """Return current hit/miss/size counters."""


class SqliteEmbeddingCache(EmbeddingCacheBackend):
    """SQLite-backed reference cache.

    Schema (mirrored in pg_schema.sql for production):

        CREATE TABLE IF NOT EXISTS embedding_cache (
            text_hash TEXT NOT NULL,
            model     TEXT NOT NULL,
            vector    TEXT NOT NULL,    -- JSON-encoded list[float]
            created_at REAL NOT NULL,
            hit_count  INTEGER NOT NULL DEFAULT 0,
            last_hit_at REAL,
            PRIMARY KEY (text_hash, model)
        );

    The composite PK (text_hash, model) protects against collisions
    across embedding backends — same input, different model → different
    cache rows.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(
            self._db_path, check_same_thread=False, isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    text_hash TEXT NOT NULL,
                    model     TEXT NOT NULL,
                    vector    TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    hit_count  INTEGER NOT NULL DEFAULT 0,
                    last_hit_at REAL,
                    PRIMARY KEY (text_hash, model)
                )
            """)

    def get(self, model: str, key: str) -> list[float] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT vector FROM embedding_cache "
                "WHERE text_hash = ? AND model = ?",
                (key, model),
            ).fetchone()
            if row is None:
                self._misses += 1
                return None
            try:
                vec = json.loads(row["vector"])
            except json.JSONDecodeError:
                self._misses += 1
                return None
            if not isinstance(vec, list):
                self._misses += 1
                return None
            # Bump hit_count + last_hit_at — best effort, never block.
            self._conn.execute(
                "UPDATE embedding_cache "
                "SET hit_count = hit_count + 1, last_hit_at = ? "
                "WHERE text_hash = ? AND model = ?",
                (time.time(), key, model),
            )
            self._hits += 1
            return vec

    def put(self, model: str, key: str, vector: list[float]) -> None:
        if not vector:
            return
        encoded = json.dumps(vector, separators=(",", ":"))
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO embedding_cache "
                "(text_hash, model, vector, created_at, hit_count, last_hit_at) "
                "VALUES (?, ?, ?, ?, 0, NULL)",
                (key, model, encoded, time.time()),
            )

    def stats(self) -> CacheStats:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM embedding_cache",
            ).fetchone()
            size = int(row["n"]) if row is not None else 0
        return CacheStats(hits=self._hits, misses=self._misses, size=size)

    def reset_counters(self) -> None:
        """Reset in-memory hit/miss counters (size persists in DB)."""
        with self._lock:
            self._hits = 0
            self._misses = 0


class CachingEmbeddingProvider(EmbeddingProvider):
    """Wraps any :class:`EmbeddingProvider` with read-through cache.

    Cache misses delegate to the underlying provider. ``None`` results
    are NOT persisted so the fallback path stays live across restarts.
    """

    def __init__(
        self,
        underlying: EmbeddingProvider,
        backend: EmbeddingCacheBackend,
    ) -> None:
        self._underlying = underlying
        self._backend = backend

    @property
    def name(self) -> str:
        return f"caching({self._underlying.name})"

    @property
    def dim(self) -> int:
        return self._underlying.dim

    def embed_one(self, text: str) -> list[float] | None:
        if not text or not text.strip():
            return None
        key = text_hash(text)
        cached = self._backend.get(self._underlying.name, key)
        if cached is not None:
            return cached
        vec = self._underlying.embed_one(text)
        if vec is None:
            return None
        self._backend.put(self._underlying.name, key, vec)
        return vec

    def embed_many(self, texts: list[str]) -> list[list[float] | None]:
        return [self.embed_one(t) for t in texts]

    @property
    def stats(self) -> CacheStats:
        """Pass-through to the cache backend stats."""
        return self._backend.stats()


__all__ = [
    "CacheStats",
    "CachingEmbeddingProvider",
    "EmbeddingCacheBackend",
    "HASH_KEY_LEN",
    "SqliteEmbeddingCache",
    "text_hash",
]
