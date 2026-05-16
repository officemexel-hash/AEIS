"""Advisor actions service."""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from sylion.core.event_bus import SylionEvent, get_event_bus

from . import audit
from ._models import ActionContext, CardAction, RouteStatus
from .retry import retry_route
from .routing_table import get_handler

_PROTO_TO_ACTION = {
    1: CardAction.ACCEPT,
    2: CardAction.REJECT,
    3: CardAction.MODIFY,
    4: CardAction.REMIND_LATER,
    5: CardAction.NOT_USEFUL,
    6: CardAction.CONVERT_TO_HUMAN_GATE,
    7: CardAction.CONVERT_TO_MASTERPLAN_CHANGE,
    8: CardAction.SAVE_AS_PREFERENCE,
    9: CardAction.DONT_LEARN_FROM_THIS,
}


class ActionsService:
    """Thin synchronous orchestrator for operator card actions."""

    def __init__(self, event_bus: Any | None = None) -> None:
        self._event_bus = event_bus or get_event_bus()

    def HandleAction(self, request: Any, context: Any | None = None) -> SimpleNamespace:
        _ = context
        ctx = self._coerce_context(request)
        if ctx.dont_learn_flag and ctx.action != CardAction.DONT_LEARN_FROM_THIS:
            self._run_auxiliary_handler(ctx, CardAction.DONT_LEARN_FROM_THIS)
        result = get_handler(ctx.action).handle(ctx)
        route_audit_id = audit.log_route(
            card_id=ctx.card_id,
            action=ctx.action,
            routed_to_module=result.routed_to_module,
            routed_target_id=result.routed_target_id,
            payload_sent=result.payload_sent,
            response=result.response,
            status=RouteStatus.SUCCESS if result.success else RouteStatus.FAILED,
            error_message=result.error_message,
        )
        if result.success:
            self._emit("aeis.advisor.actions.action_routed", {
                "route_audit_id": route_audit_id,
                "card_id": ctx.card_id,
                "action": ctx.action.value,
                "operator_id": ctx.operator_id,
                "routed_to_module": result.routed_to_module,
            })
            if ctx.action == CardAction.CONVERT_TO_HUMAN_GATE:
                self._emit("aeis.advisor.actions.human_gate_ticket_created", {
                    "card_id": ctx.card_id,
                    "ticket_id": result.routed_target_id,
                })
            if ctx.action == CardAction.CONVERT_TO_MASTERPLAN_CHANGE:
                self._emit("aeis.advisor.actions.masterplan_proposal_created", {
                    "card_id": ctx.card_id,
                    "proposal_id": result.routed_target_id,
                })
            if ctx.action == CardAction.SAVE_AS_PREFERENCE:
                self._emit("aeis.advisor.actions.preference_saved", {
                    "card_id": ctx.card_id,
                    "preference_key": ctx.preference_key,
                    "operator_id": ctx.operator_id,
                })
        else:
            self._emit("aeis.advisor.actions.routing_failed", {
                "card_id": ctx.card_id,
                "action": ctx.action.value,
                "error": result.error_message,
            })
        return SimpleNamespace(
            action_event_id=route_audit_id,
            recorded_at=datetime.now(timezone.utc),
            soft_learning_triggered=result.soft_learning_triggered,
            hard_learning_pending_confirmation=result.hard_learning_pending,
            created_human_gate_ticket_id=result.routed_target_id if ctx.action == CardAction.CONVERT_TO_HUMAN_GATE and result.success else "",
            created_masterplan_proposal_id=result.routed_target_id if ctx.action == CardAction.CONVERT_TO_MASTERPLAN_CHANGE and result.success else "",
            saved_preference_id=result.routed_target_id if ctx.action == CardAction.SAVE_AS_PREFERENCE and result.success else "",
            error_message=result.error_message or "",
        )

    def RetryFailed(self, request: Any, context: Any | None = None) -> SimpleNamespace:
        _ = context
        success, status, error_message = retry_route(getattr(request, "route_audit_id"))
        if success:
            self._emit("aeis.advisor.actions.action_retry_scheduled", {
                "route_audit_id": getattr(request, "route_audit_id"),
                "status": status,
            })
        return SimpleNamespace(success=success, status=status, error_message=error_message or "")

    def GetRoutingAudit(self, request: Any, context: Any | None = None) -> SimpleNamespace:
        _ = context
        return SimpleNamespace(entries=audit.get_routing_audit(getattr(request, "card_id")))

    def _run_auxiliary_handler(self, ctx: ActionContext, action: CardAction) -> None:
        result = get_handler(action).handle(ctx)
        audit.log_route(
            card_id=ctx.card_id,
            action=action,
            routed_to_module=result.routed_to_module,
            routed_target_id=result.routed_target_id,
            payload_sent=result.payload_sent,
            response=result.response,
            status=RouteStatus.SUCCESS if result.success else RouteStatus.FAILED,
            error_message=result.error_message,
        )

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        event = SylionEvent(
            event_id=str(uuid.uuid4()),
            topic=topic,
            payload=payload,
            source_module="sylion.aeis.advisor.actions",
            timestamp=time.time(),
            idempotency_key=f"{topic}:{payload.get('card_id', '')}:{payload.get('route_audit_id', '')}",
        )
        self._event_bus.publish(event)

    @staticmethod
    def _coerce_context(request: Any) -> ActionContext:
        if isinstance(request, ActionContext):
            return request
        action_value = getattr(request, "action")
        if isinstance(action_value, CardAction):
            action = action_value
        elif isinstance(action_value, str):
            action = CardAction(action_value)
        else:
            action = _PROTO_TO_ACTION[int(action_value)]
        return ActionContext(
            card_id=getattr(request, "card_id"),
            action=action,
            operator_id=getattr(request, "operator_id"),
            operator_note=getattr(request, "operator_note", None) or None,
            modified_recommendation=getattr(request, "modified_recommendation", None) or None,
            preference_key=getattr(request, "preference_key", None) or None,
            preference_project_type=getattr(request, "preference_project_type", None) or None,
            preference_project_domain=getattr(request, "preference_project_domain", None) or None,
            preference_value=getattr(request, "preference_value", None),
            dont_learn_flag=bool(getattr(request, "dont_learn_flag", False)),
        )


_service: ActionsService | None = None
_lock = threading.Lock()


def get_actions_service() -> ActionsService:
    global _service
    if _service is None:
        with _lock:
            if _service is None:
                _service = ActionsService()
    return _service
