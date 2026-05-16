"""Soft and hard learning flows for advisor preferences."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

from sylion.aeis.advisor.preferences import _db, audit, resolver
from sylion.aeis.advisor.preferences._models import HardChangeRequest

_PENDING: dict[str, HardChangeRequest] = {}
_PENDING_LOCK = Lock()


def apply_soft_learning(
    *,
    user_id: str,
    preference_key: str,
    value: Any,
    set_by: str = "soft_learning",
    project_type: str | None = None,
    project_domain: str | None = None,
    reason: str = "soft_learning",
) -> tuple[bool, str | None]:
    """Apply a soft update at the most specific existing level or user default."""
    target = resolver.find_most_specific_existing_level(
        user_id=user_id,
        project_type=project_type,
        project_domain=project_domain,
        preference_key=preference_key,
    )
    if target is None:
        target = (project_type, project_domain)
    row = _db.get_preference_row(user_id, target[0], target[1], preference_key)
    was_new, old_value = _db.upsert_preference(
        user_id,
        target[0],
        target[1],
        preference_key,
        value,
        set_by,
    )
    audit.log_change(
        user_id=user_id,
        project_type=target[0],
        project_domain=target[1],
        preference_key=preference_key,
        old_value=None if was_new else old_value,
        new_value=value,
        change_type="INSERT" if was_new else "UPDATE",
        changed_by=set_by,
        reason=reason,
    )
    return row is not None, preference_key


def request_hard_change(
    *,
    user_id: str,
    project_type: str | None,
    project_domain: str | None,
    preference_key: str,
    proposed_value: Any,
    source_card_id: str | None,
    rationale: str | None,
    ttl_minutes: int = 30,
) -> HardChangeRequest:
    """Create an in-memory pending hard-change request."""
    now = datetime.now(timezone.utc)
    request = HardChangeRequest(
        request_id=str(uuid4()),
        user_id=user_id,
        project_type=project_type,
        project_domain=project_domain,
        preference_key=preference_key,
        proposed_value=proposed_value,
        source_card_id=source_card_id,
        rationale=rationale,
        requested_at=now,
        expires_at=now + timedelta(minutes=ttl_minutes),
    )
    with _PENDING_LOCK:
        _PENDING[request.request_id] = request
    return request


def confirm_hard_change(
    *,
    request_id: str,
    operator_signature: str,
    confirmed: bool,
) -> tuple[bool, HardChangeRequest | None, str | None]:
    """Mark a pending hard-change request confirmed or rejected."""
    with _PENDING_LOCK:
        request = _PENDING.get(request_id)
        if request is None:
            return False, None, "request_not_found"
        if request.expires_at < datetime.now(timezone.utc):
            return False, None, "request_expired"
        request.confirmed = confirmed
        request.confirmed_at = datetime.now(timezone.utc)
        request.operator_signature = operator_signature
        if confirmed:
            return True, request, None
        _PENDING.pop(request_id, None)
        return True, request, None


def count_pending_for_user(user_id: str) -> int:
    """Return pending hard-change count for a user."""
    with _PENDING_LOCK:
        return sum(
            1
            for request in _PENDING.values()
            if request.user_id == user_id and request.confirmed is None
        )


def get_request(request_id: str) -> HardChangeRequest | None:
    """Return a pending request."""
    with _PENDING_LOCK:
        return _PENDING.get(request_id)


def reset_pending_requests() -> None:
    """Clear pending requests for tests."""
    with _PENDING_LOCK:
        _PENDING.clear()
