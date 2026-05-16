"""Models for advisor actions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class CardAction(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    MODIFY = "modify"
    REMIND_LATER = "remind_later"
    NOT_USEFUL = "not_useful"
    CONVERT_TO_HUMAN_GATE = "convert_to_human_gate"
    CONVERT_TO_MASTERPLAN_CHANGE = "convert_to_masterplan_change"
    SAVE_AS_PREFERENCE = "save_as_preference"
    DONT_LEARN_FROM_THIS = "dont_learn_from_this"


class RouteStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class ActionContext:
    card_id: str
    action: CardAction
    operator_id: str
    operator_note: str | None = None
    modified_recommendation: str | None = None
    preference_key: str | None = None
    preference_project_type: str | None = None
    preference_project_domain: str | None = None
    preference_value: Any = None
    dont_learn_flag: bool = False


@dataclass(frozen=True)
class HandlerResult:
    success: bool
    routed_to_module: str
    routed_target_id: str | None
    payload_sent: dict[str, Any]
    response: dict[str, Any] | None = None
    error_message: str | None = None
    soft_learning_triggered: bool = False
    hard_learning_pending: bool = False


@dataclass(frozen=True)
class RouteAuditRow:
    route_audit_id: str
    card_id: str
    action: CardAction
    routed_to_module: str
    routed_target_id: str | None
    payload_sent: dict[str, Any]
    response: dict[str, Any] | None
    status: RouteStatus
    error_message: str | None
    routed_at: datetime
