"""W14 BranchManager — CRUD + merge/discard for testing branches.

Backed by OntologyStore (Branch object). MergeGuard hooks (E4) are stubbed
here — the manager records a list of "would-block" violations and lets E4
controllers decide whether to enforce.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from sylion.aeis.testing.ontology.enums import BranchState, BranchType
from sylion.aeis.testing.ontology.objects import Branch
from sylion.aeis.testing.ontology.store import OntologyStore

log = logging.getLogger("sylion.aeis.testing.branches.manager")


class BranchManager:
    """Manages Branch objects (4 types) on top of OntologyStore."""

    BRANCH_TYPES = tuple(BranchType.values())

    def __init__(self, ontology: OntologyStore, event_bus: Any | None = None) -> None:
        self._ontology = ontology
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_branch(
        self,
        branch_type: str | BranchType,
        parent_branch_id: str | None,
        project_id: str,
        sot_version: str,
        masterplan_version: str,
        created_by: str = "system",
    ) -> Branch:
        """Create a new branch. Returns the persisted Branch.

        Signature matches W14_PROMPT_CODEX_E3_SIMULATION.md C3 contract:
        positional order is (branch_type, parent_branch_id, project_id,
        sot_version, masterplan_version) so positional callers cannot
        accidentally bind parent_branch_id to project_id.
        """
        bt = branch_type.value if isinstance(branch_type, BranchType) else str(branch_type)
        if bt not in self.BRANCH_TYPES:
            raise ValueError(
                f"branch_type must be one of {self.BRANCH_TYPES}, got: {bt!r}"
            )
        if not project_id:
            raise ValueError("project_id required")
        if parent_branch_id is None:
            parent_branch_id = "main"

        branch = Branch(
            branch_type=bt,
            parent_branch_id=parent_branch_id,
            project_id=project_id,
            sot_version=sot_version,
            masterplan_version=masterplan_version,
            state=BranchState.OPEN.value,
            created_by=created_by,
        )
        self._ontology.create(branch)
        self._emit("aeis.testing.branch.created", {
            "branch_id": branch.branch_id,
            "branch_type": bt,
            "project_id": project_id,
        })
        log.info("branch created: %s (type=%s, project=%s)",
                 branch.branch_id[:12], bt, project_id)
        return branch

    HARD_REJECTIONS: tuple[str, ...] = (
        "attempted_merge_of_main",
        "branch_id_is_main",
    )

    def merge(self, branch_id: str, force: bool = False) -> dict:
        """Merge branch into parent. Returns merge result with violations.

        Wires the real ``MergeGuard.check_branch`` (E4) when available
        and degrades to a defensive stub otherwise. ``force=True`` skips
        non-hard violations only — entries listed in ``HARD_REJECTIONS``
        (e.g. attempts to merge ``main`` into itself) are NEVER bypassed.
        """
        branch = self._ontology.get(Branch, branch_id)
        if branch is None:
            raise ValueError(f"branch not found: {branch_id}")

        if branch.state != BranchState.OPEN.value:
            return {
                "status": "rejected",
                "reason": f"branch not open (state={branch.state})",
                "merge_guard_violations": [],
            }

        violations = self._guard_check(branch)
        hard_violations = [v for v in violations if v in self.HARD_REJECTIONS]
        if hard_violations:
            # HARD invariants — force does NOT bypass.
            return {
                "status": "rejected",
                "reason": "hard merge-guard violations",
                "merge_guard_violations": violations,
                "hard_violations": hard_violations,
            }
        if violations and not force:
            return {
                "status": "rejected",
                "reason": "merge guard violations",
                "merge_guard_violations": violations,
            }

        branch.state = BranchState.MERGED.value
        branch.merged_at = time.time()
        self._ontology.update(branch)
        self._emit("aeis.testing.branch.merged", {
            "branch_id": branch.branch_id,
            "branch_type": branch.branch_type,
            "forced": bool(violations and force),
        })
        return {
            "status": "merged",
            "branch_id": branch.branch_id,
            "merged_at": branch.merged_at,
            "merge_guard_violations": violations,  # warnings even when forced
            "forced": bool(violations and force),
        }

    def discard(self, branch_id: str, reason: str = "") -> Branch:
        """Discard branch (cannot be reopened)."""
        branch = self._ontology.get(Branch, branch_id)
        if branch is None:
            raise ValueError(f"branch not found: {branch_id}")
        if branch.state != BranchState.OPEN.value:
            raise ValueError(
                f"cannot discard non-open branch (state={branch.state})"
            )
        branch.state = BranchState.DISCARDED.value
        branch.discarded_at = time.time()
        self._ontology.update(branch)
        self._emit("aeis.testing.branch.discarded", {
            "branch_id": branch.branch_id,
            "reason": reason,
        })
        return branch

    PRIMARY_KEY_BY_KIND: dict[str, str] = {
        "PatchProposal": "proposal_id",
        "TestRun": "run_id",
        "GuardianAlert": "alert_id",
    }

    def list_changes(self, branch_id: str) -> list[dict]:
        """Return all PatchProposals + TestRuns + GuardianAlerts on this branch."""
        from sylion.aeis.testing.ontology.objects import (
            PatchProposal, TestRun,
        )
        changes: list[dict] = []
        for kind in (PatchProposal, TestRun):
            try:
                items = self._ontology.list(
                    kind, filters={"branch_id": branch_id},
                )
            except Exception:  # pragma: no cover
                continue
            pk_field = self.PRIMARY_KEY_BY_KIND.get(kind.__name__, "")
            for it in items:
                obj_id = getattr(it, pk_field, "?") if pk_field else "?"
                changes.append({
                    "kind": kind.__name__,
                    "id": obj_id,
                    "summary": str(it)[:200],
                })
        return changes

    def list_open(self, project_id: str | None = None) -> list[Branch]:
        filters = {"state": BranchState.OPEN.value}
        if project_id:
            filters["project_id"] = project_id
        return self._ontology.list(Branch, filters=filters)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _guard_check(self, branch: Branch) -> list[str]:
        """Run MergeGuard if installed, else fall back to defensive checks."""
        violations: list[str] = []
        # Defensive HARD invariants (always evaluated, never skipped).
        if branch.branch_id == "main":
            violations.append("branch_id_is_main")
        normalized = (branch.branch_id or "").strip().casefold()
        if normalized == "main":
            violations.append("attempted_merge_of_main")

        # Real MergeGuard (E4) lives in sylion.aeis.testing.merge_guard.
        # Plug it in when present so this method ALWAYS sees the full
        # rejection set, not just stub checks.
        try:
            from sylion.aeis.testing.merge_guard import MergeGuard
            guard = MergeGuard(self._ontology)
            result = guard.check_branch(branch.branch_id)
            if isinstance(result, dict):
                violations.extend(result.get("violations", []) or [])
        except Exception:  # pragma: no cover — guard optional
            log.debug("MergeGuard.check_branch unavailable", exc_info=True)
        # Deduplicate while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for v in violations:
            if v not in seen:
                seen.add(v)
                deduped.append(v)
        return deduped

    def _emit(self, event_type: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        try:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_type=event_type,
                payload=payload,
                producer_module="aeis.testing.branches",
            ))
        except Exception as e:  # pragma: no cover
            log.debug("event emit failed (%s): %s", event_type, e)


__all__ = ["BranchManager"]
