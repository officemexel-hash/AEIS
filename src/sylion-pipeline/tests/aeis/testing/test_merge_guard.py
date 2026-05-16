"""MergeGuard tests — 8 structural rejections."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.merge_guard import REJECTIONS, MergeGuard
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import (
    Branch, Finding, LoopReport, PatchProposal,
)


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def guard(store):
    return MergeGuard(ontology=store)


@pytest.fixture
def branch(store):
    b = Branch(branch_type="repair", project_id="proj_x",
               sot_version="v1", masterplan_version="v1",
               state="open", created_by="auto")
    store.create(b)
    return b


# -------- REJECTIONS list --------

def test_rejections_has_8_canonical_items():
    assert len(REJECTIONS) == 8
    expected = (
        "mandatory_test_deleted",
        "assertion_weakened_without_hg",
        "mock_added_to_pass_live_test",
        "source_of_truth_changed_without_change_proposal",
        "masterplan_changed_without_change_proposal",
        "new_p0_p1_failure_introduced",
        "evidence_missing",
        "loop_governor_status_not_clear",
    )
    assert REJECTIONS == expected


# -------- check_branch --------

def test_check_clean_branch_allowed(guard, branch):
    result = guard.check_branch(branch.branch_id, context={
        "changed_files": [], "diff_text": "",
        "has_evidence_pack": True,
    })
    assert result["allowed"] is True


def test_check_unknown_branch_rejected(guard):
    result = guard.check_branch("br_unknown")
    assert result["allowed"] is False
    assert "branch_not_found" in result["violations"]


def test_check_main_always_rejected(guard, store):
    # Direct branch_id="main" must be rejected
    result = guard.check_branch("main")
    assert result["allowed"] is False
    # Either branch_not_found or attempted_merge_of_main
    violations = result["violations"]
    assert any(v in ("branch_not_found", "attempted_merge_of_main") for v in violations)


def test_check_blocks_test_deletion(guard, branch):
    result = guard.check_branch(branch.branch_id, context={
        "changed_files": ["tests/test_foo.py"],
        "diff_text": "--- a/tests/test_foo.py\n+++ /dev/null\n",
        "has_evidence_pack": True,
    })
    assert result["allowed"] is False
    assert "mandatory_test_deleted" in result["violations"]


def test_check_blocks_assertion_weakening_without_hg(guard, branch):
    result = guard.check_branch(branch.branch_id, context={
        "changed_files": ["tests/test_x.py"],
        "diff_text": "-    assert result == 42\n+    # removed\n",
        "has_evidence_pack": True,
        "hg_ticket_id": None,
    })
    assert result["allowed"] is False
    assert "assertion_weakened_without_hg" in result["violations"]


def test_check_allows_assertion_weakening_with_hg(guard, branch):
    result = guard.check_branch(branch.branch_id, context={
        "changed_files": ["tests/test_x.py"],
        "diff_text": "-    assert result == 42\n+    pass\n",
        "has_evidence_pack": True,
        "hg_ticket_id": "hg_approved",
    })
    # No assertion_weakened violation (other checks may still flag — focus on this)
    assert "assertion_weakened_without_hg" not in result["violations"]


def test_check_blocks_mock_in_live_test(guard, branch):
    result = guard.check_branch(branch.branch_id, context={
        "changed_files": ["sylion/api/foo_routes.py"],
        "diff_text": "+from unittest.mock import MagicMock\n+m = MagicMock()\n",
        "has_evidence_pack": True,
    })
    assert result["allowed"] is False
    assert "mock_added_to_pass_live_test" in result["violations"]


def test_check_blocks_sot_change_without_proposal(guard, branch):
    result = guard.check_branch(branch.branch_id, context={
        "sot_changed": True, "sot_change_proposal_id": None,
        "has_evidence_pack": True,
    })
    assert result["allowed"] is False
    assert "source_of_truth_changed_without_change_proposal" in result["violations"]


def test_check_blocks_masterplan_change_without_proposal(guard, branch):
    result = guard.check_branch(branch.branch_id, context={
        "masterplan_changed": True, "mp_change_proposal_id": None,
        "has_evidence_pack": True,
    })
    assert result["allowed"] is False
    assert "masterplan_changed_without_change_proposal" in result["violations"]


def test_check_blocks_new_p0_p1(guard, branch):
    result = guard.check_branch(branch.branch_id, context={
        "new_p0_p1_count": 1,
        "has_evidence_pack": True,
    })
    assert result["allowed"] is False
    assert "new_p0_p1_failure_introduced" in result["violations"]


def test_check_blocks_loop_governor_active(guard, branch, store):
    # Create patch proposal on this branch + finding + loop report
    f = Finding(severity="P1", d_level="D3", title="x",
                description="d", discovered_by="t", r_status="REPAIRING")
    store.create(f)
    p = PatchProposal(
        finding_id=f.finding_id, branch_id=branch.branch_id,
        diff_text="x", files_touched=["a.py"],
        diff_lines_added=1, diff_lines_removed=0,
        tests_to_run=["t"], proposed_by="auto", status="proposed",
    )
    store.create(p)
    lr = LoopReport(
        finding_id=f.finding_id, loop_type="same_failure",
        attempts_n=2, similarity_score=0.9,
        suspected_root_cause=["x"], blocked_actions=["further_auto_patch"],
        required_decision={"type": "Human Gate"},
    )
    store.create(lr)

    result = guard.check_branch(branch.branch_id, context={
        "has_evidence_pack": True,
    })
    assert result["allowed"] is False
    assert "loop_governor_status_not_clear" in result["violations"]
