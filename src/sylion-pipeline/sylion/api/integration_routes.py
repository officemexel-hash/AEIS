"""
SYLION API -- Integration Controller routes.

Endpoints for the IntegrationController module:
  register_integration, update_integration, deregister_integration,
  get_integration, list_integrations, record_event, get_events,
  check_health, get_health_history, get_integration_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/integrations", tags=["Integrations"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_integration_controller = None


def _get_integration_controller():
    global _integration_controller
    if _integration_controller is not None:
        return _integration_controller
    from sylion.aeis.integration_controller import get_integration_controller
    _integration_controller = get_integration_controller()
    return _integration_controller


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RegisterIntegrationRequest(BaseModel):
    name: str
    integration_type: str = "custom"
    config: dict | None = None


class UpdateIntegrationRequest(BaseModel):
    name: str | None = None
    integration_type: str | None = None
    config: dict | None = None


class RecordEventRequest(BaseModel):
    event_type: str
    payload: dict | None = None


class CheckHealthRequest(BaseModel):
    status: str = "healthy"
    details: str = ""


# ---------------------------------------------------------------------------
# Integration CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def register_integration(body: RegisterIntegrationRequest):
    """Register a new integration."""
    ctrl = _get_integration_controller()
    try:
        return ctrl.register_integration(
            name=body.name,
            integration_type=body.integration_type,
            config=body.config,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{integration_id}")
def update_integration(integration_id: str, body: UpdateIntegrationRequest):
    """Update an integration."""
    ctrl = _get_integration_controller()
    try:
        result = ctrl.update_integration(
            integration_id=integration_id,
            name=body.name,
            integration_type=body.integration_type,
            config=body.config,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Integration {integration_id} not found")
    return result


@router.delete("/{integration_id}")
def deregister_integration(integration_id: str):
    """Deregister an integration and its events/health records."""
    ctrl = _get_integration_controller()
    deregistered = ctrl.deregister_integration(integration_id)
    if not deregistered:
        raise HTTPException(status_code=404,
                            detail=f"Integration {integration_id} not found")
    return {"deregistered": True}


# ---------------------------------------------------------------------------
# Retrieval -- static paths before dynamic /{integration_id} paths
# ---------------------------------------------------------------------------

@router.get("")
def list_integrations(
    integration_type: str | None = None,
    limit: int = 100,
):
    """List integrations with optional type filter."""
    ctrl = _get_integration_controller()
    try:
        return ctrl.list_integrations(
            integration_type=integration_type,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stats")
def get_integration_stats():
    """Aggregate integration statistics."""
    ctrl = _get_integration_controller()
    return ctrl.get_integration_stats()


@router.get("/{integration_id}")
def get_integration(integration_id: str):
    """Retrieve a single integration by ID."""
    ctrl = _get_integration_controller()
    result = ctrl.get_integration(integration_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Integration {integration_id} not found")
    return result


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@router.post("/{integration_id}/events", status_code=201)
def record_event(integration_id: str, body: RecordEventRequest):
    """Record an integration event."""
    ctrl = _get_integration_controller()
    result = ctrl.record_event(
        integration_id=integration_id,
        event_type=body.event_type,
        payload=body.payload,
    )
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Integration {integration_id} not found")
    return result


@router.get("/{integration_id}/events")
def get_events(integration_id: str, limit: int = 50):
    """Get events for an integration."""
    ctrl = _get_integration_controller()
    return {"events": ctrl.get_events(integration_id, limit=limit)}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.post("/{integration_id}/health", status_code=201)
def check_health(integration_id: str, body: CheckHealthRequest):
    """Record a health check for an integration."""
    ctrl = _get_integration_controller()
    try:
        result = ctrl.check_health(
            integration_id=integration_id,
            status=body.status,
            details=body.details,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Integration {integration_id} not found")
    return result


@router.get("/{integration_id}/health")
def get_health_history(integration_id: str, limit: int = 50):
    """Get health check history for an integration."""
    ctrl = _get_integration_controller()
    return {"history": ctrl.get_health_history(integration_id, limit=limit)}
