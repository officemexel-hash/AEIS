"""Audit helpers for advisor actions."""
from __future__ import annotations

from ._db import get_route_for_retry, list_route_rows, log_route_row, update_route_status
from ._models import CardAction, RouteAuditRow, RouteStatus


def log_route(
    *,
    card_id: str,
    action: CardAction,
    routed_to_module: str,
    routed_target_id: str | None,
    payload_sent: dict,
    response: dict | None,
    status: RouteStatus,
    error_message: str | None = None,
) -> str:
    return log_route_row(
        card_id=card_id,
        action=action,
        routed_to_module=routed_to_module,
        routed_target_id=routed_target_id,
        payload_sent=payload_sent,
        response=response,
        status=status,
        error_message=error_message,
    )


def get_routing_audit(card_id: str) -> list[RouteAuditRow]:
    return list_route_rows(card_id)


__all__ = ["CardAction", "RouteAuditRow", "RouteStatus", "get_route_for_retry", "get_routing_audit", "log_route", "update_route_status"]
