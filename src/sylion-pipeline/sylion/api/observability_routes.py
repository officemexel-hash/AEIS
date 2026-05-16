"""
SYLION API -- Observability Hub routes

Unified metrics, traces, and logs endpoint.
"""

from fastapi import APIRouter

from sylion.infra.cache import cached
from sylion.observability.hub import ObservabilityHub
from sylion.observability.log_aggregator import LogAggregator

router = APIRouter(prefix="/api/v1")

_hub: ObservabilityHub | None = None


def _get_hub() -> ObservabilityHub:
    global _hub
    if _hub is None:
        _hub = ObservabilityHub(log_aggregator=LogAggregator())
    return _hub


@router.get("/observability/snapshot")
def observability_snapshot():
    """Full observability snapshot."""
    return _get_hub().snapshot()


@router.post("/observability/logs")
def emit_log(body: dict):
    """Emit a structured log entry."""
    _get_hub().log(
        service=body.get("service", "unknown"),
        level=body.get("level", "info"),
        message=body.get("message", ""),
        extra=body.get("extra"),
    )
    return {"logged": True}


@router.get("/observability/logs")
def query_logs(service: str | None = None, level: str | None = None, limit: int = 100):
    """Query aggregated logs."""
    return {"logs": _get_hub()._log.query(service, level, limit)}


@router.post("/observability/metrics/{name}")
def record_metric(name: str, body: dict):
    """Record a metric value."""
    _get_hub().record_metric(name, float(body.get("value", 0)))
    return {"recorded": name}


@router.get("/observability/metrics/{name}")
def get_metric(name: str, limit: int = 100):
    """Get metric time series."""
    return {"metric": name, "points": _get_hub().get_metric(name, limit)}


@router.get("/observability/metrics")
@cached("observability.metrics", key_fn=lambda: ("list",))
def list_metrics():
    """List all known metric names."""
    return {"metrics": _get_hub().list_metrics()}


@router.post("/observability/traces/{trace_id}/start")
def start_trace(trace_id: str, body: dict):
    """Start a distributed trace."""
    _get_hub().start_trace(
        trace_id=trace_id,
        operation=body.get("operation", "unknown"),
        service=body.get("service", "unknown"),
    )
    return {"trace_id": trace_id, "status": "started"}


@router.post("/observability/traces/{trace_id}/end")
def end_trace(trace_id: str, body: dict | None = None):
    """End a distributed trace."""
    _get_hub().end_trace(
        trace_id=trace_id,
        status=(body or {}).get("status", "ok"),
    )
    return {"trace_id": trace_id, "status": "ended"}


@router.get("/observability/traces")
def list_traces(service: str | None = None, limit: int = 50):
    """List recent traces."""
    return {"traces": _get_hub().list_traces(service, limit)}
