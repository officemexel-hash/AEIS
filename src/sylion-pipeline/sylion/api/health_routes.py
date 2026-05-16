"""
SYLION API -- Health Monitoring routes.

Endpoints for module health monitoring based on heartbeats.
"""

from fastapi import APIRouter, HTTPException

from sylion.core.module_registry import get_registry
from sylion.core.event_bus import get_event_bus
from sylion.core.health_monitor import get_health_monitor

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/modules")
def get_all_module_health():
    """Get health status of all registered modules."""
    registry = get_registry()
    monitor = get_health_monitor(registry=registry)
    results = monitor.check_all()
    return {"modules": results, "total": len(results)}


@router.get("/modules/{module_id}")
def get_module_health(module_id: str):
    """Get health status of a single module."""
    registry = get_registry()
    monitor = get_health_monitor(registry=registry)
    health = monitor.check_health(module_id)
    if health["status"] == "unknown" and registry.get(module_id) is None:
        raise HTTPException(status_code=404, detail=f"Module {module_id} not found")
    return health


@router.post("/modules/{module_id}/heartbeat")
def record_heartbeat(module_id: str):
    """Record a heartbeat for a module."""
    registry = get_registry()
    event_bus = get_event_bus()
    monitor = get_health_monitor(registry=registry, event_bus=event_bus)
    result = monitor.record_heartbeat(module_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/stats")
def get_health_stats():
    """Get aggregate health statistics."""
    registry = get_registry()
    monitor = get_health_monitor(registry=registry)
    return monitor.get_stats()


@router.get("/database")
async def get_database_health():
    """Check PostgreSQL database connectivity (if configured)."""
    import os
    db_url = os.environ.get("SYLION_DB_URL", "")
    if not db_url:
        return {"status": "sqlite", "mode": "local", "message": "PostgreSQL not configured"}
    try:
        from sylion.db.pg_migration import check_pg_health
        result = await check_pg_health()
        return result
    except Exception as exc:
        return {"status": "error", "mode": "postgres", "error": str(exc)}


@router.get("/grpc")
def get_grpc_health():
    """Check gRPC service availability."""
    try:
        from sylion.grpc.core_server import create_grpc_server
        return {"status": "available", "services": [
            "ModuleRegistryService", "EvidenceSpineService", "EventBusService",
            "WorkflowService", "JobService", "ModelRouterService", "PlanService",
            "GovernanceService", "CouncilService", "AutonomyService",
            "ExplanationService", "ImprovementService",
        ]}
    except ImportError:
        return {"status": "unavailable", "reason": "gRPC stubs not installed"}
