"""Not-useful handler."""
from __future__ import annotations

from sylion.aeis.advisor.actions._db import append_card_tag
from sylion.aeis.advisor.actions._models import ActionContext, HandlerResult
from sylion.aeis.advisor.actions.handlers.base import ActionHandler


class NotUsefulHandler(ActionHandler):
    def handle(self, ctx: ActionContext) -> HandlerResult:
        append_card_tag(ctx.card_id, "not_useful")
        return HandlerResult(
            success=True,
            routed_to_module="advisor_engine",
            routed_target_id=ctx.card_id,
            payload_sent={"card_id": ctx.card_id, "action": "not_useful"},
            response={"status": "suppressed"},
            soft_learning_triggered=not ctx.dont_learn_flag,
        )
