"""
SYLION API -- Rollback Manager routes.

Endpoints for the RollbackManager module:
  create_point, get_point, list_points, restore_point,
  create_operation, execute_operation, get_operation, list_operations,
  log_step, get_rollback_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/rollback", tags=["Rollback"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_rollback_manager = None


def _get_rollback_manager():
    global _rollback_manager
    if _rollback_manager is not None:
        return _rollback_manager
    from sylion.core.rollback_manager import get_rollback_manager
    _rollback_manager = get_rollback_manager()
    return _rollback_manager


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreatePointRequest(BaseModel):
    module_id: str
    state_json: dict | str | None = None
    description: str = ""


class CreateOperationRequest(BaseModel):
    target_module: str
    from_point: str
    to_point: str


class LogStepRequest(BaseModel):
    operation_id: str
    step: str
    status: str
    details_json: dict | str | None = None


# ---------------------------------------------------------------------------
# Restore points
# ---------------------------------------------------------------------------

@router.post("/points", status_code=201)
def create_point(body: CreatePointRequest):
    """Create a restore point for a module."""
    rm = _get_rollback_manager()
    try:
        return rm.create_point(
            module_id=body.module_id,
            state_json=body.state_json,
            description=body.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Retrieval -- static paths before dynamic /{point_id} paths
# ---------------------------------------------------------------------------

@router.get("/points")
def list_points(module_id: str | None = None, limit: int = 100):
    """List restore points, optionally filtered by module."""
    rm = _get_rollback_manager()
    return {"points": rm.list_points(module_id=module_id, limit=limit)}


@router.get("/points/{point_id}")
def get_point(point_id: str):
    """Retrieve a restore point by ID."""
    rm = _get_rollback_manager()
    result = rm.get_point(point_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Point {point_id} not found")
    return result


@router.post("/points/{point_id}/restore")
def restore_point(point_id: str):
    """Restore a module to a specific restore point's state."""
    rm = _get_rollback_manager()
    try:
        result = rm.restore_point(point_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Point {point_id} not found")
    return result


# ---------------------------------------------------------------------------
# Operations -- static paths before dynamic /{operation_id} paths
# ---------------------------------------------------------------------------

@router.post("/operations", status_code=201)
def create_operation(body: CreateOperationRequest):
    """Create a rollback operation between two restore points."""
    rm = _get_rollback_manager()
    try:
        return rm.create_operation(
            target_module=body.target_module,
            from_point=body.from_point,
            to_point=body.to_point,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/operations")
def list_operations(status: str | None = None, limit: int = 100):
    """List operations, optionally filtered by status."""
    rm = _get_rollback_manager()
    return {"operations": rm.list_operations(status=status, limit=limit)}


@router.get("/operations/{operation_id}")
def get_operation(operation_id: str):
    """Retrieve an operation by ID."""
    rm = _get_rollback_manager()
    result = rm.get_operation(operation_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found")
    return result


@router.post("/operations/{operation_id}/execute")
def execute_operation(operation_id: str):
    """Execute a pending rollback operation."""
    rm = _get_rollback_manager()
    try:
        result = rm.execute_operation(operation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found or not pending")
    return result


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

@router.post("/logs", status_code=201)
def log_step(body: LogStepRequest):
    """Log a step within an operation."""
    rm = _get_rollback_manager()
    try:
        return rm.log_step(
            operation_id=body.operation_id,
            step=body.step,
            status=body.status,
            details_json=body.details_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_rollback_stats():
    """Aggregate rollback statistics."""
    rm = _get_rollback_manager()
    return rm.get_rollback_stats()
