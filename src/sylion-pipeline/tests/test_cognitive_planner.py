"""
SYLION Cognitive -- Planner Tests

Tests for Planner: plan CRUD, task management, decomposition,
dependency resolution, get_next_task, status filtering, and event emission.
"""

from __future__ import annotations

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.planner import Planner, PlanStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def planner(bus):
    return Planner(event_bus=bus)


# ---------------------------------------------------------------------------
# Plan CRUD
# ---------------------------------------------------------------------------

class TestPlanCreateRead:

    def test_create_plan_returns_dict(self, planner):
        result = planner.create_plan("Migration Plan", "Migrate DB to PG")
        assert "plan_id" in result
        assert result["title"] == "Migration Plan"
        assert result["status"] == "pending"

    def test_create_plan_with_parent(self, planner):
        parent = planner.create_plan("Parent Plan")
        child = planner.create_plan("Child Plan", parent_plan=parent["plan_id"])
        assert child["plan_id"] != parent["plan_id"]

    def test_get_plan(self, planner):
        p = planner.create_plan("Fetchable")
        fetched = planner.get_plan(p["plan_id"])
        assert fetched is not None
        assert fetched["title"] == "Fetchable"
        assert fetched["description"] == ""

    def test_get_plan_not_found(self, planner):
        assert planner.get_plan("ghost") is None

    def test_create_plan_emits_event(self, planner, bus):
        events = []
        bus.subscribe("plan.created", lambda e: events.append(e))
        planner.create_plan("Eventful Plan")
        assert len(events) == 1
        assert events[0].payload["title"] == "Eventful Plan"

    def test_create_plan_with_description(self, planner):
        p = planner.create_plan("Titled", description="Detailed desc")
        fetched = planner.get_plan(p["plan_id"])
        assert fetched["description"] == "Detailed desc"


class TestPlanList:

    def test_list_plans_returns_all(self, planner):
        planner.create_plan("A")
        planner.create_plan("B")
        planner.create_plan("C")
        assert len(planner.list_plans()) == 3

    def test_list_plans_filter_by_status(self, planner):
        planner.create_plan("Pending 1")
        planner.create_plan("Pending 2")
        pending = planner.list_plans(status="pending")
        assert len(pending) == 2

    def test_list_plans_filter_nonexistent_status(self, planner):
        planner.create_plan("X")
        assert planner.list_plans(status="nonexistent") == []


# ---------------------------------------------------------------------------
# Task operations
# ---------------------------------------------------------------------------

class TestTaskCreate:

    def test_add_task(self, planner):
        plan = planner.create_plan("Task Plan")
        task = planner.add_task(plan["plan_id"], "Implement auth", "Write JWT module")
        assert "task_id" in task
        assert task["plan_id"] == plan["plan_id"]
        assert task["status"] == "pending"
        assert task["priority"] == 0

    def test_add_task_with_priority(self, planner):
        plan = planner.create_plan("Priority Plan")
        task = planner.add_task(plan["plan_id"], "High prio", priority=10)
        assert task["priority"] == 10

    def test_add_task_with_dependencies(self, planner):
        plan = planner.create_plan("Dep Plan")
        t1 = planner.add_task(plan["plan_id"], "First")
        t2 = planner.add_task(plan["plan_id"], "Second", depends_on=[t1["task_id"]])
        assert t2["task_id"] != ""

    def test_add_task_emits_event(self, planner, bus):
        events = []
        bus.subscribe("task.added", lambda e: events.append(e))
        plan = planner.create_plan("Ev Plan")
        planner.add_task(plan["plan_id"], "Ev Task")
        assert len(events) == 1

    def test_get_tasks_for_plan(self, planner):
        plan = planner.create_plan("Multi Task")
        planner.add_task(plan["plan_id"], "T1")
        planner.add_task(plan["plan_id"], "T2")
        planner.add_task(plan["plan_id"], "T3")
        tasks = planner.get_tasks(plan["plan_id"])
        assert len(tasks) == 3


class TestTaskComplete:

    def test_complete_task(self, planner):
        plan = planner.create_plan("Comp Plan")
        task = planner.add_task(plan["plan_id"], "Do it")
        completed = planner.complete_task(task["task_id"])
        assert completed is not None
        assert completed["status"] == PlanStatus.COMPLETED.value
        assert completed["completed_at"] > 0

    def test_complete_task_emits_event(self, planner, bus):
        events = []
        bus.subscribe("task.completed", lambda e: events.append(e))
        plan = planner.create_plan("Ev Comp")
        task = planner.add_task(plan["plan_id"], "Ev")
        planner.complete_task(task["task_id"])
        assert len(events) == 1

    def test_complete_nonexistent_task(self, planner):
        assert planner.complete_task("ghost") is None

    def test_complete_task_twice(self, planner):
        plan = planner.create_plan("Double Comp")
        task = planner.add_task(plan["plan_id"], "Once only")
        first = planner.complete_task(task["task_id"])
        assert first is not None
        second = planner.complete_task(task["task_id"])
        # Second update matches no rows since status is no longer 'pending'
        # Actually the SQL updates unconditionally, so it returns rowcount=1 again
        # because the WHERE only filters by task_id. Let's check the actual behavior.
        # The SQL: UPDATE tasks SET status = ?, completed_at = ? WHERE task_id = ?
        # No status filter, so it will update again.
        assert second is not None


class TestTaskDecompose:

    def test_decompose_creates_multiple_tasks(self, planner):
        plan = planner.create_plan("Decomp Plan")
        subtasks = [
            {"title": "Step 1", "priority": 3},
            {"title": "Step 2", "priority": 2},
            {"title": "Step 3", "priority": 1},
        ]
        results = planner.decompose(plan["plan_id"], subtasks)
        assert len(results) == 3
        assert results[0]["priority"] == 3

    def test_decompose_emits_event(self, planner, bus):
        events = []
        bus.subscribe("plan.decomposed", lambda e: events.append(e))
        plan = planner.create_plan("Decomp Ev")
        planner.decompose(plan["plan_id"], [{"title": "A"}, {"title": "B"}])
        assert len(events) == 1
        assert events[0].payload["task_count"] == 2

    def test_decompose_empty_list(self, planner):
        plan = planner.create_plan("Empty Decomp")
        results = planner.decompose(plan["plan_id"], [])
        assert results == []


class TestGetNextTask:

    def test_returns_highest_priority_pending(self, planner):
        plan = planner.create_plan("Next Plan")
        planner.add_task(plan["plan_id"], "Low", priority=1)
        planner.add_task(plan["plan_id"], "High", priority=10)
        planner.add_task(plan["plan_id"], "Mid", priority=5)
        next_task = planner.get_next_task(plan["plan_id"])
        assert next_task["title"] == "High"

    def test_returns_none_when_no_pending(self, planner):
        plan = planner.create_plan("Empty Next")
        assert planner.get_next_task(plan["plan_id"]) is None

    def test_skips_tasks_with_unmet_dependencies(self, planner):
        plan = planner.create_plan("Dep Next")
        t1 = planner.add_task(plan["plan_id"], "Blocker", priority=1)
        t2 = planner.add_task(plan["plan_id"], "Blocked", priority=10,
                              depends_on=[t1["task_id"]])
        next_task = planner.get_next_task(plan["plan_id"])
        assert next_task["title"] == "Blocker"

    def test_dependency_met_after_completion(self, planner):
        plan = planner.create_plan("Dep Met")
        t1 = planner.add_task(plan["plan_id"], "First", priority=1)
        t2 = planner.add_task(plan["plan_id"], "Second", priority=10,
                              depends_on=[t1["task_id"]])
        planner.complete_task(t1["task_id"])
        next_task = planner.get_next_task(plan["plan_id"])
        assert next_task["title"] == "Second"

    def test_no_eligible_tasks_all_blocked(self, planner):
        plan = planner.create_plan("All Blocked")
        t1 = planner.add_task(plan["plan_id"], "A", priority=1)
        t2 = planner.add_task(plan["plan_id"], "B", priority=2,
                              depends_on=[t1["task_id"]])
        t3 = planner.add_task(plan["plan_id"], "C", priority=3,
                              depends_on=[t2["task_id"]])
        # Remove t1 from pending to simulate all blocked
        planner.complete_task(t1["task_id"])
        # t2 depends on t1 (done), t3 depends on t2 (pending)
        next_task = planner.get_next_task(plan["plan_id"])
        assert next_task["title"] == "B"

    def test_get_tasks_filtered_by_status(self, planner):
        plan = planner.create_plan("Filter Plan")
        t1 = planner.add_task(plan["plan_id"], "Pending")
        t2 = planner.add_task(plan["plan_id"], "Done")
        planner.complete_task(t2["task_id"])
        pending = planner.get_tasks(plan["plan_id"], status="pending")
        completed = planner.get_tasks(plan["plan_id"], status="completed")
        assert len(pending) == 1
        assert len(completed) == 1
        assert pending[0]["title"] == "Pending"
