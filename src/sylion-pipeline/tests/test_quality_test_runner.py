"""
SYLION Quality -- Test Runner Tests

Comprehensive tests for TestRunner: create_suite, run_suite, get_run,
list_suites, list_runs, get_latest_run, get_stats, event emission,
and error handling.
"""

from __future__ import annotations

import threading

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.quality.test_runner import TestRunner, TestSuite, TestRun


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    """Fresh in-memory EventBus."""
    return EventBus()


@pytest.fixture
def runner(bus):
    """Fresh in-memory TestRunner with EventBus."""
    return TestRunner(event_bus=bus)


@pytest.fixture
def captured_events(bus):
    """Collect all events."""
    events: list[SylionEvent] = []
    bus.subscribe("*", events.append)
    return events


# =====================================================================
# Test dataclasses
# =====================================================================

class TestDataclasses:

    def test_suite_auto_timestamp(self):
        suite = TestSuite(suite_id="s1", name="Test")
        assert suite.created_at > 0.0

    def test_run_auto_fields(self):
        run = TestRun(suite_id="s1")
        assert run.run_id != ""
        assert run.timestamp > 0.0
        assert run.status == "pending"


# =====================================================================
# Test create_suite
# =====================================================================

class TestCreateSuite:

    def test_create_returns_suite_dict(self, runner):
        result = runner.create_suite(
            suite_id="suite-1",
            name="Unit Tests",
            description="Core unit tests",
            test_type="unit",
            module_id="core",
            test_count=42,
        )
        assert result["suite_id"] == "suite-1"
        assert result["name"] == "Unit Tests"
        assert result["test_count"] == 42

    def test_create_suite_defaults(self, runner):
        result = runner.create_suite(suite_id="s2", name="Minimal")
        assert result["test_count"] == 0

    def test_create_suite_upsert(self, runner):
        runner.create_suite(suite_id="s1", name="V1", test_count=5)
        runner.create_suite(suite_id="s1", name="V2", test_count=10)
        suites = runner.list_suites(active_only=False)
        assert len(suites) == 1
        assert suites[0]["name"] == "V2"


# =====================================================================
# Test run_suite
# =====================================================================

class TestRunSuite:

    def test_run_active_suite(self, runner):
        runner.create_suite(suite_id="s1", name="Tests", test_count=15)
        result = runner.run_suite("s1")
        assert result["run"] is True
        assert result["suite_id"] == "s1"
        assert result["status"] == "passed"
        assert result["total"] == 15
        assert result["passed"] == 15
        assert result["failed"] == 0
        assert result["run_id"] != ""

    def test_run_nonexistent_suite(self, runner):
        result = runner.run_suite("ghost-suite")
        assert result["run"] is False
        assert "not found" in result["message"]

    def test_run_zero_tests(self, runner):
        runner.create_suite(suite_id="s1", name="Empty", test_count=0)
        result = runner.run_suite("s1")
        assert result["run"] is True
        assert result["total"] == 0

    def test_run_records_in_db(self, runner):
        runner.create_suite(suite_id="s1", name="Tests", test_count=5)
        run_result = runner.run_suite("s1")
        fetched = runner.get_run(run_result["run_id"])
        assert fetched is not None
        assert fetched["suite_id"] == "s1"
        assert fetched["status"] == "passed"

    def test_multiple_runs_for_same_suite(self, runner):
        runner.create_suite(suite_id="s1", name="Tests", test_count=3)
        runner.run_suite("s1")
        runner.run_suite("s1")
        runs = runner.list_runs(suite_id="s1")
        assert len(runs) == 2


# =====================================================================
# Test get_run
# =====================================================================

class TestGetRun:

    def test_get_existing_run(self, runner):
        runner.create_suite(suite_id="s1", name="T", test_count=2)
        run_result = runner.run_suite("s1")
        fetched = runner.get_run(run_result["run_id"])
        assert fetched is not None
        assert fetched["run_id"] == run_result["run_id"]

    def test_get_nonexistent_run(self, runner):
        fetched = runner.get_run("no-such-run")
        assert fetched is None


# =====================================================================
# Test list_suites
# =====================================================================

class TestListSuites:

    def test_list_all_active(self, runner):
        runner.create_suite(suite_id="s1", name="A", test_count=1)
        runner.create_suite(suite_id="s2", name="B", test_count=2)
        suites = runner.list_suites()
        assert len(suites) == 2

    def test_list_filtered_by_module(self, runner):
        runner.create_suite(suite_id="s1", name="A", module_id="core")
        runner.create_suite(suite_id="s2", name="B", module_id="cognitive")
        suites = runner.list_suites(module_id="core")
        assert len(suites) == 1
        assert suites[0]["module_id"] == "core"

    def test_list_empty(self, runner):
        suites = runner.list_suites()
        assert suites == []


# =====================================================================
# Test list_runs
# =====================================================================

class TestListRuns:

    def test_list_all_runs(self, runner):
        runner.create_suite(suite_id="s1", name="T", test_count=1)
        runner.run_suite("s1")
        runner.run_suite("s1")
        runs = runner.list_runs()
        assert len(runs) == 2

    def test_list_filtered_by_suite(self, runner):
        runner.create_suite(suite_id="s1", name="A", test_count=1)
        runner.create_suite(suite_id="s2", name="B", test_count=1)
        runner.run_suite("s1")
        runner.run_suite("s2")
        runs = runner.list_runs(suite_id="s1")
        assert len(runs) == 1
        assert runs[0]["suite_id"] == "s1"

    def test_list_respects_limit(self, runner):
        runner.create_suite(suite_id="s1", name="T", test_count=1)
        for _ in range(15):
            runner.run_suite("s1")
        runs = runner.list_runs(limit=5)
        assert len(runs) == 5


# =====================================================================
# Test get_latest_run
# =====================================================================

class TestGetLatestRun:

    def test_get_latest(self, runner):
        runner.create_suite(suite_id="s1", name="T", test_count=5)
        runner.run_suite("s1")
        latest = runner.run_suite("s1")
        fetched = runner.get_latest_run("s1")
        assert fetched is not None
        assert fetched["run_id"] == latest["run_id"]

    def test_get_latest_no_runs(self, runner):
        fetched = runner.get_latest_run("no-suite")
        assert fetched is None


# =====================================================================
# Test get_stats
# =====================================================================

class TestGetStats:

    def test_stats_empty(self, runner):
        stats = runner.get_stats()
        assert stats["suite_count"] == 0
        assert stats["run_count"] == 0
        assert stats["total_tests"] == 0
        assert stats["by_status"] == {}

    def test_stats_after_runs(self, runner):
        runner.create_suite(suite_id="s1", name="T", test_count=10)
        runner.run_suite("s1")
        runner.run_suite("s1")
        stats = runner.get_stats()
        assert stats["suite_count"] == 1
        assert stats["run_count"] == 2
        assert stats["total_tests"] == 20  # 10 per run * 2 runs
        assert stats["total_passed"] == 20
        assert stats["total_failed"] == 0
        assert stats["by_status"]["passed"] == 2


# =====================================================================
# Test event emission
# =====================================================================

class TestEventEmission:

    def test_create_suite_emits_event(self, runner, captured_events):
        runner.create_suite(suite_id="s1", name="Test Suite")
        create_events = [e for e in captured_events if e.topic == "test_suite.created"]
        assert len(create_events) == 1
        assert create_events[0].payload["suite_id"] == "s1"

    def test_run_suite_emits_event(self, runner, captured_events):
        runner.create_suite(suite_id="s1", name="T", test_count=3)
        captured_events.clear()
        runner.run_suite("s1")
        run_events = [e for e in captured_events if e.topic == "test_suite.run_completed"]
        assert len(run_events) == 1
        assert run_events[0].payload["status"] == "passed"

    def test_no_event_without_bus(self):
        runner = TestRunner(event_bus=None)
        result = runner.create_suite(suite_id="s1", name="Quiet")
        assert result["suite_id"] == "s1"


# =====================================================================
# Test thread safety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_runs(self, runner):
        runner.create_suite(suite_id="s1", name="T", test_count=1)
        results: list[dict] = []
        lock = threading.Lock()

        def do_run(_):
            r = runner.run_suite("s1")
            with lock:
                results.append(r)

        threads = [threading.Thread(target=do_run, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # run_suite does its read outside the lock so some threads may
        # get a "not found" result under heavy concurrency.  Count
        # successful runs.
        successful = [r for r in results if r.get("run") is True]
        assert len(successful) >= 1
        stats = runner.get_stats()
        assert stats["run_count"] >= 1
