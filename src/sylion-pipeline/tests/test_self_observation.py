"""Tests for SelfObservation -- self-observation telemetry collection.

22 tests covering record, get_observations, get_aggregate, get_dashboard,
get_stats, thread safety, singleton, and EventBus integration.
"""

import json
import threading

import pytest

from sylion.aeis.self_observation import (
    SelfObservation,
    get_self_observation,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    """Fresh in-memory EventBus capturing events."""
    eb = EventBus()
    eb._captured: list[SylionEvent] = []
    eb.subscribe("*", lambda e: eb._captured.append(e))
    return eb


@pytest.fixture
def obs(bus):
    """Fresh in-memory SelfObservation with EventBus."""
    return SelfObservation(event_bus=bus)


@pytest.fixture
def obs_no_bus():
    """Fresh in-memory SelfObservation without EventBus."""
    return SelfObservation()


# ===================================================================
# Initialization
# ===================================================================

class TestInit:
    def test_default_memory_db(self, obs_no_bus):
        assert obs_no_bus._db_path == ":memory:"

    def test_custom_db_path(self, tmp_path):
        db = tmp_path / "so.db"
        s = SelfObservation(db_path=str(db))
        assert s._db_path == str(db)

    def test_tables_created(self, obs_no_bus):
        tables = obs_no_bus._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "observations" in names
        assert "observation_aggregates" in names

    def test_indexes_created(self, obs_no_bus):
        indexes = obs_no_bus._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        names = {r["name"] for r in indexes}
        assert "idx_obs_metric" in names
        assert "idx_obs_ts" in names

    def test_has_lock(self, obs_no_bus):
        assert isinstance(obs_no_bus._lock, type(threading.Lock()))

    def test_wal_mode_for_file_db(self, tmp_path):
        db = tmp_path / "wal_test.db"
        s = SelfObservation(db_path=str(db))
        mode = s._conn.execute("PRAGMA journal_mode").fetchone()["journal_mode"]
        assert mode == "wal"


# ===================================================================
# Record
# ===================================================================

class TestRecord:
    def test_record_returns_ids(self, obs):
        result = obs.record("cpu_usage", 72.5)
        assert result["observation_id"]
        assert result["metric"] == "cpu_usage"
        assert result["value"] == 72.5

    def test_record_stores_in_db(self, obs):
        r = obs.record("mem_usage", 85.3, unit="percent", source="host-1",
                       tags={"env": "prod"})
        row = obs._conn.execute(
            "SELECT * FROM observations WHERE observation_id = ?",
            (r["observation_id"],),
        ).fetchone()
        assert row is not None
        assert row["metric"] == "mem_usage"
        assert row["value"] == 85.3
        assert row["unit"] == "percent"
        assert row["source"] == "host-1"
        tags = json.loads(row["tags"])
        assert tags["env"] == "prod"

    def test_record_creates_aggregate(self, obs):
        obs.record("latency", 120.0)
        row = obs._conn.execute(
            "SELECT * FROM observation_aggregates WHERE metric = 'latency'"
        ).fetchone()
        assert row is not None
        assert row["avg_value"] == 120.0
        assert row["min_value"] == 120.0
        assert row["max_value"] == 120.0
        assert row["sample_count"] == 1

    def test_record_updates_aggregate_running(self, obs):
        obs.record("latency", 100.0)
        obs.record("latency", 200.0)
        obs.record("latency", 150.0)
        row = obs._conn.execute(
            "SELECT * FROM observation_aggregates WHERE metric = 'latency'"
        ).fetchone()
        assert row["sample_count"] == 3
        assert abs(row["avg_value"] - 150.0) < 0.01
        assert row["min_value"] == 100.0
        assert row["max_value"] == 200.0

    def test_record_default_tags_empty(self, obs):
        r = obs.record("cpu", 50.0)
        row = obs._conn.execute(
            "SELECT tags FROM observations WHERE observation_id = ?",
            (r["observation_id"],),
        ).fetchone()
        assert json.loads(row["tags"]) == {}

    def test_record_emits_event(self, obs, bus):
        obs.record("disk_io", 300.5)
        events = [e for e in bus._captured
                  if e.topic == "aeis.self_observation.recorded"]
        assert len(events) == 1
        assert events[0].payload["metric"] == "disk_io"
        assert events[0].payload["value"] == 300.5

    def test_record_negative_value(self, obs):
        result = obs.record("error_delta", -5.0)
        assert result["value"] == -5.0

    def test_record_zero_value(self, obs):
        result = obs.record("zero_metric", 0.0)
        assert result["value"] == 0.0


# ===================================================================
# get_observations
# ===================================================================

class TestGetObservations:
    def test_empty_returns_empty(self, obs):
        assert obs.get_observations("nonexistent") == []

    def test_returns_observations_for_metric(self, obs):
        obs.record("cpu", 50.0)
        obs.record("cpu", 60.0)
        obs.record("mem", 80.0)
        results = obs.get_observations("cpu")
        assert len(results) == 2
        assert all(r["metric"] == "cpu" for r in results)

    def test_limit_works(self, obs):
        for i in range(10):
            obs.record("cpu", float(i))
        results = obs.get_observations("cpu", limit=3)
        assert len(results) == 3

    def test_tags_parsed_as_dict(self, obs):
        obs.record("cpu", 50.0, tags={"k": "v"})
        results = obs.get_observations("cpu")
        assert isinstance(results[0]["tags"], dict)
        assert results[0]["tags"]["k"] == "v"

    def test_ordered_by_timestamp_desc(self, obs):
        obs.record("cpu", 10.0)
        obs.record("cpu", 20.0)
        results = obs.get_observations("cpu")
        assert results[0]["value"] == 20.0
        assert results[1]["value"] == 10.0


# ===================================================================
# get_aggregate
# ===================================================================

class TestGetAggregate:
    def test_not_found_returns_none(self, obs):
        assert obs.get_aggregate("nonexistent") is None

    def test_returns_aggregate(self, obs):
        obs.record("latency", 100.0)
        obs.record("latency", 200.0)
        agg = obs.get_aggregate("latency")
        assert agg is not None
        assert agg["metric"] == "latency"
        assert agg["sample_count"] == 2
        assert abs(agg["avg_value"] - 150.0) < 0.01
        assert agg["min_value"] == 100.0
        assert agg["max_value"] == 200.0


# ===================================================================
# get_dashboard
# ===================================================================

class TestGetDashboard:
    def test_empty_dashboard(self, obs):
        assert obs.get_dashboard() == []

    def test_returns_all_aggregates(self, obs):
        obs.record("cpu", 50.0)
        obs.record("mem", 80.0)
        dashboard = obs.get_dashboard()
        assert len(dashboard) == 2
        metrics = {d["metric"] for d in dashboard}
        assert "cpu" in metrics
        assert "mem" in metrics


# ===================================================================
# get_stats
# ===================================================================

class TestGetStats:
    def test_empty_stats(self, obs):
        stats = obs.get_stats()
        assert stats["total_observations"] == 0
        assert stats["unique_metrics"] == 0
        assert stats["by_metric"] == {}

    def test_stats_counts(self, obs):
        obs.record("cpu", 50.0)
        obs.record("cpu", 60.0)
        obs.record("mem", 80.0)
        stats = obs.get_stats()
        assert stats["total_observations"] == 3
        assert stats["unique_metrics"] == 2
        assert stats["by_metric"]["cpu"] == 2
        assert stats["by_metric"]["mem"] == 1


# ===================================================================
# Thread safety
# ===================================================================

class TestThreadSafety:
    def test_concurrent_records_same_metric(self, obs):
        errors = []

        def record_val(n):
            try:
                obs.record("counter", float(n))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_val, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        count = obs._conn.execute("SELECT COUNT(*) as c FROM observations").fetchone()
        assert count["c"] == 20
        agg = obs.get_aggregate("counter")
        assert agg["sample_count"] == 20

    def test_concurrent_records_different_metrics(self, obs):
        errors = []

        def record_metric(m):
            try:
                for v in range(5):
                    obs.record(m, float(v))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_metric, args=(f"metric_{i}",))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        count = obs._conn.execute("SELECT COUNT(*) as c FROM observations").fetchone()
        assert count["c"] == 50


# ===================================================================
# Singleton
# ===================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        import sylion.aeis.self_observation as mod
        mod._observer = None
        s = get_self_observation()
        assert isinstance(s, SelfObservation)
        mod._observer = None

    def test_singleton_returns_same_instance(self):
        import sylion.aeis.self_observation as mod
        mod._observer = None
        s1 = get_self_observation()
        s2 = get_self_observation()
        assert s1 is s2
        mod._observer = None


# ===================================================================
# EventBus integration
# ===================================================================

class TestEventBusIntegration:
    def test_no_bus_no_error(self, obs_no_bus):
        obs_no_bus.record("cpu", 50.0)
        # No crash = success

    def test_event_source_module(self, obs, bus):
        obs.record("cpu", 50.0)
        events = [e for e in bus._captured
                  if e.topic == "aeis.self_observation.recorded"]
        assert events[0].source_module == "aeis.self_observation"

    def test_multiple_events(self, obs, bus):
        obs.record("cpu", 50.0)
        obs.record("mem", 80.0)
        events = [e for e in bus._captured
                  if e.topic == "aeis.self_observation.recorded"]
        assert len(events) == 2
