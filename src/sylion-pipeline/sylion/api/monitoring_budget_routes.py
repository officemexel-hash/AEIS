"""SYLION API -- Budget monitoring routes."""

import math

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sylion.aeis.advisor.events.lifecycle import publish_lifecycle_event

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring_budget"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ConfigureBudgetRequest(BaseModel):
    model_id: str = ""
    budget_limit: float
    provider: str = ""
    fallback_model_id: str = ""


class RecordUsageRequest(BaseModel):
    model_id: str = ""
    amount: float
    tokens_in: int = 0
    tokens_out: int = 0
    task_type: str = ""
    session_id: str = ""


class ResolveModelRequest(BaseModel):
    task_type: str = ""


# ---------------------------------------------------------------------------
# Lazy tracker singleton
# ---------------------------------------------------------------------------

_tracker = None


def _get_tracker():
    global _tracker
    if _tracker is not None:
        return _tracker
    from sylion.monitoring.model_budget import get_model_budget_tracker
    _tracker = get_model_budget_tracker()
    return _tracker


def _existing_budget_limit(tracker, model_id: str) -> float | None:
    if not hasattr(tracker, "get_budget"):
        return None
    existing = tracker.get_budget(model_id)
    if not existing:
        return None
    if "budget_limit" in existing:
        return float(existing["budget_limit"])
    if "monthly_limit" in existing:
        return float(existing["monthly_limit"])
    return None


def _json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/budget/configure", status_code=201)
def configure_budget(req: ConfigureBudgetRequest):
    """Configure or update the budget for a model."""
    tracker = _get_tracker()
    try:
        old_threshold = _existing_budget_limit(tracker, req.model_id)
        result = tracker.configure(
            req.model_id,
            req.budget_limit,
            provider=req.provider,
            fallback_model_id=req.fallback_model_id,
        )
        publish_lifecycle_event(
            "aeis.system.budget_config_requested",
            {
                "operator_id": "system",
                "scope": "provider" if req.provider else "global",
                "scope_id": req.model_id,
                "old_threshold_usd": old_threshold,
                "new_threshold_usd": req.budget_limit,
                "period": "monthly",
            },
            source_module="sylion.api.monitoring_budget_routes",
            primary_key=req.model_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/budget/usage", status_code=201)
def record_usage(req: RecordUsageRequest):
    """Record a usage/cost entry against a model's budget."""
    tracker = _get_tracker()
    try:
        return tracker.record_transaction(
            req.model_id,
            req.amount,
            tokens_in=req.tokens_in,
            tokens_out=req.tokens_out,
            task_type=req.task_type,
            session_id=req.session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/budget")
def get_all_budgets():
    """Get budget status for all tracked models."""
    tracker = _get_tracker()
    return {"budgets": tracker.get_all_budgets()}


@router.get("/budget/transactions")
def get_transactions(model_id: str | None = None, limit: int = Query(default=100, ge=1, le=1000)):
    """Get recent usage transactions, optionally filtered by model."""
    tracker = _get_tracker()
    return {"transactions": tracker.get_transactions(model_id=model_id, limit=limit)}


@router.get("/budget/summary")
def get_spending_summary():
    """Get an aggregated spending summary across all models."""
    tracker = _get_tracker()
    return tracker.get_spending_summary()


@router.put("/budget/{model_id}")
def configure_budget_for_model(model_id: str, req: ConfigureBudgetRequest):
    """Legacy dashboard shape: configure budget under the model URL."""
    payload = req.model_copy(update={"model_id": model_id})
    return configure_budget(payload)


@router.get("/budget/{model_id}")
def check_budget(model_id: str):
    """Check the budget status for a specific model."""
    tracker = _get_tracker()
    budget = tracker.get_budget(model_id) if hasattr(tracker, "get_budget") else None
    result = tracker.check_budget(model_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not tracked")
    if budget:
        result = {**budget, **result}
    return _json_safe(result)


@router.post("/budget/{model_id}/resolve")
def resolve_model(model_id: str, body: ResolveModelRequest):
    """Resolve the best model for a task, considering budget limits and fallbacks."""
    tracker = _get_tracker()
    try:
        return tracker.resolve(model_id, task_type=body.task_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/budget/{model_id}/usage", status_code=201)
def record_usage_for_model(model_id: str, req: RecordUsageRequest):
    """Legacy dashboard shape: record usage under the model URL."""
    payload = req.model_copy(update={"model_id": model_id})
    return record_usage(payload)


@router.post("/budget/{model_id}/reset")
def reset_budget(model_id: str):
    """Reset spending counters for a model."""
    tracker = _get_tracker()
    try:
        return tracker.reset(model_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
