"""PersonaRegistry tests — autoload + CRUD + dynamic state."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import HumanPersona
from sylion.aeis.testing.personas import PersonaRegistry
from sylion.aeis.testing.personas.registry import STARTER_PERSONA_IDS


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def registry(store):
    return PersonaRegistry(ontology=store, autoload_starters=True)


# -------- Autoload --------

def test_autoload_creates_4_starter_personas(registry):
    starters = registry.list_starter()
    names = {p.name for p in starters}
    assert names == set(STARTER_PERSONA_IDS)


def test_autoload_idempotent(store):
    PersonaRegistry(store, autoload_starters=True)
    PersonaRegistry(store, autoload_starters=True)  # second call
    all_personas = store.list(HumanPersona, limit=100)
    # Each starter only loaded once
    by_name = {p.name: 0 for p in all_personas}
    for p in all_personas:
        by_name[p.name] += 1
    for name in STARTER_PERSONA_IDS:
        assert by_name.get(name, 0) == 1


def test_starter_beginner_has_high_error_proneness(registry):
    p = registry.get_by_name("operator_beginner")
    assert p.error_proneness >= 0.4
    assert p.capability_level == "beginner"


def test_starter_power_user_has_low_error_proneness(registry):
    p = registry.get_by_name("operator_power_user")
    assert p.error_proneness <= 0.15
    assert p.capability_level == "expert"


def test_starter_auditor_has_evidence_focus(registry):
    p = registry.get_by_name("auditor")
    assert "compliance" in p.expertise_domains or "evidence_chains" in p.expertise_domains
    assert p.behavior_modifiers.get("verifies_evidence_probability", 0) > 0.9


def test_starter_overloaded_has_high_fatigue(registry):
    p = registry.get_by_name("operator_overloaded")
    assert p.dynamic_state["fatigue_level"] >= 0.7
    assert p.dynamic_state["cognitive_load"] >= 0.8


# -------- CRUD --------

def test_register_custom_persona(registry):
    p = HumanPersona(
        name="custom_test_persona",
        capability_level="intermediate",
        error_proneness=0.2, attention_span_min=30,
        trust_in_ai_baseline=0.5, risk_tolerance="medium",
        dynamic_state={"fatigue_level": 0.0},
        behavior_modifiers={"decision_latency_multiplier": 1.0},
    )
    registry.register(p)
    fetched = registry.get_by_name("custom_test_persona")
    assert fetched is not None


def test_get_unknown_returns_none(registry):
    assert registry.get("persona_doesnotexist") is None


# -------- Dynamic state --------

def test_update_dynamic_state(registry):
    p = registry.get_by_name("operator_beginner")
    updated = registry.update_dynamic_state(
        p.persona_id, {"fatigue_level": 0.5, "cognitive_load": 0.6}
    )
    assert updated.dynamic_state["fatigue_level"] == 0.5
    assert updated.dynamic_state["cognitive_load"] == 0.6


def test_reset_dynamic_state_clears_fatigue(registry):
    p = registry.get_by_name("operator_overloaded")  # starts fatigued
    reset = registry.reset_dynamic_state(p.persona_id)
    assert reset.dynamic_state["fatigue_level"] == 0.0
    assert reset.dynamic_state["cognitive_load"] == 0.0
    assert reset.dynamic_state["consecutive_decisions_count"] == 0


def test_update_unknown_persona_raises(registry):
    with pytest.raises(ValueError, match="not found"):
        registry.update_dynamic_state("persona_missing", {"fatigue_level": 1.0})
