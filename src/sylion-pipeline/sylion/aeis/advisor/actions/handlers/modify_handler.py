"""Modify handler."""
from __future__ import annotations

from sylion.aeis.advisor.actions._db import apply_card_modification
from sylion.aeis.advisor.actions._models import ActionContext, HandlerResult
from sylion.aeis.advisor.actions.handlers.base import ActionHandler


class ModifyHandler(ActionHandler):
    def handle(self, ctx: ActionContext) -> HandlerResult:
        if not ctx.modified_recommendation:
            return HandlerResult(
                success=False,
                routed_to_module="advisor_engine",
                routed_target_id=ctx.card_id,
                payload_sent={"card_id": ctx.card_id},
                error_message="modified_recommendation_required",
            )
        updated = apply_card_modification(ctx.card_id, ctx.modified_recommendation)
        if not updated:
            return HandlerResult(
                success=False,
                routed_to_module="advisor_engine",
                routed_target_id=ctx.card_id,
                payload_sent={"card_id": ctx.card_id, "modified_recommendation": ctx.modified_recommendation},
                error_message="card_not_found",
            )
        return HandlerResult(
            success=True,
            routed_to_module="advisor_engine",
            routed_target_id=ctx.card_id,
            payload_sent={"card_id": ctx.card_id, "modified_recommendation": ctx.modified_recommendation},
            response={"status": "modified"},
            soft_learning_triggered=not ctx.dont_learn_flag,
        )
