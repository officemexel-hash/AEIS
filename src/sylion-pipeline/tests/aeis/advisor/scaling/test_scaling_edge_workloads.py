"""Edge-case tests for AEIS Advisor — Scaling.

0 tokens, 1_000_000_000 tokens, negative values, missing keys.
"""

from __future__ import annotations

import pytest

from sylion.aeis.advisor.scaling.topology_recommender import recommend_topology
from sylion.aeis.advisor.scaling.service import get_scaling_service


class TestScalingEdgeWorkloads:
    """Extreme and malformed workload profiles."""

    # 1. Zero tokens --------------------------------------------------------
    def test_zero_tokens_local_only(self):
        card = recommend_topology("op_z", {
            "estimated_tokens_per_day": 0,
            "parallelism": 1,
        })
        assert card.recommended == "local_only"
        assert card.d_level == "D2"

    # 2. One billion tokens -------------------------------------------------
    def test_billion_tokens_vps_or_multi(self):
        card = recommend_topology("op_b", {
            "estimated_tokens_per_day": 1_000_000_000,
            "parallelism": 1,
        })
        assert card.recommended in ("vps_only", "multi_vps")
        assert card.d_level in ("D3", "D4")

    # 3. Negative tokens ----------------------------------------------------
    def test_negative_tokens_coerced_to_zero(self):
        card = recommend_topology("op_neg", {
            "estimated_tokens_per_day": -500_000,
            "parallelism": 1,
        })
        assert card.recommended == "local_only"

    # 4. Negative parallelism -----------------------------------------------
    def test_negative_parallelism_coerced_to_one(self):
        card = recommend_topology("op_np", {
            "estimated_tokens_per_day": 50_000,
            "parallelism": -5,
        })
        assert card.recommended == "local_only"

    # 5. Zero parallelism ---------------------------------------------------
    def test_zero_parallelism_coerced_to_one(self):
        card = recommend_topology("op_zp", {
            "estimated_tokens_per_day": 50_000,
            "parallelism": 0,
        })
        assert card.recommended == "local_only"

    # 6. None values --------------------------------------------------------
    def test_none_tokens_coerced(self):
        card = recommend_topology("op_nt", {
            "estimated_tokens_per_day": None,
            "parallelism": 1,
        })
        assert card.recommended == "local_only"

    def test_none_parallelism_coerced(self):
        card = recommend_topology("op_np2", {
            "estimated_tokens_per_day": 500_000,
            "parallelism": None,
        })
        assert card.recommended == "local_plus_vps"

    def test_none_latency_coerced(self):
        card = recommend_topology("op_nl", {
            "estimated_tokens_per_day": 50_000,
            "parallelism": 1,
            "latency_target_seconds": None,
        })
        assert card.impacts["latency_estimate_seconds"] == 10.0

    # 7. Empty workload dict ------------------------------------------------
    def test_empty_workload_defaults_to_local(self):
        card = recommend_topology("op_ew", {})
        assert card.recommended == "local_only"
        assert card.d_level == "D2"

    # 8. Extreme parallelism ------------------------------------------------
    def test_extreme_parallelism_multi_vps(self):
        card = recommend_topology("op_ep", {
            "estimated_tokens_per_day": 1_000_000,
            "parallelism": 10_000,
        })
        assert card.recommended == "multi_vps"
        assert card.d_level == "D4"
        assert card.impacts["max_parallelism"] == 10_002

    # 9. Negative latency ---------------------------------------------------
    def test_negative_latency_coerced(self):
        card = recommend_topology("op_nlat", {
            "estimated_tokens_per_day": 50_000,
            "parallelism": 1,
            "latency_target_seconds": -5.0,
        })
        assert card.impacts["latency_estimate_seconds"] == 10.0

    # 10. Boundary at exactly 100k tokens -----------------------------------
    def test_boundary_100k_tokens(self):
        card = recommend_topology("op_100k", {
            "estimated_tokens_per_day": 100_000,
            "parallelism": 1,
        })
        # 100_000 is NOT < 100_000, so falls through to next branch
        assert card.recommended == "local_plus_vps"
        assert card.d_level == "D3"

    # 11. Boundary at exactly 1M tokens -------------------------------------
    def test_boundary_1m_tokens(self):
        card = recommend_topology("op_1m", {
            "estimated_tokens_per_day": 1_000_000,
            "parallelism": 2,
        })
        # 1_000_000 is NOT < 1_000_000, parallelism <= 3 → vps_only
        assert card.recommended == "vps_only"
        assert card.d_level == "D3"

    # 12. Service-level edge case -------------------------------------------
    def test_service_edge_missing_keys(self):
        svc = get_scaling_service()
        card = svc.recommend_topology("op_se", "proj", {})
        assert card.recommended == "local_only"
