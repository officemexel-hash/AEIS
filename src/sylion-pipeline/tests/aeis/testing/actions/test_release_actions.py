"""Tests for release actions (3) including unresolved P0/P1 blocking."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.actions.release_actions import (
    CloseLoopAsBlockedHandler, PromoteReleaseCandidateHandler,
    RollbackReleaseHandler,
)
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import (
    Finding, LoopReport, ReleaseCandidate,
)


@pytest.fixture
def store():
    return OntologyStore()


def _promote_payload(branch="br_release", findings=None):
    return {
        "branch_id": branch,
        "project_id": "proj_demo",
        "hg_ticket_id": "hg_promote_1",
        "evidence_pack_id": "ep_1",
        "test_run_summary": {"passed": 50, "failed": 0},
        "unresolved_findings": findings or [],
    }


# -------- promote_release_candidate --------

def test_promote_creates_rc(store):
    h = PromoteReleaseCandidateHandler(ontology=store)
    p = _promote_payload()
    h.validate(p)
    result = h.execute(p, intent_id="i")
    assert result["rc_id"].startswith("rc_")
    assert result["gate_status"] == "RELEASE_CANDIDATE"


def test_promote_REJECTS_main_branch(store):
    h = PromoteReleaseCandidateHandler(ontology=store)
    p = _promote_payload(branch="main")
    with pytest.raises(ValueError, match="MUST NOT be 'main'"):
        h.validate(p)


def test_promote_BLOCKS_unresolved_p1(store):
    f = Finding(
        severity="P1", d_level="D3",
        title="bug", description="open",
        discovered_by="test",
    )
    store.create(f)
    h = PromoteReleaseCandidateHandler(ontology=store)
    p = _promote_payload(findings=[f.finding_id])
    h.validate(p)
    with pytest.raises(ValueError, match="P1.*blocks release"):
        h.execute(p, intent_id="i")


def test_promote_allows_resolved_p1(store):
    f = Finding(
        severity="P1", d_level="D3",
        title="bug", description="fixed",
        discovered_by="test",
        r_status="VERIFIED",
    )
    store.create(f)
    h = PromoteReleaseCandidateHandler(ontology=store)
    p = _promote_payload(findings=[f.finding_id])
    h.validate(p)
    result = h.execute(p, intent_id="i")
    assert result["rc_id"]


def test_promote_rejects_non_dict_summary(store):
    h = PromoteReleaseCandidateHandler(ontology=store)
    p = _promote_payload()
    p["test_run_summary"] = "not a dict"
    with pytest.raises(ValueError, match="must be dict"):
        h.validate(p)


# -------- rollback_release --------

def test_rollback_creates_decision(store):
    # First promote
    p = PromoteReleaseCandidateHandler(ontology=store)
    pp = _promote_payload()
    p.validate(pp)
    promoted = p.execute(pp, intent_id="i1")

    r = RollbackReleaseHandler(ontology=store)
    rp = {
        "rc_id": promoted["rc_id"],
        "hg_ticket_id": "hg_rollback_1",
        "rollback_reason": "p0 in production",
        "rollback_plan": {"steps": ["disable", "revert"]},
    }
    r.validate(rp)
    result = r.execute(rp, intent_id="i2")
    assert result["status"] == "rollback"
    rc = store.get(ReleaseCandidate, promoted["rc_id"])
    assert rc.gate_status == "ROLLBACK_REQUIRED"


def test_rollback_rejects_empty_plan(store):
    h = RollbackReleaseHandler(ontology=store)
    rp = {
        "rc_id": "rc_x", "hg_ticket_id": "hg",
        "rollback_reason": "x", "rollback_plan": {},
    }
    with pytest.raises(ValueError, match="non-empty dict"):
        h.validate(rp)


def test_rollback_rejects_bad_rc_prefix(store):
    h = RollbackReleaseHandler(ontology=store)
    rp = {
        "rc_id": "wrong_id", "hg_ticket_id": "hg",
        "rollback_reason": "x", "rollback_plan": {"a": 1},
    }
    with pytest.raises(ValueError, match="rc_"):
        h.validate(rp)


# -------- close_loop_as_blocked --------

def test_close_loop_with_accept(store):
    # Setup: finding + loop report
    f = Finding(severity="P2", d_level="D3", title="x",
                description="d", discovered_by="t")
    store.create(f)
    lr = LoopReport(
        finding_id=f.finding_id, loop_type="same_failure",
        attempts_n=3, similarity_score=0.95,
        suspected_root_cause=["spec ambiguous"],
        blocked_actions=["further_auto_patch"],
        required_decision={"type": "Human Gate", "suggested_d_level": "D3"},
    )
    store.create(lr)

    h = CloseLoopAsBlockedHandler(ontology=store)
    p = {
        "finding_id": f.finding_id,
        "loop_report_id": lr.report_id,
        "hg_ticket_id": "hg_x",
        "human_decision": "accept_known_issue",
        "rationale": "low impact, ship next quarter",
    }
    h.validate(p)
    result = h.execute(p, intent_id="i")
    assert result["r_status"] == "CLOSED"


def test_close_loop_with_reassign_escalates(store):
    f = Finding(severity="P1", d_level="D4", title="x",
                description="d", discovered_by="t")
    store.create(f)
    lr = LoopReport(
        finding_id=f.finding_id, loop_type="no_progress",
        attempts_n=2, similarity_score=0.7,
        suspected_root_cause=["wrong contract"],
        blocked_actions=["further_auto_patch"],
        required_decision={"type": "Human Gate", "suggested_d_level": "D3"},
    )
    store.create(lr)
    h = CloseLoopAsBlockedHandler(ontology=store)
    p = {
        "finding_id": f.finding_id,
        "loop_report_id": lr.report_id,
        "hg_ticket_id": "hg_x",
        "human_decision": "reassign",
        "rationale": "needs senior",
    }
    h.validate(p)
    result = h.execute(p, intent_id="i")
    assert result["r_status"] == "ESCALATED"


def test_close_loop_rejects_bad_decision(store):
    h = CloseLoopAsBlockedHandler(ontology=store)
    p = {
        "finding_id": "find_x", "loop_report_id": "lr_x",
        "hg_ticket_id": "hg", "human_decision": "ignore_it",
        "rationale": "x",
    }
    with pytest.raises(ValueError, match="human_decision"):
        h.validate(p)
