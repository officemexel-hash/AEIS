"""Tests for sylion.rebuild.cft_runner -- CFTRunner."""

import pytest

from sylion.rebuild.cft_runner import CFTRunner, CFTSuite, CFTResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner():
    return CFTRunner(db_path=":memory:")


def _create_suite(runner, name="Test Suite", description="desc",
                  module_id="mod-1"):
    return runner.create_suite(name, description, module_id)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class TestCFTSuite:
    def test_auto_generates_suite_id(self):
        s = CFTSuite(name="test")
        assert len(s.suite_id) > 0

    def test_auto_generates_timestamp(self):
        s = CFTSuite(name="test")
        assert s.created_at > 0

    def test_preserves_explicit_id(self):
        s = CFTSuite(suite_id="explicit-id", name="test")
        assert s.suite_id == "explicit-id"


class TestCFTResult:
    def test_auto_generates_result_id(self):
        r = CFTResult(suite_id="s1")
        assert len(r.result_id) > 0

    def test_auto_generates_timestamp(self):
        r = CFTResult(suite_id="s1")
        assert r.timestamp > 0


# ---------------------------------------------------------------------------
# create_suite()
# ---------------------------------------------------------------------------

class TestCreateSuite:
    def test_create_returns_dict(self, runner):
        r = _create_suite(runner)
        assert "suite_id" in r
        assert r["name"] == "Test Suite"

    def test_create_with_defaults(self, runner):
        r = runner.create_suite("Minimal")
        assert r["name"] == "Minimal"

    def test_create_with_module_id(self, runner):
        r = runner.create_suite("M", module_id="kernel-core")
        assert r["name"] == "M"


# ---------------------------------------------------------------------------
# run_test()
# ---------------------------------------------------------------------------

class TestRunTest:
    def test_matching_hashes_pass(self, runner):
        _create_suite(runner)
        sid = runner.list_suites()[0]["suite_id"]
        r = runner.run_test(sid, "abc123")
        assert r["passed"] is True
        assert r["fidelity_score"] == 1.0

    def test_mismatched_hashes_fail(self, runner):
        _create_suite(runner)
        sid = runner.list_suites()[0]["suite_id"]
        r = runner.run_test(sid, "golden", actual_hash="different")
        assert r["passed"] is False
        assert r["fidelity_score"] == 0.0

    def test_explicit_actual_hash(self, runner):
        _create_suite(runner)
        sid = runner.list_suites()[0]["suite_id"]
        r = runner.run_test(sid, "h1", actual_hash="h1")
        assert r["passed"] is True

    def test_result_has_result_id(self, runner):
        _create_suite(runner)
        sid = runner.list_suites()[0]["suite_id"]
        r = runner.run_test(sid, "h1")
        assert "result_id" in r

    def test_custom_duration(self, runner):
        _create_suite(runner)
        sid = runner.list_suites()[0]["suite_id"]
        r = runner.run_test(sid, "h1", duration_ms=500)
        # duration_ms is stored in the DB record
        results = runner.get_results(sid)
        assert results[0]["duration_ms"] == 500


# ---------------------------------------------------------------------------
# get_results()
# ---------------------------------------------------------------------------

class TestGetResults:
    def test_empty_for_suite(self, runner):
        _create_suite(runner)
        sid = runner.list_suites()[0]["suite_id"]
        assert runner.get_results(sid) == []

    def test_returns_results(self, runner):
        _create_suite(runner)
        sid = runner.list_suites()[0]["suite_id"]
        runner.run_test(sid, "h1")
        runner.run_test(sid, "h2")
        assert len(runner.get_results(sid)) == 2

    def test_limit(self, runner):
        _create_suite(runner)
        sid = runner.list_suites()[0]["suite_id"]
        for i in range(5):
            runner.run_test(sid, f"h{i}")
        assert len(runner.get_results(sid, limit=3)) == 3

    def test_only_results_for_requested_suite(self, runner):
        s1 = runner.create_suite("Suite1", module_id="m1")
        s2 = runner.create_suite("Suite2", module_id="m2")
        runner.run_test(s1["suite_id"], "h1")
        runner.run_test(s2["suite_id"], "h2")
        assert len(runner.get_results(s1["suite_id"])) == 1


# ---------------------------------------------------------------------------
# get_pass_rate()
# ---------------------------------------------------------------------------

class TestPassRate:
    def test_empty_suite(self, runner):
        _create_suite(runner)
        sid = runner.list_suites()[0]["suite_id"]
        rate = runner.get_pass_rate(sid)
        assert rate["total"] == 0
        assert rate["pass_rate"] == 0.0

    def test_all_pass(self, runner):
        _create_suite(runner)
        sid = runner.list_suites()[0]["suite_id"]
        runner.run_test(sid, "h1")
        runner.run_test(sid, "h2")
        rate = runner.get_pass_rate(sid)
        assert rate["passed"] == 2
        assert rate["pass_rate"] == 1.0

    def test_mixed_results(self, runner):
        _create_suite(runner)
        sid = runner.list_suites()[0]["suite_id"]
        runner.run_test(sid, "h1")
        runner.run_test(sid, "h2", actual_hash="different")
        rate = runner.get_pass_rate(sid)
        assert rate["passed"] == 1
        assert rate["total"] == 2
        assert rate["pass_rate"] == 0.5


# ---------------------------------------------------------------------------
# list_suites()
# ---------------------------------------------------------------------------

class TestListSuites:
    def test_list_all_active(self, runner):
        _create_suite(runner)
        assert len(runner.list_suites()) == 1

    def test_filter_by_module(self, runner):
        runner.create_suite("A", module_id="m1")
        runner.create_suite("B", module_id="m2")
        assert len(runner.list_suites(module_id="m1")) == 1

    def test_active_only_default(self, runner):
        _create_suite(runner)
        suites = runner.list_suites(active_only=True)
        assert len(suites) == 1

    def test_limit(self, runner):
        for i in range(5):
            runner.create_suite(f"Suite-{i}")
        assert len(runner.list_suites(limit=3)) == 3

    def test_empty(self, runner):
        assert runner.list_suites() == []


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_create_suite_emits(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        runner = CFTRunner(db_path=":memory:", event_bus=MockBus())
        runner.create_suite("Test")
        assert any(e.topic == "rebuild.cft.suite_created" for e in events)

    def test_run_test_emits(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        runner = CFTRunner(db_path=":memory:", event_bus=MockBus())
        s = runner.create_suite("Test")
        runner.run_test(s["suite_id"], "h1")
        assert any(e.topic == "rebuild.cft.test_completed" for e in events)
