"""Masterplan conversion handler."""
from __future__ import annotations

import uuid

from sylion.aeis.advisor.actions._db import append_card_tag, fetch_card_snapshot
from sylion.aeis.advisor.actions._models import ActionContext, HandlerResult
from sylion.aeis.advisor.actions.handlers.base import ActionHandler
from sylion.governance.decision_ladder import DecisionProposal, get_decision_ladder


class MasterplanHandler(ActionHandler):
    def handle(self, ctx: ActionContext) -> HandlerResult:
        row = fetch_card_snapshot(ctx.card_id)
        if not row:
            return HandlerResult(
                success=False,
                routed_to_module="masterplan",
                routed_target_id=None,
                payload_sent={"card_id": ctx.card_id},
                error_message="card_not_found",
            )
        proposal_id = str(uuid.uuid4())
        payload = {
            "proposal_id": proposal_id,
            "source_card_id": ctx.card_id,
            "title": row[1],
            "rationale": row[2],
            "project_id": str(row[5]) if row[5] else None,
            "advisor_body": row[6],
            "operator_id": ctx.operator_id,
            "operator_note": ctx.operator_note,
        }
        proposal = DecisionProposal(
            proposal_id=proposal_id,
            title=f"Advisor masterplan change: {row[1]}",
            description=str(row[2] or ""),
            source_plan="advisor_card",
            module_id=str(row[5] or "project"),
            change_type="masterplan",
            blast_radius=_blast_radius_for_decision(str(row[3] or "D2")),
            reversible=True,
            affects_contracts=str(row[3] or "D2") in {"D3", "D4", "D5"},
            affects_kernel=False,
            proposed_by=ctx.operator_id,
            rollback_plan="Revert masterplan proposal and re-run Council deliberation for the affected project phase.",
        )
        get_decision_ladder().propose(proposal)
        append_card_tag(ctx.card_id, "masterplan")
        return HandlerResult(
            success=True,
            routed_to_module="masterplan",
            routed_target_id=proposal_id,
            payload_sent=payload,
            response={"proposal_id": proposal_id},
        )


def _blast_radius_for_decision(d_level: str) -> str:
    if d_level in {"D5", "D4"}:
        return "critical"
    if d_level == "D3":
        return "high"
    if d_level == "D2":
        return "medium"
    return "low"
