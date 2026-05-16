"""Tests for SYLION Monitoring Pipeline Monitor (40+ tests)."""

import json
import time

import pytest

from sylion.monitoring.pipeline_monitor import (
    PipelineMonitor,
    get_pipeline_monitor,
    reset_pipeline_monitor,
)
from sylion.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def monitor(event_bus):
    return PipelineMonitor(event_bus=event_bus)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_pipeline_monitor()
    yield
    reset_pipeline_monitor()


# ===========================================================================
# 1. Start / End Runs
# ===========================================================================

def test_start_run_returns_dict(monitor):
    run = monitor.start_run("pipe-1", '{"workers": 4}')
    assert run["run_id"]
    assert run["pipeline_id"] == "pipe-1"
    assert run["status"] == "running"
    assert run["started_at"] > 0


def test_start_run_default_config(monitor):
    run = monitor.start_run("pipe-2")
    assert run["config_json"] == "{}"


def test_end_run_completed(monitor):
    run = monitor.start_run("pipe-3")
    result = monitor.end_run(run["run_id"], "completed", '{"rows": 100}')
    assert result["status"] == "completed"
    assert result["ended_at"] is not None


def test_end_run_failed(monitor):
    run = monitor.start_run("pipe-4")
    result = monitor.end_run(run["run_id"], "failed", '{"error": "timeout"}')
    assert result["status"] == "failed"


def test_end_run_nonexistent(monitor):
    assert monitor.end_run("nope", "completed") is None


def test_end_run_default_status(monitor):
    run = monitor.start_run("pipe-5")
    result = monitor.end_run(run["run_id"])
    assert result["status"] == "completed"


# ===========================================================================
# 2. Get / List Runs
# ===========================================================================

def test_get_run(monitor):
    run = monitor.start_run("pipe-get")
    fetched = monitor.get_run(run["run_id"])
    assert fetched["pipeline_id"] == "pipe-get"


def test_get_run_nonexistent(monitor):
    assert monitor.get_run("nope") is None


def test_list_runs_all(monitor):
    monitor.start_run("a")
    monitor.start_run("b")
    runs = monitor.list_runs()
    assert len(runs) == 2


def test_list_runs_by_pipeline(monitor):
    monitor.start_run("pipe-x")
    monitor.start_run("pipe-y")
    monitor.start_run("pipe-x")
    runs = monitor.list_runs(pipeline_id="pipe-x")
    assert len(runs) == 2


def test_list_runs_by_status(monitor):
    r1 = monitor.start_run("a")
    monitor.start_run("b")
    monitor.end_run(r1["run_id"], "completed")
    running = monitor.list_runs(status="running")
    assert len(running) == 1


def test_list_runs_combined_filter(monitor):
    r1 = monitor.start_run("p1")
    monitor.start_run("p1")
    monitor.end_run(r1["run_id"], "completed")
    completed = monitor.list_runs(pipeline_id="p1", status="completed")
    assert len(completed) == 1


def test_list_runs_empty(monitor):
    assert monitor.list_runs() == []


# ===========================================================================
# 3. Metrics
# ===========================================================================

def test_record_metric(monitor):
    run = monitor.start_run("metric-pipe")
    metric = monitor.record_metric(run["run_id"], "duration_ms", 1234.5)
    assert metric["metric_id"]
    assert metric["metric_name"] == "duration_ms"
    assert metric["value"] == 1234.5


def test_record_multiple_metrics(monitor):
    run = monitor.start_run("multi-metric")
    monitor.record_metric(run["run_id"], "duration_ms", 500)
    monitor.record_metric(run["run_id"], "rows_processed", 1000)
    metrics = monitor.get_metrics(run["run_id"])
    assert len(metrics) == 2


def test_get_metrics_empty(monitor):
    run = monitor.start_run("empty-metric")
    assert monitor.get_metrics(run["run_id"]) == []


def test_get_metrics_nonexistent_run(monitor):
    assert monitor.get_metrics("nope") == []


# ===========================================================================
# 4. Alerts
# ===========================================================================

def test_create_alert(monitor):
    alert = monitor.create_alert("pipe-1", "timeout", "Pipeline timed out after 60s")
    assert alert["alert_id"]
    assert alert["pipeline_id"] == "pipe-1"
    assert alert["alert_type"] == "timeout"
    assert alert["acknowledged"] == 0


def test_list_alerts_all(monitor):
    monitor.create_alert("p1", "timeout", "t1")
    monitor.create_alert("p2", "error", "e1")
    alerts = monitor.list_alerts()
    assert len(alerts) == 2


def test_list_alerts_by_pipeline(monitor):
    monitor.create_alert("p1", "timeout", "t1")
    monitor.create_alert("p2", "error", "e1")
    alerts = monitor.list_alerts(pipeline_id="p1")
    assert len(alerts) == 1


def test_list_alerts_by_acknowledged(monitor):
    a1 = monitor.create_alert("p1", "timeout", "t1")
    monitor.create_alert("p2", "error", "e1")
    monitor.acknowledge_alert(a1["alert_id"])
    unack = monitor.list_alerts(acknowledged=False)
    assert len(unack) == 1
    acked = monitor.list_alerts(acknowledged=True)
    assert len(acked) == 1


def test_acknowledge_alert(monitor):
    alert = monitor.create_alert("p1", "timeout", "t1")
    result = monitor.acknowledge_alert(alert["alert_id"])
    assert result["acknowledged"] == 1


def test_acknowledge_alert_nonexistent(monitor):
    assert monitor.acknowledge_alert("nope") is None


def test_list_alerts_empty(monitor):
    assert monitor.list_alerts() == []


# ===========================================================================
# 5. Stats
# ===========================================================================

def test_get_pipeline_stats_empty(monitor):
    stats = monitor.get_pipeline_stats()
    assert stats["total_runs"] == 0
    assert stats["success_rate"] == 0.0
    assert stats["unacknowledged_alerts"] == 0


def test_get_pipeline_stats_with_data(monitor):
    r1 = monitor.start_run("p1")
    r2 = monitor.start_run("p1")
    monitor.end_run(r1["run_id"], "completed")
    monitor.end_run(r2["run_id"], "failed")
    monitor.record_metric(r1["run_id"], "duration", 100)
    monitor.create_alert("p1", "error", "Run failed")
    stats = monitor.get_pipeline_stats()
    assert stats["total_runs"] == 2
    assert stats["completed_runs"] == 1
    assert stats["failed_runs"] == 1
    assert stats["success_rate"] == 50.0
    assert stats["total_metrics"] == 1
    assert stats["total_alerts"] == 1
    assert stats["running_runs"] == 0


# ===========================================================================
# 6. Events
# ===========================================================================

def test_start_run_emits_event(monitor, event_bus):
    monitor.start_run("ev-pipe")
    events = event_bus.query(topic="pipeline.run_started")
    assert len(events) == 1
    payload = events[0]["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload["pipeline_id"] == "ev-pipe"


def test_end_run_emits_event(monitor, event_bus):
    run = monitor.start_run("ev-end")
    monitor.end_run(run["run_id"], "completed")
    events = event_bus.query(topic="pipeline.run_completed")
    assert len(events) == 1


def test_record_metric_emits_event(monitor, event_bus):
    run = monitor.start_run("ev-metric")
    monitor.record_metric(run["run_id"], "x", 42)
    events = event_bus.query(topic="pipeline.metric_recorded")
    assert len(events) == 1


def test_create_alert_emits_event(monitor, event_bus):
    monitor.create_alert("ev-alert-pipe", "timeout", "test")
    events = event_bus.query(topic="pipeline.alert_created")
    assert len(events) == 1


def test_no_event_without_bus():
    mon = PipelineMonitor(event_bus=None)
    run = mon.start_run("no-ev")
    assert run["status"] == "running"
    mon.close()


# ===========================================================================
# 7. Singleton
# ===========================================================================

def test_get_pipeline_monitor_singleton():
    a = get_pipeline_monitor()
    b = get_pipeline_monitor()
    assert a is b


def test_reset_pipeline_monitor():
    a = get_pipeline_monitor()
    reset_pipeline_monitor()
    b = get_pipeline_monitor()
    assert a is not b


# ===========================================================================
# 8. Close / Persistent DB
# ===========================================================================

def test_close(monitor):
    monitor.start_run("x")
    monitor.close()


def test_persistent_db(tmp_path):
    db_file = tmp_path / "pm_test.db"
    mon = PipelineMonitor(db_path=str(db_file))
    run = mon.start_run("persist-pipe")
    mon.end_run(run["run_id"], "completed")
    mon.close()
    mon2 = PipelineMonitor(db_path=str(db_file))
    fetched = mon2.get_run(run["run_id"])
    assert fetched is not None
    assert fetched["status"] == "completed"
    mon2.close()


# ===========================================================================
# 9. Integration
# ===========================================================================

def test_full_pipeline_lifecycle(monitor, event_bus):
    run = monitor.start_run("lifecycle-pipe", '{"stages": 3}')
    monitor.record_metric(run["run_id"], "duration_ms", 2500)
    monitor.record_metric(run["run_id"], "memory_mb", 128)
    monitor.end_run(run["run_id"], "completed", '{"output": "ok"}')

    metrics = monitor.get_metrics(run["run_id"])
    assert len(metrics) == 2

    stats = monitor.get_pipeline_stats()
    assert stats["total_runs"] == 1
    assert stats["success_rate"] == 100.0


def test_failed_run_triggers_alert(monitor):
    run = monitor.start_run("fail-pipe")
    monitor.end_run(run["run_id"], "failed", '{"error": "OOM"}')
    monitor.create_alert("fail-pipe", "failure", "Pipeline OOM")

    alerts = monitor.list_alerts(pipeline_id="fail-pipe", acknowledged=False)
    assert len(alerts) == 1

    monitor.acknowledge_alert(alerts[0]["alert_id"])
    assert len(monitor.list_alerts(acknowledged=True)) == 1


def test_multiple_pipelines_stats(monitor):
    r1 = monitor.start_run("a")
    r2 = monitor.start_run("b")
    r3 = monitor.start_run("a")
    monitor.end_run(r1["run_id"], "completed")
    monitor.end_run(r2["run_id"], "completed")
    monitor.end_run(r3["run_id"], "failed")

    stats = monitor.get_pipeline_stats()
    assert stats["total_runs"] == 3
    assert stats["completed_runs"] == 2
    assert stats["failed_runs"] == 1
    assert stats["success_rate"] == pytest.approx(66.67, rel=0.01)
