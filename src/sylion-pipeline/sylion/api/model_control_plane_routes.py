"""API routes for the unified ModelControlPlane."""

from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sylion.cognitive.model_control_plane import ModelControlPlane, get_model_control_plane

router = APIRouter(prefix="/api/v1/model-control-plane", tags=["Model Control Plane"])

_control_plane: ModelControlPlane | None = None


def _get_control_plane() -> ModelControlPlane:
    global _control_plane
    if _control_plane is None:
        _control_plane = get_model_control_plane()
    return _control_plane


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


class ProviderModelRequest(BaseModel):
    model_id: str
    display_name: str = ""
    provider_model: str = ""
    capabilities: list[str] = Field(default_factory=list)
    model_family: str = ""
    context_window: int | None = None
    proficiency: str = "medium"
    cost_profile: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class RegisterProviderRequest(BaseModel):
    provider_id: str
    display_name: str = ""
    models: list[ProviderModelRequest] = Field(default_factory=list)
    quotas: dict[str, Any] = Field(default_factory=dict)
    keys_ref: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SetBudgetRequest(BaseModel):
    model_id: str
    daily_limit: float = 0.0
    monthly_limit: float = 0.0
    alert_threshold_pct: float = 80.0
    provider: str = ""
    fallback_model_id: str = ""


class SetRouteRequest(BaseModel):
    stage: str
    model_id: str
    project_id: str = ""
    fallback_chain: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


class ResolveRouteRequest(BaseModel):
    stage: str
    project_id: str = ""
    task_type: str = ""
    estimated_cost: float = 0.0


class CouncilConfigRequest(BaseModel):
    project_id: str
    quorum: int = 1
    roles: list[str] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)
    model_assignments: dict[str, str] = Field(default_factory=dict)


@router.post("/providers", status_code=201)
def register_provider(body: RegisterProviderRequest) -> dict[str, Any]:
    try:
        return _json_safe(_get_control_plane().register_provider(
            body.provider_id,
            display_name=body.display_name,
            models=[model.model_dump() if hasattr(model, "model_dump") else model.dict() for model in body.models],
            quotas=body.quotas,
            keys_ref=body.keys_ref,
            metadata=body.metadata,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/providers")
def list_providers() -> dict[str, Any]:
    providers = _get_control_plane().list_providers()
    return {"providers": providers, "count": len(providers)}


@router.post("/budgets", status_code=201)
def set_budget(body: SetBudgetRequest) -> dict[str, Any]:
    try:
        return _json_safe(_get_control_plane().set_budget(
            body.model_id,
            daily_limit=body.daily_limit,
            monthly_limit=body.monthly_limit,
            alert_threshold_pct=body.alert_threshold_pct,
            provider=body.provider,
            fallback_model_id=body.fallback_model_id,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/routing", status_code=201)
def set_routing(body: SetRouteRequest) -> dict[str, Any]:
    try:
        return _json_safe(_get_control_plane().set_routing(
            body.stage,
            body.model_id,
            project_id=body.project_id,
            fallback_chain=body.fallback_chain,
            constraints=body.constraints,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/routing")
def list_routing() -> dict[str, Any]:
    routes = _get_control_plane().list_routes()
    return {"routes": routes, "count": len(routes)}


@router.post("/routing/resolve")
def resolve_routing(body: ResolveRouteRequest) -> dict[str, Any]:
    try:
        return _json_safe(_get_control_plane().resolve_route(
            body.stage,
            project_id=body.project_id,
            task_type=body.task_type,
            estimated_cost=body.estimated_cost,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/council-config", status_code=201)
def configure_council(body: CouncilConfigRequest) -> dict[str, Any]:
    try:
        return _json_safe(_get_control_plane().configure_council(
            body.project_id,
            quorum=body.quorum,
            roles=body.roles,
            weights=body.weights,
            model_assignments=body.model_assignments,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/council-config")
def list_council_configs(project_id: str | None = None) -> dict[str, Any]:
    plane = _get_control_plane()
    if project_id:
        item = plane.get_council_config(project_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Council config not found: {project_id}")
        return {"configs": [item], "count": 1}
    configs = plane.list_council_configs()
    return {"configs": configs, "count": len(configs)}


@router.get("/snapshot")
def snapshot() -> dict[str, Any]:
    return _json_safe(_get_control_plane().snapshot())
