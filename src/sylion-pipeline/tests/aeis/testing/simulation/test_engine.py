"""Simulation contract + sandbox + engine tests."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import (
    SimulationBranch, SimulationContract, SimulationEvidence,
)
from sylion.aeis.testing.simulation import (
    SimulationEngine, TransactionalSandbox, build_contract,
)


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def engine(store):
    return SimulationEngine(ontology=store)


def _make_contract(sim_id="sim_t1") -> SimulationContract:
    return build_contract(
        simulation_id=sim_id,
        branch_id="br_sim_1",
        source_project_id="proj_demo",
        sot_version="sot_v1",
        masterplan_version="mp_v1",
    )


# -------- L0 Contract --------

def test_contract_has_safe_defaults():
    c = _make_contract()
    assert c.isolation["main_mutation_allowed"] is False
    assert c.isolation["external_network_allowed"] is False
    assert c.isolation["real_device_allowed"] is False
    assert c.model_mode["llm_mode"] == "deterministic_stub"
    assert c.persistence["discard_object_state"] is True


def test_contract_REJECTS_main_mutation():
    with pytest.raises(ValueError, match="main_mutation_allowed"):
        build_contract(
            simulation_id="sim_x",
            branch_id="br_x",
            source_project_id="proj_x",
            sot_version="v1",
            masterplan_version="v1",
            isolation_overrides={"main_mutation_allowed": True},
        )


def test_contract_REJECTS_external_network():
    with pytest.raises(ValueError, match="external_network"):
        build_contract(
            simulation_id="sim_x", branch_id="br_x",
            source_project_id="proj_x", sot_version="v1", masterplan_version="v1",
            isolation_overrides={"external_network_allowed": True},
        )


def test_contract_REJECTS_real_device():
    with pytest.raises(ValueError, match="real_device"):
        build_contract(
            simulation_id="sim_x", branch_id="br_x",
            source_project_id="proj_x", sot_version="v1", masterplan_version="v1",
            isolation_overrides={"real_device_allowed": True},
        )


def test_contract_REJECTS_runtime_over_hard_max():
    with pytest.raises(ValueError, match="max_runtime_seconds"):
        build_contract(
            simulation_id="sim_x", branch_id="br_x",
            source_project_id="proj_x", sot_version="v1", masterplan_version="v1",
            safety_overrides={"max_runtime_seconds": 9999},
        )


def test_contract_REJECTS_cost_over_hard_max():
    with pytest.raises(ValueError, match="max_cost_usd"):
        build_contract(
            simulation_id="sim_x", branch_id="br_x",
            source_project_id="proj_x", sot_version="v1", masterplan_version="v1",
            safety_overrides={"max_cost_usd": 99.99},
        )


# -------- L1 Sandbox --------

def test_sandbox_starts_with_isolated_components():
    sb = TransactionalSandbox(simulation_id="sim_a", in_memory=True)
    sb.start()
    assert sb.ontology is not None
    assert sb.event_bus is not None
    assert sb.llm is not None
    sb.discard()


def test_sandbox_metrics_track_actions():
    sb = TransactionalSandbox(simulation_id="sim_b", in_memory=True)
    sb.start()
    sb.record_action(cost_usd=0.05)
    sb.record_action(cost_usd=0.03)
    m = sb.metrics()
    assert m["action_count"] == 2
    assert m["cost_usd"] == pytest.approx(0.08)
    sb.discard()


def test_sandbox_llm_returns_deterministic_stub():
    sb = TransactionalSandbox(simulation_id="sim_c", in_memory=True,
                               llm_fixtures={"hello": "world"})
    sb.start()
    assert sb.llm.complete("hello") == "world"
    assert sb.llm.complete("anything").startswith("[STUB:")
    sb.discard()


def test_sandbox_event_bus_buffers():
    from sylion.core.event_bus import SylionEvent
    sb = TransactionalSandbox(simulation_id="sim_d", in_memory=True)
    sb.start()
    sb.event_bus.publish(SylionEvent(event_id="", topic="test.x", payload={}))
    assert sb.event_bus.count() == 1
    assert sb.event_bus.replay()[0]["topic"] == "test.x"
    sb.discard()


def test_sandbox_discard_idempotent():
    sb = TransactionalSandbox(simulation_id="sim_e", in_memory=True)
    sb.start()
    sb.discard()
    sb.discard()  # second call no-op
    assert sb._discarded


# -------- SimulationEngine --------

def test_engine_start_persists_contract_and_sim_branch(engine, store):
    c = _make_contract()
    sim_id = engine.start(c)
    assert sim_id == "sim_t1"
    persisted_c = store.get(SimulationContract, c.contract_id)
    assert persisted_c is not None
    branches = store.list(SimulationBranch, filters={"contract_id": c.contract_id})
    assert len(branches) == 1
    assert branches[0].state == "open"


def test_engine_run_layer_dispatches(engine):
    c = _make_contract()
    engine.start(c)
    for layer in (1, 2, 3, 4):
        result = engine.run_layer("sim_t1", layer, {"x": 1})
        assert result["layer"] == layer or result.get("ok") is True


def test_engine_run_layer_rejects_invalid_layer(engine):
    c = _make_contract()
    engine.start(c)
    with pytest.raises(ValueError, match="layer"):
        engine.run_layer("sim_t1", 5, {})


def test_engine_run_layer_rejects_unknown_simulation(engine):
    with pytest.raises(ValueError, match="not active"):
        engine.run_layer("sim_unknown", 1, {})


def test_engine_max_actions_blocks_excess(engine):
    c = build_contract(
        simulation_id="sim_safety",
        branch_id="br_safety",
        source_project_id="proj_x",
        sot_version="v1", masterplan_version="v1",
        safety_overrides={"max_actions": 3},
    )
    engine.start(c)
    engine.run_layer("sim_safety", 1, {})
    engine.run_layer("sim_safety", 1, {})
    engine.run_layer("sim_safety", 1, {})
    with pytest.raises(RuntimeError, match="max_actions"):
        engine.run_layer("sim_safety", 1, {})


def test_engine_collect_evidence_persists(engine, store):
    c = _make_contract()
    engine.start(c)
    engine.run_layer("sim_t1", 1, {})
    evidence = engine.collect_evidence("sim_t1")
    assert evidence.evidence_id.startswith("se_")
    persisted = store.get(SimulationEvidence, evidence.evidence_id)
    assert persisted is not None


def test_engine_discard_marks_branch_discarded(engine, store):
    c = _make_contract()
    engine.start(c)
    engine.discard("sim_t1", reason="test cleanup")
    branches = store.list(SimulationBranch, filters={"contract_id": c.contract_id})
    assert branches[0].state == "discarded"
    assert "test cleanup" in (branches[0].discard_reason or "")


def test_engine_double_start_rejected(engine):
    c = _make_contract()
    engine.start(c)
    with pytest.raises(RuntimeError, match="already active"):
        engine.start(c)
