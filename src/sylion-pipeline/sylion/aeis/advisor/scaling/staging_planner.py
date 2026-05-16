"""AEIS Advisor — Staging planner."""

from __future__ import annotations

from typing import Any

from sylion.aeis.advisor.scaling._models import StagingPlan


TOPOLOGY_ORDER = ["local_only", "local_plus_vps", "vps_only", "multi_vps"]


def propose_staging_plan(
    current_topology: str,
    target_topology: str,
) -> StagingPlan:
    """Propose a phased staging plan between topologies."""
    plan = StagingPlan(
        current_topology=current_topology,
        target_topology=target_topology,
    )

    if current_topology == target_topology:
        plan.phases.append({
            "phase": 1,
            "action": "no_change",
            "description": "Current and target topology are the same",
        })
        return plan

    # Determine direction
    current_idx = TOPOLOGY_ORDER.index(current_topology) if current_topology in TOPOLOGY_ORDER else -1
    target_idx = TOPOLOGY_ORDER.index(target_topology) if target_topology in TOPOLOGY_ORDER else -1

    if current_idx < target_idx:
        # Scale up
        phase_num = 1
        for topo in TOPOLOGY_ORDER[current_idx + 1:target_idx + 1]:
            plan.phases.append({
                "phase": phase_num,
                "action": "deploy_env",
                "topology": topo,
                "description": f"Deploy {topo} environment",
            })
            phase_num += 1
    else:
        # Scale down
        phase_num = 1
        for topo in reversed(TOPOLOGY_ORDER[target_idx:current_idx]):
            plan.phases.append({
                "phase": phase_num,
                "action": "decommission_env",
                "topology": topo,
                "description": f"Decommission {topo} environment",
            })
            phase_num += 1

    return plan
