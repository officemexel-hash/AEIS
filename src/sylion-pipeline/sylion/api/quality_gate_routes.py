"""
SYLION API -- Quality Gate Engine routes.

Endpoints for: quality gate CRUD, evaluation, and statistics.
Module: sylion.quality.quality_gate_engine
"""

from fastapi import APIRouter, HTTPException

from sylion.quality.quality_gate_engine import get_quality_gate_engine

router = APIRouter(prefix="/api/v1/quality", tags=["quality-gates"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_qge = None


def _get_qge():
    global _qge
    if _qge is not None:
        return _qge
    _qge = get_quality_gate_engine()
    return _qge


# ---------------------------------------------------------------------------
# Gate CRUD
# ---------------------------------------------------------------------------

@router.post("/gates", status_code=201)
def create_gate(name: str, gate_type: str, description: str = "",
                criteria: str = ""):
    """Create a new quality gate."""
    import json
    crit = json.loads(criteria) if criteria else None
    try:
        return _get_qge().create_gate(name, gate_type,
                                      description=description,
                                      criteria=crit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/gates")
def list_gates(gate_type: str | None = None, enabled: bool | None = None):
    """List quality gates with optional filters."""
    return {"gates": _get_qge().list_gates(gate_type=gate_type, enabled=enabled)}


@router.get("/gates/{gate_id}")
def get_gate(gate_id: str):
    """Get a quality gate by ID."""
    result = _get_qge().get_gate(gate_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Gate {gate_id} not found")
    return result


@router.put("/gates/{gate_id}")
def update_gate(gate_id: str, name: str | None = None,
                criteria: str = "", enabled: bool | None = None):
    """Update a quality gate."""
    import json
    crit = json.loads(criteria) if criteria else None
    result = _get_qge().update_gate(gate_id, name=name,
                                    criteria=crit, enabled=enabled)
    if not result.get("updated"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.delete("/gates/{gate_id}")
def delete_gate(gate_id: str):
    """Delete a quality gate."""
    result = _get_qge().delete_gate(gate_id)
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

@router.post("/gates/{gate_id}/evaluate")
def evaluate_gate(gate_id: str, module_id: str, context: str = ""):
    """Evaluate a quality gate against a module."""
    import json
    ctx = json.loads(context) if context else None
    return _get_qge().evaluate_gate(gate_id, module_id, context=ctx)


# ---------------------------------------------------------------------------
# Evaluations -- static routes before dynamic {evaluation_id}
# ---------------------------------------------------------------------------

@router.get("/evaluations")
def list_evaluations(gate_id: str | None = None,
                     module_id: str | None = None,
                     result: str | None = None,
                     limit: int = 100):
    """List evaluations with optional filters."""
    try:
        return {"evaluations": _get_qge().list_evaluations(
            gate_id=gate_id, module_id=module_id,
            result=result, limit=limit,
        )}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str):
    """Get a single evaluation by ID."""
    result = _get_qge().get_evaluation(evaluation_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Evaluation {evaluation_id} not found")
    return result


# ---------------------------------------------------------------------------
# Stats -- static path
# ---------------------------------------------------------------------------

@router.get("/stats")
def quality_gate_stats():
    """Get quality gate engine statistics."""
    return _get_qge().get_stats()
