"""Production deploy pipeline API."""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from sylion.governance.deployment_gate import (
    ensure_production_deployment_gate,
    requires_production_gate,
)
from sylion.ops.production_deploy_pipeline import (
    ProductionDeployRequest,
    get_production_deploy_pipeline,
)
from sylion.security.rbac import requires_role


router = APIRouter(prefix="/api/v1/production-deploy", tags=["production-deploy"])


class ProductionDeployRunPayload(BaseModel):
    project_id: str
    artifact_sha256: str
    previous_artifact_sha256: str
    release_version: str
    target_environment: str = "production"
    approval_ticket_id: str = ""
    canary_percent: int = Field(default=5, ge=5, le=100)
    canary_observation_minutes: int = Field(default=15, ge=15)
    scan_report: dict[str, Any] = Field(default_factory=dict)
    smoke_report: dict[str, Any] = Field(default_factory=dict)
    operator_probe: dict[str, Any] = Field(default_factory=dict)
    failure_injection_stage: str = ""
    include_rollback_drill: bool = True
    rollback_on_failure: bool = True


class RollbackPayload(BaseModel):
    approval_ticket_id: str = ""
    reason: str = "operator_requested_rollback"


class RollbackDrillPayload(BaseModel):
    reason: str = "operator_requested_rollback_drill"


def _model_dump(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _pipeline():
    return get_production_deploy_pipeline(
        db_path=os.environ.get("SYLION_DB_PATH", "sylion_aeis.db"),
    )


def _gate_or_block(
    *,
    action: str,
    target: str,
    approval_ticket_id: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    if not requires_production_gate(target):
        return None
    gate = ensure_production_deployment_gate(
        action=action,
        target=target,
        approval_ticket_id=approval_ticket_id,
        payload=payload,
    )
    if not gate.get("allowed"):
        raise HTTPException(status_code=423, detail=gate)
    return gate


@router.post("/pipeline/run", status_code=201)
def run_production_deploy_pipeline(
    body: ProductionDeployRunPayload,
    _user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    payload = _model_dump(body)
    try:
        gate = _gate_or_block(
            action="production_deploy.pipeline.run",
            target=body.target_environment,
            approval_ticket_id=body.approval_ticket_id,
            payload={
                "project_id": body.project_id,
                "release_version": body.release_version,
                "artifact_sha256": body.artifact_sha256,
            },
        )
        result = _pipeline().run(ProductionDeployRequest(**payload))
        return {"run": result, "production_gate": gate}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/pipelines")
def list_production_deploy_runs(
    project_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    return {
        "runs": _pipeline().list_runs(
            project_id=project_id,
            status=status,
            limit=limit,
        )
    }


@router.get("/pipeline/{run_id}")
def get_production_deploy_run(
    run_id: str,
    _user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    run = _pipeline().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"production deploy run not found: {run_id}")
    return {"run": run}


@router.post("/pipeline/{run_id}/rollback-test")
def run_production_rollback_drill(
    run_id: str,
    body: RollbackDrillPayload,
    _user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    try:
        rollback = _pipeline().rollback(run_id, reason=body.reason, drill=True)
        run = _pipeline().get_run(run_id)
        return {"rollback": rollback, "run": run}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/pipeline/{run_id}/rollback")
def rollback_production_deploy(
    run_id: str,
    body: RollbackPayload,
    _user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    run = _pipeline().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"production deploy run not found: {run_id}")
    try:
        gate = _gate_or_block(
            action="production_deploy.pipeline.rollback",
            target=str(run.get("target_environment") or "production"),
            approval_ticket_id=body.approval_ticket_id,
            payload={
                "project_id": run.get("project_id", ""),
                "release_version": run.get("release_version", ""),
                "run_id": run_id,
            },
        )
        rollback = _pipeline().rollback(run_id, reason=body.reason, drill=False)
        return {"rollback": rollback, "run": _pipeline().get_run(run_id), "production_gate": gate}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
