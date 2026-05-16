"""
SYLION Cognitive -- Evaluator Tests

Tests for Evaluator: evaluation CRUD, query by target, average scores,
listing, error handling, verdict types, and event emission.
"""

from __future__ import annotations

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.evaluator import Evaluator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def evaluator(bus):
    return Evaluator(event_bus=bus)


# ---------------------------------------------------------------------------
# Evaluation CRUD
# ---------------------------------------------------------------------------

class TestEvaluatorCreate:

    def test_evaluate_returns_dict(self, evaluator):
        result = evaluator.evaluate("plan", "p-001", score=0.92, verdict="pass")
        assert "evaluation_id" in result
        assert result["target_type"] == "plan"
        assert result["target_id"] == "p-001"
        assert result["score"] == 0.92
        assert result["verdict"] == "pass"
        assert result["timestamp"] > 0

    def test_evaluate_with_details(self, evaluator):
        result = evaluator.evaluate(
            "task", "t-001", score=0.75, verdict="conditional",
            details={"reason": "partial coverage", "coverage": 75},
        )
        fetched = evaluator.get_evaluation(result["evaluation_id"])
        assert fetched["details"]["reason"] == "partial coverage"
        assert fetched["details"]["coverage"] == 75

    def test_evaluate_without_details_defaults_empty(self, evaluator):
        result = evaluator.evaluate("plan", "p-002", score=1.0, verdict="pass")
        fetched = evaluator.get_evaluation(result["evaluation_id"])
        assert fetched["details"] == {}

    def test_evaluate_fail_verdict(self, evaluator):
        result = evaluator.evaluate("module", "m-bad", score=0.1, verdict="fail",
                                    details={"error": "crash"})
        assert result["verdict"] == "fail"

    def test_evaluate_emits_event(self, evaluator, bus):
        events = []
        bus.subscribe("evaluation.recorded", lambda e: events.append(e))
        evaluator.evaluate("plan", "p-ev", score=0.8, verdict="pass")
        assert len(events) == 1
        assert events[0].payload["score"] == 0.8
        assert events[0].payload["verdict"] == "pass"

    def test_multiple_evaluations_same_target(self, evaluator):
        evaluator.evaluate("plan", "p-multi", score=0.9, verdict="pass")
        evaluator.evaluate("plan", "p-multi", score=0.7, verdict="conditional")
        evaluator.evaluate("plan", "p-multi", score=0.5, verdict="fail")
        results = evaluator.query_by_target("plan", "p-multi")
        assert len(results) == 3
        # Most recent first
        assert results[0]["verdict"] == "fail"


class TestEvaluatorRead:

    def test_get_evaluation(self, evaluator):
        result = evaluator.evaluate("plan", "p-get", score=0.88, verdict="pass")
        fetched = evaluator.get_evaluation(result["evaluation_id"])
        assert fetched is not None
        assert fetched["target_type"] == "plan"
        assert fetched["target_id"] == "p-get"
        assert fetched["score"] == 0.88

    def test_get_evaluation_not_found(self, evaluator):
        assert evaluator.get_evaluation("nonexistent") is None

    def test_get_evaluation_parses_details_json(self, evaluator):
        evaluator.evaluate("task", "t-json", score=0.6, verdict="conditional",
                           details={"key": "value", "nested": {"a": 1}})
        fetched_list = evaluator.query_by_target("task", "t-json")
        assert fetched_list[0]["details"]["key"] == "value"
        assert fetched_list[0]["details"]["nested"]["a"] == 1


class TestEvaluatorQueryByTarget:

    def test_query_by_target_returns_matching(self, evaluator):
        evaluator.evaluate("plan", "x", score=0.9, verdict="pass")
        evaluator.evaluate("plan", "x", score=0.7, verdict="conditional")
        evaluator.evaluate("plan", "y", score=0.5, verdict="fail")
        results = evaluator.query_by_target("plan", "x")
        assert len(results) == 2
        assert all(r["target_id"] == "x" for r in results)

    def test_query_by_target_empty(self, evaluator):
        results = evaluator.query_by_target("nonexistent", "ghost")
        assert results == []

    def test_query_by_target_ordered_by_timestamp_desc(self, evaluator):
        evaluator.evaluate("plan", "order", score=0.9, verdict="pass")
        evaluator.evaluate("plan", "order", score=0.7, verdict="conditional")
        results = evaluator.query_by_target("plan", "order")
        assert results[0]["score"] == 0.7
        assert results[1]["score"] == 0.9


class TestEvaluatorAverageScore:

    def test_get_average_score(self, evaluator):
        evaluator.evaluate("module", "m-1", score=0.8, verdict="pass")
        evaluator.evaluate("module", "m-2", score=0.6, verdict="conditional")
        result = evaluator.get_average_score("module")
        assert isinstance(result, dict)
        assert result["target_type"] == "module"
        assert result["avg_score"] == pytest.approx(0.7, abs=0.01)
        assert result["count"] == 2

    def test_get_average_score_empty(self, evaluator):
        result = evaluator.get_average_score("nonexistent")
        assert result["avg_score"] == 0.0
        assert result["count"] == 0

    def test_get_average_score_single(self, evaluator):
        evaluator.evaluate("task", "t-1", score=0.95, verdict="pass")
        result = evaluator.get_average_score("task")
        assert result["avg_score"] == pytest.approx(0.95, abs=0.01)
        assert result["count"] == 1

    def test_get_average_score_per_type_isolation(self, evaluator):
        evaluator.evaluate("plan", "p-a", score=1.0, verdict="pass")
        evaluator.evaluate("module", "m-a", score=0.0, verdict="fail")
        plan_avg = evaluator.get_average_score("plan")
        mod_avg = evaluator.get_average_score("module")
        assert plan_avg["avg_score"] == pytest.approx(1.0, abs=0.01)
        assert mod_avg["avg_score"] == pytest.approx(0.0, abs=0.01)


class TestEvaluatorList:

    def test_list_evaluations(self, evaluator):
        evaluator.evaluate("plan", "a", score=1.0, verdict="pass")
        evaluator.evaluate("task", "b", score=0.5, verdict="fail")
        listed = evaluator.list_evaluations()
        assert len(listed) == 2

    def test_list_evaluations_respects_limit(self, evaluator):
        for i in range(20):
            evaluator.evaluate("plan", f"p-{i}", score=0.5, verdict="pass")
        listed = evaluator.list_evaluations(limit=5)
        assert len(listed) == 5

    def test_list_evaluations_ordered_by_timestamp_desc(self, evaluator):
        evaluator.evaluate("plan", "first", score=0.5, verdict="pass")
        evaluator.evaluate("plan", "second", score=0.8, verdict="pass")
        listed = evaluator.list_evaluations()
        assert listed[0]["target_id"] == "second"
        assert listed[1]["target_id"] == "first"

    def test_list_evaluations_empty(self, evaluator):
        assert evaluator.list_evaluations() == []


class TestEvaluatorEdgeCases:

    def test_score_zero(self, evaluator):
        result = evaluator.evaluate("plan", "zero", score=0.0, verdict="fail")
        fetched = evaluator.get_evaluation(result["evaluation_id"])
        assert fetched["score"] == 0.0

    def test_score_negative(self, evaluator):
        result = evaluator.evaluate("plan", "neg", score=-0.5, verdict="fail")
        fetched = evaluator.get_evaluation(result["evaluation_id"])
        assert fetched["score"] == -0.5

    def test_score_above_one(self, evaluator):
        result = evaluator.evaluate("plan", "high", score=1.5, verdict="pass")
        fetched = evaluator.get_evaluation(result["evaluation_id"])
        assert fetched["score"] == 1.5

    def test_large_details_dict(self, evaluator):
        big_details = {f"key_{i}": f"value_{i}" for i in range(100)}
        result = evaluator.evaluate("plan", "big", score=0.9, verdict="pass",
                                    details=big_details)
        fetched = evaluator.get_evaluation(result["evaluation_id"])
        assert len(fetched["details"]) == 100

    def test_special_characters_in_details(self, evaluator):
        result = evaluator.evaluate("plan", "special", score=0.8, verdict="pass",
                                    details={"msg": "unicode: \u2603 \u2764"})
        fetched = evaluator.get_evaluation(result["evaluation_id"])
        assert "\u2603" in fetched["details"]["msg"]
