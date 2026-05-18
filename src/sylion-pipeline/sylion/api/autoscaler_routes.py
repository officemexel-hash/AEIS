"""
SYLION API -- Auto-Scaler routes

Controls auto-scaling policies and execution for the worker fleet.
"""

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sylion.security.rbac import requires_role
from sylion.worker.autoscaler import (
    AutoScaler,
    AutoscalerSignal,
    AutoscalerSimulationProfile,
    get_autoscaler_simulation_runner,
)
from sylion.worker.registry import get_worker_registry

router = APIRouter(prefix="/api/v1/workers")

_autoscaler: AutoScaler | None = None


def _get_autoscaler() -> AutoScaler:
    global _autoscaler
    if _autoscaler is None:
        db_path = os.environ.get("SYLION_WORKER_DB_PATH") or os.environ.get("SYLION_DB_PATH")
        _autoscaler = AutoScaler(registry=get_worker_registry(db_path=db_path))
    return _autoscaler


class AutoscalerSignalRequest(BaseModel):
    at_sec: float = Field(ge=0)
    queue_depth: int = Field(ge=0)
    cpu_pct: float = Field(ge=0, le=100)
    error_rate: float = Field(ge=0)


class AutoscalerSimulationRequest(BaseModel):
    name: str = "autoscaler_production_readiness"
    initial_workers: int = Field(default=2, ge=1)
    min_workers: int = Field(default=2, ge=1)
    max_workers: int = Field(default=6, ge=1)
    target_queue_depth: int = Field(default=3, ge=1)
    scale_up_threshold_ratio: float = Field(default=1.0, gt=0)
    scale_down_threshold_ratio: float = Field(default=0.5, gt=0)
    scale_up_cpu_pct: float = Field(default=75.0, ge=0, le=100)
    scale_down_cpu_pct: float = Field(default=25.0, ge=0, le=100)
    scale_up_error_rate: float = Field(default=0.05, ge=0)
    scale_down_error_rate: float = Field(default=0.01, ge=0)
    cooldown_sec: float = Field(default=60.0, ge=0)
    signals: list[AutoscalerSignalRequest] = Field(default_factory=list)


def _model_dump(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@router.get("/autoscaler/status")
def autoscaler_status():
    """Current auto-scaler evaluation status."""
    return _get_autoscaler().evaluate()


@router.post("/autoscaler/evaluate")
def autoscaler_evaluate():
    """Force re-evaluation of scaling needs."""
    return _get_autoscaler().evaluate()


@router.post("/autoscaler/execute")
def autoscaler_execute(decision: str | None = None):
    """Execute a scaling decision (scale_up, scale_down, or auto)."""
    return _get_autoscaler().execute(decision)


@router.get("/autoscaler/history")
def autoscaler_history(limit: int = 20):
    """Recent scaling actions."""
    return {"history": _get_autoscaler().get_history(limit=limit)}


@router.get("/autoscaler/policy")
def autoscaler_policy():
    """Current scaling policy."""
    return _get_autoscaler().get_policy()


@router.post("/autoscaler/policy")
def autoscaler_update_policy(body: dict):
    """Update scaling policy parameters."""
    return _get_autoscaler().update_policy(**body)


@router.post("/autoscaler/simulate")
def autoscaler_simulate(
    body: AutoscalerSimulationRequest,
    _user: str = Depends(requires_role("operator")),
):
    """Run a production-readiness autoscaler simulation."""
    payload = _model_dump(body)
    signals = [AutoscalerSignal(**item) for item in payload.pop("signals", [])]
    try:
        profile = AutoscalerSimulationProfile(**payload, signals=signals)
        return get_autoscaler_simulation_runner().run(profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
