"""Tests for SYLION Execution Task Scheduler (40+ tests)."""

import json
import time

import pytest

from sylion.execution.task_scheduler import (
    TaskScheduler,
    get_task_scheduler,
    reset_task_scheduler,
)
from sylion.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def scheduler(event_bus):
    return TaskScheduler(event_bus=event_bus)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_task_scheduler()
    yield
    reset_task_scheduler()


# ===========================================================================
# 1. Schedule / Update / Cancel Tasks
# ===========================================================================

def test_schedule_task_returns_dict(scheduler):
    result = scheduler.schedule_task("backup", "cron", "0 * * * *", '{"retention": 7}')
    assert result["task_id"]
    assert result["name"] == "backup"
    assert result["task_type"] == "cron"
    assert result["cron_expr"] == "0 * * * *"
    assert result["status"] == "active"
    assert result["created_at"] > 0


def test_schedule_task_default_config(scheduler):
    result = scheduler.schedule_task("cleanup", "batch", "0 0 * * *")
    assert result["config_json"] == "{}"


def test_schedule_multiple_tasks(scheduler):
    t1 = scheduler.schedule_task("a", "cron", "* * * * *")
    t2 = scheduler.schedule_task("b", "batch", "0 0 * * *")
    assert t1["task_id"] != t2["task_id"]


def test_update_task_name(scheduler):
    task = scheduler.schedule_task("old", "cron", "* * * * *")
    updated = scheduler.update_task(task["task_id"], name="new")
    assert updated["name"] == "new"


def test_update_task_cron(scheduler):
    task = scheduler.schedule_task("x", "cron", "* * * * *")
    updated = scheduler.update_task(task["task_id"], cron_expr="0 0 * * *")
    assert updated["cron_expr"] == "0 0 * * *"


def test_update_task_updates_timestamp(scheduler):
    task = scheduler.schedule_task("ts", "cron", "* * * * *")
    time.sleep(0.01)
    updated = scheduler.update_task(task["task_id"], name="ts2")
    assert updated["updated_at"] >= task["created_at"]


def test_update_task_nonexistent(scheduler):
    assert scheduler.update_task("nope", name="x") is None


def test_update_task_unknown_field_raises(scheduler):
    task = scheduler.schedule_task("x", "cron", "* * * * *")
    with pytest.raises(ValueError, match="unknown field"):
        scheduler.update_task(task["task_id"], bad_field="x")


def test_update_task_no_fields_returns_existing(scheduler):
    task = scheduler.schedule_task("x", "cron", "* * * * *")
    result = scheduler.update_task(task["task_id"])
    assert result["task_id"] == task["task_id"]


def test_cancel_task(scheduler):
    task = scheduler.schedule_task("cancel-me", "cron", "* * * * *")
    result = scheduler.cancel_task(task["task_id"])
    assert result["status"] == "cancelled"
    fetched = scheduler.get_task(task["task_id"])
    assert fetched["status"] == "cancelled"


def test_cancel_task_nonexistent(scheduler):
    assert scheduler.cancel_task("nope") is None


# ===========================================================================
# 2. Get / List Tasks
# ===========================================================================

def test_get_task(scheduler):
    task = scheduler.schedule_task("find-me", "cron", "* * * * *")
    fetched = scheduler.get_task(task["task_id"])
    assert fetched["name"] == "find-me"


def test_get_task_nonexistent(scheduler):
    assert scheduler.get_task("nope") is None


def test_list_tasks_all(scheduler):
    scheduler.schedule_task("a", "cron", "* * * * *")
    scheduler.schedule_task("b", "batch", "0 0 * * *")
    tasks = scheduler.list_tasks()
    assert len(tasks) == 2


def test_list_tasks_by_status(scheduler):
    t1 = scheduler.schedule_task("active", "cron", "* * * * *")
    t2 = scheduler.schedule_task("to-cancel", "cron", "* * * * *")
    scheduler.cancel_task(t2["task_id"])
    active = scheduler.list_tasks(status="active")
    assert len(active) == 1
    assert active[0]["task_id"] == t1["task_id"]


def test_list_tasks_by_type(scheduler):
    scheduler.schedule_task("a", "cron", "* * * * *")
    scheduler.schedule_task("b", "cron", "0 0 * * *")
    scheduler.schedule_task("c", "batch", "0 0 * * *")
    cron_tasks = scheduler.list_tasks(task_type="cron")
    assert len(cron_tasks) == 2


def test_list_tasks_combined_filter(scheduler):
    t1 = scheduler.schedule_task("a", "cron", "* * * * *")
    t2 = scheduler.schedule_task("b", "cron", "0 0 * * *")
    scheduler.cancel_task(t2["task_id"])
    active_cron = scheduler.list_tasks(status="active", task_type="cron")
    assert len(active_cron) == 1


def test_list_tasks_empty(scheduler):
    assert scheduler.list_tasks() == []


# ===========================================================================
# 3. Executions
# ===========================================================================

def test_record_execution_success(scheduler):
    task = scheduler.schedule_task("exec-ok", "cron", "* * * * *")
    ex = scheduler.record_execution(task["task_id"], "success", '{"rows": 10}', 150)
    assert ex["execution_id"]
    assert ex["status"] == "success"
    assert ex["duration_ms"] == 150


def test_record_execution_failed(scheduler):
    task = scheduler.schedule_task("exec-fail", "cron", "* * * * *")
    ex = scheduler.record_execution(task["task_id"], "failed", '{"error": "timeout"}', 30000)
    assert ex["status"] == "failed"


def test_record_execution_default_duration(scheduler):
    task = scheduler.schedule_task("exec-no-dur", "cron", "* * * * *")
    ex = scheduler.record_execution(task["task_id"], "success")
    assert ex["duration_ms"] is None


def test_get_executions_by_task(scheduler):
    task = scheduler.schedule_task("exec-list", "cron", "* * * * *")
    scheduler.record_execution(task["task_id"], "success", '{}', 100)
    scheduler.record_execution(task["task_id"], "failed", '{}', 200)
    execs = scheduler.get_executions(task_id=task["task_id"])
    assert len(execs) == 2


def test_get_executions_all(scheduler):
    t1 = scheduler.schedule_task("a", "cron", "* * * * *")
    t2 = scheduler.schedule_task("b", "cron", "* * * * *")
    scheduler.record_execution(t1["task_id"], "success")
    scheduler.record_execution(t2["task_id"], "success")
    execs = scheduler.get_executions()
    assert len(execs) == 2


def test_get_executions_with_limit(scheduler):
    task = scheduler.schedule_task("lim", "cron", "* * * * *")
    for i in range(10):
        scheduler.record_execution(task["task_id"], "success", '{}', i * 10)
    execs = scheduler.get_executions(task_id=task["task_id"], limit=3)
    assert len(execs) == 3


def test_get_executions_empty(scheduler):
    assert scheduler.get_executions() == []


# ===========================================================================
# 4. Dependencies
# ===========================================================================

def test_add_dependency(scheduler):
    t1 = scheduler.schedule_task("parent", "cron", "* * * * *")
    t2 = scheduler.schedule_task("child", "cron", "* * * * *")
    dep = scheduler.add_dependency(t2["task_id"], t1["task_id"])
    assert dep["dependency_id"]
    assert dep["task_id"] == t2["task_id"]
    assert dep["depends_on_task_id"] == t1["task_id"]


def test_add_multiple_dependencies(scheduler):
    t1 = scheduler.schedule_task("a", "cron", "* * * * *")
    t2 = scheduler.schedule_task("b", "cron", "* * * * *")
    t3 = scheduler.schedule_task("c", "cron", "* * * * *")
    scheduler.add_dependency(t3["task_id"], t1["task_id"])
    scheduler.add_dependency(t3["task_id"], t2["task_id"])
    # Both deps recorded (no list method on deps, verify via stats)
    stats = scheduler.get_task_stats()
    assert stats["total_dependencies"] == 2


def test_remove_dependency(scheduler):
    t1 = scheduler.schedule_task("a", "cron", "* * * * *")
    t2 = scheduler.schedule_task("b", "cron", "* * * * *")
    dep = scheduler.add_dependency(t2["task_id"], t1["task_id"])
    result = scheduler.remove_dependency(dep["dependency_id"])
    assert result["removed"] is True
    stats = scheduler.get_task_stats()
    assert stats["total_dependencies"] == 0


def test_remove_dependency_nonexistent(scheduler):
    assert scheduler.remove_dependency("nope") is None


# ===========================================================================
# 5. Stats
# ===========================================================================

def test_get_task_stats_empty(scheduler):
    stats = scheduler.get_task_stats()
    assert stats["total_tasks"] == 0
    assert stats["active_tasks"] == 0
    assert stats["total_executions"] == 0
    assert stats["failure_rate"] == 0.0


def test_get_task_stats_populated(scheduler):
    t1 = scheduler.schedule_task("a", "cron", "* * * * *")
    t2 = scheduler.schedule_task("b", "batch", "0 0 * * *")
    scheduler.record_execution(t1["task_id"], "success", '{}', 100)
    scheduler.record_execution(t1["task_id"], "failed", '{}', 500)
    scheduler.add_dependency(t2["task_id"], t1["task_id"])

    stats = scheduler.get_task_stats()
    assert stats["total_tasks"] == 2
    assert stats["active_tasks"] == 2
    assert stats["total_executions"] == 2
    assert stats["failed_executions"] == 1
    assert stats["failure_rate"] == 50.0
    assert stats["total_dependencies"] == 1
    assert stats["by_task_type"]["cron"] == 1
    assert stats["by_task_type"]["batch"] == 1


# ===========================================================================
# 6. Events
# ===========================================================================

def test_schedule_task_emits_event(scheduler, event_bus):
    scheduler.schedule_task("ev-task", "cron", "* * * * *")
    events = event_bus.query(topic="execution.task_scheduled")
    assert len(events) == 1
    payload = events[0]["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload["name"] == "ev-task"


def test_record_success_emits_executed(scheduler, event_bus):
    task = scheduler.schedule_task("ev-ok", "cron", "* * * * *")
    scheduler.record_execution(task["task_id"], "success")
    events = event_bus.query(topic="execution.task_executed")
    assert len(events) == 1


def test_record_failure_emits_failed(scheduler, event_bus):
    task = scheduler.schedule_task("ev-fail", "cron", "* * * * *")
    scheduler.record_execution(task["task_id"], "failed")
    events = event_bus.query(topic="execution.task_failed")
    assert len(events) == 1


def test_add_dependency_emits_event(scheduler, event_bus):
    t1 = scheduler.schedule_task("a", "cron", "* * * * *")
    t2 = scheduler.schedule_task("b", "cron", "* * * * *")
    scheduler.add_dependency(t2["task_id"], t1["task_id"])
    events = event_bus.query(topic="execution.dependency_added")
    assert len(events) == 1


def test_update_task_emits_event(scheduler, event_bus):
    task = scheduler.schedule_task("ev-upd", "cron", "* * * * *")
    scheduler.update_task(task["task_id"], name="updated")
    events = event_bus.query(topic="execution.task_updated")
    assert len(events) == 1


def test_no_event_without_bus():
    sched = TaskScheduler(event_bus=None)
    task = sched.schedule_task("no-ev", "cron", "* * * * *")
    assert task["status"] == "active"
    sched.close()


# ===========================================================================
# 7. Singleton
# ===========================================================================

def test_get_task_scheduler_singleton():
    a = get_task_scheduler()
    b = get_task_scheduler()
    assert a is b


def test_reset_task_scheduler():
    a = get_task_scheduler()
    reset_task_scheduler()
    b = get_task_scheduler()
    assert a is not b


# ===========================================================================
# 8. Close / Persistent DB
# ===========================================================================

def test_close(scheduler):
    scheduler.schedule_task("x", "cron", "* * * * *")
    scheduler.close()


def test_persistent_db(tmp_path):
    db_file = tmp_path / "ts_test.db"
    sched = TaskScheduler(db_path=str(db_file))
    task = sched.schedule_task("persist", "cron", "* * * * *")
    sched.record_execution(task["task_id"], "success", '{}', 50)
    sched.close()
    sched2 = TaskScheduler(db_path=str(db_file))
    fetched = sched2.get_task(task["task_id"])
    assert fetched is not None
    assert fetched["name"] == "persist"
    execs = sched2.get_executions(task_id=task["task_id"])
    assert len(execs) == 1
    sched2.close()


# ===========================================================================
# 9. Integration
# ===========================================================================

def test_full_task_lifecycle(scheduler, event_bus):
    t1 = scheduler.schedule_task("extract", "cron", "0 * * * *")
    t2 = scheduler.schedule_task("transform", "cron", "30 * * * *")
    scheduler.add_dependency(t2["task_id"], t1["task_id"])

    # Run extract successfully
    scheduler.record_execution(t1["task_id"], "success", '{"rows": 1000}', 200)

    # Run transform
    scheduler.record_execution(t2["task_id"], "success", '{"rows": 950}', 500)

    stats = scheduler.get_task_stats()
    assert stats["total_tasks"] == 2
    assert stats["total_executions"] == 2
    assert stats["failure_rate"] == 0.0
    assert stats["total_dependencies"] == 1


def test_task_failure_and_retry(scheduler):
    task = scheduler.schedule_task("retry-me", "cron", "* * * * *")
    scheduler.record_execution(task["task_id"], "failed", '{"error": "timeout"}', 30000)
    scheduler.record_execution(task["task_id"], "failed", '{"error": "timeout"}', 30000)
    scheduler.record_execution(task["task_id"], "success", '{}', 150)

    execs = scheduler.get_executions(task_id=task["task_id"])
    assert len(execs) == 3
    stats = scheduler.get_task_stats()
    assert stats["failed_executions"] == 2
    assert stats["failure_rate"] == pytest.approx(66.67, rel=0.01)
