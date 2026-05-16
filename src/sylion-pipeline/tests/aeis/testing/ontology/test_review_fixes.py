"""Regression tests for the bugs surfaced during the triple review.

Each test pins the behavior reported by Codex / Kimi / gpt-oss so that
the next iteration cannot quietly regress it.
"""
from __future__ import annotations

import json
import threading

import pytest

from sylion.aeis.testing.ontology.objects import (
    Requirement,
    TestCharter,
)
from sylion.aeis.testing.ontology.store import (
    MAX_JSON_DEPTH,
    MAX_PAYLOAD_BYTES,
    OntologyStore,
    get_ontology_store,
    reset_ontology_store,
)
from tests.aeis.testing.ontology.fixtures import (
    make_charter,
    make_requirement,
)


# ---------------------------------------------------------------------------
# Codex bug #1 — route shadowing: reserved segments are rejected by _resolve_kind
# ---------------------------------------------------------------------------


def test_resolve_kind_rejects_reserved_segments() -> None:
    from fastapi import HTTPException

    from sylion.api.testing_routes import _resolve_kind

    for reserved in ("relations", "charters", "findings", "health", "objects"):
        with pytest.raises(HTTPException) as exc:
            _resolve_kind(reserved)
        assert exc.value.status_code == 404
        assert "reserved" in exc.value.detail.lower()


def test_dedicated_relations_route_registered_before_kind_route() -> None:
    """FastAPI matches in declaration order. Verify /relations/* comes first."""
    from sylion.api.testing_routes import router

    paths = [getattr(r, "path", "") for r in router.routes]
    relations_idx = next(
        i for i, p in enumerate(paths) if p.endswith("/relations/{src_id}")
    )
    kind_obj_idx = next(
        i for i, p in enumerate(paths) if p.endswith("/{kind}/{obj_id}")
    )
    assert relations_idx < kind_obj_idx, (
        f"/relations/* must register before /{{kind}}/{{obj_id}} (got "
        f"relations={relations_idx}, kind={kind_obj_idx})"
    )

    charters_idx = next(
        i for i, p in enumerate(paths)
        if p.endswith("/charters/{charter_id}/approve")
    )
    findings_idx = next(
        i for i, p in enumerate(paths)
        if p.endswith("/findings/{finding_id}/waive")
    )
    kind_idx = next(i for i, p in enumerate(paths) if p.endswith("/{kind}"))
    assert charters_idx < kind_idx
    assert findings_idx < kind_idx


# ---------------------------------------------------------------------------
# Codex bug #2 — list() must apply filter BEFORE pagination
# ---------------------------------------------------------------------------


def test_list_filter_applied_before_limit() -> None:
    """Ten rows total, half match. Limit=3 must yield 3 matching rows."""
    store = OntologyStore()
    for i in range(5):
        store.create(make_requirement(source="SoT", description=f"sot-{i}"))
    for i in range(5):
        store.create(make_requirement(source="Masterplan", description=f"mp-{i}"))

    sot_only = store.list(Requirement, filters={"source": "SoT"}, limit=3)
    assert len(sot_only) == 3
    assert all(r.source == "SoT" for r in sot_only)


def test_list_filter_consistent_across_pages() -> None:
    store = OntologyStore()
    for i in range(20):
        src = "SoT" if i % 2 == 0 else "Masterplan"
        store.create(make_requirement(source=src, description=f"row-{i}"))

    page1 = store.list(Requirement, filters={"source": "SoT"}, limit=5, offset=0)
    page2 = store.list(Requirement, filters={"source": "SoT"}, limit=5, offset=5)

    assert len(page1) == 5
    assert len(page2) == 5
    assert {r.req_id for r in page1}.isdisjoint({r.req_id for r in page2})


# ---------------------------------------------------------------------------
# Codex bug #3 / Kimi bug #2 — status transition enforced on update()
# ---------------------------------------------------------------------------


def test_charter_update_blocks_illegal_transition() -> None:
    store = OntologyStore()
    c = make_charter()  # status='draft'
    store.create(c)
    c.status = "approved"  # draft -> approved is illegal (must go via proposed)
    with pytest.raises(ValueError, match="illegal transition"):
        store.update(c)


def test_charter_update_allows_legal_transition() -> None:
    store = OntologyStore()
    c = make_charter()
    store.create(c)
    c.status = "proposed"
    store.update(c)
    c.status = "approved"
    store.update(c)
    refreshed = store.get(TestCharter, c.charter_id)
    assert refreshed is not None
    assert refreshed.status == "approved"


# ---------------------------------------------------------------------------
# Kimi bug #1 — JSON bomb / oversized payload defused on read
# ---------------------------------------------------------------------------


def test_deserialize_rejects_oversized_payload() -> None:
    store = OntologyStore()
    r = make_requirement()
    store.create(r)
    bloated = "x" * (MAX_PAYLOAD_BYTES + 10)
    store._conn.execute(
        "UPDATE w14_requirements SET payload = ? WHERE obj_id = ?",
        (bloated, r.req_id),
    )
    store._conn.commit()
    # _deserialize is wrapped in try/except inside list(); ensure get() raises.
    fetched = store.get(Requirement, r.req_id)
    assert fetched is None  # row exists but is unparseable -> treated as missing


def test_deserialize_rejects_overly_deep_payload() -> None:
    def deeply_nested(depth: int) -> dict:
        node: dict = {}
        head = node
        for _ in range(depth):
            head["k"] = {}
            head = head["k"]
        return node

    payload = json.dumps({
        "req_id": "req_deepf00d1234",
        "source": "SoT",
        "source_ref": "x",
        "criticality": "D2",
        "test_required": True,
        "description": "deep",
        "created_at": 1.0,
        "scope": deeply_nested(MAX_JSON_DEPTH + 5),
    })
    with pytest.raises(ValueError, match="nesting"):
        OntologyStore._deserialize(Requirement, payload)


# ---------------------------------------------------------------------------
# Kimi bug #3 — singleton init race
# ---------------------------------------------------------------------------


def test_get_ontology_store_concurrent_init_returns_same_instance() -> None:
    reset_ontology_store()
    instances: list[OntologyStore] = []
    barrier = threading.Barrier(20)

    def worker() -> None:
        barrier.wait()
        instances.append(get_ontology_store())

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    first = instances[0]
    assert all(inst is first for inst in instances)
    reset_ontology_store()


# ---------------------------------------------------------------------------
# Codex suggestion — TestCharter.project_id must use 'proj_' prefix and
#                    require_uuid_hex is now actually enforced on charter_id
# ---------------------------------------------------------------------------


def test_charter_rejects_project_id_without_prefix() -> None:
    with pytest.raises(ValueError, match="project_id"):
        make_charter(project_id="abc-no-prefix-123")


def test_charter_rejects_short_hex_tail() -> None:
    with pytest.raises(ValueError, match="charter_id"):
        TestCharter(
            charter_id="tc_short",
            project_id="proj_abc123def456",
            source_of_truth_version="1",
            masterplan_version="1",
            scope={"x": 1},
            required_test_classes=["T2"],
            required_personas=["operator"],
            required_evidence=["test_result"],
            release_blockers=["P0"],
            auto_repair_policy={},
            approval={"d_level": "D3"},
        )
