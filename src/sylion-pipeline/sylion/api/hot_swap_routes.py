"""
SYLION API -- Hot-Swap routes.

Endpoints for environment hot-swap operations:
  list environments, get active, switch environment, bind modules, health.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sylion.core.hot_swap import get_hot_swap_orchestrator

router = APIRouter(prefix="/api/v1/core/hot-swap", tags=["hot-swap"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class SwitchRequest(BaseModel):
    target: str
    module_filter: list[str] | None = None


class BindRequest(BaseModel):
    module_id: str
    env_name: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/environments")
def list_environments():
    """List all registered environments."""
    orch = get_hot_swap_orchestrator()
    return {"environments": orch.list_environments()}


@router.get("/active")
def get_active():
    """Get the currently active environment."""
    orch = get_hot_swap_orchestrator()
    return orch.get_active()


@router.post("/switch")
def switch_environment(body: SwitchRequest):
    """Switch to a target environment, optionally filtering by modules."""
    orch = get_hot_swap_orchestrator()
    result = orch.switch_env(body.target, module_filter=body.module_filter)
    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot switch to unknown environment '{body.target}'",
        )
    return {
        "success": result.success,
        "old_env": result.old_env,
        "new_env": result.new_env,
        "switched_modules": result.switched_modules,
        "timestamp": result.timestamp,
    }


@router.post("/bind")
def bind_module(body: BindRequest):
    """Bind a module to a specific environment."""
    orch = get_hot_swap_orchestrator()
    result = orch.bind_module(body.module_id, body.env_name)
    if not result.get("bound"):
        raise HTTPException(status_code=400, detail=result.get("message", "Bind failed"))
    return result


@router.get("/module/{module_id}")
def get_module_env(module_id: str):
    """Get which environment a module is bound to."""
    orch = get_hot_swap_orchestrator()
    return orch.get_module_env(module_id)


@router.get("/health")
def health_check():
    """Per-environment health check."""
    orch = get_hot_swap_orchestrator()
    return orch.health_check()
