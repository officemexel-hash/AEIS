"""
SYLION Observability -- Hub

Aggregates metrics, traces, and logs from all subsystems.
Provides a unified health and performance snapshot.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from sylion.observability.log_aggregator import LogAggregator


class ObservabilityHub:
    """Central observability hub collecting metrics, traces, and logs."""

    def __init__(self, log_aggregator: LogAggregator | None = None):
        self._log = log_aggregator or LogAggregator()
        self._metrics: dict[str, list[tuple[float, float]]] = {}
        self._traces: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def record_metric(self, name: str, value: float) -> None:
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = []
            self._metrics[name].append((time.time(), value))
            # Keep last 1000 points per metric
            if len(self._metrics[name]) > 1000:
                self._metrics[name] = self._metrics[name][-1000:]

    def get_metric(self, name: str, limit: int = 100) -> list[dict]:
        with self._lock:
            points = self._metrics.get(name, [])[-limit:]
        return [{"timestamp": ts, "value": val} for ts, val in points]

    def list_metrics(self) -> list[str]:
        with self._lock:
            return list(self._metrics.keys())

    def start_trace(self, trace_id: str, operation: str, service: str) -> None:
        with self._lock:
            self._traces[trace_id] = {
                "trace_id": trace_id,
                "operation": operation,
                "service": service,
                "start_time": time.time(),
                "end_time": None,
                "duration_ms": None,
                "status": "running",
            }

    def end_trace(self, trace_id: str, status: str = "ok") -> None:
        with self._lock:
            if trace_id in self._traces:
                self._traces[trace_id]["end_time"] = time.time()
                self._traces[trace_id]["status"] = status
                start = self._traces[trace_id]["start_time"]
                self._traces[trace_id]["duration_ms"] = round((time.time() - start) * 1000, 2)

    def get_trace(self, trace_id: str) -> dict | None:
        with self._lock:
            return self._traces.get(trace_id)

    def list_traces(self, service: str | None = None, limit: int = 50) -> list[dict]:
        with self._lock:
            traces = list(self._traces.values())
        if service:
            traces = [t for t in traces if t.get("service") == service]
        return sorted(traces, key=lambda x: x["start_time"], reverse=True)[:limit]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "timestamp": time.time(),
                "backend": self._log.get_backend_type(),
                "metrics_count": len(self._metrics),
                "traces_count": len(self._traces),
                "recent_logs": self._log.query(limit=5),
            }

    def log(self, service: str, level: str, message: str, extra: dict | None = None) -> None:
        self._log.log(service, level, message, extra)
