"""W14 repair actions (4): propose_patch / approve_patch / apply_patch / run_regression."""
from __future__ import annotations

from sylion.aeis.testing.actions.base import TestingActionHandler
from sylion.aeis.testing.ontology.enums import DLevel, GateType
from sylion.aeis.testing.ontology.objects import (
    Finding, PatchProposal, RegressionRun,
)


class ProposePatchHandler(TestingActionHandler):
    target_action: str = "propose_patch"
    d_level: DLevel = DLevel.D2
    phase: str = "TWO_PHASE"
    mirror_to_ticket: bool = True
    gate_type: GateType = GateType.NON_BLOCKING

    LARGE_PATCH_FILES = 5
    LARGE_PATCH_LOC = 300

    def validate(self, payload: dict) -> None:
        self._require_keys(
            payload, "finding_id", "branch_id", "diff_text",
            "files_touched", "diff_lines_added", "diff_lines_removed",
            "tests_to_run", "proposed_by",
        )
        self._require_prefix(payload, "finding_id", "find_")
        # HARD: branch_id != "main"
        self._require_not_main(payload, "branch_id")
        files = payload["files_touched"]
        if not isinstance(files, list) or len(files) == 0:
            raise ValueError("propose_patch: files_touched must be non-empty list")
        if not isinstance(payload["diff_text"], str) or len(payload["diff_text"]) == 0:
            raise ValueError("propose_patch: diff_text must be non-empty")
        tests = payload["tests_to_run"]
        if not isinstance(tests, list) or len(tests) == 0:
            raise ValueError("propose_patch: tests_to_run must be non-empty list")

    def execute(self, payload: dict, intent_id: str) -> dict:
        if self.ontology is None:
            raise RuntimeError("propose_patch: ontology not configured")
        # Defensive: re-check branch_id even if execute is invoked without a
        # prior validate() call (validator-bypass attack vector).
        self._require_not_main(payload, "branch_id")
        finding = self.ontology.get(Finding, payload["finding_id"])
        if finding is None:
            raise ValueError(f"finding not found: {payload['finding_id']}")

        proposal = PatchProposal(
            finding_id=payload["finding_id"],
            branch_id=payload["branch_id"],
            diff_text=payload["diff_text"],
            files_touched=list(payload["files_touched"]),
            diff_lines_added=int(payload["diff_lines_added"]),
            diff_lines_removed=int(payload["diff_lines_removed"]),
            risk_assessment=payload.get("risk_assessment", {}),
            tests_to_run=list(payload["tests_to_run"]),
            status="proposed",
            proposed_by=payload["proposed_by"],
        )
        self.ontology.create(proposal)
        try:
            self.ontology.link(finding.finding_id, proposal.proposal_id, "patches")
        except Exception:
            pass

        # Large patch -> escalate gate to BLOCKING
        is_large = (
            len(proposal.files_touched) > self.LARGE_PATCH_FILES
            or (proposal.diff_lines_added + proposal.diff_lines_removed)
            > self.LARGE_PATCH_LOC
        )
        ticket_id = self._mirror_ticket(
            project_id="",
            title=f"Patch proposal for {finding.finding_id}",
            summary=(
                f"{len(proposal.files_touched)} files, "
                f"+{proposal.diff_lines_added}/-{proposal.diff_lines_removed} LOC"
            ),
            payload={
                "proposal_id": proposal.proposal_id,
                "finding_id": finding.finding_id,
                "branch_id": proposal.branch_id,
                "is_large": is_large,
            },
            gate_type_override=GateType.BLOCKING if is_large else None,
        )

        self._emit("aeis.testing.repair.proposed", {
            "proposal_id": proposal.proposal_id,
            "finding_id": finding.finding_id,
            "is_large": is_large,
        }, trace_id=intent_id)
        return {
            "proposal_id": proposal.proposal_id,
            "status": "proposed",
            "is_large": is_large,
            "ticket_id": ticket_id,
        }


class ApprovePatchHandler(TestingActionHandler):
    target_action: str = "approve_patch"
    d_level: DLevel = DLevel.D3
    phase: str = "TWO_PHASE"
    mirror_to_ticket: bool = True
    gate_type: GateType = GateType.PRODUCTION

    def validate(self, payload: dict) -> None:
        self._require_keys(payload, "proposal_id", "approver", "rationale")
        self._require_prefix(payload, "proposal_id", "patch_")

    def execute(self, payload: dict, intent_id: str) -> dict:
        if self.ontology is None:
            raise RuntimeError("approve_patch: ontology not configured")
        proposal = self.ontology.get(PatchProposal, payload["proposal_id"])
        if proposal is None:
            raise ValueError(f"proposal not found: {payload['proposal_id']}")
        if proposal.status != "proposed":
            raise ValueError(
                f"proposal status must be proposed, got: {proposal.status}"
            )
        # Large patch requires hg_ticket_id (sentinel rule)
        is_large = (
            len(proposal.files_touched) > 5
            or (proposal.diff_lines_added + proposal.diff_lines_removed) > 300
        )
        if is_large and not payload.get("hg_ticket_id"):
            raise ValueError(
                "approve_patch: hg_ticket_id REQUIRED for patches >5 files or >300 LOC"
            )
        proposal.status = "approved"
        self.ontology.update(proposal)
        ticket_id = self._mirror_ticket(
            project_id=payload.get("project_id", ""),
            title=f"Approve patch {proposal.proposal_id}",
            summary=payload.get("rationale", "")[:200],
            payload={
                "proposal_id": proposal.proposal_id,
                "finding_id": proposal.finding_id,
                "branch_id": proposal.branch_id,
                "is_large": is_large,
                "hg_ticket_id": payload.get("hg_ticket_id"),
                "intent_id": intent_id,
            },
            requested_by=payload["approver"],
        )
        self._emit("aeis.testing.repair.approved", {
            "proposal_id": proposal.proposal_id,
            "approver": payload["approver"],
            "is_large": is_large,
            "trace_id": intent_id,
        })
        return {
            "proposal_id": proposal.proposal_id,
            "status": "approved",
            "ticket_id": ticket_id,
        }


class ApplyPatchToBranchHandler(TestingActionHandler):
    target_action: str = "apply_patch_to_branch"
    d_level: DLevel = DLevel.D2
    phase: str = "TWO_PHASE"
    mirror_to_ticket: bool = False  # already ticketed at proposal stage

    def validate(self, payload: dict) -> None:
        self._require_keys(payload, "proposal_id", "applied_by")
        self._require_prefix(payload, "proposal_id", "patch_")

    def execute(self, payload: dict, intent_id: str) -> dict:
        if self.ontology is None:
            raise RuntimeError("apply_patch_to_branch: ontology not configured")
        proposal = self.ontology.get(PatchProposal, payload["proposal_id"])
        if proposal is None:
            raise ValueError(f"proposal not found: {payload['proposal_id']}")
        if proposal.status != "approved":
            raise ValueError(
                f"proposal status must be approved, got: {proposal.status}"
            )
        # Defensive: branch_id never main
        if proposal.branch_id == "main":
            raise ValueError(
                "apply_patch_to_branch: branch_id is 'main' — HARD STOP "
                "(W14 prohibits direct main mutation)"
            )
        proposal.status = "applied"
        self.ontology.update(proposal)
        self._emit("aeis.testing.repair.applied", {
            "proposal_id": proposal.proposal_id,
            "branch_id": proposal.branch_id,
            "applied_by": payload["applied_by"],
        }, trace_id=intent_id)
        return {
            "proposal_id": proposal.proposal_id,
            "branch_id": proposal.branch_id,
            "status": "applied",
        }


class RunRegressionHandler(TestingActionHandler):
    target_action: str = "run_regression"
    d_level: DLevel = DLevel.D1
    phase: str = "IMMEDIATE"
    mirror_to_ticket: bool = False

    def validate(self, payload: dict) -> None:
        self._require_keys(
            payload, "finding_id", "pre_fix_run_id", "post_fix_run_id"
        )
        self._require_prefix(payload, "finding_id", "find_")

    def execute(self, payload: dict, intent_id: str) -> dict:
        if self.ontology is None:
            raise RuntimeError("run_regression: ontology not configured")

        regression = RegressionRun(
            finding_id=payload["finding_id"],
            pre_fix_run_id=payload["pre_fix_run_id"],
            post_fix_run_id=payload["post_fix_run_id"],
            neighbor_test_run_ids=list(payload.get("neighbor_test_run_ids", [])),
            status="pending",
        )
        self.ontology.create(regression)
        self._emit("aeis.testing.regression.started", {
            "regression_id": regression.regression_id,
            "finding_id": regression.finding_id,
        }, trace_id=intent_id)
        # E2 stub: real comparison logic in E4 (Auto-Repair Controller)
        return {
            "regression_id": regression.regression_id,
            "status": "pending",
            "note": "E2 stub: comparison happens via Auto-Repair Controller in E4",
        }


REPAIR_HANDLERS = (
    ProposePatchHandler,
    ApprovePatchHandler,
    ApplyPatchToBranchHandler,
    RunRegressionHandler,
)
