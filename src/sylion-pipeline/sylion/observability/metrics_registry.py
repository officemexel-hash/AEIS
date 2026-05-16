"""
SYLION Observability -- Metrics Registry

Central registry for Prometheus-style metrics.
Wraps prometheus_client collectors with a convenient API.

Usage:
    from sylion.observability.metrics_registry import MetricsRegistry, get_metrics_registry
    reg = get_metrics_registry()
    reg.counter("aeis_funding_calls_scanned_total", "Calls scanned", ["program"])
    reg.inc("aeis_funding_calls_scanned_total", {"program": "horizon_europe"})
"""

from __future__ import annotations

import logging
import threading
from typing import Any

try:
    from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
    _PROM_AVAILABLE = True
except Exception:  # pragma: no cover
    _PROM_AVAILABLE = False

log = logging.getLogger("sylion.observability.metrics_registry")


class MetricsRegistry:
    """Central metrics registry with named collectors."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        if _PROM_AVAILABLE:
            self._registry = CollectorRegistry()
        else:
            self._registry = None  # type: ignore[assignment]
        self._collectors: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def counter(self, name: str, description: str = "",
                labelnames: list[str] | None = None) -> Any:
        """Register or retrieve a Counter."""
        if not _PROM_AVAILABLE:
            return _NullCollector()
        with self._lock:
            if name not in self._collectors:
                self._collectors[name] = Counter(name, description,
                                                  labelnames or [],
                                                  registry=self._registry)
            return self._collectors[name]

    def gauge(self, name: str, description: str = "",
              labelnames: list[str] | None = None) -> Any:
        """Register or retrieve a Gauge."""
        if not _PROM_AVAILABLE:
            return _NullCollector()
        with self._lock:
            if name not in self._collectors:
                self._collectors[name] = Gauge(name, description,
                                                labelnames or [],
                                                registry=self._registry)
            return self._collectors[name]

    def histogram(self, name: str, description: str = "",
                  labelnames: list[str] | None = None,
                  buckets: list[float] | None = None) -> Any:
        """Register or retrieve a Histogram."""
        if not _PROM_AVAILABLE:
            return _NullCollector()
        with self._lock:
            if name not in self._collectors:
                kwargs: dict[str, Any] = {"registry": self._registry}
                if buckets:
                    kwargs["buckets"] = buckets
                self._collectors[name] = Histogram(name, description,
                                                    labelnames or [],
                                                    **kwargs)
            return self._collectors[name]

    # ------------------------------------------------------------------
    # Convenience mutations
    # ------------------------------------------------------------------

    def inc(self, name: str, labels: dict[str, str] | None = None, amount: float = 1) -> None:
        """Increment a counter or gauge."""
        coll = self._collectors.get(name)
        if coll is None:
            log.debug("metric %s not found, skipping inc", name)
            return
        try:
            if labels:
                coll.labels(**labels).inc(amount)
            else:
                coll.inc(amount)
        except Exception as exc:
            log.debug("inc failed for %s: %s", name, exc)

    def set(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge value."""
        coll = self._collectors.get(name)
        if coll is None:
            log.debug("metric %s not found, skipping set", name)
            return
        try:
            if labels:
                coll.labels(**labels).set(value)
            else:
                coll.set(value)
        except Exception as exc:
            log.debug("set failed for %s: %s", name, exc)

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Observe a histogram value."""
        coll = self._collectors.get(name)
        if coll is None:
            log.debug("metric %s not found, skipping observe", name)
            return
        try:
            if labels:
                coll.labels(**labels).observe(value)
            else:
                coll.observe(value)
        except Exception as exc:
            log.debug("observe failed for %s: %s", name, exc)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def generate_latest(self) -> bytes:
        """Return Prometheus exposition format bytes."""
        if not _PROM_AVAILABLE or self._registry is None:
            return b""
        return generate_latest(self._registry)

    @property
    def content_type(self) -> str:
        if _PROM_AVAILABLE:
            return CONTENT_TYPE_LATEST
        return "text/plain"


class _NullCollector:
    """No-op collector when prometheus_client is unavailable."""

    def inc(self, amount: float = 1) -> None:
        pass

    def set(self, value: float) -> None:
        pass

    def observe(self, value: float) -> None:
        pass

    def labels(self, **kwargs: Any) -> "_NullCollector":
        return self


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_registry_instance: MetricsRegistry | None = None


def get_metrics_registry() -> MetricsRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = MetricsRegistry()
    return _registry_instance


def reset_metrics_registry() -> MetricsRegistry:
    global _registry_instance
    _registry_instance = MetricsRegistry()
    return _registry_instance
