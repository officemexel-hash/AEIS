"""Regression tests for the W14 E4 review-fix pass.

Each test pins an issue surfaced by Codex / Kimi / self-audit on
auto_repair_controller / loop_governor / merge_guard.
"""
from __future__ import annotations

import threading
import time

import pytest

from sylion.aeis.testing.auto_repair_controller import (
    AutoRepairController,
)
from sylion.aeis.testing.loop_governor import (
    DEFAULT_LIMITS, LoopGovernor,
)
from sylion.aeis.testing.merge_guard import MergeGuard, REJECTIONS
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import (
    Branch, Finding, LoopReport, RepairAttempt,
)


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def finding(store):
    f = Finding(severity="P1", d_level="D3", title="x",
                description="d", discovered_by="t", r_status="OPEN")
    store.create(f)
    return f


# ---------------------------------------------------------------------------
# Codex bug — class-level constants on contract surface
# ---------------------------------------------------------------------------


def test_loop_governor_defaults_is_class_attribute() -> None:
    assert hasattr(LoopGovernor, "DEFAULTS")
    assert isinstance(LoopGovernor.DEFAULTS, dict)
    assert LoopGovernor.DEFAULTS == DEFAULT_LIMITS
    assert LoopGovernor.DEFAULTS["max_auto_fix_attempts_per_finding"] == 2


def test_merge_guard_rejections_is_class_attribute() -> None:
    assert hasattr(MergeGuard, "REJECTIONS")
    assert MergeGuard.REJECTIONS == REJECTIONS
    assert len(MergeGuard.REJECTIONS) == 8


# ---------------------------------------------------------------------------
# Codex bug — start_repair returns str, not RepairSession
# ---------------------------------------------------------------------------


def test_start_repair_returns_str(store, finding) -> None:
    ctrl = AutoRepairController(ontology=store)
    out = ctrl.start_repair(finding.finding_id)
    assert isinstance(out, str)
    assert out.startswith("ars_")


# ---------------------------------------------------------------------------
# Codex bug — start_repair creates a Branch type='repair'
# ---------------------------------------------------------------------------


def test_start_repair_persists_repair_branch(store, finding) -> None:
    ctrl = AutoRepairController(ontology=store)
    sid = ctrl.start_repair(finding.finding_id)
    sess = ctrl.get_session(sid)
    branch = store.get(Branch, sess["branch_id"])
    assert branch is not None
    assert branch.branch_type == "repair"
    assert branch.parent_branch_id == "main"
    assert branch.state == "open"


# ---------------------------------------------------------------------------
# Codex bug — step() owns merge-guard validation at terminal phases
# ---------------------------------------------------------------------------


def test_step_invokes_merge_guard_at_verified(store, finding) -> None:
    ctrl = AutoRepairController(ontology=store)
    sid = ctrl.start_repair(finding.finding_id)
    # Simulate a context where the merge guard finds a violation.
    result = ctrl.step(
        sid, "VERIFIED",
        merge_context={
            "changed_files": ["tests/test_login.py"],
            "diff_text": "--- a/tests/test_login.py\n+++ /dev/null\n",
        },
    )
    assert result["blocked"] is True
    assert "merge_guard_violation" in result["reason"]
    assert "mandatory_test_deleted" in result["violations"]


# ---------------------------------------------------------------------------
# Kimi attack #3 — parallel-session guard for same finding
# ---------------------------------------------------------------------------


def test_parallel_start_repair_for_same_finding_rejected(store, finding) -> None:
    ctrl = AutoRepairController(ontology=store)
    ctrl.start_repair(finding.finding_id)
    with pytest.raises(RuntimeError, match="already has an active"):
        ctrl.start_repair(finding.finding_id)


def test_concurrent_start_repair_only_one_wins(store) -> None:
    """Two threads racing on start_repair for the same finding: exactly one
    wins; the loser sees RuntimeError. Ensures the lock actually serializes."""
    f = Finding(severity="P2", d_level="D2", title="x",
                description="d", discovered_by="t", r_status="OPEN")
    store.create(f)
    ctrl = AutoRepairController(ontology=store)
    results: list = []

    def worker():
        try:
            results.append(ctrl.start_repair(f.finding_id))
        except RuntimeError as exc:
            results.append(exc)

    barrier = threading.Barrier(8)

    def race():
        barrier.wait()
        worker()

    threads = [threading.Thread(target=race) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    successes = [r for r in results if isinstance(r, str)]
    failures = [r for r in results if isinstance(r, RuntimeError)]
    assert len(successes) == 1
    assert len(failures) == 7


# ---------------------------------------------------------------------------
# Codex bug — step() rejects illegal backward transitions
# ---------------------------------------------------------------------------


def test_step_forward_only(store, finding) -> None:
    ctrl = AutoRepairController(ontology=store)
    sid = ctrl.start_repair(finding.finding_id)
    ctrl.step(sid, "REPRODUCED")
    ctrl.step(sid, "CLASSIFIED")
    with pytest.raises(ValueError, match="illegal transition"):
        ctrl.step(sid, "OPEN")


def test_step_allows_regression_loopback(store, finding) -> None:
    """REGRESSION_FAILED is a legal loopback from REPAIRING."""
    ctrl = AutoRepairController(ontology=store)
    sid = ctrl.start_repair(finding.finding_id)
    ctrl.step(sid, "REPRODUCED")
    ctrl.step(sid, "CLASSIFIED")
    ctrl.step(sid, "REPAIR_PROPOSED",
              attempt_payload={"files_touched_count": 1, "diff_lines": 5})
    ctrl.step(sid, "REPAIRING",
              attempt_payload={"files_touched_count": 1, "diff_lines": 5})
    # Loopback into REGRESSION_FAILED then back to REPAIRING is allowed.
    result = ctrl.step(sid, "REGRESSION_FAILED")
    assert result["next_status"] == "REGRESSION_FAILED"


# ---------------------------------------------------------------------------
# Kimi attack #4 — LoopReport idempotency
# ---------------------------------------------------------------------------


def test_loop_report_idempotent_per_finding_loop_type(store, finding) -> None:
    """Two block calls on the same (finding, loop_type) reuse the same report."""
    # Pre-create 2 attempts to trip the limit.
    for n in (1, 2):
        store.create(RepairAttempt(
            finding_id=finding.finding_id, n=n, r_phase="REPAIRING",
            result="failed_same", files_touched_count=1, diff_lines=5,
            time_in_phase_s=10.0, completed_at=time.time(),
        ))
    gov = LoopGovernor(ontology=store)
    r1 = gov.check(finding.finding_id)
    r2 = gov.check(finding.finding_id)
    assert r1["loop_report_id"] == r2["loop_report_id"]
    reports = store.list(LoopReport, filters={"finding_id": finding.finding_id},
                         limit=10)
    assert len(reports) == 1


# ---------------------------------------------------------------------------
# Kimi/Codex — defensive int coercion in LoopGovernor + MergeGuard
# ---------------------------------------------------------------------------


def test_loop_governor_accepts_garbage_int_payload(store, finding) -> None:
    gov = LoopGovernor(ontology=store)
    out = gov.check(finding.finding_id, attempt_payload={
        "files_touched_count": "not-a-number",
        "diff_lines": float("nan"),
    })
    # Must not raise — bad values are coerced to 0 with a logged warning.
    assert out["allowed"] is True


def test_merge_guard_accepts_garbage_int_count(store) -> None:
    branch = Branch(
        branch_type="repair", parent_branch_id="main",
        project_id="proj_x", sot_version="v1", masterplan_version="v1",
        created_by="alice",
    )
    store.create(branch)
    guard = MergeGuard(ontology=store)
    result = guard.check_branch(
        branch.branch_id,
        context={"new_p0_p1_count": "definitely-not-int"},
    )
    # Bad coercion -> default 0 -> rule does not trigger.
    assert "new_p0_p1_failure_introduced" not in result.get("violations", [])


# ---------------------------------------------------------------------------
# MergeGuard — case/whitespace folding on 'main' invariant
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("evil", ["main", "MAIN", " main ", "Main\n", "mAiN"])
def test_merge_guard_rejects_main_variants(store, evil: str) -> None:
    guard = MergeGuard(ontology=store)
    result = guard.check_branch(evil)
    assert result["allowed"] is False
    assert "attempted_merge_of_main" in result["violations"]


# ---------------------------------------------------------------------------
# MergeGuard — case-insensitive heuristics for test deletion / weakening
# ---------------------------------------------------------------------------


def test_merge_guard_detects_weakened_assertion_case_insensitive(store) -> None:
    branch = Branch(
        branch_type="repair", parent_branch_id="main",
        project_id="proj_x", sot_version="v1", masterplan_version="v1",
        created_by="alice",
    )
    store.create(branch)
    guard = MergeGuard(ontology=store)
    diff = "@@ -1 +1 @@\n-    ASSERT user.is_admin\n+    pass\n"
    result = guard.check_branch(branch.branch_id, context={"diff_text": diff})
    assert "assertion_weakened_without_hg" in result["violations"]


def test_merge_guard_detects_test_deletion_with_backslash_path(store) -> None:
    branch = Branch(
        branch_type="repair", parent_branch_id="main",
        project_id="proj_x", sot_version="v1", masterplan_version="v1",
        created_by="alice",
    )
    store.create(branch)
    guard = MergeGuard(ontology=store)
    result = guard.check_branch(branch.branch_id, context={
        "changed_files": ["Tests\\test_login.py"],
        "diff_text": "--- a/tests/test_login.py\n+++ /dev/null\n",
    })
    assert "mandatory_test_deleted" in result["violations"]


# ---------------------------------------------------------------------------
# LoopGovernor — _suspect_root_cause uses canonical loop_type values
# ---------------------------------------------------------------------------


def test_suspect_root_cause_uses_canonical_loop_types() -> None:
    causes = LoopGovernor._suspect_root_cause([], "scope_drift")
    assert "scope_too_large_for_auto_repair" in causes
    causes = LoopGovernor._suspect_root_cause([], "new_failures")
    assert "patch_breaks_neighboring_modules" in causes
    causes = LoopGovernor._suspect_root_cause([], "test_modification")
    assert "test_was_weakened_or_skipped_to_pass" in causes
