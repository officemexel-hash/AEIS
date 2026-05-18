"""SYLION API -- Worker Fleet & Assignment routes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from sylion.security.rbac import requires_role

router = APIRouter(prefix="/api/v1/workers", tags=["workers"])

_wr = None
_orch = None
_compact = None
_lifecycle = None


def _get_registry():
    global _wr
    if _wr is not None:
        return _wr
    from sylion.worker.registry import get_worker_registry
    from sylion.core.event_bus import get_event_bus
    db_path = os.environ.get("SYLION_WORKER_DB_PATH") or os.environ.get("SYLION_DB_PATH")
    _wr = get_worker_registry(db_path=db_path, event_bus=get_event_bus())
    return _wr


def _get_orchestrator():
    global _orch
    if _orch is not None:
        return _orch
    from sylion.worker.assignment import AssignmentOrchestrator
    _orch = AssignmentOrchestrator(worker_registry=_get_registry())
    return _orch


def _get_compact_generator():
    global _compact
    if _compact is not None:
        return _compact
    from sylion.worker.compact import CompactGenerator
    manifest_dir = Path(__file__).parent.parent / "contracts" / "manifests"
    _compact = CompactGenerator(worker_registry=_get_registry(), manifest_dir=manifest_dir)
    return _compact


def _get_lifecycle():
    global _lifecycle
    if _lifecycle is not None:
        return _lifecycle
    from sylion.core.event_bus import get_event_bus
    from sylion.worker.lifecycle import WorkerFleetLifecycle

    db_path = os.environ.get("SYLION_WORKER_DB_PATH") or os.environ.get("SYLION_DB_PATH")
    _lifecycle = WorkerFleetLifecycle(
        registry=_get_registry(),
        db_path=db_path,
        event_bus=get_event_bus(),
    )
    return _lifecycle


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class RegisterWorkerRequest(BaseModel):
    name: str
    host: str = "localhost"
    capacity: int = 3
    api_key_hash: str = ""
    budget_limit: float = 0.0
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateWorkerRequest(BaseModel):
    name: str | None = None
    host: str | None = None
    status: str | None = None
    capacity: int | None = None
    api_key_hash: str | None = None
    budget_limit: float | None = None
    budget_spent: float | None = None
    token_usage: int | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class HeartbeatRequest(BaseModel):
    load: dict[str, Any] | None = None


class CreateAssignmentRequest(BaseModel):
    module_id: str
    priority: int = 5
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateAssignmentRequest(BaseModel):
    status: str | None = None
    priority: int | None = None
    error_log: str | None = None
    metadata: dict[str, Any] | None = None


class PatchProposalRequest(BaseModel):
    patch_content: str
    evidence_pack: dict[str, Any] | None = None


class AutoAssignRequest(BaseModel):
    modules: list[dict[str, Any]]
    strategy: str = "balanced"


class TopologyRequest(BaseModel):
    name: str
    description: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class WorkerLifecycleDrillRequest(BaseModel):
    actor_id: str = "operator-dashboard"
    project_id: str = "worker_fleet_drill"


class WorkerShutdownRequest(BaseModel):
    reason: str = "operator_requested"
    actor_id: str = "operator-dashboard"


# ---------------------------------------------------------------------------
# Worker CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def register_worker(body: RegisterWorkerRequest):
    reg = _get_registry()
    return reg.register_worker(
        name=body.name,
        host=body.host,
        capacity=body.capacity,
        api_key_hash=body.api_key_hash,
        budget_limit=body.budget_limit,
        tags=body.tags,
        metadata=body.metadata,
    )


@router.get("")
def list_workers(status: str | None = None, host: str | None = None):
    reg = _get_registry()
    return {"workers": reg.list_workers(status=status, host=host)}


@router.get("/topology")
def list_topologies_alias():
    reg = _get_registry()
    return {"topologies": reg.list_topologies()}


@router.post("/fleet/lifecycle-drill", status_code=201)
def run_worker_fleet_lifecycle_drill(
    body: WorkerLifecycleDrillRequest,
    _user: str = Depends(requires_role("operator")),
):
    return _get_lifecycle().run_lifecycle_drill(
        actor_id=body.actor_id,
        project_id=body.project_id,
    )


@router.get("/fleet/lifecycle-drills")
def list_worker_fleet_lifecycle_drills(
    limit: int = Query(default=100, ge=1, le=500),
    _user: str = Depends(requires_role("operator")),
):
    return {"drills": _get_lifecycle().list_drills(limit=limit)}


@router.get("/fleet/lifecycle-drills/{drill_id}")
def get_worker_fleet_lifecycle_drill(
    drill_id: str,
    _user: str = Depends(requires_role("operator")),
):
    drill = _get_lifecycle().get_drill(drill_id)
    if not drill:
        raise HTTPException(status_code=404, detail="Lifecycle drill not found")
    return drill


@router.get("/{worker_id}")
def get_worker(worker_id: str):
    reg = _get_registry()
    w = reg.get_worker(worker_id)
    if not w:
        raise HTTPException(status_code=404, detail="Worker not found")
    return w


@router.patch("/{worker_id}")
def update_worker(worker_id: str, body: UpdateWorkerRequest):
    reg = _get_registry()
    fields = body.model_dump(exclude_unset=True)
    if "metadata" in fields:
        fields["metadata_json"] = fields.pop("metadata")
    if "tags" in fields:
        fields["tags"] = fields["tags"]
    w = reg.update_worker(worker_id, **fields)
    if not w:
        raise HTTPException(status_code=404, detail="Worker not found")
    return w


@router.delete("/{worker_id}", status_code=204)
def unregister_worker(worker_id: str):
    reg = _get_registry()
    if not reg.unregister_worker(worker_id):
        raise HTTPException(status_code=404, detail="Worker not found")
    return None


@router.post("/{worker_id}/heartbeat")
def heartbeat(worker_id: str, body: HeartbeatRequest | None = None):
    reg = _get_registry()
    if not reg.heartbeat(worker_id, load=(body.load if body else None)):
        raise HTTPException(status_code=404, detail="Worker not found")
    worker = reg.get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    return {
        "worker": worker,
        "heartbeat_recorded": True,
        "last_heartbeat": worker.get("last_heartbeat"),
        "load": body.load if body else None,
    }


@router.post("/{worker_id}/graceful-shutdown")
def graceful_shutdown_worker(
    worker_id: str,
    body: WorkerShutdownRequest,
    _user: str = Depends(requires_role("operator")),
):
    try:
        return _get_lifecycle().graceful_shutdown(
            worker_id,
            reason=body.reason,
            actor_id=body.actor_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------

@router.post("/{worker_id}/assignments", status_code=201)
def create_assignment(worker_id: str, body: CreateAssignmentRequest):
    reg = _get_registry()
    return reg.create_assignment(
        worker_id=worker_id,
        module_id=body.module_id,
        priority=body.priority,
        metadata=body.metadata,
    )


@router.get("/{worker_id}/assignments")
def list_assignments(worker_id: str, status: str | None = None):
    reg = _get_registry()
    return {"assignments": reg.list_assignments(worker_id=worker_id, status=status)}


@router.get("/assignments/all")
def list_all_assignments(status: str | None = None, module_id: str | None = None):
    reg = _get_registry()
    return {"assignments": reg.list_assignments(status=status, module_id=module_id)}


@router.patch("/{worker_id}/assignments/{assignment_id}")
def update_assignment(worker_id: str, assignment_id: str, body: UpdateAssignmentRequest):
    reg = _get_registry()
    fields = body.model_dump(exclude_unset=True)
    if "metadata" in fields:
        fields["metadata_json"] = fields.pop("metadata")
    a = reg.update_assignment(assignment_id, **fields)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return a


@router.post("/{worker_id}/assignments/{assignment_id}/patch")
def submit_patch_proposal(worker_id: str, assignment_id: str, body: PatchProposalRequest):
    reg = _get_registry()
    a = reg.submit_patch_proposal(assignment_id, body.patch_content, body.evidence_pack)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return a


@router.post("/assignments/orchestrate")
def auto_assign(body: AutoAssignRequest):
    orch = _get_orchestrator()
    return orch.auto_assign(modules=body.modules, strategy=body.strategy)


@router.post("/assignments/rebalance")
def rebalance():
    orch = _get_orchestrator()
    return orch.rebalance()


# ---------------------------------------------------------------------------
# Compact
# ---------------------------------------------------------------------------

@router.get("/{worker_id}/compact")
def get_compact(worker_id: str, format: str = "json"):
    gen = _get_compact_generator()
    try:
        compact = gen.generate(worker_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if format == "markdown":
        return {"content": gen.render_markdown(compact)}
    return compact


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------

@router.post("/topology", status_code=201)
def create_topology(body: TopologyRequest):
    reg = _get_registry()
    return reg.create_topology(name=body.name, description=body.description, config=body.config)


@router.get("/topology/all")
def list_topologies():
    reg = _get_registry()
    return {"topologies": reg.list_topologies()}


@router.get("/topology/{topology_id}")
def get_topology(topology_id: str):
    reg = _get_registry()
    t = reg.get_topology(topology_id)
    if not t:
        raise HTTPException(status_code=404, detail="Topology not found")
    return t


@router.patch("/topology/{topology_id}")
def update_topology(topology_id: str, body: TopologyRequest):
    reg = _get_registry()
    fields = body.model_dump(exclude_unset=True)
    if "config" in fields:
        fields["config_json"] = fields.pop("config")
    t = reg.update_topology(topology_id, **fields)
    if not t:
        raise HTTPException(status_code=404, detail="Topology not found")
    return t


@router.post("/topology/{topology_id}/generate-config")
def generate_topology_config(topology_id: str, variant: str = "8_server"):
    orch = _get_orchestrator()
    reg = _get_registry()
    t = reg.get_topology(topology_id)
    if not t:
        raise HTTPException(status_code=404, detail="Topology not found")
    config = orch.generate_topology_config(variant)
    reg.update_topology(topology_id, config_json=config)
    return {"topology_id": topology_id, "variant": variant, "config": config}
