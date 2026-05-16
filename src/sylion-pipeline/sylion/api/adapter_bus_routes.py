"""
SYLION API -- Adapter Bus routes.

Endpoints for the AdapterBus module:
  register_adapter, update_adapter, deregister_adapter,
  get_adapter, list_adapters,
  add_route, remove_route, list_routes,
  transform_data,
  get_adapter_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/adapters", tags=["Adapters"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_bus = None


def _get_bus():
    global _bus
    if _bus is not None:
        return _bus
    from sylion.execution.adapter_bus import get_adapter_bus
    _bus = get_adapter_bus()
    return _bus


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RegisterAdapterRequest(BaseModel):
    name: str
    protocol: str = "json"
    config_json: dict | None = None


class UpdateAdapterRequest(BaseModel):
    name: str | None = None
    protocol: str | None = None
    config: dict | None = None
    status: str | None = None


class AddRouteRequest(BaseModel):
    adapter_id: str
    source_format: str
    target_format: str
    transform_json: dict | None = None


class TransformDataRequest(BaseModel):
    data_json: dict | None = None


# ---------------------------------------------------------------------------
# Create / List
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def register_adapter(body: RegisterAdapterRequest):
    """Register a new adapter."""
    bus = _get_bus()
    return bus.register_adapter(
        name=body.name,
        protocol=body.protocol,
        config_json=body.config_json,
    )


@router.get("/list")
def list_adapters(protocol: str | None = None):
    """List adapters, optionally filtered by protocol."""
    bus = _get_bus()
    return {"adapters": bus.list_adapters(protocol=protocol)}


@router.get("/stats")
def get_adapter_stats():
    """Aggregate adapter statistics."""
    bus = _get_bus()
    return bus.get_adapter_stats()


# ---------------------------------------------------------------------------
# Single adapter -- static paths before dynamic /{adapter_id} paths
# ---------------------------------------------------------------------------

@router.get("/{adapter_id}")
def get_adapter(adapter_id: str):
    """Get a single adapter by ID."""
    bus = _get_bus()
    result = bus.get_adapter(adapter_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Adapter {adapter_id} not found")
    return result


@router.patch("/{adapter_id}")
def update_adapter(adapter_id: str, body: UpdateAdapterRequest):
    """Update mutable adapter fields."""
    bus = _get_bus()
    try:
        result = bus.update_adapter(adapter_id, **body.model_dump(exclude_none=True))
        if not result:
            raise HTTPException(status_code=404, detail=f"Adapter {adapter_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{adapter_id}")
def deregister_adapter(adapter_id: str):
    """Remove an adapter and all associated routes/logs."""
    bus = _get_bus()
    ok = bus.deregister_adapter(adapter_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Adapter {adapter_id} not found")
    return {"deleted": True, "adapter_id": adapter_id}


# ---------------------------------------------------------------------------
# Route management
# ---------------------------------------------------------------------------

@router.get("/routes/list")
def list_routes(adapter_id: str | None = None):
    """List routes, optionally filtered by adapter."""
    bus = _get_bus()
    return {"routes": bus.list_routes(adapter_id=adapter_id)}


@router.post("/routes", status_code=201)
def add_route(body: AddRouteRequest):
    """Add a format-mapping route to an adapter."""
    bus = _get_bus()
    try:
        return bus.add_route(
            adapter_id=body.adapter_id,
            source_format=body.source_format,
            target_format=body.target_format,
            transform_json=body.transform_json,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/routes/{route_id}")
def remove_route(route_id: str):
    """Remove a route by ID."""
    bus = _get_bus()
    ok = bus.remove_route(route_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
    return {"deleted": True, "route_id": route_id}


# ---------------------------------------------------------------------------
# Transform execution
# ---------------------------------------------------------------------------

@router.post("/routes/{route_id}/transform")
def transform_data(route_id: str, body: TransformDataRequest):
    """Execute a transform using a route's spec."""
    bus = _get_bus()
    try:
        result = bus.transform_data(route_id, data_json=body.data_json)
        if not result.get("success"):
            raise HTTPException(status_code=422, detail=result.get("error", "transform failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
