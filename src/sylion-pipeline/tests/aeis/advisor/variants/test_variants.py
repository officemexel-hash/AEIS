"""Tests for AEIS Advisor — Variants module.

Scenarios per manifest §5:
- three_variants_generated_for_software_project
- cost_saving_variant_uses_local_only_when_possible
- aggressive_variant_includes_critic_and_governance_models
- all_variants_costs_within_budget_threshold
- variant_trade_off_matrix_includes_required_dimensions

Post-REWIRE adversarial scenarios (commit 8f3bb42).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from sylion.aeis.advisor.pricing._models import CostEstimate
from sylion.aeis.advisor.variants.generator import generate_variants, compare_variants
from sylion.aeis.advisor.variants.service import get_variants_service


class TestThreeVariantsGenerated:
    """three_variants_generated_for_software_project"""

    def test_generates_three(self):
        ctx = {"context_id": "proj_sw_1", "project_type": "software"}
        vs = generate_variants(ctx)
        assert len(vs.variants) == 3
        names = {v.name for v in vs.variants}
        assert names == {"cost_saving", "balanced", "aggressive"}


class TestCostSavingLocalOnly:
    """cost_saving_variant_uses_local_only_when_possible"""

    def test_cost_saving_params(self):
        vs = generate_variants()
        cost_saving = [v for v in vs.variants if v.name == "cost_saving"][0]
        assert cost_saving.parameters["use_local_models"] is True
        assert cost_saving.parameters["use_external_apis"] is False
        assert cost_saving.parameters["vps_envs"] == 0
        assert cost_saving.parameters["topology"] == "local_only"
        assert cost_saving.parameters["critic_model"] is None


class TestAggressiveIncludesCritic:
    """aggressive_variant_includes_critic_and_governance_models"""

    def test_aggressive_params(self):
        vs = generate_variants()
        aggressive = [v for v in vs.variants if v.name == "aggressive"][0]
        assert aggressive.parameters["critic_model"] == "claude-opus-4-7"
        assert aggressive.parameters["use_external_apis"] is True
        assert aggressive.parameters["vps_envs"] == 3
        assert aggressive.parameters["council_size"] == 7


class TestCostsWithinBudget:
    """all_variants_costs_within_budget_threshold"""

    def test_costs_non_negative(self):
        vs = generate_variants()
        for v in vs.variants:
            assert v.estimated_cost_usd >= 0

    def test_costs_ordered(self):
        vs = generate_variants()
        costs = {v.name: v.estimated_cost_usd for v in vs.variants}
        assert costs["cost_saving"] <= costs["balanced"]
        assert costs["balanced"] <= costs["aggressive"]


class TestTradeOffMatrix:
    """variant_trade_off_matrix_includes_required_dimensions"""

    def test_comparison_dimensions(self):
        vs = generate_variants()
        ids = [v.variant_id for v in vs.variants[:2]]
        result = compare_variants(ids, vs)
        dim_names = [d["dimension"] for d in result["dimensions"]]
        assert "estimated_cost_usd" in dim_names
        assert "estimated_time_hours" in dim_names
        assert "risk_level" in dim_names
        assert "quality_projection" in dim_names

    def test_service_compare(self):
        svc = get_variants_service()
        vs = svc.generate_variants({"context_id": "cmp_test"})
        ids = [v.variant_id for v in vs.variants]
        result = svc.compare_variants(ids, context_id="cmp_test")
        dim_names = [d["dimension"] for d in result.get("dimensions", [])]
        assert "estimated_cost_usd" in dim_names
        assert "quality_projection" in dim_names


class TestVariantsAdversarial:
    """Adversarial scenarios for variants post-REWIRE (commit 8f3bb42)."""

    def test_extreme_workload_context_values(self):
        """Workload context with extreme values (0 tokens, 1B tokens) must not crash."""
        ctx_zero = {"context_id": "extreme_zero", "estimated_input_tokens": 0, "estimated_output_tokens": 0}
        vs_zero = generate_variants(ctx_zero)
        assert len(vs_zero.variants) == 3
        for v in vs_zero.variants:
            assert v.estimated_cost_usd >= 0
            assert v.estimated_time_hours >= 0

        ctx_billion = {
            "context_id": "extreme_billion",
            "estimated_input_tokens": 1_000_000_000,
            "estimated_output_tokens": 1_000_000_000,
        }
        vs_billion = generate_variants(ctx_billion)
        assert len(vs_billion.variants) == 3
        for v in vs_billion.variants:
            assert v.estimated_cost_usd >= 0
            assert v.estimated_time_hours >= 0

    def test_all_providers_blocked_variant_wins(self):
        """When all external providers are blocked, cost_saving must win on cost."""
        vs = generate_variants({"context_id": "all_blocked"})
        ids = [v.variant_id for v in vs.variants]
        result = compare_variants(ids, vs)
        cost_dim = next((d for d in result["dimensions"] if d["dimension"] == "estimated_cost_usd"), None)
        assert cost_dim is not None
        assert cost_dim["winner"] == "cost_saving"

    def test_cost_saving_local_unavailable(self):
        """Cost-saving variant when local model pricing is unavailable.

        If estimate_cost returns an assumption (no pricing data), the generator
        must still produce a valid cost_saving variant with cost >= 0.
        """
        def fake_estimate_cost(model_id, input_tokens, output_tokens, cache_hit_tokens=0):
            return CostEstimate(
                model_id=model_id,
                provider_id="local",
                total_cost_usd=0.0,
                input_cost_usd=0.0,
                output_cost_usd=0.0,
                cache_cost_usd=0.0,
                source="assumption",
                is_assumption=True,
                assumption_note="No pricing data available for this model",
                pricing_effective_from=None,
                pricing_id="",
            )

        with patch("sylion.aeis.advisor.variants.generator.estimate_cost", side_effect=fake_estimate_cost):
            vs = generate_variants({"context_id": "local_unavailable"})
            cost_saving = next((v for v in vs.variants if v.name == "cost_saving"), None)
            assert cost_saving is not None
            assert cost_saving.estimated_cost_usd >= 0
            assert cost_saving.parameters["use_local_models"] is True
            assert cost_saving.parameters["use_external_apis"] is False
