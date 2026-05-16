"""Tests for aeis.self_evolution module."""

import pytest
from sylion.aeis.self_evolution import SelfEvolution, VALID_EVOLUTION_STATES


@pytest.fixture
def engine():
    return SelfEvolution()


def test_propose(engine):
    result = engine.propose("core.event_bus", "parameter_tune",
                            description="Tune batch size",
                            rationale="Improve throughput")
    assert result["target_module"] == "core.event_bus"
    assert result["mutation_type"] == "parameter_tune"
    assert result["state"] == "PROPOSED"
    assert "proposal_id" in result


def test_get_proposal(engine):
    proposed = engine.propose("core.event_bus", "parameter_tune")
    proposal = engine.get(proposed["proposal_id"])
    assert proposal is not None
    assert proposal["target_module"] == "core.event_bus"
    assert proposal["state"] == "PROPOSED"


def test_get_not_found(engine):
    assert engine.get("nonexistent") is None


def test_transition_valid(engine):
    proposed = engine.propose("core.event_bus", "parameter_tune")
    result = engine.transition(proposed["proposal_id"], "EVALUATING")
    assert result["from_state"] == "PROPOSED"
    assert result["to_state"] == "EVALUATING"

    proposal = engine.get(proposed["proposal_id"])
    assert proposal["state"] == "EVALUATING"


def test_transition_invalid(engine):
    proposed = engine.propose("core.event_bus", "parameter_tune")
    with pytest.raises(ValueError, match="Cannot transition"):
        engine.transition(proposed["proposal_id"], "VERIFIED")


def test_transition_not_found(engine):
    with pytest.raises(ValueError, match="not found"):
        engine.transition("nonexistent", "EVALUATING")


def test_full_lifecycle_approved(engine):
    pid = engine.propose("core.event_bus", "parameter_tune")["proposal_id"]
    engine.transition(pid, "EVALUATING")
    engine.transition(pid, "APPROVED")
    engine.transition(pid, "APPLYING")
    engine.transition(pid, "VERIFIED")

    proposal = engine.get(pid)
    assert proposal["state"] == "VERIFIED"


def test_rejected_lifecycle(engine):
    pid = engine.propose("core.event_bus", "parameter_tune")["proposal_id"]
    engine.transition(pid, "EVALUATING")
    engine.transition(pid, "REJECTED")

    proposal = engine.get(pid)
    assert proposal["state"] == "REJECTED"


def test_rollback_lifecycle(engine):
    pid = engine.propose("core.event_bus", "parameter_tune")["proposal_id"]
    engine.transition(pid, "EVALUATING")
    engine.transition(pid, "APPROVED")
    engine.transition(pid, "APPLYING")
    engine.transition(pid, "ROLLED_BACK")

    # Can re-propose from ROLLED_BACK
    engine.transition(pid, "PROPOSED")
    proposal = engine.get(pid)
    assert proposal["state"] == "PROPOSED"


def test_record_fitness(engine):
    pid = engine.propose("core.event_bus", "parameter_tune")["proposal_id"]
    result = engine.record_fitness(pid, fitness_before=0.7, fitness_after=0.85)
    assert result["delta"] == pytest.approx(0.15, abs=0.01)

    proposal = engine.get(pid)
    assert proposal["fitness_before"] == 0.7
    assert proposal["fitness_after"] == 0.85


def test_record_fitness_not_found(engine):
    with pytest.raises(ValueError, match="not found"):
        engine.record_fitness("nonexistent", 0.5, 0.6)


def test_get_events(engine):
    pid = engine.propose("core.event_bus", "parameter_tune")["proposal_id"]
    engine.transition(pid, "EVALUATING")
    engine.transition(pid, "REJECTED")

    events = engine.get_events(pid)
    assert len(events) == 2
    assert events[0]["from_state"] == "PROPOSED"
    assert events[0]["to_state"] == "EVALUATING"
    assert events[1]["from_state"] == "EVALUATING"
    assert events[1]["to_state"] == "REJECTED"


def test_list_proposals(engine):
    engine.propose("core.event_bus", "parameter_tune")
    engine.propose("core.module_registry", "strategy_change")

    all_proposals = engine.list_proposals()
    assert len(all_proposals) == 2

    filtered = engine.list_proposals(target_module="core.event_bus")
    assert len(filtered) == 1


def test_list_by_state(engine):
    pid = engine.propose("core.event_bus", "parameter_tune")["proposal_id"]
    engine.transition(pid, "EVALUATING")

    evaluating = engine.list_proposals(state="EVALUATING")
    assert len(evaluating) == 1

    proposed = engine.list_proposals(state="PROPOSED")
    assert len(proposed) == 0


def test_stats(engine):
    engine.propose("core.event_bus", "parameter_tune")
    engine.propose("core.module_registry", "strategy_change")
    engine.propose("core.event_bus", "parameter_tune")

    stats = engine.get_stats()
    assert stats["total_proposals"] == 3
    assert stats["by_state"]["PROPOSED"] == 3
    assert stats["by_type"]["parameter_tune"] == 2
    assert stats["by_module"]["core.event_bus"] == 2
