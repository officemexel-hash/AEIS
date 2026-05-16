"""SYLION API -- Integration Orchestrator & Drift Detector routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/integration", tags=["integration"])

_orch = None
_drift = None


def _get_orchestrator():
    global _orch
    if _orch is not None:
        return _orch
    from sylion.integration.orchestrator import get_integration_orchestrator
    from sylion.worker.registry import get_worker_registry
    from sylion.worker.sandbox import SandboxManager
    from sylion.core.event_bus import get_event_bus
    _orch = get_integration_orchestrator(
        event_bus=get_event_bus(),
        worker_registry=get_worker_registry(event_bus=get_event_bus()),
        sandbox_manager=SandboxManager(),
    )
    return _orch


def _get_drift_detector():
    global _drift
    if _drift is not None:
        return _drift
    from sylion.integration.drift_detector import get_drift_detector
    from sylion.core.event_bus import get_event_bus
    _drift = get_drift_detector(event_bus=get_event_bus())
    return _drift


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CreateBuildRequest(BaseModel):
    name: str
    description: str = ""
    patch_ids: list[str] = Field(default_factory=list)
    module_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateBuildRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None


class ValidateBuildRequest(BaseModel):
    sandbox_dir: str | None = None


class RejectBuildRequest(BaseModel):
    reason: str = ""


class ResolveDriftRequest(BaseModel):
    resolution: str = ""


# ---------------------------------------------------------------------------
# Candidate Builds
# ---------------------------------------------------------------------------

@router.post("/builds", status_code=201)
def create_build(body: CreateBuildRequest):
    orch = _get_orchestrator()
    return orch.create_candidate_build(
        name=body.name,
        description=body.description,
        patch_ids=body.patch_ids,
        module_ids=body.module_ids,
        metadata=body.metadata,
    )


@router.get("/builds")
def list_builds(status: str | None = None):
    orch = _get_orchestrator()
    return {"builds": orch.list_candidate_builds(status=status)}


@router.get("/builds/{build_id}")
def get_build(build_id: str):
    orch = _get_orchestrator()
    b = orch.get_candidate_build(build_id)
    if not b:
        raise HTTPException(status_code=404, detail="Build not found")
    return b


@router.patch("/builds/{build_id}")
def update_build(build_id: str, body: UpdateBuildRequest):
    orch = _get_orchestrator()
    fields = body.model_dump(exclude_unset=True)
    if "metadata" in fields:
        fields["metadata_json"] = fields.pop("metadata")
    if "status" in fields:
        b = orch.update_build_status(build_id, fields["status"])
    else:
        # Generic update not fully implemented in orchestrator; delegate to status for now
        b = orch.get_candidate_build(build_id)
    if not b:
        raise HTTPException(status_code=404, detail="Build not found")
    return b


@router.delete("/builds/{build_id}", status_code=204)
def delete_build(build_id: str):
    orch = _get_orchestrator()
    if not orch.delete_candidate_build(build_id):
        raise HTTPException(status_code=404, detail="Build not found")
    return None


@router.post("/builds/{build_id}/validate")
def validate_build(build_id: str, body: ValidateBuildRequest | None = None):
    orch = _get_orchestrator()
    b = orch.get_candidate_build(build_id)
    if not b:
        raise HTTPException(status_code=404, detail="Build not found")
    sandbox = body.sandbox_dir if body else None
    results = orch.run_validation(build_id, sandbox_dir=sandbox)
    return {"build_id": build_id, "results": results}


@router.post("/builds/{build_id}/promote")
def promote_build(build_id: str):
    orch = _get_orchestrator()
    b = orch.promote(build_id)
    if not b:
        raise HTTPException(status_code=404, detail="Build not found")
    return b


@router.post("/builds/{build_id}/reject")
def reject_build(build_id: str, body: RejectBuildRequest | None = None):
    orch = _get_orchestrator()
    b = orch.reject(build_id, reason=(body.reason if body else ""))
    if not b:
        raise HTTPException(status_code=404, detail="Build not found")
    return b


@router.get("/builds/{build_id}/results")
def get_build_results(build_id: str):
    orch = _get_orchestrator()
    b = orch.get_candidate_build(build_id)
    if not b:
        raise HTTPException(status_code=404, detail="Build not found")
    return {"build_id": build_id, "results": orch.get_results_for_build(build_id)}


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------

@router.post("/drift/detect")
def detect_drift():
    detector = _get_drift_detector()
    drifts = detector.detect_all()
    return {"drifts": drifts, "count": len(drifts)}


@router.get("/drift")
def list_drifts(status: str | None = None, severity: str | None = None, source_module: str | None = None):
    detector = _get_drift_detector()
    return {"drifts": detector.list_drifts(status=status, severity=severity, source_module=source_module)}


@router.get("/drift/summary")
def drift_summary():
    detector = _get_drift_detector()
    return detector.get_drift_summary()


@router.post("/drift/{drift_id}/resolve")
def resolve_drift(drift_id: str, body: ResolveDriftRequest | None = None):
    detector = _get_drift_detector()
    d = detector.resolve_drift(drift_id, resolution=(body.resolution if body else ""))
    if not d:
        raise HTTPException(status_code=404, detail="Drift not found")
    return d
