"""
SYLION API -- Worker Monitor routes

Endpoints for worker health monitoring and alerts.
"""

from fastapi import APIRouter, HTTPException

from sylion.worker.monitor import WorkerMonitor
from sylion.worker.registry import get_worker_registry

router = APIRouter(prefix="/api/v1/workers")


def _get_monitor() -> WorkerMonitor:
    return WorkerMonitor(registry=get_worker_registry())


@router.post("/monitor/check")
def check_workers():
    """Run health checks on all workers and return new alerts."""
    monitor = _get_monitor()
    alerts = monitor.check_all()
    return {"checked": len(alerts), "alerts": [monitor._to_dict(a) for a in alerts]}


@router.get("/monitor/alerts")
def list_alerts(worker_id: str | None = None, unresolved_only: bool = False):
    """List worker alerts with optional filters."""
    monitor = _get_monitor()
    return {"alerts": monitor.list_alerts(worker_id=worker_id, unresolved_only=unresolved_only)}


@router.post("/monitor/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: str):
    """Resolve a worker alert."""
    monitor = _get_monitor()
    if monitor.resolve_alert(alert_id):
        return {"resolved": alert_id}
    raise HTTPException(status_code=404, detail="Alert not found")
