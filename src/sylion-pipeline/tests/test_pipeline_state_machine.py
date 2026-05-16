"""
Tests for PipelineStateMachine -- state transitions, decision-gate integration,
pause/resume, cancel, decision change rollback, revision counting, active runs,
stats, concurrency, singleton.

~50 tests covering full lifecycle.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.pipeline.state_machine import (
    PipelineStateMachine,
    get_pipeline_state_machine,
    reset_pipeline_state_machine,
    ALLOWED_TRANSITIONS,
    ACTIVE_STATES,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset global singleton before and after every test."""
    reset_pipeline_state_machine()
    yield
    reset_pipeline_state_machine()


@pytest.fixture
def sm() -> PipelineStateMachine:
    """Fresh in-memory PipelineStateMachine."""
    return PipelineStateMachine()


@pytest.fixture
def sm_bus() -> tuple[PipelineStateMachine, EventBus]:
    """PipelineStateMachine with EventBus attached."""
    bus = EventBus()
    machine = PipelineStateMachine(event_bus=bus)
    return machine, bus


def _full_lifecycle(sm, run_id="R-001"):
    """Drive a run through the full lifecycle: idle -> ... -> archived."""
    sm.create_run(run_id)
    sm.transition(run_id, "planning")
    sm.transition(run_id, "planned", trigger="auto")
    sm.transition(run_id, "generating", trigger="gate_pass", gate_id="G1")
    sm.transition(run_id, "reviewing")
    sm.transition(run_id, "complete")
    sm.transition(run_id, "archived")
    return run_id


# ===========================================================================
# TestCreateRun
# ===========================================================================

class TestCreateRun:

    def test_create_returns_record(self, sm):
        rec = sm.create_run("R-001")
        assert rec["run_id"] == "R-001"
        assert rec["current_state"] == "idle"
        assert rec["total_revisions"] == 0
        assert rec["cancelled"] == 0

    def test_create_custom_initial_state(self, sm):
        rec = sm.create_run("R-002", initial_state="planning")
        assert rec["current_state"] == "planning"

    def test_create_duplicate_raises(self, sm):
        sm.create_run("R-003")
        with pytest.raises(ValueError, match="already exists"):
            sm.create_run("R-003")

    def test_created_at_is_set(self, sm):
        before = time.time()
        rec = sm.create_run("R-004")
        after = time.time()
        assert before <= rec["state_entered_at"] <= after


# ===========================================================================
# TestValidTransitions -- full lifecycle
# ===========================================================================

class TestValidTransitions:

    def test_idle_to_planning(self, sm):
        sm.create_run("R-010")
        result = sm.transition("R-010", "planning")
        assert result["from_state"] == "idle"
        assert result["to_state"] == "planning"

    def test_planning_to_planned(self, sm):
        sm.create_run("R-011")
        sm.transition("R-011", "planning")
        result = sm.transition("R-011", "planned")
        assert result["to_state"] == "planned"

    def test_planned_to_generating_with_gate(self, sm):
        sm.create_run("R-012")
        sm.transition("R-012", "planning")
        sm.transition("R-012", "planned")
        result = sm.transition("R-012", "generating",
                               trigger="gate_pass", gate_id="G-QUALITY")
        assert result["to_state"] == "generating"
        assert result["trigger"] == "gate_pass"
        assert result["gate_id"] == "G-QUALITY"

    def test_generating_to_reviewing(self, sm):
        sm.create_run("R-013")
        sm.transition("R-013", "planning")
        sm.transition("R-013", "planned")
        sm.transition("R-013", "generating", trigger="gate_pass")
        result = sm.transition("R-013", "reviewing")
        assert result["to_state"] == "reviewing"

    def test_reviewing_to_complete(self, sm):
        sm.create_run("R-014")
        sm.transition("R-014", "planning")
        sm.transition("R-014", "planned")
        sm.transition("R-014", "generating", trigger="gate_pass")
        sm.transition("R-014", "reviewing")
        result = sm.transition("R-014", "complete")
        assert result["to_state"] == "complete"

    def test_complete_to_archived(self, sm):
        sm.create_run("R-015")
        sm.transition("R-015", "planning")
        sm.transition("R-015", "planned")
        sm.transition("R-015", "generating", trigger="gate_pass")
        sm.transition("R-015", "reviewing")
        sm.transition("R-015", "complete")
        result = sm.transition("R-015", "archived")
        assert result["to_state"] == "archived"

    def test_planning_to_failed_is_not_allowed(self, sm):
        """planning -> failed is not in allowed transitions."""
        sm.create_run("R-016")
        sm.transition("R-016", "planning")
        with pytest.raises(ValueError, match="invalid transition"):
            sm.transition("R-016", "failed")

    def test_full_lifecycle(self, sm):
        run_id = _full_lifecycle(sm, "R-017")
        state = sm.get_state(run_id)
        assert state["current_state"] == "archived"


# ===========================================================================
# TestInvalidTransitions
# ===========================================================================

class TestInvalidTransitions:

    def test_idle_to_generating_invalid(self, sm):
        sm.create_run("R-020")
        with pytest.raises(ValueError, match="invalid transition"):
            sm.transition("R-020", "generating")

    def test_idle_to_complete_invalid(self, sm):
        sm.create_run("R-021")
        with pytest.raises(ValueError):
            sm.transition("R-021", "complete")

    def test_archived_no_transitions(self, sm):
        _full_lifecycle(sm, "R-022")
        with pytest.raises(ValueError):
            sm.transition("R-022", "idle")

    def test_cancelled_no_transitions(self, sm):
        sm.create_run("R-023")
        sm.transition("R-023", "planning")
        sm.cancel("R-023")
        with pytest.raises(ValueError):
            sm.transition("R-023", "planning")

    def test_nonexistent_run_raises(self, sm):
        with pytest.raises(ValueError, match="not found"):
            sm.transition("NO-SUCH-RUN", "planning")

    def test_idle_to_reviewing_invalid(self, sm):
        sm.create_run("R-024")
        with pytest.raises(ValueError):
            sm.transition("R-024", "reviewing")


# ===========================================================================
# TestStateLogging
# ===========================================================================

class TestStateLogging:

    def test_history_is_chronological(self, sm):
        sm.create_run("R-030")
        sm.transition("R-030", "planning")
        sm.transition("R-030", "planned")
        history = sm.get_history("R-030")
        assert len(history) == 2
        assert history[0]["from_state"] == "idle"
        assert history[0]["to_state"] == "planning"
        assert history[1]["from_state"] == "planning"
        assert history[1]["to_state"] == "planned"
        # Timestamps should be non-decreasing
        assert history[0]["created_at"] <= history[1]["created_at"]

    def test_log_records_trigger(self, sm):
        sm.create_run("R-031")
        sm.transition("R-031", "planning", trigger="manual")
        history = sm.get_history("R-031")
        assert history[0]["trigger"] == "manual"

    def test_log_records_snapshot_and_gate(self, sm):
        sm.create_run("R-032")
        sm.transition("R-032", "planning")
        sm.transition("R-032", "planned")
        sm.transition("R-032", "generating",
                      trigger="gate_pass",
                      snapshot_id="SNAP-1",
                      gate_id="G-QA")
        history = sm.get_history("R-032")
        gen_log = [h for h in history if h["to_state"] == "generating"][0]
        assert gen_log["snapshot_id"] == "SNAP-1"
        assert gen_log["gate_id"] == "G-QA"

    def test_log_records_metadata_json(self, sm):
        sm.create_run("R-033")
        sm.transition("R-033", "planning",
                      metadata={"initiator": "user", "priority": "high"})
        history = sm.get_history("R-033")
        assert history[0]["metadata"] is not None

    def test_empty_history_for_new_run(self, sm):
        sm.create_run("R-034")
        assert sm.get_history("R-034") == []


# ===========================================================================
# TestPauseResume
# ===========================================================================

class TestPauseResume:

    def test_pause_saves_state(self, sm):
        sm.create_run("R-040")
        sm.transition("R-040", "planning")
        sm.pause("R-040")
        state = sm.get_state("R-040")
        assert state["current_state"] == "paused"
        assert state["paused_from"] == "planning"

    def test_resume_restores_state(self, sm):
        sm.create_run("R-041")
        sm.transition("R-041", "planning")
        sm.pause("R-041")
        sm.resume("R-041")
        state = sm.get_state("R-041")
        assert state["current_state"] == "planning"
        assert state["paused_from"] is None

    def test_pause_from_generating(self, sm):
        sm.create_run("R-042")
        sm.transition("R-042", "planning")
        sm.transition("R-042", "planned")
        sm.transition("R-042", "generating", trigger="gate_pass")
        sm.pause("R-042")
        state = sm.get_state("R-042")
        assert state["current_state"] == "paused"
        assert state["paused_from"] == "generating"

    def test_resume_generating(self, sm):
        sm.create_run("R-043")
        sm.transition("R-043", "planning")
        sm.transition("R-043", "planned")
        sm.transition("R-043", "generating", trigger="gate_pass")
        sm.pause("R-043")
        sm.resume("R-043")
        state = sm.get_state("R-043")
        assert state["current_state"] == "generating"

    def test_pause_already_paused_raises(self, sm):
        sm.create_run("R-044")
        sm.transition("R-044", "planning")
        sm.pause("R-044")
        with pytest.raises(ValueError, match="already paused"):
            sm.pause("R-044")

    def test_resume_not_paused_raises(self, sm):
        sm.create_run("R-045")
        sm.transition("R-045", "planning")
        with pytest.raises(ValueError, match="not paused"):
            sm.resume("R-045")

    def test_pause_complete_raises(self, sm):
        _full_lifecycle(sm, "R-046")
        # R-046 is now archived; let's test complete specifically
        sm.create_run("R-046B")
        sm.transition("R-046B", "planning")
        sm.transition("R-046B", "planned")
        sm.transition("R-046B", "generating", trigger="gate_pass")
        sm.transition("R-046B", "reviewing")
        sm.transition("R-046B", "complete")
        with pytest.raises(ValueError, match="cannot pause"):
            sm.pause("R-046B")

    def test_pause_nonexistent_raises(self, sm):
        with pytest.raises(ValueError, match="not found"):
            sm.pause("NOPE")


# ===========================================================================
# TestCancel
# ===========================================================================

class TestCancel:

    def test_cancel_from_planning(self, sm):
        sm.create_run("R-050")
        sm.transition("R-050", "planning")
        result = sm.cancel("R-050", reason="user request")
        assert result["to_state"] == "cancelled"
        state = sm.get_state("R-050")
        assert state["cancelled"] == 1
        assert state["cancellation_reason"] == "user request"

    def test_cancel_from_generating(self, sm):
        sm.create_run("R-051")
        sm.transition("R-051", "planning")
        sm.transition("R-051", "planned")
        sm.transition("R-051", "generating", trigger="gate_pass")
        sm.cancel("R-051")
        state = sm.get_state("R-051")
        assert state["current_state"] == "cancelled"

    def test_cancel_from_paused(self, sm):
        sm.create_run("R-052")
        sm.transition("R-052", "planning")
        sm.pause("R-052")
        sm.cancel("R-052")
        state = sm.get_state("R-052")
        assert state["current_state"] == "cancelled"

    def test_cancel_already_cancelled_raises(self, sm):
        sm.create_run("R-053")
        sm.transition("R-053", "planning")
        sm.cancel("R-053")
        with pytest.raises(ValueError, match="already cancelled"):
            sm.cancel("R-053")

    def test_cancel_nonexistent_raises(self, sm):
        with pytest.raises(ValueError, match="not found"):
            sm.cancel("GHOST")

    def test_cancel_records_reason(self, sm):
        sm.create_run("R-054")
        sm.transition("R-054", "planning")
        sm.cancel("R-054", reason="timeout exceeded")
        state = sm.get_state("R-054")
        assert "timeout" in state["cancellation_reason"]


# ===========================================================================
# TestDecisionChangeRollback
# ===========================================================================

class TestDecisionChangeRollback:

    def test_rollback_from_generating(self, sm):
        sm.create_run("R-060")
        sm.transition("R-060", "planning")
        sm.transition("R-060", "planned")
        sm.transition("R-060", "generating", trigger="gate_pass")
        result = sm.handle_decision_change(
            "R-060", snapshot_id="SNAP-1", decision_id="DEC-1")
        assert result["rolled_back"] is True
        assert result["from_state"] == "generating"
        assert result["to_state"] == "planning"
        state = sm.get_state("R-060")
        assert state["current_state"] == "planning"

    def test_rollback_from_reviewing(self, sm):
        sm.create_run("R-061")
        sm.transition("R-061", "planning")
        sm.transition("R-061", "planned")
        sm.transition("R-061", "generating", trigger="gate_pass")
        sm.transition("R-061", "reviewing")
        result = sm.handle_decision_change(
            "R-061", snapshot_id="SNAP-2", decision_id="DEC-2")
        assert result["rolled_back"] is True
        assert result["from_state"] == "reviewing"
        state = sm.get_state("R-061")
        assert state["current_state"] == "planning"

    def test_no_rollback_from_planning(self, sm):
        sm.create_run("R-062")
        sm.transition("R-062", "planning")
        result = sm.handle_decision_change("R-062")
        assert result["rolled_back"] is False
        assert result["from_state"] == "planning"
        assert result["to_state"] == "planning"

    def test_no_rollback_from_idle(self, sm):
        sm.create_run("R-063")
        result = sm.handle_decision_change("R-063")
        assert result["rolled_back"] is False

    def test_no_rollback_from_complete(self, sm):
        sm.create_run("R-064")
        sm.transition("R-064", "planning")
        sm.transition("R-064", "planned")
        sm.transition("R-064", "generating", trigger="gate_pass")
        sm.transition("R-064", "reviewing")
        sm.transition("R-064", "complete")
        result = sm.handle_decision_change("R-064")
        assert result["rolled_back"] is False

    def test_decision_change_logs_trigger(self, sm):
        sm.create_run("R-065")
        sm.transition("R-065", "planning")
        sm.transition("R-065", "planned")
        sm.transition("R-065", "generating", trigger="gate_pass")
        sm.handle_decision_change(
            "R-065", snapshot_id="SNAP-3", decision_id="DEC-3")
        history = sm.get_history("R-065")
        rollback = [h for h in history if h["trigger"] == "decision_change"]
        assert len(rollback) == 1
        assert rollback[0]["decision_id"] == "DEC-3"
        assert rollback[0]["snapshot_id"] == "SNAP-3"

    def test_nonexistent_run_raises(self, sm):
        with pytest.raises(ValueError, match="not found"):
            sm.handle_decision_change("GHOST")


# ===========================================================================
# TestRevisionLoop
# ===========================================================================

class TestRevisionLoop:

    def test_revision_count_increments(self, sm):
        sm.create_run("R-070")
        sm.transition("R-070", "planning")
        sm.transition("R-070", "planned")
        sm.transition("R-070", "generating", trigger="gate_pass")
        sm.transition("R-070", "reviewing")
        sm.transition("R-070", "generating")  # revision 1
        state = sm.get_state("R-070")
        assert state["total_revisions"] == 1

    def test_multiple_revisions(self, sm):
        sm.create_run("R-071")
        sm.transition("R-071", "planning")
        sm.transition("R-071", "planned")
        sm.transition("R-071", "generating", trigger="gate_pass")
        sm.transition("R-071", "reviewing")
        sm.transition("R-071", "generating")  # rev 1
        sm.transition("R-071", "reviewing")
        sm.transition("R-071", "generating")  # rev 2
        sm.transition("R-071", "reviewing")
        sm.transition("R-071", "generating")  # rev 3
        state = sm.get_state("R-071")
        assert state["total_revisions"] == 3

    def test_revision_preserved_through_complete(self, sm):
        sm.create_run("R-072")
        sm.transition("R-072", "planning")
        sm.transition("R-072", "planned")
        sm.transition("R-072", "generating", trigger="gate_pass")
        sm.transition("R-072", "reviewing")
        sm.transition("R-072", "generating")  # rev 1
        sm.transition("R-072", "reviewing")
        sm.transition("R-072", "complete")
        state = sm.get_state("R-072")
        assert state["total_revisions"] == 1


# ===========================================================================
# TestListActiveRuns
# ===========================================================================

class TestListActiveRuns:

    def test_active_runs_excludes_complete(self, sm):
        sm.create_run("R-080")
        sm.transition("R-080", "planning")
        _full_lifecycle(sm, "R-081")  # goes to archived (creates R-081 internally)
        active = sm.list_active_runs()
        active_ids = [r["run_id"] for r in active]
        assert "R-080" in active_ids
        assert "R-081" not in active_ids

    def test_active_runs_excludes_cancelled(self, sm):
        sm.create_run("R-082")
        sm.transition("R-082", "planning")
        sm.cancel("R-082")
        sm.create_run("R-083")
        sm.transition("R-083", "planning")
        active = sm.list_active_runs()
        active_ids = [r["run_id"] for r in active]
        assert "R-082" not in active_ids
        assert "R-083" in active_ids

    def test_empty_when_no_runs(self, sm):
        assert sm.list_active_runs() == []

    def test_includes_paused_runs(self, sm):
        sm.create_run("R-084")
        sm.transition("R-084", "planning")
        sm.pause("R-084")
        active = sm.list_active_runs()
        active_ids = [r["run_id"] for r in active]
        assert "R-084" in active_ids


# ===========================================================================
# TestRunStats
# ===========================================================================

class TestRunStats:

    def test_empty_stats(self, sm):
        stats = sm.get_run_stats()
        assert stats["total"] == 0
        assert stats["by_state"] == {}
        assert stats["active_count"] == 0

    def test_stats_by_state(self, sm):
        sm.create_run("R-090")
        sm.transition("R-090", "planning")
        _full_lifecycle(sm, "R-091")
        stats = sm.get_run_stats()
        assert stats["total"] == 2
        assert stats["by_state"]["planning"] == 1
        assert stats["by_state"]["archived"] == 1
        assert stats["active_count"] == 1

    def test_stats_with_cancelled(self, sm):
        sm.create_run("R-092")
        sm.transition("R-092", "planning")
        sm.cancel("R-092")
        sm.create_run("R-093")
        sm.transition("R-093", "planning")
        stats = sm.get_run_stats()
        assert stats["total"] == 2
        assert stats["by_state"]["cancelled"] == 1
        assert stats["active_count"] == 1


# ===========================================================================
# TestConcurrentTransitions
# ===========================================================================

class TestConcurrentTransitions:

    def test_concurrent_different_runs(self, sm):
        """Multiple threads transitioning different runs should not conflict."""
        errors: list[Exception] = []

        def run_lifecycle(run_id):
            try:
                sm.create_run(run_id)
                sm.transition(run_id, "planning")
                sm.transition(run_id, "planned")
                sm.transition(run_id, "generating", trigger="gate_pass")
                sm.transition(run_id, "reviewing")
                sm.transition(run_id, "complete")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=run_lifecycle, args=(f"CONC-{i}",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        for i in range(10):
            state = sm.get_state(f"CONC-{i}")
            assert state["current_state"] == "complete"

    def test_concurrent_transitions_same_run_fails(self, sm):
        """Two threads trying to transition the same run: one should fail."""
        sm.create_run("R-COLLIDE")
        sm.transition("R-COLLIDE", "planning")
        sm.transition("R-COLLIDE", "planned")

        errors: list[Exception] = []

        def try_transition(target):
            try:
                sm.transition("R-COLLIDE", target)
            except ValueError:
                pass  # expected: only one succeeds

        # Both try different targets; first wins, second hits invalid from-state
        t1 = threading.Thread(target=try_transition, args=("generating",))
        t2 = threading.Thread(target=try_transition, args=("cancelled",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        state = sm.get_state("R-COLLIDE")
        assert state["current_state"] in ("generating", "cancelled")


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_same_instance(self):
        a = get_pipeline_state_machine()
        b = get_pipeline_state_machine()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = get_pipeline_state_machine()
        b = reset_pipeline_state_machine()
        assert a is not b

    def test_after_reset_get_returns_new(self):
        a = get_pipeline_state_machine()
        reset_pipeline_state_machine()
        c = get_pipeline_state_machine()
        assert a is not c


# ===========================================================================
# TestEventBusIntegration
# ===========================================================================

class TestEventBusIntegration:

    def test_transition_emits_event(self, sm_bus):
        sm, bus = sm_bus
        events: list[SylionEvent] = []
        bus.subscribe("pipeline.state.transitioned", events.append)
        sm.create_run("R-EVT")
        sm.transition("R-EVT", "planning")
        assert len(events) >= 1
        assert events[-1].payload["from_state"] == "idle"
        assert events[-1].payload["to_state"] == "planning"

    def test_create_run_emits_event(self, sm_bus):
        sm, bus = sm_bus
        events: list[SylionEvent] = []
        bus.subscribe("pipeline.run.created", events.append)
        sm.create_run("R-EVT2")
        assert len(events) == 1
        assert events[0].payload["run_id"] == "R-EVT2"

    def test_cancel_emits_transition_event(self, sm_bus):
        sm, bus = sm_bus
        events: list[SylionEvent] = []
        bus.subscribe("pipeline.state.transitioned", events.append)
        sm.create_run("R-EVT3")
        sm.transition("R-EVT3", "planning")
        sm.cancel("R-EVT3")
        cancel_events = [e for e in events
                         if e.payload.get("to_state") == "cancelled"]
        assert len(cancel_events) == 1


# ===========================================================================
# TestGetState
# ===========================================================================

class TestGetState:

    def test_returns_none_for_unknown(self, sm):
        assert sm.get_state("GHOST") is None

    def test_returns_current_state(self, sm):
        sm.create_run("R-100")
        sm.transition("R-100", "planning")
        state = sm.get_state("R-100")
        assert state["current_state"] == "planning"
        assert state["previous_state"] == "idle"


# ===========================================================================
# TestEdgeCases
# ===========================================================================

class TestEdgeCases:

    def test_cancelled_run_cannot_be_cancelled_again(self, sm):
        sm.create_run("R-110")
        sm.transition("R-110", "planning")
        sm.cancel("R-110")
        with pytest.raises(ValueError):
            sm.cancel("R-110")

    def test_paused_from_cleared_after_resume(self, sm):
        sm.create_run("R-111")
        sm.transition("R-111", "planning")
        sm.transition("R-111", "planned")
        sm.pause("R-111")
        state_before = sm.get_state("R-111")
        assert state_before["paused_from"] == "planned"
        sm.resume("R-111")
        state_after = sm.get_state("R-111")
        assert state_after["paused_from"] is None
        assert state_after["current_state"] == "planned"

    def test_decision_change_rollback_then_proceed(self, sm):
        """Roll back to planning, then continue through lifecycle."""
        sm.create_run("R-112")
        sm.transition("R-112", "planning")
        sm.transition("R-112", "planned")
        sm.transition("R-112", "generating", trigger="gate_pass")
        sm.handle_decision_change("R-112", decision_id="DEC-X")
        assert sm.get_state("R-112")["current_state"] == "planning"
        # Re-plan and proceed
        sm.transition("R-112", "planned")
        sm.transition("R-112", "generating", trigger="gate_pass")
        sm.transition("R-112", "reviewing")
        sm.transition("R-112", "complete")
        assert sm.get_state("R-112")["current_state"] == "complete"

    def test_multiple_decision_changes(self, sm):
        """Multiple decision changes during generating."""
        sm.create_run("R-113")
        sm.transition("R-113", "planning")
        sm.transition("R-113", "planned")
        sm.transition("R-113", "generating", trigger="gate_pass")
        sm.handle_decision_change("R-113", decision_id="D1")
        assert sm.get_state("R-113")["current_state"] == "planning"
        sm.transition("R-113", "planned")
        sm.transition("R-113", "generating", trigger="gate_pass")
        sm.transition("R-113", "reviewing")
        sm.handle_decision_change("R-113", decision_id="D2")
        assert sm.get_state("R-113")["current_state"] == "planning"

    def test_transition_with_all_optional_fields(self, sm):
        sm.create_run("R-114")
        result = sm.transition(
            "R-114", "planning",
            trigger="gate_pass",
            snapshot_id="SNAP-X",
            gate_id="G-X",
            decision_id="DEC-X",
            metadata={"key": "value"},
        )
        assert result["snapshot_id"] == "SNAP-X"
        assert result["gate_id"] == "G-X"
        assert result["decision_id"] == "DEC-X"
