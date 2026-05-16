"""BranchManager tests."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.branches import BranchManager
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import Branch


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def mgr(store):
    return BranchManager(ontology=store)


def _create(mgr, branch_type="repair", project_id="proj_x",
            parent="main", created_by="system"):
    return mgr.create_branch(
        branch_type,
        parent_branch_id=parent,
        project_id=project_id,
        sot_version="sot_v1",
        masterplan_version="mp_v1",
        created_by=created_by,
    )


def test_create_simulation_branch(mgr, store):
    b = _create(mgr, "simulation")
    assert b.branch_id.startswith("br_")
    assert b.branch_type == "simulation"
    assert b.state == "open"
    assert store.get(Branch, b.branch_id) is not None


def test_create_repair_branch(mgr):
    b = _create(mgr, "repair", created_by="auto_repair")
    assert b.branch_type == "repair"


def test_create_test_branch(mgr):
    b = _create(mgr, "test")
    assert b.branch_type == "test"


def test_create_release_branch(mgr):
    b = _create(mgr, "release")
    assert b.branch_type == "release"


def test_create_rejects_unknown_type(mgr):
    with pytest.raises(ValueError, match="branch_type"):
        _create(mgr, "invalid_type")


def test_create_rejects_missing_project(mgr):
    with pytest.raises(ValueError, match="project_id"):
        _create(mgr, "repair", project_id="")


def test_merge_open_branch(mgr, store):
    b = _create(mgr, "repair")
    result = mgr.merge(b.branch_id)
    assert result["status"] == "merged"
    assert result["merged_at"] > 0
    persisted = store.get(Branch, b.branch_id)
    assert persisted.state == "merged"


def test_merge_unknown_branch_raises(mgr):
    with pytest.raises(ValueError, match="not found"):
        mgr.merge("br_doesnotexist")


def test_merge_already_merged_rejected(mgr):
    b = _create(mgr, "repair")
    mgr.merge(b.branch_id)  # first
    result = mgr.merge(b.branch_id)  # again
    assert result["status"] == "rejected"
    assert "not open" in result["reason"]


def test_discard_open_branch(mgr, store):
    b = _create(mgr, "simulation")
    discarded = mgr.discard(b.branch_id, reason="test cleanup")
    assert discarded.state == "discarded"
    assert store.get(Branch, b.branch_id).state == "discarded"


def test_discard_merged_rejected(mgr):
    b = _create(mgr, "repair")
    mgr.merge(b.branch_id)
    with pytest.raises(ValueError, match="cannot discard"):
        mgr.discard(b.branch_id)


def test_list_open_filters_by_project(mgr):
    _create(mgr, "repair", project_id="proj_a")
    _create(mgr, "test", project_id="proj_a")
    _create(mgr, "release", project_id="proj_b")
    a = mgr.list_open("proj_a")
    b = mgr.list_open("proj_b")
    assert len(a) == 2
    assert len(b) == 1


def test_list_changes_returns_empty_for_new_branch(mgr):
    b = _create(mgr, "repair")
    assert mgr.list_changes(b.branch_id) == []
