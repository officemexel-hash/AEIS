"""
SYLION Core -- Global Build State Aggregator

Aggregates the full state of the build factory:
  - worker fleet status
  - assignments per worker
  - integration build pipeline
  - drift summary
  - frozen contracts
  - recent alerts
  - governance decisions pending

Provides a single snapshot for the Operator Console Dashboard Pro.
"""

from __future__ import annotations

import threading
from typing import Any

from sylion.contracts.freeze_manager import ContractFreezeManager
from sylion.integration.drift_detector import DriftDetector
from sylion.worker.monitor import WorkerMonitor
from sylion.worker.registry import WorkerRegistry


class BuildStateAggregator:
    """Aggregates global build state from all subsystems."""

    def __init__(
        self,
        registry: WorkerRegistry,
        monitor: WorkerMonitor | None = None,
        drift_detector: DriftDetector | None = None,
        freeze_manager: ContractFreezeManager | None = None,
    ):
        self._registry = registry
        self._monitor = monitor
        self._drift = drift_detector
        self._freeze = freeze_manager
        self._lock = threading.RLock()

    def snapshot(self) -> dict[str, Any]:
        """Return a full snapshot of the build factory state."""
        with self._lock:
            workers = self._registry.list_workers()
            assignments = []
            for w in workers:
                assignments.extend(
                    self._registry.list_assignments(worker_id=w["worker_id"])
                    if hasattr(self._registry, "list_assignments")
                    else []
                )

            assigned_assignments = [a for a in assignments if a.get("status") == "assigned"]
            in_progress_assignments = [a for a in assignments if a.get("status") == "in_progress"]
            completed_assignments = [a for a in assignments if a.get("status") == "completed"]

            alerts = []
            if self._monitor:
                alerts = self._monitor.list_alerts(unresolved_only=True)

            drift = []
            if self._drift:
                drift = self._drift.detect_all()

            freeze = {}
            if self._freeze:
                freeze = self._freeze.status()

            return {
                "timestamp": __import__("time").time(),
                "workers": {
                    "total": len(workers),
                    "active": len([w for w in workers if w.get("status") == "active"]),
                    "offline": len([w for w in workers if w.get("status") == "offline"]),
                    "list": workers,
                },
                "assignments": {
                    "total": len(assignments),
                    "assigned": len(assigned_assignments),
                    "in_progress": len(in_progress_assignments),
                    "completed": len(completed_assignments),
                },
                "alerts": {
                    "total_unresolved": len(alerts),
                    "list": alerts[:10],  # limit snapshot size
                },
                "drift": {
                    "total_open": len(drift),
                    "critical": len([d for d in drift if d.get("severity") == "critical"]),
                },
                "contracts": freeze,
                "build_factory_ready": freeze.get("frozen", False) and len(workers) > 0,
            }
