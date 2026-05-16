"""W14 finding actions (3): mark_reproduced / waive / disable_test."""
from __future__ import annotations

import time

from sylion.aeis.testing.actions.base import TestingActionHandler
from sylion.aeis.testing.ontology.enums import DLevel, GateType, RStatus
from sylion.aeis.testing.ontology.objects import Finding, TestCase


class MarkFindingReproducedHandler(TestingActionHandler):
    target_action: str = "mark_finding_reproduced"
    d_level: DLevel = DLevel.D1
    phase: str = "IMMEDIATE"
    mirror_to_ticket: bool = False

    def validate(self, payload: dict) -> None:
        self._require_keys(payload, "finding_id", "reproducer", "evidence")
        self._require_prefix(payload, "finding_id", "find_")

    def execute(self, payload: dict, intent_id: str) -> dict:
        if self.ontology is None:
            raise RuntimeError("mark_finding_reproduced: ontology not configured")
        finding = self.ontology.get(Finding, payload["finding_id"])
        if finding is None:
            raise ValueError(f"finding not found: {payload['finding_id']}")
        allowed = {RStatus.OPEN.value, RStatus.TRIAGED.value}
        if finding.r_status not in allowed:
            raise ValueError(
                f"finding status must be OPEN or TRIAGED, got: {finding.r_status}"
            )
        finding.r_status = RStatus.REPRODUCED.value
        self.ontology.update(finding)
        self._emit("aeis.testing.finding.transitioned", {
            "finding_id": finding.finding_id,
            "r_status": finding.r_status,
            "reproducer": payload["reproducer"],
        }, trace_id=intent_id)
        return {"finding_id": finding.finding_id, "r_status": finding.r_status}


class WaiveFindingHandler(TestingActionHandler):
    target_action: str = "waive_finding"
    d_level: DLevel = DLevel.D3
    phase: str = "TWO_PHASE"
    mirror_to_ticket: bool = True
    gate_type: GateType = GateType.PRODUCTION

    MIN_EXPIRY_SECONDS = 24 * 3600  # 24h hard minimum (no perpetual waivers)

    def validate(self, payload: dict) -> None:
        self._require_keys(
            payload, "finding_id", "hg_ticket_id", "rationale", "expiry_at"
        )
        self._require_prefix(payload, "finding_id", "find_")
        rationale = payload["rationale"]
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("waive_finding: rationale must be a non-empty string")
        expiry = float(payload["expiry_at"])
        if expiry < time.time() + self.MIN_EXPIRY_SECONDS:
            raise ValueError(
                "waive_finding: expiry_at must be at least 24h in the future "
                "(no perpetual waivers)"
            )

    def execute(self, payload: dict, intent_id: str) -> dict:
        if self.ontology is None:
            raise RuntimeError("waive_finding: ontology not configured")
        finding = self.ontology.get(Finding, payload["finding_id"])
        if finding is None:
            raise ValueError(f"finding not found: {payload['finding_id']}")
        finding.r_status = RStatus.WAIVED_BY_HUMAN.value
        finding.closed_at = time.time()
        self.ontology.update(finding)

        ticket_id = self._mirror_ticket(
            project_id=getattr(finding, "project_id", "") or "",
            title=f"Waive finding {finding.finding_id} ({finding.severity})",
            summary=payload["rationale"][:200],
            payload={
                "finding_id": finding.finding_id,
                "expiry_at": payload["expiry_at"],
                "hg_ticket_id": payload["hg_ticket_id"],
            },
        )
        self._emit("aeis.testing.finding.waived", {
            "finding_id": finding.finding_id,
            "expiry_at": payload["expiry_at"],
        }, trace_id=intent_id)
        self._emit("aeis.testing.finding.closed", {
            "finding_id": finding.finding_id,
            "reason": "waived",
        }, trace_id=intent_id)
        return {
            "finding_id": finding.finding_id,
            "r_status": finding.r_status,
            "expiry_at": payload["expiry_at"],
            "ticket_id": ticket_id,
        }


class DisableTestHandler(TestingActionHandler):
    """ONLY action that can disable mandatory tests. D4: requires Council + HG."""

    target_action: str = "disable_test"
    d_level: DLevel = DLevel.D4
    phase: str = "TWO_PHASE"
    mirror_to_ticket: bool = True
    gate_type: GateType = GateType.PRODUCTION

    def validate(self, payload: dict) -> None:
        self._require_keys(
            payload, "case_id", "council_session_id", "hg_ticket_id", "rationale"
        )
        self._require_prefix(payload, "case_id", "tc_")

    def execute(self, payload: dict, intent_id: str) -> dict:
        if self.ontology is None:
            raise RuntimeError("disable_test: ontology not configured")
        case = self.ontology.get(TestCase, payload["case_id"])
        if case is None:
            raise ValueError(f"test case not found: {payload['case_id']}")
        case.enabled = False
        self.ontology.update(case)

        ticket_id = self._mirror_ticket(
            project_id="",
            title=f"DISABLE test case {case.case_id}",
            summary=f"D4: Council {payload['council_session_id']} + HG {payload['hg_ticket_id']}",
            payload={
                "case_id": case.case_id,
                "council_session_id": payload["council_session_id"],
                "hg_ticket_id": payload["hg_ticket_id"],
                "rationale": payload["rationale"],
            },
            gate_type_override=GateType.PRODUCTION,
        )
        self._emit("aeis.testing.case.disabled", {
            "case_id": case.case_id,
            "council_session_id": payload["council_session_id"],
            "hg_ticket_id": payload["hg_ticket_id"],
        }, trace_id=intent_id)
        return {
            "case_id": case.case_id,
            "enabled": False,
            "council_session_id": payload["council_session_id"],
            "hg_ticket_id": payload["hg_ticket_id"],
            "ticket_id": ticket_id,
        }


FINDING_HANDLERS = (
    MarkFindingReproducedHandler,
    WaiveFindingHandler,
    DisableTestHandler,
)
