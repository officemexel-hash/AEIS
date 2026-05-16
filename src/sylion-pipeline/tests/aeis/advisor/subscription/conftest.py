"""Subscription test conftest — installs SQLite-backed PG pool shim and seeds schema.

Per 08_audit_revisions.md Revision 2 the subscription module is PG-only in
production. Tests use an in-memory SQLite-backed shim of the shared PG pool;
schema is recreated per-test for isolation.
"""
from __future__ import annotations

import pytest

# F-011: requires PostgreSQL — auto-skipped by tests/conftest.py if PG not reachable.
pytestmark = pytest.mark.requires_postgres

from tests.aeis.advisor.engine._pg_test_pool import install_test_pool


_SUBSCRIPTION_TEST_SCHEMA_SQLITE = """
CREATE TABLE subscription_usage (
  record_id TEXT PRIMARY KEY,
  operator_id TEXT NOT NULL,
  provider_id TEXT NOT NULL DEFAULT '',
  model_id TEXT NOT NULL DEFAULT '',
  tokens_in INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0,
  cost_usd REAL NOT NULL DEFAULT 0.0,
  timestamp REAL NOT NULL DEFAULT 0
);

CREATE TABLE subscription_plans (
  plan_id TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL DEFAULT '',
  monthly_price_usd REAL NOT NULL DEFAULT 0.0,
  included_tokens INTEGER NOT NULL DEFAULT 0,
  rate_limits TEXT NOT NULL DEFAULT '{}',
  is_assumption INTEGER NOT NULL DEFAULT 0,
  source_url TEXT NOT NULL DEFAULT ''
);

CREATE TABLE subscription_custom_plans (
  plan_id TEXT PRIMARY KEY,
  operator_id TEXT NOT NULL,
  plan_data TEXT NOT NULL DEFAULT '{}',
  created_at REAL NOT NULL DEFAULT 0
);

-- Pricing tables needed by integration tests calling estimate_cost
CREATE TABLE advisor_pricing_pricing_tables (
  pricing_id TEXT PRIMARY KEY,
  model_id TEXT NOT NULL,
  input_tokens_usd_per_million REAL,
  output_tokens_usd_per_million REAL,
  cache_hit_tokens_usd_per_million REAL,
  source TEXT NOT NULL,
  source_url TEXT,
  is_assumption INTEGER NOT NULL DEFAULT 0,
  assumption_note TEXT,
  effective_from REAL NOT NULL,
  effective_until REAL
);

CREATE TABLE advisor_pricing_provider_models (
  model_id TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL,
  display_name TEXT,
  context_window INTEGER,
  is_local INTEGER NOT NULL DEFAULT 0,
  capabilities TEXT NOT NULL DEFAULT '[]',
  is_default_judge INTEGER NOT NULL DEFAULT 0,
  is_default_local INTEGER NOT NULL DEFAULT 0,
  is_deprecated INTEGER NOT NULL DEFAULT 0
);
"""

_PRICING_REWRITES: dict[str, str] = {
    "advisor_pricing.pricing_tables": "advisor_pricing_pricing_tables",
    "advisor_pricing.provider_models": "advisor_pricing_provider_models",
}


@pytest.fixture(autouse=True)
def _subscription_pg_pool(monkeypatch):
    from sylion.aeis.advisor.subscription.service import reset_subscription_service

    reset_subscription_service()
    pool = install_test_pool(monkeypatch)

    # Patch query translator for pricing schema-qualified names
    from tests.aeis.advisor.engine import _pg_test_pool as shim
    original_translate = shim.translate_query

    def _translate_with_rewrites(query: str) -> str:
        out = original_translate(query)
        for fq, flat in _PRICING_REWRITES.items():
            out = out.replace(fq, flat)
        return out

    monkeypatch.setattr(shim, "translate_query", _translate_with_rewrites)

    pool._conn.executescript(_SUBSCRIPTION_TEST_SCHEMA_SQLITE)
    pool._conn.commit()

    # Seed test pricing data used by integration tests
    pool._conn.execute(
        "INSERT INTO advisor_pricing_provider_models (model_id, provider_id, display_name, context_window, is_local, capabilities, is_default_judge, is_default_local, is_deprecated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("claude-sonnet-4-6", "anthropic", "Claude Sonnet 4.6", 200000, 0, '["chat"]', 0, 0, 0),
    )
    pool._conn.execute(
        "INSERT INTO advisor_pricing_pricing_tables (pricing_id, model_id, input_tokens_usd_per_million, output_tokens_usd_per_million, cache_hit_tokens_usd_per_million, source, source_url, is_assumption, assumption_note, effective_from, effective_until) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("price-1", "claude-sonnet-4-6", 3.0, 15.0, 1.5, "measured", "", 0, "", 0, None),
    )
    pool._conn.commit()

    yield pool
    pool.close()
    reset_subscription_service()
