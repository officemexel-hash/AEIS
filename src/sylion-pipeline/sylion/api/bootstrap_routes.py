"""
SYLION API -- Bootstrap Flow routes.

Endpoints for the BootstrapFlow module:
  create_flow, update_flow, delete_flow,
  get_flow, list_flows,
  add_step, remove_step,
  execute_flow, get_execution, list_executions,
  get_flow_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/bootstrap", tags=["Bootstrap"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_flow = None


def _get_flow():
    global _flow
    if _flow is not None:
        return _flow
    from sylion.security.bootstrap_flow import get_bootstrap_flow
    _flow = get_bootstrap_flow()
    return _flow


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class StepDef(BaseModel):
    step_name: str | None = None
    step_type: str = "action"
    step_order: int | None = None
    config_json: dict | None = None


class CreateFlowRequest(BaseModel):
    name: str
    description: str = ""
    steps_list: list[StepDef] | None = None


class UpdateFlowRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class AddStepRequest(BaseModel):
    step_name: str
    step_type: str = "action"
    config_json: dict | None = None


class ExecuteFlowRequest(BaseModel):
    context_json: dict | None = None


# ---------------------------------------------------------------------------
# Create / List
# ---------------------------------------------------------------------------

@router.post("/flows", status_code=201)
def create_flow(body: CreateFlowRequest):
    """Create a new bootstrap flow with optional initial steps."""
    bf = _get_flow()
    steps = None
    if body.steps_list:
        steps = [s.model_dump(exclude_none=True) for s in body.steps_list]
    return bf.create_flow(
        name=body.name,
        description=body.description,
        steps_list=steps,
    )


@router.get("/flows/list")
def list_flows(status: str | None = None):
    """List flows, optionally filtered by status."""
    bf = _get_flow()
    return {"flows": bf.list_flows(status=status)}


@router.get("/stats")
def get_flow_stats():
    """Aggregate flow statistics."""
    bf = _get_flow()
    return bf.get_flow_stats()


# ---------------------------------------------------------------------------
# Single flow -- static paths before dynamic /{flow_id} paths
# ---------------------------------------------------------------------------

@router.get("/flows/{flow_id}")
def get_flow(flow_id: str):
    """Get a flow with its steps."""
    bf = _get_flow()
    result = bf.get_flow(flow_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Flow {flow_id} not found")
    return result


@router.patch("/flows/{flow_id}")
def update_flow(flow_id: str, body: UpdateFlowRequest):
    """Update mutable flow fields."""
    bf = _get_flow()
    try:
        result = bf.update_flow(flow_id, **body.model_dump(exclude_none=True))
        if not result:
            raise HTTPException(status_code=404, detail=f"Flow {flow_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/flows/{flow_id}")
def delete_flow(flow_id: str):
    """Delete a flow and all associated steps/executions."""
    bf = _get_flow()
    ok = bf.delete_flow(flow_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Flow {flow_id} not found")
    return {"deleted": True, "flow_id": flow_id}


# ---------------------------------------------------------------------------
# Step management
# ---------------------------------------------------------------------------

@router.post("/flows/{flow_id}/steps", status_code=201)
def add_step(flow_id: str, body: AddStepRequest):
    """Add a step to a flow (appended at end)."""
    bf = _get_flow()
    try:
        return bf.add_step(
            flow_id=flow_id,
            step_name=body.step_name,
            step_type=body.step_type,
            config_json=body.config_json,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/steps/{step_id}")
def remove_step(step_id: str):
    """Remove a step from a flow."""
    bf = _get_flow()
    ok = bf.remove_step(step_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found")
    return {"deleted": True, "step_id": step_id}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

@router.post("/flows/{flow_id}/execute", status_code=201)
def execute_flow(flow_id: str, body: ExecuteFlowRequest):
    """Execute a flow by running all steps in order."""
    bf = _get_flow()
    try:
        result = bf.execute_flow(flow_id, context_json=body.context_json)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("error", "execution failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/executions/{execution_id}")
def get_execution(execution_id: str):
    """Get an execution record by ID."""
    bf = _get_flow()
    result = bf.get_execution(execution_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    return result


@router.get("/executions")
def list_executions(flow_id: str | None = None, status: str | None = None):
    """List executions, optionally filtered by flow and/or status."""
    bf = _get_flow()
    return {"executions": bf.list_executions(flow_id=flow_id, status=status)}
