"""
test_metric_aggregator.py -- ~40 tests for MetricAggregator

Covers:
  1. Table creation and schema
  2. record() -- basic, with tags, with source
  3. get_points() -- filters (source, since, until, limit)
  4. aggregate() -- period bucketing, validation, recompute
  5. get_aggregates() -- filters
  6. get_latest() -- with and without source filter
  7. get_stats() -- empty, populated, per-metric/source breakdown
  8. EventBus integration
  9. Thread safety
 10. Singleton / reset
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sylion.monitoring.metric_aggregator import (
    MetricAggregator,
    PERIOD_SECONDS,
    VALID_PERIODS,
    get_metric_aggregator,
    reset_metric_aggregator,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make(**kw) -> MetricAggregator:
    """Create an in-memory MetricAggregator for testing."""
    return MetricAggregator(db_path=":memory:", **kw)


def _record_batch(agg: MetricAggregator, metric_name: str,
                  values: list[float], source: str = "",
                  base_ts: float | None = None) -> list[dict]:
    """Record a batch of values and return the results."""
    results = []
    for i, v in enumerate(values):
        ts = (base_ts or time.time()) + i
        # We inject timestamp via record() -- but record() uses time.time()
        # internally.  For deterministic bucketing we patch the timestamp
        # directly in SQLite after insert.
        r = agg.record(metric_name, v, source=source)
        if base_ts is not None:
            # Overwrite the timestamp for deterministic testing
            with agg._lock:
                agg._conn.execute(
                    "UPDATE metric_points SET timestamp = ? WHERE point_id = ?",
                    (base_ts + i, r["point_id"]),
                )
                agg._conn.commit()
        results.append(r)
    return results


# ===================================================================
# PART 1: Table creation and schema (3 tests)
# ===================================================================

class TestSchema:
    """Verify tables and indexes are created correctly."""

    def test_metric_points_table_exists(self):
        agg = _make()
        with agg._lock:
            row = agg._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='metric_points'"
            ).fetchone()
        assert row is not None

    def test_metric_aggregates_table_exists(self):
        agg = _make()
        with agg._lock:
            row = agg._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='metric_aggregates'"
            ).fetchone()
        assert row is not None

    def test_indexes_created(self):
        agg = _make()
        with agg._lock:
            indexes = agg._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_m%'"
            ).fetchall()
        index_names = {r["name"] for r in indexes}
        assert "idx_mp_name" in index_names
        assert "idx_mp_source" in index_names
        assert "idx_mp_ts" in index_names
        assert "idx_ma_name" in index_names
        assert "idx_ma_period" in index_names
        assert "idx_ma_source" in index_names


# ===================================================================
# PART 2: record() (6 tests)
# ===================================================================

class TestRecord:
    """Verify metric point recording."""

    def test_record_returns_point_id(self):
        agg = _make()
        result = agg.record("cpu.usage", 72.5)
        assert "point_id" in result
        assert len(result["point_id"]) == 32  # uuid hex

    def test_record_stores_correct_value(self):
        agg = _make()
        result = agg.record("memory.used", 4096.0, source="host-1")
        assert result["metric_name"] == "memory.used"
        assert result["value"] == 4096.0
        assert result["source"] == "host-1"

    def test_record_with_tags(self):
        agg = _make()
        result = agg.record("latency", 12.3, source="api", tags={"region": "us-east"})
        assert result["metric_name"] == "latency"

        # Verify tags are stored as JSON
        with agg._lock:
            row = agg._conn.execute(
                "SELECT tags FROM metric_points WHERE point_id = ?",
                (result["point_id"],),
            ).fetchone()
        import json
        tags = json.loads(row["tags"])
        assert tags == {"region": "us-east"}

    def test_record_without_tags_stores_empty_json(self):
        agg = _make()
        result = agg.record("disk.io", 100.0)
        with agg._lock:
            row = agg._conn.execute(
                "SELECT tags FROM metric_points WHERE point_id = ?",
                (result["point_id"],),
            ).fetchone()
        assert row["tags"] == "{}"

    def test_record_timestamp_is_set(self):
        agg = _make()
        before = time.time()
        result = agg.record("req.rate", 50.0)
        after = time.time()
        assert before <= result["timestamp"] <= after

    def test_record_multiple_points(self):
        agg = _make()
        for i in range(10):
            agg.record("counter", float(i))
        points = agg.get_points("counter")
        assert len(points) == 10


# ===================================================================
# PART 3: get_points() (7 tests)
# ===================================================================

class TestGetPoints:
    """Verify get_points filtering."""

    def setup_method(self):
        self.agg = _make()
        self.agg.record("cpu", 10.0, source="a")
        self.agg.record("cpu", 20.0, source="b")
        self.agg.record("cpu", 30.0, source="a")
        self.agg.record("mem", 100.0, source="a")

    def test_filter_by_metric_name(self):
        points = self.agg.get_points("cpu")
        assert len(points) == 3
        assert all(p["metric_name"] == "cpu" for p in points)

    def test_filter_by_source(self):
        points = self.agg.get_points("cpu", source="a")
        assert len(points) == 2
        assert all(p["source"] == "a" for p in points)

    def test_filter_by_since(self):
        # Get timestamp of second point
        all_cpu = self.agg.get_points("cpu")
        since_ts = all_cpu[1]["timestamp"]
        points = self.agg.get_points("cpu", since=since_ts)
        assert len(points) == 2

    def test_filter_by_until(self):
        all_cpu = self.agg.get_points("cpu")
        until_ts = all_cpu[1]["timestamp"]
        points = self.agg.get_points("cpu", until=until_ts)
        assert len(points) == 2

    def test_filter_by_since_and_until(self):
        all_cpu = self.agg.get_points("cpu")
        points = self.agg.get_points(
            "cpu",
            since=all_cpu[0]["timestamp"],
            until=all_cpu[1]["timestamp"],
        )
        assert len(points) == 2

    def test_limit(self):
        points = self.agg.get_points("cpu", limit=1)
        assert len(points) == 1

    def test_tags_deserialized(self):
        self.agg.record("net", 5.0, tags={"iface": "eth0"})
        points = self.agg.get_points("net")
        assert points[0]["tags"] == {"iface": "eth0"}


# ===================================================================
# PART 4: aggregate() (8 tests)
# ===================================================================

class TestAggregate:
    """Verify time-bucket aggregation."""

    def test_aggregate_single_bucket(self):
        agg = _make()
        base = 1700000000.0  # fixed base for determinism
        _record_batch(agg, "cpu", [10.0, 20.0, 30.0], base_ts=base)
        result = agg.aggregate("cpu", period="1h")
        assert len(result) == 1
        assert result[0]["avg_value"] == pytest.approx(20.0)
        assert result[0]["min_value"] == 10.0
        assert result[0]["max_value"] == 30.0
        assert result[0]["count"] == 3

    def test_aggregate_multiple_buckets(self):
        agg = _make()
        base = 1700000000.0
        # First hour: 3 points
        _record_batch(agg, "cpu", [10.0, 20.0, 30.0], base_ts=base)
        # Second hour: 2 points (offset by 3600s)
        _record_batch(agg, "cpu", [40.0, 50.0], base_ts=base + 3600)
        result = agg.aggregate("cpu", period="1h")
        assert len(result) == 2
        # Ordered by bucket start
        assert result[0]["count"] == 3
        assert result[1]["count"] == 2
        assert result[1]["avg_value"] == pytest.approx(45.0)

    def test_aggregate_with_source_filter(self):
        agg = _make()
        base = 1700000000.0
        _record_batch(agg, "cpu", [10.0, 20.0], source="host-a", base_ts=base)
        _record_batch(agg, "cpu", [100.0], source="host-b", base_ts=base)
        result = agg.aggregate("cpu", period="1h", source="host-a")
        assert len(result) == 1
        assert result[0]["avg_value"] == pytest.approx(15.0)
        assert result[0]["count"] == 2

    def test_aggregate_invalid_period_raises(self):
        agg = _make()
        with pytest.raises(ValueError, match="Invalid period"):
            agg.aggregate("cpu", period="2w")

    def test_aggregate_no_points_returns_empty(self):
        agg = _make()
        result = agg.aggregate("nonexistent", period="1h")
        assert result == []

    def test_aggregate_period_start_end(self):
        agg = _make()
        base = 1700000000.0
        _record_batch(agg, "cpu", [42.0], base_ts=base)
        result = agg.aggregate("cpu", period="1h")
        assert len(result) == 1
        # period_start should be the bucket aligned to 3600
        expected_start = (base // 3600) * 3600
        assert result[0]["period_start"] == expected_start
        assert result[0]["period_end"] == expected_start + 3600

    def test_aggregate_idempotent_upsert(self):
        agg = _make()
        base = 1700000000.0
        _record_batch(agg, "cpu", [10.0, 20.0], base_ts=base)
        r1 = agg.aggregate("cpu", period="1h")
        assert len(r1) == 1
        # Aggregate again -- should upsert, not duplicate
        r2 = agg.aggregate("cpu", period="1h")
        assert len(r2) == 1
        stored = agg.get_aggregates("cpu", period="1h")
        assert len(stored) == 1

    def test_aggregate_five_minute_period(self):
        agg = _make()
        base = 1700000000.0
        # Three points in first 5-min bucket
        _record_batch(agg, "req", [1.0, 2.0, 3.0], base_ts=base)
        # One point in second 5-min bucket (300s later)
        _record_batch(agg, "req", [10.0], base_ts=base + 300)
        result = agg.aggregate("req", period="5m")
        assert len(result) == 2
        assert result[0]["count"] == 3
        assert result[1]["count"] == 1


# ===================================================================
# PART 5: get_aggregates() (4 tests)
# ===================================================================

class TestGetAggregates:
    """Verify aggregate retrieval."""

    def setup_method(self):
        self.agg = _make()
        base = 1700000000.0
        _record_batch(self.agg, "cpu", [10.0, 20.0], source="a", base_ts=base)
        _record_batch(self.agg, "cpu", [30.0], source="b", base_ts=base)
        self.agg.aggregate("cpu", period="1h", source="a")
        self.agg.aggregate("cpu", period="1h", source="b")

    def test_get_aggregates_by_metric(self):
        result = self.agg.get_aggregates("cpu")
        assert len(result) == 2

    def test_get_aggregates_filter_by_source(self):
        result = self.agg.get_aggregates("cpu", source="a")
        assert len(result) == 1
        assert result[0]["source"] == "a"

    def test_get_aggregates_filter_by_period(self):
        result = self.agg.get_aggregates("cpu", period="1h")
        assert len(result) == 2
        # Different period should yield nothing
        result2 = self.agg.get_aggregates("cpu", period="5m")
        assert len(result2) == 0

    def test_get_aggregates_limit(self):
        result = self.agg.get_aggregates("cpu", limit=1)
        assert len(result) == 1


# ===================================================================
# PART 6: get_latest() (4 tests)
# ===================================================================

class TestGetLatest:
    """Verify latest-point retrieval."""

    def test_get_latest_returns_newest(self):
        agg = _make()
        agg.record("temp", 20.0)
        time.sleep(0.01)
        agg.record("temp", 25.0)
        time.sleep(0.01)
        agg.record("temp", 30.0)
        latest = agg.get_latest("temp")
        assert latest is not None
        assert latest["value"] == 30.0

    def test_get_latest_with_source_filter(self):
        agg = _make()
        agg.record("cpu", 10.0, source="a")
        agg.record("cpu", 20.0, source="b")
        agg.record("cpu", 15.0, source="a")
        latest = agg.get_latest("cpu", source="a")
        assert latest is not None
        assert latest["value"] == 15.0

    def test_get_latest_nonexistent_returns_none(self):
        agg = _make()
        assert agg.get_latest("no.such.metric") is None

    def test_get_latest_tags_deserialized(self):
        agg = _make()
        agg.record("net", 5.0, tags={"iface": "eth0"})
        latest = agg.get_latest("net")
        assert latest["tags"] == {"iface": "eth0"}


# ===================================================================
# PART 7: get_stats() (4 tests)
# ===================================================================

class TestGetStats:
    """Verify aggregate statistics."""

    def test_empty_stats(self):
        agg = _make()
        stats = agg.get_stats()
        assert stats["total_points"] == 0
        assert stats["total_aggregates"] == 0
        assert stats["metric_count"] == 0
        assert stats["by_metric"] == {}
        assert stats["by_source"] == {}

    def test_stats_after_records(self):
        agg = _make()
        agg.record("cpu", 10.0, source="host-a")
        agg.record("cpu", 20.0, source="host-b")
        agg.record("mem", 100.0, source="host-a")
        stats = agg.get_stats()
        assert stats["total_points"] == 3
        assert stats["metric_count"] == 2
        assert stats["by_metric"]["cpu"] == 2
        assert stats["by_metric"]["mem"] == 1
        assert stats["by_source"]["host-a"] == 2
        assert stats["by_source"]["host-b"] == 1

    def test_stats_after_aggregates(self):
        agg = _make()
        base = 1700000000.0
        _record_batch(agg, "cpu", [10.0, 20.0], base_ts=base)
        agg.aggregate("cpu", period="1h")
        stats = agg.get_stats()
        assert stats["total_aggregates"] == 1

    def test_stats_counts_distinct_metrics(self):
        agg = _make()
        agg.record("a", 1.0)
        agg.record("b", 2.0)
        agg.record("c", 3.0)
        stats = agg.get_stats()
        assert stats["metric_count"] == 3


# ===================================================================
# PART 8: EventBus integration (4 tests)
# ===================================================================

class TestEventBusIntegration:
    """Verify EventBus events are emitted."""

    def test_record_emits_metric_recorded(self):
        bus = EventBus(db_path=":memory:")
        agg = _make(event_bus=bus)
        agg.record("cpu", 42.0, source="test")

        events = bus.query(topic="metric.recorded")
        assert len(events) == 1
        payload = json.loads(events[0]["payload"])
        assert payload["metric_name"] == "cpu"
        assert payload["value"] == 42.0
        assert payload["source"] == "test"

    def test_aggregate_emits_metric_aggregated(self):
        bus = EventBus(db_path=":memory:")
        agg = _make(event_bus=bus)
        base = 1700000000.0
        _record_batch(agg, "cpu", [10.0, 20.0], base_ts=base)
        agg.aggregate("cpu", period="1h")

        events = bus.query(topic="metric.aggregated")
        assert len(events) == 1
        payload = json.loads(events[0]["payload"])
        assert payload["metric_name"] == "cpu"
        assert payload["bucket_count"] == 1

    def test_event_source_module(self):
        bus = EventBus(db_path=":memory:")
        agg = _make(event_bus=bus)
        agg.record("x", 1.0)

        events = bus.query(topic="metric.recorded")
        assert events[0]["source_module"] == "monitoring.metric_aggregator"

    def test_no_events_without_bus(self):
        agg = _make()
        # Should not raise
        agg.record("cpu", 1.0)
        base = 1700000000.0
        _record_batch(agg, "cpu", [10.0], base_ts=base)
        agg.aggregate("cpu", period="1h")


# ===================================================================
# PART 9: Thread safety (2 tests)
# ===================================================================

class TestThreadSafety:
    """Verify concurrent access works correctly."""

    def test_concurrent_records(self):
        agg = _make()
        errors: list[Exception] = []

        def writer(offset: int):
            try:
                for i in range(50):
                    agg.record("thread.cpu", float(offset + i))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t * 100,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        points = agg.get_points("thread.cpu")
        assert len(points) == 200

    def test_concurrent_record_and_aggregate(self):
        agg = _make()
        errors: list[Exception] = []
        base = 1700000000.0

        # Pre-populate some points
        _record_batch(agg, "concurrent", [float(i) for i in range(20)], base_ts=base)

        def writer():
            try:
                for i in range(20):
                    agg.record("concurrent", float(i + 100))
            except Exception as exc:
                errors.append(exc)

        def aggregator():
            try:
                for _ in range(5):
                    agg.aggregate("concurrent", period="1h")
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=aggregator),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ===================================================================
# PART 10: Singleton / reset + constants (4 tests)
# ===================================================================

class TestSingletonAndConstants:
    """Verify singleton management and module constants."""

    def setup_method(self):
        reset_metric_aggregator()

    def teardown_method(self):
        reset_metric_aggregator()

    def test_get_metric_aggregator_creates_singleton(self):
        agg = get_metric_aggregator()
        assert isinstance(agg, MetricAggregator)
        agg2 = get_metric_aggregator()
        assert agg is agg2

    def test_reset_clears_singleton(self):
        agg1 = get_metric_aggregator()
        reset_metric_aggregator()
        agg2 = get_metric_aggregator()
        assert agg1 is not agg2

    def test_valid_periods_constant(self):
        assert VALID_PERIODS == ("1m", "5m", "15m", "1h", "6h", "1d", "7d")

    def test_period_seconds_mapping(self):
        assert PERIOD_SECONDS["1m"] == 60.0
        assert PERIOD_SECONDS["5m"] == 300.0
        assert PERIOD_SECONDS["15m"] == 900.0
        assert PERIOD_SECONDS["1h"] == 3600.0
        assert PERIOD_SECONDS["6h"] == 21600.0
        assert PERIOD_SECONDS["1d"] == 86400.0
        assert PERIOD_SECONDS["7d"] == 604800.0
        assert len(PERIOD_SECONDS) == len(VALID_PERIODS)


# ===================================================================
# PART 11: All valid periods (7 tests)
# ===================================================================

class TestAllPeriods:
    """Verify aggregation works for every defined period."""

    @pytest.mark.parametrize("period", VALID_PERIODS)
    def test_aggregate_for_period(self, period):
        agg = _make()
        base = 1700000000.0
        _record_batch(agg, "metric", [1.0, 2.0, 3.0], base_ts=base)
        result = agg.aggregate("metric", period=period)
        assert len(result) >= 1
        assert result[0]["period"] == period
        assert result[0]["count"] == 3
