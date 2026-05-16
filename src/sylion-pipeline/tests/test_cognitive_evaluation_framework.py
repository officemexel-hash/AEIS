"""
SYLION Cognitive -- Evaluation Framework Tests

Covers:
  - create_evaluation (CRUD, validation, duplicate prevention)
  - record_result (scoring, details, closed-evaluation guard)
  - get_evaluation (full retrieval with criteria)
  - list_evaluations (filtering by model_id and status)
  - compute_score (weighted average, per-criterion breakdown)
  - compare_models (ranking, winner selection)
  - get_stats (aggregation by model, scored vs unscored)
  - close_evaluation (status transition, immutability guard)
  - delete_evaluation (cascade deletion)
  - event emission
  - thread safety
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.evaluation_framework import EvaluationFramework


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def fw(bus):
    """Fresh in-memory EvaluationFramework wired to a test EventBus."""
    return EvaluationFramework(event_bus=bus)


def _make_criteria(names_weights=None):
    """Helper to build criteria dicts."""
    if names_weights is None:
        names_weights = [("accuracy", 0.4), ("speed", 0.3), ("reliability", 0.3)]
    return [{"name": n, "weight": w} for n, w in names_weights]


# ===========================================================================
# 1. create_evaluation
# ===========================================================================

class TestCreateEvaluation:

    def test_create_returns_full_dict(self, fw):
        criteria = _make_criteria()
        result = fw.create_evaluation("eval-1", "gpt-4o", criteria, dataset="mmlu")
        assert result["eval_id"] == "eval-1"
        assert result["model_id"] == "gpt-4o"
        assert result["dataset"] == "mmlu"
        assert result["status"] == "open"
        assert len(result["criteria"]) == 3
        assert result["created_at"] > 0

    def test_create_with_metric(self, fw):
        criteria = [{"name": "f1", "weight": 1.0, "metric": "F1 score"}]
        result = fw.create_evaluation("eval-m", "model-a", criteria)
        assert result["criteria"][0]["metric"] == "F1 score"

    def test_create_emits_event(self, fw, bus):
        events = []
        bus.subscribe("evaluation.created", lambda e: events.append(e))
        fw.create_evaluation("eval-ev", "model-x", _make_criteria())
        assert len(events) == 1
        assert events[0].payload["eval_id"] == "eval-ev"
        assert events[0].payload["criteria_count"] == 3

    def test_create_duplicate_raises(self, fw):
        fw.create_evaluation("dup-1", "model-a", _make_criteria())
        with pytest.raises(ValueError, match="already exists"):
            fw.create_evaluation("dup-1", "model-b", _make_criteria())

    def test_create_empty_eval_id_raises(self, fw):
        with pytest.raises(ValueError, match="eval_id must not be empty"):
            fw.create_evaluation("", "model-a", _make_criteria())

    def test_create_empty_model_id_raises(self, fw):
        with pytest.raises(ValueError, match="model_id must not be empty"):
            fw.create_evaluation("eval-x", "", _make_criteria())

    def test_create_empty_criteria_raises(self, fw):
        with pytest.raises(ValueError, match="criteria must not be empty"):
            fw.create_evaluation("eval-x", "model-a", [])

    def test_create_criterion_missing_name_raises(self, fw):
        with pytest.raises(ValueError, match="must have a 'name'"):
            fw.create_evaluation("eval-x", "model-a", [{"weight": 1.0}])

    def test_create_criterion_missing_weight_raises(self, fw):
        with pytest.raises(ValueError, match="missing 'weight'"):
            fw.create_evaluation("eval-x", "model-a", [{"name": "test"}])

    def test_create_criterion_negative_weight_raises(self, fw):
        with pytest.raises(ValueError, match="weight must be >= 0"):
            fw.create_evaluation("eval-x", "model-a", [{"name": "x", "weight": -0.1}])

    def test_create_multiple_evaluations_independent(self, fw):
        fw.create_evaluation("e1", "m1", _make_criteria())
        fw.create_evaluation("e2", "m2", _make_criteria())
        e1 = fw.get_evaluation("e1")
        e2 = fw.get_evaluation("e2")
        assert e1["model_id"] == "m1"
        assert e2["model_id"] == "m2"


# ===========================================================================
# 2. record_result
# ===========================================================================

class TestRecordResult:

    def test_record_returns_result_dict(self, fw):
        fw.create_evaluation("e-rr", "m-rr", _make_criteria())
        result = fw.record_result("e-rr", "accuracy", 0.92)
        assert result["eval_id"] == "e-rr"
        assert result["criterion"] == "accuracy"
        assert result["score"] == 0.92
        assert result["recorded_at"] > 0

    def test_record_with_string_details(self, fw):
        fw.create_evaluation("e-det", "m-det", _make_criteria())
        fw.record_result("e-det", "accuracy", 0.9, details="passed threshold")
        ev = fw.get_evaluation("e-det")
        acc = [c for c in ev["criteria"] if c["name"] == "accuracy"][0]
        assert acc["details"] == "passed threshold"

    def test_record_with_dict_details(self, fw):
        fw.create_evaluation("e-dict", "m-dict", _make_criteria())
        fw.record_result("e-dict", "speed", 0.8, details={"latency_p50": 120})
        ev = fw.get_evaluation("e-dict")
        sp = [c for c in ev["criteria"] if c["name"] == "speed"][0]
        assert sp["details"]["latency_p50"] == 120

    def test_record_emits_event(self, fw, bus):
        events = []
        bus.subscribe("evaluation.result_recorded", lambda e: events.append(e))
        fw.create_evaluation("e-ev", "m-ev", _make_criteria())
        fw.record_result("e-ev", "accuracy", 0.85)
        assert len(events) == 1
        assert events[0].payload["score"] == 0.85

    def test_record_nonexistent_eval_raises(self, fw):
        with pytest.raises(ValueError, match="not found"):
            fw.record_result("ghost", "accuracy", 0.5)

    def test_record_nonexistent_criterion_raises(self, fw):
        fw.create_evaluation("e-nf", "m-nf", _make_criteria())
        with pytest.raises(ValueError, match="criterion.*not found"):
            fw.record_result("e-nf", "nonexistent_criterion", 0.5)

    def test_record_on_closed_eval_raises(self, fw):
        fw.create_evaluation("e-closed", "m-cl", _make_criteria())
        fw.close_evaluation("e-closed")
        with pytest.raises(ValueError, match="is closed"):
            fw.record_result("e-closed", "accuracy", 0.5)

    def test_record_multiple_criteria(self, fw):
        fw.create_evaluation("e-multi", "m-multi", _make_criteria())
        fw.record_result("e-multi", "accuracy", 0.9)
        fw.record_result("e-multi", "speed", 0.8)
        fw.record_result("e-multi", "reliability", 0.7)
        ev = fw.get_evaluation("e-multi")
        scored = [c for c in ev["criteria"] if "score" in c]
        assert len(scored) == 3


# ===========================================================================
# 3. get_evaluation
# ===========================================================================

class TestGetEvaluation:

    def test_get_returns_none_for_unknown(self, fw):
        assert fw.get_evaluation("ghost") is None

    def test_get_returns_criteria_with_no_scores(self, fw):
        fw.create_evaluation("e-ns", "m-ns", _make_criteria())
        ev = fw.get_evaluation("e-ns")
        for c in ev["criteria"]:
            assert "score" not in c

    def test_get_criteria_include_recorded_at(self, fw):
        fw.create_evaluation("e-ra", "m-ra", _make_criteria())
        fw.record_result("e-ra", "accuracy", 0.95)
        ev = fw.get_evaluation("e-ra")
        acc = [c for c in ev["criteria"] if c["name"] == "accuracy"][0]
        assert acc["recorded_at"] > 0


# ===========================================================================
# 4. list_evaluations
# ===========================================================================

class TestListEvaluations:

    def test_list_all(self, fw):
        fw.create_evaluation("l1", "m1", _make_criteria())
        fw.create_evaluation("l2", "m2", _make_criteria())
        assert len(fw.list_evaluations()) == 2

    def test_list_filter_by_model(self, fw):
        fw.create_evaluation("la", "m-a", _make_criteria())
        fw.create_evaluation("lb", "m-b", _make_criteria())
        results = fw.list_evaluations(model_id="m-a")
        assert len(results) == 1
        assert results[0]["eval_id"] == "la"

    def test_list_filter_by_status(self, fw):
        fw.create_evaluation("lo", "m-o", _make_criteria())
        fw.create_evaluation("lc", "m-c", _make_criteria())
        fw.close_evaluation("lc")
        open_evals = fw.list_evaluations(status="open")
        closed_evals = fw.list_evaluations(status="closed")
        assert len(open_evals) == 1
        assert len(closed_evals) == 1

    def test_list_filter_by_model_and_status(self, fw):
        fw.create_evaluation("lao", "m1", _make_criteria())
        fw.create_evaluation("lac", "m1", _make_criteria())
        fw.create_evaluation("lbo", "m2", _make_criteria())
        fw.close_evaluation("lac")
        results = fw.list_evaluations(model_id="m1", status="open")
        assert len(results) == 1
        assert results[0]["eval_id"] == "lao"

    def test_list_empty(self, fw):
        assert fw.list_evaluations() == []

    def test_list_ordered_by_created_at_desc(self, fw):
        fw.create_evaluation("early", "m1", _make_criteria())
        time.sleep(0.01)
        fw.create_evaluation("late", "m1", _make_criteria())
        results = fw.list_evaluations()
        assert results[0]["eval_id"] == "late"


# ===========================================================================
# 5. compute_score
# ===========================================================================

class TestComputeScore:

    def test_weighted_average(self, fw):
        criteria = [{"name": "a", "weight": 0.5}, {"name": "b", "weight": 0.5}]
        fw.create_evaluation("cs1", "m1", criteria)
        fw.record_result("cs1", "a", 0.8)
        fw.record_result("cs1", "b", 0.6)
        result = fw.compute_score("cs1")
        assert result["weighted_score"] == pytest.approx(0.7, abs=0.001)
        assert result["total_weight"] == pytest.approx(1.0, abs=0.001)
        assert result["scored_criteria"] == 2

    def test_partial_scoring(self, fw):
        criteria = [{"name": "x", "weight": 0.6}, {"name": "y", "weight": 0.4}]
        fw.create_evaluation("cs2", "m2", criteria)
        fw.record_result("cs2", "x", 1.0)
        result = fw.compute_score("cs2")
        # weighted_score = (1.0*0.6) / 1.0 = 0.6
        assert result["weighted_score"] == pytest.approx(0.6, abs=0.001)
        assert result["scored_criteria"] == 1
        assert result["total_criteria"] == 2

    def test_no_scores_recorded(self, fw):
        fw.create_evaluation("cs3", "m3", _make_criteria())
        result = fw.compute_score("cs3")
        assert result["weighted_score"] == 0.0
        assert result["scored_criteria"] == 0

    def test_per_criterion_breakdown(self, fw):
        criteria = [{"name": "p", "weight": 0.7}, {"name": "q", "weight": 0.3}]
        fw.create_evaluation("cs4", "m4", criteria)
        fw.record_result("cs4", "p", 0.9)
        fw.record_result("cs4", "q", 0.5)
        result = fw.compute_score("cs4")
        p_entry = [e for e in result["per_criterion"] if e["name"] == "p"][0]
        q_entry = [e for e in result["per_criterion"] if e["name"] == "q"][0]
        assert p_entry["weighted"] == pytest.approx(0.63, abs=0.001)
        assert q_entry["weighted"] == pytest.approx(0.15, abs=0.001)

    def test_nonexistent_evaluation_raises(self, fw):
        with pytest.raises(ValueError, match="not found"):
            fw.compute_score("ghost")

    def test_unequal_weights(self, fw):
        criteria = [{"name": "heavy", "weight": 0.8}, {"name": "light", "weight": 0.2}]
        fw.create_evaluation("cs5", "m5", criteria)
        fw.record_result("cs5", "heavy", 1.0)
        fw.record_result("cs5", "light", 0.0)
        result = fw.compute_score("cs5")
        assert result["weighted_score"] == pytest.approx(0.8, abs=0.001)


# ===========================================================================
# 6. compare_models
# ===========================================================================

class TestCompareModels:

    def _setup_comparison(self, fw):
        criteria = [{"name": "quality", "weight": 1.0}]
        fw.create_evaluation("cmp-a", "model-a", criteria)
        fw.record_result("cmp-a", "quality", 0.9)
        fw.create_evaluation("cmp-b", "model-b", criteria)
        fw.record_result("cmp-b", "quality", 0.7)
        fw.create_evaluation("cmp-c", "model-c", criteria)
        fw.record_result("cmp-c", "quality", 0.5)

    def test_compare_returns_winner(self, fw):
        self._setup_comparison(fw)
        result = fw.compare_models(["cmp-a", "cmp-b", "cmp-c"])
        assert result["winner"] == "model-a"

    def test_compare_ranking_sorted(self, fw):
        self._setup_comparison(fw)
        result = fw.compare_models(["cmp-a", "cmp-b", "cmp-c"])
        ranking = result["ranking"]
        assert ranking[0]["rank"] == 1
        assert ranking[0]["model_id"] == "model-a"
        assert ranking[2]["rank"] == 3
        assert ranking[2]["model_id"] == "model-c"

    def test_compare_evaluations_included(self, fw):
        self._setup_comparison(fw)
        result = fw.compare_models(["cmp-a", "cmp-b"])
        assert len(result["evaluations"]) == 2

    def test_compare_empty_list_raises(self, fw):
        with pytest.raises(ValueError, match="must not be empty"):
            fw.compare_models([])

    def test_compare_nonexistent_eval_raises(self, fw):
        with pytest.raises(ValueError, match="not found"):
            fw.compare_models(["ghost-id"])

    def test_compare_single_model(self, fw):
        criteria = [{"name": "perf", "weight": 1.0}]
        fw.create_evaluation("cmp-solo", "solo-model", criteria)
        fw.record_result("cmp-solo", "perf", 0.88)
        result = fw.compare_models(["cmp-solo"])
        assert result["winner"] == "solo-model"
        assert len(result["ranking"]) == 1


# ===========================================================================
# 7. get_stats
# ===========================================================================

class TestGetStats:

    def test_stats_empty(self, fw):
        stats = fw.get_stats()
        assert stats["total_evaluations"] == 0
        assert stats["avg_score"] == 0.0
        assert stats["scored_evaluations"] == 0
        assert stats["by_model"] == {}

    def test_stats_with_scored_evaluations(self, fw):
        criteria = [{"name": "quality", "weight": 1.0}]
        fw.create_evaluation("s1", "model-a", criteria)
        fw.record_result("s1", "quality", 0.8)
        fw.create_evaluation("s2", "model-b", criteria)
        fw.record_result("s2", "quality", 0.6)
        stats = fw.get_stats()
        assert stats["total_evaluations"] == 2
        assert stats["scored_evaluations"] == 2
        assert stats["avg_score"] == pytest.approx(0.7, abs=0.01)

    def test_stats_by_model(self, fw):
        criteria = [{"name": "quality", "weight": 1.0}]
        fw.create_evaluation("sa1", "model-x", criteria)
        fw.record_result("sa1", "quality", 0.9)
        fw.create_evaluation("sa2", "model-x", criteria)
        fw.record_result("sa2", "quality", 0.7)
        fw.create_evaluation("sb1", "model-y", criteria)
        fw.record_result("sb1", "quality", 0.5)
        stats = fw.get_stats()
        assert stats["by_model"]["model-x"]["count"] == 2
        assert stats["by_model"]["model-y"]["count"] == 1
        assert stats["by_model"]["model-x"]["avg_score"] == pytest.approx(0.8, abs=0.01)
        assert stats["by_model"]["model-x"]["min_score"] == pytest.approx(0.7, abs=0.01)
        assert stats["by_model"]["model-x"]["max_score"] == pytest.approx(0.9, abs=0.01)

    def test_stats_unscored_not_in_avg(self, fw):
        criteria = [{"name": "quality", "weight": 1.0}]
        fw.create_evaluation("s-sc", "model-u", criteria)
        fw.record_result("s-sc", "quality", 0.9)
        fw.create_evaluation("s-uns", "model-u", [{"name": "quality", "weight": 1.0}])
        # no result recorded for s-uns
        stats = fw.get_stats()
        assert stats["scored_evaluations"] == 1
        assert stats["avg_score"] == pytest.approx(0.9, abs=0.01)


# ===========================================================================
# 8. close_evaluation
# ===========================================================================

class TestCloseEvaluation:

    def test_close_changes_status(self, fw):
        fw.create_evaluation("cl-1", "m-cl", _make_criteria())
        result = fw.close_evaluation("cl-1")
        assert result["status"] == "closed"
        ev = fw.get_evaluation("cl-1")
        assert ev["status"] == "closed"

    def test_close_emits_event(self, fw, bus):
        events = []
        bus.subscribe("evaluation.closed", lambda e: events.append(e))
        fw.create_evaluation("cl-ev", "m-cl", _make_criteria())
        fw.close_evaluation("cl-ev")
        assert len(events) == 1
        assert events[0].payload["eval_id"] == "cl-ev"

    def test_close_nonexistent_raises(self, fw):
        with pytest.raises(ValueError, match="not found or already closed"):
            fw.close_evaluation("ghost")

    def test_close_twice_raises(self, fw):
        fw.create_evaluation("cl-2", "m-cl", _make_criteria())
        fw.close_evaluation("cl-2")
        with pytest.raises(ValueError, match="not found or already closed"):
            fw.close_evaluation("cl-2")


# ===========================================================================
# 9. delete_evaluation
# ===========================================================================

class TestDeleteEvaluation:

    def test_delete_returns_true(self, fw):
        fw.create_evaluation("del-1", "m-del", _make_criteria())
        assert fw.delete_evaluation("del-1") is True
        assert fw.get_evaluation("del-1") is None

    def test_delete_nonexistent_returns_false(self, fw):
        assert fw.delete_evaluation("ghost") is False

    def test_delete_emits_event(self, fw, bus):
        events = []
        bus.subscribe("evaluation.deleted", lambda e: events.append(e))
        fw.create_evaluation("del-ev", "m-del", _make_criteria())
        fw.delete_evaluation("del-ev")
        assert len(events) == 1

    def test_delete_cascades_criteria(self, fw):
        fw.create_evaluation("del-cas", "m-del", _make_criteria())
        fw.record_result("del-cas", "accuracy", 0.9)
        fw.delete_evaluation("del-cas")
        # After deletion, compute_score should raise
        with pytest.raises(ValueError):
            fw.compute_score("del-cas")


# ===========================================================================
# 10. Event emission edge cases
# ===========================================================================

class TestEventEmission:

    def test_no_event_bus_does_not_raise(self):
        fw = EvaluationFramework(event_bus=None)
        fw.create_evaluation("no-bus", "m1", _make_criteria())
        fw.record_result("no-bus", "accuracy", 0.5)
        fw.close_evaluation("no-bus")

    def test_multiple_events_in_sequence(self, fw, bus):
        events = []
        bus.subscribe("evaluation.created", lambda e: events.append(("created", e)))
        bus.subscribe("evaluation.result_recorded", lambda e: events.append(("result", e)))
        bus.subscribe("evaluation.closed", lambda e: events.append(("closed", e)))
        fw.create_evaluation("seq-1", "m-seq", _make_criteria())
        fw.record_result("seq-1", "accuracy", 0.9)
        fw.close_evaluation("seq-1")
        assert len(events) == 3
        assert events[0][0] == "created"
        assert events[1][0] == "result"
        assert events[2][0] == "closed"


# ===========================================================================
# 11. Thread safety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_creates(self):
        fw = EvaluationFramework()
        results = []
        errors = []
        lock = threading.Lock()

        def create_eval(idx):
            try:
                r = fw.create_evaluation(
                    f"t-{idx}", f"model-{idx % 3}",
                    _make_criteria([("quality", 1.0)]),
                )
                with lock:
                    results.append(r)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=create_eval, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        assert len(results) == 20
        assert len(fw.list_evaluations()) == 20

    def test_concurrent_record_results(self):
        fw = EvaluationFramework()
        criteria = [{"name": f"metric-{i}", "weight": 1.0} for i in range(5)]
        fw.create_evaluation("concurrent-rec", "m-cr", criteria)
        errors = []
        lock = threading.Lock()

        def record(idx):
            try:
                fw.record_result("concurrent-rec", f"metric-{idx % 5}", 0.5 + idx * 0.01)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=record, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        ev = fw.get_evaluation("concurrent-rec")
        scored = [c for c in ev["criteria"] if "score" in c]
        assert len(scored) == 5
