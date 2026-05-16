"""AEIS Advisor — Topology recommender."""

from __future__ import annotations

from typing import Any

from sylion.aeis.advisor.scaling._models import ScalingCard


def recommend_topology(
    operator_id: str,
    workload: dict[str, Any],
) -> ScalingCard:
    """Recommend topology based on workload profile."""
    estimated_tokens_per_day = workload.get("estimated_tokens_per_day", 0)
    parallelism = workload.get("parallelism", 1)
    latency_target = workload.get("latency_target_seconds", 10.0)

    # Defensive: coerce None / negatives to safe defaults
    if estimated_tokens_per_day is None or estimated_tokens_per_day < 0:
        estimated_tokens_per_day = 0
    if parallelism is None or parallelism < 1:
        parallelism = 1
    if latency_target is None or latency_target <= 0:
        latency_target = 10.0

    if estimated_tokens_per_day < 100_000 and parallelism == 1:
        recommended = "local_only"
        d_level = "D2"
        alternatives = ["local_plus_vps"]
        impacts = {
            "monthly_cost_usd": 0,
            "max_parallelism": 1,
            "latency_estimate_seconds": latency_target,
        }
    elif estimated_tokens_per_day < 1_000_000:
        recommended = "local_plus_vps"
        d_level = "D3"
        alternatives = ["local_only", "multi_vps"]
        impacts = {
            "monthly_cost_usd": 20,
            "max_parallelism": 2,
            "latency_estimate_seconds": latency_target * 0.8,
        }
    elif parallelism > 3:
        recommended = "multi_vps"
        d_level = "D4"
        alternatives = ["local_plus_vps", "vps_only"]
        impacts = {
            "monthly_cost_usd": 60,
            "max_parallelism": parallelism + 2,
            "latency_estimate_seconds": latency_target * 0.5,
        }
    else:
        recommended = "vps_only"
        d_level = "D3"
        alternatives = ["local_plus_vps", "multi_vps"]
        impacts = {
            "monthly_cost_usd": 40,
            "max_parallelism": 3,
            "latency_estimate_seconds": latency_target * 0.7,
        }

    human_gate = d_level in ("D3", "D4", "D5")
    evidence_pack = f"evp_scaling_{recommended}" if human_gate else None

    return ScalingCard(
        operator_id=operator_id,
        project_id=workload.get("project_id", ""),
        recommended=recommended,
        alternatives=alternatives,
        d_level=d_level,
        evidence_pack_id=evidence_pack,
        human_gate_required=human_gate,
        impacts=impacts,
    )
