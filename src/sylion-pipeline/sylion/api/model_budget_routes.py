"""
SYLION API -- Model Budget routes.

Endpoints for the ModelBudgetManager module:
  set_budget, get_budget, list_budgets, record_usage, get_usage,
  check_budget, list_alerts, acknowledge_alert, get_budget_summary.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/model-budget", tags=["Model Budget"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_model_budget = None


def _get_model_budget():
    global _model_budget
    if _model_budget is not None:
        return _model_budget
    from sylion.monitoring.model_budget import get_model_budget
    _model_budget = get_model_budget()
    return _model_budget


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SetBudgetRequest(BaseModel):
    model_id: str
    daily_limit: float = 0
    monthly_limit: float = 0
    alert_threshold_pct: float = 80.0


class RecordUsageRequest(BaseModel):
    model_id: str
    tokens: int
    cost: float


# ---------------------------------------------------------------------------
# Budget configuration -- static paths before dynamic /{model_id} paths
# ---------------------------------------------------------------------------

@router.post("/budgets")
def set_budget(body: SetBudgetRequest):
    """Set or update the budget for a model."""
    mgr = _get_model_budget()
    return mgr.set_budget(
        model_id=body.model_id,
        daily_limit=body.daily_limit,
        monthly_limit=body.monthly_limit,
        alert_threshold_pct=body.alert_threshold_pct,
    )


@router.get("/budgets")
def list_budgets():
    """List all configured budgets."""
    mgr = _get_model_budget()
    return mgr.list_budgets()


@router.get("/summary")
def get_budget_summary():
    """Aggregate budget summary across all models."""
    mgr = _get_model_budget()
    return mgr.get_budget_summary()


@router.get("/budgets/{model_id}")
def get_budget(model_id: str):
    """Get budget configuration for a model."""
    mgr = _get_model_budget()
    result = mgr.get_budget(model_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Budget for model {model_id} not found")
    return result


@router.get("/budgets/{model_id}/check")
def check_budget(model_id: str):
    """Check if a model is within its budget."""
    mgr = _get_model_budget()
    return mgr.check_budget(model_id)


# ---------------------------------------------------------------------------
# Usage recording
# ---------------------------------------------------------------------------

@router.post("/usage", status_code=201)
def record_usage(body: RecordUsageRequest):
    """Record token usage and cost against a model's budget."""
    mgr = _get_model_budget()
    return mgr.record_usage(
        model_id=body.model_id,
        tokens=body.tokens,
        cost=body.cost,
    )


@router.get("/usage/{model_id}")
def get_usage(model_id: str, period: str = "all"):
    """Get usage records for a model."""
    mgr = _get_model_budget()
    return {"usage": mgr.get_usage(model_id, period=period)}


# ---------------------------------------------------------------------------
# Alerts -- static paths before dynamic /{alert_id} paths
# ---------------------------------------------------------------------------

@router.get("/alerts")
def list_alerts(
    model_id: str | None = None,
    acknowledged: bool | None = None,
):
    """List budget alerts with optional filters."""
    mgr = _get_model_budget()
    return mgr.list_alerts(model_id=model_id, acknowledged=acknowledged)


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    """Acknowledge a budget alert."""
    mgr = _get_model_budget()
    result = mgr.acknowledge_alert(alert_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Alert {alert_id} not found")
    return result
