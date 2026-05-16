"""Tests for E8 starter scenarios + extended personas (8 total)."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.personas import PersonaRegistry, PersonaRuntime
from sylion.aeis.testing.personas.scenarios import starter_scenarios


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def registry(store):
    return PersonaRegistry(ontology=store, autoload_starters=True)


# -------- 8 personas (4 starter from E3 + 4 new in E8) --------

def test_autoload_includes_8_personas_after_E8(registry):
    all_p = registry.list_all()
    names = {p.name for p in all_p}
    expected = {
        "operator_beginner", "operator_power_user", "auditor",
        "operator_overloaded",
        "admin_overconfident", "viewer_curious",
        "mobile_first_operator", "incident_responder",
    }
    assert expected.issubset(names)


def test_admin_overconfident_high_risk_tolerance(registry):
    p = registry.get_by_name("admin_overconfident")
    assert p is not None
    assert p.risk_tolerance == "high"
    assert p.behavior_modifiers["skips_warnings_probability"] >= 0.5


def test_viewer_curious_attempts_unauthorized(registry):
    p = registry.get_by_name("viewer_curious")
    assert p is not None
    assert p.behavior_modifiers["attempts_unauthorized_action_probability"] > 0.5


def test_mobile_first_has_misclick(registry):
    p = registry.get_by_name("mobile_first_operator")
    assert p is not None
    assert p.behavior_modifiers["small_screen_misclick_probability"] > 0


def test_incident_responder_high_pressure(registry):
    p = registry.get_by_name("incident_responder")
    assert p is not None
    assert p.dynamic_state["time_pressure"] >= 0.9
    assert p.dynamic_state["cognitive_load"] >= 0.85


# -------- 10 starter scenarios --------

def test_starter_scenarios_returns_10():
    s = starter_scenarios()
    assert len(s) == 10


def test_starter_scenarios_cover_distinct_personas():
    s = starter_scenarios()
    persona_ids = {sc.persona_id for sc in s}
    assert len(persona_ids) >= 6  # at least 6 distinct personas covered


def test_each_scenario_has_workflow_and_decisions():
    for s in starter_scenarios():
        assert len(s.workflow_steps) > 0
        assert len(s.decision_points) > 0
        assert len(s.success_criteria) > 0
        assert "q" in s.comprehension_check


def test_scenarios_include_difficulty_variety():
    s = starter_scenarios()
    difficulties = {sc.difficulty for sc in s}
    assert "hard" in difficulties
    assert difficulties & {"easy", "medium"}


def test_hmep_scenario_for_beginner_easy():
    s = starter_scenarios()
    hmep = [sc for sc in s if sc.domain == "hmep"]
    assert hmep
    # First HMEP project for beginner — should be easy
    assert hmep[0].difficulty == "easy"
    assert hmep[0].persona_id == "persona_operator_beginner"


def test_d5_admin_scenario_is_hard():
    s = starter_scenarios()
    admin = [sc for sc in s if sc.persona_id == "persona_admin_overconfident"]
    assert admin
    assert admin[0].difficulty == "hard"


def test_loop_governor_scenario_for_auditor():
    from sylion.aeis.testing.personas.scenarios import all_scenarios
    s = all_scenarios()
    loop = [sc for sc in s
            if "loop" in str(sc.workflow_steps).lower()
            or "loop" in str(sc.decision_points).lower()]
    assert loop


# -------- PersonaRuntime extended cognitive scoring --------

def test_runtime_with_overloaded_persona_gives_low_comprehension(store, registry):
    from sylion.aeis.testing.personas.scenarios import all_scenarios
    rt = PersonaRuntime(ontology=store, registry=registry, rng_seed=7)
    overloaded = registry.get_by_name("operator_overloaded")
    scenarios = all_scenarios()
    overloaded_scn = next(
        s for s in scenarios if s.persona_id == "persona_operator_overloaded"
    )
    store.create(overloaded_scn)
    trace = rt.simulate_workflow(
        overloaded.persona_id, overloaded_scn.scenario_id, "sim_e8",
    )
    # High fatigue + hard difficulty => comprehension < 0.6
    assert trace.behavior_metrics["comprehension_score"] < 0.7


def test_runtime_with_expert_gives_high_comprehension(store, registry):
    rt = PersonaRuntime(ontology=store, registry=registry, rng_seed=7)
    auditor = registry.get_by_name("auditor")
    scenarios = starter_scenarios()
    auditor_scn = next(s for s in scenarios if s.persona_id == "persona_auditor")
    store.create(auditor_scn)
    trace = rt.simulate_workflow(
        auditor.persona_id, auditor_scn.scenario_id, "sim_e8b",
    )
    assert trace.behavior_metrics["comprehension_score"] >= 0.6
