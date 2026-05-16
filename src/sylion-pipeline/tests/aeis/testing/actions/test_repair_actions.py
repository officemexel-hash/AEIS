"""Tests for repair actions (4) — including HARD branch_id != main rule."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.actions.repair_actions import (
    ApplyPatchToBranchHandler, ApprovePatchHandler,
    ProposePatchHandler, RunRegressionHandler,
)
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import (
    Finding, RegressionRun,
)


@pytest.fixture
def store_with_finding():
    s = OntologyStore()
    f = Finding(
        severity="P1", d_level="D2",
        title="test finding", description="desc",
        discovered_by="test",
    )
    s.create(f)
    return s, f


def _propose_payload(finding_id, branch="br_repair_1"):
    return {
        "finding_id": finding_id,
        "branch_id": branch,
        "diff_text": "diff --git a/x b/x\n@@ +1 @@\n+fix",
        "files_touched": ["sylion/x.py"],
        "diff_lines_added": 1,
        "diff_lines_removed": 0,
        "tests_to_run": ["test_x"],
        "proposed_by": "claude",
    }


# -------- propose_patch HARD branch_id != main --------

def test_propose_patch_REJECTS_main_branch(store_with_finding):
    store, finding = store_with_finding
    h = ProposePatchHandler(ontology=store)
    payload = _propose_payload(finding.finding_id, branch="main")
    with pytest.raises(ValueError, match="MUST NOT be 'main'"):
        h.validate(payload)


def test_propose_patch_accepts_repair_branch(store_with_finding):
    store, finding = store_with_finding
    h = ProposePatchHandler(ontology=store)
    payload = _propose_payload(finding.finding_id, branch="br_repair_1")
    h.validate(payload)
    result = h.execute(payload, intent_id="i")
    assert result["status"] == "proposed"
    assert result["proposal_id"].startswith("patch_")


def test_propose_patch_marks_large_when_files_gt_5(store_with_finding):
    store, finding = store_with_finding
    h = ProposePatchHandler(ontology=store)
    payload = _propose_payload(finding.finding_id)
    payload["files_touched"] = [f"f{i}.py" for i in range(6)]
    h.validate(payload)
    result = h.execute(payload, intent_id="i")
    assert result["is_large"] is True


def test_propose_patch_marks_large_when_loc_gt_300(store_with_finding):
    store, finding = store_with_finding
    h = ProposePatchHandler(ontology=store)
    payload = _propose_payload(finding.finding_id)
    payload["diff_lines_added"] = 200
    payload["diff_lines_removed"] = 150
    h.validate(payload)
    result = h.execute(payload, intent_id="i")
    assert result["is_large"] is True


def test_propose_patch_rejects_empty_diff(store_with_finding):
    store, finding = store_with_finding
    h = ProposePatchHandler(ontology=store)
    payload = _propose_payload(finding.finding_id)
    payload["diff_text"] = ""
    with pytest.raises(ValueError, match="diff_text"):
        h.validate(payload)


def test_propose_patch_rejects_unknown_finding(store_with_finding):
    store, _ = store_with_finding
    h = ProposePatchHandler(ontology=store)
    payload = _propose_payload("find_doesnotexist")
    h.validate(payload)
    with pytest.raises(ValueError, match="finding not found"):
        h.execute(payload, intent_id="i")


# -------- approve_patch --------

def test_approve_patch_changes_status(store_with_finding):
    store, finding = store_with_finding
    p = ProposePatchHandler(ontology=store)
    payload = _propose_payload(finding.finding_id)
    p.validate(payload)
    proposed = p.execute(payload, intent_id="i1")

    a = ApprovePatchHandler(ontology=store)
    ap = {"proposal_id": proposed["proposal_id"], "approver": "op", "rationale": "ok"}
    a.validate(ap)
    result = a.execute(ap, intent_id="i2")
    assert result["status"] == "approved"


def test_approve_patch_requires_hg_for_large_patch(store_with_finding):
    store, finding = store_with_finding
    p = ProposePatchHandler(ontology=store)
    payload = _propose_payload(finding.finding_id)
    payload["files_touched"] = [f"f{i}.py" for i in range(7)]  # large
    p.validate(payload)
    proposed = p.execute(payload, intent_id="i1")

    a = ApprovePatchHandler(ontology=store)
    ap = {"proposal_id": proposed["proposal_id"], "approver": "op", "rationale": "x"}
    a.validate(ap)
    with pytest.raises(ValueError, match="hg_ticket_id REQUIRED"):
        a.execute(ap, intent_id="i2")


# -------- apply_patch_to_branch --------

def test_apply_patch_changes_status_to_applied(store_with_finding):
    store, finding = store_with_finding
    # propose + approve
    p = ProposePatchHandler(ontology=store)
    payload = _propose_payload(finding.finding_id)
    p.validate(payload)
    proposed = p.execute(payload, intent_id="i1")
    a = ApprovePatchHandler(ontology=store)
    ap = {"proposal_id": proposed["proposal_id"], "approver": "op", "rationale": "ok"}
    a.validate(ap)
    a.execute(ap, intent_id="i2")
    # apply
    ap_h = ApplyPatchToBranchHandler(ontology=store)
    apply_p = {"proposal_id": proposed["proposal_id"], "applied_by": "ci"}
    ap_h.validate(apply_p)
    result = ap_h.execute(apply_p, intent_id="i3")
    assert result["status"] == "applied"
    assert result["branch_id"] == "br_repair_1"


def test_apply_patch_rejects_non_approved(store_with_finding):
    store, finding = store_with_finding
    p = ProposePatchHandler(ontology=store)
    payload = _propose_payload(finding.finding_id)
    p.validate(payload)
    proposed = p.execute(payload, intent_id="i1")
    # do NOT approve
    ap_h = ApplyPatchToBranchHandler(ontology=store)
    apply_p = {"proposal_id": proposed["proposal_id"], "applied_by": "ci"}
    ap_h.validate(apply_p)
    with pytest.raises(ValueError, match="status must be approved"):
        ap_h.execute(apply_p, intent_id="i2")


# -------- run_regression --------

def test_run_regression_creates_record(store_with_finding):
    store, finding = store_with_finding
    h = RunRegressionHandler(ontology=store)
    p = {
        "finding_id": finding.finding_id,
        "pre_fix_run_id": "tr_pre",
        "post_fix_run_id": "tr_post",
        "neighbor_test_run_ids": ["tr_n1"],
    }
    h.validate(p)
    result = h.execute(p, intent_id="i")
    assert result["status"] == "pending"
    persisted = store.get(RegressionRun, result["regression_id"])
    assert persisted is not None
    assert persisted.finding_id == finding.finding_id
