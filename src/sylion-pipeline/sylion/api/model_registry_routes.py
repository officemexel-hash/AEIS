"""
SYLION API -- Model Registry routes.

Endpoints for ModelRegistry:
  register_model, update_model, deregister_model, get_model, list_models,
  add_capability, remove_capability, record_performance, get_performance,
  get_model_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/model-registry", tags=["Model Registry"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_registry = None


def _get_registry():
    global _registry
    if _registry is not None:
        return _registry
    from sylion.cognitive.model_registry import get_model_registry
    _registry = get_model_registry()
    return _registry


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RegisterModelRequest(BaseModel):
    model_id: str
    provider: str
    display_name: str
    config_json: str = "{}"


class UpdateModelRequest(BaseModel):
    provider: str | None = None
    display_name: str | None = None
    config_json: str | None = None


class AddCapabilityRequest(BaseModel):
    model_id: str
    capability: str
    metadata_json: str = "{}"


class RecordPerformanceRequest(BaseModel):
    model_id: str
    metrics_json: str = "{}"


# ---------------------------------------------------------------------------
# Model CRUD
# ---------------------------------------------------------------------------

@router.post("/models", status_code=201)
def register_model(body: RegisterModelRequest):
    """Register a new model or update an existing one."""
    try:
        return _get_registry().register_model(
            model_id=body.model_id,
            provider=body.provider,
            display_name=body.display_name,
            config_json=body.config_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/models/{model_id}")
def update_model(model_id: str, body: UpdateModelRequest):
    """Update mutable fields on a model."""
    fields = {}
    if body.provider is not None:
        fields["provider"] = body.provider
    if body.display_name is not None:
        fields["display_name"] = body.display_name
    if body.config_json is not None:
        fields["config_json"] = body.config_json
    try:
        result = _get_registry().update_model(model_id, **fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return result


@router.delete("/models/{model_id}")
def deregister_model(model_id: str):
    """Soft-delete a model (sets is_active = 0)."""
    ok = _get_registry().deregister_model(model_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found or already inactive")
    return {"model_id": model_id, "deregistered": True}


# ---------------------------------------------------------------------------
# Listing -- static paths before dynamic /{model_id}
# ---------------------------------------------------------------------------

@router.get("/models")
def list_models(provider: str | None = None, capability: str | None = None):
    """List active models with optional filters."""
    return {"models": _get_registry().list_models(
        provider=provider, capability=capability,
    )}


@router.get("/models/stats")
def get_model_stats():
    """Aggregate registry statistics."""
    return _get_registry().get_model_stats()


@router.get("/models/{model_id}")
def get_model(model_id: str):
    """Retrieve a single active model by ID."""
    result = _get_registry().get_model(model_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return result


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

@router.post("/capabilities", status_code=201)
def add_capability(body: AddCapabilityRequest):
    """Add a capability to a model."""
    try:
        return _get_registry().add_capability(
            model_id=body.model_id,
            capability=body.capability,
            metadata_json=body.metadata_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/capabilities/{capability_id}")
def remove_capability(capability_id: str):
    """Remove a capability by ID."""
    ok = _get_registry().remove_capability(capability_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Capability {capability_id} not found")
    return {"capability_id": capability_id, "removed": True}


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

@router.post("/performance", status_code=201)
def record_performance(body: RecordPerformanceRequest):
    """Record a performance snapshot for a model."""
    try:
        return _get_registry().record_performance(
            model_id=body.model_id,
            metrics_json=body.metrics_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/models/{model_id}/performance")
def get_performance(model_id: str, limit: int = 100):
    """Get performance snapshots for a model."""
    return {"snapshots": _get_registry().get_performance(
        model_id=model_id, limit=limit,
    )}


# ---------------------------------------------------------------------------
# Alias router for /api/v1/registry/* (frontend compatibility)
# ---------------------------------------------------------------------------

alias_router = APIRouter(prefix="/api/v1/registry", tags=["Model Registry"])


@alias_router.get("/models")
def alias_list_models(provider: str | None = None,
                      capability: str | None = None,
                      status: str | None = None,
                      limit: int = 100):
    _ = status, limit  # underlying registry ignores status/limit
    return list_models(provider=provider, capability=capability)


@alias_router.post("/models", status_code=201)
def alias_register_model(body: RegisterModelRequest):
    return register_model(body=body)


@alias_router.get("/models/{model_id}")
def alias_get_model(model_id: str):
    return get_model(model_id=model_id)


@alias_router.delete("/models/{model_id}")
def alias_deregister_model(model_id: str):
    return deregister_model(model_id=model_id)


@alias_router.post("/models/{model_id}/performance", status_code=201)
def alias_record_performance(model_id: str, body: RecordPerformanceRequest):
    return record_performance(model_id=model_id, body=body)
