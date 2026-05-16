"""PersonaRuntime tests — L2/L3/L4 simulation."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import (
    Finding, HumanDecisionTrace, HumanErrorInjection,
    HumanNearMiss, HumanScenario,
)
from sylion.aeis.testing.personas import PersonaRegistry, PersonaRuntime


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def registry(store):
    return PersonaRegistry(ontology=store, autoload_starters=True)


@pytest.fixture
def runtime(store, registry):
    return PersonaRuntime(ontology=store, registry=registry, rng_seed=42)


@pytest.fixture
def scenario(store):
    s = HumanScenario(
        persona_id="persona_dummy",
        domain="hmep",
        workflow_steps=[
            {"step": "intake"},
            {"step": "approve_charter"},
            {"step": "monitor_release"},
        ],
        decision_points=[{"d": "approve_charter"}],
        success_criteria=["charter_approved"],
        comprehension_check={"q": "what is gate?"},
        difficulty="medium",
    )
    store.create(s)
    return s


# -------- L2 simulate_workflow --------

def test_simulate_workflow_creates_trace(runtime, registry, scenario):
    p = registry.get_by_name("operator_beginner")
    trace = runtime.simulate_workflow(p.persona_id, scenario.scenario_id, "sim_x")
    assert isinstance(trace, HumanDecisionTrace)
    assert trace.persona_id == p.persona_id
    assert len(trace.decisions_made) == len(scenario.workflow_steps)
    assert "comprehension_score" in trace.behavior_metrics


def test_workflow_beginner_lower_comprehension_than_expert(runtime, registry, scenario):
    beginner = registry.get_by_name("operator_beginner")
    expert = registry.get_by_name("operator_power_user")
    t_beg = runtime.simulate_workflow(beginner.persona_id, scenario.scenario_id, "sim_b")
    t_exp = runtime.simulate_workflow(expert.persona_id, scenario.scenario_id, "sim_e")
    assert t_beg.behavior_metrics["comprehension_score"] < t_exp.behavior_metrics["comprehension_score"]


def test_workflow_overloaded_has_low_comprehension(runtime, registry, scenario):
    overloaded = registry.get_by_name("operator_overloaded")
    trace = runtime.simulate_workflow(overloaded.persona_id, scenario.scenario_id, "sim_o")
    # High fatigue penalty
    assert trace.behavior_metrics["comprehension_score"] < 0.7


def test_simulate_workflow_unknown_persona_raises(runtime, scenario):
    with pytest.raises(ValueError, match="persona not found"):
        runtime.simulate_workflow("persona_missing", scenario.scenario_id, "sim_x")


# -------- L3 simulate_decision --------

def test_decision_beginner_defers_d3(runtime, registry):
    beginner = registry.get_by_name("operator_beginner")
    result = runtime.simulate_decision(
        beginner.persona_id, {"d_level": "D3"}, "sim_x"
    )
    assert result["decision"] == "defer"


def test_decision_high_risk_tolerance_approves(store):
    from sylion.aeis.testing.ontology.objects import HumanPersona
    risky = HumanPersona(
        name="risky_test", capability_level="expert", error_proneness=0.1,
        attention_span_min=60, trust_in_ai_baseline=0.7,
        risk_tolerance="high",
        dynamic_state={"fatigue_level": 0.0}, behavior_modifiers={},
    )
    store.create(risky)
    reg = PersonaRegistry(store, autoload_starters=False)
    rt = PersonaRuntime(ontology=store, registry=reg, rng_seed=1)
    result = rt.simulate_decision(risky.persona_id, {"d_level": "D2"}, "sim_x")
    assert result["decision"] == "approve"


def test_decision_latency_uses_persona_modifier(runtime, registry):
    beg = registry.get_by_name("operator_beginner")  # multiplier 2.5
    pow = registry.get_by_name("operator_power_user")  # multiplier 0.4
    r1 = runtime.simulate_decision(beg.persona_id, {"d_level": "D2"}, "sim_x")
    r2 = runtime.simulate_decision(pow.persona_id, {"d_level": "D2"}, "sim_x")
    assert r1["decision_latency_ms"] > r2["decision_latency_ms"]


# -------- L4 inject_error --------

def test_inject_error_blocked_creates_near_miss(runtime, registry, store):
    inj = HumanErrorInjection(
        error_class="gate_skip",
        target_action="approve_d3_no_evidence",
        timing="before_evidence",
        expected_system_response=["block"],
        severity_if_system_allows_error="D4",
        simulated_target_d_level="D3",
        action_d_level="D2",
    )
    store.create(inj)
    p = registry.get_by_name("operator_beginner")
    result = runtime.inject_error(
        p.persona_id, inj.injection_id, "sim_x",
        system_blocks_action=True,
    )
    assert result["result"] == "blocked"
    assert result["near_miss_id"].startswith("nm_")
    nm = store.get(HumanNearMiss, result["near_miss_id"])
    assert nm.blocked_successfully is True


def test_inject_error_allowed_creates_finding_with_high_severity(runtime, registry, store):
    inj = HumanErrorInjection(
        error_class="premature_action",
        target_action="upload_no_backup",
        timing="before_backup",
        expected_system_response=["block_upload"],
        severity_if_system_allows_error="D5",
        simulated_target_d_level="D5",
        action_d_level="D2",
    )
    store.create(inj)
    p = registry.get_by_name("operator_overloaded")
    result = runtime.inject_error(
        p.persona_id, inj.injection_id, "sim_x",
        system_blocks_action=False,  # system FAILED to block
    )
    assert result["result"] == "allowed"
    assert result["severity"] == "P0"  # D5 breach -> P0
    assert result["d_level"] == "D5"
    f = store.get(Finding, result["finding_id"])
    assert f.severity == "P0"


def test_inject_error_unknown_injection_raises(runtime, registry):
    p = registry.get_by_name("operator_beginner")
    with pytest.raises(ValueError, match="not found"):
        runtime.inject_error(p.persona_id, "hei_missing", "sim_x")


def test_inject_error_unknown_persona_raises(runtime, store):
    inj = HumanErrorInjection(
        error_class="gate_skip", target_action="x", timing="t",
        expected_system_response=["block"],
        severity_if_system_allows_error="D3",
        simulated_target_d_level="D3", action_d_level="D2",
    )
    store.create(inj)
    with pytest.raises(ValueError, match="persona not found"):
        runtime.inject_error("persona_missing", inj.injection_id, "sim_x")
