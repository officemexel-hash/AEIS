"""
SYLION API -- Global Build State routes

Provides a single snapshot endpoint for the Operator Console Dashboard Pro.
"""

from fastapi import APIRouter

from sylion.contracts.freeze_manager import get_freeze_manager
from sylion.core.build_state import BuildStateAggregator
from sylion.integration.drift_detector import DriftDetector
from sylion.worker.monitor import WorkerMonitor
from sylion.worker.registry import get_worker_registry

router = APIRouter(prefix="/api/v1")


def _get_aggregator() -> BuildStateAggregator:
    registry = get_worker_registry()
    return BuildStateAggregator(
        registry=registry,
        monitor=WorkerMonitor(registry),
        drift_detector=DriftDetector(),
        freeze_manager=get_freeze_manager(),
    )


@router.get("/build-state")
def build_state_snapshot():
    """Full build factory snapshot for Dashboard Pro."""
    return _get_aggregator().snapshot()
