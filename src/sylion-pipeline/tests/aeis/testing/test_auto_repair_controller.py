"""AutoRepairController tests — R0..R9 lifecycle integration."""
from __future__ import annotations

import time
import pytest

from sylion.aeis.testing.auto_repair_controller import (
    AutoRepairController, PHASES_ORDER,
)
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.enums import RStatus
from sylion.aeis.testing.ontology.objects import Branch, Finding, RepairAttempt


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def controller(store):
    return AutoRepairController(ontology=store)


@pytest.fixture
def finding(store):
    f = Finding(severity="P1", d_level="D3", title="x",
                description="d", discovered_by="t", r_status="OPEN")
    store.create(f)
    return f


def _make_branch(store) -> str:
    b = Branch(
        branch_type="repair", parent_branch_id="main",
        project_id="proj_repair", sot_version="v1", masterplan_version="v1",
        state="open", created_by="alice",
    )
    store.create(b)
    return b.branch_id


# -------- start_repair --------


def test_start_repair_creates_session(controller, finding):
    sid = controller.start_repair(finding.finding_id)
    assert isinstance(sid, str)
    assert sid.startswith("ars_")
    sess = controller.get_session(sid)
    assert sess["finding_id"] == finding.finding_id
    assert sess["branch_id"].startswith("br_")  # auto-created repair branch
    assert sess["blocked"] is False


def test_start_repair_creates_repair_branch(controller, store, finding):
    """C4 contract: start_repair must materialize a Branch type='repair'."""
    sid = controller.start_repair(finding.finding_id)
    sess = controller.get_session(sid)
    branch = store.get(Branch, sess["branch_id"])
    assert branch is not None
    assert branch.branch_type == "repair"


def test_start_repair_uses_caller_supplied_branch(controller, store, finding):
    branch_id = _make_branch(store)
    sid = controller.start_repair(finding.finding_id, branch_id=branch_id)
    sess = controller.get_session(sid)
    assert sess["branch_id"] == branch_id


def test_start_repair_unknown_finding_raises(controller):
    with pytest.raises(ValueError, match="not found"):
        controller.start_repair("find_doesnotexist")


def test_start_repair_blocked_when_loop_governor_blocks(store, finding):
    # Pre-create 2 attempts to trip max_auto_fix_attempts
    for n in range(1, 3):
        store.create(RepairAttempt(
            finding_id=finding.finding_id, n=n, r_phase="REPAIRING",
            result="failed_same", files_touched_count=1, diff_lines=5,
            time_in_phase_s=10.0, completed_at=time.time(),
        ))
    controller = AutoRepairController(ontology=store)
    sid = controller.start_repair(finding.finding_id)
    sess = controller.get_session(sid)
    assert sess["blocked"] is True
    assert sess["block_reason"] == "max_auto_fix_attempts_per_finding"
    assert sess["loop_report_id"] is not None


def test_start_repair_rejects_parallel_session(controller, finding):
    """Kimi attack #3: only one open session per finding."""
    controller.start_repair(finding.finding_id)
    with pytest.raises(RuntimeError, match="already has an active"):
        controller.start_repair(finding.finding_id)


# -------- step --------


def test_step_transitions_finding_status(controller, store, finding):
    sid = controller.start_repair(finding.finding_id)
    result = controller.step(sid, RStatus.REPRODUCED.value)
    assert result["next_status"] == "REPRODUCED"
    assert result["blocked"] is False
    assert store.get(Finding, finding.finding_id).r_status == "REPRODUCED"


def test_step_classified_then_repair_proposed(controller, finding):
    sid = controller.start_repair(finding.finding_id)
    controller.step(sid, "REPRODUCED")
    controller.step(sid, "CLASSIFIED")
    result = controller.step(
        sid, "REPAIR_PROPOSED",
        attempt_payload={"files_touched_count": 1, "diff_lines": 10},
    )
    assert result["next_status"] == "REPAIR_PROPOSED"
    assert result["attempts"] == 1


def test_step_repairing_creates_repair_attempt(controller, store, finding):
    sid = controller.start_repair(finding.finding_id)
    controller.step(sid, "REPRODUCED")
    controller.step(sid, "CLASSIFIED")
    controller.step(sid, "REPAIR_PROPOSED",
                    attempt_payload={"files_touched_count": 1, "diff_lines": 5})
    controller.step(sid, "REPAIRING",
                    attempt_payload={"files_touched_count": 1, "diff_lines": 5,
                                     "patch_proposal_id": "patch_x"})
    attempts = store.list(
        RepairAttempt, filters={"finding_id": finding.finding_id}, limit=10,
    )
    assert len(attempts) == 2  # propose + repair


def test_step_blocked_when_loop_governor_trips(controller, store, finding):
    sid = controller.start_repair(finding.finding_id)
    controller.step(sid, "REPRODUCED")
    controller.step(sid, "CLASSIFIED")
    # First attempt OK
    controller.step(sid, "REPAIR_PROPOSED",
                    attempt_payload={"files_touched_count": 1, "diff_lines": 5})
    # Second attempt OK (still <2)
    controller.step(sid, "REPAIR_PROPOSED",
                    attempt_payload={"files_touched_count": 1, "diff_lines": 5})
    # Third attempt: now 2 attempts persisted -> Loop Governor should block
    result = controller.step(sid, "REPAIR_PROPOSED",
                             attempt_payload={"files_touched_count": 1, "diff_lines": 5})
    assert result["blocked"] is True
    assert "max_auto_fix_attempts" in result["reason"]


def test_step_unknown_session_raises(controller):
    with pytest.raises(ValueError, match="session not found"):
        controller.step("ars_unknown", "REPRODUCED")


def test_step_invalid_phase_raises(controller, finding):
    sid = controller.start_repair(finding.finding_id)
    with pytest.raises(ValueError, match="invalid target_phase"):
        controller.step(sid, "NOT_A_REAL_PHASE")


def test_step_rejects_illegal_backward_transition(controller, finding):
    """Codex bug: forward-only along PHASES_ORDER."""
    sid = controller.start_repair(finding.finding_id)
    controller.step(sid, "REPRODUCED")
    controller.step(sid, "CLASSIFIED")
    with pytest.raises(ValueError, match="illegal transition"):
        controller.step(sid, "OPEN")  # backward not allowed


def test_step_allows_terminal_jump_to_closed(controller, finding):
    """Terminal statuses (CLOSED/ESCALATED/WAIVED) bypass forward-only."""
    sid = controller.start_repair(finding.finding_id)
    # Branch was auto-created so MergeGuard sees a real Branch.
    result = controller.step(sid, "CLOSED",
                             merge_context={"has_evidence_pack": True})
    # MergeGuard might still block (loop governor / evidence checks),
    # but the transition itself must be syntactically allowed.
    assert "next_status" in result


# -------- list_sessions --------


def test_list_sessions_blocked_only(store):
    f1 = Finding(severity="P1", d_level="D3", title="x",
                 description="d", discovered_by="t")
    f2 = Finding(severity="P2", d_level="D3", title="y",
                 description="d", discovered_by="t")
    store.create(f1)
    store.create(f2)

    # Pre-block f1 by creating 2 failed attempts
    for n in range(1, 3):
        store.create(RepairAttempt(
            finding_id=f1.finding_id, n=n, r_phase="REPAIRING",
            result="failed_same", files_touched_count=1, diff_lines=5,
            time_in_phase_s=10.0, completed_at=time.time(),
        ))

    controller = AutoRepairController(ontology=store)
    controller.start_repair(f1.finding_id)  # blocked
    controller.start_repair(f2.finding_id)  # ok

    blocked = controller.list_sessions(blocked_only=True)
    assert len(blocked) == 1
    assert blocked[0]["finding_id"] == f1.finding_id


def test_phases_order_constant():
    assert PHASES_ORDER[0] == "OPEN"
    assert PHASES_ORDER[-1] == "CLOSED"
    assert "WAITING_FOR_HUMAN_GATE" in PHASES_ORDER


def test_get_session_returns_dict_or_none(controller, finding):
    """C4 contract: get_session returns a dict, not RepairSession."""
    sid = controller.start_repair(finding.finding_id)
    sess = controller.get_session(sid)
    assert isinstance(sess, dict)
    assert sess["session_id"] == sid
    assert controller.get_session("ars_nonexistent") is None
