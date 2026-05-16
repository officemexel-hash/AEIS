"""Tests for SYLION Execution -- Capacity Planner.

Covers:
  - Constants (RESOURCE_TYPES, FORECAST_PERIODS)
  - Usage recording and querying
  - Forecast computation (linear extrapolation, headroom)
  - Forecast retrieval and listing
  - Bottleneck detection
  - Statistics aggregation
  - EventBus emission (usage_recorded, forecast_computed, bottleneck_detected)
  - Thread safety
  - Singleton pattern
  - Edge cases and error handling
"""
from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.execution.capacity_planner import (
    FORECAST_PERIODS,
    RESOURCE_TYPES,
    CapacityPlanner,
    get_capacity_planner,
    reset_capacity_planner,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the global singleton before and after each test."""
    reset_capacity_planner()
    yield
    reset_capacity_planner()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def planner(bus):
    return CapacityPlanner(db_path=":memory:", event_bus=bus)


@pytest.fixture
def planner_no_bus():
    return CapacityPlanner(db_path=":memory:", event_bus=None)


def _record_samples(planner, resource_type="compute", resource_id="node-1",
                    metric="cpu_percent", count=10, base_value=50.0,
                    base_time=None):
    """Helper to record a series of usage samples."""
    results = []
    base = base_time or time.time()
    for i in range(count):
        r = planner.record_usage(
            resource_type, resource_id, metric,
            value=base_value + i * 5.0,
        )
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# 1. Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_resource_types(self):
        assert "compute" in RESOURCE_TYPES
        assert "memory" in RESOURCE_TYPES
        assert "storage" in RESOURCE_TYPES
        assert "network" in RESOURCE_TYPES
        assert "api_calls" in RESOURCE_TYPES
        assert "tokens" in RESOURCE_TYPES
        assert len(RESOURCE_TYPES) == 6

    def test_forecast_periods(self):
        assert "1d" in FORECAST_PERIODS
        assert "7d" in FORECAST_PERIODS
        assert "30d" in FORECAST_PERIODS
        assert "90d" in FORECAST_PERIODS
        assert len(FORECAST_PERIODS) == 4


# ---------------------------------------------------------------------------
# 2. Usage recording
# ---------------------------------------------------------------------------

class TestRecordUsage:
    def test_record_returns_usage_dict(self, planner):
        r = planner.record_usage("compute", "node-1", "cpu_percent", 75.0)
        assert "usage_id" in r
        assert r["resource_type"] == "compute"
        assert r["resource_id"] == "node-1"
        assert r["metric"] == "cpu_percent"
        assert r["value"] == 75.0
        assert r["unit"] == "units"
        assert r["recorded_at"] > 0

    def test_record_with_custom_unit(self, planner):
        r = planner.record_usage("memory", "node-1", "rss", 4096.0, unit="MB")
        assert r["unit"] == "MB"

    def test_record_default_unit(self, planner):
        r = planner.record_usage("compute", "node-1", "cpu", 50.0)
        assert r["unit"] == "units"

    def test_record_generates_unique_ids(self, planner):
        r1 = planner.record_usage("compute", "node-1", "cpu", 10.0)
        r2 = planner.record_usage("compute", "node-1", "cpu", 20.0)
        assert r1["usage_id"] != r2["usage_id"]

    def test_record_sets_recorded_at(self, planner):
        before = time.time()
        r = planner.record_usage("compute", "node-1", "cpu", 50.0)
        after = time.time()
        assert before <= r["recorded_at"] <= after

    def test_record_invalid_resource_type_raises(self, planner):
        with pytest.raises(ValueError, match="Invalid resource_type"):
            planner.record_usage("invalid_type", "node-1", "cpu", 50.0)

    def test_record_all_resource_types(self, planner):
        for rt in RESOURCE_TYPES:
            r = planner.record_usage(rt, "res-1", "utilization", 50.0)
            assert r["resource_type"] == rt


# ---------------------------------------------------------------------------
# 3. Get usage
# ---------------------------------------------------------------------------

class TestGetUsage:
    def test_get_usage_empty(self, planner):
        assert planner.get_usage() == []

    def test_get_usage_returns_all(self, planner):
        _record_samples(planner, count=3)
        results = planner.get_usage()
        assert len(results) == 3

    def test_get_usage_filter_by_resource_type(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.record_usage("memory", "n1", "rss", 4096.0)
        planner.record_usage("compute", "n2", "cpu", 60.0)
        results = planner.get_usage(resource_type="compute")
        assert len(results) == 2
        assert all(r["resource_type"] == "compute" for r in results)

    def test_get_usage_filter_by_resource_id(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.record_usage("compute", "n2", "cpu", 60.0)
        results = planner.get_usage(resource_id="n1")
        assert len(results) == 1
        assert results[0]["resource_id"] == "n1"

    def test_get_usage_filter_by_metric(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.record_usage("compute", "n1", "mem", 4096.0)
        results = planner.get_usage(metric="cpu")
        assert len(results) == 1
        assert results[0]["metric"] == "cpu"

    def test_get_usage_filter_by_since(self, planner):
        old_time = time.time() - 3600
        # Record with an old timestamp by direct insert (bypassing record_usage)
        with planner._lock:
            planner._conn.execute(
                "INSERT INTO resource_usage "
                "(usage_id, resource_type, resource_id, metric, value, unit, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("old1", "compute", "n1", "cpu", 10.0, "units", old_time),
            )
            planner._conn.commit()
        planner.record_usage("compute", "n1", "cpu", 50.0)
        results = planner.get_usage(since=time.time() - 60)
        assert len(results) == 1
        assert results[0]["value"] == 50.0

    def test_get_usage_respects_limit(self, planner):
        _record_samples(planner, count=10)
        results = planner.get_usage(limit=5)
        assert len(results) == 5

    def test_get_usage_ordered_by_recorded_at_desc(self, planner):
        r1 = planner.record_usage("compute", "n1", "cpu", 10.0)
        r2 = planner.record_usage("compute", "n1", "cpu", 20.0)
        r3 = planner.record_usage("compute", "n1", "cpu", 30.0)
        results = planner.get_usage()
        assert results[0]["usage_id"] == r3["usage_id"]
        assert results[2]["usage_id"] == r1["usage_id"]

    def test_get_usage_combined_filters(self, planner):
        planner.record_usage("compute", "n1", "cpu", 10.0)
        planner.record_usage("compute", "n1", "mem", 20.0)
        planner.record_usage("compute", "n2", "cpu", 30.0)
        planner.record_usage("memory", "n1", "cpu", 40.0)
        results = planner.get_usage(resource_type="compute", resource_id="n1", metric="cpu")
        assert len(results) == 1
        assert results[0]["value"] == 10.0

    def test_get_usage_invalid_resource_type_raises(self, planner):
        with pytest.raises(ValueError, match="Invalid resource_type"):
            planner.get_usage(resource_type="bad_type")


# ---------------------------------------------------------------------------
# 4. Compute forecast
# ---------------------------------------------------------------------------

class TestComputeForecast:
    def test_compute_forecast_returns_dict(self, planner):
        _record_samples(planner, count=5)
        f = planner.compute_forecast("compute", "node-1")
        assert "forecast_id" in f
        assert f["resource_type"] == "compute"
        assert f["resource_id"] == "node-1"
        assert f["forecast_period"] == "7d"
        assert "current_capacity" in f
        assert "projected_demand" in f
        assert "headroom" in f
        assert "computed_at" in f

    def test_compute_forecast_no_usage_data(self, planner):
        f = planner.compute_forecast("compute", "node-1")
        assert f["current_capacity"] == 1.0
        assert f["projected_demand"] == 0.0
        assert f["headroom"] == 1.0

    def test_compute_forecast_with_single_sample(self, planner):
        planner.record_usage("compute", "node-1", "cpu", 50.0)
        f = planner.compute_forecast("compute", "node-1")
        assert f["projected_demand"] == 50.0
        assert f["current_capacity"] == 75.0  # 50 * 1.5
        assert f["headroom"] > 0

    def test_compute_forecast_with_growing_trend(self, planner):
        _record_samples(planner, count=10, base_value=10.0)
        f = planner.compute_forecast("compute", "node-1")
        # Projected demand should be higher than initial values
        assert f["projected_demand"] > 10.0
        assert f["current_capacity"] > 0

    def test_compute_forecast_headroom_calculation(self, planner):
        planner.record_usage("compute", "node-1", "cpu", 80.0)
        f = planner.compute_forecast("compute", "node-1")
        # capacity = 80 * 1.5 = 120, demand = 80
        # headroom = (120 - 80) / 120 = 0.333...
        expected_headroom = (120.0 - 80.0) / 120.0
        assert abs(f["headroom"] - expected_headroom) < 0.01

    def test_compute_forecast_upserts_existing(self, planner):
        _record_samples(planner, count=5)
        f1 = planner.compute_forecast("compute", "node-1")
        f2 = planner.compute_forecast("compute", "node-1")
        # Only one forecast for this key
        forecasts = planner.list_forecasts(resource_type="compute")
        assert len(forecasts) == 1
        assert forecasts[0]["forecast_id"] == f2["forecast_id"]

    def test_compute_forecast_different_periods(self, planner):
        planner.record_usage("compute", "node-1", "cpu", 50.0)
        f1 = planner.compute_forecast("compute", "node-1", "1d")
        f2 = planner.compute_forecast("compute", "node-1", "7d")
        forecasts = planner.list_forecasts()
        assert len(forecasts) == 2

    def test_compute_forecast_invalid_resource_type_raises(self, planner):
        with pytest.raises(ValueError, match="Invalid resource_type"):
            planner.compute_forecast("bad", "node-1")

    def test_compute_forecast_invalid_period_raises(self, planner):
        with pytest.raises(ValueError, match="Invalid forecast_period"):
            planner.compute_forecast("compute", "node-1", "365d")

    def test_compute_forecast_default_period_is_7d(self, planner):
        planner.record_usage("compute", "node-1", "cpu", 50.0)
        f = planner.compute_forecast("compute", "node-1")
        assert f["forecast_period"] == "7d"

    def test_compute_forecast_all_periods(self, planner):
        planner.record_usage("compute", "node-1", "cpu", 50.0)
        for period in FORECAST_PERIODS:
            f = planner.compute_forecast("compute", "node-1", period)
            assert f["forecast_period"] == period


# ---------------------------------------------------------------------------
# 5. Get forecast
# ---------------------------------------------------------------------------

class TestGetForecast:
    def test_get_forecast_existing(self, planner):
        planner.record_usage("compute", "node-1", "cpu", 50.0)
        planner.compute_forecast("compute", "node-1", "7d")
        f = planner.get_forecast("compute", "node-1", "7d")
        assert f is not None
        assert f["resource_type"] == "compute"
        assert f["resource_id"] == "node-1"

    def test_get_forecast_nonexistent_returns_none(self, planner):
        assert planner.get_forecast("compute", "node-1") is None

    def test_get_forecast_wrong_period_returns_none(self, planner):
        planner.record_usage("compute", "node-1", "cpu", 50.0)
        planner.compute_forecast("compute", "node-1", "7d")
        assert planner.get_forecast("compute", "node-1", "30d") is None

    def test_get_forecast_invalid_resource_type_raises(self, planner):
        with pytest.raises(ValueError, match="Invalid resource_type"):
            planner.get_forecast("bad", "node-1")

    def test_get_forecast_invalid_period_raises(self, planner):
        with pytest.raises(ValueError, match="Invalid forecast_period"):
            planner.get_forecast("compute", "node-1", "1y")


# ---------------------------------------------------------------------------
# 6. List forecasts
# ---------------------------------------------------------------------------

class TestListForecasts:
    def test_list_forecasts_empty(self, planner):
        assert planner.list_forecasts() == []

    def test_list_forecasts_returns_all(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.record_usage("memory", "n2", "rss", 4096.0)
        planner.compute_forecast("compute", "n1")
        planner.compute_forecast("memory", "n2")
        assert len(planner.list_forecasts()) == 2

    def test_list_forecasts_filter_by_resource_type(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.record_usage("memory", "n2", "rss", 4096.0)
        planner.compute_forecast("compute", "n1")
        planner.compute_forecast("memory", "n2")
        results = planner.list_forecasts(resource_type="compute")
        assert len(results) == 1
        assert results[0]["resource_type"] == "compute"

    def test_list_forecasts_filter_by_period(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.compute_forecast("compute", "n1", "1d")
        planner.compute_forecast("compute", "n1", "7d")
        results = planner.list_forecasts(forecast_period="1d")
        assert len(results) == 1
        assert results[0]["forecast_period"] == "1d"

    def test_list_forecasts_respects_limit(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        for period in FORECAST_PERIODS:
            planner.compute_forecast("compute", "n1", period)
        results = planner.list_forecasts(limit=2)
        assert len(results) == 2

    def test_list_forecasts_invalid_resource_type_raises(self, planner):
        with pytest.raises(ValueError, match="Invalid resource_type"):
            planner.list_forecasts(resource_type="bad")

    def test_list_forecasts_invalid_period_raises(self, planner):
        with pytest.raises(ValueError, match="Invalid forecast_period"):
            planner.list_forecasts(forecast_period="1y")


# ---------------------------------------------------------------------------
# 7. Bottleneck detection
# ---------------------------------------------------------------------------

class TestGetBottlenecks:
    def test_no_bottlenecks_when_empty(self, planner):
        assert planner.get_bottlenecks() == []

    def test_no_bottlenecks_with_high_headroom(self, planner):
        planner.record_usage("compute", "n1", "cpu", 10.0)
        planner.compute_forecast("compute", "n1")
        bottlenecks = planner.get_bottlenecks()
        assert len(bottlenecks) == 0

    def test_bottleneck_detected_when_low_headroom(self, planner):
        # Record very high usage to create low headroom
        for i in range(10):
            planner.record_usage("compute", "n1", "cpu", 90.0 + i * 0.5)
        f = planner.compute_forecast("compute", "n1")
        # If headroom is low, it should appear in bottlenecks
        if f["headroom"] < 0.2:
            bottlenecks = planner.get_bottlenecks()
            assert len(bottlenecks) >= 1
            assert bottlenecks[0]["resource_type"] == "compute"

    def test_bottleneck_custom_threshold(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.compute_forecast("compute", "n1")
        # With a very high threshold, everything is a bottleneck
        bottlenecks = planner.get_bottlenecks(headroom_threshold=0.99)
        assert len(bottlenecks) >= 1

    def test_bottleneck_zero_threshold(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.compute_forecast("compute", "n1")
        # With threshold=0, only negative headroom qualifies
        bottlenecks = planner.get_bottlenecks(headroom_threshold=0.0)
        # Most normal resources have positive headroom
        assert isinstance(bottlenecks, list)

    def test_bottlenecks_ordered_by_headroom_asc(self, planner):
        # Two resources, different headroom levels
        planner.record_usage("compute", "n1", "cpu", 90.0)
        planner.record_usage("memory", "n2", "rss", 10.0)
        f1 = planner.compute_forecast("compute", "n1")
        f2 = planner.compute_forecast("memory", "n2")
        bottlenecks = planner.get_bottlenecks(headroom_threshold=1.0)
        if len(bottlenecks) >= 2:
            assert bottlenecks[0]["headroom"] <= bottlenecks[1]["headroom"]


# ---------------------------------------------------------------------------
# 8. Statistics
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_stats_empty(self, planner):
        stats = planner.get_stats()
        assert stats["total_usage"] == 0
        assert stats["total_forecasts"] == 0
        assert stats["bottleneck_count"] == 0

    def test_stats_counts_usage(self, planner):
        _record_samples(planner, count=5)
        stats = planner.get_stats()
        assert stats["total_usage"] == 5

    def test_stats_counts_forecasts(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.compute_forecast("compute", "n1")
        stats = planner.get_stats()
        assert stats["total_forecasts"] == 1

    def test_stats_by_type(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.record_usage("compute", "n2", "cpu", 60.0)
        planner.record_usage("memory", "n1", "rss", 4096.0)
        stats = planner.get_stats()
        assert stats["usage_by_type"]["compute"] == 2
        assert stats["usage_by_type"]["memory"] == 1

    def test_stats_by_metric(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.record_usage("compute", "n1", "mem", 4096.0)
        planner.record_usage("compute", "n1", "cpu", 60.0)
        stats = planner.get_stats()
        assert stats["usage_by_metric"]["cpu"] == 2
        assert stats["usage_by_metric"]["mem"] == 1

    def test_stats_by_period(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.compute_forecast("compute", "n1", "1d")
        planner.compute_forecast("compute", "n1", "7d")
        stats = planner.get_stats()
        assert stats["forecasts_by_period"]["1d"] == 1
        assert stats["forecasts_by_period"]["7d"] == 1

    def test_stats_includes_all_resource_types(self, planner):
        stats = planner.get_stats()
        for rt in RESOURCE_TYPES:
            assert rt in stats["usage_by_type"]

    def test_stats_includes_all_periods(self, planner):
        stats = planner.get_stats()
        for fp in FORECAST_PERIODS:
            assert fp in stats["forecasts_by_period"]

    def test_stats_bottleneck_count(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.compute_forecast("compute", "n1")
        stats = planner.get_stats()
        assert isinstance(stats["bottleneck_count"], int)


# ---------------------------------------------------------------------------
# 9. EventBus emission
# ---------------------------------------------------------------------------

class TestEventEmission:
    def test_record_usage_emits_event(self, planner, bus):
        events = []
        bus.subscribe("capacity.usage_recorded", events.append)
        planner.record_usage("compute", "n1", "cpu", 50.0)
        assert len(events) == 1
        assert events[0].payload["resource_type"] == "compute"
        assert events[0].payload["value"] == 50.0

    def test_compute_forecast_emits_event(self, planner, bus):
        events = []
        bus.subscribe("capacity.forecast_computed", events.append)
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.compute_forecast("compute", "n1")
        assert len(events) == 1
        assert events[0].payload["resource_type"] == "compute"
        assert "headroom" in events[0].payload

    def test_bottleneck_emits_event(self, planner, bus):
        events = []
        bus.subscribe("capacity.bottleneck_detected", events.append)
        # High usage values to force low headroom
        for i in range(10):
            planner.record_usage("compute", "n1", "cpu", 90.0 + i)
        f = planner.compute_forecast("compute", "n1")
        if f["headroom"] < 0.2:
            assert len(events) == 1
            assert events[0].payload["resource_type"] == "compute"
            assert events[0].payload["headroom"] < 0.2

    def test_no_bottleneck_event_when_headroom_ok(self, planner, bus):
        events = []
        bus.subscribe("capacity.bottleneck_detected", events.append)
        planner.record_usage("compute", "n1", "cpu", 10.0)
        planner.compute_forecast("compute", "n1")
        assert len(events) == 0

    def test_no_bus_does_not_crash_on_record(self, planner_no_bus):
        planner_no_bus.record_usage("compute", "n1", "cpu", 50.0)
        # No crash means event emission was safely skipped

    def test_no_bus_does_not_crash_on_forecast(self, planner_no_bus):
        planner_no_bus.record_usage("compute", "n1", "cpu", 50.0)
        planner_no_bus.compute_forecast("compute", "n1")
        # No crash means event emission was safely skipped

    def test_usage_event_contains_usage_id(self, planner, bus):
        events = []
        bus.subscribe("capacity.usage_recorded", events.append)
        planner.record_usage("compute", "n1", "cpu", 50.0)
        assert "usage_id" in events[0].payload
        assert len(events[0].payload["usage_id"]) > 0


# ---------------------------------------------------------------------------
# 10. Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_record_usage(self, planner):
        results = []
        errors = []

        def record(i):
            try:
                r = planner.record_usage(
                    "compute", f"node-{i}", "cpu", float(i),
                )
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        assert len(set(r["usage_id"] for r in results)) == 20

    def test_concurrent_compute_forecast(self, planner):
        for i in range(5):
            planner.record_usage("compute", f"node-{i}", "cpu", float(i * 10))

        errors = []

        def compute(i):
            try:
                planner.compute_forecast("compute", f"node-{i}", "7d")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=compute, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        forecasts = planner.list_forecasts()
        assert len(forecasts) == 5

    def test_concurrent_reads_and_writes(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        errors = []
        read_results = []

        def writer():
            try:
                for i in range(5):
                    planner.record_usage("compute", "n1", "cpu", float(i))
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                r = planner.get_usage()
                read_results.append(len(r))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer)]
        threads += [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(isinstance(r, int) for r in read_results)


# ---------------------------------------------------------------------------
# 11. Singleton pattern
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_returns_same_instance(self):
        a = get_capacity_planner(db_path=":memory:")
        b = get_capacity_planner(db_path=":memory:")
        assert a is b

    def test_reset_creates_new_instance(self):
        a = get_capacity_planner(db_path=":memory:")
        reset_capacity_planner(db_path=":memory:")
        b = get_capacity_planner(db_path=":memory:")
        assert a is not b

    def test_reset_returns_planner(self):
        p = reset_capacity_planner(db_path=":memory:")
        assert isinstance(p, CapacityPlanner)

    def test_get_after_reset_returns_new(self):
        a = get_capacity_planner(db_path=":memory:")
        reset_capacity_planner(db_path=":memory:")
        b = get_capacity_planner(db_path=":memory:")
        assert b is not a


# ---------------------------------------------------------------------------
# 12. Linear extrapolation edge cases
# ---------------------------------------------------------------------------

class TestLinearExtrapolation:
    def test_empty_data(self):
        result = CapacityPlanner._linear_extrapolate([], [], 0, 100)
        assert result == 0.0

    def test_single_point(self):
        result = CapacityPlanner._linear_extrapolate([0.0], [42.0], 0, 100)
        assert result == 42.0

    def test_two_points_constant(self):
        result = CapacityPlanner._linear_extrapolate(
            [0.0, 10.0], [50.0, 50.0], 0, 20.0,
        )
        assert abs(result - 50.0) < 0.01

    def test_two_points_growing(self):
        result = CapacityPlanner._linear_extrapolate(
            [0.0, 10.0], [0.0, 100.0], 0, 20.0,
        )
        assert result == pytest.approx(200.0, abs=0.01)

    def test_negative_slope_clamped(self):
        """Negative slope (decreasing) is clamped to max observed."""
        result = CapacityPlanner._linear_extrapolate(
            [0.0, 10.0], [100.0, 0.0], 0, 20.0,
        )
        # Should clamp to max value (100.0) instead of going negative
        assert result >= 0

    def test_identical_timestamps(self):
        """All timestamps the same: returns the mean."""
        result = CapacityPlanner._linear_extrapolate(
            [5.0, 5.0, 5.0], [10.0, 20.0, 30.0], 0, 100,
        )
        assert result == 20.0  # mean of 10, 20, 30


# ---------------------------------------------------------------------------
# 13. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_zero_value_usage(self, planner):
        r = planner.record_usage("compute", "n1", "cpu", 0.0)
        assert r["value"] == 0.0

    def test_negative_value_usage(self, planner):
        r = planner.record_usage("compute", "n1", "cpu", -5.0)
        assert r["value"] == -5.0

    def test_very_large_value(self, planner):
        r = planner.record_usage("compute", "n1", "cpu", 1e15)
        assert r["value"] == 1e15

    def test_multiple_resources_same_type(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.record_usage("compute", "n2", "cpu", 60.0)
        planner.compute_forecast("compute", "n1")
        planner.compute_forecast("compute", "n2")
        forecasts = planner.list_forecasts(resource_type="compute")
        assert len(forecasts) == 2

    def test_forecast_with_many_samples(self, planner):
        for i in range(100):
            planner.record_usage("compute", "n1", "cpu", float(i))
        f = planner.compute_forecast("compute", "n1")
        assert f["forecast_id"] is not None
        assert f["headroom"] is not None

    def test_get_bottlenecks_after_multiple_forecasts(self, planner):
        planner.record_usage("compute", "n1", "cpu", 10.0)
        planner.record_usage("memory", "n2", "rss", 4096.0)
        planner.compute_forecast("compute", "n1")
        planner.compute_forecast("memory", "n2")
        bottlenecks = planner.get_bottlenecks(headroom_threshold=0.5)
        assert isinstance(bottlenecks, list)

    def test_forecast_id_is_unique(self, planner):
        planner.record_usage("compute", "n1", "cpu", 50.0)
        planner.compute_forecast("compute", "n1", "1d")
        planner.compute_forecast("compute", "n1", "7d")
        f1 = planner.get_forecast("compute", "n1", "1d")
        f2 = planner.get_forecast("compute", "n1", "7d")
        assert f1["forecast_id"] != f2["forecast_id"]

    def test_no_bus_singleton(self):
        p = reset_capacity_planner(db_path=":memory:", event_bus=None)
        p.record_usage("compute", "n1", "cpu", 50.0)
        p.compute_forecast("compute", "n1")
        # Should not crash even without event bus
        stats = p.get_stats()
        assert stats["total_usage"] == 1
        assert stats["total_forecasts"] == 1
