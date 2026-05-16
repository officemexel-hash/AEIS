"""
SYLION API -- Decision Boundaries routes.

Endpoints for: DecisionBoundariesManager (create, update, delete, get,
              list boundaries; evaluate; get evaluation history).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/v1/decision-boundaries",
    tags=["Decision Boundaries"],
)

# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_boundaries = None


def _get_boundaries():
    global _boundaries
    if _boundaries is not None:
        return _boundaries
    from sylion.governance.decision_boundaries import get_decision_boundaries_manager
    _boundaries = get_decision_boundaries_manager()
    return _boundaries


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateBoundaryRequest(BaseModel):
    name: str
    scope: str
    rules_json: Optional[list[dict] | str] = None


class UpdateBoundaryRequest(BaseModel):
    name: Optional[str] = None
    scope: Optional[str] = None
    rules_json: Optional[list[dict] | str] = None
    is_active: Optional[bool] = None


class EvaluateBoundaryRequest(BaseModel):
    context: dict


# ---------------------------------------------------------------------------
# Endpoints -- static routes before parameterized /{boundary_id} routes
# ---------------------------------------------------------------------------

@router.post("/boundaries", status_code=201)
def create_boundary(body: CreateBoundaryRequest):
    """Create a new decision boundary."""
    mgr = _get_boundaries()
    try:
        return mgr.create_boundary(body.name, body.scope, rules_json=body.rules_json)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/boundaries")
def list_boundaries(scope: Optional[str] = None, active_only: bool = False):
    """List decision boundaries, optionally filtered by scope."""
    mgr = _get_boundaries()
    return {"boundaries": mgr.list_boundaries(scope=scope, active_only=active_only)}


@router.post("/evaluate/{boundary_id}", status_code=201)
def evaluate_boundary(boundary_id: str, body: EvaluateBoundaryRequest):
    """Evaluate a boundary against a context dict."""
    mgr = _get_boundaries()
    try:
        return mgr.evaluate_boundary(boundary_id, body.context)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/evaluations/{boundary_id}")
def get_evaluation_history(boundary_id: str, limit: int = 100):
    """Get evaluation history for a boundary, newest first."""
    mgr = _get_boundaries()
    return {"evaluations": mgr.get_evaluation_history(boundary_id, limit=limit)}


# ---------------------------------------------------------------------------
# Endpoints -- parameterized /{boundary_id} routes
# ---------------------------------------------------------------------------

@router.get("/boundaries/{boundary_id}")
def get_boundary(boundary_id: str):
    """Retrieve a single decision boundary by ID."""
    mgr = _get_boundaries()
    result = mgr.get_boundary(boundary_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Boundary {boundary_id} not found")
    return result


@router.put("/boundaries/{boundary_id}")
def update_boundary(boundary_id: str, body: UpdateBoundaryRequest):
    """Update an existing decision boundary."""
    mgr = _get_boundaries()
    try:
        result = mgr.update_boundary(
            boundary_id,
            name=body.name,
            scope=body.scope,
            rules_json=body.rules_json,
            is_active=body.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Boundary {boundary_id} not found")
    return result


@router.delete("/boundaries/{boundary_id}")
def delete_boundary(boundary_id: str):
    """Delete a decision boundary."""
    mgr = _get_boundaries()
    deleted = mgr.delete_boundary(boundary_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Boundary {boundary_id} not found")
    return {"deleted": boundary_id}
