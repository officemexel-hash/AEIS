"""
SYLION API -- Lifecycle Gates routes.

Endpoints for the LifecycleGates module:
  define_stage, list_stages, create_gate, list_gates,
  evaluate_gate, get_evaluation_history, promote, get_lifecycle_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/lifecycle", tags=["Lifecycle"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_lifecycle_gates = None


def _get_lifecycle_gates():
    global _lifecycle_gates
    if _lifecycle_gates is not None:
        return _lifecycle_gates
    from sylion.core.lifecycle_gates import get_lifecycle_gates
    _lifecycle_gates = get_lifecycle_gates()
    return _lifecycle_gates


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class DefineStageRequest(BaseModel):
    name: str
    order: int
    description: str = ""


class CreateGateRequest(BaseModel):
    stage_id: str
    gate_name: str
    criteria_json: dict | str | None = None


class EvaluateGateRequest(BaseModel):
    gate_id: str
    context_json: dict | str | None = None


class PromoteRequest(BaseModel):
    target_id: str
    from_stage: str
    to_stage: str
    evaluation_data: dict | None = None


# ---------------------------------------------------------------------------
# Stage CRUD
# ---------------------------------------------------------------------------

@router.post("/stages", status_code=201)
def define_stage(body: DefineStageRequest):
    """Define a lifecycle stage."""
    import sqlite3
    lg = _get_lifecycle_gates()
    try:
        return lg.define_stage(
            name=body.name,
            order=body.order,
            description=body.description,
        )
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stages")
def list_stages():
    """List all stages ordered by stage_order."""
    lg = _get_lifecycle_gates()
    return {"stages": lg.list_stages()}


# ---------------------------------------------------------------------------
# Gate CRUD
# ---------------------------------------------------------------------------

@router.post("/gates", status_code=201)
def create_gate(body: CreateGateRequest):
    """Create a gate attached to a stage."""
    lg = _get_lifecycle_gates()
    try:
        return lg.create_gate(
            stage_id=body.stage_id,
            gate_name=body.gate_name,
            criteria_json=body.criteria_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/gates")
def list_gates(stage_id: str | None = None):
    """List gates, optionally filtered by stage."""
    lg = _get_lifecycle_gates()
    return {"gates": lg.list_gates(stage_id=stage_id)}


# ---------------------------------------------------------------------------
# Gate evaluation -- static paths before dynamic /{gate_id} paths
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_lifecycle_stats():
    """Aggregate lifecycle statistics."""
    lg = _get_lifecycle_gates()
    return lg.get_lifecycle_stats()


@router.post("/gates/{gate_id}/evaluate")
def evaluate_gate(gate_id: str, body: EvaluateGateRequest):
    """Evaluate a gate against a context."""
    lg = _get_lifecycle_gates()
    try:
        return lg.evaluate_gate(gate_id, context_json=body.context_json)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/gates/{gate_id}/history")
def get_evaluation_history(gate_id: str, limit: int = 50):
    """Get evaluation history for a gate, most recent first."""
    lg = _get_lifecycle_gates()
    return {"evaluations": lg.get_evaluation_history(gate_id, limit=limit)}


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------

@router.post("/promote")
def promote(body: PromoteRequest):
    """Promote a target from one stage to another after gate checks."""
    lg = _get_lifecycle_gates()
    try:
        return lg.promote(
            target_id=body.target_id,
            from_stage=body.from_stage,
            to_stage=body.to_stage,
            evaluation_data=body.evaluation_data,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
