"""
SYLION API -- Deployment Orchestrator routes.

Endpoints for: deployment lifecycle, step management, and statistics.
Module: sylion.execution.deployment_orchestrator
"""

from fastapi import APIRouter, Depends, HTTPException

from sylion.aeis.advisor.events.lifecycle import publish_lifecycle_event
from sylion.execution.deployment_orchestrator import get_deployment_orchestrator
from sylion.governance.deployment_gate import (
    ensure_production_deployment_gate,
    requires_production_gate,
)
from sylion.security.rbac import requires_role

router = APIRouter(prefix="/api/v1/deployments", tags=["deployments"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_orch = None


def _get_orch():
    global _orch
    if _orch is not None:
        return _orch
    _orch = get_deployment_orchestrator()
    return _orch


def _topology_for_stage(stage: str) -> str:
    """Map deployment stages to advisor-facing topology labels."""
    if stage in {"draft", "build", "validate"}:
        return "local_only"
    if stage in {"shadow", "dual"}:
        return "hybrid"
    if stage in {"cutover", "stable"}:
        return "local_vps"
    if stage == "deprecated":
        return "vps_only"
    return stage


def _env_count_for_topology(topology: str) -> int:
    """Estimate environment count from the selected runtime topology."""
    if topology == "local_only":
        return 1
    if topology in {"hybrid", "local_vps"}:
        return 2
    if topology == "vps_only":
        return 1
    return 1


def _scaling_action(current_topology: str, proposed_topology: str) -> str:
    """Choose the closest scaling action for the topology delta."""
    current_env_count = _env_count_for_topology(current_topology)
    target_env_count = _env_count_for_topology(proposed_topology)
    if target_env_count > current_env_count:
        return "add_env"
    if target_env_count < current_env_count:
        return "remove_env"
    if current_topology == "local_only" and proposed_topology in {"hybrid", "local_vps", "vps_only"}:
        return "scale_up"
    if current_topology in {"hybrid", "local_vps", "vps_only"} and proposed_topology == "local_only":
        return "scale_down"
    return "parallel_split" if proposed_topology == "hybrid" else "add_env"


# ---------------------------------------------------------------------------
# Create deployment
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_deployment(module_id: str, from_stage: str, to_stage: str,
                      strategy: str = "blue_green",
                      approval_ticket_id: str = "",
                      _user: str = Depends(requires_role("operator"))):
    """Create a new deployment with auto-generated steps. Operator-gated."""
    try:
        gate: dict[str, object] | None = None
        if requires_production_gate(to_stage):
            gate = ensure_production_deployment_gate(
                action="deployment.create",
                target=to_stage,
                approval_ticket_id=approval_ticket_id,
                payload={
                    "module_id": module_id,
                    "from_stage": from_stage,
                    "to_stage": to_stage,
                    "strategy": strategy,
                },
            )
            if not gate.get("allowed"):
                raise HTTPException(status_code=423, detail=gate)
        result = _get_orch().create_deployment(
            module_id, from_stage, to_stage, strategy=strategy,
        )
        if gate:
            metadata = result.setdefault("metadata", {})
            metadata["governance_ticket_id"] = approval_ticket_id or gate.get("governance_ticket_id", "")
            metadata["production_gate"] = gate
        current_topology = _topology_for_stage(from_stage)
        proposed_topology = _topology_for_stage(to_stage)
        current_env_count = _env_count_for_topology(current_topology)
        target_env_count = _env_count_for_topology(proposed_topology)
        publish_lifecycle_event(
            "aeis.system.runtime_topology_change_requested",
            {
                "operator_id": "operator",
                "project_id": module_id,
                "current_topology": current_topology,
                "proposed_topology": proposed_topology,
                "workload_profile": {
                    "token_estimate": 0,
                    "parallelism": target_env_count,
                    "latency_target": "standard",
                    "strategy": strategy,
                },
            },
            source_module="sylion.api.deployment_routes",
            primary_key=result.get("deployment_id", module_id),
        )
        publish_lifecycle_event(
            "aeis.system.vps_scaling_requested",
            {
                "operator_id": "operator",
                "project_id": module_id,
                "action": _scaling_action(current_topology, proposed_topology),
                "current_env_count": current_env_count,
                "target_env_count": target_env_count,
                "evidence_pack_required": target_env_count > 1 or proposed_topology in {"hybrid", "local_vps"},
            },
            source_module="sylion.api.deployment_routes",
            primary_key=result.get("deployment_id", module_id),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# List / Get -- static routes before dynamic {deployment_id}
# ---------------------------------------------------------------------------

@router.get("/stats")
def deployment_stats():
    """Get deployment orchestrator statistics."""
    return _get_orch().get_stats()


@router.get("")
def list_deployments(module_id: str | None = None,
                     status: str | None = None,
                     limit: int = 100):
    """List deployments with optional filters."""
    try:
        return {"deployments": _get_orch().list_deployments(
            module_id=module_id, status=status, limit=limit,
        )}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Single deployment + lifecycle actions
# ---------------------------------------------------------------------------

@router.get("/{deployment_id}")
def get_deployment(deployment_id: str):
    """Get a single deployment by ID."""
    result = _get_orch().get_deployment(deployment_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Deployment {deployment_id} not found")
    return result


@router.post("/{deployment_id}/advance")
def advance_step(deployment_id: str, step_name: str, output: str = ""):
    """Advance a step within a deployment."""
    try:
        return _get_orch().advance_step(deployment_id, step_name, output=output)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{deployment_id}/complete")
def complete_deployment(deployment_id: str):
    """Mark a deployment as completed."""
    try:
        return _get_orch().complete_deployment(deployment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{deployment_id}/fail")
def fail_deployment(deployment_id: str, reason: str = ""):
    """Mark a deployment as failed."""
    try:
        return _get_orch().fail_deployment(deployment_id, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{deployment_id}/rollback")
def rollback_deployment(deployment_id: str):
    """Rollback a deployment."""
    try:
        return _get_orch().rollback_deployment(deployment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{deployment_id}/steps")
def get_deployment_steps(deployment_id: str):
    """Get all steps for a deployment."""
    try:
        return {"steps": _get_orch().get_steps(deployment_id)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
