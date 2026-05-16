"""
SYLION API -- Connector Framework routes.

Endpoints for the ConnectorFramework module:
  register_connector, update_connector, deregister_connector,
  get_connector, list_connectors,
  get_config, update_config,
  check_health, record_health, get_health_history,
  get_connector_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/connectors", tags=["Connectors"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_framework = None


def _get_framework():
    global _framework
    if _framework is not None:
        return _framework
    from sylion.execution.connector_framework import get_connector_framework
    _framework = get_connector_framework()
    return _framework


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RegisterConnectorRequest(BaseModel):
    name: str
    connector_type: str = "api"
    config_json: dict | None = None


class UpdateConnectorRequest(BaseModel):
    name: str | None = None
    connector_type: str | None = None
    status: str | None = None


class UpdateConfigRequest(BaseModel):
    config_json: dict


class RecordHealthRequest(BaseModel):
    status: str
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Create / List
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def register_connector(body: RegisterConnectorRequest):
    """Register a new external connector."""
    fw = _get_framework()
    return fw.register_connector(
        name=body.name,
        connector_type=body.connector_type,
        config_json=body.config_json,
    )


@router.get("/list")
def list_connectors(connector_type: str | None = None):
    """List connectors, optionally filtered by type."""
    fw = _get_framework()
    return {"connectors": fw.list_connectors(connector_type=connector_type)}


@router.get("/stats")
def get_connector_stats():
    """Aggregate connector statistics."""
    fw = _get_framework()
    return fw.get_connector_stats()


# ---------------------------------------------------------------------------
# Single connector -- static paths before dynamic /{connector_id} paths
# ---------------------------------------------------------------------------

@router.get("/{connector_id}")
def get_connector(connector_id: str):
    """Get a single connector with its current config."""
    fw = _get_framework()
    result = fw.get_connector(connector_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Connector {connector_id} not found")
    return result


@router.patch("/{connector_id}")
def update_connector(connector_id: str, body: UpdateConnectorRequest):
    """Update mutable connector fields."""
    fw = _get_framework()
    try:
        result = fw.update_connector(connector_id, **body.model_dump(exclude_none=True))
        if not result:
            raise HTTPException(status_code=404, detail=f"Connector {connector_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{connector_id}")
def deregister_connector(connector_id: str):
    """Remove a connector and all associated data."""
    fw = _get_framework()
    ok = fw.deregister_connector(connector_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Connector {connector_id} not found")
    return {"deleted": True, "connector_id": connector_id}


# ---------------------------------------------------------------------------
# Config management
# ---------------------------------------------------------------------------

@router.get("/{connector_id}/config")
def get_config(connector_id: str):
    """Get the latest config for a connector."""
    fw = _get_framework()
    result = fw.get_config(connector_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Config for connector {connector_id} not found")
    return result


@router.put("/{connector_id}/config")
def update_config(connector_id: str, body: UpdateConfigRequest):
    """Create a new config version for a connector."""
    fw = _get_framework()
    ok = fw.update_config(connector_id, body.config_json)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Connector {connector_id} not found")
    return {"updated": True, "connector_id": connector_id}


# ---------------------------------------------------------------------------
# Health tracking
# ---------------------------------------------------------------------------

@router.get("/{connector_id}/health")
def check_health(connector_id: str):
    """Return the most recent health record for a connector."""
    fw = _get_framework()
    result = fw.check_health(connector_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No health data for connector {connector_id}")
    return result


@router.post("/{connector_id}/health", status_code=201)
def record_health(connector_id: str, body: RecordHealthRequest):
    """Record a health-check result for a connector."""
    fw = _get_framework()
    try:
        return fw.record_health(connector_id, status=body.status, latency_ms=body.latency_ms)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{connector_id}/health/history")
def get_health_history(connector_id: str, limit: int = 50):
    """Return recent health records for a connector."""
    fw = _get_framework()
    return {"history": fw.get_health_history(connector_id, limit=limit)}
