-- SYLION AEIS v2 — embeddings cache PostgreSQL schema (sprint 2 day 4).
--
-- Mirror of the SQLite reference schema in cache.py.
-- The vector column uses pgvector for HNSW indexing of similarity queries
-- (currently the cache is keyed by sha256 hash, but down the road we expect
-- to add ANN lookup over near-duplicate inputs).
--
-- Deployment prereq:
--     CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector >= 0.5
--
-- ADR-001 #5 (W7→W13 hybrid) — 4-layer fallback: pg cache → ollama →
-- jaccard tag overlap → static demo set. The pg layer is layer 1.

CREATE TABLE IF NOT EXISTS embedding_cache (
    text_hash    bytea       NOT NULL,                       -- sha256 trunc 8 bytes
    model        text        NOT NULL,                       -- e.g. ollama:nomic-embed-text
    vector       vector(768) NOT NULL,                       -- pgvector
    created_at   timestamptz NOT NULL DEFAULT now(),
    hit_count    bigint      NOT NULL DEFAULT 0,
    last_hit_at  timestamptz,
    PRIMARY KEY (text_hash, model)
);

-- HNSW index for ANN lookup. Cosine ops to match the in-process helper.
CREATE INDEX IF NOT EXISTS embedding_cache_hnsw_cosine_idx
    ON embedding_cache USING hnsw (vector vector_cosine_ops);

-- Eviction support — last_hit_at lets us TTL prune cold rows.
CREATE INDEX IF NOT EXISTS embedding_cache_last_hit_at_idx
    ON embedding_cache (last_hit_at)
    WHERE last_hit_at IS NOT NULL;

-- Audit trail (append-only). Keeps cache decisions visible to the
-- governance layer without forcing every reader to walk JSONL.
CREATE TABLE IF NOT EXISTS embedding_audit (
    event_id    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    text_hash   bytea       NOT NULL,
    model       text        NOT NULL,
    action      varchar(16) NOT NULL CHECK (action IN ('hit','miss','put','evict')),
    occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS embedding_audit_occurred_at_idx
    ON embedding_audit (occurred_at);

-- Materialized view: hit-rate dashboard — refreshed nightly by the
-- cost_ledger refresher (charter W17 §4 evidence spine).
CREATE MATERIALIZED VIEW IF NOT EXISTS embedding_cache_hit_rate_24h AS
    SELECT
        model,
        COUNT(*) FILTER (WHERE action = 'hit')  AS hits,
        COUNT(*) FILTER (WHERE action = 'miss') AS misses,
        COUNT(*)                                 AS total,
        CASE WHEN COUNT(*) = 0 THEN 0
             ELSE COUNT(*) FILTER (WHERE action = 'hit')::float / COUNT(*)
        END                                      AS hit_rate
    FROM embedding_audit
    WHERE occurred_at > now() - interval '24 hours'
    GROUP BY model;

CREATE UNIQUE INDEX IF NOT EXISTS embedding_cache_hit_rate_24h_pk
    ON embedding_cache_hit_rate_24h (model);
