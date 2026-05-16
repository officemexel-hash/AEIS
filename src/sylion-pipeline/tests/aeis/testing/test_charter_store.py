"""CharterStore lifecycle tests."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.charter import (
    TRANSITIONS, VALID_STATUSES, CharterStore,
)
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import TestCharter


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def cs(store):
    return CharterStore(ontology=store)


def _new_charter(status="draft") -> TestCharter:
    return TestCharter(
        project_id="proj_x",
        source_of_truth_version="v1", masterplan_version="v1",
        scope={}, required_test_classes=["T2"],
        required_personas=["operator_beginner"],
        required_evidence=[], release_blockers=[],
        auto_repair_policy={}, approval={"d_level": "D3"},
        status=status,
    )


def test_valid_statuses_constant():
    assert set(VALID_STATUSES) == {
        "draft", "proposed", "approved", "rejected", "archived",
    }


def test_create_with_explicit_draft(cs, store):
    """TestCharter dataclass enforces valid status; CharterStore persists it."""
    c = TestCharter(
        project_id="proj_x", source_of_truth_version="v1",
        masterplan_version="v1", scope={}, required_test_classes=["T2"],
        required_personas=[], required_evidence=[], release_blockers=[],
        auto_repair_policy={}, approval={},
        status="draft",
    )
    persisted = cs.create(c)
    assert persisted.status == "draft"


def test_propose_draft_to_proposed(cs):
    c = cs.create(_new_charter("draft"))
    cs.propose(c.charter_id)
    assert cs.list_for_project("proj_x")[0].status == "proposed"


def test_approve_records_metadata(cs):
    c = cs.create(_new_charter("draft")); cs.propose(c.charter_id)
    cs.approve(c.charter_id, approver="operator", hg_ticket_id="hg_1",
                council_session_id="cs_1")
    fetched = cs.list_for_project("proj_x")[0]
    assert fetched.status == "approved"
    assert fetched.hg_ticket_id == "hg_1"
    assert fetched.council_session_id == "cs_1"
    assert fetched.approved_at is not None


def test_reject_from_draft(cs):
    c = cs.create(_new_charter("draft"))
    cs.reject(c.charter_id, reason="out of scope")
    assert cs.list_for_project("proj_x")[0].status == "rejected"


def test_archive_after_approval(cs):
    c = cs.create(_new_charter("draft")); cs.propose(c.charter_id)
    cs.approve(c.charter_id, approver="op")
    cs.archive(c.charter_id)
    assert cs.list_for_project("proj_x")[0].status == "archived"


def test_invalid_transition_raises(cs):
    c = cs.create(_new_charter("draft"))
    # draft -> approved is invalid (must propose first)
    with pytest.raises(ValueError, match="invalid transition"):
        cs.approve(c.charter_id, approver="op")


def test_archive_terminal(cs):
    c = cs.create(_new_charter("draft")); cs.propose(c.charter_id)
    cs.approve(c.charter_id, approver="op")
    cs.archive(c.charter_id)
    # archived -> anything is invalid
    with pytest.raises(ValueError, match="invalid transition"):
        cs.propose(c.charter_id)


def test_get_active_returns_most_recent_approved(cs):
    import time as _t
    c1 = cs.create(_new_charter("draft"))
    cs.propose(c1.charter_id)
    cs.approve(c1.charter_id, approver="op")
    _t.sleep(0.001)
    c2 = cs.create(_new_charter("draft"))
    cs.propose(c2.charter_id)
    cs.approve(c2.charter_id, approver="op")
    active = cs.get_active("proj_x")
    assert active is not None
    assert active.charter_id == c2.charter_id


def test_get_active_returns_none_when_no_approved(cs):
    cs.create(_new_charter("draft"))
    assert cs.get_active("proj_x") is None


def test_unknown_charter_raises(cs):
    with pytest.raises(ValueError, match="not found"):
        cs.propose("tc_doesnotexist")


def test_transitions_constant_complete():
    # Every valid status appears as a key
    for s in VALID_STATUSES:
        assert s in TRANSITIONS
    # archived is terminal
    assert TRANSITIONS["archived"] == set()
