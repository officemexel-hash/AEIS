"""Tests for sylion.security.bootstrap_flow -- BootstrapFlow.

Covers: create_flow, update_flow, delete_flow, get_flow, list_flows,
add_step, remove_step, execute_flow, get_execution, list_executions,
get_flow_stats, event emission, error handling, thread safety,
singleton lifecycle.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus
from sylion.security.bootstrap_flow import (
    BootstrapFlow,
    get_bootstrap_flow,
    reset_bootstrap_flow,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset():
    reset_bootstrap_flow()
    yield
    reset_bootstrap_flow()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def bf(bus):
    return BootstrapFlow(event_bus=bus)


@pytest.fixture
def bf_no_bus():
    return BootstrapFlow(event_bus=None)


# ===========================================================================
# TestCreateFlow
# ===========================================================================

class TestCreateFlow:

    def test_create_returns_descriptor(self, bf):
        result = bf.create_flow("startup", "System startup sequence")
        assert result["flow_id"]
        assert result["name"] == "startup"
        assert result["description"] == "System startup sequence"
        assert result["status"] == "active"

    def test_create_with_steps(self, bf):
        steps = [
            {"step_name": "check_db", "step_type": "validate",
             "config_json": {"db": "main"}},
            {"step_name": "load_config", "step_type": "action"},
        ]
        result = bf.create_flow("with_steps", steps_list=steps)
        flow = bf.get_flow(result["flow_id"])
        assert len(flow["steps"]) == 2

    def test_create_empty_steps(self, bf):
        result = bf.create_flow("empty")
        flow = bf.get_flow(result["flow_id"])
        assert flow["steps"] == []

    def test_create_multiple(self, bf):
        bf.create_flow("flow_a")
        bf.create_flow("flow_b")
        bf.create_flow("flow_c")
        assert len(bf.list_flows()) == 3

    def test_create_emits_event(self, bf, bus):
        events = []
        bus.subscribe("flow_created", events.append)
        bf.create_flow("evt_flow")
        assert len(events) == 1
        assert events[0].payload["name"] == "evt_flow"

    def test_create_unique_ids(self, bf):
        r1 = bf.create_flow("a")
        r2 = bf.create_flow("b")
        assert r1["flow_id"] != r2["flow_id"]


# ===========================================================================
# TestUpdateFlow
# ===========================================================================

class TestUpdateFlow:

    def test_update_name(self, bf):
        r = bf.create_flow("old_name")
        updated = bf.update_flow(r["flow_id"], name="new_name")
        assert updated["name"] == "new_name"

    def test_update_description(self, bf):
        r = bf.create_flow("desc")
        updated = bf.update_flow(r["flow_id"],
                                 description="updated desc")
        assert updated["description"] == "updated desc"

    def test_update_status(self, bf):
        r = bf.create_flow("stat")
        updated = bf.update_flow(r["flow_id"], status="archived")
        assert updated["status"] == "archived"

    def test_update_nonexistent(self, bf):
        assert bf.update_flow("ghost", name="nope") is None

    def test_update_no_allowed_fields(self, bf):
        r = bf.create_flow("bad")
        assert bf.update_flow(r["flow_id"], bad="x") is None


# ===========================================================================
# TestDeleteFlow
# ===========================================================================

class TestDeleteFlow:

    def test_delete_existing(self, bf):
        r = bf.create_flow("del")
        assert bf.delete_flow(r["flow_id"]) is True
        assert bf.get_flow(r["flow_id"]) is None

    def test_delete_nonexistent(self, bf):
        assert bf.delete_flow("ghost") is False

    def test_delete_removes_steps(self, bf):
        r = bf.create_flow("del_steps",
                           steps_list=[{"step_name": "s1"}])
        fid = r["flow_id"]
        bf.delete_flow(fid)
        # Verify steps are gone by re-creating with same checks
        assert bf.get_flow(fid) is None

    def test_delete_removes_executions(self, bf):
        r = bf.create_flow("del_exec",
                           steps_list=[{"step_name": "s1"}])
        fid = r["flow_id"]
        bf.execute_flow(fid)
        bf.delete_flow(fid)
        assert bf.list_executions(flow_id=fid) == []

    def test_delete_twice(self, bf):
        r = bf.create_flow("twice")
        fid = r["flow_id"]
        assert bf.delete_flow(fid) is True
        assert bf.delete_flow(fid) is False


# ===========================================================================
# TestGetFlow
# ===========================================================================

class TestGetFlow:

    def test_get_existing(self, bf):
        r = bf.create_flow("get_test",
                           steps_list=[{"step_name": "s1"},
                                       {"step_name": "s2"}])
        flow = bf.get_flow(r["flow_id"])
        assert flow is not None
        assert flow["name"] == "get_test"
        assert len(flow["steps"]) == 2

    def test_get_nonexistent(self, bf):
        assert bf.get_flow("ghost") is None

    def test_get_parses_step_config(self, bf):
        r = bf.create_flow("parsed",
                           steps_list=[{"step_name": "s1",
                                        "config_json": {"key": "val"}}])
        flow = bf.get_flow(r["flow_id"])
        assert isinstance(flow["steps"][0]["config_json"], dict)
        assert flow["steps"][0]["config_json"]["key"] == "val"


# ===========================================================================
# TestListFlows
# ===========================================================================

class TestListFlows:

    def test_list_empty(self, bf):
        assert bf.list_flows() == []

    def test_list_all(self, bf):
        bf.create_flow("flow_a")
        bf.create_flow("flow_b")
        assert len(bf.list_flows()) == 2

    def test_list_filter_by_status(self, bf):
        bf.create_flow("active_flow")
        r = bf.create_flow("archived_flow")
        bf.update_flow(r["flow_id"], status="archived")
        result = bf.list_flows(status="active")
        assert len(result) == 1
        assert result[0]["name"] == "active_flow"

    def test_list_no_filter(self, bf):
        bf.create_flow("a")
        bf.create_flow("b")
        bf.create_flow("c")
        assert len(bf.list_flows()) == 3


# ===========================================================================
# TestStepManagement
# ===========================================================================

class TestStepManagement:

    def test_add_step(self, bf):
        r = bf.create_flow("step_test")
        step = bf.add_step(r["flow_id"], "check_db", "validate",
                           {"db": "main"})
        assert step["step_id"]
        assert step["step_name"] == "check_db"
        assert step["step_type"] == "validate"

    def test_add_step_appends(self, bf):
        r = bf.create_flow("append")
        fid = r["flow_id"]
        bf.add_step(fid, "step_1")
        bf.add_step(fid, "step_2")
        bf.add_step(fid, "step_3")
        flow = bf.get_flow(fid)
        assert len(flow["steps"]) == 3
        orders = [s["step_order"] for s in flow["steps"]]
        assert orders == sorted(orders)

    def test_add_step_with_config(self, bf):
        r = bf.create_flow("cfg_step")
        step = bf.add_step(r["flow_id"], "s1", "action",
                           {"timeout": 30})
        flow = bf.get_flow(r["flow_id"])
        assert flow["steps"][0]["config_json"]["timeout"] == 30

    def test_remove_step(self, bf):
        r = bf.create_flow("rm_step")
        step = bf.add_step(r["flow_id"], "to_remove")
        assert bf.remove_step(step["step_id"]) is True
        flow = bf.get_flow(r["flow_id"])
        assert len(flow["steps"]) == 0

    def test_remove_nonexistent_step(self, bf):
        assert bf.remove_step("ghost") is False

    def test_remove_step_twice(self, bf):
        r = bf.create_flow("dbl_rm")
        step = bf.add_step(r["flow_id"], "s1")
        assert bf.remove_step(step["step_id"]) is True
        assert bf.remove_step(step["step_id"]) is False


# ===========================================================================
# TestExecuteFlow
# ===========================================================================

class TestExecuteFlow:

    def test_execute_basic(self, bf):
        r = bf.create_flow("exec_basic",
                           steps_list=[
                               {"step_name": "step_1", "step_type": "action"},
                               {"step_name": "step_2", "step_type": "validate"},
                           ])
        result = bf.execute_flow(r["flow_id"])
        assert result["status"] == "completed"
        assert len(result["step_results"]) == 2

    def test_execute_step_results(self, bf):
        r = bf.create_flow("results",
                           steps_list=[
                               {"step_name": "validate_step",
                                "step_type": "validate"},
                               {"step_name": "transform_step",
                                "step_type": "transform"},
                               {"step_name": "action_step",
                                "step_type": "action"},
                           ])
        result = bf.execute_flow(r["flow_id"])
        results = result["step_results"]
        assert results[0]["result"] == "validated"
        assert results[1]["result"] == "transformed"
        assert results[2]["result"] == "executed"

    def test_execute_empty_flow(self, bf):
        r = bf.create_flow("empty_exec")
        result = bf.execute_flow(r["flow_id"])
        assert result["status"] == "completed"
        assert result["step_results"] == []

    def test_execute_with_context(self, bf):
        r = bf.create_flow("ctx",
                           steps_list=[{"step_name": "s1"}])
        result = bf.execute_flow(r["flow_id"],
                                 context_json={"env": "prod"})
        exec_record = bf.get_execution(result["execution_id"])
        assert exec_record["context_json"]["env"] == "prod"

    def test_execute_nonexistent_flow(self, bf):
        result = bf.execute_flow("ghost")
        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_execute_emits_flow_started(self, bf, bus):
        events = []
        bus.subscribe("flow_started", events.append)
        r = bf.create_flow("started_evt",
                           steps_list=[{"step_name": "s1"}])
        bf.execute_flow(r["flow_id"])
        assert len(events) == 1
        assert events[0].payload["flow_id"] == r["flow_id"]

    def test_execute_emits_step_completed(self, bf, bus):
        events = []
        bus.subscribe("step_completed", events.append)
        r = bf.create_flow("step_evt",
                           steps_list=[
                               {"step_name": "s1"},
                               {"step_name": "s2"},
                           ])
        bf.execute_flow(r["flow_id"])
        assert len(events) == 2

    def test_execute_emits_flow_completed(self, bf, bus):
        events = []
        bus.subscribe("flow_completed", events.append)
        r = bf.create_flow("comp_evt",
                           steps_list=[{"step_name": "s1"}])
        bf.execute_flow(r["flow_id"])
        assert len(events) == 1
        assert events[0].payload["status"] == "completed"

    def test_execute_records_timing(self, bf):
        r = bf.create_flow("timing",
                           steps_list=[{"step_name": "s1"}])
        result = bf.execute_flow(r["flow_id"])
        exec_record = bf.get_execution(result["execution_id"])
        assert exec_record["started_at"] is not None
        assert exec_record["completed_at"] is not None
        assert exec_record["completed_at"] >= exec_record["started_at"]


# ===========================================================================
# TestGetExecution
# ===========================================================================

class TestGetExecution:

    def test_get_existing(self, bf):
        r = bf.create_flow("get_exec",
                           steps_list=[{"step_name": "s1"}])
        exec_result = bf.execute_flow(r["flow_id"])
        record = bf.get_execution(exec_result["execution_id"])
        assert record is not None
        assert record["status"] == "completed"

    def test_get_nonexistent(self, bf):
        assert bf.get_execution("ghost") is None

    def test_get_parses_step_results(self, bf):
        r = bf.create_flow("parsed_exec",
                           steps_list=[{"step_name": "s1"}])
        exec_result = bf.execute_flow(r["flow_id"])
        record = bf.get_execution(exec_result["execution_id"])
        assert isinstance(record["step_results"], list)

    def test_get_parses_context(self, bf):
        r = bf.create_flow("ctx_exec",
                           steps_list=[{"step_name": "s1"}])
        exec_result = bf.execute_flow(r["flow_id"],
                                      context_json={"x": 1})
        record = bf.get_execution(exec_result["execution_id"])
        assert isinstance(record["context_json"], dict)
        assert record["context_json"]["x"] == 1


# ===========================================================================
# TestListExecutions
# ===========================================================================

class TestListExecutions:

    def test_list_empty(self, bf):
        assert bf.list_executions() == []

    def test_list_all(self, bf):
        r = bf.create_flow("list_exec",
                           steps_list=[{"step_name": "s1"}])
        bf.execute_flow(r["flow_id"])
        bf.execute_flow(r["flow_id"])
        assert len(bf.list_executions()) == 2

    def test_list_filter_by_flow(self, bf):
        r1 = bf.create_flow("f1", steps_list=[{"step_name": "s1"}])
        r2 = bf.create_flow("f2", steps_list=[{"step_name": "s1"}])
        bf.execute_flow(r1["flow_id"])
        bf.execute_flow(r2["flow_id"])
        assert len(bf.list_executions(flow_id=r1["flow_id"])) == 1

    def test_list_filter_by_status(self, bf):
        r = bf.create_flow("status_exec",
                           steps_list=[{"step_name": "s1"}])
        bf.execute_flow(r["flow_id"])
        result = bf.list_executions(status="completed")
        assert len(result) == 1

    def test_list_parses_fields(self, bf):
        r = bf.create_flow("parse_exec",
                           steps_list=[{"step_name": "s1"}])
        bf.execute_flow(r["flow_id"])
        entries = bf.list_executions()
        assert isinstance(entries[0]["step_results"], list)
        assert isinstance(entries[0]["context_json"], dict)


# ===========================================================================
# TestGetFlowStats
# ===========================================================================

class TestGetFlowStats:

    def test_empty_stats(self, bf):
        stats = bf.get_flow_stats()
        assert stats["total_flows"] == 0
        assert stats["total_steps"] == 0
        assert stats["total_executions"] == 0
        assert stats["by_status"] == {}

    def test_stats_with_flows(self, bf):
        bf.create_flow("s1", steps_list=[{"step_name": "a"},
                                          {"step_name": "b"}])
        bf.create_flow("s2", steps_list=[{"step_name": "c"}])
        stats = bf.get_flow_stats()
        assert stats["total_flows"] == 2
        assert stats["total_steps"] == 3

    def test_stats_with_executions(self, bf):
        r = bf.create_flow("exec_stats",
                           steps_list=[{"step_name": "s1"}])
        bf.execute_flow(r["flow_id"])
        bf.execute_flow(r["flow_id"])
        stats = bf.get_flow_stats()
        assert stats["total_executions"] == 2
        assert stats["by_status"]["completed"] == 2


# ===========================================================================
# TestNoBus
# ===========================================================================

class TestNoBus:

    def test_no_bus_no_crash(self, bf_no_bus):
        r = bf_no_bus.create_flow("nb",
                                  steps_list=[{"step_name": "s1"}])
        bf_no_bus.execute_flow(r["flow_id"])
        bf_no_bus.delete_flow(r["flow_id"])


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        assert isinstance(get_bootstrap_flow(), BootstrapFlow)

    def test_idempotent(self):
        a = get_bootstrap_flow()
        b = get_bootstrap_flow()
        assert a is b

    def test_reset_creates_new(self):
        a = get_bootstrap_flow()
        b = reset_bootstrap_flow()
        assert a is not b


# ===========================================================================
# TestThreadSafety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_flow_creation(self, bf):
        errors = []

        def create(idx):
            try:
                bf.create_flow(f"flow-{idx}",
                               steps_list=[{"step_name": "s1"}])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(bf.list_flows()) == 20

    def test_concurrent_executions(self, bf):
        r = bf.create_flow("conc_exec",
                           steps_list=[{"step_name": "s1"}])
        fid = r["flow_id"]
        errors = []

        def execute(idx):
            try:
                bf.execute_flow(fid, context_json={"i": idx})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=execute, args=(i,))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(bf.list_executions(flow_id=fid)) == 10
