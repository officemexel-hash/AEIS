"""Regression tests for the W14 E3 simulation review-fix pass."""
from __future__ import annotations

from pathlib import Path

import pytest

from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.simulation import (
    MockEventBus, MockLLM, SimulationEngine, TransactionalSandbox,
    build_contract,
)
from sylion.aeis.testing.simulation.mock_llm import _stub_response


# ---------------------------------------------------------------------------
# Spec coverage — simulation/mock_bus.py & mock_llm.py exposed as modules
# ---------------------------------------------------------------------------


def test_mock_bus_publish_and_replay() -> None:
    bus = MockEventBus(simulation_id="sim_x")
    from sylion.core.event_bus import SylionEvent

    bus.publish(SylionEvent(event_id="", topic="t1", payload={"k": 1}))
    bus.publish(SylionEvent(event_id="", topic="t2", payload={"k": 2}))
    assert bus.count() == 2
    captured = bus.replay()
    assert captured[0]["topic"] == "t1"
    assert captured[1]["payload"]["k"] == 2
    # Filter
    assert bus.count(topic="t1") == 1


def test_mock_bus_does_not_share_state_across_instances() -> None:
    a = MockEventBus(simulation_id="sim_a")
    b = MockEventBus(simulation_id="sim_b")
    from sylion.core.event_bus import SylionEvent

    a.publish(SylionEvent(event_id="", topic="x", payload={}))
    assert a.count() == 1
    assert b.count() == 0


def test_mock_llm_deterministic_across_runs() -> None:
    """Python's built-in hash() is salted; mock LLM must use SHA256."""
    a = MockLLM().complete("hello world")
    b = MockLLM().complete("hello world")
    assert a == b
    assert a == _stub_response("hello world")
    assert a.startswith("[STUB:")


def test_mock_llm_fixtures_exact_match() -> None:
    llm = MockLLM(fixtures={"hi": "hello"})
    assert llm.complete("hi") == "hello"
    # Whitespace / case must NOT match a fixture.
    assert llm.complete("Hi") != "hello"


def test_mock_llm_recorded_replay_consumed_in_order() -> None:
    llm = MockLLM(recorded_replay=[
        ("p1", "r1"),
        ("p2", "r2"),
    ])
    assert llm.complete("anything") == "r1"
    assert llm.complete("anything") == "r2"
    # Exhausted -> falls back to deterministic stub.
    third = llm.complete("p3")
    assert third == _stub_response("p3")


def test_mock_llm_call_log() -> None:
    llm = MockLLM()
    llm.complete("hi")
    llm.complete("there")
    assert llm.call_count() == 2


# ---------------------------------------------------------------------------
# Codex bug — sandbox is file-backed by default (sim_<id>_*.db)
# ---------------------------------------------------------------------------


def test_sandbox_file_backed_uses_sim_prefix(tmp_path: Path) -> None:
    sb = TransactionalSandbox(
        simulation_id="br_abc12345",
        snapshot_base_dir=str(tmp_path),
    )
    sb.start()
    try:
        assert sb.snapshot is not None
        assert sb.snapshot.path.name.startswith("sim_br_abc12345_")
    finally:
        sb.discard()
        assert sb.snapshot is None or not sb.snapshot.path.exists()


def test_sandbox_metrics_zero_duration_when_not_started() -> None:
    sb = TransactionalSandbox(simulation_id="sim_dummy", in_memory=True)
    m = sb.metrics()
    assert m["duration_s"] == 0.0
    assert m["action_count"] == 0


# ---------------------------------------------------------------------------
# Codex bug — collect_evidence reports max layer reached, not always 4
# ---------------------------------------------------------------------------


def test_engine_collect_evidence_reports_max_layer() -> None:
    store = OntologyStore()
    eng = SimulationEngine(
        ontology=store, cleanup_orphans_on_init=False,
    )
    contract = build_contract(
        simulation_id=f"sim_layer_{id(store)}",
        branch_id=f"br_lay_{id(store)}",
        source_project_id="proj_x",
        sot_version="1",
        masterplan_version="1",
    )
    eng.start(contract, in_memory=True)
    try:
        # Run only L1 + L2; evidence must report layer_executed=2, not 4.
        eng.run_layer(contract.simulation_id, 1, {})
        eng.run_layer(contract.simulation_id, 2, {})
        evidence = eng.collect_evidence(contract.simulation_id)
        assert evidence.layer_executed == 2
    finally:
        eng.discard(contract.simulation_id)


# ---------------------------------------------------------------------------
# Codex bug — engine persists snapshot_db_path on the SimulationBranch row
# ---------------------------------------------------------------------------


def test_engine_persists_snapshot_db_path(tmp_path: Path) -> None:
    store = OntologyStore()
    eng = SimulationEngine(
        ontology=store,
        snapshot_base_dir=str(tmp_path),
        cleanup_orphans_on_init=False,
    )
    contract = build_contract(
        simulation_id="sim_persist_path",
        branch_id="br_persist_path",
        source_project_id="proj_x",
        sot_version="1",
        masterplan_version="1",
    )
    eng.start(contract, in_memory=False)
    try:
        from sylion.aeis.testing.ontology.objects import SimulationBranch

        rows = store.list(SimulationBranch, limit=10)
        assert any(
            r.snapshot_db_path and r.snapshot_db_path.startswith(str(tmp_path))
            for r in rows
        )
    finally:
        eng.discard(contract.simulation_id)


# ---------------------------------------------------------------------------
# Codex bug — main_mutation_allowed permitted only with D5+council
# ---------------------------------------------------------------------------


def test_contract_rejects_main_mutation_without_d5_and_council() -> None:
    with pytest.raises(ValueError, match="main_mutation_allowed"):
        build_contract(
            simulation_id="sim_x",
            branch_id="br_x",
            source_project_id="proj_x",
            sot_version="1",
            masterplan_version="1",
            isolation_overrides={"main_mutation_allowed": True},
        )


def test_contract_allows_main_mutation_with_d5_and_council() -> None:
    contract = build_contract(
        simulation_id="sim_x",
        branch_id="br_x",
        source_project_id="proj_x",
        sot_version="1",
        masterplan_version="1",
        isolation_overrides={"main_mutation_allowed": True},
        safety_overrides={
            "approved_d_level": "D5",
            "council_approved": True,
        },
    )
    assert contract.isolation["main_mutation_allowed"] is True


def test_contract_rejects_external_network_without_d4_sentinel() -> None:
    with pytest.raises(ValueError, match="external_network_allowed"):
        build_contract(
            simulation_id="sim_x",
            branch_id="br_x",
            source_project_id="proj_x",
            sot_version="1",
            masterplan_version="1",
            isolation_overrides={"external_network_allowed": True},
        )


def test_contract_allows_external_network_with_d4_sentinel() -> None:
    contract = build_contract(
        simulation_id="sim_x",
        branch_id="br_x",
        source_project_id="proj_x",
        sot_version="1",
        masterplan_version="1",
        isolation_overrides={"external_network_allowed": True},
        safety_overrides={
            "approved_d_level": "D4",
            "sentinel_approved": True,
        },
    )
    assert contract.isolation["external_network_allowed"] is True


# ---------------------------------------------------------------------------
# Kimi attack #4 — NaN / Inf in safety params must not bypass hard bounds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -float("inf")])
def test_contract_rejects_nan_inf_runtime(bad_value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        build_contract(
            simulation_id="sim_x",
            branch_id="br_x",
            source_project_id="proj_x",
            sot_version="1",
            masterplan_version="1",
            safety_overrides={"max_runtime_seconds": bad_value},
        )


def test_contract_rejects_negative_safety_values() -> None:
    with pytest.raises(ValueError, match=">=" ):
        build_contract(
            simulation_id="sim_x",
            branch_id="br_x",
            source_project_id="proj_x",
            sot_version="1",
            masterplan_version="1",
            safety_overrides={"max_cost_usd": -1.0},
        )


def test_contract_rejects_non_numeric_safety() -> None:
    with pytest.raises(ValueError, match="numeric"):
        build_contract(
            simulation_id="sim_x",
            branch_id="br_x",
            source_project_id="proj_x",
            sot_version="1",
            masterplan_version="1",
            safety_overrides={"max_runtime_seconds": "fast"},
        )


# ---------------------------------------------------------------------------
# Kimi attack #2 — discard order: file gone first, registry entry last
# ---------------------------------------------------------------------------


def test_engine_discard_removes_file_before_dropping_registry(tmp_path: Path) -> None:
    """If we crash between sandbox.discard() and _active.pop, the file is
    already gone and orphan_cleanup has nothing to remove. The registry
    entry is dropped only at the end of the success path."""
    store = OntologyStore()
    eng = SimulationEngine(
        ontology=store, snapshot_base_dir=str(tmp_path),
        cleanup_orphans_on_init=False,
    )
    contract = build_contract(
        simulation_id="sim_disc_order",
        branch_id="br_disc_order",
        source_project_id="proj_x",
        sot_version="1",
        masterplan_version="1",
    )
    eng.start(contract, in_memory=False)
    sandbox_path = eng._active[contract.simulation_id]["sandbox"].snapshot.path
    assert sandbox_path.exists()
    eng.discard(contract.simulation_id)
    assert not sandbox_path.exists()
    assert contract.simulation_id not in eng._active


# ---------------------------------------------------------------------------
# Crash recovery — orphan cleanup runs on engine init
# ---------------------------------------------------------------------------


def test_engine_init_runs_orphan_cleanup(tmp_path: Path) -> None:
    """A leftover sim_*_*.db with no active simulation must be removed
    when a fresh engine boots in the same base dir."""
    from sylion.aeis.testing.branches.snapshot import BranchSnapshot

    leftover = BranchSnapshot.create_for(
        branch_id="br_orphan", base_dir=tmp_path,
    )
    assert leftover.path.exists()
    # Boot engine — cleanup_orphans_on_init defaults True.
    SimulationEngine(
        ontology=OntologyStore(),
        snapshot_base_dir=str(tmp_path),
    )
    assert not leftover.path.exists()
