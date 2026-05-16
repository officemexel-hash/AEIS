"""
SYLION API -- Capacity Planning routes.

Endpoints for the CapacityPlanner module:
  - record_usage, get_usage
  - compute_forecast, get_forecast, list_forecasts
  - get_bottlenecks
  - get_stats
"""

from typing import Optional

from fastapi import APIRouter, Body, HTTPException

from sylion.execution.capacity_planner import get_capacity_planner

router = APIRouter(prefix="/api/v1/capacity", tags=["Capacity Planning"])


# ---------------------------------------------------------------------------
# Usage recording
# ---------------------------------------------------------------------------

@router.post("/usage", status_code=201)
def record_usage(resource_type: str, resource_id: str,
                 metric: str, value: float, unit: str = "units"):
    """Record a resource usage sample."""
    planner = get_capacity_planner()
    try:
        return planner.record_usage(resource_type, resource_id,
                                    metric, value, unit=unit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/usage")
def get_usage(resource_type: Optional[str] = None,
              resource_id: Optional[str] = None,
              metric: Optional[str] = None,
              since: Optional[float] = None,
              limit: int = 1000):
    """Query usage samples with optional filters."""
    planner = get_capacity_planner()
    try:
        return {"usage": planner.get_usage(
            resource_type=resource_type,
            resource_id=resource_id,
            metric=metric,
            since=since,
            limit=limit,
        )}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resources", status_code=201)
def register_resource(body: dict = Body(default_factory=dict)):
    """Compatibility endpoint for UI resource registration panels."""
    resource_type = str(body.get("resource_type") or body.get("type") or "compute")
    resource_type = {
        "worker": "compute",
        "agent": "compute",
        "model": "tokens",
        "llm": "tokens",
        "database": "storage",
        "db": "storage",
    }.get(resource_type, resource_type)
    resource_id = str(body.get("resource_id") or body.get("id") or body.get("name") or "resource")
    metric = str(body.get("metric") or "capacity")
    value = float(body.get("value") or body.get("capacity") or 0)
    unit = str(body.get("unit") or "units")
    planner = get_capacity_planner()
    try:
        sample = planner.record_usage(resource_type, resource_id, metric, value, unit=unit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "resource": {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "metric": metric,
            "value": value,
            "unit": unit,
        },
        "sample": sample,
    }


@router.get("/resources")
def list_resources(limit: int = 1000):
    """Compatibility endpoint returning distinct resources from usage data."""
    planner = get_capacity_planner()
    usage = planner.get_usage(limit=limit)
    resources: dict[str, dict] = {}
    for item in usage:
        resource_type = item.get("resource_type", "generic")
        resource_id = item.get("resource_id", "")
        key = f"{resource_type}:{resource_id}"
        resources[key] = {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "last_metric": item.get("metric"),
            "last_value": item.get("value"),
            "unit": item.get("unit"),
        }
    return {"resources": list(resources.values())}


# ---------------------------------------------------------------------------
# Forecast computation
# ---------------------------------------------------------------------------

@router.post("/forecasts/compute")
def compute_forecast(resource_type: str, resource_id: str,
                     forecast_period: str = "7d"):
    """Compute a capacity forecast from recent usage data."""
    planner = get_capacity_planner()
    try:
        return planner.compute_forecast(resource_type, resource_id,
                                        forecast_period=forecast_period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/forecasts")
def list_forecasts(resource_type: Optional[str] = None,
                   forecast_period: Optional[str] = None,
                   limit: int = 100):
    """List forecasts with optional filters."""
    planner = get_capacity_planner()
    try:
        return {"forecasts": planner.list_forecasts(
            resource_type=resource_type,
            forecast_period=forecast_period,
            limit=limit,
        )}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/forecasts/{resource_type}/{resource_id}")
def get_forecast(resource_type: str, resource_id: str,
                 forecast_period: str = "7d"):
    """Get the latest forecast for a specific resource."""
    planner = get_capacity_planner()
    try:
        result = planner.get_forecast(resource_type, resource_id,
                                      forecast_period=forecast_period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No forecast for {resource_type}/{resource_id} "
                   f"period={forecast_period}",
        )
    return result


@router.get("/resources/{resource_id}/forecast")
def get_resource_forecast(resource_id: str, forecast_period: str = "7d"):
    """Compatibility endpoint for UI callers that do not track resource type."""
    planner = get_capacity_planner()
    usage = planner.get_usage(resource_id=resource_id, limit=1)
    resource_type = usage[0].get("resource_type", "generic") if usage else "generic"
    result = planner.get_forecast(resource_type, resource_id, forecast_period=forecast_period)
    if result:
        return result
    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "forecast_period": forecast_period,
        "status": "insufficient_data",
        "forecast": [],
    }


# ---------------------------------------------------------------------------
# Bottleneck detection
# ---------------------------------------------------------------------------

@router.get("/bottlenecks")
def get_bottlenecks(headroom_threshold: float = 0.2):
    """Return resources whose headroom is below the threshold."""
    planner = get_capacity_planner()
    return {"bottlenecks": planner.get_bottlenecks(
        headroom_threshold=headroom_threshold,
    )}


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_stats():
    """Return aggregate capacity planning statistics."""
    planner = get_capacity_planner()
    return planner.get_stats()
