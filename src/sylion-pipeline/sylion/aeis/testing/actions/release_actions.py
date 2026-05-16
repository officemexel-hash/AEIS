"""W14 release actions (3): promote_release_candidate / rollback_release / close_loop_as_blocked."""
from __future__ import annotations

from sylion.aeis.testing.actions.base import TestingActionHandler
from sylion.aeis.testing.ontology.enums import (
    DLevel, GateType, ReleaseStatus, RStatus, Severity,
)
from sylion.aeis.testing.ontology.objects import (
    Finding, LoopReport, ReleaseCandidate, ReleaseDecision,
)


class PromoteReleaseCandidateHandler(TestingActionHandler):
    target_action: str = "promote_release_candidate"
    d_level: DLevel = DLevel.D3
    phase: str = "TWO_PHASE"
    mirror_to_ticket: bool = True
    gate_type: GateType = GateType.PRODUCTION

    def validate(self, payload: dict) -> None:
        self._require_keys(
            payload, "branch_id", "project_id", "hg_ticket_id",
            "evidence_pack_id", "test_run_summary",
        )
        # HARD: branch_id != main
        self._require_not_main(payload, "branch_id")
        if not isinstance(payload["test_run_summary"], dict):
            raise ValueError(
                "promote_release_candidate: test_run_summary must be dict"
            )

    def execute(self, payload: dict, intent_id: str) -> dict:
        if self.ontology is None:
            raise RuntimeError("promote_release_candidate: ontology not configured")

        # Hard reject if any P0/P1 unresolved findings
        unresolved = list(payload.get("unresolved_findings", []))
        if unresolved:
            for fid in unresolved:
                f = self.ontology.get(Finding, fid)
                if f and f.severity in (Severity.P0.value, Severity.P1.value):
                    if f.r_status not in (
                        RStatus.VERIFIED.value,
                        RStatus.WAIVED_BY_HUMAN.value,
                        RStatus.CLOSED.value,
                    ):
                        raise ValueError(
                            f"promote_release_candidate: unresolved {f.severity} "
                            f"finding {fid} blocks release (r_status={f.r_status})"
                        )

        rc = ReleaseCandidate(
            branch_id=payload["branch_id"],
            project_id=payload["project_id"],
            test_run_summary=payload["test_run_summary"],
            unresolved_findings=unresolved,
            evidence_pack_id=payload["evidence_pack_id"],
            gate_status=ReleaseStatus.RELEASE_CANDIDATE.value,
        )
        self.ontology.create(rc)

        ticket_id = self._mirror_ticket(
            project_id=payload["project_id"],
            title=f"Release Candidate: {rc.rc_id}",
            summary=(
                f"Branch: {payload['branch_id']}, "
                f"Evidence: {payload['evidence_pack_id']}"
            ),
            payload={
                "rc_id": rc.rc_id,
                "branch_id": payload["branch_id"],
                "hg_ticket_id": payload["hg_ticket_id"],
            },
        )
        self._emit("aeis.testing.release.candidate_ready", {
            "rc_id": rc.rc_id,
            "project_id": payload["project_id"],
        }, trace_id=intent_id)
        return {
            "rc_id": rc.rc_id,
            "gate_status": rc.gate_status,
            "ticket_id": ticket_id,
        }


class RollbackReleaseHandler(TestingActionHandler):
    target_action: str = "rollback_release"
    d_level: DLevel = DLevel.D3
    phase: str = "TWO_PHASE"
    mirror_to_ticket: bool = True
    gate_type: GateType = GateType.EMERGENCY

    def validate(self, payload: dict) -> None:
        self._require_keys(
            payload, "rc_id", "hg_ticket_id", "rollback_reason", "rollback_plan"
        )
        self._require_prefix(payload, "rc_id", "rc_")
        if not isinstance(payload["rollback_plan"], dict) or not payload["rollback_plan"]:
            raise ValueError("rollback_release: rollback_plan must be non-empty dict")

    def execute(self, payload: dict, intent_id: str) -> dict:
        if self.ontology is None:
            raise RuntimeError("rollback_release: ontology not configured")
        rc = self.ontology.get(ReleaseCandidate, payload["rc_id"])
        if rc is None:
            raise ValueError(f"release candidate not found: {payload['rc_id']}")

        decision = ReleaseDecision(
            rc_id=rc.rc_id,
            hg_ticket_id=payload["hg_ticket_id"],
            outcome="rollback",
            rollback_plan=payload["rollback_plan"],
            signatures=[{"role": "operator", "decision": "rollback"}],
        )
        self.ontology.create(decision)

        rc.gate_status = ReleaseStatus.ROLLBACK_REQUIRED.value
        self.ontology.update(rc)

        ticket_id = self._mirror_ticket(
            project_id=rc.project_id,
            title=f"EMERGENCY ROLLBACK: {rc.rc_id}",
            summary=payload["rollback_reason"][:200],
            payload={
                "rc_id": rc.rc_id,
                "decision_id": decision.decision_id,
                "rollback_plan": payload["rollback_plan"],
            },
        )
        self._emit("aeis.testing.release.rolled_back", {
            "decision_id": decision.decision_id,
            "rc_id": rc.rc_id,
        }, trace_id=intent_id)
        return {
            "decision_id": decision.decision_id,
            "rc_id": rc.rc_id,
            "status": "rollback",
            "ticket_id": ticket_id,
        }


class CloseLoopAsBlockedHandler(TestingActionHandler):
    target_action: str = "close_loop_as_blocked"
    d_level: DLevel = DLevel.D3
    phase: str = "TWO_PHASE"
    mirror_to_ticket: bool = True
    gate_type: GateType = GateType.PRODUCTION

    DECISIONS = (
        "accept_known_issue",
        "change_masterplan",
        "change_sot",
        "abandon",
        "reassign",
    )

    def validate(self, payload: dict) -> None:
        self._require_keys(
            payload, "finding_id", "loop_report_id",
            "hg_ticket_id", "human_decision", "rationale",
        )
        self._require_prefix(payload, "loop_report_id", "lr_")
        self._require_prefix(payload, "finding_id", "find_")
        if payload["human_decision"] not in self.DECISIONS:
            raise ValueError(
                f"close_loop_as_blocked: human_decision must be one of "
                f"{self.DECISIONS}, got: {payload['human_decision']}"
            )

    def execute(self, payload: dict, intent_id: str) -> dict:
        if self.ontology is None:
            raise RuntimeError("close_loop_as_blocked: ontology not configured")
        finding = self.ontology.get(Finding, payload["finding_id"])
        if finding is None:
            raise ValueError(f"finding not found: {payload['finding_id']}")
        loop = self.ontology.get(LoopReport, payload["loop_report_id"])
        if loop is None:
            raise ValueError(f"loop report not found: {payload['loop_report_id']}")

        # Decision -> r_status mapping
        new_status = (
            RStatus.CLOSED.value
            if payload["human_decision"] in ("accept_known_issue", "abandon")
            else RStatus.ESCALATED.value
        )
        finding.r_status = new_status
        self.ontology.update(finding)

        ticket_id = self._mirror_ticket(
            project_id="",
            title=f"Loop blocked, human decided: {payload['human_decision']}",
            summary=payload["rationale"][:200],
            payload={
                "finding_id": finding.finding_id,
                "loop_report_id": loop.report_id,
                "decision": payload["human_decision"],
                "hg_ticket_id": payload["hg_ticket_id"],
            },
        )
        self._emit("aeis.testing.loop.escalated", {
            "finding_id": finding.finding_id,
            "loop_report_id": loop.report_id,
            "human_decision": payload["human_decision"],
        }, trace_id=intent_id)
        return {
            "finding_id": finding.finding_id,
            "decision": payload["human_decision"],
            "r_status": new_status,
            "ticket_id": ticket_id,
        }


RELEASE_HANDLERS = (
    PromoteReleaseCandidateHandler,
    RollbackReleaseHandler,
    CloseLoopAsBlockedHandler,
)
