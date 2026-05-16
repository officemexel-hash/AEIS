"""
Comprehensive tests for sylion.rebuild.cutover_controller -- CutoverController

Covers:
  - create_plan CRUD (create, get_plan, list_plans)
  - create_plan with auto_rollback flag
  - execute transitions plan to completed and updates current_state
  - execute records cutover.executed event in DB
  - execute for nonexistent plan returns error dict
  - rollback transitions plan to rolled_back and sets target_state = current_state
  - rollback for nonexistent plan returns error dict
  - record_event persists event with details JSON
  - list_plans filtered by status and module_id
  - get_plan returns None for unknown IDs
  - plan_id auto-generation
  - event emission via EventBus
  - thread safety under concurrent plan creation
"""

from __future__ import annotations

import json
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.rebuild.cutover_controller import CutoverController


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def controller():
    """Fresh in-memory CutoverController with no event bus."""
    return CutoverController()


@pytest.fixture
def controller_with_bus():
    """Controller wired to a fresh EventBus."""
    bus = EventBus()
    ctrl = CutoverController(event_bus=bus)
    return ctrl, bus


# ===========================================================================
# 1. create_plan() -- create
# ===========================================================================

class TestCreatePlan:

    def test_create_plan_returns_plan_id(self, controller):
        result = controller.create_plan("mod-alpha")
        assert "plan_id" in result
        assert len(result["plan_id"]) == 32  # uuid hex
        assert result["module_id"] == "mod-alpha"
        assert result["status"] == "pending"

    def test_create_plan_default_states(self, controller):
        result = controller.create_plan("mod-beta")
        plan = controller.get_plan(result["plan_id"])
        assert plan["current_state"] == "shadow"
        assert plan["target_state"] == "cutover"

    def test_create_plan_custom_states(self, controller):
        result = controller.create_plan(
            "mod-gamma",
            current_state="dual",
            target_state="stable",
        )
        plan = controller.get_plan(result["plan_id"])
        assert plan["current_state"] == "dual"
        assert plan["target_state"] == "stable"

    def test_create_plan_auto_rollback_flag(self, controller):
        result = controller.create_plan("mod-delta", auto_rollback=True)
        plan = controller.get_plan(result["plan_id"])
        assert plan["auto_rollback"] == 1

    def test_create_plan_auto_rollback_default_false(self, controller):
        result = controller.create_plan("mod-epsilon")
        plan = controller.get_plan(result["plan_id"])
        assert plan["auto_rollback"] == 0

    def test_create_plan_auto_sets_timestamp(self, controller):
        before = time.time()
        result = controller.create_plan("mod-zeta")
        after = time.time()
        plan = controller.get_plan(result["plan_id"])
        assert before <= plan["created_at"] <= after


# ===========================================================================
# 2. get_plan() -- read
# ===========================================================================

class TestGetPlan:

    def test_get_plan_returns_full_record(self, controller):
        controller.create_plan("mod-read", current_state="dual", target_state="cutover")
        plans = controller.list_plans()
        plan_id = plans[0]["plan_id"]

        plan = controller.get_plan(plan_id)
        assert plan is not None
        assert plan["module_id"] == "mod-read"
        assert plan["current_state"] == "dual"
        assert plan["target_state"] == "cutover"
        assert plan["status"] == "pending"

    def test_get_plan_nonexistent_returns_none(self, controller):
        assert controller.get_plan("nonexistent_id") is None


# ===========================================================================
# 3. list_plans() -- query
# ===========================================================================

class TestListPlans:

    def test_list_plans_returns_all(self, controller):
        controller.create_plan("mod-a")
        controller.create_plan("mod-b")
        controller.create_plan("mod-c")
        plans = controller.list_plans()
        assert len(plans) == 3

    def test_list_plans_filter_by_status(self, controller):
        controller.create_plan("mod-draft")
        result = controller.create_plan("mod-exec")
        controller.execute(result["plan_id"])

        pending = controller.list_plans(status="pending")
        assert len(pending) == 1
        assert pending[0]["module_id"] == "mod-draft"

        completed = controller.list_plans(status="completed")
        assert len(completed) == 1
        assert completed[0]["module_id"] == "mod-exec"

    def test_list_plans_filter_by_module_id(self, controller):
        controller.create_plan("mod-x")
        controller.create_plan("mod-y")
        controller.create_plan("mod-x")  # second plan for mod-x

        results = controller.list_plans(module_id="mod-x")
        assert len(results) == 2
        assert all(r["module_id"] == "mod-x" for r in results)

    def test_list_plans_combined_filters(self, controller):
        controller.create_plan("mod-x")
        r2 = controller.create_plan("mod-x")
        controller.execute(r2["plan_id"])

        results = controller.list_plans(module_id="mod-x", status="pending")
        assert len(results) == 1

    def test_list_plans_respects_limit(self, controller):
        for i in range(10):
            controller.create_plan(f"mod-{i}")
        plans = controller.list_plans(limit=3)
        assert len(plans) == 3

    def test_list_plans_ordered_by_created_at_desc(self, controller):
        controller.create_plan("first")
        time.sleep(0.01)
        controller.create_plan("second")
        time.sleep(0.01)
        controller.create_plan("third")
        plans = controller.list_plans()
        assert plans[0]["module_id"] == "third"
        assert plans[2]["module_id"] == "first"


# ===========================================================================
# 4. execute()
# ===========================================================================

class TestExecute:

    def test_execute_marks_completed(self, controller):
        result = controller.create_plan("mod-exec", current_state="shadow", target_state="cutover")
        exec_result = controller.execute(result["plan_id"])

        assert exec_result["status"] == "completed"
        assert exec_result["executed_at"] > 0

        plan = controller.get_plan(result["plan_id"])
        assert plan["status"] == "completed"
        assert plan["executed_at"] > 0

    def test_execute_updates_current_state_to_target(self, controller):
        result = controller.create_plan(
            "mod-transition",
            current_state="shadow",
            target_state="cutover",
        )
        controller.execute(result["plan_id"])
        plan = controller.get_plan(result["plan_id"])
        assert plan["current_state"] == "cutover"

    def test_execute_records_event_in_db(self, controller):
        result = controller.create_plan("mod-event", current_state="shadow", target_state="dual")
        controller.execute(result["plan_id"])

        # record_event is called internally; verify by querying cutover_events table
        rows = controller._conn.execute(
            "SELECT * FROM cutover_events WHERE plan_id = ?",
            (result["plan_id"],),
        ).fetchall()
        assert len(rows) >= 1
        event = dict(rows[0])
        assert event["event_type"] == "cutover.executed"
        details = json.loads(event["details"])
        assert details["previous_state"] == "shadow"
        assert details["new_state"] == "dual"

    def test_execute_nonexistent_returns_error(self, controller):
        result = controller.execute("nonexistent_id")
        assert "error" in result
        assert "not found" in result["error"]


# ===========================================================================
# 5. rollback()
# ===========================================================================

class TestRollback:

    def test_rollback_marks_rolled_back(self, controller):
        result = controller.create_plan(
            "mod-rb",
            current_state="shadow",
            target_state="cutover",
        )
        rb_result = controller.rollback(result["plan_id"])

        assert rb_result["status"] == "rolled_back"
        assert rb_result["executed_at"] > 0

        plan = controller.get_plan(result["plan_id"])
        assert plan["status"] == "rolled_back"

    def test_rollback_sets_target_to_current(self, controller):
        result = controller.create_plan(
            "mod-rb-state",
            current_state="shadow",
            target_state="cutover",
        )
        controller.rollback(result["plan_id"])
        plan = controller.get_plan(result["plan_id"])
        # target_state should now equal current_state (shadow)
        assert plan["target_state"] == plan["current_state"]

    def test_rollback_records_event(self, controller):
        result = controller.create_plan("mod-rb-evt", current_state="dual", target_state="cutover")
        controller.rollback(result["plan_id"])

        rows = controller._conn.execute(
            "SELECT * FROM cutover_events WHERE plan_id = ? AND event_type = ?",
            (result["plan_id"], "cutover.rolled_back"),
        ).fetchall()
        assert len(rows) == 1
        details = json.loads(dict(rows[0])["details"])
        assert details["rolled_back_to"] == "dual"

    def test_rollback_nonexistent_returns_error(self, controller):
        result = controller.rollback("nonexistent_id")
        assert "error" in result
        assert "not found" in result["error"]


# ===========================================================================
# 6. record_event()
# ===========================================================================

class TestRecordEvent:

    def test_record_event_returns_event_id(self, controller):
        result = controller.record_event("plan-123", "test.event", {"key": "value"})
        assert "event_id" in result
        assert len(result["event_id"]) == 32
        assert result["plan_id"] == "plan-123"
        assert result["event_type"] == "test.event"

    def test_record_event_persists_details(self, controller):
        details = {"reason": "manual trigger", "operator": "admin"}
        controller.record_event("plan-abc", "manual.override", details)

        rows = controller._conn.execute(
            "SELECT * FROM cutover_events WHERE plan_id = ?",
            ("plan-abc",),
        ).fetchall()
        assert len(rows) == 1
        stored = json.loads(dict(rows[0])["details"])
        assert stored["reason"] == "manual trigger"
        assert stored["operator"] == "admin"

    def test_record_event_default_details_empty(self, controller):
        controller.record_event("plan-def", "simple.event")
        rows = controller._conn.execute(
            "SELECT * FROM cutover_events WHERE plan_id = ?",
            ("plan-def",),
        ).fetchall()
        details = json.loads(dict(rows[0])["details"])
        assert details == {}

    def test_record_event_auto_sets_timestamp(self, controller):
        before = time.time()
        controller.record_event("plan-ts", "ts.event")
        after = time.time()
        rows = controller._conn.execute(
            "SELECT * FROM cutover_events WHERE plan_id = ?",
            ("plan-ts",),
        ).fetchall()
        assert before <= dict(rows[0])["timestamp"] <= after


# ===========================================================================
# 7. Event emission
# ===========================================================================

class TestEventEmission:

    def test_create_plan_emits_event(self, controller_with_bus):
        ctrl, bus = controller_with_bus
        events = []
        bus.subscribe("rebuild.cutover.plan_created", lambda e: events.append(e))

        ctrl.create_plan("mod-emit", current_state="shadow", target_state="cutover")
        assert len(events) == 1
        assert events[0].payload["module_id"] == "mod-emit"
        assert events[0].payload["current_state"] == "shadow"
        assert events[0].payload["target_state"] == "cutover"

    def test_execute_emits_event(self, controller_with_bus):
        ctrl, bus = controller_with_bus
        events = []
        bus.subscribe("rebuild.cutover.executed", lambda e: events.append(e))

        result = ctrl.create_plan("mod-exec-emit")
        ctrl.execute(result["plan_id"])
        assert len(events) == 1
        assert events[0].payload["module_id"] == "mod-exec-emit"

    def test_rollback_emits_event(self, controller_with_bus):
        ctrl, bus = controller_with_bus
        events = []
        bus.subscribe("rebuild.cutover.rolled_back", lambda e: events.append(e))

        result = ctrl.create_plan("mod-rb-emit")
        ctrl.rollback(result["plan_id"])
        assert len(events) == 1
        assert events[0].payload["module_id"] == "mod-rb-emit"

    def test_no_event_bus_does_not_raise(self):
        ctrl = CutoverController(event_bus=None)
        result = ctrl.create_plan("mod-no-bus")
        ctrl.execute(result["plan_id"])
        ctrl.rollback(ctrl.create_plan("mod-no-bus-2")["plan_id"])


# ===========================================================================
# 8. Thread safety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_plan_creation(self):
        ctrl = CutoverController()
        results = []
        results_lock = threading.Lock()

        def create_plan(idx):
            r = ctrl.create_plan(f"mod-concurrent-{idx}")
            with results_lock:
                results.append(r)

        threads = [threading.Thread(target=create_plan, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(results) == 20
        plan_ids = [r["plan_id"] for r in results]
        assert len(set(plan_ids)) == 20

        plans = ctrl.list_plans()
        assert len(plans) == 20
