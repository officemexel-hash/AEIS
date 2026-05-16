"""Adversarial tests for the W14 ontology store.

These tests probe the failure surface: malformed input, race conditions,
oversized payloads, SQL injection attempts, FK dangling, and rollback /
re-application of the migration.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import threading
from pathlib import Path

import pytest

from sylion.aeis.testing.ontology.objects import (
    Finding,
    PatchProposal,
    Requirement,
    SimulationContract,
    TestCharter,
)
from sylion.aeis.testing.ontology.store import OntologyStore
from tests.aeis.testing.ontology.fixtures import (
    make_charter,
    make_finding,
    make_loop_report,
    make_patch,
    make_requirement,
    make_simulation_contract,
)


# ---------------------------------------------------------------------------
# 1. Invalid id prefixes are rejected at construction time
# ---------------------------------------------------------------------------


def test_invalid_id_prefix_rejected_for_requirement() -> None:
    with pytest.raises(ValueError, match="req_id"):
        Requirement(
            req_id="bad_prefix_12345678",
            source="SoT",
            source_ref="x",
            description="d",
        )


def test_invalid_id_prefix_rejected_for_finding() -> None:
    with pytest.raises(ValueError, match="finding_id"):
        Finding(
            finding_id="finding-without-underscore",
            title="x",
            description="y",
            discovered_by="z",
        )


# ---------------------------------------------------------------------------
# 2. D-level above D5 / arbitrary enum violation rejected
# ---------------------------------------------------------------------------


def test_d_level_above_d5_rejected() -> None:
    with pytest.raises(ValueError, match="d_level"):
        make_finding(d_level="D6")


def test_loop_type_outside_set_rejected() -> None:
    with pytest.raises(ValueError, match="loop_type"):
        make_loop_report(loop_type="alien_loop")


# ---------------------------------------------------------------------------
# 3. Foreign-key dangling: link a non-existent obj — store accepts the link
#    edge (we treat relations as a graph layer) but get_related must NOT
#    surface non-existent ids as if they were live objects.
# ---------------------------------------------------------------------------


def test_dangling_link_does_not_resurrect_object() -> None:
    store = OntologyStore()
    store.link("req_phantom", "find_phantom", "discovered")
    # Both ids are referenced in relations but neither object exists.
    assert store.get(Requirement, "req_phantom") is None
    assert store.get(Finding, "find_phantom") is None
    # Relation row exists.
    assert store.get_related("req_phantom", "discovered") == ["find_phantom"]


# ---------------------------------------------------------------------------
# 4. Duplicate id constraint — race-condition style probe
# ---------------------------------------------------------------------------


def test_duplicate_id_rejected_after_first_insert() -> None:
    store = OntologyStore()
    r = make_requirement()
    store.create(r)
    dup = make_requirement(req_id=r.req_id)
    with pytest.raises(ValueError, match="Duplicate"):
        store.create(dup)


def test_concurrent_inserts_same_id_only_one_wins() -> None:
    store = OntologyStore()
    base = make_requirement()
    barrier = threading.Barrier(8)
    failures: list[Exception] = []

    def worker() -> None:
        try:
            barrier.wait()
            r = make_requirement(req_id=base.req_id)
            store.create(r)
        except ValueError as exc:
            failures.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(failures) == 7
    assert store.count(Requirement) == 1


# ---------------------------------------------------------------------------
# 5. Huge payload (1MB+) survives JSON round-trip
# ---------------------------------------------------------------------------


def test_huge_payload_persists_and_round_trips() -> None:
    store = OntologyStore()
    blob = "x" * (1024 * 1024 + 7)  # > 1 MB
    r = make_requirement()
    r.description = blob
    store.create(r)
    fetched = store.get(Requirement, r.req_id)
    assert fetched is not None
    assert len(fetched.description) == len(blob)


# ---------------------------------------------------------------------------
# 6. SQL-injection attempt via filter values
# ---------------------------------------------------------------------------


def test_sql_injection_in_filter_does_not_drop_table() -> None:
    store = OntologyStore()
    for _ in range(5):
        store.create(make_requirement())
    bad_filter = {"source": "'); DROP TABLE w14_requirements; --"}
    items = store.list(Requirement, filters=bad_filter)
    assert items == []
    # Table is intact and queryable.
    assert store.count(Requirement) == 5


def test_sql_injection_in_id_does_not_break_get() -> None:
    store = OntologyStore()
    r = make_requirement()
    store.create(r)
    # Crafted id should simply miss; no exception, no table loss.
    assert store.get(Requirement, "req_xx'); DROP TABLE x; --") is None
    assert store.count(Requirement) == 1


# ---------------------------------------------------------------------------
# 7. Self-relation rejected at API surface
# ---------------------------------------------------------------------------


def test_self_relation_rejected_for_link() -> None:
    store = OntologyStore()
    with pytest.raises(ValueError, match="self-relations"):
        store.link("anything", "anything", "rel")


# ---------------------------------------------------------------------------
# 8. Round-trip with an unknown extra field is tolerated (forward-compat)
# ---------------------------------------------------------------------------


def test_unknown_field_in_persisted_payload_is_dropped_on_read() -> None:
    store = OntologyStore()
    r = make_requirement()
    store.create(r)
    # Inject an extra field via raw SQL to simulate forward-compat row.
    payload = store._conn.execute(
        "SELECT payload FROM w14_requirements WHERE obj_id = ?",
        (r.req_id,),
    ).fetchone()["payload"]
    data = json.loads(payload)
    data["future_field"] = "ignore-me"
    store._conn.execute(
        "UPDATE w14_requirements SET payload = ? WHERE obj_id = ?",
        (json.dumps(data), r.req_id),
    )
    fetched = store.get(Requirement, r.req_id)
    assert fetched is not None
    assert not hasattr(fetched, "future_field")


# ---------------------------------------------------------------------------
# 9. Migration up + down + up round-trip is clean
# ---------------------------------------------------------------------------


def test_migration_round_trip_idempotent() -> None:
    mig_path = (
        Path(__file__).resolve().parents[4]
        / "sylion" / "db" / "migrations" / "0001_w14_ontology.py"
    )
    spec = importlib.util.spec_from_file_location("m0001", str(mig_path))
    assert spec is not None and spec.loader is not None
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)

    conn = sqlite3.connect(":memory:")
    up_result = mig.up(conn)
    assert up_result["direction"] == "up"
    table_count = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'w14_%'"
    ).fetchone()[0]
    assert table_count == 27

    down_result = mig.down(conn)
    assert down_result["direction"] == "down"
    remaining = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'w14_%'"
    ).fetchone()[0]
    assert remaining == 0

    # Re-apply must succeed.
    re_up = mig.up(conn)
    assert re_up["direction"] == "up"
    conn.close()


# ---------------------------------------------------------------------------
# 10. Hard semantic invariants survive store round-trip
# ---------------------------------------------------------------------------


def test_simulation_contract_hard_safety_round_trip() -> None:
    store = OntologyStore()
    sc = make_simulation_contract()
    store.create(sc)
    fetched = store.get(SimulationContract, sc.contract_id)
    assert fetched is not None
    assert fetched.safety["max_runtime_seconds"] <= 3600
    assert fetched.safety["max_cost_usd"] <= 10.0


def test_patch_branch_main_constraint_persists() -> None:
    store = OntologyStore()
    p = make_patch()
    store.create(p)
    fetched = store.get(PatchProposal, p.proposal_id)
    assert fetched is not None
    assert fetched.branch_id != "main"


def test_charter_status_only_legal_transitions_succeed() -> None:
    store = OntologyStore()
    c = make_charter(status="draft")
    store.create(c)
    c.status = "proposed"
    store.update(c)
    refetched = store.get(TestCharter, c.charter_id)
    assert refetched is not None
    assert refetched.status == "proposed"


# ---------------------------------------------------------------------------
# 11. Bus failures do not corrupt state (subscriber raising)
# ---------------------------------------------------------------------------


def test_subscriber_exception_does_not_break_create() -> None:
    from sylion.core.event_bus import EventBus

    bus = EventBus()

    def boom(_event):
        raise RuntimeError("subscriber blew up")

    bus.subscribe("aeis.testing.ontology.created", boom)
    store = OntologyStore(event_bus=bus)
    r = make_requirement()
    store.create(r)
    assert store.get(Requirement, r.req_id) is not None
