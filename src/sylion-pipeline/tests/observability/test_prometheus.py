"""
Tests for observability/prometheus_exporter (FIX-220).
"""

from __future__ import annotations

import pytest

from sylion.observability.metrics_registry import MetricsRegistry, get_metrics_registry, reset_metrics_registry
from sylion.observability.prometheus_exporter import METRIC_SEED, seed_metrics, update_live_gauges


@pytest.fixture(autouse=True)
def _reset_registry():
    reset_metrics_registry()
    yield
    reset_metrics_registry()


class TestSeedMetrics:
    def test_seeds_at_least_20(self):
        reg = seed_metrics()
        assert len(METRIC_SEED) >= 20
        # Check that all collectors registered successfully
        for spec in METRIC_SEED:
            assert spec["name"] in reg._collectors

    def test_counter_registered(self):
        reg = seed_metrics()
        c = reg.counter("aeis_pipeline_runs_total", "", ["status", "decision_class"])
        c.labels(status="ok", decision_class="D2").inc(3)
        assert b"aeis_pipeline_runs_total{decision_class=\"D2\",status=\"ok\"} 3.0" in reg.generate_latest()

    def test_gauge_registered(self):
        reg = seed_metrics()
        g = reg.gauge("aeis_skill_loaded_count")
        g.set(7)
        assert b"aeis_skill_loaded_count 7.0" in reg.generate_latest()

    def test_histogram_registered(self):
        reg = seed_metrics()
        h = reg.histogram("aeis_pipeline_duration_seconds")
        h.observe(1.5)
        latest = reg.generate_latest()
        assert b"aeis_pipeline_duration_seconds_bucket" in latest


class TestMetricsEndpoint:
    def test_metrics_route_returns_prometheus(self):
        from sylion.api.metrics_routes import metrics
        import asyncio
        response = asyncio.run(metrics())
        assert response.status_code == 200
        assert response.media_type.startswith("text/plain")
        body = response.body
        assert b"aeis_" in body


class TestLiveGauges:
    def test_update_live_gauges_runs(self):
        reg = seed_metrics()
        update_live_gauges(reg)
        # Should not raise; exact values depend on DB state
        assert reg.generate_latest() is not None
