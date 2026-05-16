"""PostgreSQL-backed EmbeddingCacheBackend.

Sprint 3 B-pg companion to ``PgUserDataStore`` — production deployments
swap out :class:`SqliteEmbeddingCache` via constructor injection on
``CachingEmbeddingProvider`` and the rest of the system stays
unchanged.

The on-disk schema lives in ``aeis_v2/embeddings/pg_schema.sql`` (commit
``47b54c03``) and uses pgvector for ANN lookup. This Python wrapper
treats the vector column as ``vector(768)`` (the ``nomic-embed-text``
default) but degrades gracefully when ``pgvector`` is unavailable on
the connection — the JSON-encoded fallback path keeps the cache usable
in degraded mode (per Kimi k4 review of pgvector dim-mismatch risk).

Per Kimi k2 / k4 reviews:

* Composite PK ``(text_hash, model)`` so different embedding backends
  share the same table without cross-contamination.
* ``hit_count`` + ``last_hit_at`` updated on every read — write
  amplification mitigated by batching the UPDATE behind a connection
  factory hook (next sprint).
* Module loads safely without ``psycopg`` installed; methods import
  it lazily on first use.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from typing import Any

from sylion.aeis_v2.embeddings.cache import (
    CacheStats,
    EmbeddingCacheBackend,
)

log = logging.getLogger(__name__)

#: Same idempotent DDL referenced from pg_schema.sql — kept here so
#: the production deploy script can run it without parsing the SQL file.
PG_EMBEDDING_DDL: str = """
CREATE TABLE IF NOT EXISTS embedding_cache (
    text_hash    bytea       NOT NULL,
    model        text        NOT NULL,
    vector_json  text        NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    hit_count    bigint      NOT NULL DEFAULT 0,
    last_hit_at  timestamptz,
    PRIMARY KEY (text_hash, model)
);
CREATE INDEX IF NOT EXISTS embedding_cache_last_hit_at_idx
    ON embedding_cache (last_hit_at)
    WHERE last_hit_at IS NOT NULL;
"""


class PgEmbeddingCache(EmbeddingCacheBackend):
    """psycopg-backed cache compatible with :class:`CachingEmbeddingProvider`.

    Differences from :class:`SqliteEmbeddingCache`:

    * Composite PK ``(text_hash::bytea, model::text)`` — bytea uses 8
      bytes for a sha256-trunc key vs sqlite's 16-char hex string.
    * Vector stored as JSON in ``vector_json text`` for the in-Python
      fallback. Production deployments that have ``pgvector`` installed
      can layer the ``vector(768)`` column on top via a separate
      migration; this module ignores it (read-through stays correct).
    * ``last_hit_at`` updated only on cache hits — preserves the
      eviction signal for the AuditRotator.
    """

    def __init__(
        self,
        dsn: str | None = None,
        *,
        connection_factory: Any | None = None,
    ) -> None:
        self._dsn = dsn
        self._connection_factory = connection_factory
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._init_done = False

    # ------------------------------------------------------------------
    # Connection plumbing
    # ------------------------------------------------------------------

    def _get_connection(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()
        import psycopg  # type: ignore[import-not-found]

        return psycopg.connect(self._dsn)

    def ensure_schema(self) -> None:
        with self._lock:
            if self._init_done:
                return
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(PG_EMBEDDING_DDL)
                conn.commit()
            self._init_done = True

    # ------------------------------------------------------------------
    # EmbeddingCacheBackend interface
    # ------------------------------------------------------------------

    @staticmethod
    def _key_to_bytea(key: str) -> bytes:
        """Cache key (16-char hex from cache.text_hash) → 8-byte bytea."""
        # The CachingEmbeddingProvider passes 16-char hex strings; we
        # decode to bytes for the bytea PK column.
        try:
            return bytes.fromhex(key)
        except ValueError:
            # Defensive fallback: treat as utf-8 then hash.
            return hashlib.sha256(key.encode("utf-8")).digest()[:8]

    def get(self, model: str, key: str) -> list[float] | None:
        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT vector_json FROM embedding_cache "
                        "WHERE text_hash = %s AND model = %s",
                        (self._key_to_bytea(key), model),
                    )
                    row = cur.fetchone()
                    if row is None:
                        self._misses += 1
                        return None
                    raw = (
                        row[0] if not isinstance(row, dict)
                        else row.get("vector_json")
                    )
                    try:
                        vec = json.loads(raw) if isinstance(raw, str) else raw
                    except json.JSONDecodeError:
                        self._misses += 1
                        return None
                    if not isinstance(vec, list):
                        self._misses += 1
                        return None
                    cur.execute(
                        "UPDATE embedding_cache "
                        "SET hit_count = hit_count + 1, last_hit_at = now() "
                        "WHERE text_hash = %s AND model = %s",
                        (self._key_to_bytea(key), model),
                    )
                conn.commit()
        self._hits += 1
        return vec

    def put(self, model: str, key: str, vector: list[float]) -> None:
        if not vector:
            return
        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO embedding_cache
                            (text_hash, model, vector_json, last_hit_at)
                        VALUES (%s, %s, %s, NULL)
                        ON CONFLICT (text_hash, model) DO UPDATE
                            SET vector_json = EXCLUDED.vector_json,
                                last_hit_at = NULL
                        """,
                        (
                            self._key_to_bytea(key),
                            model,
                            json.dumps(vector, separators=(",", ":")),
                        ),
                    )
                conn.commit()

    def stats(self) -> CacheStats:
        with self._lock:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM embedding_cache")
                    row = cur.fetchone()
        size = (
            int(row[0]) if row and not isinstance(row, dict)
            else int(row.get("count", 0)) if row else 0
        )
        return CacheStats(hits=self._hits, misses=self._misses, size=size)

    def reset_counters(self) -> None:
        with self._lock:
            self._hits = 0
            self._misses = 0


__all__ = [
    "PG_EMBEDDING_DDL",
    "PgEmbeddingCache",
]
