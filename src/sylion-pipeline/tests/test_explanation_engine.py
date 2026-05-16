"""Tests for ExplanationEngine -- template-based explanation generation.

35+ tests covering init, templates, generation, recording, accuracy
evaluation, statistics, thread safety, and EventBus integration.
"""

import threading
import time

import pytest

from sylion.aeis.explanation_engine import (
    ExplanationEngine,
    get_explanation_engine,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    """Fresh in-memory EventBus capturing events."""
    eb = EventBus()
    eb._captured: list[SylionEvent] = []
    eb.subscribe("*", lambda e: eb._captured.append(e))
    return eb


@pytest.fixture
def eng(bus):
    """Fresh in-memory ExplanationEngine with EventBus."""
    return ExplanationEngine(event_bus=bus)


@pytest.fixture
def eng_no_bus():
    """Fresh in-memory ExplanationEngine without EventBus."""
    return ExplanationEngine()


@pytest.fixture
def eng_with_templates(eng):
    """Engine with 3 sample templates registered."""
    eng.register_template(
        "tpl_reject", "rejection",
        ["reason", "threshold"],
        "Rejected because {reason} (threshold={threshold}).",
    )
    eng.register_template(
        "tpl_approve", "approval",
        ["approver", "score"],
        "Approved by {approver} with score {score}.",
    )
    eng.register_template(
        "tpl_warn", "warning",
        ["metric", "value"],
        "Warning: {metric} exceeded limit at {value}.",
    )
    return eng


# ===================================================================
# Initialization
# ===================================================================

class TestInit:
    def test_default_memory_db(self, eng_no_bus):
        assert eng_no_bus._db_path == ":memory:"

    def test_custom_db_path(self, tmp_path):
        db = tmp_path / "test.db"
        e = ExplanationEngine(db_path=str(db))
        assert e._db_path == str(db)

    def test_tables_created(self, eng_no_bus):
        tables = eng_no_bus._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'sylion_expl%'"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "sylion_explanation_templates" in names
        assert "sylion_explanations" in names

    def test_indexes_created(self, eng_no_bus):
        indexes = eng_no_bus._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_expl_%'"
        ).fetchall()
        names = {r["name"] for r in indexes}
        assert len(names) >= 3

    def test_wal_mode_for_file_db(self, tmp_path):
        db = tmp_path / "wal_test.db"
        e = ExplanationEngine(db_path=str(db))
        mode = e._conn.execute("PRAGMA journal_mode").fetchone()["journal_mode"]
        assert mode == "wal"

    def test_has_lock(self, eng_no_bus):
        assert isinstance(eng_no_bus._lock, type(threading.Lock()))


# ===================================================================
# register_template
# ===================================================================

class TestRegisterTemplate:
    def test_register_returns_ids(self, eng):
        result = eng.register_template(
            "t1", "cls_a", ["x"], "value={x}")
        assert result["template_id"] == "t1"
        assert result["decision_class"] == "cls_a"

    def test_template_stored(self, eng):
        eng.register_template("t1", "cls_a", ["x", "y"], "x={x} y={y}")
        row = eng._conn.execute(
            "SELECT * FROM sylion_explanation_templates WHERE template_id='t1'"
        ).fetchone()
        assert row is not None
        assert row["decision_class"] == "cls_a"
        import json
        assert json.loads(row["required_fields"]) == ["x", "y"]
        assert row["format_string"] == "x={x} y={y}"

    def test_register_replaces_existing(self, eng):
        eng.register_template("t1", "cls_a", ["x"], "old {x}")
        eng.register_template("t1", "cls_a", ["x", "y"], "new {x} {y}")
        row = eng._conn.execute(
            "SELECT * FROM sylion_explanation_templates WHERE template_id='t1'"
        ).fetchone()
        assert "new" in row["format_string"]

    def test_register_emits_event(self, eng, bus):
        eng.register_template("t1", "cls_a", ["x"], "val={x}")
        events = [e for e in bus._captured
                  if e.topic == "aeis.explanation_engine.template_registered"]
        assert len(events) == 1
        assert events[0].payload["template_id"] == "t1"

    def test_multiple_templates_same_class(self, eng):
        eng.register_template("t1", "cls", ["x"], "first {x}")
        eng.register_template("t2", "cls", ["x"], "second {x}")
        rows = eng._conn.execute(
            "SELECT * FROM sylion_explanation_templates WHERE decision_class='cls'"
        ).fetchall()
        assert len(rows) == 2


# ===================================================================
# generate_explanation
# ===================================================================

class TestGenerateExplanation:
    def test_generate_with_matching_template(self, eng_with_templates):
        result = eng_with_templates.generate_explanation(
            "rejection",
            {"reason": "low score", "threshold": "0.8"},
        )
        assert "low score" in result["explanation_text"]
        assert "0.8" in result["explanation_text"]
        assert result["confidence_score"] == 1.0
        assert result["template_id"] == "tpl_reject"
        assert result["warnings"] == []
        assert result["explanation_id"]

    def test_generate_no_template(self, eng):
        result = eng.generate_explanation("unknown_class", {"x": 1})
        assert "No template" in result["explanation_text"]
        assert result["confidence_score"] == 0.0
        assert "no_template" in result["warnings"]

    def test_generate_missing_fields(self, eng_with_templates):
        result = eng_with_templates.generate_explanation(
            "rejection", {"reason": "low"},
        )
        assert "Missing required context fields" in result["explanation_text"]
        assert result["confidence_score"] == 0.0
        assert "missing_fields" in result["warnings"]

    def test_generate_format_error(self, eng):
        eng.register_template("bad", "bad_cls", ["x"], "{x} {missing_key}")
        result = eng.generate_explanation("bad_cls", {"x": "val"})
        assert "Template formatting error" in result["explanation_text"]
        assert "format_error" in result["warnings"]

    def test_generate_explanation_stored(self, eng_with_templates):
        eng_with_templates.generate_explanation(
            "rejection", {"reason": "test", "threshold": "0.5"},
        )
        rows = eng_with_templates._conn.execute(
            "SELECT * FROM sylion_explanations"
        ).fetchall()
        assert len(rows) == 1

    def test_generate_uses_latest_template_for_class(self, eng):
        eng.register_template("old", "cls", ["x"], "old {x}")
        time.sleep(0.01)
        eng.register_template("new", "cls", ["x"], "new {x}")
        result = eng.generate_explanation("cls", {"x": "val"})
        assert result["explanation_text"] == "new val"
        assert result["template_id"] == "new"

    def test_generate_emits_event(self, eng_with_templates, bus):
        eng_with_templates.generate_explanation(
            "approval", {"approver": "alice", "score": "95"},
        )
        events = [e for e in bus._captured
                  if e.topic == "aeis.explanation_engine.generated"]
        assert len(events) == 1
        assert events[0].payload["confidence_score"] == 1.0

    def test_generate_context_snapshot_stored(self, eng_with_templates):
        eng_with_templates.generate_explanation(
            "rejection",
            {"reason": "test", "threshold": "0.5", "extra": "data"},
        )
        row = eng_with_templates._conn.execute(
            "SELECT * FROM sylion_explanations"
        ).fetchone()
        import json
        ctx = json.loads(row["context_snapshot"])
        assert ctx["extra"] == "data"

    def test_generate_stores_decision_id_from_context(self, eng_with_templates):
        eng_with_templates.generate_explanation(
            "rejection",
            {"reason": "test", "threshold": "0.5", "decision_id": "DEC-001"},
        )
        row = eng_with_templates._conn.execute(
            "SELECT * FROM sylion_explanations"
        ).fetchone()
        assert row["decision_id"] == "DEC-001"


# ===================================================================
# record_explanation
# ===================================================================

class TestRecordExplanation:
    def test_record_returns_ids(self, eng):
        result = eng.record_explanation("D1", "Some explanation", 0.85)
        assert result["explanation_id"]
        assert result["decision_id"] == "D1"
        assert result["confidence_score"] == 0.85

    def test_record_stored_in_db(self, eng):
        eng.record_explanation("D1", "Explained", 0.9, decision_class="cls")
        row = eng._conn.execute(
            "SELECT * FROM sylion_explanations WHERE decision_id='D1'"
        ).fetchone()
        assert row is not None
        assert row["explanation_text"] == "Explained"
        assert row["confidence_score"] == 0.9
        assert row["decision_class"] == "cls"

    def test_record_emits_event(self, eng, bus):
        eng.record_explanation("D1", "Text", 0.5)
        events = [e for e in bus._captured
                  if e.topic == "aeis.explanation_engine.recorded"]
        assert len(events) == 1
        assert events[0].payload["decision_id"] == "D1"

    def test_record_default_class(self, eng):
        eng.record_explanation("D1", "Text", 0.7)
        row = eng._conn.execute(
            "SELECT * FROM sylion_explanations WHERE decision_id='D1'"
        ).fetchone()
        assert row["decision_class"] == ""


# ===================================================================
# evaluate_accuracy
# ===================================================================

class TestEvaluateAccuracy:
    def test_evaluate_updates_rating(self, eng):
        r = eng.record_explanation("D1", "Text", 0.9)
        eng.evaluate_accuracy(r["explanation_id"], 0.85)
        row = eng._conn.execute(
            "SELECT * FROM sylion_explanations WHERE explanation_id=?",
            (r["explanation_id"],),
        ).fetchone()
        assert abs(row["accuracy_rating"] - 0.85) < 1e-6

    def test_evaluate_returns_updated_true(self, eng):
        r = eng.record_explanation("D1", "Text", 0.9)
        result = eng.evaluate_accuracy(r["explanation_id"], 0.7)
        assert result["updated"] is True
        assert result["accuracy_rating"] == 0.7

    def test_evaluate_nonexistent_returns_updated_false(self, eng):
        result = eng.evaluate_accuracy("nonexistent", 0.5)
        assert result["updated"] is False

    def test_evaluate_clamps_to_0_1(self, eng):
        r = eng.record_explanation("D1", "Text", 0.9)
        result = eng.evaluate_accuracy(r["explanation_id"], -0.5)
        assert result["accuracy_rating"] == 0.0

        result = eng.evaluate_accuracy(r["explanation_id"], 1.5)
        assert result["accuracy_rating"] == 1.0

    def test_evaluate_emits_event(self, eng, bus):
        r = eng.record_explanation("D1", "Text", 0.9)
        eng.evaluate_accuracy(r["explanation_id"], 0.8)
        events = [e for e in bus._captured
                  if e.topic == "aeis.explanation_engine.evaluated"]
        assert len(events) == 1
        assert events[0].payload["accuracy_rating"] == 0.8

    def test_evaluate_sets_rated_at(self, eng):
        r = eng.record_explanation("D1", "Text", 0.9)
        before = time.time()
        eng.evaluate_accuracy(r["explanation_id"], 0.75)
        row = eng._conn.execute(
            "SELECT rated_at FROM sylion_explanations WHERE explanation_id=?",
            (r["explanation_id"],),
        ).fetchone()
        assert row["rated_at"] >= before - 1


# ===================================================================
# get_accuracy_stats
# ===================================================================

class TestGetAccuracyStats:
    def test_empty_stats(self, eng):
        stats = eng.get_accuracy_stats()
        assert stats["avg_accuracy"] == 0.0
        assert stats["rated_count"] == 0
        assert stats["by_decision_class"] == {}

    def test_stats_with_ratings(self, eng):
        r1 = eng.record_explanation("D1", "T1", 0.9, decision_class="cls_a")
        r2 = eng.record_explanation("D2", "T2", 0.8, decision_class="cls_a")
        r3 = eng.record_explanation("D3", "T3", 0.7, decision_class="cls_b")
        eng.evaluate_accuracy(r1["explanation_id"], 0.9)
        eng.evaluate_accuracy(r2["explanation_id"], 0.7)
        eng.evaluate_accuracy(r3["explanation_id"], 0.5)

        stats = eng.get_accuracy_stats()
        assert stats["rated_count"] == 3
        assert abs(stats["avg_accuracy"] - (0.9 + 0.7 + 0.5) / 3) < 0.01
        assert "cls_a" in stats["by_decision_class"]
        assert abs(stats["by_decision_class"]["cls_a"]["avg_accuracy"] - 0.8) < 0.01
        assert stats["by_decision_class"]["cls_a"]["rated_count"] == 2
        assert stats["by_decision_class"]["cls_b"]["rated_count"] == 1

    def test_stats_ignores_unrated(self, eng):
        eng.record_explanation("D1", "T1", 0.9)
        r2 = eng.record_explanation("D2", "T2", 0.8)
        eng.evaluate_accuracy(r2["explanation_id"], 0.6)

        stats = eng.get_accuracy_stats()
        assert stats["rated_count"] == 1
        assert stats["avg_accuracy"] == 0.6


# ===================================================================
# list_explanations
# ===================================================================

class TestListExplanations:
    def test_empty_list(self, eng):
        assert eng.list_explanations() == []

    def test_returns_recent(self, eng):
        for i in range(5):
            eng.record_explanation(f"D{i}", f"Text {i}", 0.5 + i * 0.1)
        results = eng.list_explanations(limit=3)
        assert len(results) == 3
        # newest first
        assert results[0]["decision_id"] == "D4"

    def test_default_limit_20(self, eng):
        for i in range(25):
            eng.record_explanation(f"D{i}", f"Text {i}", 0.5)
        results = eng.list_explanations()
        assert len(results) == 20

    def test_context_snapshot_parsed(self, eng_with_templates):
        eng_with_templates.generate_explanation(
            "rejection", {"reason": "test", "threshold": "0.5"},
        )
        results = eng_with_templates.list_explanations()
        assert isinstance(results[0]["context_snapshot"], dict)


# ===================================================================
# get_stats
# ===================================================================

class TestGetStats:
    def test_initial_stats(self, eng):
        stats = eng.get_stats()
        assert stats["total_explanations"] == 0
        assert stats["avg_confidence"] == 0.0
        assert stats["accuracy_rate"] == 0.0
        assert stats["rated_count"] == 0
        assert stats["unrated_count"] == 0

    def test_stats_after_records(self, eng):
        eng.record_explanation("D1", "T1", 0.8)
        eng.record_explanation("D2", "T2", 0.6)
        stats = eng.get_stats()
        assert stats["total_explanations"] == 2
        assert abs(stats["avg_confidence"] - 0.7) < 0.01
        assert stats["unrated_count"] == 2

    def test_stats_with_accuracy(self, eng):
        r = eng.record_explanation("D1", "T1", 0.9)
        eng.evaluate_accuracy(r["explanation_id"], 0.85)
        stats = eng.get_stats()
        assert stats["rated_count"] == 1
        assert stats["unrated_count"] == 0
        assert abs(stats["accuracy_rate"] - 0.85) < 0.01


# ===================================================================
# Thread safety
# ===================================================================

class TestThreadSafety:
    def test_concurrent_register_templates(self, eng):
        errors = []

        def register(n):
            try:
                eng.register_template(f"tpl_{n}", f"cls_{n}", ["x"], f"val_{n} {{x}}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        rows = eng._conn.execute(
            "SELECT * FROM sylion_explanation_templates"
        ).fetchall()
        assert len(rows) == 20

    def test_concurrent_generate_and_evaluate(self, eng):
        eng.register_template("t1", "cls", ["x"], "val={x}")
        errors = []

        def generate(n):
            try:
                eng.generate_explanation("cls", {"x": n})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=generate, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        rows = eng._conn.execute(
            "SELECT * FROM sylion_explanations"
        ).fetchall()
        assert len(rows) == 20

    def test_concurrent_record_and_evaluate(self, eng):
        errors = []
        ids = []

        def record(n):
            try:
                r = eng.record_explanation(f"D{n}", f"Text {n}", 0.5)
                ids.append(r["explanation_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

        def evaluate(eid):
            try:
                eng.evaluate_accuracy(eid, 0.8)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=evaluate, args=(eid,)) for eid in ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ===================================================================
# Singleton
# ===================================================================

class TestSingleton:
    def test_get_explanation_engine_returns_instance(self):
        import sylion.aeis.explanation_engine as mod
        mod._engine = None
        e = get_explanation_engine()
        assert isinstance(e, ExplanationEngine)
        # Cleanup
        mod._engine = None

    def test_singleton_returns_same_instance(self):
        import sylion.aeis.explanation_engine as mod
        mod._engine = None
        e1 = get_explanation_engine()
        e2 = get_explanation_engine()
        assert e1 is e2
        # Cleanup
        mod._engine = None


# ===================================================================
# EventBus integration
# ===================================================================

class TestEventBusIntegration:
    def test_no_bus_no_error(self, eng_no_bus):
        eng_no_bus.register_template("t1", "cls", ["x"], "{x}")
        result = eng_no_bus.generate_explanation("cls", {"x": "val"})
        assert result["confidence_score"] == 1.0

    def test_event_source_module(self, eng, bus):
        eng.record_explanation("D1", "Text", 0.5)
        events = [e for e in bus._captured
                  if e.topic == "aeis.explanation_engine.recorded"]
        assert events[0].source_module == "aeis.explanation_engine"

    def test_multiple_events_different_topics(self, eng, bus):
        eng.register_template("t1", "cls", ["x"], "{x}")
        eng.generate_explanation("cls", {"x": "val"})
        r = eng.record_explanation("D1", "Text", 0.5)
        eng.evaluate_accuracy(r["explanation_id"], 0.9)

        topics = {e.topic for e in bus._captured}
        assert "aeis.explanation_engine.template_registered" in topics
        assert "aeis.explanation_engine.generated" in topics
        assert "aeis.explanation_engine.recorded" in topics
        assert "aeis.explanation_engine.evaluated" in topics
