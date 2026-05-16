"""Tests for sylion.quality.golden_set_runner -- GoldenSetRunner.

~40 tests covering: start_run, get_run, list_runs, get_results,
get_run_summary, compare_runs, get_stats, singleton, concurrency,
edge cases, error handling.
"""

from __future__ import annotations

import threading

import pytest

from sylion.quality.golden_set_runner import (
    GoldenSetRunner,
    get_golden_set_runner,
    reset_golden_set_runner,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_golden_set_runner()
    yield
    reset_golden_set_runner()


@pytest.fixture
def runner():
    return GoldenSetRunner(db_path=":memory:")


def _sample_cases():
    return [
        {"case_id": "c1", "input_json": "hello", "expected_output_json": "HELLO"},
        {"case_id": "c2", "input_json": "world", "expected_output_json": "WORLD"},
    ]


# ===========================================================================
# TestStartRun
# ===========================================================================

class TestStartRun:

    def test_start_run_returns_run_id(self, runner):
        result = runner.start_run("set-1", cases=_sample_cases(),
                                  executor_fn=lambda x: x.upper())
        assert "run_id" in result
        assert isinstance(result["run_id"], str)

    def test_start_run_all_pass(self, runner):
        result = runner.start_run("set-1", cases=_sample_cases(),
                                  executor_fn=lambda x: x.upper())
        assert result["passed"] == 2
        assert result["failed"] == 0
        assert result["status"] == "completed"

    def test_start_run_some_fail(self, runner):
        result = runner.start_run("set-1", cases=_sample_cases(),
                                  executor_fn=lambda x: "WRONG")
        assert result["failed"] == 2
        assert result["passed"] == 0

    def test_start_run_no_executor(self, runner):
        cases = [{"case_id": "c1", "input_json": "a",
                  "expected_output_json": "a"}]
        result = runner.start_run("set-1", cases=cases)
        # Without executor, actual is None, expected is "a" -> fail
        assert result["failed"] == 1

    def test_start_run_empty_cases(self, runner):
        result = runner.start_run("set-1", cases=[])
        assert result["status"] == "completed"
        assert result["total_cases"] == 0

    def test_start_run_with_config(self, runner):
        config = {"model": "gpt-4", "temperature": 0.0}
        result = runner.start_run("set-1", cases=_sample_cases(),
                                  runner_config_json=config,
                                  executor_fn=lambda x: x.upper())
        run = runner.get_run(result["run_id"])
        assert run["runner_config"] == config

    def test_start_run_executor_exception(self, runner):
        cases = [{"case_id": "c1", "input_json": "x",
                  "expected_output_json": "X"}]

        def boom(x):
            raise RuntimeError("boom")

        result = runner.start_run("set-1", cases=cases, executor_fn=boom)
        assert result["failed"] == 1
        assert result["passed"] == 0

    def test_start_run_measures_duration(self, runner):
        result = runner.start_run("set-1", cases=_sample_cases(),
                                  executor_fn=lambda x: x.upper())
        assert result["duration_ms"] >= 0

    def test_start_run_mixed_pass_fail(self, runner):
        cases = [
            {"case_id": "c1", "input_json": "hello",
             "expected_output_json": "HELLO"},
            {"case_id": "c2", "input_json": "world",
             "expected_output_json": "WRONG"},
        ]
        result = runner.start_run("set-1", cases=cases,
                                  executor_fn=lambda x: x.upper())
        assert result["passed"] == 1
        assert result["failed"] == 1


# ===========================================================================
# TestGetRun
# ===========================================================================

class TestGetRun:

    def test_get_existing_run(self, runner):
        r = runner.start_run("set-1", cases=_sample_cases(),
                             executor_fn=lambda x: x.upper())
        run = runner.get_run(r["run_id"])
        assert run is not None
        assert run["run_id"] == r["run_id"]

    def test_get_nonexistent_run(self, runner):
        assert runner.get_run("nonexistent") is None

    def test_get_run_parses_config(self, runner):
        config = {"key": "value"}
        r = runner.start_run("set-1", cases=_sample_cases(),
                             runner_config_json=config,
                             executor_fn=lambda x: x.upper())
        run = runner.get_run(r["run_id"])
        assert run["runner_config"] == config


# ===========================================================================
# TestListRuns
# ===========================================================================

class TestListRuns:

    def test_list_empty(self, runner):
        assert runner.list_runs() == []

    def test_list_returns_all(self, runner):
        runner.start_run("set-1", cases=_sample_cases(),
                         executor_fn=lambda x: x.upper())
        runner.start_run("set-2", cases=_sample_cases(),
                         executor_fn=lambda x: x.upper())
        assert len(runner.list_runs()) == 2

    def test_list_filter_by_set_id(self, runner):
        runner.start_run("set-1", cases=_sample_cases(),
                         executor_fn=lambda x: x.upper())
        runner.start_run("set-2", cases=_sample_cases(),
                         executor_fn=lambda x: x.upper())
        runs = runner.list_runs(set_id="set-1")
        assert len(runs) == 1
        assert runs[0]["set_id"] == "set-1"

    def test_list_filter_by_status(self, runner):
        runner.start_run("set-1", cases=_sample_cases(),
                         executor_fn=lambda x: x.upper())
        runs = runner.list_runs(status="completed")
        assert len(runs) == 1

    def test_list_filter_status_no_match(self, runner):
        runner.start_run("set-1", cases=_sample_cases(),
                         executor_fn=lambda x: x.upper())
        runs = runner.list_runs(status="running")
        assert runs == []


# ===========================================================================
# TestGetResults
# ===========================================================================

class TestGetResults:

    def test_get_results_for_run(self, runner):
        r = runner.start_run("set-1", cases=_sample_cases(),
                             executor_fn=lambda x: x.upper())
        results = runner.get_results(r["run_id"])
        assert len(results) == 2

    def test_get_results_parse_json(self, runner):
        cases = [{"case_id": "c1", "input_json": {"x": 1},
                  "expected_output_json": {"y": 2}}]
        r = runner.start_run("set-1", cases=cases,
                             executor_fn=lambda x: {"y": 2})
        results = runner.get_results(r["run_id"])
        assert results[0]["input_json"] == {"x": 1}
        assert results[0]["expected_json"] == {"y": 2}

    def test_get_results_passed_is_bool(self, runner):
        r = runner.start_run("set-1", cases=_sample_cases(),
                             executor_fn=lambda x: x.upper())
        results = runner.get_results(r["run_id"])
        for res in results:
            assert isinstance(res["passed"], bool)

    def test_get_results_nonexistent_run(self, runner):
        assert runner.get_results("nonexistent") == []


# ===========================================================================
# TestGetRunSummary
# ===========================================================================

class TestGetRunSummary:

    def test_summary_pass_rate(self, runner):
        r = runner.start_run("set-1", cases=_sample_cases(),
                             executor_fn=lambda x: x.upper())
        summary = runner.get_run_summary(r["run_id"])
        assert summary["pass_rate"] == 1.0
        assert summary["passed"] == 2

    def test_summary_nonexistent(self, runner):
        assert runner.get_run_summary("nonexistent") is None

    def test_summary_partial_pass(self, runner):
        cases = [
            {"case_id": "c1", "input_json": "hello",
             "expected_output_json": "HELLO"},
            {"case_id": "c2", "input_json": "world",
             "expected_output_json": "WRONG"},
        ]
        r = runner.start_run("set-1", cases=cases,
                             executor_fn=lambda x: x.upper())
        summary = runner.get_run_summary(r["run_id"])
        assert summary["pass_rate"] == 0.5

    def test_summary_zero_cases(self, runner):
        r = runner.start_run("set-1", cases=[])
        summary = runner.get_run_summary(r["run_id"])
        assert summary["pass_rate"] == 0.0


# ===========================================================================
# TestCompareRuns
# ===========================================================================

class TestCompareRuns:

    def test_compare_identical_runs(self, runner):
        r1 = runner.start_run("set-1", cases=_sample_cases(),
                              executor_fn=lambda x: x.upper())
        r2 = runner.start_run("set-1", cases=_sample_cases(),
                              executor_fn=lambda x: x.upper())
        diff = runner.compare_runs(r1["run_id"], r2["run_id"])
        assert diff is not None
        assert all(not d["changed"] for d in diff["diffs"])

    def test_compare_different_runs(self, runner):
        r1 = runner.start_run("set-1", cases=_sample_cases(),
                              executor_fn=lambda x: x.upper())
        r2 = runner.start_run("set-1", cases=_sample_cases(),
                              executor_fn=lambda x: "WRONG")
        diff = runner.compare_runs(r1["run_id"], r2["run_id"])
        assert diff is not None
        assert all(d["changed"] for d in diff["diffs"])

    def test_compare_nonexistent_run(self, runner):
        r = runner.start_run("set-1", cases=_sample_cases(),
                             executor_fn=lambda x: x.upper())
        assert runner.compare_runs(r["run_id"], "nonexistent") is None

    def test_compare_has_run_metadata(self, runner):
        r1 = runner.start_run("set-1", cases=_sample_cases(),
                              executor_fn=lambda x: x.upper())
        r2 = runner.start_run("set-1", cases=_sample_cases(),
                              executor_fn=lambda x: x.upper())
        diff = runner.compare_runs(r1["run_id"], r2["run_id"])
        assert "run_1" in diff
        assert "run_2" in diff
        assert diff["run_1"]["passed"] == 2


# ===========================================================================
# TestGetStats
# ===========================================================================

class TestGetStats:

    def test_stats_empty(self, runner):
        stats = runner.get_stats()
        assert stats["total_runs"] == 0
        assert stats["pass_rate"] == 0.0

    def test_stats_with_runs(self, runner):
        runner.start_run("set-1", cases=_sample_cases(),
                         executor_fn=lambda x: x.upper())
        stats = runner.get_stats()
        assert stats["total_runs"] == 1
        assert stats["total_passed"] == 2
        assert stats["pass_rate"] == 1.0

    def test_stats_accumulates(self, runner):
        runner.start_run("set-1", cases=_sample_cases(),
                         executor_fn=lambda x: x.upper())
        runner.start_run("set-2", cases=_sample_cases(),
                         executor_fn=lambda x: "WRONG")
        stats = runner.get_stats()
        assert stats["total_runs"] == 2
        assert stats["total_passed"] == 2
        assert stats["total_failed"] == 2


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        inst = get_golden_set_runner(db_path=":memory:")
        assert isinstance(inst, GoldenSetRunner)

    def test_get_idempotent(self):
        a = get_golden_set_runner(db_path=":memory:")
        b = get_golden_set_runner()
        assert a is b

    def test_reset_creates_new(self):
        a = get_golden_set_runner(db_path=":memory:")
        reset_golden_set_runner(db_path=":memory:")
        b = get_golden_set_runner(db_path=":memory:")
        assert a is not b


# ===========================================================================
# TestConcurrency
# ===========================================================================

class TestConcurrency:

    def test_concurrent_runs(self, runner):
        errors = []

        def do_run(i):
            try:
                cases = [{"case_id": f"c{i}", "input_json": f"val{i}",
                          "expected_output_json": f"val{i}"}]
                runner.start_run(f"set-{i}", cases=cases,
                                 executor_fn=lambda x: x)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_run, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert runner.get_stats()["total_runs"] == 20
