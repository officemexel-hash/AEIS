"""
SYLION API -- Auto-Scaler routes

Controls auto-scaling policies and execution for the worker fleet.
"""

from fastapi import APIRouter

from sylion.worker.autoscaler import AutoScaler
from sylion.worker.registry import get_worker_registry

router = APIRouter(prefix="/api/v1/workers")

_autoscaler: AutoScaler | None = None


def _get_autoscaler() -> AutoScaler:
    global _autoscaler
    if _autoscaler is None:
        _autoscaler = AutoScaler(registry=get_worker_registry())
    return _autoscaler


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
