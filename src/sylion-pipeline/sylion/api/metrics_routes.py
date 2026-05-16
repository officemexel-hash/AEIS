"""
SYLION API -- Metrics Routes

Exposes /metrics in Prometheus text format.

Hook v1.0 (2026-04-24)
Changes: initial; router is mounted by the main API router and metrics are seeded on module load.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from sylion.observability.metrics_registry import get_metrics_registry
from sylion.observability.prometheus_exporter import seed_metrics, update_live_gauges

router = APIRouter(prefix="/api/v1", tags=["metrics"])

# Seed metrics on module load (idempotent)
seed_metrics()


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus exposition endpoint."""
    update_live_gauges()
    reg = get_metrics_registry()
    return Response(
        content=reg.generate_latest(),
        media_type=reg.content_type,
    )
