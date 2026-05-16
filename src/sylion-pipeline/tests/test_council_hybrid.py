"""
Comprehensive tests for sylion.governance.council_hybrid -- CouncilHybrid class.

Tests: open_session, get_session, list_sessions, close_session,
       add_analysis, get_analyses, add_discussion_round, get_discussion,
       set_consolidated, get_consolidated, get_session_summary,
       rate_analysis, get_model_stats, events, thread safety, edge cases.
"""
from __future__ import annotations

import json
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.council_hybrid import (
    CouncilHybrid,
    DEFAULT_ROLE_WEIGHTS,
    RANK_MULTIPLIER,
    VALID_RANKS,
    VALID_ROLES,
    compute_role_weight,
    get_council_hybrid,
    reset_council_hybrid,
)


def _parse_event_payload(event_dict: dict) -> dict:
    """Parse the JSON-encoded payload string from a raw EventBus query row."""
    p = event_dict["payload"]
    if isinstance(p, str):
        return json.loads(p)
    return p


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_council_hybrid()
    yield
    reset_council_hybrid()


@pytest.fixture
def council():
    """Fresh CouncilHybrid with in-memory DB."""
    return CouncilHybrid()


@pytest.fixture
def bus():
    """Fresh EventBus with in-memory DB."""
    return EventBus()


@pytest.fixture
def council_with_bus(bus):
    """CouncilHybrid wired to an EventBus for event assertions."""
    return CouncilHybrid(event_bus=bus)


def _open_session(council, topic="Test topic", models=None, **kwargs):
    """Helper to open a session with sensible defaults."""
    return council.open_session(
        topic=topic,
        models=models or ["model-a", "model-b"],
        **kwargs,
    )


# =====================================================================
# TestOpenSession
# =====================================================================

class TestOpenSession:

    def test_returns_session_id(self, council):
        result = _open_session(council)
        assert "session_id" in result
        assert len(result["session_id"]) > 0

    def test_returns_topic(self, council):
        result = _open_session(council, topic="Rust migration")
        assert result["topic"] == "Rust migration"

    def test_returns_models_list(self, council):
        result = _open_session(council, models=["gpt-4", "claude-3"])
        assert result["models"] == ["gpt-4", "claude-3"]

    def test_default_phase_is_parallel_analysis(self, council):
        result = _open_session(council)
        assert result["phase"] == "parallel_analysis"

    def test_default_status_is_open(self, council):
        result = _open_session(council)
        assert result["status"] == "open"

    def test_context_defaults_to_empty(self, council):
        result = _open_session(council)
        assert result["context"] == ""

    def test_context_passed_through(self, council):
        result = _open_session(council, context="Some context")
        assert result["context"] == "Some context"

    def test_moderator_model_defaults_to_empty(self, council):
        result = _open_session(council)
        assert result["moderator_model"] == ""

    def test_moderator_model_passed_through(self, council):
        result = _open_session(council, moderator_model="gpt-4")
        assert result["moderator_model"] == "gpt-4"

    def test_created_at_is_timestamp(self, council):
        before = time.time()
        result = _open_session(council)
        after = time.time()
        assert before <= result["created_at"] <= after

    def test_emits_opened_event(self, council_with_bus, bus):
        _open_session(council_with_bus)
        events = bus.query(topic="council.session.opened")
        assert len(events) == 1
        payload = _parse_event_payload(events[0])
        assert payload["topic"] == "Test topic"


# =====================================================================
# TestGetSession
# =====================================================================

class TestGetSession:

    def test_returns_session_by_id(self, council):
        opened = _open_session(council)
        result = council.get_session(opened["session_id"])
        assert result is not None
        assert result["session_id"] == opened["session_id"]

    def test_returns_none_for_missing(self, council):
        result = council.get_session("nonexistent")
        assert result is None

    def test_models_decoded_as_list(self, council):
        opened = _open_session(council, models=["m1", "m2"])
        result = council.get_session(opened["session_id"])
        assert result["models"] == ["m1", "m2"]

    def test_reflects_phase_changes(self, council):
        opened = _open_session(council)
        sid = opened["session_id"]
        council.add_analysis(sid, "m1", "text", "approve", 0.9, "ok")
        result = council.get_session(sid)
        assert result["phase"] == "verdicts"


# =====================================================================
# TestListSessions
# =====================================================================

class TestListSessions:

    def test_empty_list(self, council):
        result = council.list_sessions()
        assert result == []

    def test_returns_all_sessions(self, council):
        _open_session(council, topic="S1")
        _open_session(council, topic="S2")
        result = council.list_sessions()
        assert len(result) == 2

    def test_filter_by_status_open(self, council):
        s = _open_session(council)
        council.close_session(s["session_id"])
        _open_session(council, topic="Still open")
        result = council.list_sessions(status="open")
        assert len(result) == 1
        assert result[0]["topic"] == "Still open"

    def test_filter_by_status_closed(self, council):
        s = _open_session(council)
        council.close_session(s["session_id"])
        result = council.list_sessions(status="closed")
        assert len(result) == 1

    def test_limit(self, council):
        for i in range(10):
            _open_session(council, topic=f"S{i}")
        result = council.list_sessions(limit=3)
        assert len(result) == 3

    def test_offset(self, council):
        for i in range(5):
            _open_session(council, topic=f"S{i}")
        result = council.list_sessions(offset=3)
        assert len(result) == 2

    def test_limit_and_offset_combined(self, council):
        for i in range(10):
            _open_session(council, topic=f"S{i}")
        result = council.list_sessions(limit=2, offset=4)
        assert len(result) == 2


# =====================================================================
# TestCloseSession
# =====================================================================

class TestCloseSession:

    def test_close_sets_status(self, council):
        s = _open_session(council)
        result = council.close_session(s["session_id"])
        assert result["status"] == "closed"

    def test_close_sets_closed_at(self, council):
        s = _open_session(council)
        result = council.close_session(s["session_id"])
        assert result["closed_at"] is not None
        assert result["closed_at"] > 0

    def test_close_returns_none_for_missing(self, council):
        result = council.close_session("nonexistent")
        assert result is None

    def test_close_sets_phase_to_closed(self, council):
        s = _open_session(council)
        council.close_session(s["session_id"])
        session = council.get_session(s["session_id"])
        assert session["phase"] == "closed"

    def test_close_emits_event(self, council_with_bus, bus):
        s = _open_session(council_with_bus)
        council_with_bus.close_session(s["session_id"])
        events = bus.query(topic="council.session.closed")
        assert len(events) == 1
        payload = _parse_event_payload(events[0])
        assert payload["session_id"] == s["session_id"]


# =====================================================================
# TestAddAnalysis
# =====================================================================

class TestAddAnalysis:

    def test_returns_analysis_id(self, council):
        s = _open_session(council)
        result = council.add_analysis(
            s["session_id"], "model-a", "Good idea", "approve", 0.9, "Solid",
        )
        assert "analysis_id" in result
        assert len(result["analysis_id"]) > 0

    def test_returns_all_fields(self, council):
        s = _open_session(council)
        result = council.add_analysis(
            s["session_id"], "model-a", "Text", "approve", 0.8, "Reason",
        )
        assert result["model_id"] == "model-a"
        assert result["analysis_text"] == "Text"
        assert result["verdict"] == "approve"
        assert result["confidence"] == 0.8
        assert result["rationale"] == "Reason"
        assert result["session_id"] == s["session_id"]

    def test_invalid_verdict_raises(self, council):
        s = _open_session(council)
        with pytest.raises(ValueError, match="Invalid verdict"):
            council.add_analysis(
                s["session_id"], "m1", "text", "maybe", 0.5, "reason",
            )

    def test_missing_session_raises(self, council):
        with pytest.raises(ValueError, match="not found"):
            council.add_analysis(
                "nonexistent", "m1", "text", "approve", 0.5, "reason",
            )

    def test_advances_phase_from_parallel_to_verdicts(self, council):
        s = _open_session(council)
        council.add_analysis(
            s["session_id"], "m1", "text", "approve", 0.5, "ok",
        )
        session = council.get_session(s["session_id"])
        assert session["phase"] == "verdicts"

    def test_does_not_downgrade_phase(self, council):
        s = _open_session(council)
        council.add_analysis(
            s["session_id"], "m1", "text", "approve", 0.5, "ok",
        )
        # Phase is now 'verdicts'. Add another analysis.
        council.add_analysis(
            s["session_id"], "m2", "text", "reject", 0.3, "bad",
        )
        session = council.get_session(s["session_id"])
        assert session["phase"] == "verdicts"

    def test_all_valid_verdicts(self, council):
        s = _open_session(council)
        for i, verdict in enumerate(["approve", "reject", "conditional"]):
            result = council.add_analysis(
                s["session_id"], f"m{i}", "text", verdict, 0.5, "reason",
            )
            assert result["verdict"] == verdict

    def test_emits_analysis_added_event(self, council_with_bus, bus):
        s = _open_session(council_with_bus)
        council_with_bus.add_analysis(
            s["session_id"], "m1", "text", "approve", 0.9, "ok",
        )
        events = bus.query(topic="council.analysis.added")
        assert len(events) == 1
        payload = _parse_event_payload(events[0])
        assert payload["model_id"] == "m1"
        assert payload["verdict"] == "approve"


# =====================================================================
# TestGetAnalyses
# =====================================================================

class TestGetAnalyses:

    def test_empty_before_adding(self, council):
        s = _open_session(council)
        result = council.get_analyses(s["session_id"])
        assert result == []

    def test_returns_added_analyses(self, council):
        s = _open_session(council)
        council.add_analysis(
            s["session_id"], "m1", "text1", "approve", 0.9, "ok",
        )
        council.add_analysis(
            s["session_id"], "m2", "text2", "reject", 0.3, "bad",
        )
        result = council.get_analyses(s["session_id"])
        assert len(result) == 2
        models = {r["model_id"] for r in result}
        assert models == {"m1", "m2"}

    def test_ordered_by_created_at(self, council):
        s = _open_session(council)
        council.add_analysis(
            s["session_id"], "m1", "first", "approve", 0.9, "ok",
        )
        council.add_analysis(
            s["session_id"], "m2", "second", "reject", 0.3, "bad",
        )
        result = council.get_analyses(s["session_id"])
        assert result[0]["analysis_text"] == "first"
        assert result[1]["analysis_text"] == "second"


# =====================================================================
# TestAddDiscussionRound
# =====================================================================

class TestAddDiscussionRound:

    def test_returns_round_id(self, council):
        s = _open_session(council)
        result = council.add_discussion_round(
            s["session_id"], 1, "m1", "I agree",
        )
        assert "round_id" in result
        assert len(result["round_id"]) > 0

    def test_returns_all_fields(self, council):
        s = _open_session(council)
        result = council.add_discussion_round(
            s["session_id"], 2, "m1", "Contribution",
            reaction_to="round-abc",
        )
        assert result["round_number"] == 2
        assert result["model_id"] == "m1"
        assert result["contribution"] == "Contribution"
        assert result["reaction_to"] == "round-abc"

    def test_reaction_to_defaults_to_none(self, council):
        s = _open_session(council)
        result = council.add_discussion_round(
            s["session_id"], 1, "m1", "Hello",
        )
        assert result["reaction_to"] is None

    def test_missing_session_raises(self, council):
        with pytest.raises(ValueError, match="not found"):
            council.add_discussion_round(
                "nonexistent", 1, "m1", "text",
            )

    def test_advances_phase_to_discussion(self, council):
        s = _open_session(council)
        council.add_discussion_round(
            s["session_id"], 1, "m1", "Let's discuss",
        )
        session = council.get_session(s["session_id"])
        assert session["phase"] == "discussion"

    def test_emits_discussion_round_event(self, council_with_bus, bus):
        s = _open_session(council_with_bus)
        council_with_bus.add_discussion_round(
            s["session_id"], 1, "m1", "point",
        )
        events = bus.query(topic="council.discussion.round")
        assert len(events) == 1
        payload = _parse_event_payload(events[0])
        assert payload["round_number"] == 1

    def test_multiple_rounds(self, council):
        s = _open_session(council)
        for r in range(1, 4):
            council.add_discussion_round(
                s["session_id"], r, "m1", f"Round {r}",
            )
        discussion = council.get_discussion(s["session_id"])
        assert len(discussion) == 3


# =====================================================================
# TestGetDiscussion
# =====================================================================

class TestGetDiscussion:

    def test_empty_before_any_rounds(self, council):
        s = _open_session(council)
        result = council.get_discussion(s["session_id"])
        assert result == []

    def test_returns_all_rounds(self, council):
        s = _open_session(council)
        council.add_discussion_round(
            s["session_id"], 1, "m1", "point1",
        )
        council.add_discussion_round(
            s["session_id"], 1, "m2", "point2",
        )
        council.add_discussion_round(
            s["session_id"], 2, "m1", "rebuttal",
        )
        result = council.get_discussion(s["session_id"])
        assert len(result) == 3

    def test_ordered_by_round_then_time(self, council):
        s = _open_session(council)
        council.add_discussion_round(
            s["session_id"], 2, "m1", "round 2",
        )
        council.add_discussion_round(
            s["session_id"], 1, "m1", "round 1",
        )
        result = council.get_discussion(s["session_id"])
        assert result[0]["round_number"] == 1
        assert result[1]["round_number"] == 2


# =====================================================================
# TestSetConsolidated
# =====================================================================

class TestSetConsolidated:

    def test_sets_consolidated_text(self, council):
        s = _open_session(council)
        result = council.set_consolidated(
            s["session_id"], "Final recommendation: proceed", 0.85,
        )
        assert result["consolidated_text"] == "Final recommendation: proceed"

    def test_sets_consensus_level(self, council):
        s = _open_session(council)
        result = council.set_consolidated(
            s["session_id"], "text", 0.75,
        )
        assert result["consensus_level"] == 0.75

    def test_sets_phase_to_consolidated(self, council):
        s = _open_session(council)
        council.set_consolidated(s["session_id"], "text", 0.8)
        session = council.get_session(s["session_id"])
        assert session["phase"] == "consolidated"

    def test_missing_session_raises(self, council):
        with pytest.raises(ValueError, match="not found"):
            council.set_consolidated("nonexistent", "text", 0.5)

    def test_emits_consolidated_event(self, council_with_bus, bus):
        s = _open_session(council_with_bus)
        council_with_bus.set_consolidated(s["session_id"], "done", 0.9)
        events = bus.query(topic="council.session.consolidated")
        assert len(events) == 1
        payload = _parse_event_payload(events[0])
        assert payload["consensus_level"] == 0.9


# =====================================================================
# TestGetConsolidated
# =====================================================================

class TestGetConsolidated:

    def test_returns_none_before_consolidation(self, council):
        s = _open_session(council)
        result = council.get_consolidated(s["session_id"])
        assert result is None

    def test_returns_consolidated_data(self, council):
        s = _open_session(council)
        council.set_consolidated(
            s["session_id"], "Final answer", 0.92,
        )
        result = council.get_consolidated(s["session_id"])
        assert result is not None
        assert result["consolidated_text"] == "Final answer"
        assert result["consensus_level"] == 0.92

    def test_returns_none_for_missing_session(self, council):
        result = council.get_consolidated("nonexistent")
        assert result is None


# =====================================================================
# TestGetSessionSummary
# =====================================================================

class TestGetSessionSummary:

    def test_empty_for_missing(self, council):
        result = council.get_session_summary("nonexistent")
        assert result == {}

    def test_returns_session_with_analyses(self, council):
        s = _open_session(council)
        council.add_analysis(
            s["session_id"], "m1", "Good", "approve", 0.9, "solid",
        )
        summary = council.get_session_summary(s["session_id"])
        assert summary["session_id"] == s["session_id"]
        assert len(summary["analyses"]) == 1

    def test_returns_session_with_discussion(self, council):
        s = _open_session(council)
        council.add_discussion_round(
            s["session_id"], 1, "m1", "point",
        )
        summary = council.get_session_summary(s["session_id"])
        assert len(summary["discussion"]) == 1

    def test_includes_consolidated_when_set(self, council):
        s = _open_session(council)
        council.set_consolidated(s["session_id"], "result", 0.8)
        summary = council.get_session_summary(s["session_id"])
        assert summary["consolidated"] is not None
        assert summary["consolidated"]["consolidated_text"] == "result"

    def test_consolidated_is_none_when_not_set(self, council):
        s = _open_session(council)
        summary = council.get_session_summary(s["session_id"])
        assert summary["consolidated"] is None

    def test_full_summary_all_sections(self, council):
        s = _open_session(council)
        sid = s["session_id"]
        council.add_analysis(sid, "m1", "text", "approve", 0.9, "ok")
        council.add_discussion_round(sid, 1, "m1", "discuss")
        council.set_consolidated(sid, "consensus", 0.95)

        summary = council.get_session_summary(sid)
        assert summary["session_id"] == sid
        assert len(summary["analyses"]) == 1
        assert len(summary["discussion"]) == 1
        assert summary["consolidated"]["consensus_level"] == 0.95


# =====================================================================
# TestRateAnalysis
# =====================================================================

class TestRateAnalysis:

    def test_rate_sets_rating(self, council):
        s = _open_session(council)
        council.add_analysis(
            s["session_id"], "m1", "text", "approve", 0.9, "ok",
        )
        result = council.rate_analysis(s["session_id"], "m1", 4.5)
        assert result["rating"] == 4.5

    def test_rate_missing_raises(self, council):
        s = _open_session(council)
        with pytest.raises(ValueError, match="No analysis found"):
            council.rate_analysis(s["session_id"], "m1", 5.0)

    def test_rate_persists(self, council):
        s = _open_session(council)
        council.add_analysis(
            s["session_id"], "m1", "text", "approve", 0.9, "ok",
        )
        council.rate_analysis(s["session_id"], "m1", 3.7)
        analyses = council.get_analyses(s["session_id"])
        assert analyses[0]["rating"] == 3.7


# =====================================================================
# TestGetModelStats
# =====================================================================

class TestGetModelStats:

    def test_empty_when_no_analyses(self, council):
        stats = council.get_model_stats()
        assert stats == {}

    def test_stats_after_analyses(self, council):
        s1 = _open_session(council, topic="S1")
        s2 = _open_session(council, topic="S2", models=["model-a", "model-c"])

        council.add_analysis(s1["session_id"], "model-a", "t", "approve", 0.9, "ok")
        council.add_analysis(s1["session_id"], "model-b", "t", "reject", 0.3, "bad")
        council.add_analysis(s2["session_id"], "model-a", "t", "conditional", 0.6, "maybe")
        council.add_analysis(s2["session_id"], "model-c", "t", "approve", 0.8, "good")

        stats = council.get_model_stats()
        assert "model-a" in stats
        assert stats["model-a"]["total_analyses"] == 2
        assert stats["model-a"]["approves"] == 1
        assert stats["model-a"]["conditionals"] == 1
        assert stats["model-b"]["total_analyses"] == 1
        assert stats["model-b"]["rejects"] == 1
        assert stats["model-c"]["total_analyses"] == 1

    def test_avg_confidence(self, council):
        s = _open_session(council)
        council.add_analysis(s["session_id"], "m1", "t", "approve", 0.8, "ok")
        council.add_analysis(s["session_id"], "m1", "t", "approve", 0.6, "ok")
        stats = council.get_model_stats()
        assert stats["m1"]["avg_confidence"] == 0.7

    def test_avg_rating(self, council):
        s = _open_session(council)
        council.add_analysis(s["session_id"], "m1", "t", "approve", 0.9, "ok")
        council.rate_analysis(s["session_id"], "m1", 4.0)
        stats = council.get_model_stats()
        assert stats["m1"]["avg_rating"] == 4.0


# =====================================================================
# TestSingleton
# =====================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        c = get_council_hybrid()
        assert isinstance(c, CouncilHybrid)

    def test_idempotent(self):
        c1 = get_council_hybrid()
        c2 = get_council_hybrid()
        assert c1 is c2

    def test_reset_creates_new(self):
        c1 = get_council_hybrid()
        c2 = reset_council_hybrid()
        assert c1 is not c2

    def test_reset_then_get_same(self):
        c = reset_council_hybrid()
        c2 = get_council_hybrid()
        assert c is c2


# =====================================================================
# TestEventEmission
# =====================================================================

class TestEventEmission:

    def test_full_lifecycle_events(self, council_with_bus, bus):
        s = _open_session(council_with_bus)
        sid = s["session_id"]

        council_with_bus.add_analysis(sid, "m1", "t", "approve", 0.9, "ok")
        council_with_bus.add_discussion_round(sid, 1, "m1", "point")
        council_with_bus.set_consolidated(sid, "result", 0.9)
        council_with_bus.close_session(sid)

        opened = bus.query(topic="council.session.opened")
        analysis = bus.query(topic="council.analysis.added")
        discussion = bus.query(topic="council.discussion.round")
        consolidated = bus.query(topic="council.session.consolidated")
        closed = bus.query(topic="council.session.closed")

        assert len(opened) == 1
        assert len(analysis) == 1
        assert len(discussion) == 1
        assert len(consolidated) == 1
        assert len(closed) == 1

    def test_events_have_correct_source(self, council_with_bus, bus):
        _open_session(council_with_bus)
        events = bus.query(topic="council.session.opened")
        assert events[0]["source_module"] == "governance.council_hybrid"

    def test_no_events_without_bus(self, council):
        # Should not crash when no EventBus is set
        s = _open_session(council)
        council.add_analysis(
            s["session_id"], "m1", "t", "approve", 0.9, "ok",
        )
        council.close_session(s["session_id"])


# =====================================================================
# TestThreadSafety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_session_creation(self):
        council = CouncilHybrid()
        results = []
        errors = []

        def create_session(idx):
            try:
                r = council.open_session(
                    topic=f"Concurrent {idx}",
                    models=["m1"],
                )
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_session, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        # All session IDs should be unique
        ids = {r["session_id"] for r in results}
        assert len(ids) == 20

    def test_concurrent_analysis_addition(self):
        council = CouncilHybrid()
        s = council.open_session(topic="Concurrent", models=["m1"])
        sid = s["session_id"]
        errors = []

        def add_analysis(idx):
            try:
                council.add_analysis(
                    sid, f"m{idx}", "text", "approve", 0.5, "ok",
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_analysis, args=(i,))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        analyses = council.get_analyses(sid)
        assert len(analyses) == 10

    def test_concurrent_discussion_rounds(self):
        council = CouncilHybrid()
        s = council.open_session(topic="Concurrent", models=["m1"])
        sid = s["session_id"]
        errors = []

        def add_round(idx):
            try:
                council.add_discussion_round(
                    sid, 1, f"m{idx}", f"Contribution {idx}",
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_round, args=(i,))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        discussion = council.get_discussion(sid)
        assert len(discussion) == 10


# =====================================================================
# TestPhaseTransitions
# =====================================================================

class TestPhaseTransitions:

    def test_initial_phase(self, council):
        s = _open_session(council)
        assert s["phase"] == "parallel_analysis"

    def test_add_analysis_moves_to_verdicts(self, council):
        s = _open_session(council)
        council.add_analysis(
            s["session_id"], "m1", "t", "approve", 0.5, "ok",
        )
        assert council.get_session(s["session_id"])["phase"] == "verdicts"

    def test_add_discussion_moves_to_discussion(self, council):
        s = _open_session(council)
        council.add_discussion_round(
            s["session_id"], 1, "m1", "point",
        )
        assert council.get_session(s["session_id"])["phase"] == "discussion"

    def test_set_consolidated_moves_to_consolidated(self, council):
        s = _open_session(council)
        council.set_consolidated(s["session_id"], "done", 0.9)
        assert council.get_session(s["session_id"])["phase"] == "consolidated"

    def test_close_moves_to_closed(self, council):
        s = _open_session(council)
        council.close_session(s["session_id"])
        assert council.get_session(s["session_id"])["phase"] == "closed"

    def test_full_lifecycle_phases(self, council):
        s = _open_session(council)
        sid = s["session_id"]

        assert council.get_session(sid)["phase"] == "parallel_analysis"

        council.add_analysis(sid, "m1", "t", "approve", 0.9, "ok")
        assert council.get_session(sid)["phase"] == "verdicts"

        council.add_discussion_round(sid, 1, "m1", "discuss")
        assert council.get_session(sid)["phase"] == "discussion"

        council.set_consolidated(sid, "result", 0.95)
        assert council.get_session(sid)["phase"] == "consolidated"

        council.close_session(sid)
        assert council.get_session(sid)["phase"] == "closed"


# =====================================================================
# TestEdgeCases
# =====================================================================

class TestEdgeCases:

    def test_session_with_empty_models_list(self, council):
        result = council.open_session(topic="Empty", models=[])
        assert result["models"] == []

    def test_session_with_many_models(self, council):
        models = [f"model-{i}" for i in range(50)]
        result = council.open_session(topic="Big", models=models)
        assert len(result["models"]) == 50

    def test_confidence_boundary_zero(self, council):
        s = _open_session(council)
        result = council.add_analysis(
            s["session_id"], "m1", "t", "conditional", 0.0, "unsure",
        )
        assert result["confidence"] == 0.0

    def test_confidence_boundary_one(self, council):
        s = _open_session(council)
        result = council.add_analysis(
            s["session_id"], "m1", "t", "approve", 1.0, "certain",
        )
        assert result["confidence"] == 1.0

    def test_multiple_analyses_same_model(self, council):
        s = _open_session(council)
        council.add_analysis(
            s["session_id"], "m1", "first", "approve", 0.9, "ok",
        )
        council.add_analysis(
            s["session_id"], "m1", "second", "reject", 0.3, "changed mind",
        )
        analyses = council.get_analyses(s["session_id"])
        assert len(analyses) == 2

    def test_consolidated_can_be_overwritten(self, council):
        s = _open_session(council)
        council.set_consolidated(s["session_id"], "first", 0.5)
        council.set_consolidated(s["session_id"], "second", 0.9)
        result = council.get_consolidated(s["session_id"])
        assert result["consolidated_text"] == "second"
        assert result["consensus_level"] == 0.9


class TestComputeRoleWeight:
    def test_defaults(self): assert compute_role_weight("x", "y", {}, {}) == 1.0
    @pytest.mark.parametrize("role", VALID_ROLES)
    def test_all_canonical_9_roles(self, role): assert compute_role_weight(role, "primary", DEFAULT_ROLE_WEIGHTS, {"primary": 1.0}) == DEFAULT_ROLE_WEIGHTS[role]
    @pytest.mark.parametrize("rank", VALID_RANKS)
    def test_all_5_ranks(self, rank): assert compute_role_weight("planner", rank, {"planner": 1.0}, RANK_MULTIPLIER) == RANK_MULTIPLIER[rank]
    def test_missing_role_returns_1_0(self): assert compute_role_weight("missing", "primary", {}, {"primary": 1.0}) == 1.0
    def test_missing_rank_returns_1_0(self): assert compute_role_weight("planner", "missing", {"planner": 1.0}, {}) == 1.0


class TestGatedConsolidation:
    def test_sentinel_fail_blocks_consolidation_even_with_critic_signature(self, council):
        session = _open_session(council, models=["critic-model", "cost-model"])
        sid = session["session_id"]
        council.add_participant(sid, "critic-model", "critic", "primary")
        council.add_participant(sid, "cost-model", "cost_sentinel", "support")
        council.add_analysis(sid, "critic-model", "conditional", "conditional", 0.8, "needs guard pass")
        council.add_analysis(sid, "cost-model", "conditional", "conditional", 0.7, "cost guard analysis")
        council.record_critic_signature(sid, "critic-model", "conditional", "critic signed")
        council.record_sentinel_evaluation(
            sid,
            "cost_sentinel",
            "cost-model",
            "fail",
            score=0.98,
            details="budget cap exceeded",
        )

        consensus = council.compute_weighted_consensus(sid)
        assert consensus["sentinel_blocks"] == ["cost_sentinel"]
        with pytest.raises(ValueError, match="sentinel block: cost_sentinel"):
            council.consolidate_with_signatures(sid, "should not consolidate")

    def test_sentinel_pass_allows_consolidation_after_critic_signature(self, council):
        session = _open_session(council, models=["critic-model", "security-model"])
        sid = session["session_id"]
        council.add_participant(sid, "critic-model", "critic", "primary")
        council.add_participant(sid, "security-model", "security_sentinel", "support")
        council.add_analysis(sid, "critic-model", "approve", "approve", 0.9, "ok")
        council.add_analysis(sid, "security-model", "approve", "approve", 0.7, "security guard analysis")
        council.record_critic_signature(sid, "critic-model", "approve", "critic signed")
        council.record_sentinel_evaluation(
            sid,
            "security_sentinel",
            "security-model",
            "pass",
            score=0.05,
            details="no blocking finding",
        )

        result = council.consolidate_with_signatures(sid, "approved with pass sentinel")
        assert result["phase"] == "consolidated"
        assert result["consolidated_text"] == "approved with pass sentinel"

    def test_adversarial_critic_signature_is_required_when_present(self, council):
        session = _open_session(council, models=["critic-model", "adv-model"])
        sid = session["session_id"]
        council.add_participant(sid, "critic-model", "critic", "primary")
        council.add_participant(sid, "adv-model", "adversarial_critic", "primary")
        council.add_analysis(sid, "critic-model", "approve", "approve", 0.9, "critic ok")
        council.add_analysis(sid, "adv-model", "approve", "approve", 0.85, "adversarial ok")
        council.record_critic_signature(sid, "critic-model", "approve", "critic signed")

        consensus = council.compute_weighted_consensus(sid)
        assert consensus["critic_signed"] is False
        assert consensus["required_critic_roles"] == ["adversarial_critic", "critic"]
        assert consensus["critic_signature_roles"] == ["critic"]
        with pytest.raises(ValueError, match="missing critic signature"):
            council.consolidate_with_signatures(sid, "must wait for adversarial critic")

        council.record_critic_signature(sid, "adv-model", "approve", "adversarial critic signed")
        consensus = council.compute_weighted_consensus(sid)
        assert consensus["critic_signed"] is True
        assert consensus["adversarial_critic_signed"] is True
        result = council.consolidate_with_signatures(sid, "both critics signed")
        assert result["phase"] == "consolidated"

    def test_latest_sentinel_verdict_supersedes_previous_fail(self, council):
        session = _open_session(council, models=["critic-model", "cost-model"])
        sid = session["session_id"]
        council.add_participant(sid, "critic-model", "critic", "primary")
        council.add_participant(sid, "cost-model", "cost_sentinel", "support")
        council.add_analysis(sid, "critic-model", "conditional", "conditional", 0.8, "needs guard pass")
        council.add_analysis(sid, "cost-model", "conditional", "conditional", 0.7, "cost guard analysis")
        council.record_critic_signature(sid, "critic-model", "conditional", "critic signed")
        council.record_sentinel_evaluation(sid, "cost_sentinel", "cost-model", "fail", score=0.9)
        time.sleep(0.001)
        council.record_sentinel_evaluation(sid, "cost_sentinel", "cost-model", "pass", score=0.01)

        consensus = council.compute_weighted_consensus(sid)
        assert consensus["sentinel_blocks"] == []
        result = council.consolidate_with_signatures(sid, "resolved after pass")
        assert result["phase"] == "consolidated"

    def test_missing_model_analysis_blocks_consolidation(self, council):
        session = _open_session(council, models=["critic-model", "cost-model"])
        sid = session["session_id"]
        council.add_participant(sid, "critic-model", "critic", "primary")
        council.add_participant(sid, "cost-model", "cost_sentinel", "support")
        council.add_analysis(sid, "critic-model", "approve", "approve", 0.9, "ok")
        council.record_critic_signature(sid, "critic-model", "approve", "critic signed")
        council.record_sentinel_evaluation(sid, "cost_sentinel", "cost-model", "pass", score=0.01)

        with pytest.raises(ValueError, match="model wait barrier: missing analyses for cost-model"):
            council.consolidate_with_signatures(sid, "should wait for cost model")
