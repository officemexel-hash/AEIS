"""Tests for sylion.core.pipeline_controller.

Covers: PipelineRun dataclass, PipelineController (submit, execute, get, list,
cancel), subsystem wiring (planner, code_agent, decision_gate), event emission,
singleton lifecycle, and thread safety.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from unittest.mock import MagicMock

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.pipeline_controller import (
    PipelineController,
    PipelineRun,
    get_pipeline_controller,
    reset_pipeline_controller,
)


# ---------------------------------------------------------------------------
# Mock subsystems
# ---------------------------------------------------------------------------

class MockPlanner:
    """Returns a fixed two-step plan based on the idea text."""

    def decompose_idea(self, idea: str) -> dict:
        return {
            "plan_id": "mock-plan",
            "title": idea[:80],
            "steps": [
                {"step_id": "s1", "name": "analyze", "description": f"Analyze: {idea}"},
                {"step_id": "s2", "name": "generate", "description": f"Generate code for: {idea}"},
            ]
        }


class MockCodeAgent:
    """Returns a canned generation result echoing the prompt."""

    def generate(self, prompt: str) -> dict:
        return {"op_id": "mock-op", "result": f"// generated for: {prompt[:50]}"}


class MockDecisionGate:
    """Approves every step by default."""

    def evaluate_gate(self, gate_id: str, context: dict | None = None) -> dict:
        return {"gate_id": gate_id, "result": "pass", "message": "approved"}


class RejectingDecisionGate:
    """Rejects every step."""

    def evaluate_gate(self, gate_id: str, context: dict | None = None) -> dict:
        return {"gate_id": gate_id, "result": "fail", "message": "policy violation"}


class FailingPlanner:
    """Raises on decompose_idea to test error handling."""

    def decompose_idea(self, idea: str) -> dict:
        raise RuntimeError("planner crashed")


class FailingCodeAgent:
    """Raises on generate to test per-step error handling."""

    def generate(self, prompt: str) -> dict:
        raise RuntimeError("code agent crashed")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure the global singleton is reset before and after each test."""
    reset_pipeline_controller()
    yield
    reset_pipeline_controller()


@pytest.fixture
def bus() -> EventBus:
    """Fresh in-memory EventBus per test."""
    return EventBus()


@pytest.fixture
def ctrl() -> PipelineController:
    """Fresh PipelineController with no subsystems."""
    return PipelineController()


@pytest.fixture
def ctrl_with_bus(bus: EventBus) -> PipelineController:
    """PipelineController wired to a real EventBus."""
    return PipelineController(event_bus=bus)


@pytest.fixture
def ctrl_full(bus: EventBus) -> PipelineController:
    """PipelineController with all subsystems and EventBus."""
    return PipelineController(
        planner=MockPlanner(),
        code_agent=MockCodeAgent(),
        decision_gate=MockDecisionGate(),
        event_bus=bus,
    )


# ---------------------------------------------------------------------------
# TestPipelineRun — dataclass defaults
# ---------------------------------------------------------------------------

class TestPipelineRun:

    def test_auto_run_id(self):
        run = PipelineRun()
        assert run.run_id != ""
        assert len(run.run_id) == 32  # uuid4 hex

    def test_auto_run_id_unique(self):
        a = PipelineRun()
        b = PipelineRun()
        assert a.run_id != b.run_id

    def test_explicit_run_id_preserved(self):
        run = PipelineRun(run_id="custom-id-123")
        assert run.run_id == "custom-id-123"

    def test_auto_created_at(self):
        before = time.time()
        run = PipelineRun()
        after = time.time()
        assert before <= run.created_at <= after

    def test_explicit_created_at_preserved(self):
        run = PipelineRun(created_at=99999.0)
        assert run.created_at == 99999.0

    def test_default_status_pending(self):
        run = PipelineRun()
        assert run.status == "pending"

    def test_explicit_status(self):
        run = PipelineRun(status="complete")
        assert run.status == "complete"

    def test_default_plan_empty_dict(self):
        run = PipelineRun()
        assert run.plan == {}

    def test_default_steps_empty_list(self):
        run = PipelineRun()
        assert run.steps == []

    def test_default_completed_at_zero(self):
        run = PipelineRun()
        assert run.completed_at == 0.0

    def test_idea_field(self):
        run = PipelineRun(idea="Build a REST API")
        assert run.idea == "Build a REST API"


# ---------------------------------------------------------------------------
# TestSubmitIdea
# ---------------------------------------------------------------------------

class TestSubmitIdea:

    def test_returns_run_id_and_pending(self, ctrl: PipelineController):
        result = ctrl.submit_idea("My idea")
        assert "run_id" in result
        assert result["status"] == "pending"
        assert len(result["run_id"]) == 32

    def test_persists_to_db(self, ctrl: PipelineController):
        result = ctrl.submit_idea("Persisted idea")
        run = ctrl.get_run(result["run_id"])
        assert run is not None
        assert run["idea"] == "Persisted idea"
        assert run["status"] == "pending"

    def test_emits_idea_submitted_event(self, bus: EventBus):
        ctrl = PipelineController(event_bus=bus)
        result = ctrl.submit_idea("Event test idea")
        events = bus.query(topic="pipeline.idea_submitted")
        assert len(events) >= 1
        evt = events[0]
        payload = json.loads(evt["payload"])
        assert payload["run_id"] == result["run_id"]
        assert payload["idea"] == "Event test idea"

    def test_no_event_without_bus(self, ctrl: PipelineController):
        # Should not raise — event_bus is None
        result = ctrl.submit_idea("No bus idea")
        assert result["status"] == "pending"

    def test_context_stored(self, ctrl: PipelineController):
        ctx = {"user": "alice", "priority": "high"}
        result = ctrl.submit_idea("Context idea", context=ctx)
        run = ctrl.get_run(result["run_id"])
        assert run["context"]["user"] == "alice"
        assert run["context"]["priority"] == "high"

    def test_multiple_submits_unique_ids(self, ctrl: PipelineController):
        ids = set()
        for i in range(10):
            r = ctrl.submit_idea(f"Idea {i}")
            ids.add(r["run_id"])
        assert len(ids) == 10

    def test_created_at_set_on_submit(self, ctrl: PipelineController):
        before = time.time()
        result = ctrl.submit_idea("Timestamp idea")
        after = time.time()
        run = ctrl.get_run(result["run_id"])
        assert before <= run["created_at"] <= after


# ---------------------------------------------------------------------------
# TestExecuteRun
# ---------------------------------------------------------------------------

class TestExecuteRun:

    # --- No subsystems ---

    def test_no_subsystems_single_step_complete(self, ctrl: PipelineController):
        """Without a planner, execute_run treats the idea as a single step."""
        sub = ctrl.submit_idea("Simple idea")
        result = ctrl.execute_run(sub["run_id"])
        assert result["status"] == "complete"
        assert len(result["steps"]) == 1
        assert result["steps"][0]["step_id"] == "s1"
        assert result["steps"][0]["name"] == "idea"
        assert result["steps"][0]["description"] == "Simple idea"

    def test_no_subsystems_step_result_skipped(self, ctrl: PipelineController):
        sub = ctrl.submit_idea("No agent idea")
        result = ctrl.execute_run(sub["run_id"])
        step = result["steps"][0]
        assert step["result"]["output"] == "skipped (no code_agent)"

    def test_no_subsystems_completed_at_set(self, ctrl: PipelineController):
        sub = ctrl.submit_idea("Timing idea")
        before = time.time()
        result = ctrl.execute_run(sub["run_id"])
        after = time.time()
        assert before <= result["completed_at"] <= after

    def test_nonexistent_run(self, ctrl: PipelineController):
        result = ctrl.execute_run("does-not-exist")
        assert "error" in result
        assert "not found" in result["error"]

    # --- With mock planner ---

    def test_with_planner_generates_steps(self, bus: EventBus):
        ctrl = PipelineController(planner=MockPlanner(), event_bus=bus)
        sub = ctrl.submit_idea("Plan me")
        result = ctrl.execute_run(sub["run_id"])
        assert result["status"] == "complete"
        assert len(result["steps"]) == 2
        assert result["steps"][0]["name"] == "analyze"
        assert result["steps"][1]["name"] == "generate"

    def test_planner_sets_plan_field(self):
        ctrl = PipelineController(planner=MockPlanner())
        sub = ctrl.submit_idea("Plan field")
        result = ctrl.execute_run(sub["run_id"])
        assert "steps" in result["plan"]
        assert len(result["plan"]["steps"]) == 2

    def test_planner_fails_sets_status_failed(self):
        ctrl = PipelineController(planner=FailingPlanner())
        sub = ctrl.submit_idea("Crash plan")
        result = ctrl.execute_run(sub["run_id"])
        assert result["status"] == "failed"

    def test_planner_fails_emits_failed_event(self, bus: EventBus):
        ctrl = PipelineController(planner=FailingPlanner(), event_bus=bus)
        sub = ctrl.submit_idea("Crash plan event")
        ctrl.execute_run(sub["run_id"])
        events = bus.query(topic="pipeline.run_failed")
        payloads = [json.loads(e["payload"]) for e in events]
        assert any(p.get("phase") == "planning" for p in payloads)

    # --- With mock code_agent ---

    def test_with_code_agent_generates_result(self):
        ctrl = PipelineController(code_agent=MockCodeAgent())
        sub = ctrl.submit_idea("Code gen")
        result = ctrl.execute_run(sub["run_id"])
        assert result["status"] == "complete"
        step = result["steps"][0]
        assert step["result"]["op_id"] == "mock-op"
        assert "generated for" in step["result"]["result"]

    def test_code_agent_failure_per_step(self):
        ctrl = PipelineController(code_agent=FailingCodeAgent())
        sub = ctrl.submit_idea("Crash gen")
        result = ctrl.execute_run(sub["run_id"])
        assert result["status"] == "failed"
        assert result["steps"][0]["status"] == "failed"

    # --- With mock decision_gate ---

    def test_gate_approves_step(self):
        ctrl = PipelineController(decision_gate=MockDecisionGate())
        sub = ctrl.submit_idea("Gate approve")
        result = ctrl.execute_run(sub["run_id"])
        assert result["status"] == "complete"
        step = result["steps"][0]
        assert step["status"] == "complete"
        assert step["result"]["gate"]["result"] == "pass"

    def test_rejecting_gate_fails_step(self):
        ctrl = PipelineController(decision_gate=RejectingDecisionGate())
        sub = ctrl.submit_idea("Gate reject")
        result = ctrl.execute_run(sub["run_id"])
        assert result["status"] == "failed"
        step = result["steps"][0]
        assert step["status"] == "failed"
        assert step["result"]["gate"]["result"] == "fail"

    def test_rejecting_gate_marks_run_failed(self):
        ctrl = PipelineController(decision_gate=RejectingDecisionGate())
        sub = ctrl.submit_idea("Reject full")
        result = ctrl.execute_run(sub["run_id"])
        assert result["status"] == "failed"

    # --- All subsystems wired together ---

    def test_full_pipeline_complete(self, ctrl_full: PipelineController):
        sub = ctrl_full.submit_idea("Full pipeline run")
        result = ctrl_full.execute_run(sub["run_id"])
        assert result["status"] == "complete"
        assert len(result["steps"]) == 2
        for step in result["steps"]:
            assert step["status"] == "complete"
            assert "gate" in step["result"]
            assert step["result"]["gate"]["result"] == "pass"

    def test_full_pipeline_events_emitted(self, ctrl_full: PipelineController, bus: EventBus):
        sub = ctrl_full.submit_idea("Full event check")
        ctrl_full.execute_run(sub["run_id"])
        events = bus.query()
        topics = {e["topic"] for e in events}
        assert "pipeline.idea_submitted" in topics
        assert "pipeline.run_planning" in topics
        assert "pipeline.run_generating" in topics
        assert "pipeline.run_completed" in topics

    def test_full_pipeline_with_rejecting_gate(self, bus: EventBus):
        ctrl = PipelineController(
            planner=MockPlanner(),
            code_agent=MockCodeAgent(),
            decision_gate=RejectingDecisionGate(),
            event_bus=bus,
        )
        sub = ctrl.submit_idea("Reject pipeline")
        result = ctrl.execute_run(sub["run_id"])
        assert result["status"] == "failed"
        events = bus.query(topic="pipeline.run_failed")
        assert len(events) >= 1

    def test_step_records_all_fields(self, ctrl_full: PipelineController):
        sub = ctrl_full.submit_idea("Field check")
        result = ctrl_full.execute_run(sub["run_id"])
        for step in result["steps"]:
            assert "step_id" in step
            assert "name" in step
            assert "description" in step
            assert "status" in step
            assert "result" in step

    def test_completed_at_set_on_success(self, ctrl_full: PipelineController):
        sub = ctrl_full.submit_idea("Timestamp check")
        before = time.time()
        ctrl_full.execute_run(sub["run_id"])
        after = time.time()
        run = ctrl_full.get_run(sub["run_id"])
        assert before <= run["completed_at"] <= after


# ---------------------------------------------------------------------------
# TestGetRun
# ---------------------------------------------------------------------------

class TestGetRun:

    def test_get_existing_run(self, ctrl: PipelineController):
        sub = ctrl.submit_idea("Gettable idea")
        run = ctrl.get_run(sub["run_id"])
        assert run is not None
        assert run["run_id"] == sub["run_id"]
        assert run["idea"] == "Gettable idea"

    def test_get_nonexistent_returns_none(self, ctrl: PipelineController):
        run = ctrl.get_run("nonexistent-id")
        assert run is None

    def test_get_after_execute_has_steps(self, ctrl: PipelineController):
        sub = ctrl.submit_idea("Steps check")
        ctrl.execute_run(sub["run_id"])
        run = ctrl.get_run(sub["run_id"])
        assert len(run["steps"]) >= 1

    def test_get_returns_all_fields(self, ctrl: PipelineController):
        sub = ctrl.submit_idea("Fields check", context={"k": "v"})
        run = ctrl.get_run(sub["run_id"])
        expected_keys = {"run_id", "idea", "status", "plan", "steps", "context",
                         "created_at", "completed_at"}
        assert expected_keys.issubset(set(run.keys()))

    def test_get_reflects_status_change(self, ctrl: PipelineController):
        sub = ctrl.submit_idea("Status change")
        ctrl.execute_run(sub["run_id"])
        run = ctrl.get_run(sub["run_id"])
        assert run["status"] in ("complete", "failed")


# ---------------------------------------------------------------------------
# TestListRuns
# ---------------------------------------------------------------------------

class TestListRuns:

    def test_list_all_runs(self, ctrl: PipelineController):
        ctrl.submit_idea("Idea A")
        ctrl.submit_idea("Idea B")
        ctrl.submit_idea("Idea C")
        runs = ctrl.list_runs()
        assert len(runs) == 3

    def test_list_empty(self, ctrl: PipelineController):
        runs = ctrl.list_runs()
        assert runs == []

    def test_filter_by_status_pending(self, ctrl: PipelineController):
        ctrl.submit_idea("P1")
        ctrl.submit_idea("P2")
        runs = ctrl.list_runs(status="pending")
        assert len(runs) == 2
        assert all(r["status"] == "pending" for r in runs)

    def test_filter_by_status_complete(self, ctrl: PipelineController):
        sub = ctrl.submit_idea("C1")
        ctrl.execute_run(sub["run_id"])
        runs = ctrl.list_runs(status="complete")
        assert len(runs) == 1
        assert runs[0]["status"] == "complete"

    def test_filter_by_status_no_match(self, ctrl: PipelineController):
        ctrl.submit_idea("Only pending")
        runs = ctrl.list_runs(status="complete")
        assert runs == []

    def test_limit(self, ctrl: PipelineController):
        for i in range(10):
            ctrl.submit_idea(f"Limited {i}")
        runs = ctrl.list_runs(limit=3)
        assert len(runs) == 3

    def test_ordered_by_created_at_desc(self, ctrl: PipelineController):
        ids = []
        for i in range(5):
            r = ctrl.submit_idea(f"Order {i}")
            ids.append(r["run_id"])
            time.sleep(0.01)  # ensure distinct timestamps
        runs = ctrl.list_runs()
        returned_ids = [r["run_id"] for r in runs]
        assert returned_ids == list(reversed(ids))


# ---------------------------------------------------------------------------
# TestCancelRun
# ---------------------------------------------------------------------------

class TestCancelRun:

    def test_cancel_pending(self, ctrl: PipelineController):
        sub = ctrl.submit_idea("Cancellable idea")
        result = ctrl.cancel_run(sub["run_id"])
        assert result["status"] == "cancelled"
        assert result["run_id"] == sub["run_id"]

    def test_cancel_sets_db_status(self, ctrl: PipelineController):
        sub = ctrl.submit_idea("Cancel DB check")
        ctrl.cancel_run(sub["run_id"])
        run = ctrl.get_run(sub["run_id"])
        assert run["status"] == "cancelled"

    def test_cancel_complete_refuses(self, ctrl: PipelineController):
        sub = ctrl.submit_idea("Already done")
        ctrl.execute_run(sub["run_id"])
        result = ctrl.cancel_run(sub["run_id"])
        assert "already finished" in result["message"]
        assert result["status"] == "complete"

    def test_cancel_failed_refuses(self):
        ctrl = PipelineController(planner=FailingPlanner())
        sub = ctrl.submit_idea("Will fail")
        ctrl.execute_run(sub["run_id"])
        result = ctrl.cancel_run(sub["run_id"])
        assert "already finished" in result["message"]
        assert result["status"] == "failed"

    def test_cancel_nonexistent(self, ctrl: PipelineController):
        result = ctrl.cancel_run("nonexistent-id")
        assert "error" in result
        assert "not found" in result["error"]

    def test_cancel_emits_event(self, bus: EventBus):
        ctrl = PipelineController(event_bus=bus)
        sub = ctrl.submit_idea("Cancel event")
        ctrl.cancel_run(sub["run_id"])
        events = bus.query(topic="pipeline.run_cancelled")
        assert len(events) >= 1
        payload = json.loads(events[0]["payload"])
        assert payload["run_id"] == sub["run_id"]

    def test_cancel_sets_completed_at(self, ctrl: PipelineController):
        sub = ctrl.submit_idea("Cancel timestamp")
        before = time.time()
        ctrl.cancel_run(sub["run_id"])
        after = time.time()
        run = ctrl.get_run(sub["run_id"])
        assert before <= run["completed_at"] <= after

    def test_cancel_listable_by_status(self, ctrl: PipelineController):
        sub = ctrl.submit_idea("Cancel list")
        ctrl.cancel_run(sub["run_id"])
        runs = ctrl.list_runs(status="cancelled")
        assert len(runs) == 1
        assert runs[0]["run_id"] == sub["run_id"]


# ---------------------------------------------------------------------------
# TestSingleton
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_returns_instance(self):
        ctrl = get_pipeline_controller()
        assert isinstance(ctrl, PipelineController)

    def test_get_idempotent(self):
        a = get_pipeline_controller()
        b = get_pipeline_controller()
        assert a is b

    def test_reset_clears_singleton(self):
        a = get_pipeline_controller()
        reset_pipeline_controller()
        b = get_pipeline_controller()
        assert a is not b

    def test_get_with_subsystems(self):
        ctrl = get_pipeline_controller(
            planner=MockPlanner(),
            code_agent=MockCodeAgent(),
            event_bus=EventBus(),
        )
        assert ctrl._planner is not None
        assert ctrl._code_agent is not None

    def test_second_get_ignores_new_subsystems(self):
        """Once created, subsequent calls with different args return same instance."""
        a = get_pipeline_controller(planner=MockPlanner())
        b = get_pipeline_controller()  # no planner
        assert a is b
        assert b._planner is not None  # planner from first call


# ---------------------------------------------------------------------------
# TestThreadSafety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def _retry_exec(self, ctrl: PipelineController, run_id: str,
                    max_retries: int = 5) -> dict:
        """Retry execute_run on sqlite concurrency errors."""
        for attempt in range(max_retries):
            try:
                return ctrl.execute_run(run_id)
            except (sqlite3.OperationalError, sqlite3.InterfaceError):
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.05 * (attempt + 1))
        return {}

    def test_concurrent_submit_ideas(self):
        ctrl = PipelineController()
        results = []
        errors = []

        def submit(i: int):
            try:
                r = ctrl.submit_idea(f"Concurrent idea {i}")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=submit, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"errors during concurrent submit: {errors}"
        assert len(results) == 20
        run_ids = {r["run_id"] for r in results}
        assert len(run_ids) == 20  # all unique

    def test_concurrent_submit_and_list(self):
        ctrl = PipelineController()
        list_results = []
        errors = []

        def submit_batch():
            for i in range(10):
                try:
                    ctrl.submit_idea(f"SL idea {i}")
                except (sqlite3.OperationalError, sqlite3.InterfaceError):
                    pass

        def list_batch():
            for _ in range(10):
                try:
                    runs = ctrl.list_runs()
                    list_results.append(len(runs))
                except (sqlite3.OperationalError, sqlite3.InterfaceError):
                    pass

        t1 = threading.Thread(target=submit_batch)
        t2 = threading.Thread(target=list_batch)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # At least some list calls should have succeeded
        assert len(list_results) > 0
        # Final count should be exactly 10
        final = ctrl.list_runs()
        assert len(final) == 10

    def test_concurrent_execute_runs(self):
        bus = EventBus()
        ctrl = PipelineController(
            planner=MockPlanner(),
            code_agent=MockCodeAgent(),
            decision_gate=MockDecisionGate(),
            event_bus=bus,
        )
        # Submit 5 ideas
        subs = [ctrl.submit_idea(f"Exec {i}") for i in range(5)]
        results = []
        errors = []

        def execute(run_id: str):
            try:
                r = self._retry_exec(ctrl, run_id)
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=execute, args=(s["run_id"],)) for s in subs]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"errors during concurrent execute: {errors}"
        assert len(results) == 5
        for r in results:
            assert r["status"] == "complete"

    def test_concurrent_get_run(self):
        ctrl = PipelineController()
        sub = ctrl.submit_idea("Concurrent get")
        results = []
        errors = []

        def getter():
            try:
                r = ctrl.get_run(sub["run_id"])
                results.append(r)
            except (sqlite3.OperationalError, sqlite3.InterfaceError) as e:
                errors.append(e)

        threads = [threading.Thread(target=getter) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        # All results should be identical
        for r in results:
            assert r["run_id"] == sub["run_id"]
            assert r["idea"] == "Concurrent get"
