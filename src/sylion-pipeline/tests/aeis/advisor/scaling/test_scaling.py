"""Tests for AEIS Advisor — Scaling module.

Scenarios per manifest §7:
- local_only_recommended_for_small_workload
- vps_recommended_for_high_workload
- multi_vps_d3_min_with_evidence_pack
- staging_plan_phases_environments_correctly
"""

from __future__ import annotations

import pytest

from sylion.aeis.advisor.scaling.topology_recommender import recommend_topology
from sylion.aeis.advisor.scaling.staging_planner import propose_staging_plan
from sylion.aeis.advisor.scaling.env_inventory import register_env, get_env_inventory
from sylion.aeis.advisor.scaling.service import get_scaling_service


class TestLocalOnlySmallWorkload:
    """local_only_recommended_for_small_workload"""

    def test_small_workload_local(self):
        card = recommend_topology("op1", {
            "estimated_tokens_per_day": 50_000,
            "parallelism": 1,
            "latency_target_seconds": 5.0,
        })
        assert card.recommended == "local_only"
        assert card.d_level == "D2"


class TestVpsForHighWorkload:
    """vps_recommended_for_high_workload"""

    def test_high_tokens_vps(self):
        card = recommend_topology("op2", {
            "estimated_tokens_per_day": 500_000,
            "parallelism": 2,
            "latency_target_seconds": 3.0,
        })
        assert card.recommended == "local_plus_vps"
        assert card.d_level == "D3"


class TestMultiVpsD3Min:
    """multi_vps_d3_min_with_evidence_pack"""

    def test_multi_vps_high_parallel(self):
        card = recommend_topology("op3", {
            "estimated_tokens_per_day": 2_000_000,
            "parallelism": 5,
            "latency_target_seconds": 2.0,
        })
        assert card.recommended == "multi_vps"
        assert card.d_level in ("D3", "D4", "D5")
        assert card.evidence_pack_id is not None
        assert card.human_gate_required is True


class TestStagingPlan:
    """staging_plan_phases_environments_correctly"""

    def test_scale_up_phases(self):
        plan = propose_staging_plan("local_only", "multi_vps")
        assert len(plan.phases) == 3
        topologies = [p["topology"] for p in plan.phases]
        assert topologies == ["local_plus_vps", "vps_only", "multi_vps"]

    def test_scale_down_phases(self):
        plan = propose_staging_plan("multi_vps", "local_only")
        assert len(plan.phases) == 3
        actions = [p["action"] for p in plan.phases]
        assert all(a == "decommission_env" for a in actions)

    def test_service_propose_staging(self):
        svc = get_scaling_service()
        plan = svc.propose_staging_plan("local_only", "local_plus_vps")
        assert len(plan.phases) == 1
        assert plan.phases[0]["topology"] == "local_plus_vps"

    def test_env_inventory(self):
        register_env({
            "env_id": "env1",
            "operator_id": "op4",
            "name": "prod-vps-1",
            "kind": "vps",
            "capacity_tokens_per_day": 1_000_000,
        })
        envs = get_env_inventory("op4")
        assert len(envs) == 1
        assert envs[0].name == "prod-vps-1"
