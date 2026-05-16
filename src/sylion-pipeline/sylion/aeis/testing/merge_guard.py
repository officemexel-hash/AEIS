"""W14 Merge Guard — 8 structural rejections at merge time.

Per docs/CLAUDE_AEIS_W14_TESTING.md sec 9. Rejects merge when ANY of:

  1. mandatory_test_deleted
  2. assertion_weakened_without_hg
  3. mock_added_to_pass_live_test
  4. source_of_truth_changed_without_change_proposal
  5. masterplan_changed_without_change_proposal
  6. new_p0_p1_failure_introduced
  7. evidence_missing
  8. loop_governor_status_not_clear

The MergeGuard is consulted by BranchManager.merge() (E4 hookup) and by the
external Auto-Repair Controller before applying patches.
"""
from __future__ import annotations

import logging
from typing import Any

from sylion.aeis.testing.ontology.objects import (
    Branch, Finding, LoopReport, PatchProposal,
)
from sylion.aeis.testing.ontology.store import OntologyStore

log = logging.getLogger("sylion.aeis.testing.merge_guard")


# Module-level alias kept for backward compatibility; the contract surface
# is ``MergeGuard.REJECTIONS`` (class attribute below).
REJECTIONS: tuple[str, ...] = (
    "mandatory_test_deleted",
    "assertion_weakened_without_hg",
    "mock_added_to_pass_live_test",
    "source_of_truth_changed_without_change_proposal",
    "masterplan_changed_without_change_proposal",
    "new_p0_p1_failure_introduced",
    "evidence_missing",
    "loop_governor_status_not_clear",
)


class MergeGuard:
    """Check a branch for the 8 structural rejections before merge."""

    # Contract surface (W14_INTEGRATION_CONTRACTS.md C4): the canonical
    # rejection set is published on the class itself.
    REJECTIONS: tuple[str, ...] = REJECTIONS

    def __init__(self, ontology: OntologyStore) -> None:
        self._ontology = ontology

    def check_branch(self, branch_id: str, context: dict | None = None) -> dict:
        """Return {'allowed': bool, 'violations': list[str]}.

        `context` may include hints from the caller:
          - changed_files: list[str]
          - diff_text: str
          - sot_changed: bool, sot_change_proposal_id: str | None
          - masterplan_changed: bool, mp_change_proposal_id: str | None
          - has_evidence_pack: bool
          - new_p0_p1_count: int
        """
        ctx = context or {}
        violations: list[str] = []

        # Defensive: case/whitespace-folded match against 'main' BEFORE
        # we hit the store, so a tampered id can't sneak past.
        if isinstance(branch_id, str) and branch_id.strip().casefold() == "main":
            return {"allowed": False, "violations": ["attempted_merge_of_main"]}

        branch = self._ontology.get(Branch, branch_id)
        if branch is None:
            return {"allowed": False, "violations": ["branch_not_found"]}
        if isinstance(branch.branch_id, str) and \
                branch.branch_id.strip().casefold() == "main":
            return {"allowed": False, "violations": ["attempted_merge_of_main"]}

        # 1. Test deletion (heuristic on changed_files)
        changed = ctx.get("changed_files") or []
        if any(self._is_mandatory_test_deletion(f, ctx) for f in changed):
            violations.append("mandatory_test_deleted")

        # 2. Assertion weakening (heuristic on diff_text)
        diff = ctx.get("diff_text", "")
        if self._has_weakened_assertion(diff) and not ctx.get("hg_ticket_id"):
            violations.append("assertion_weakened_without_hg")

        # 3. Mock added to pass live test
        if self._has_mock_in_live_test(diff, changed):
            violations.append("mock_added_to_pass_live_test")

        # 4. SoT changed without proposal
        if ctx.get("sot_changed") and not ctx.get("sot_change_proposal_id"):
            violations.append("source_of_truth_changed_without_change_proposal")

        # 5. Masterplan changed without proposal
        if ctx.get("masterplan_changed") and not ctx.get("mp_change_proposal_id"):
            violations.append("masterplan_changed_without_change_proposal")

        # 6. New P0/P1 failures introduced (caller supplied count)
        if self._safe_int(ctx.get("new_p0_p1_count"), "new_p0_p1_count") > 0:
            violations.append("new_p0_p1_failure_introduced")

        # 7. Evidence missing for this branch's patch proposals
        if not self._has_evidence(branch_id, ctx):
            violations.append("evidence_missing")

        # 8. Loop governor still has open block on related findings
        if self._loop_governor_blocked(branch_id):
            violations.append("loop_governor_status_not_clear")

        return {
            "allowed": len(violations) == 0,
            "violations": violations,
        }

    @staticmethod
    def _safe_int(value: Any, field_name: str, default: int = 0) -> int:
        """Coerce caller-supplied int values; bad input -> default+log."""
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            log.warning(
                "merge_guard: invalid %s=%r, using default %d",
                field_name, value, default,
            )
            return default

    # ------------------------------------------------------------------
    # Heuristics
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_path(file_path: str) -> str:
        """Lower-case + forward-slash so 'Tests\\Foo.py' compares cleanly."""
        if not isinstance(file_path, str):
            return ""
        return file_path.replace("\\", "/").casefold()

    @staticmethod
    def _is_mandatory_test_deletion(file_path: str, ctx: dict) -> bool:
        if not isinstance(file_path, str):
            return False
        norm = MergeGuard._normalize_path(file_path)
        if not (norm.startswith("tests/") and norm.endswith(".py")):
            return False
        # diff_text may use either the original or the normalized path.
        diff = (ctx.get("diff_text", "") or "").casefold()
        # Match either backslash or forward slash variant.
        for variant in (file_path, file_path.replace("\\", "/"), norm):
            if (
                f"--- a/{variant.casefold()}" in diff
                and "+++ /dev/null" in diff
            ):
                return True
        return False

    @staticmethod
    def _has_weakened_assertion(diff_text: str) -> bool:
        if not diff_text:
            return False
        # Heuristic: a removed `assert X == Y` not replaced by an equally
        # strong one. Comparison is case-insensitive so 'Assert' / 'ASSERT'
        # cannot slip the check.
        lower = diff_text.casefold()
        markers = ("-    assert ", "-assert ", "@pytest.mark.skip",
                   "@pytest.mark.xfail")
        return any(m in lower for m in markers)

    @staticmethod
    def _has_mock_in_live_test(diff_text: str, changed_files: list[str]) -> bool:
        if not diff_text:
            return False
        # Mock added to a non-test file is fine; mock added to "live" test or
        # production module is suspicious.
        live_files = [
            f for f in (changed_files or [])
            if not MergeGuard._normalize_path(f).startswith("tests/")
            and not MergeGuard._normalize_path(f).endswith("_mock.ts")
        ]
        if not live_files:
            return False
        lower = diff_text.casefold()
        markers = ("+from unittest.mock import", "+import mock",
                   "+magicmock(", "+mock()", "+ patch(",
                   "+monkeypatch.setattr", "+mocker.patch")
        return any(m in lower for m in markers)

    def _has_evidence(self, branch_id: str, ctx: dict) -> bool:
        if ctx.get("has_evidence_pack") is True:
            return True
        # Check: any proposed patch on this branch has an applied status?
        proposals = self._ontology.list(
            PatchProposal, filters={"branch_id": branch_id}, limit=1000,
        )
        if not proposals:
            # No patches -> no evidence required (e.g. test branch)
            return True
        # If there are proposals, require at least one applied AND linked Finding
        applied = [p for p in proposals if p.status == "applied"]
        return bool(applied)

    def _loop_governor_blocked(self, branch_id: str) -> bool:
        """Any finding with active LoopReport blocks merge."""
        proposals = self._ontology.list(
            PatchProposal, filters={"branch_id": branch_id}, limit=1000,
        )
        finding_ids = {p.finding_id for p in proposals}
        for fid in finding_ids:
            reports = self._ontology.list(
                LoopReport, filters={"finding_id": fid}, limit=10,
            )
            if reports:
                # Active LoopReport exists -> finding must be CLOSED/WAIVED
                f = self._ontology.get(Finding, fid)
                if f is None:
                    return True
                if f.r_status not in ("CLOSED", "WAIVED_BY_HUMAN", "VERIFIED"):
                    return True
        return False


__all__ = ["MergeGuard", "REJECTIONS"]
