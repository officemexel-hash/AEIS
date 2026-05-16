"""Tests for persona/simulation action stubs (6 handlers)."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.actions.persona_actions import (
    InjectHumanErrorHandler, RecordComprehensionFindingHandler,
    RegisterHumanScenarioHandler, RegisterPersonaHandler,
    SimulateHumanDecisionHandler, SimulateHumanWorkflowHandler,
)
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import (
    Finding, HumanDecisionTrace, HumanErrorInjection,
    HumanNearMiss, HumanPersona,
)


@pytest.fixture
def store():
    return OntologyStore()


def _persona_payload():
    return {
        "persona_data": {
            "name": "Anna",
            "capability_level": "beginner",
            "expertise_domains": [],
            "error_proneness": 0.4,
            "attention_span_min": 12,
            "trust_in_ai_baseline": 0.6,
            "risk_tolerance": "low",
            "dynamic_state": {"fatigue_level": 0.0},
            "behavior_modifiers": {"decision_latency_multiplier": 2.0},
        }
    }


# -------- register_persona --------

def test_register_persona_creates_record(store):
    h = RegisterPersonaHandler(ontology=store)
    p = _persona_payload()
    h.validate(p)
    result = h.execute(p, intent_id="i")
    assert result["persona_id"].startswith("persona_")
    persisted = store.get(HumanPersona, result["persona_id"])
    assert persisted.name == "Anna"


def test_register_persona_rejects_bad_capability(store):
    h = RegisterPersonaHandler(ontology=store)
    p = _persona_payload()
    p["persona_data"]["capability_level"] = "wizard"
    with pytest.raises(ValueError, match="capability_level"):
        h.validate(p)


def test_register_persona_rejects_missing_field(store):
    h = RegisterPersonaHandler(ontology=store)
    p = _persona_payload()
    del p["persona_data"]["error_proneness"]
    with pytest.raises(ValueError, match="error_proneness"):
        h.validate(p)


# -------- register_human_scenario --------

def test_register_scenario_creates_record(store):
    h = RegisterHumanScenarioHandler(ontology=store)
    p = {
        "scenario_data": {
            "persona_id": "persona_beginner",
            "domain": "hmep",
            "workflow_steps": [{"step": "intake"}],
            "decision_points": [{"d": "approve_charter"}],
            "success_criteria": ["charter_approved"],
            "comprehension_check": {"q": "what is gate?"},
            "difficulty": "medium",
        },
        "registered_by": "test_architect",
    }
    h.validate(p)
    result = h.execute(p, intent_id="i")
    assert result["scenario_id"].startswith("scn_")


def test_register_scenario_rejects_bad_difficulty(store):
    h = RegisterHumanScenarioHandler(ontology=store)
    p = {
        "scenario_data": {
            "persona_id": "x", "domain": "y",
            "workflow_steps": [], "decision_points": [],
            "success_criteria": [], "comprehension_check": {},
            "difficulty": "expert",
        },
        "registered_by": "x",
    }
    with pytest.raises(ValueError, match="difficulty"):
        h.validate(p)


# -------- simulate_human_workflow (E2 stub) --------

def test_simulate_workflow_e2_stub_creates_trace(store):
    h = SimulateHumanWorkflowHandler(ontology=store)
    p = {
        "persona_id": "persona_x",
        "scenario_id": "scn_x",
        "simulation_id": "sim_x",
    }
    h.validate(p)
    result = h.execute(p, intent_id="i")
    assert result["trace_id"].startswith("hdt_")
    assert "E2 stub" in result["note"]
    persisted = store.get(HumanDecisionTrace, result["trace_id"])
    assert persisted.visible_state_snapshot.get("_e2_stub") is True


# -------- simulate_human_decision (E2 stub) --------

def test_simulate_decision_e2_stub_returns_defer(store):
    h = SimulateHumanDecisionHandler(ontology=store)
    p = {
        "persona_id": "persona_x",
        "gate_context": {"gate_type": "production"},
        "simulation_id": "sim_x",
    }
    h.validate(p)
    result = h.execute(p, intent_id="i")
    assert result["decision"] == "defer"  # safe stub default
    assert "E2 stub" in result["note"]


# -------- inject_human_error (E2 stub) --------

def test_inject_error_e2_stub_creates_near_miss(store):
    # Setup: HumanErrorInjection registered first
    inj = HumanErrorInjection(
        error_class="gate_skip",
        target_action="approve",
        timing="before_evidence",
        expected_system_response=["block"],
        severity_if_system_allows_error="D4",
        simulated_target_d_level="D3",
        action_d_level="D2",
    )
    store.create(inj)

    h = InjectHumanErrorHandler(ontology=store)
    p = {
        "persona_id": "persona_x",
        "error_injection_id": inj.injection_id,
        "simulation_id": "sim_x",
        "system_blocks": True,
    }
    h.validate(p)
    result = h.execute(p, intent_id="i")
    assert result["result"] == "blocked"
    assert result["near_miss_id"].startswith("nm_")
    persisted = store.get(HumanNearMiss, result["near_miss_id"])
    assert persisted is not None
    assert persisted.blocked_successfully is True
    # finding_d_level should be max(D3 simulated_target, D4 sev_if_allowed)=D4
    assert result["finding_d_level"] == "D4"


def test_inject_error_creates_finding_when_system_does_not_block(store):
    """Regression: when system_blocks=False, open Finding at elevated D-level."""
    from sylion.aeis.testing.ontology.objects import Finding

    inj = HumanErrorInjection(
        error_class="gate_skip",
        target_action="approve",
        timing="before_evidence",
        expected_system_response=["block"],
        severity_if_system_allows_error="D5",
        simulated_target_d_level="D3",
        action_d_level="D2",
    )
    store.create(inj)

    h = InjectHumanErrorHandler(ontology=store)
    p = {
        "persona_id": "persona_x",
        "error_injection_id": inj.injection_id,
        "simulation_id": "sim_x",
        "system_blocks": False,
    }
    h.validate(p)
    result = h.execute(p, intent_id="i")
    assert result["result"] == "allowed"
    assert result["near_miss_id"] is None
    assert result["finding_id"].startswith("find_")
    # max(D3, D5) == D5
    assert result["finding_d_level"] == "D5"
    finding = store.get(Finding, result["finding_id"])
    assert finding is not None
    assert finding.d_level == "D5"


def test_inject_error_rejects_unknown_injection(store):
    h = InjectHumanErrorHandler(ontology=store)
    p = {
        "persona_id": "x",
        "error_injection_id": "hei_unknown",
        "simulation_id": "sim",
        "system_blocks": True,
    }
    h.validate(p)
    with pytest.raises(ValueError, match="not found"):
        h.execute(p, intent_id="i")


def test_inject_error_rejects_bad_prefix(store):
    h = InjectHumanErrorHandler(ontology=store)
    with pytest.raises(ValueError, match="hei_"):
        h.validate({
            "persona_id": "x",
            "error_injection_id": "wrong_prefix",
            "simulation_id": "sim",
            "system_blocks": True,
        })


def test_inject_error_rejects_non_bool_system_blocks(store):
    """Regression: system_blocks must be boolean (truthy strings rejected)."""
    h = InjectHumanErrorHandler(ontology=store)
    with pytest.raises(ValueError, match="system_blocks"):
        h.validate({
            "persona_id": "x",
            "error_injection_id": "hei_xxxxx",
            "simulation_id": "sim",
            "system_blocks": "yes",
        })


# -------- record_comprehension_finding --------

def test_record_comprehension_creates_finding(store):
    h = RecordComprehensionFindingHandler(ontology=store)
    p = {
        "persona_id": "persona_beginner",
        "scenario_id": "scn_x",
        "comprehension_score": 0.3,
        "ui_element": "approve_button",
        "misunderstood_text": "Was unsure if this was final",
    }
    h.validate(p)
    result = h.execute(p, intent_id="i")
    finding = store.get(Finding, result["finding_id"])
    assert finding is not None
    assert finding.severity == "P3"


def test_record_comprehension_rejects_score_out_of_range(store):
    h = RecordComprehensionFindingHandler(ontology=store)
    p = {
        "persona_id": "x", "scenario_id": "x",
        "comprehension_score": 1.5,  # out of range
        "ui_element": "x", "misunderstood_text": "x",
    }
    with pytest.raises(ValueError, match="comprehension_score"):
        h.validate(p)
