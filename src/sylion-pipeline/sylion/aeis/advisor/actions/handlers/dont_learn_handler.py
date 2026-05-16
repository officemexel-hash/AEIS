"""Dont-learn handler."""
from __future__ import annotations

from sylion.aeis.advisor.actions._db import set_card_flag
from sylion.aeis.advisor.actions._models import ActionContext, HandlerResult
from sylion.aeis.advisor.actions.handlers.base import ActionHandler


class DontLearnHandler(ActionHandler):
    def handle(self, ctx: ActionContext) -> HandlerResult:
        set_card_flag(ctx.card_id, "dont_learn", True)
        return HandlerResult(
            success=True,
            routed_to_module="advisor_engine",
            routed_target_id=ctx.card_id,
            payload_sent={"card_id": ctx.card_id, "dont_learn": True},
            response={"status": "flagged"},
        )
