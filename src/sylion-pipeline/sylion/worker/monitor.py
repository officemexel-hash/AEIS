"""
SYLION Worker -- Monitoring & Alerting

Tracks worker health metrics and emits alerts for:
  - stale heartbeat (no heartbeat within threshold)
  - overloaded worker (assignments >= capacity * threshold)
  - budget exhaustion (budget_spent >= budget_limit * 0.9)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from sylion.worker.registry import WorkerRegistry


@dataclass
class WorkerAlert:
    alert_id: str
    worker_id: str
    alert_type: str  # stale_heartbeat | overloaded | budget_warning
    severity: str    # info | warning | critical
    message: str
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False


class WorkerMonitor:
    """Monitors worker fleet and produces alerts."""

    def __init__(
        self,
        registry: WorkerRegistry,
        heartbeat_threshold_sec: float = 120.0,
        overload_ratio: float = 0.9,
        budget_warning_ratio: float = 0.9,
    ):
        self._registry = registry
        self._heartbeat_threshold = heartbeat_threshold_sec
        self._overload_ratio = overload_ratio
        self._budget_warning_ratio = budget_warning_ratio
        self._alerts: list[WorkerAlert] = []
        self._lock = threading.RLock()
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"wa_{self._counter:06d}"

    def check_all(self) -> list[WorkerAlert]:
        """Run health checks on all active workers and return new alerts."""
        now = time.time()
        new_alerts: list[WorkerAlert] = []
        with self._lock:
            for worker in self._registry.list_workers(status="active"):
                wid = worker["worker_id"]
                # Stale heartbeat
                last_hb = worker.get("last_heartbeat")
                if last_hb and (now - last_hb) > self._heartbeat_threshold:
                    new_alerts.append(
                        WorkerAlert(
                            alert_id=self._next_id(),
                            worker_id=wid,
                            alert_type="stale_heartbeat",
                            severity="critical",
                            message=f"No heartbeat from {worker['name']} for {int(now - last_hb)}s",
                        )
                    )
                # Overloaded
                capacity = worker.get("capacity", 1)
                assigned = len(
                    self._registry.list_assignments(worker_id=wid)
                    if hasattr(self._registry, "list_assignments")
                    else []
                )
                if capacity > 0 and assigned >= capacity * self._overload_ratio:
                    new_alerts.append(
                        WorkerAlert(
                            alert_id=self._next_id(),
                            worker_id=wid,
                            alert_type="overloaded",
                            severity="warning",
                            message=f"{worker['name']} has {assigned}/{capacity} assignments",
                        )
                    )
                # Budget warning
                budget_limit = worker.get("budget_limit", 0.0)
                budget_spent = worker.get("budget_spent", 0.0)
                if budget_limit > 0 and budget_spent >= budget_limit * self._budget_warning_ratio:
                    new_alerts.append(
                        WorkerAlert(
                            alert_id=self._next_id(),
                            worker_id=wid,
                            alert_type="budget_warning",
                            severity="warning",
                            message=f"{worker['name']} budget {budget_spent:.2f}/{budget_limit:.2f}",
                        )
                    )
            self._alerts.extend(new_alerts)
        return new_alerts

    def list_alerts(self, worker_id: str | None = None, unresolved_only: bool = False) -> list[dict]:
        with self._lock:
            result = self._alerts
            if worker_id:
                result = [a for a in result if a.worker_id == worker_id]
            if unresolved_only:
                result = [a for a in result if not a.resolved]
            return [self._to_dict(a) for a in result]

    def resolve_alert(self, alert_id: str) -> bool:
        with self._lock:
            for a in self._alerts:
                if a.alert_id == alert_id:
                    a.resolved = True
                    return True
            return False

    @staticmethod
    def _to_dict(a: WorkerAlert) -> dict[str, Any]:
        return {
            "alert_id": a.alert_id,
            "worker_id": a.worker_id,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "message": a.message,
            "timestamp": a.timestamp,
            "resolved": a.resolved,
        }
