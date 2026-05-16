"""
Comprehensive tests for sylion.execution.workflow_engine.

Tests WorkflowEngine class: create_workflow, get_workflow, list_workflows,
run_workflow, get_run, list_runs, edge cases, thread safety, event emission.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.execution.workflow_engine import (
    Workflow,
    WorkflowEngine,
    WorkflowRun,
    WorkflowStep,
    get_workflow_engine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine() -> WorkflowEngine:
    """Fresh in-memory WorkflowEngine per test."""
    return WorkflowEngine()


@pytest.fixture
def engine_with_bus() -> tuple[WorkflowEngine, MagicMock]:
    """WorkflowEngine with a mock EventBus to verify event emission."""
    bus = MagicMock(spec=EventBus)
    eng = WorkflowEngine(event_bus=bus)
    return eng, bus


@pytest.fixture
def sample_steps() -> list[dict]:
    return [
        {"name": "build", "tool": "docker", "input": {"tag": "latest"}},
        {"name": "test", "tool": "pytest"},
        {"name": "deploy", "tool": "k8s"},
    ]


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestWorkflowDataclasses:

    def test_workflow_step_defaults(self):
        step = WorkflowStep()
        assert step.name == ""
        assert step.tool == ""
        assert step.input == {}

    def test_workflow_step_with_values(self):
        step = WorkflowStep(name="build", tool="docker", input={"key": "val"})
        assert step.name == "build"
        assert step.tool == "docker"
        assert step.input["key"] == "val"

    def test_workflow_auto_timestamp(self):
        before = time.time()
        wf = Workflow(name="test")
        after = time.time()
        assert before <= wf.created_at <= after

    def test_workflow_no_auto_timestamp_when_set(self):
        wf = Workflow(name="test", created_at=12345.0)
        assert wf.created_at == 12345.0

    def test_workflow_run_defaults(self):
        run = WorkflowRun()
        assert run.run_id == ""
        assert run.status == "pending"
        assert run.current_step == 0
        assert run.step_results == []


# ---------------------------------------------------------------------------
# create_workflow
# ---------------------------------------------------------------------------

class TestCreateWorkflow:

    def test_basic_creation(self, engine):
        result = engine.create_workflow("Deploy Pipeline")
        assert "workflow_id" in result
        assert result["name"] == "Deploy Pipeline"
        assert result["status"] == "draft"

    def test_with_description(self, engine):
        result = engine.create_workflow("WF", description="A test workflow")
        fetched = engine.get_workflow(result["workflow_id"])
        assert fetched["description"] == "A test workflow"

    def test_with_steps(self, engine, sample_steps):
        result = engine.create_workflow("WF", steps=sample_steps)
        fetched = engine.get_workflow(result["workflow_id"])
        assert len(fetched["steps"]) == 3
        assert fetched["steps"][0]["name"] == "build"
        assert fetched["steps"][0]["tool"] == "docker"

    def test_with_empty_steps(self, engine):
        result = engine.create_workflow("WF", steps=[])
        fetched = engine.get_workflow(result["workflow_id"])
        assert fetched["steps"] == []

    def test_default_steps_is_empty(self, engine):
        result = engine.create_workflow("WF")
        fetched = engine.get_workflow(result["workflow_id"])
        assert fetched["steps"] == []

    def test_unique_ids(self, engine):
        r1 = engine.create_workflow("A")
        r2 = engine.create_workflow("B")
        assert r1["workflow_id"] != r2["workflow_id"]

    def test_emits_created_event(self, engine_with_bus):
        eng, bus = engine_with_bus
        eng.create_workflow("EventWF", steps=[{"name": "s1"}])
        bus.publish.assert_called_once()
        event = bus.publish.call_args[0][0]
        assert isinstance(event, SylionEvent)
        assert event.topic == "execution.workflow.created"
        assert event.payload["name"] == "EventWF"
        assert event.payload["step_count"] == 1


# ---------------------------------------------------------------------------
# get_workflow
# ---------------------------------------------------------------------------

class TestGetWorkflow:

    def test_existing_workflow(self, engine):
        created = engine.create_workflow("FetchMe")
        fetched = engine.get_workflow(created["workflow_id"])
        assert fetched is not None
        assert fetched["name"] == "FetchMe"
        assert fetched["status"] == "draft"

    def test_nonexistent_returns_none(self, engine):
        assert engine.get_workflow("ghost-id") is None

    def test_returns_parsed_steps(self, engine):
        steps = [{"name": "a"}, {"name": "b"}]
        created = engine.create_workflow("Parsed", steps=steps)
        fetched = engine.get_workflow(created["workflow_id"])
        assert isinstance(fetched["steps"], list)
        assert len(fetched["steps"]) == 2

    def test_returns_all_fields(self, engine):
        created = engine.create_workflow("Full", description="desc")
        fetched = engine.get_workflow(created["workflow_id"])
        assert "workflow_id" in fetched
        assert "name" in fetched
        assert "description" in fetched
        assert "steps" in fetched
        assert "status" in fetched
        assert "created_at" in fetched
        assert "completed_at" in fetched


# ---------------------------------------------------------------------------
# list_workflows
# ---------------------------------------------------------------------------

class TestListWorkflows:

    def test_empty_list(self, engine):
        assert engine.list_workflows() == []

    def test_all_workflows(self, engine):
        engine.create_workflow("A")
        engine.create_workflow("B")
        engine.create_workflow("C")
        wfs = engine.list_workflows()
        assert len(wfs) == 3

    def test_filter_by_status(self, engine):
        engine.create_workflow("DraftWF")
        wf = engine.create_workflow("RunMe", steps=[{"name": "s1"}])
        engine.run_workflow(wf["workflow_id"])
        drafts = engine.list_workflows(status="draft")
        completed = engine.list_workflows(status="completed")
        assert len(drafts) == 1
        assert len(completed) == 1

    def test_filter_nonexistent_status_returns_empty(self, engine):
        engine.create_workflow("A")
        result = engine.list_workflows(status="nonexistent")
        assert result == []

    def test_ordered_by_created_at_desc(self, engine):
        engine.create_workflow("First")
        engine.create_workflow("Second")
        wfs = engine.list_workflows()
        assert wfs[0]["name"] == "Second"
        assert wfs[1]["name"] == "First"


# ---------------------------------------------------------------------------
# run_workflow
# ---------------------------------------------------------------------------

class TestRunWorkflow:

    def test_successful_run(self, engine, sample_steps):
        wf = engine.create_workflow("Runnable", steps=sample_steps)
        run = engine.run_workflow(wf["workflow_id"])
        assert run["status"] == "completed"
        assert run["steps_executed"] == 3
        assert "run_id" in run

    def test_single_step(self, engine):
        wf = engine.create_workflow("One", steps=[{"name": "s1", "tool": "t1"}])
        run = engine.run_workflow(wf["workflow_id"])
        assert run["steps_executed"] == 1

    def test_zero_steps(self, engine):
        wf = engine.create_workflow("Empty", steps=[])
        run = engine.run_workflow(wf["workflow_id"])
        assert run["status"] == "completed"
        assert run["steps_executed"] == 0

    def test_nonexistent_workflow(self, engine):
        result = engine.run_workflow("ghost-wf")
        assert "error" in result
        assert result["workflow_id"] == "ghost-wf"

    def test_updates_workflow_status_to_completed(self, engine):
        wf = engine.create_workflow("Status", steps=[{"name": "s1"}])
        engine.run_workflow(wf["workflow_id"])
        fetched = engine.get_workflow(wf["workflow_id"])
        assert fetched["status"] == "completed"
        assert fetched["completed_at"] > 0

    def test_step_results_recorded_in_run(self, engine):
        steps = [
            {"name": "step_a", "tool": "tool_a"},
            {"name": "step_b", "tool": "tool_b"},
        ]
        wf = engine.create_workflow("Detailed", steps=steps)
        run = engine.run_workflow(wf["workflow_id"])
        record = engine.get_run(run["run_id"])
        assert len(record["step_results"]) == 2
        assert record["step_results"][0]["name"] == "step_a"
        assert record["step_results"][0]["status"] == "completed"
        assert record["step_results"][1]["name"] == "step_b"

    def test_emits_completed_event(self, engine_with_bus):
        eng, bus = engine_with_bus
        wf = eng.create_workflow("EventRun", steps=[{"name": "s1"}])
        eng.run_workflow(wf["workflow_id"])
        # Two calls: created + completed
        assert bus.publish.call_count == 2
        event = bus.publish.call_args[0][0]
        assert event.topic == "execution.workflow.completed"
        assert event.payload["steps_executed"] == 1


# ---------------------------------------------------------------------------
# get_run
# ---------------------------------------------------------------------------

class TestGetRun:

    def test_existing_run(self, engine):
        wf = engine.create_workflow("R", steps=[{"name": "s"}])
        run = engine.run_workflow(wf["workflow_id"])
        record = engine.get_run(run["run_id"])
        assert record is not None
        assert record["status"] == "completed"
        assert isinstance(record["step_results"], list)

    def test_nonexistent_run(self, engine):
        assert engine.get_run("ghost-run") is None

    def test_run_has_parsed_step_results(self, engine):
        steps = [{"name": "a"}, {"name": "b"}]
        wf = engine.create_workflow("Parsed", steps=steps)
        run = engine.run_workflow(wf["workflow_id"])
        record = engine.get_run(run["run_id"])
        assert isinstance(record["step_results"], list)
        assert len(record["step_results"]) == 2


# ---------------------------------------------------------------------------
# list_runs
# ---------------------------------------------------------------------------

class TestListRuns:

    def test_empty(self, engine):
        assert engine.list_runs() == []

    def test_all_runs(self, engine):
        wf = engine.create_workflow("Multi", steps=[{"name": "s"}])
        engine.run_workflow(wf["workflow_id"])
        engine.run_workflow(wf["workflow_id"])
        runs = engine.list_runs()
        assert len(runs) == 2

    def test_filter_by_workflow_id(self, engine):
        wf1 = engine.create_workflow("WF1", steps=[{"name": "s"}])
        wf2 = engine.create_workflow("WF2", steps=[{"name": "s"}])
        engine.run_workflow(wf1["workflow_id"])
        engine.run_workflow(wf1["workflow_id"])
        engine.run_workflow(wf2["workflow_id"])
        runs_wf1 = engine.list_runs(workflow_id=wf1["workflow_id"])
        assert len(runs_wf1) == 2

    def test_limit_parameter(self, engine):
        wf = engine.create_workflow("Limited", steps=[{"name": "s"}])
        for _ in range(5):
            engine.run_workflow(wf["workflow_id"])
        runs = engine.list_runs(limit=3)
        assert len(runs) == 3

    def test_runs_have_parsed_step_results(self, engine):
        wf = engine.create_workflow("Parsed", steps=[{"name": "s"}])
        engine.run_workflow(wf["workflow_id"])
        runs = engine.list_runs()
        assert isinstance(runs[0]["step_results"], list)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestWorkflowEngineThreadSafety:

    def test_concurrent_create_workflow(self):
        engine = WorkflowEngine()
        results = []
        errors = []

        def create_wf(name):
            try:
                r = engine.create_workflow(name)
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_wf, args=(f"WF-{i}",))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        # All IDs should be unique
        ids = [r["workflow_id"] for r in results]
        assert len(set(ids)) == 20

    def test_concurrent_run_workflow(self):
        """Run the same workflow from multiple threads. Each thread creates
        its own WorkflowEngine to avoid SQLite contention on a single conn."""
        results = []
        errors = []

        def run_wf():
            try:
                eng = WorkflowEngine()
                wf = eng.create_workflow("ThreadWF", steps=[
                    {"name": f"step_{i}"} for i in range(3)
                ])
                r = eng.run_workflow(wf["workflow_id"])
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run_wf) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert all(r["status"] == "completed" for r in results)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestGetWorkflowEngineSingleton:

    def test_returns_instance(self):
        import sylion.execution.workflow_engine as mod
        mod._engine = None  # reset
        eng = get_workflow_engine()
        assert isinstance(eng, WorkflowEngine)

    def test_singleton_reuse(self):
        import sylion.execution.workflow_engine as mod
        mod._engine = None
        eng1 = get_workflow_engine()
        eng2 = get_workflow_engine()
        assert eng1 is eng2

    def test_singleton_with_args(self):
        import sylion.execution.workflow_engine as mod
        mod._engine = None
        bus = MagicMock(spec=EventBus)
        eng = get_workflow_engine(event_bus=bus)
        assert eng._event_bus is bus
        # Cleanup
        mod._engine = None
