"""Integration tests for scaling → Codex pricing/preferences + Claude engine.

Pricing-dependent test is active.
Preferences-, engine-, and PG-migration-dependent tests remain skipped.
"""

from __future__ import annotations

import pytest


def test_topology_recommendation_uses_real_pricing_for_vps_cost():
    """Test Codex pricing.estimator feeds VPS cost into scaling impacts.

    Exercises: sylion.aeis.advisor.pricing.estimator (Codex Phase 2)
    """
    from sylion.aeis.advisor.pricing.estimator import estimate_cost
    from sylion.aeis.advisor.scaling.service import get_scaling_service

    svc = get_scaling_service()
    est = estimate_cost("claude-opus-4-7", 2000, 1000)
    assert float(est.total_cost_usd) > 0.0

    card = svc.recommend_topology(
        "op_tp", "proj",
        {"estimated_tokens_per_day": 500_000, "parallelism": 2}
    )
    assert card.impacts["monthly_cost_usd"] >= 20.0


@pytest.mark.skip(reason="awaiting preferences→scaling wiring")
def test_staging_plan_respects_operator_preference_runtime_strategy():
    """Test Codex preferences override default staging strategy.

    Exercises: sylion.aeis.advisor.preferences (Codex Phase 2)
    Unskip after: scaling service reads preferences resolver directly.
    """
    from sylion.aeis.advisor.preferences import get_preferences
    from sylion.aeis.advisor.scaling.service import get_scaling_service

    svc = get_scaling_service()
    get_preferences().set_preference(
        user_id="00000000-0000-0000-0000-000000000001",
        project_type=None,
        project_domain=None,
        preference_key="runtime_strategy",
        value="blue_green",
    )
    plan = svc.propose_staging_plan("local_only", "multi_vps")
    # Preference should influence staging action naming if wired
    assert len(plan.phases) == 3


@pytest.mark.skip(reason="awaiting Claude engine creator")
def test_multi_vps_d3_evidence_pack_via_real_engine_creator():
    """Test Claude engine creator injects evidence pack into D3 scaling card.

    Exercises: sylion.aeis.advisor.engine.creator (Claude engine)
    """
    from sylion.aeis.advisor.engine.creator import EngineCreator
    from sylion.aeis.advisor.scaling.service import get_scaling_service

    svc = get_scaling_service()
    card = svc.recommend_topology(
        "op_eng", "proj",
        {"estimated_tokens_per_day": 2_000_000, "parallelism": 5}
    )
    assert card.d_level in ("D3", "D4", "D5")
    assert card.evidence_pack_id is not None

    # If engine creator is present, it should validate evidence pack
    creator = EngineCreator()
    validated = creator.validate_card(card.to_dict())
    assert validated["evidence_pack_present"] is True


@pytest.mark.skip(reason="awaiting Codex PG migration for scaling_envs")
def test_env_inventory_persisted_with_real_pg_connection_pool():
    """Test scaling envs persist through real PG connection pool.

    Exercises: sylion.aeis.advisor._db.get_pool (Codex PG migration)
    """
    from sylion.aeis.advisor._db import get_pool
    from sylion.aeis.advisor.scaling.service import get_scaling_service

    svc = get_scaling_service()
    # Register env through service
    svc.register_env({
        "env_id": "env_pg_1",
        "operator_id": "op_pg",
        "name": "prod-pg",
        "kind": "vps",
        "capacity_tokens_per_day": 1_000_000,
    })

    # Query directly via PG pool to verify cross-layer persistence
    pool = get_pool()
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT name FROM scaling_envs WHERE env_id = %s",
            ("env_pg_1",)
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "prod-pg"
