"""Tests for sylion.rebuild.golden_set_manager module."""
import pytest
from sylion.rebuild.golden_set_manager import GoldenSetManager


class TestGoldenSetManager:
    @pytest.fixture
    def mgr(self):
        return GoldenSetManager()

    def test_create_golden_set(self, mgr):
        result = mgr.create_golden_set("Test Set", version="1.0")
        assert "set_id" in result
        assert result["name"] == "Test Set"
        assert result["status"] == "draft"

    def test_create_golden_set_with_cases(self, mgr):
        cases = [{"input": "a", "expected": "b"}, {"input": "c", "expected": "d"}]
        result = mgr.create_golden_set("With Cases", test_cases=cases)
        gs = mgr.get_golden_set(result["set_id"])
        assert gs["case_count"] == 2

    def test_add_test_case(self, mgr):
        gs = mgr.create_golden_set("Case Test")
        result = mgr.add_test_case(gs["set_id"], "input data", "expected output")
        assert "case_id" in result
        assert result["set_id"] == gs["set_id"]

    def test_get_golden_set(self, mgr):
        gs = mgr.create_golden_set("Get Test")
        mgr.add_test_case(gs["set_id"], "in", "out")
        found = mgr.get_golden_set(gs["set_id"])
        assert found is not None
        assert found["name"] == "Get Test"
        assert found["case_count"] == 1

    def test_get_golden_set_not_found(self, mgr):
        assert mgr.get_golden_set("nonexistent") is None

    def test_list_golden_sets(self, mgr):
        mgr.create_golden_set("List A")
        mgr.create_golden_set("List B")
        sets = mgr.list_golden_sets()
        assert len(sets) >= 2

    def test_run_fidelity_test(self, mgr):
        gs = mgr.create_golden_set("Fidelity", test_cases=[{"input": "a", "expected": "a"}])
        result = mgr.run_fidelity_test(gs["set_id"], "mod-a", threshold=0.90)
        assert result["passed"] is True
        assert result["score"] >= 0.90

    def test_run_fidelity_test_not_found(self, mgr):
        result = mgr.run_fidelity_test("nonexistent", "mod-a")
        assert "error" in result

    def test_get_fidelity_history(self, mgr):
        gs = mgr.create_golden_set("History", test_cases=[{"input": "x", "expected": "x"}])
        mgr.run_fidelity_test(gs["set_id"], "mod-hist")
        history = mgr.get_fidelity_history("mod-hist")
        assert len(history) >= 1

    def test_validate_set(self, mgr):
        gs = mgr.create_golden_set("Valid", test_cases=[{"input": "i", "expected": "o"}])
        result = mgr.validate_set(gs["set_id"])
        assert result["valid"] is True

    def test_validate_set_empty(self, mgr):
        gs = mgr.create_golden_set("Empty")
        result = mgr.validate_set(gs["set_id"])
        assert result["valid"] is False

    def test_validate_set_not_found(self, mgr):
        result = mgr.validate_set("nonexistent")
        assert result["valid"] is False

    def test_get_stats(self, mgr):
        mgr.create_golden_set("Stats")
        stats = mgr.get_stats()
        assert stats["total_sets"] >= 1
