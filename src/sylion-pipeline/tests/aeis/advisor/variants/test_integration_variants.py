"""Integration tests for variants → Codex preferences/pricing.

Tests depending only on Codex Phase 2 pricing are active.
Tests needing preferences wiring into variants remain skipped.
"""

from __future__ import annotations

import pytest


def test_generate_with_real_pricing_estimates_costs():
    """Test Codex pricing.estimator feeds real costs into variant generation.

    Exercises: sylion.aeis.advisor.pricing.estimator (Codex Phase 2)
    """
    from sylion.aeis.advisor.pricing.estimator import estimate_cost
    from sylion.aeis.advisor.variants.service import get_variants_service

    svc = get_variants_service()
    # Ensure real pricing returns non-zero for external models
    est = estimate_cost("claude-sonnet-4-6", 1500, 750)
    assert float(est.total_cost_usd) > 0.0

    vs = svc.generate_variants({"context_id": "int_pricing"})
    for v in vs.variants:
        assert v.estimated_cost_usd >= 0.0
    aggressive = [v for v in vs.variants if v.name == "aggressive"][0]
    assert aggressive.estimated_cost_usd > 0.0


@pytest.mark.skip(reason="awaiting preferences→variants wiring")
def test_aggressive_variant_uses_real_council_size_preference():
    """Test Codex preferences override council_size in aggressive variant.

    Exercises: sylion.aeis.advisor.preferences (Codex Phase 2)
    Unskip after: variants generator reads preferences resolver directly.
    """
    from sylion.aeis.advisor.preferences import get_preferences
    from sylion.aeis.advisor.variants.service import get_variants_service

    svc = get_variants_service()
    get_preferences().set_preference(
        user_id="00000000-0000-0000-0000-000000000001",
        project_type=None,
        project_domain=None,
        preference_key="council_size",
        value=9,
    )
    vs = svc.generate_variants({"context_id": "int_council"})
    aggressive = [v for v in vs.variants if v.name == "aggressive"][0]
    assert aggressive.parameters["council_size"] == 9


@pytest.mark.skip(reason="awaiting preferences→variants wiring")
def test_cost_saving_variant_respects_blocked_providers():
    """Test blocked providers preference forces cost-saving to stay local-only.

    Exercises: sylion.aeis.advisor.preferences (Codex Phase 2)
    Unskip after: variants generator reads preferences resolver directly.
    """
    from sylion.aeis.advisor.preferences import get_preferences
    from sylion.aeis.advisor.variants.service import get_variants_service

    svc = get_variants_service()
    get_preferences().set_preference(
        user_id="00000000-0000-0000-0000-000000000002",
        project_type=None,
        project_domain=None,
        preference_key="blocked_providers",
        value=["anthropic", "openai", "google"],
        bypass_hard_check=True,
    )
    vs = svc.generate_variants({"context_id": "int_block"})
    cost_saving = [v for v in vs.variants if v.name == "cost_saving"][0]
    assert cost_saving.parameters["use_external_apis"] is False


@pytest.mark.skip(reason="awaiting preferences→variants wiring")
def test_variant_recommendations_within_budget_threshold_preference():
    """Test budget ceiling preference limits all variant costs.

    Exercises: sylion.aeis.advisor.preferences (Codex Phase 2)
    Unskip after: variants generator reads preferences resolver directly.
    """
    from sylion.aeis.advisor.preferences import get_preferences
    from sylion.aeis.advisor.variants.service import get_variants_service

    svc = get_variants_service()
    get_preferences().set_preference(
        user_id="00000000-0000-0000-0000-000000000003",
        project_type=None,
        project_domain=None,
        preference_key="cost_ceilings",
        value={"low": 0.5, "medium": 0.5, "high": 0.5, "critical": 0.5},
    )
    vs = svc.generate_variants({"context_id": "int_budget"})
    for v in vs.variants:
        assert v.estimated_cost_usd <= 1.0, f"{v.name} exceeds budget preference"
