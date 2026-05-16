"""Retry helpers for failed action routes."""
from __future__ import annotations

from sylion.aeis.advisor.actions import audit
from sylion.aeis.advisor.actions._models import ActionContext, CardAction, RouteStatus
from sylion.aeis.advisor.actions.routing_table import get_handler


def retry_route(route_audit_id: str) -> tuple[bool, str, str | None]:
    row = audit.get_route_for_retry(route_audit_id)
    if not row:
        return False, "not_found", "route_audit_id_not_found"
    if row[4] != RouteStatus.FAILED.value:
        return False, str(row[4]), "not_in_failed_state"
    payload = row[3] or {}
    ctx = ActionContext(
        card_id=str(row[1]),
        action=CardAction(str(row[2])),
        operator_id=str(payload.get("operator_id", "")),
        operator_note=payload.get("operator_note"),
        modified_recommendation=payload.get("modified_recommendation"),
        preference_key=payload.get("preference_key"),
        preference_project_type=payload.get("project_type"),
        preference_project_domain=payload.get("project_domain"),
        preference_value=payload.get("preference_value"),
        dont_learn_flag=bool(payload.get("dont_learn_flag", False)),
    )
    result = get_handler(ctx.action).handle(ctx)
    if result.success:
        audit.update_route_status(route_audit_id, RouteStatus.SUCCESS, None)
        return True, RouteStatus.SUCCESS.value, None
    audit.update_route_status(route_audit_id, RouteStatus.FAILED, result.error_message)
    return False, RouteStatus.FAILED.value, result.error_message
