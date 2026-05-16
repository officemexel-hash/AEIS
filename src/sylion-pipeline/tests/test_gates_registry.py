"""Tests for sylion.governance.gates_registry -- GatesRegistry.

~40 tests covering: create_gate, update_gate, delete_gate, get_gate,
list_gates, evaluate_gate, get_evaluations, get_gate_stats, singleton,
concurrency, edge cases, error handling.
"""

from __future__ import annotations

import threading

import pytest

from sylion.governance.gates_registry import (
    GatesRegistry,
    get_gates_registry,
    reset_gates_registry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_gates_registry()
    yield
    reset_gates_registry()


@pytest.fixture
def reg():
    return GatesRegistry(db_path=":memory:")


# ===========================================================================
# TestCreateGate
# ===========================================================================

class TestCreateGate:

    def test_create_returns_gate_id(self, reg):
        result = reg.create_gate("Test Gate")
        assert "gate_id" in result
        assert isinstance(result["gate_id"], str)

    def test_create_returns_name(self, reg):
        result = reg.create_gate("Test Gate")
        assert result["name"] == "Test Gate"

    def test_create_with_type(self, reg):
        result = reg.create_gate("G", gate_type="security")
        assert result["gate_type"] == "security"

    def test_create_default_type(self, reg):
        result = reg.create_gate("G")
        assert result["gate_type"] == "quality"

    def test_create_with_criteria(self, reg):
        criteria = {"min_coverage": 80, "tests_pass": True}
        result = reg.create_gate("G", criteria_json=criteria)
        assert result["criteria_json"] == criteria

    def test_create_with_scope(self, reg):
        result = reg.create_gate("G", scope="module.auth")
        assert result["scope"] == "module.auth"

    def test_create_default_scope_empty(self, reg):
        result = reg.create_gate("G")
        assert result["scope"] == ""

    def test_create_enabled_by_default(self, reg):
        result = reg.create_gate("G")
        assert result["enabled"] == 1

    def test_create_has_created_at(self, reg):
        result = reg.create_gate("G")
        assert result["created_at"] > 0

    def test_create_unique_ids(self, reg):
        a = reg.create_gate("A")
        b = reg.create_gate("B")
        assert a["gate_id"] != b["gate_id"]


# ===========================================================================
# TestUpdateGate
# ===========================================================================

class TestUpdateGate:

    def test_update_name(self, reg):
        g = reg.create_gate("Original")
        result = reg.update_gate(g["gate_id"], name="Updated")
        assert result["name"] == "Updated"

    def test_update_type(self, reg):
        g = reg.create_gate("G")
        result = reg.update_gate(g["gate_id"], gate_type="security")
        assert result["gate_type"] == "security"

    def test_update_criteria(self, reg):
        g = reg.create_gate("G")
        new_criteria = {"max_latency_ms": 100}
        result = reg.update_gate(g["gate_id"], criteria_json=new_criteria)
        assert result["criteria_json"] == new_criteria

    def test_update_scope(self, reg):
        g = reg.create_gate("G")
        result = reg.update_gate(g["gate_id"], scope="module.new")
        assert result["scope"] == "module.new"

    def test_update_enabled(self, reg):
        g = reg.create_gate("G")
        result = reg.update_gate(g["gate_id"], enabled=False)
        assert result["enabled"] == 0

    def test_update_nonexistent_returns_none(self, reg):
        assert reg.update_gate("nonexistent", name="X") is None

    def test_update_sets_updated_at(self, reg):
        g = reg.create_gate("G")
        result = reg.update_gate(g["gate_id"], name="New")
        assert result["updated_at"] is not None


# ===========================================================================
# TestDeleteGate
# ===========================================================================

class TestDeleteGate:

    def test_delete_existing(self, reg):
        g = reg.create_gate("G")
        assert reg.delete_gate(g["gate_id"]) is True

    def test_delete_nonexistent(self, reg):
        assert reg.delete_gate("nonexistent") is False

    def test_delete_removes_evaluations(self, reg):
        g = reg.create_gate("G", criteria_json={"x": 1})
        reg.evaluate_gate(g["gate_id"], context_json={"x": 1})
        reg.delete_gate(g["gate_id"])
        assert reg.get_evaluations(g["gate_id"]) == []

    def test_delete_removes_from_list(self, reg):
        g = reg.create_gate("G")
        reg.delete_gate(g["gate_id"])
        assert reg.list_gates() == []


# ===========================================================================
# TestGetGate
# ===========================================================================

class TestGetGate:

    def test_get_existing(self, reg):
        g = reg.create_gate("G", criteria_json={"k": "v"})
        result = reg.get_gate(g["gate_id"])
        assert result is not None
        assert result["name"] == "G"
        assert result["criteria_json"] == {"k": "v"}

    def test_get_nonexistent(self, reg):
        assert reg.get_gate("nonexistent") is None


# ===========================================================================
# TestListGates
# ===========================================================================

class TestListGates:

    def test_list_empty(self, reg):
        assert reg.list_gates() == []

    def test_list_returns_all(self, reg):
        reg.create_gate("A")
        reg.create_gate("B")
        assert len(reg.list_gates()) == 2

    def test_list_filter_by_type(self, reg):
        reg.create_gate("A", gate_type="quality")
        reg.create_gate("B", gate_type="security")
        result = reg.list_gates(gate_type="security")
        assert len(result) == 1

    def test_list_filter_by_scope(self, reg):
        reg.create_gate("A", scope="mod1")
        reg.create_gate("B", scope="mod2")
        result = reg.list_gates(scope="mod1")
        assert len(result) == 1

    def test_list_criteria_parsed(self, reg):
        reg.create_gate("G", criteria_json={"x": 1})
        gates = reg.list_gates()
        assert gates[0]["criteria_json"] == {"x": 1}


# ===========================================================================
# TestEvaluateGate
# ===========================================================================

class TestEvaluateGate:

    def test_evaluate_pass(self, reg):
        g = reg.create_gate("G", criteria_json={"status": "ready"})
        result = reg.evaluate_gate(g["gate_id"], context_json={"status": "ready"})
        assert result["result"] == "passed"
        assert result["passed"] is True

    def test_evaluate_fail(self, reg):
        g = reg.create_gate("G", criteria_json={"status": "ready"})
        result = reg.evaluate_gate(g["gate_id"], context_json={"status": "not_ready"})
        assert result["result"] == "failed"
        assert result["passed"] is False

    def test_evaluate_no_criteria_passes(self, reg):
        g = reg.create_gate("G")
        result = reg.evaluate_gate(g["gate_id"], context_json={})
        assert result["result"] == "passed"

    def test_evaluate_multiple_criteria(self, reg):
        g = reg.create_gate("G", criteria_json={"a": 1, "b": 2})
        result = reg.evaluate_gate(g["gate_id"], context_json={"a": 1, "b": 2})
        assert result["result"] == "passed"

    def test_evaluate_partial_criteria_fails(self, reg):
        g = reg.create_gate("G", criteria_json={"a": 1, "b": 2})
        result = reg.evaluate_gate(g["gate_id"], context_json={"a": 1, "b": 3})
        assert result["result"] == "failed"

    def test_evaluate_nonexistent_gate(self, reg):
        result = reg.evaluate_gate("nonexistent")
        assert result is None

    def test_evaluate_disabled_gate(self, reg):
        g = reg.create_gate("G", criteria_json={"x": 1})
        reg.update_gate(g["gate_id"], enabled=False)
        result = reg.evaluate_gate(g["gate_id"], context_json={"x": 1})
        assert result is None

    def test_evaluate_returns_evaluation_id(self, reg):
        g = reg.create_gate("G")
        result = reg.evaluate_gate(g["gate_id"])
        assert "evaluation_id" in result
        assert isinstance(result["evaluation_id"], str)

    def test_evaluate_returns_message(self, reg):
        g = reg.create_gate("G", criteria_json={"x": 1})
        result = reg.evaluate_gate(g["gate_id"], context_json={"x": 2})
        assert "message" in result
        assert "x" in result["message"]

    def test_evaluate_string_context(self, reg):
        g = reg.create_gate("G", criteria_json={"x": 1})
        result = reg.evaluate_gate(g["gate_id"],
                                   context_json='{"x": 1}')
        assert result["result"] == "passed"


# ===========================================================================
# TestGetEvaluations
# ===========================================================================

class TestGetEvaluations:

    def test_empty(self, reg):
        g = reg.create_gate("G")
        assert reg.get_evaluations(g["gate_id"]) == []

    def test_returns_evaluations(self, reg):
        g = reg.create_gate("G")
        reg.evaluate_gate(g["gate_id"])
        evals = reg.get_evaluations(g["gate_id"])
        assert len(evals) == 1

    def test_limit(self, reg):
        g = reg.create_gate("G")
        for _ in range(10):
            reg.evaluate_gate(g["gate_id"])
        evals = reg.get_evaluations(g["gate_id"], limit=3)
        assert len(evals) == 3

    def test_context_json_parsed(self, reg):
        g = reg.create_gate("G")
        reg.evaluate_gate(g["gate_id"], context_json={"k": "v"})
        evals = reg.get_evaluations(g["gate_id"])
        assert evals[0]["context_json"] == {"k": "v"}


# ===========================================================================
# TestGetGateStats
# ===========================================================================

class TestGetGateStats:

    def test_stats_empty(self, reg):
        stats = reg.get_gate_stats()
        assert stats["total_gates"] == 0
        assert stats["total_evaluations"] == 0
        assert stats["pass_rate"] == 0.0

    def test_stats_with_data(self, reg):
        g = reg.create_gate("G", criteria_json={"x": 1})
        reg.evaluate_gate(g["gate_id"], context_json={"x": 1})
        reg.evaluate_gate(g["gate_id"], context_json={"x": 2})
        stats = reg.get_gate_stats()
        assert stats["total_gates"] == 1
        assert stats["total_evaluations"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["pass_rate"] == 0.5


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        inst = get_gates_registry(db_path=":memory:")
        assert isinstance(inst, GatesRegistry)

    def test_get_idempotent(self):
        a = get_gates_registry(db_path=":memory:")
        b = get_gates_registry()
        assert a is b

    def test_reset_creates_new(self):
        a = get_gates_registry(db_path=":memory:")
        reset_gates_registry(db_path=":memory:")
        b = get_gates_registry(db_path=":memory:")
        assert a is not b


# ===========================================================================
# TestConcurrency
# ===========================================================================

class TestConcurrency:

    def test_concurrent_create_and_evaluate(self, reg):
        errors = []

        def create_and_eval(i):
            try:
                g = reg.create_gate(f"G{i}", criteria_json={"x": i})
                reg.evaluate_gate(g["gate_id"], context_json={"x": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_and_eval, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert reg.get_gate_stats()["total_gates"] == 20
        assert reg.get_gate_stats()["total_evaluations"] == 20
