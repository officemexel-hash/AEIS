"""Human Gate conversion handler."""
from __future__ import annotations

import uuid

from sylion.aeis.advisor.actions._db import append_card_tag, fetch_card_snapshot
from sylion.aeis.advisor.actions._models import ActionContext, HandlerResult
from sylion.aeis.advisor.actions.handlers.base import ActionHandler
from sylion.governance.tickets import GovernanceTicket, submit


class HumanGateHandler(ActionHandler):
    def handle(self, ctx: ActionContext) -> HandlerResult:
        row = fetch_card_snapshot(ctx.card_id)
        if not row:
            return HandlerResult(
                success=False,
                routed_to_module="human_gate",
                routed_target_id=None,
                payload_sent={"card_id": ctx.card_id},
                error_message="card_not_found",
            )
        ticket_id = str(uuid.uuid4())
        payload = {
            "ticket_id": ticket_id,
            "source_card_id": ctx.card_id,
            "title": row[1],
            "rationale": row[2],
            "d_level": row[3],
            "evidence_pack_id": str(row[4]) if row[4] else None,
            "project_id": str(row[5]) if row[5] else None,
            "operator_id": ctx.operator_id,
            "operator_note": ctx.operator_note,
        }
        submit(GovernanceTicket(
            ticket_id=ticket_id,
            origin="global",
            project_id=str(row[5]) if row[5] else None,
            decision_class=str(row[3] or "D2"),
            gate_type="blocking",
            priority=_priority_for_decision(str(row[3] or "D2")),
            title=f"Advisor HumanGate: {row[1]}",
            summary=str(row[2] or ""),
            payload=payload,
            requested_by="advisor_actions",
        ))
        append_card_tag(ctx.card_id, "human_gate")
        return HandlerResult(
            success=True,
            routed_to_module="human_gate",
            routed_target_id=ticket_id,
            payload_sent=payload,
            response={"ticket_id": ticket_id},
        )


def _priority_for_decision(d_level: str) -> str:
    if d_level in {"D5", "D4"}:
        return "P1"
    if d_level == "D3":
        return "P2"
    return "P3"
