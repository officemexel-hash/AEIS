"""
SYLION API -- Efficiency routes.

Endpoints for: memory_footprint, runtime_perf, performance_budget.
(Code bloat is already in monitoring_routes.py)
"""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import StreamingResponse

from sylion.efficiency.memory_footprint import get_memory_footprint_tracker
from sylion.efficiency.runtime_perf import get_runtime_perf_tracker

# Lazy imports let the API report module availability without failing startup.
try:
    from sylion.efficiency.performance_budget import get_performance_budget_manager
    _HAS_PERF_BUDGET = True
except ImportError:
    _HAS_PERF_BUDGET = False

router = APIRouter(prefix="/api/v1/efficiency", tags=["efficiency"])


# ---------------------------------------------------------------------------
# Memory Footprint Tracker
# ---------------------------------------------------------------------------

@router.post("/memory/snapshots", status_code=201)
def memory_snapshot(module_id: str, rss: int = 0, heap: int = 0,
                    peak: int = 0, gc: int = 0):
    """Record a memory footprint snapshot for a module."""
    tracker = get_memory_footprint_tracker()
    return tracker.snapshot(module_id, rss=rss, heap=heap, peak=peak, gc=gc)


@router.get("/memory/snapshots/{module_id}")
def get_memory_snapshots(module_id: str, limit: int = 50):
    """Get memory snapshots for a module."""
    tracker = get_memory_footprint_tracker()
    return {"snapshots": tracker.get_snapshots(module_id, limit=limit)}


@router.get("/memory/current/{module_id}")
def get_current_memory(module_id: str):
    """Get the current memory footprint for a module."""
    tracker = get_memory_footprint_tracker()
    result = tracker.get_current(module_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Module {module_id} not tracked")
    return result


@router.post("/memory/budgets")
def set_memory_budget(module_id: str, max_rss: int = 0, max_heap: int = 0):
    """Set memory budget for a module."""
    tracker = get_memory_footprint_tracker()
    return tracker.set_budget(module_id, max_rss=max_rss, max_heap=max_heap)


@router.get("/memory/budgets/{module_id}")
def check_memory_budget(module_id: str):
    """Check if a module is within its memory budget."""
    tracker = get_memory_footprint_tracker()
    return tracker.check_budget(module_id)


@router.get("/memory/leaks/{module_id}")
def detect_memory_leaks(module_id: str, window: int = 10):
    """Detect potential memory leaks for a module."""
    tracker = get_memory_footprint_tracker()
    return tracker.detect_leaks(module_id, window=window)


# ---------------------------------------------------------------------------
# Runtime Performance Tracker
# ---------------------------------------------------------------------------

@router.post("/perf/measurements", status_code=201)
def record_perf_measurement(endpoint: str, latency_ms: int,
                            p50: int = 0, p95: int = 0, p99: int = 0,
                            error_rate: float = 0.0, throughput: float = 0.0):
    """Record a runtime performance measurement."""
    tracker = get_runtime_perf_tracker()
    return tracker.record(endpoint, latency_ms, p50=p50, p95=p95, p99=p99,
                          error_rate=error_rate, throughput=throughput)


@router.get("/perf/measurements/{endpoint}")
def get_perf_measurements(endpoint: str, limit: int = 100):
    """Get performance measurements for an endpoint."""
    tracker = get_runtime_perf_tracker()
    return {"measurements": tracker.get_measurements(endpoint, limit=limit)}


@router.post("/perf/slos", status_code=201)
def define_slo(endpoint: str, target_p95_ms: int = 100,
               target_error_rate: float = 0.01, description: str = ""):
    """Define an SLO for an endpoint."""
    tracker = get_runtime_perf_tracker()
    return tracker.define_slo(endpoint, target_p95_ms=target_p95_ms,
                              target_error_rate=target_error_rate,
                              description=description)


@router.get("/perf/slos")
def list_slos():
    """List all defined SLOs."""
    tracker = get_runtime_perf_tracker()
    return {"slos": tracker.list_slos()}


@router.get("/perf/slos/{endpoint}")
def check_slo(endpoint: str):
    """Check SLO compliance for an endpoint."""
    tracker = get_runtime_perf_tracker()
    return tracker.check_slo(endpoint)


@router.get("/perf/stats/{endpoint}")
def perf_stats(endpoint: str):
    """Get performance statistics for an endpoint."""
    tracker = get_runtime_perf_tracker()
    return tracker.get_stats(endpoint)


# ---------------------------------------------------------------------------
# Performance Budget Manager
# ---------------------------------------------------------------------------

@router.get("/budgets")
def list_performance_budgets(module_class: str | None = None):
    """List performance budgets across modules."""
    if not _HAS_PERF_BUDGET:
        return {"budgets": [], "message": "performance_budget module not available"}
    mgr = get_performance_budget_manager()
    return {"budgets": mgr.list_budgets(module_class=module_class)}


@router.get("/budgets/over")
def list_over_budget_modules():
    """List modules currently over their performance budget."""
    if not _HAS_PERF_BUDGET:
        return {"over_budget": [], "message": "performance_budget module not available"}
    mgr = get_performance_budget_manager()
    return {"over_budget": mgr.list_over_budget()}


# ---------------------------------------------------------------------------
# Config Drift
# ---------------------------------------------------------------------------

@router.get("/drift")
def config_drift_status():
    """Get config drift status across modules.

    Returns drift detection results when the config_drift module is available.
    """
    try:
        from sylion.efficiency.config_drift import get_config_drift_tracker
        tracker = get_config_drift_tracker()
        return tracker.get_drift_status()
    except ImportError:
        return {
            "drift_detected": False,
            "modules_checked": 0,
            "drifts": [],
            "available": False,
            "message": "config_drift tracker unavailable in this runtime",
        }


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

@router.get("/circuits")
def circuit_breaker_status():
    """Get circuit breaker status.

    Returns circuit breaker states when the module is available.
    """
    try:
        from sylion.efficiency.circuit_breaker import get_circuit_breaker_manager
        mgr = get_circuit_breaker_manager()
        return mgr.get_all_states()
    except ImportError:
        return {
            "circuits": {},
            "available": False,
            "message": "circuit_breaker manager unavailable in this runtime",
        }


# ── Cost Envelope ──────────────────────────────────────────────────────────────

@router.post("/cost/records")
def record_cost(provider: str, model_id: str = "", input_tokens: int = 0, output_tokens: int = 0, cost_usd: float = 0.0, task_type: str = ""):
    try:
        from sylion.efficiency.cost_envelope import get_cost_envelope_tracker
        svc = get_cost_envelope_tracker()
        return svc.record(provider, model_id, input_tokens, output_tokens, cost_usd, task_type)
    except ImportError:
        raise HTTPException(501, "cost_envelope not available")


@router.post("/cost/budgets")
def set_cost_budget(provider: str, daily_limit: float = 100.0, monthly_limit: float = 3000.0, alert_threshold: float = 0.8):
    try:
        from sylion.efficiency.cost_envelope import get_cost_envelope_tracker
        svc = get_cost_envelope_tracker()
        return svc.set_budget(provider, daily_limit, monthly_limit, alert_threshold)
    except ImportError:
        raise HTTPException(501, "cost_envelope not available")


@router.get("/cost/budgets/{provider}")
def check_cost_budget(provider: str):
    try:
        from sylion.efficiency.cost_envelope import get_cost_envelope_tracker
        svc = get_cost_envelope_tracker()
        return svc.check_budget(provider)
    except ImportError:
        raise HTTPException(501, "cost_envelope not available")


@router.get("/cost/records")
def list_cost_records(provider: str | None = None, limit: int = 100):
    try:
        from sylion.efficiency.cost_envelope import get_cost_envelope_tracker
        svc = get_cost_envelope_tracker()
        records = svc.get_records(provider=provider, limit=limit)
        return {"records": records}
    except ImportError:
        raise HTTPException(501, "cost_envelope not available")


@router.get("/cost/daily")
def get_daily_spend(provider: str | None = None):
    try:
        from sylion.efficiency.cost_envelope import get_cost_envelope_tracker
        svc = get_cost_envelope_tracker()
        return {"daily_spend": svc.get_daily_spend(provider)}
    except ImportError:
        raise HTTPException(501, "cost_envelope not available")


@router.get("/cost/monthly")
def get_monthly_spend(provider: str | None = None):
    try:
        from sylion.efficiency.cost_envelope import get_cost_envelope_tracker
        svc = get_cost_envelope_tracker()
        return {"monthly_spend": svc.get_monthly_spend(provider)}
    except ImportError:
        raise HTTPException(501, "cost_envelope not available")


# ── Live Cost Monitor (SSE) ────────────────────────────────────────────────────

try:
    from sylion.efficiency.cost_monitor import get_cost_monitor
    _HAS_COST_MONITOR = True
except ImportError:
    _HAS_COST_MONITOR = False


@router.get("/cost/stream")
async def cost_sse_stream(request: Request):
    """SSE endpoint for real-time cost alert push.

    Clients connect and receive ``data: {json}\\n\\n`` frames for each
    new CostAlert generated by the monitoring system.
    """
    if not _HAS_COST_MONITOR:
        raise HTTPException(501, "cost_monitor module not available")

    monitor = get_cost_monitor()
    queue = monitor.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"
        finally:
            monitor.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/cost/alerts")
def get_cost_alerts(limit: int = 50):
    """Return recent cost alerts, newest first."""
    if not _HAS_COST_MONITOR:
        raise HTTPException(501, "cost_monitor module not available")
    monitor = get_cost_monitor()
    return {"alerts": monitor.get_alerts(limit=limit)}


@router.get("/cost/summary")
def get_cost_summary():
    """Return per-provider realtime spend, budget remaining, and health status."""
    if not _HAS_COST_MONITOR:
        raise HTTPException(501, "cost_monitor module not available")
    monitor = get_cost_monitor()
    return monitor.get_realtime_summary()


@router.post("/cost/check")
def trigger_budget_check():
    """Manually trigger a budget check and return generated alerts.

    Primarily for testing and manual verification.
    """
    if not _HAS_COST_MONITOR:
        raise HTTPException(501, "cost_monitor module not available")
    monitor = get_cost_monitor()
    alerts = monitor.check_budgets()
    return {
        "alerts_generated": len(alerts),
        "alerts": [a.to_dict() for a in alerts],
    }
