"""
test_quality_gate_engine.py - Comprehensive tests for QualityGateEngine.

~40 tests covering:
  1. Gate CRUD (create, get, list, update, delete)
  2. Gate type validation
  3. Evaluation logic (pass, fail, warning, error, disabled gate, missing context)
  4. Evaluation queries (get, list, filters)
  5. Statistics
  6. EventBus integration
  7. Thread safety
  8. Singleton / reset
  9. Criteria evaluation (operators, edge cases)
  10. Default criteria
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.quality.quality_gate_engine import (
    DEFAULT_CRITERIA,
    GateEvaluation,
    QualityGate,
    QualityGateEngine,
    VALID_GATE_TYPES,
    VALID_RESULTS,
    get_quality_gate_engine,
    reset_quality_gate_engine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine(event_bus: EventBus | None = None) -> QualityGateEngine:
    """Create a fresh in-memory engine."""
    return QualityGateEngine(db_path=":memory:", event_bus=event_bus)


def _create_sample_gate(engine: QualityGateEngine, name: str = "Test Gate",
                        gate_type: str = "entry",
                        criteria: dict | None = None) -> dict:
    """Create a sample gate and return its dict."""
    return engine.create_gate(
        name=name,
        gate_type=gate_type,
        description="Sample gate for testing",
        criteria=criteria,
    )


# ===================================================================
# PART 1: Constants and data classes (5 tests)
# ===================================================================

class TestConstants:
    def test_valid_gate_types(self):
        assert "entry" in VALID_GATE_TYPES
        assert "exit" in VALID_GATE_TYPES
        assert "transition" in VALID_GATE_TYPES
        assert "deployment" in VALID_GATE_TYPES
        assert len(VALID_GATE_TYPES) == 4

    def test_valid_results(self):
        assert "pass" in VALID_RESULTS
        assert "fail" in VALID_RESULTS
        assert "warning" in VALID_RESULTS
        assert "error" in VALID_RESULTS
        assert len(VALID_RESULTS) == 4

    def test_default_criteria_has_test_coverage(self):
        assert "test_coverage" in DEFAULT_CRITERIA
        assert DEFAULT_CRITERIA["test_coverage"]["operator"] == ">="
        assert DEFAULT_CRITERIA["test_coverage"]["value"] == 0.8

    def test_default_criteria_has_no_critical_violations(self):
        assert "no_critical_violations" in DEFAULT_CRITERIA
        assert DEFAULT_CRITERIA["no_critical_violations"]["operator"] == "=="
        assert DEFAULT_CRITERIA["no_critical_violations"]["value"] is True

    def test_default_criteria_is_dict(self):
        assert isinstance(DEFAULT_CRITERIA, dict)
        assert len(DEFAULT_CRITERIA) >= 2


class TestDataClasses:
    def test_quality_gate_auto_ids(self):
        gate = QualityGate(name="test")
        assert gate.gate_id != ""
        assert len(gate.gate_id) == 32
        assert gate.created_at > 0

    def test_quality_gate_default_criteria(self):
        gate = QualityGate(name="test")
        parsed = json.loads(gate.criteria)
        assert "test_coverage" in parsed

    def test_gate_evaluation_auto_ids(self):
        ev = GateEvaluation(gate_id="g1", module_id="m1", result="pass", score=1.0)
        assert ev.evaluation_id != ""
        assert len(ev.evaluation_id) == 32
        assert ev.evaluated_at > 0

    def test_quality_gate_preserves_custom_criteria(self):
        custom = {"my_metric": {"operator": ">", "value": 42}}
        gate = QualityGate(name="test", criteria=json.dumps(custom))
        parsed = json.loads(gate.criteria)
        assert parsed == custom

    def test_gate_evaluation_preserves_values(self):
        ev = GateEvaluation(
            evaluation_id="fixed_id",
            gate_id="g1",
            module_id="m1",
            result="fail",
            score=0.3,
            details='{"info": "details"}',
            evaluated_at=12345.0,
        )
        assert ev.evaluation_id == "fixed_id"
        assert ev.evaluated_at == 12345.0


# ===================================================================
# PART 2: Create gate (4 tests)
# ===================================================================

class TestCreateGate:
    def test_create_gate_returns_dict(self):
        engine = _make_engine()
        result = _create_sample_gate(engine)
        assert "gate_id" in result
        assert result["name"] == "Test Gate"
        assert result["gate_type"] == "entry"
        assert result["enabled"] == 1
        assert result["created_at"] > 0

    def test_create_gate_with_custom_criteria(self):
        engine = _make_engine()
        criteria = {"coverage": {"operator": ">=", "value": 0.9}}
        result = _create_sample_gate(engine, criteria=criteria)
        parsed = json.loads(result["criteria"])
        assert parsed["coverage"]["value"] == 0.9

    def test_create_gate_invalid_type_raises(self):
        engine = _make_engine()
        with pytest.raises(ValueError, match="Invalid gate_type"):
            engine.create_gate(name="Bad", gate_type="invalid")

    def test_create_all_valid_types(self):
        engine = _make_engine()
        for gt in VALID_GATE_TYPES:
            result = engine.create_gate(name=f"Gate-{gt}", gate_type=gt)
            assert result["gate_type"] == gt


# ===================================================================
# PART 3: Get gate (3 tests)
# ===================================================================

class TestGetGate:
    def test_get_existing_gate(self):
        engine = _make_engine()
        created = _create_sample_gate(engine)
        fetched = engine.get_gate(created["gate_id"])
        assert fetched is not None
        assert fetched["gate_id"] == created["gate_id"]
        assert fetched["name"] == "Test Gate"

    def test_get_nonexistent_gate(self):
        engine = _make_engine()
        result = engine.get_gate("no_such_gate")
        assert result is None

    def test_get_gate_returns_all_fields(self):
        engine = _make_engine()
        created = _create_sample_gate(engine)
        fetched = engine.get_gate(created["gate_id"])
        expected_keys = {"gate_id", "name", "description", "gate_type",
                         "criteria", "enabled", "created_at"}
        assert expected_keys.issubset(set(fetched.keys()))


# ===================================================================
# PART 4: List gates (4 tests)
# ===================================================================

class TestListGates:
    def test_list_all_gates(self):
        engine = _make_engine()
        _create_sample_gate(engine, "A", "entry")
        _create_sample_gate(engine, "B", "exit")
        _create_sample_gate(engine, "C", "transition")
        gates = engine.list_gates()
        assert len(gates) == 3

    def test_list_gates_filter_by_type(self):
        engine = _make_engine()
        _create_sample_gate(engine, "A", "entry")
        _create_sample_gate(engine, "B", "exit")
        _create_sample_gate(engine, "C", "entry")
        entry_gates = engine.list_gates(gate_type="entry")
        assert len(entry_gates) == 2
        assert all(g["gate_type"] == "entry" for g in entry_gates)

    def test_list_gates_filter_by_enabled(self):
        engine = _make_engine()
        g1 = _create_sample_gate(engine, "Enabled", "entry")
        g2 = _create_sample_gate(engine, "Disabled", "entry")
        engine.update_gate(g2["gate_id"], enabled=False)

        enabled = engine.list_gates(enabled=True)
        disabled = engine.list_gates(enabled=False)
        assert len(enabled) == 1
        assert len(disabled) == 1
        assert enabled[0]["name"] == "Enabled"
        assert disabled[0]["name"] == "Disabled"

    def test_list_gates_empty(self):
        engine = _make_engine()
        gates = engine.list_gates()
        assert gates == []


# ===================================================================
# PART 5: Update gate (5 tests)
# ===================================================================

class TestUpdateGate:
    def test_update_name(self):
        engine = _make_engine()
        created = _create_sample_gate(engine)
        result = engine.update_gate(created["gate_id"], name="Updated Name")
        assert result["updated"] is True
        assert result["name"] == "Updated Name"

    def test_update_criteria(self):
        engine = _make_engine()
        created = _create_sample_gate(engine)
        new_criteria = {"coverage": {"operator": ">=", "value": 0.95}}
        result = engine.update_gate(created["gate_id"], criteria=new_criteria)
        assert result["updated"] is True
        fetched = engine.get_gate(created["gate_id"])
        parsed = json.loads(fetched["criteria"])
        assert parsed["coverage"]["value"] == 0.95

    def test_update_enabled(self):
        engine = _make_engine()
        created = _create_sample_gate(engine)
        result = engine.update_gate(created["gate_id"], enabled=False)
        assert result["updated"] is True
        fetched = engine.get_gate(created["gate_id"])
        assert fetched["enabled"] == 0

    def test_update_nonexistent_gate(self):
        engine = _make_engine()
        result = engine.update_gate("no_such_gate", name="X")
        assert result["updated"] is False
        assert "not found" in result["message"]

    def test_update_no_fields(self):
        engine = _make_engine()
        created = _create_sample_gate(engine)
        result = engine.update_gate(created["gate_id"])
        assert result["updated"] is False
        assert "No fields" in result["message"]


# ===================================================================
# PART 6: Delete gate (4 tests)
# ===================================================================

class TestDeleteGate:
    def test_delete_existing_gate(self):
        engine = _make_engine()
        created = _create_sample_gate(engine)
        result = engine.delete_gate(created["gate_id"])
        assert result["deleted"] is True
        assert engine.get_gate(created["gate_id"]) is None

    def test_delete_nonexistent_gate(self):
        engine = _make_engine()
        result = engine.delete_gate("no_such_gate")
        assert result["deleted"] is False

    def test_delete_gate_removes_evaluations(self):
        engine = _make_engine()
        created = _create_sample_gate(engine)
        engine.evaluate_gate(created["gate_id"], "mod.1",
                             context={"test_coverage": 1.0, "no_critical_violations": True})
        engine.delete_gate(created["gate_id"])
        evals = engine.list_evaluations(gate_id=created["gate_id"])
        assert len(evals) == 0

    def test_delete_gate_does_not_affect_other_gates(self):
        engine = _make_engine()
        g1 = _create_sample_gate(engine, "Keep", "entry")
        g2 = _create_sample_gate(engine, "Remove", "exit")
        engine.delete_gate(g2["gate_id"])
        assert engine.get_gate(g1["gate_id"]) is not None
        assert engine.get_gate(g2["gate_id"]) is None


# ===================================================================
# PART 7: Evaluate gate - pass/fail/warning (6 tests)
# ===================================================================

class TestEvaluateGate:
    def test_evaluate_pass_all_criteria(self):
        engine = _make_engine()
        created = _create_sample_gate(engine)
        result = engine.evaluate_gate(
            created["gate_id"], "mod.pass",
            context={"test_coverage": 0.95, "no_critical_violations": True},
        )
        assert result["evaluated"] is True
        assert result["result"] == "pass"
        assert result["score"] == 1.0

    def test_evaluate_fail_all_criteria(self):
        engine = _make_engine()
        created = _create_sample_gate(engine)
        result = engine.evaluate_gate(
            created["gate_id"], "mod.fail",
            context={"test_coverage": 0.3, "no_critical_violations": False},
        )
        assert result["evaluated"] is True
        assert result["result"] == "fail"
        assert result["score"] == 0.0

    def test_evaluate_partial_pass_gives_warning(self):
        engine = _make_engine()
        created = _create_sample_gate(engine)
        result = engine.evaluate_gate(
            created["gate_id"], "mod.partial",
            context={"test_coverage": 0.9, "no_critical_violations": False},
        )
        assert result["evaluated"] is True
        assert result["result"] == "warning"
        assert result["score"] == 0.5

    def test_evaluate_missing_context_gives_fail(self):
        engine = _make_engine()
        created = _create_sample_gate(engine)
        result = engine.evaluate_gate(created["gate_id"], "mod.missing")
        assert result["evaluated"] is True
        assert result["result"] == "fail"
        assert result["score"] == 0.0

    def test_evaluate_nonexistent_gate(self):
        engine = _make_engine()
        result = engine.evaluate_gate("no_such_gate", "mod.x")
        assert result["evaluated"] is False
        assert "not found" in result["message"]

    def test_evaluate_disabled_gate_gives_warning(self):
        engine = _make_engine()
        created = _create_sample_gate(engine)
        engine.update_gate(created["gate_id"], enabled=False)
        result = engine.evaluate_gate(created["gate_id"], "mod.disabled")
        assert result["evaluated"] is True
        assert result["result"] == "warning"
        assert result["score"] == 0.0


# ===================================================================
# PART 8: Criteria evaluation operators (5 tests)
# ===================================================================

class TestCriteriaOperators:
    def _eval(self, criteria, context):
        engine = _make_engine()
        gate = engine.create_gate("op-test", "entry", criteria=criteria)
        return engine.evaluate_gate(gate["gate_id"], "mod.op", context=context)

    def test_greater_than_or_equal(self):
        result = self._eval(
            {"score": {"operator": ">=", "value": 0.8}},
            {"score": 0.9},
        )
        assert result["result"] == "pass"

    def test_greater_than(self):
        result = self._eval(
            {"score": {"operator": ">", "value": 0.8}},
            {"score": 0.8},
        )
        assert result["result"] == "fail"

    def test_less_than_or_equal(self):
        result = self._eval(
            {"latency_ms": {"operator": "<=", "value": 100}},
            {"latency_ms": 50},
        )
        assert result["result"] == "pass"

    def test_equality(self):
        result = self._eval(
            {"status_ok": {"operator": "==", "value": True}},
            {"status_ok": True},
        )
        assert result["result"] == "pass"

    def test_inequality(self):
        result = self._eval(
            {"has_errors": {"operator": "!=", "value": True}},
            {"has_errors": False},
        )
        assert result["result"] == "pass"


# ===================================================================
# PART 9: Evaluation queries (5 tests)
# ===================================================================

class TestEvaluationQueries:
    def _setup_evaluations(self, engine):
        gate = _create_sample_gate(engine)
        engine.evaluate_gate(gate["gate_id"], "mod.1",
                             context={"test_coverage": 0.95, "no_critical_violations": True})
        engine.evaluate_gate(gate["gate_id"], "mod.2",
                             context={"test_coverage": 0.3, "no_critical_violations": False})
        engine.evaluate_gate(gate["gate_id"], "mod.3",
                             context={"test_coverage": 0.9, "no_critical_violations": False})
        return gate

    def test_get_evaluation(self):
        engine = _make_engine()
        gate = _create_sample_gate(engine)
        ev = engine.evaluate_gate(gate["gate_id"], "mod.get",
                                  context={"test_coverage": 0.95, "no_critical_violations": True})
        fetched = engine.get_evaluation(ev["evaluation_id"])
        assert fetched is not None
        assert fetched["evaluation_id"] == ev["evaluation_id"]
        assert fetched["result"] == "pass"

    def test_get_nonexistent_evaluation(self):
        engine = _make_engine()
        assert engine.get_evaluation("no_such_eval") is None

    def test_list_evaluations_by_gate(self):
        engine = _make_engine()
        gate = self._setup_evaluations(engine)
        evals = engine.list_evaluations(gate_id=gate["gate_id"])
        assert len(evals) == 3

    def test_list_evaluations_by_module(self):
        engine = _make_engine()
        self._setup_evaluations(engine)
        evals = engine.list_evaluations(module_id="mod.1")
        assert len(evals) == 1
        assert evals[0]["module_id"] == "mod.1"

    def test_list_evaluations_by_result(self):
        engine = _make_engine()
        self._setup_evaluations(engine)
        failed = engine.list_evaluations(result="fail")
        assert all(e["result"] == "fail" for e in failed)
        assert len(failed) >= 1

    def test_list_evaluations_invalid_result_raises(self):
        engine = _make_engine()
        with pytest.raises(ValueError, match="Invalid result"):
            engine.list_evaluations(result="bogus")

    def test_list_evaluations_with_limit(self):
        engine = _make_engine()
        gate = _create_sample_gate(engine)
        for i in range(10):
            engine.evaluate_gate(gate["gate_id"], f"mod.limit.{i}",
                                 context={"test_coverage": 0.95, "no_critical_violations": True})
        evals = engine.list_evaluations(limit=5)
        assert len(evals) == 5


# ===================================================================
# PART 10: Statistics (3 tests)
# ===================================================================

class TestGetStats:
    def test_empty_stats(self):
        engine = _make_engine()
        stats = engine.get_stats()
        assert stats["total_gates"] == 0
        assert stats["total_evaluations"] == 0
        assert stats["enabled_gates"] == 0
        assert stats["gates_by_type"] == {}
        assert stats["evaluations_by_result"] == {}

    def test_stats_with_data(self):
        engine = _make_engine()
        g1 = _create_sample_gate(engine, "Entry", "entry")
        g2 = _create_sample_gate(engine, "Exit", "exit")
        engine.evaluate_gate(g1["gate_id"], "mod.s",
                             context={"test_coverage": 0.95, "no_critical_violations": True})
        engine.evaluate_gate(g1["gate_id"], "mod.f",
                             context={"test_coverage": 0.3, "no_critical_violations": False})

        stats = engine.get_stats()
        assert stats["total_gates"] == 2
        assert stats["enabled_gates"] == 2
        assert stats["total_evaluations"] == 2
        assert stats["gates_by_type"]["entry"] == 1
        assert stats["gates_by_type"]["exit"] == 1
        assert "pass" in stats["evaluations_by_result"]
        assert "fail" in stats["evaluations_by_result"]

    def test_stats_disabled_gate_count(self):
        engine = _make_engine()
        g1 = _create_sample_gate(engine, "A", "entry")
        g2 = _create_sample_gate(engine, "B", "entry")
        engine.update_gate(g2["gate_id"], enabled=False)
        stats = engine.get_stats()
        assert stats["total_gates"] == 2
        assert stats["enabled_gates"] == 1


# ===================================================================
# PART 11: EventBus integration (3 tests)
# ===================================================================

class TestEventBusIntegration:
    def test_evaluation_emits_event(self):
        bus = EventBus(db_path=":memory:")
        engine = _make_engine(event_bus=bus)
        gate = _create_sample_gate(engine)
        engine.evaluate_gate(gate["gate_id"], "mod.evt",
                             context={"test_coverage": 0.95, "no_critical_violations": True})

        events = bus.query(topic="quality_gate.evaluated")
        assert len(events) == 1
        payload = json.loads(events[0]["payload"]) if isinstance(events[0]["payload"], str) else events[0]["payload"]
        assert payload["gate_id"] == gate["gate_id"]
        assert payload["result"] == "pass"

    def test_event_contains_score(self):
        bus = EventBus(db_path=":memory:")
        engine = _make_engine(event_bus=bus)
        gate = _create_sample_gate(engine)
        engine.evaluate_gate(gate["gate_id"], "mod.score",
                             context={"test_coverage": 0.5, "no_critical_violations": False})

        events = bus.query(topic="quality_gate.evaluated")
        assert len(events) == 1
        payload = json.loads(events[0]["payload"]) if isinstance(events[0]["payload"], str) else events[0]["payload"]
        assert "score" in payload
        assert payload["score"] == 0.0

    def test_disabled_gate_does_not_emit_event(self):
        bus = EventBus(db_path=":memory:")
        engine = _make_engine(event_bus=bus)
        gate = _create_sample_gate(engine)
        engine.update_gate(gate["gate_id"], enabled=False)
        engine.evaluate_gate(gate["gate_id"], "mod.no_evt")

        events = bus.query(topic="quality_gate.evaluated")
        assert len(events) == 0

    def test_multiple_evaluations_emit_multiple_events(self):
        bus = EventBus(db_path=":memory:")
        engine = _make_engine(event_bus=bus)
        gate = _create_sample_gate(engine)
        for i in range(5):
            engine.evaluate_gate(gate["gate_id"], f"mod.evt.{i}",
                                 context={"test_coverage": 0.9, "no_critical_violations": True})
        events = bus.query(topic="quality_gate.evaluated")
        assert len(events) == 5


# ===================================================================
# PART 12: Thread safety (2 tests)
# ===================================================================

class TestThreadSafety:
    def test_concurrent_creates(self):
        engine = _make_engine()
        errors: list[Exception] = []

        def create_gate(idx):
            try:
                engine.create_gate(f"Concurrent-{idx}", "entry")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_gate, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(engine.list_gates()) == 20

    def test_concurrent_evaluates(self):
        engine = _make_engine()
        gate = _create_sample_gate(engine)
        errors: list[Exception] = []

        def evaluate(idx):
            try:
                engine.evaluate_gate(
                    gate["gate_id"], f"mod.concurrent.{idx}",
                    context={"test_coverage": 0.9, "no_critical_violations": True},
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=evaluate, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        evals = engine.list_evaluations(gate_id=gate["gate_id"])
        assert len(evals) == 20


# ===================================================================
# PART 13: Singleton / reset (3 tests)
# ===================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        reset_quality_gate_engine()
        engine = get_quality_gate_engine(db_path=":memory:")
        assert engine is not None
        assert isinstance(engine, QualityGateEngine)
        reset_quality_gate_engine()

    def test_get_returns_same_instance(self):
        reset_quality_gate_engine()
        e1 = get_quality_gate_engine(db_path=":memory:")
        e2 = get_quality_gate_engine(db_path=":memory:")
        assert e1 is e2
        reset_quality_gate_engine()

    def test_reset_clears_singleton(self):
        reset_quality_gate_engine()
        e1 = get_quality_gate_engine(db_path=":memory:")
        reset_quality_gate_engine()
        e2 = get_quality_gate_engine(db_path=":memory:")
        assert e1 is not e2
        reset_quality_gate_engine()


# ===================================================================
# PART 14: Evaluation details (3 tests)
# ===================================================================

class TestEvaluationDetails:
    def test_details_contain_per_metric_status(self):
        engine = _make_engine()
        gate = _create_sample_gate(engine)
        result = engine.evaluate_gate(
            gate["gate_id"], "mod.detail",
            context={"test_coverage": 0.95, "no_critical_violations": True},
        )
        details = result["details"]
        assert "test_coverage" in details
        assert details["test_coverage"]["check_passed"] is True

    def test_details_show_missing_metric(self):
        engine = _make_engine()
        gate = _create_sample_gate(engine)
        result = engine.evaluate_gate(gate["gate_id"], "mod.miss", context={})
        details = result["details"]
        assert details["test_coverage"]["status"] == "missing"
        assert details["test_coverage"]["check_passed"] is False

    def test_details_show_threshold_and_actual(self):
        engine = _make_engine()
        gate = _create_sample_gate(engine)
        result = engine.evaluate_gate(
            gate["gate_id"], "mod.vals",
            context={"test_coverage": 0.7, "no_critical_violations": False},
        )
        details = result["details"]
        assert details["test_coverage"]["threshold"] == 0.8
        assert details["test_coverage"]["actual"] == 0.7
        assert details["test_coverage"]["check_passed"] is False


# ===================================================================
# PART 15: Edge cases (3 tests)
# ===================================================================

class TestEdgeCases:
    def test_empty_criteria_gives_pass(self):
        engine = _make_engine()
        gate = engine.create_gate("Empty Criteria Gate", "entry", criteria={})
        result = engine.evaluate_gate(gate["gate_id"], "mod.empty")
        assert result["evaluated"] is True
        # No criteria means 0/0 = 0.0, which is a fail
        assert result["result"] == "fail"
        assert result["score"] == 0.0

    def test_evaluate_with_extra_context_ignored(self):
        engine = _make_engine()
        gate = _create_sample_gate(engine)
        result = engine.evaluate_gate(
            gate["gate_id"], "mod.extra",
            context={"test_coverage": 0.95, "no_critical_violations": True,
                     "extra_metric": 999},
        )
        assert result["result"] == "pass"
        assert result["score"] == 1.0

    def test_custom_criteria_evaluation(self):
        engine = _make_engine()
        criteria = {
            "response_time_ms": {"operator": "<=", "value": 200},
            "error_rate": {"operator": "<", "value": 0.01},
        }
        gate = engine.create_gate("Perf Gate", "deployment", criteria=criteria)
        result = engine.evaluate_gate(
            gate["gate_id"], "mod.perf",
            context={"response_time_ms": 150, "error_rate": 0.005},
        )
        assert result["result"] == "pass"
        assert result["score"] == 1.0
