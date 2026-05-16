"""Perf test conftest — installs SQLite-backed PG pool shim.

Perf benchmarks run against the in-memory SQLite shim so they don't require
a live PG schema for subscription_usage / scaling_envs.
"""
from __future__ import annotations

import pytest

# F-011: requires PostgreSQL — auto-skipped by tests/conftest.py if PG not reachable.
pytestmark = pytest.mark.requires_postgres

from tests.aeis.advisor.engine._pg_test_pool import install_test_pool


_PERF_SCHEMA_SQLITE = """
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

CREATE TABLE scaling_envs (
  env_id TEXT PRIMARY KEY,
  operator_id TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL DEFAULT '',
  capacity_tokens_per_day INTEGER NOT NULL DEFAULT 0,
  registered_at REAL NOT NULL DEFAULT 0
);

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

CREATE TABLE advisor_preferences_preferences (
  user_id TEXT NOT NULL,
  project_type TEXT,
  project_domain TEXT,
  preference_key TEXT NOT NULL,
  preference_value TEXT,
  set_by TEXT NOT NULL DEFAULT 'system',
  created_at REAL NOT NULL DEFAULT 0,
  updated_at REAL NOT NULL DEFAULT 0
);

CREATE TABLE advisor_preferences_preference_key_catalog (
  preference_key TEXT PRIMARY KEY,
  display_name TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  value_schema TEXT NOT NULL DEFAULT '{}',
  default_value TEXT,
  is_hard_change INTEGER NOT NULL DEFAULT 0
);
"""

_PRICING_REWRITES: dict[str, str] = {
    "advisor_pricing.pricing_tables": "advisor_pricing_pricing_tables",
    "advisor_pricing.provider_models": "advisor_pricing_provider_models",
    "advisor_preferences.preferences": "advisor_preferences_preferences",
    "advisor_preferences.preference_key_catalog": "advisor_preferences_preference_key_catalog",
}


@pytest.fixture(scope="module", autouse=True)
def _perf_pg_pool():
    monkeypatch = pytest.MonkeyPatch()
    pool = install_test_pool(monkeypatch)

    from tests.aeis.advisor.engine import _pg_test_pool as shim
    original_translate = shim.translate_query

    def _translate_with_rewrites(query: str) -> str:
        out = original_translate(query)
        for fq, flat in _PRICING_REWRITES.items():
            out = out.replace(fq, flat)
        return out

    monkeypatch.setattr(shim, "translate_query", _translate_with_rewrites)

    pool._conn.executescript(_PERF_SCHEMA_SQLITE)
    pool._conn.commit()

    # Seed pricing data for benchmarks
    pool._conn.executemany(
        "INSERT INTO advisor_pricing_provider_models (model_id, provider_id, display_name, context_window, is_local, capabilities, is_default_judge, is_default_local, is_deprecated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("claude-sonnet-4-6", "anthropic", "Claude Sonnet 4.6", 200000, 0, '["chat"]', 0, 0, 0),
            ("claude-opus-4-7", "anthropic", "Claude Opus 4.7", 200000, 0, '["chat"]', 0, 0, 0),
            ("qwen2.5:72b-instruct", "local", "Qwen 2.5 72B Instruct", 32768, 1, '["chat"]', 0, 1, 0),
            ("qwen2.5:7b-instruct", "local", "Qwen 2.5 7B Instruct", 32768, 1, '["chat"]', 0, 0, 0),
        ],
    )
    pool._conn.executemany(
        "INSERT INTO advisor_pricing_pricing_tables (pricing_id, model_id, input_tokens_usd_per_million, output_tokens_usd_per_million, cache_hit_tokens_usd_per_million, source, source_url, is_assumption, assumption_note, effective_from, effective_until) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("price-1", "claude-sonnet-4-6", 3.0, 15.0, 1.5, "measured", "", 0, "", 0, None),
            ("price-2", "claude-opus-4-7", 15.0, 75.0, 7.5, "measured", "", 0, "", 0, None),
            ("price-3", "qwen2.5:72b-instruct", 0.0, 0.0, 0.0, "measured", "", 0, "", 0, None),
            ("price-4", "qwen2.5:7b-instruct", 0.0, 0.0, 0.0, "measured", "", 0, "", 0, None),
        ],
    )
    pool._conn.executemany(
        "INSERT INTO advisor_preferences_preference_key_catalog (preference_key, display_name, description, value_schema, default_value, is_hard_change) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("blocked_providers", "Blocked providers", "", "{}", "[]", 0),
            (
                "cost_ceilings",
                "Cost ceilings",
                "",
                "{}",
                '{"low": 6.0, "medium": 6.0, "high": 6.0, "critical": 6.0}',
                0,
            ),
            ("llm_judge_routing_override", "Judge routing override", "", "{}", "{}", 0),
        ],
    )
    pool._conn.commit()

    yield pool

    pool.close()
    monkeypatch.undo()
