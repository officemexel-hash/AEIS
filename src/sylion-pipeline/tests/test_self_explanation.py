"""Tests for SelfExplanationEngine -- self-explanation generation and validation.

23 tests covering generate, validate, get_explanation, list_explanations,
get_stats, thread safety, singleton, and EventBus integration.
"""

import json
import threading

import pytest

from sylion.aeis.self_explanation import (
    SelfExplanationEngine,
    get_self_explanation_engine,
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
    """Fresh in-memory SelfExplanationEngine with EventBus."""
    return SelfExplanationEngine(event_bus=bus)


@pytest.fixture
def eng_no_bus():
    """Fresh in-memory SelfExplanationEngine without EventBus."""
    return SelfExplanationEngine()


# ===================================================================
# Initialization
# ===================================================================

class TestInit:
    def test_default_memory_db(self, eng_no_bus):
        assert eng_no_bus._db_path == ":memory:"

    def test_custom_db_path(self, tmp_path):
        db = tmp_path / "se.db"
        e = SelfExplanationEngine(db_path=str(db))
        assert e._db_path == str(db)

    def test_tables_created(self, eng_no_bus):
        tables = eng_no_bus._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "explanations" in names
        assert "explanation_validations" in names

    def test_indexes_created(self, eng_no_bus):
        indexes = eng_no_bus._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        names = {r["name"] for r in indexes}
        assert "idx_expl_decision" in names
        assert "idx_expl_validated" in names
        assert "idx_val_expl" in names

    def test_has_lock(self, eng_no_bus):
        assert isinstance(eng_no_bus._lock, type(threading.Lock()))

    def test_wal_mode_for_file_db(self, tmp_path):
        db = tmp_path / "wal_test.db"
        e = SelfExplanationEngine(db_path=str(db))
        mode = e._conn.execute("PRAGMA journal_mode").fetchone()["journal_mode"]
        assert mode == "wal"


# ===================================================================
# Generate
# ===================================================================

class TestGenerate:
    def test_generate_returns_ids(self, eng):
        result = eng.generate("DEC-001", "Why was X chosen?")
        assert result["explanation_id"]
        assert result["decision_id"] == "DEC-001"
        assert result["confidence"] == 0.0

    def test_generate_with_full_params(self, eng):
        result = eng.generate(
            "DEC-002", "Why Y?",
            explanation="Because of performance",
            reasoning_steps=["Step 1", "Step 2"],
            confidence=0.85,
        )
        assert result["confidence"] == 0.85

    def test_generate_stores_in_db(self, eng):
        r = eng.generate(
            "DEC-003", "Why Z?",
            explanation="Reason",
            reasoning_steps=["A", "B"],
            confidence=0.9,
        )
        row = eng._conn.execute(
            "SELECT * FROM explanations WHERE explanation_id = ?",
            (r["explanation_id"],),
        ).fetchone()
        assert row is not None
        assert row["decision_id"] == "DEC-003"
        assert row["question"] == "Why Z?"
        assert row["explanation"] == "Reason"
        assert row["confidence"] == 0.9
        assert row["validated"] == 0

    def test_generate_stores_reasoning_steps_as_json(self, eng):
        r = eng.generate("D1", "Q?", reasoning_steps=["S1", "S2"])
        row = eng._conn.execute(
            "SELECT reasoning_steps FROM explanations WHERE explanation_id = ?",
            (r["explanation_id"],),
        ).fetchone()
        steps = json.loads(row["reasoning_steps"])
        assert steps == ["S1", "S2"]

    def test_generate_default_reasoning_steps_empty(self, eng):
        r = eng.generate("D2", "Q?")
        row = eng._conn.execute(
            "SELECT reasoning_steps FROM explanations WHERE explanation_id = ?",
            (r["explanation_id"],),
        ).fetchone()
        assert json.loads(row["reasoning_steps"]) == []

    def test_generate_emits_event(self, eng, bus):
        eng.generate("DEC-004", "Why?", confidence=0.7)
        events = [e for e in bus._captured
                  if e.topic == "aeis.self_explanation.generated"]
        assert len(events) == 1
        assert events[0].payload["decision_id"] == "DEC-004"
        assert events[0].payload["confidence"] == 0.7


# ===================================================================
# Validate
# ===================================================================

class TestValidate:
    def test_validate_returns_ids(self, eng):
        r = eng.generate("D1", "Q?")
        v = eng.validate(r["explanation_id"], "reviewer_a", "approved")
        assert v["validation_id"]
        assert v["explanation_id"] == r["explanation_id"]
        assert v["verdict"] == "approved"

    def test_validate_marks_explanation_validated(self, eng):
        r = eng.generate("D1", "Q?")
        eng.validate(r["explanation_id"], "rev", "approved")
        row = eng._conn.execute(
            "SELECT validated FROM explanations WHERE explanation_id = ?",
            (r["explanation_id"],),
        ).fetchone()
        assert row["validated"] == 1

    def test_validate_stores_in_db(self, eng):
        r = eng.generate("D1", "Q?")
        eng.validate(r["explanation_id"], "alice", "rejected", feedback="Unclear")
        row = eng._conn.execute(
            "SELECT * FROM explanation_validations WHERE explanation_id = ?",
            (r["explanation_id"],),
        ).fetchone()
        assert row is not None
        assert row["validator"] == "alice"
        assert row["verdict"] == "rejected"
        assert row["feedback"] == "Unclear"

    def test_validate_emits_event(self, eng, bus):
        r = eng.generate("D1", "Q?")
        eng.validate(r["explanation_id"], "bob", "approved")
        events = [e for e in bus._captured
                  if e.topic == "aeis.self_explanation.validated"]
        assert len(events) == 1
        assert events[0].payload["verdict"] == "approved"

    def test_multiple_validations_same_explanation(self, eng):
        r = eng.generate("D1", "Q?")
        eng.validate(r["explanation_id"], "a", "approved")
        eng.validate(r["explanation_id"], "b", "rejected", feedback="Bad")
        rows = eng._conn.execute(
            "SELECT * FROM explanation_validations WHERE explanation_id = ?",
            (r["explanation_id"],),
        ).fetchall()
        assert len(rows) == 2


# ===================================================================
# get_explanation
# ===================================================================

class TestGetExplanation:
    def test_returns_explanation(self, eng):
        r = eng.generate("D1", "Q?", explanation="Reason", confidence=0.9)
        result = eng.get_explanation(r["explanation_id"])
        assert result is not None
        assert result["decision_id"] == "D1"
        assert result["explanation"] == "Reason"
        assert result["confidence"] == 0.9

    def test_not_found_returns_none(self, eng):
        assert eng.get_explanation("nonexistent") is None

    def test_reasoning_steps_parsed(self, eng):
        r = eng.generate("D1", "Q?", reasoning_steps=["S1", "S2"])
        result = eng.get_explanation(r["explanation_id"])
        assert isinstance(result["reasoning_steps"], list)
        assert result["reasoning_steps"] == ["S1", "S2"]


# ===================================================================
# list_explanations
# ===================================================================

class TestListExplanations:
    def test_empty_list(self, eng):
        assert eng.list_explanations() == []

    def test_returns_all_without_filter(self, eng):
        eng.generate("D1", "Q1?")
        eng.generate("D2", "Q2?")
        assert len(eng.list_explanations()) == 2

    def test_filter_by_validated(self, eng):
        r1 = eng.generate("D1", "Q1?")
        eng.generate("D2", "Q2?")
        eng.validate(r1["explanation_id"], "rev", "approved")
        validated = eng.list_explanations(validated=1)
        assert len(validated) == 1
        assert validated[0]["decision_id"] == "D1"

    def test_filter_unvalidated(self, eng):
        r1 = eng.generate("D1", "Q1?")
        eng.generate("D2", "Q2?")
        eng.validate(r1["explanation_id"], "rev", "approved")
        unvalidated = eng.list_explanations(validated=0)
        assert len(unvalidated) == 1
        assert unvalidated[0]["decision_id"] == "D2"

    def test_limit_works(self, eng):
        for i in range(10):
            eng.generate(f"D{i}", f"Q{i}?")
        results = eng.list_explanations(limit=3)
        assert len(results) == 3

    def test_reasoning_steps_parsed_in_list(self, eng):
        eng.generate("D1", "Q?", reasoning_steps=["Step"])
        results = eng.list_explanations()
        assert isinstance(results[0]["reasoning_steps"], list)


# ===================================================================
# get_stats
# ===================================================================

class TestGetStats:
    def test_empty_stats(self, eng):
        stats = eng.get_stats()
        assert stats["total_explanations"] == 0
        assert stats["validated"] == 0
        assert stats["unvalidated"] == 0
        assert stats["avg_confidence"] == 0.0
        assert stats["total_validations"] == 0
        assert stats["by_verdict"] == {}

    def test_stats_after_generate(self, eng):
        eng.generate("D1", "Q?", confidence=0.8)
        eng.generate("D2", "Q?", confidence=0.6)
        stats = eng.get_stats()
        assert stats["total_explanations"] == 2
        assert stats["unvalidated"] == 2
        assert abs(stats["avg_confidence"] - 0.7) < 0.01

    def test_stats_after_validate(self, eng):
        r = eng.generate("D1", "Q?", confidence=0.9)
        eng.validate(r["explanation_id"], "rev", "approved")
        stats = eng.get_stats()
        assert stats["validated"] == 1
        assert stats["unvalidated"] == 0
        assert stats["total_validations"] == 1
        assert stats["by_verdict"]["approved"] == 1

    def test_stats_multiple_verdicts(self, eng):
        r1 = eng.generate("D1", "Q?")
        r2 = eng.generate("D2", "Q?")
        eng.validate(r1["explanation_id"], "a", "approved")
        eng.validate(r2["explanation_id"], "b", "rejected")
        stats = eng.get_stats()
        assert stats["by_verdict"]["approved"] == 1
        assert stats["by_verdict"]["rejected"] == 1


# ===================================================================
# Thread safety
# ===================================================================

class TestThreadSafety:
    def test_concurrent_generates(self, eng):
        errors = []

        def generate(n):
            try:
                eng.generate(f"D{n}", f"Q{n}?")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=generate, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        count = eng._conn.execute("SELECT COUNT(*) as c FROM explanations").fetchone()
        assert count["c"] == 20

    def test_concurrent_generate_and_validate(self, eng):
        ids = [eng.generate(f"D{i}", f"Q{i}?")["explanation_id"] for i in range(10)]
        errors = []

        def validate(eid):
            try:
                eng.validate(eid, "rev", "approved")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=validate, args=(eid,)) for eid in ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        count = eng._conn.execute(
            "SELECT COUNT(*) as c FROM explanation_validations"
        ).fetchone()
        assert count["c"] == 10


# ===================================================================
# Singleton
# ===================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        import sylion.aeis.self_explanation as mod
        mod._engine = None
        e = get_self_explanation_engine()
        assert isinstance(e, SelfExplanationEngine)
        mod._engine = None

    def test_singleton_returns_same_instance(self):
        import sylion.aeis.self_explanation as mod
        mod._engine = None
        e1 = get_self_explanation_engine()
        e2 = get_self_explanation_engine()
        assert e1 is e2
        mod._engine = None


# ===================================================================
# EventBus integration
# ===================================================================

class TestEventBusIntegration:
    def test_no_bus_no_error(self, eng_no_bus):
        r = eng_no_bus.generate("D1", "Q?")
        eng_no_bus.validate(r["explanation_id"], "rev", "approved")
        # No crash = success

    def test_event_source_module(self, eng, bus):
        eng.generate("D1", "Q?")
        events = [e for e in bus._captured
                  if e.topic == "aeis.self_explanation.generated"]
        assert events[0].source_module == "aeis.self_explanation"

    def test_multiple_events_different_topics(self, eng, bus):
        r = eng.generate("D1", "Q?")
        eng.validate(r["explanation_id"], "rev", "approved")
        topics = {e.topic for e in bus._captured}
        assert "aeis.self_explanation.generated" in topics
        assert "aeis.self_explanation.validated" in topics
