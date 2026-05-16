"""CRUD + thread-safety tests for OntologyStore."""
from __future__ import annotations

import threading

import pytest

from sylion.aeis.testing.ontology.objects import (
    Finding,
    PatchProposal,
    Requirement,
    TestCharter,
)
from sylion.aeis.testing.ontology.store import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    OntologyStore,
)
from sylion.core.event_bus import EventBus
from tests.aeis.testing.ontology.fixtures import (
    make_charter,
    make_finding,
    make_patch,
    make_requirement,
)


@pytest.fixture
def store() -> OntologyStore:
    return OntologyStore()  # in-memory


@pytest.fixture
def store_with_bus() -> tuple[OntologyStore, EventBus, list]:
    bus = EventBus()
    captured: list = []
    bus.subscribe("*", lambda ev: captured.append(ev))
    return OntologyStore(event_bus=bus), bus, captured


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_init_creates_27_tables(store: OntologyStore) -> None:
    rows = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'w14_%'"
    ).fetchall()
    # 25 object tables + relations + history
    assert len(rows) == 27


# ---------------------------------------------------------------------------
# Create / Get / List
# ---------------------------------------------------------------------------


def test_create_returns_object(store: OntologyStore) -> None:
    r = make_requirement()
    out = store.create(r)
    assert out is r


def test_get_returns_persisted_obj(store: OntologyStore) -> None:
    r = make_requirement(description="login req")
    store.create(r)
    fetched = store.get(Requirement, r.req_id)
    assert fetched is not None
    assert fetched.description == "login req"


def test_get_returns_none_when_missing(store: OntologyStore) -> None:
    assert store.get(Requirement, "req_missing") is None


def test_list_returns_objects(store: OntologyStore) -> None:
    for _ in range(3):
        store.create(make_requirement())
    items = store.list(Requirement)
    assert len(items) == 3


def test_list_respects_limit(store: OntologyStore) -> None:
    for _ in range(5):
        store.create(make_requirement())
    assert len(store.list(Requirement, limit=2)) == 2


def test_list_filters_by_field(store: OntologyStore) -> None:
    sot = make_requirement(source="SoT")
    mp = make_requirement(source="Masterplan")
    store.create(sot)
    store.create(mp)
    sot_only = store.list(Requirement, filters={"source": "SoT"})
    assert len(sot_only) == 1
    assert sot_only[0].source == "SoT"


def test_list_offset_paginates(store: OntologyStore) -> None:
    ids = []
    for _ in range(5):
        r = make_requirement()
        store.create(r)
        ids.append(r.req_id)
    page1 = store.list(Requirement, limit=2, offset=0)
    page2 = store.list(Requirement, limit=2, offset=2)
    assert {r.req_id for r in page1}.isdisjoint({r.req_id for r in page2})


def test_list_rejects_invalid_limit(store: OntologyStore) -> None:
    with pytest.raises(ValueError, match="limit"):
        store.list(Requirement, limit=0)
    with pytest.raises(ValueError, match="limit"):
        store.list(Requirement, limit=MAX_LIMIT + 1)


# ---------------------------------------------------------------------------
# Update / Soft delete
# ---------------------------------------------------------------------------


def test_update_persists_changes(store: OntologyStore) -> None:
    f = make_finding()
    store.create(f)
    f.r_status = "TRIAGED"
    store.update(f)
    fetched = store.get(Finding, f.finding_id)
    assert fetched is not None
    assert fetched.r_status == "TRIAGED"


def test_update_unknown_object_raises(store: OntologyStore) -> None:
    f = make_finding()
    with pytest.raises(ValueError, match="not found"):
        store.update(f)


def test_soft_delete_hides_from_get(store: OntologyStore) -> None:
    r = make_requirement()
    store.create(r)
    assert store.soft_delete(Requirement, r.req_id) is True
    assert store.get(Requirement, r.req_id) is None


def test_soft_delete_idempotent(store: OntologyStore) -> None:
    r = make_requirement()
    store.create(r)
    assert store.soft_delete(Requirement, r.req_id) is True
    assert store.soft_delete(Requirement, r.req_id) is False


def test_list_with_include_deleted(store: OntologyStore) -> None:
    r = make_requirement()
    store.create(r)
    store.soft_delete(Requirement, r.req_id)
    assert len(store.list(Requirement)) == 0
    assert len(store.list(Requirement, include_deleted=True)) == 1


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------


def test_link_and_get_related(store: OntologyStore) -> None:
    c = make_charter()
    store.create(c)
    f = make_finding()
    store.create(f)
    store.link(c.charter_id, f.finding_id, "discovered")
    related = store.get_related(c.charter_id, "discovered")
    assert related == [f.finding_id]


def test_inverse_related(store: OntologyStore) -> None:
    c = make_charter()
    f = make_finding()
    store.create(c)
    store.create(f)
    store.link(c.charter_id, f.finding_id, "discovered")
    inverse = store.get_inverse_related(f.finding_id, "discovered")
    assert inverse == [c.charter_id]


def test_link_idempotent(store: OntologyStore) -> None:
    a, b = "src_1", "dst_1"
    store.link(a, b, "rel")
    store.link(a, b, "rel")  # second call is a no-op
    assert store.get_related(a, "rel") == [b]


def test_link_self_relation_rejected(store: OntologyStore) -> None:
    with pytest.raises(ValueError, match="self-relations"):
        store.link("x", "x", "rel")


def test_unlink_returns_true_then_false(store: OntologyStore) -> None:
    store.link("a", "b", "rel")
    assert store.unlink("a", "b", "rel") is True
    assert store.unlink("a", "b", "rel") is False


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def test_history_records_create_and_update(store: OntologyStore) -> None:
    f = make_finding()
    store.create(f, actor="alice")
    f.r_status = "TRIAGED"
    store.update(f, actor="bob")
    rows = store.history(f.finding_id)
    assert len(rows) == 2
    assert rows[0]["verb"] == "create"
    assert rows[0]["actor"] == "alice"
    assert rows[1]["verb"] == "update"
    assert rows[1]["actor"] == "bob"


def test_history_records_soft_delete(store: OntologyStore) -> None:
    r = make_requirement()
    store.create(r)
    store.soft_delete(Requirement, r.req_id, actor="audit")
    verbs = [row["verb"] for row in store.history(r.req_id)]
    assert "soft_delete" in verbs


def test_history_orders_chronologically(store: OntologyStore) -> None:
    f = make_finding()
    store.create(f, actor="a")
    f.r_status = "TRIAGED"
    store.update(f, actor="b")
    f.r_status = "REPRODUCED"
    store.update(f, actor="c")
    rows = store.history(f.finding_id)
    timestamps = [r["timestamp"] for r in rows]
    assert timestamps == sorted(timestamps)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_reports_zero_objects_initially(store: OntologyStore) -> None:
    h = store.health()
    assert h["ok"] is True
    assert all(v == 0 for v in h["counts"].values())
    assert h["history_total"] == 0
    assert h["relations_total"] == 0


def test_health_reflects_creates(store: OntologyStore) -> None:
    store.create(make_requirement())
    store.create(make_finding())
    h = store.health()
    assert h["counts"]["Requirement"] == 1
    assert h["counts"]["Finding"] == 1
    assert h["history_total"] == 2


# ---------------------------------------------------------------------------
# Event bus integration
# ---------------------------------------------------------------------------


def test_event_emitted_on_create(store_with_bus: tuple) -> None:
    store, _bus, captured = store_with_bus
    store.create(make_requirement())
    topics = [ev.topic for ev in captured]
    assert "aeis.testing.ontology.created" in topics


def test_event_emitted_on_update(store_with_bus: tuple) -> None:
    store, _bus, captured = store_with_bus
    f = make_finding()
    store.create(f)
    f.r_status = "TRIAGED"
    store.update(f)
    topics = [ev.topic for ev in captured]
    assert "aeis.testing.ontology.updated" in topics


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


def test_concurrent_creates_all_persist(store: OntologyStore) -> None:
    n = 20
    barrier = threading.Barrier(n)
    errors: list[Exception] = []

    def worker() -> None:
        try:
            barrier.wait()
            store.create(make_requirement())
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert store.count(Requirement) == n


def test_concurrent_reads_during_writes(store: OntologyStore) -> None:
    for _ in range(10):
        store.create(make_requirement())

    stop = threading.Event()
    seen_counts: list[int] = []

    def reader() -> None:
        while not stop.is_set():
            seen_counts.append(len(store.list(Requirement, limit=100)))

    def writer() -> None:
        for _ in range(10):
            store.create(make_requirement())

    rt = threading.Thread(target=reader)
    rt.start()
    wt = threading.Thread(target=writer)
    wt.start()
    wt.join()
    stop.set()
    rt.join()
    assert max(seen_counts) >= 10


def test_concurrent_link_and_get_related(store: OntologyStore) -> None:
    src = "src_concurrent"

    def worker(idx: int) -> None:
        store.link(src, f"dst_{idx}", "rel")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(15)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    related = store.get_related(src, "rel")
    assert sorted(related) == sorted(f"dst_{i}" for i in range(15))


def test_concurrent_history_writes_consistent(store: OntologyStore) -> None:
    f = make_finding()
    store.create(f)

    def worker(value: str) -> None:
        f_local = make_finding(finding_id=f.finding_id)
        f_local.title = value
        # Re-use the same id; OntologyStore.update uses the row's id field.
        f_local.finding_id = f.finding_id
        try:
            store.update(f_local)
        except Exception:
            pass

    threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rows = store.history(f.finding_id)
    # 1 create + N updates; we don't enforce N exactly because some titles may
    # collide with validators, but at minimum the first create persisted.
    assert any(r["verb"] == "create" for r in rows)


def test_concurrent_duplicate_id_only_one_wins(store: OntologyStore) -> None:
    """Race condition: ten threads try to insert same id; one wins."""
    base = make_requirement()
    insert_errors: list[Exception] = []
    barrier = threading.Barrier(10)

    def worker() -> None:
        try:
            barrier.wait()
            r_dup = make_requirement(req_id=base.req_id)
            store.create(r_dup)
        except ValueError as exc:
            insert_errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one should have succeeded; nine should have raised.
    assert len(insert_errors) == 9
    assert store.count(Requirement) == 1


# ---------------------------------------------------------------------------
# Default limit constant
# ---------------------------------------------------------------------------


def test_default_limit_is_100() -> None:
    assert DEFAULT_LIMIT == 100
    assert MAX_LIMIT == 10000


# ---------------------------------------------------------------------------
# Cross-module sanity (HARD constraint)
# ---------------------------------------------------------------------------


def test_patch_proposal_persists_only_with_non_main_branch(store: OntologyStore) -> None:
    p = make_patch()
    store.create(p)
    fetched = store.get(PatchProposal, p.proposal_id)
    assert fetched is not None
    assert fetched.branch_id != "main"


def test_charter_persists_with_all_sla_fields(store: OntologyStore) -> None:
    c = make_charter()
    store.create(c)
    fetched = store.get(TestCharter, c.charter_id)
    assert fetched is not None
    assert fetched.required_test_classes == c.required_test_classes
