"""
Comprehensive tests for sylion.cognitive.evaluator -- Evaluator

Covers:
  - Criteria CRUD (create, update, delete, list)
  - Evaluation lifecycle (create, score, complete)
  - Weighted scoring computation
  - list_evaluations with filters
  - get_evaluation and get_evaluation_summary
  - EventBus emission (criteria_created, evaluation_created, evaluation_completed)
  - Input validation
  - Edge cases (empty db, unknown IDs)
  - Thread safety
  - Singleton get/reset
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.evaluator import (
    Evaluator,
    get_evaluator,
    reset_evaluator,
    VALID_EVAL_STATUSES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ev():
    return Evaluator()


@pytest.fixture
def ev_with_bus():
    bus = EventBus()
    e = Evaluator(event_bus=bus)
    return e, bus


def _make_criteria(ev, name="Test Criterion", weight=1.0):
    return ev.create_criteria(name, description="A test criterion", weight=weight)


def _make_evaluation(ev, target_id="target1", target_type="idea"):
    c1 = ev.create_criteria("Quality", weight=2.0)
    c2 = ev.create_criteria("Feasibility", weight=1.0)
    return ev.create_evaluation(target_id, target_type, [c1["criteria_id"], c2["criteria_id"]])


# ===========================================================================
# 1. create_criteria()
# ===========================================================================

class TestCreateCriteria:

    def test_returns_criteria_dict(self, ev):
        c = ev.create_criteria("Quality")
        assert "criteria_id" in c
        assert len(c["criteria_id"]) == 32
        assert c["name"] == "Quality"
        assert c["weight"] == 1.0

    def test_with_description(self, ev):
        c = ev.create_criteria("Quality", description="Measures quality")
        assert c["description"] == "Measures quality"

    def test_custom_weight(self, ev):
        c = ev.create_criteria("Impact", weight=2.5)
        assert c["weight"] == 2.5

    def test_with_rubric(self, ev):
        rubric = {"5": "Excellent", "1": "Poor"}
        c = ev.create_criteria("Score", rubric=rubric)
        assert c["rubric"] == rubric

    def test_empty_name_raises(self, ev):
        with pytest.raises(ValueError, match="name"):
            ev.create_criteria("")

    def test_negative_weight_raises(self, ev):
        with pytest.raises(ValueError, match="weight"):
            ev.create_criteria("X", weight=-1.0)

    def test_zero_weight_ok(self, ev):
        c = ev.create_criteria("X", weight=0.0)
        assert c["weight"] == 0.0

    def test_auto_timestamp(self, ev):
        before = time.time()
        c = ev.create_criteria("X")
        after = time.time()
        assert before <= c["created_at"] <= after


# ===========================================================================
# 2. update_criteria()
# ===========================================================================

class TestUpdateCriteria:

    def test_update_name(self, ev):
        c = _make_criteria(ev, "Old")
        updated = ev.update_criteria(c["criteria_id"], name="New")
        assert updated["name"] == "New"

    def test_update_weight(self, ev):
        c = _make_criteria(ev)
        updated = ev.update_criteria(c["criteria_id"], weight=3.0)
        assert updated["weight"] == 3.0

    def test_update_description(self, ev):
        c = _make_criteria(ev)
        updated = ev.update_criteria(c["criteria_id"], description="Updated")
        assert updated["description"] == "Updated"

    def test_update_rubric(self, ev):
        c = _make_criteria(ev)
        rubric = {"high": "5", "low": "1"}
        updated = ev.update_criteria(c["criteria_id"], rubric=rubric)
        assert updated["rubric"] == rubric

    def test_nonexistent_returns_none(self, ev):
        assert ev.update_criteria("nonexistent", name="X") is None

    def test_negative_weight_raises(self, ev):
        c = _make_criteria(ev)
        with pytest.raises(ValueError, match="weight"):
            ev.update_criteria(c["criteria_id"], weight=-0.5)

    def test_no_fields_returns_existing(self, ev):
        c = _make_criteria(ev, "Name")
        result = ev.update_criteria(c["criteria_id"])
        assert result["name"] == "Name"


# ===========================================================================
# 3. delete_criteria()
# ===========================================================================

class TestDeleteCriteria:

    def test_delete_existing(self, ev):
        c = _make_criteria(ev)
        assert ev.delete_criteria(c["criteria_id"]) is True

    def test_delete_nonexistent(self, ev):
        assert ev.delete_criteria("nonexistent") is False

    def test_list_after_delete(self, ev):
        c = _make_criteria(ev)
        ev.delete_criteria(c["criteria_id"])
        assert len(ev.list_criteria()) == 0


# ===========================================================================
# 4. list_criteria()
# ===========================================================================

class TestListCriteria:

    def test_empty(self, ev):
        assert ev.list_criteria() == []

    def test_returns_all(self, ev):
        ev.create_criteria("A")
        ev.create_criteria("B")
        assert len(ev.list_criteria()) == 2

    def test_includes_rubric_parsed(self, ev):
        ev.create_criteria("C", rubric={"key": "value"})
        criteria = ev.list_criteria()
        assert criteria[0]["rubric"] == {"key": "value"}


# ===========================================================================
# 5. create_evaluation()
# ===========================================================================

class TestCreateEvaluation:

    def test_returns_evaluation_dict(self, ev):
        e = ev.create_evaluation("target1", "idea")
        assert "evaluation_id" in e
        assert len(e["evaluation_id"]) == 32
        assert e["target_id"] == "target1"
        assert e["target_type"] == "idea"
        assert e["status"] == "pending"

    def test_with_criteria_ids(self, ev):
        c1 = ev.create_criteria("Q")
        c2 = ev.create_criteria("F")
        e = ev.create_evaluation("t1", "idea", [c1["criteria_id"], c2["criteria_id"]])
        assert len(e["results"]) == 2

    def test_without_criteria(self, ev):
        e = ev.create_evaluation("t1", "idea")
        assert e["results"] == []

    def test_auto_timestamp(self, ev):
        before = time.time()
        e = ev.create_evaluation("t1", "idea")
        after = time.time()
        assert before <= e["created_at"] <= after

    def test_completed_at_is_none(self, ev):
        e = ev.create_evaluation("t1", "idea")
        assert e["completed_at"] is None


# ===========================================================================
# 6. score_criterion()
# ===========================================================================

class TestScoreCriterion:

    def test_score_existing(self, ev):
        c = _make_criteria(ev)
        e = ev.create_evaluation("t1", "idea", [c["criteria_id"]])
        result = ev.score_criterion(e["evaluation_id"], c["criteria_id"], 4.5, "Good")
        assert result["score"] == 4.5
        assert result["notes"] == "Good"

    def test_score_updates_status_to_in_progress(self, ev):
        c = _make_criteria(ev)
        e = ev.create_evaluation("t1", "idea", [c["criteria_id"]])
        assert e["status"] == "pending"
        ev.score_criterion(e["evaluation_id"], c["criteria_id"], 3.0)
        fetched = ev.get_evaluation(e["evaluation_id"])
        assert fetched["status"] == "in_progress"

    def test_score_nonexistent_evaluation_returns_none(self, ev):
        c = _make_criteria(ev)
        result = ev.score_criterion("nonexistent", c["criteria_id"], 3.0)
        assert result is None

    def test_negative_score_raises(self, ev):
        c = _make_criteria(ev)
        e = ev.create_evaluation("t1", "idea", [c["criteria_id"]])
        with pytest.raises(ValueError, match="score"):
            ev.score_criterion(e["evaluation_id"], c["criteria_id"], -1.0)

    def test_score_new_criteria_creates_result(self, ev):
        e = ev.create_evaluation("t1", "idea")
        c = _make_criteria(ev)
        result = ev.score_criterion(e["evaluation_id"], c["criteria_id"], 5.0, "Great")
        assert result is not None
        assert result["score"] == 5.0

    def test_re_score_updates(self, ev):
        c = _make_criteria(ev)
        e = ev.create_evaluation("t1", "idea", [c["criteria_id"]])
        ev.score_criterion(e["evaluation_id"], c["criteria_id"], 3.0)
        ev.score_criterion(e["evaluation_id"], c["criteria_id"], 5.0, "Improved")
        fetched = ev.get_evaluation(e["evaluation_id"])
        scores = [r["score"] for r in fetched["results"] if r["criteria_id"] == c["criteria_id"]]
        assert scores[0] == 5.0


# ===========================================================================
# 7. complete_evaluation()
# ===========================================================================

class TestCompleteEvaluation:

    def test_computes_weighted_score(self, ev):
        c1 = ev.create_criteria("Q", weight=2.0)
        c2 = ev.create_criteria("F", weight=1.0)
        e = ev.create_evaluation("t1", "idea", [c1["criteria_id"], c2["criteria_id"]])
        ev.score_criterion(e["evaluation_id"], c1["criteria_id"], 6.0)
        ev.score_criterion(e["evaluation_id"], c2["criteria_id"], 3.0)
        result = ev.complete_evaluation(e["evaluation_id"])
        # (6*2 + 3*1) / (2+1) = 15/3 = 5.0
        assert result["weighted_score"] == 5.0
        assert result["status"] == "completed"

    def test_completed_at_set(self, ev):
        e = _make_evaluation(ev)
        result = ev.complete_evaluation(e["evaluation_id"])
        assert result["completed_at"] is not None

    def test_nonexistent_returns_none(self, ev):
        assert ev.complete_evaluation("nonexistent") is None

    def test_no_scores_zero_division(self, ev):
        e = ev.create_evaluation("t1", "idea")
        result = ev.complete_evaluation(e["evaluation_id"])
        assert result["weighted_score"] == 0.0


# ===========================================================================
# 8. get_evaluation()
# ===========================================================================

class TestGetEvaluation:

    def test_returns_evaluation_with_results(self, ev):
        e = _make_evaluation(ev)
        fetched = ev.get_evaluation(e["evaluation_id"])
        assert fetched is not None
        assert fetched["evaluation_id"] == e["evaluation_id"]
        assert len(fetched["results"]) == 2

    def test_nonexistent_returns_none(self, ev):
        assert ev.get_evaluation("nonexistent") is None


# ===========================================================================
# 9. list_evaluations()
# ===========================================================================

class TestListEvaluations:

    def test_empty(self, ev):
        assert ev.list_evaluations() == []

    def test_returns_all(self, ev):
        ev.create_evaluation("t1", "idea")
        ev.create_evaluation("t2", "plan")
        assert len(ev.list_evaluations()) == 2

    def test_filter_by_target_id(self, ev):
        ev.create_evaluation("t1", "idea")
        ev.create_evaluation("t2", "idea")
        results = ev.list_evaluations(target_id="t1")
        assert len(results) == 1

    def test_filter_by_status(self, ev):
        e = ev.create_evaluation("t1", "idea")
        ev.complete_evaluation(e["evaluation_id"])
        results = ev.list_evaluations(status="completed")
        assert len(results) == 1

    def test_invalid_status_raises(self, ev):
        with pytest.raises(ValueError, match="Invalid status"):
            ev.list_evaluations(status="bogus")

    def test_limit(self, ev):
        for i in range(10):
            ev.create_evaluation(f"t{i}", "idea")
        results = ev.list_evaluations(limit=3)
        assert len(results) == 3


# ===========================================================================
# 10. get_evaluation_summary()
# ===========================================================================

class TestGetEvaluationSummary:

    def test_returns_summary(self, ev):
        c1 = ev.create_criteria("Quality", weight=2.0)
        c2 = ev.create_criteria("Feasibility", weight=1.0)
        e = ev.create_evaluation("t1", "idea", [c1["criteria_id"], c2["criteria_id"]])
        ev.score_criterion(e["evaluation_id"], c1["criteria_id"], 4.0, "Good")
        ev.score_criterion(e["evaluation_id"], c2["criteria_id"], 3.0, "OK")
        ev.complete_evaluation(e["evaluation_id"])

        summary = ev.get_evaluation_summary(e["evaluation_id"])
        assert summary is not None
        assert summary["status"] == "completed"
        assert len(summary["breakdown"]) == 2
        assert summary["breakdown"][0]["name"] == "Quality"
        assert summary["breakdown"][0]["weight"] == 2.0

    def test_nonexistent_returns_none(self, ev):
        assert ev.get_evaluation_summary("nonexistent") is None


# ===========================================================================
# 11. Event emission
# ===========================================================================

class TestEventEmission:

    def test_create_criteria_emits(self, ev_with_bus):
        e, bus = ev_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("criteria_created", lambda ev: events.append(ev))
        e.create_criteria("Test")
        assert len(events) == 1
        assert events[0].payload["name"] == "Test"

    def test_create_evaluation_emits(self, ev_with_bus):
        e, bus = ev_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("evaluation_created", lambda ev: events.append(ev))
        e.create_evaluation("t1", "idea")
        assert len(events) == 1
        assert events[0].payload["target_id"] == "t1"

    def test_complete_evaluation_emits(self, ev_with_bus):
        e, bus = ev_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("evaluation_completed", lambda ev: events.append(ev))
        ev_id = e.create_evaluation("t1", "idea")
        e.complete_evaluation(ev_id["evaluation_id"])
        assert len(events) == 1
        assert "weighted_score" in events[0].payload

    def test_event_source_module(self, ev_with_bus):
        e, bus = ev_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("criteria_created", lambda ev: events.append(ev))
        e.create_criteria("Test")
        assert events[0].source_module == "cognitive.evaluator"

    def test_no_bus_does_not_raise(self):
        e = Evaluator()
        c = e.create_criteria("Test")
        ev = e.create_evaluation("t1", "idea", [c["criteria_id"]])
        e.score_criterion(ev["evaluation_id"], c["criteria_id"], 5.0)
        e.complete_evaluation(ev["evaluation_id"])


# ===========================================================================
# 12. Thread safety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_creates(self):
        e = Evaluator()
        results: list[dict] = []
        results_lock = threading.Lock()

        def create_eval(idx):
            r = e.create_evaluation(f"t{idx}", "idea")
            with results_lock:
                results.append(r)

        threads = [threading.Thread(target=create_eval, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(results) == 20
        ids = [r["evaluation_id"] for r in results]
        assert len(set(ids)) == 20

    def test_concurrent_scoring(self):
        e = Evaluator()
        c = e.create_criteria("Q")
        ev = e.create_evaluation("t1", "idea", [c["criteria_id"]])
        errors: list[Exception] = []
        errors_lock = threading.Lock()

        def score(idx):
            try:
                e.score_criterion(ev["evaluation_id"], c["criteria_id"], float(idx % 5 + 1))
            except Exception as ex:
                with errors_lock:
                    errors.append(ex)

        threads = [threading.Thread(target=score, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0


# ===========================================================================
# 13. Singleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_same(self):
        reset_evaluator()
        e1 = get_evaluator()
        e2 = get_evaluator()
        assert e1 is e2
        reset_evaluator()

    def test_reset_creates_new(self):
        reset_evaluator()
        e1 = get_evaluator()
        reset_evaluator()
        e2 = get_evaluator()
        assert e1 is not e2
        reset_evaluator()

    def test_singleton_with_custom_params(self):
        reset_evaluator()
        bus = EventBus()
        e = get_evaluator(event_bus=bus)
        assert e is not None
        reset_evaluator()


# ===========================================================================
# 14. Status validation
# ===========================================================================

class TestStatusValidation:

    def test_all_valid_eval_statuses(self):
        for s in VALID_EVAL_STATUSES:
            assert s in ("pending", "in_progress", "completed")
