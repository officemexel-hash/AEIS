"""Preference save handler."""
from __future__ import annotations

from sylion.aeis.advisor.actions._models import ActionContext, HandlerResult
from sylion.aeis.advisor.actions.handlers.base import ActionHandler


class PreferenceHandler(ActionHandler):
    def handle(self, ctx: ActionContext) -> HandlerResult:
        if not ctx.preference_key:
            return HandlerResult(
                success=False,
                routed_to_module="advisor_preferences",
                routed_target_id=None,
                payload_sent={},
                error_message="preference_key_required",
            )
        try:
            from sylion.aeis.advisor.preferences.service import get_preferences_service
        except ImportError:
            return HandlerResult(
                success=False,
                routed_to_module="advisor_preferences",
                routed_target_id=None,
                payload_sent={"preference_key": ctx.preference_key},
                error_message="preferences_module_unavailable",
            )
        service = get_preferences_service()
        result = service.set_preference(
            user_id=ctx.operator_id,
            project_type=ctx.preference_project_type,
            project_domain=ctx.preference_project_domain,
            preference_key=ctx.preference_key,
            value=ctx.preference_value,
            set_by="user",
            reason=f"saved_from_card:{ctx.card_id}",
        )
        return HandlerResult(
            success=bool(result.get("success")),
            routed_to_module="advisor_preferences",
            routed_target_id=result.get("saved_preference_id") or ctx.preference_key,
            payload_sent={
                "preference_key": ctx.preference_key,
                "project_type": ctx.preference_project_type,
                "project_domain": ctx.preference_project_domain,
                "operator_id": ctx.operator_id,
            },
            response=result,
            error_message=result.get("error_message"),
            hard_learning_pending=bool(result.get("requires_hard_confirmation")),
        )
