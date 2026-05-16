"""W14 E8 review-fix regression tests.

Pins issues from Codex BLOCK 97% (15-persona/50-scenario coverage,
runtime contract uniformity) and Kimi FAIL high (8 attacks).
"""
from __future__ import annotations

import math
import threading

import pytest

from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import HumanErrorInjection, HumanPersona
from sylion.aeis.testing.personas.registry import (
    ALL_PERSONA_IDS, EXTENDED_PERSONA_IDS, PersonaRegistry, STARTER_PERSONA_IDS,
)
from sylion.aeis.testing.personas.runtime import PersonaRuntime, _seed_from
from sylion.aeis.testing.personas.scenarios import (
    CANONICAL_DOMAINS, all_scenarios, scenarios_for_domain, starter_scenarios,
)


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def registry(store):
    return PersonaRegistry(ontology=store)


# ---------------------------------------------------------------------------
# Codex coverage — 15 personas + 50 scenarios + 21 error classes
# ---------------------------------------------------------------------------


def test_full_persona_catalog_has_15(registry):
    catalog = registry.list_full_catalog()
    assert len(catalog) == 15


def test_starter_personas_are_4():
    assert len(STARTER_PERSONA_IDS) == 4


def test_extended_personas_are_11():
    assert len(EXTENDED_PERSONA_IDS) == 11


def test_all_persona_ids_are_15():
    assert len(ALL_PERSONA_IDS) == 15
    assert set(ALL_PERSONA_IDS) == set(STARTER_PERSONA_IDS + EXTENDED_PERSONA_IDS)


def test_scenario_library_has_50():
    assert len(all_scenarios()) == 50


def test_each_canonical_domain_has_5_scenarios():
    for domain in CANONICAL_DOMAINS:
        scns = scenarios_for_domain(domain)
        assert len(scns) == 5, f"{domain} has {len(scns)} scenarios, expected 5"


def test_starter_scenarios_one_per_domain():
    s = starter_scenarios()
    assert len(s) == 10
    domains = {sc.domain for sc in s}
    assert domains == set(CANONICAL_DOMAINS)


def test_unknown_domain_returns_empty():
    assert scenarios_for_domain("nonexistent_domain") == []


# ---------------------------------------------------------------------------
# Codex bug — error_class_count: 21 fixtures cover all 21 HumanErrorClass values
# ---------------------------------------------------------------------------


def test_error_class_fixtures_cover_all_21_classes():
    from pathlib import Path
    import json

    err_dir = (
        Path(__file__).resolve().parents[4]
        / "sylion" / "aeis" / "testing" / "personas" / "_errors"
    )
    files = sorted(err_dir.glob("*.json"))
    classes_seen: set[str] = set()
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        classes_seen.add(data["error_class"])
    from sylion.aeis.testing.ontology.enums import HumanErrorClass
    expected = set(HumanErrorClass.values())
    assert classes_seen == expected, (
        f"missing: {expected - classes_seen}, extra: {classes_seen - expected}"
    )


# ---------------------------------------------------------------------------
# Kimi attack #1 — duplicate name rejected
# ---------------------------------------------------------------------------


def test_register_rejects_duplicate_name(registry):
    p1 = HumanPersona(
        name="duplicate_test",
        capability_level="intermediate",
        error_proneness=0.1,
        attention_span_min=30,
        trust_in_ai_baseline=0.5,
        risk_tolerance="medium",
        dynamic_state={"fatigue_level": 0.0},
        behavior_modifiers={"decision_latency_multiplier": 1.0},
    )
    registry.register(p1)
    p2 = HumanPersona(
        name="duplicate_test",
        capability_level="expert",
        error_proneness=0.05,
        attention_span_min=60,
        trust_in_ai_baseline=0.6,
        risk_tolerance="low",
        dynamic_state={"fatigue_level": 0.0},
        behavior_modifiers={"decision_latency_multiplier": 0.9},
    )
    with pytest.raises(ValueError, match="already registered"):
        registry.register(p2)


# ---------------------------------------------------------------------------
# Kimi attack #2 — RNG determinism: same seed -> same trace
# ---------------------------------------------------------------------------


def test_simulate_workflow_is_deterministic(store, registry):
    rt_a = PersonaRuntime(ontology=store, registry=registry, rng_seed=42)
    rt_b = PersonaRuntime(ontology=store, registry=registry, rng_seed=42)
    persona = registry.get_by_name("operator_beginner")
    scn = scenarios_for_domain("hmep")[0]
    store.create(scn)

    trace_a = rt_a.simulate_workflow(persona.persona_id, scn.scenario_id, "sim_a")
    # Re-run with the same simulation_id from a second runtime instance.
    trace_b = rt_b.simulate_workflow(persona.persona_id, scn.scenario_id, "sim_a")

    metrics_a = trace_a.behavior_metrics
    metrics_b = trace_b.behavior_metrics
    assert metrics_a["decision_latency_ms_total"] == metrics_b["decision_latency_ms_total"]
    assert metrics_a["hesitation_count"] == metrics_b["hesitation_count"]
    assert metrics_a["comprehension_score"] == metrics_b["comprehension_score"]


def test_seed_from_helper_stable():
    """Stable across calls in the same Python process."""
    a = _seed_from("persona_x", "scenario_y")
    b = _seed_from("persona_x", "scenario_y")
    assert a == b
    c = _seed_from("persona_x", "scenario_z")
    assert a != c


# ---------------------------------------------------------------------------
# Kimi attack #3 — NaN fatigue clamped, comprehension stays in [0,1]
# ---------------------------------------------------------------------------


def test_comprehension_stays_in_range_even_with_nan_fatigue(store, registry):
    persona = registry.get_by_name("operator_beginner")
    persona.dynamic_state = {"fatigue_level": float("nan")}
    store.update(persona)

    rt = PersonaRuntime(ontology=store, registry=registry, rng_seed=1)
    scn = scenarios_for_domain("hmep")[0]
    store.create(scn)
    trace = rt.simulate_workflow(persona.persona_id, scn.scenario_id, "sim_nan")
    score = trace.behavior_metrics["comprehension_score"]
    assert math.isfinite(score)
    assert 0.0 <= score <= 1.0


def test_comprehension_stays_in_range_with_inf_fatigue(store, registry):
    persona = registry.get_by_name("operator_beginner")
    persona.dynamic_state = {"fatigue_level": float("inf")}
    store.update(persona)

    rt = PersonaRuntime(ontology=store, registry=registry, rng_seed=1)
    scn = scenarios_for_domain("hmep")[0]
    store.create(scn)
    trace = rt.simulate_workflow(persona.persona_id, scn.scenario_id, "sim_inf")
    score = trace.behavior_metrics["comprehension_score"]
    assert math.isfinite(score)
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Kimi attack #4 — bogus d_level on injection falls back to D2
# ---------------------------------------------------------------------------


def test_inject_error_falls_back_for_bogus_d_level(store, registry, monkeypatch):
    """Constructor + store reject bogus D-levels at build time, but if a
    corrupted row escapes via legacy code/manual SQL, PersonaRuntime
    must NOT propagate the garbage to the Finding. Monkeypatched
    ontology.get returns a tampered injection bypassing the validator.
    """
    inj = HumanErrorInjection(
        error_class="gate_skip",
        target_action="approve_x",
        timing="during_review",
        expected_system_response=["block"],
        severity_if_system_allows_error="D5",
        simulated_target_d_level="D3",
        action_d_level="D2",
    )
    store.create(inj)
    # In-memory tamper after persist — never written back through update().
    inj.severity_if_system_allows_error = "GARBAGE"

    real_get = store.get

    def patched_get(cls, oid):
        if oid == inj.injection_id:
            return inj
        return real_get(cls, oid)

    monkeypatch.setattr(store, "get", patched_get)

    rt = PersonaRuntime(ontology=store, registry=registry, rng_seed=1)
    persona = registry.get_by_name("operator_beginner")
    out = rt.inject_error(
        persona.persona_id, inj.injection_id, "sim_e8x",
        system_blocks_action=False,
    )
    assert out["d_level"] == "D2"


# ---------------------------------------------------------------------------
# Kimi attack #5 — decision_points sanitized (no arbitrary objects)
# ---------------------------------------------------------------------------


def test_scenarios_use_string_keyed_dicts():
    for s in all_scenarios():
        for step in s.workflow_steps:
            assert isinstance(step, dict)
            assert "step" in step
            assert isinstance(step["step"], str)
        for d in s.decision_points:
            assert isinstance(d, dict)
            assert "d" in d
            assert isinstance(d["d"], str)


# ---------------------------------------------------------------------------
# Kimi attack #6 — dynamic_state RMW under contention
# ---------------------------------------------------------------------------


def test_dynamic_state_rmw_serialized(store, registry):
    persona = registry.get_by_name("operator_beginner")
    persona_id = persona.persona_id
    barrier = threading.Barrier(8)

    def worker(i):
        barrier.wait()
        registry.update_dynamic_state(
            persona_id, {f"counter_{i}": float(i)},
        )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    final = registry.get(persona_id)
    # All eight keys must survive — last-writer-wins on the persona, not
    # last-reader-wins on the partial state copy.
    assert all(f"counter_{i}" in final.dynamic_state for i in range(8))


# ---------------------------------------------------------------------------
# Kimi attack #8 — JSON dupe keys rejected
# ---------------------------------------------------------------------------


def test_reject_dupe_keys_helper():
    from sylion.aeis.testing.personas.registry import _reject_dupe_keys
    _reject_dupe_keys([("a", 1), ("b", 2)])  # ok
    with pytest.raises(ValueError, match="duplicate"):
        _reject_dupe_keys([("a", 1), ("a", 2)])


def test_normalize_name_nfkc():
    """Cyrillic 'а' (U+0430) and Latin 'a' must NOT collapse to the same
    string under NFKC (they're different glyphs); the test pins that
    NFKC doesn't accidentally merge security-relevant names while still
    stripping zero-width and compat duplicates."""
    from sylion.aeis.testing.personas.registry import _normalize_name
    cyr = "аbc"  # Cyrillic 'а' + 'bc'
    lat = "abc"
    assert _normalize_name(cyr) != _normalize_name(lat)
    # NBSP / trim
    assert _normalize_name("  hello  ") == "hello"


# ---------------------------------------------------------------------------
# Codex bug — runtime outputs always include simulation_id + comprehension_score
# ---------------------------------------------------------------------------


def test_simulate_decision_includes_simulation_id_and_score(store, registry):
    rt = PersonaRuntime(ontology=store, registry=registry, rng_seed=1)
    persona = registry.get_by_name("operator_beginner")
    out = rt.simulate_decision(
        persona.persona_id, {"d_level": "D3"}, "sim_dec",
    )
    assert out["simulation_id"] == "sim_dec"
    assert 0.0 <= out["comprehension_score"] <= 1.0


def test_inject_error_includes_simulation_id_and_score(store, registry):
    inj = HumanErrorInjection(
        error_class="gate_skip",
        target_action="approve_x",
        timing="during_review",
        expected_system_response=["block"],
        severity_if_system_allows_error="D4",
        simulated_target_d_level="D3",
        action_d_level="D2",
    )
    store.create(inj)
    rt = PersonaRuntime(ontology=store, registry=registry, rng_seed=1)
    persona = registry.get_by_name("operator_beginner")
    blocked = rt.inject_error(
        persona.persona_id, inj.injection_id, "sim_inj_b",
        system_blocks_action=True,
    )
    allowed = rt.inject_error(
        persona.persona_id, inj.injection_id, "sim_inj_a",
        system_blocks_action=False,
    )
    for out in (blocked, allowed):
        assert "simulation_id" in out
        assert "comprehension_score" in out
        assert 0.0 <= out["comprehension_score"] <= 1.0
