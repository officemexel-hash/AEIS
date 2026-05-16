"""
SYLION API -- Notification Engine routes.

Endpoints for the NotificationEngine module:
  create_channel, update_channel, delete_channel, list_channels,
  create_rule, update_rule, delete_rule, list_rules,
  send_notification, get_notifications, mark_read,
  get_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_notification_engine = None


def _get_notification_engine():
    global _notification_engine
    if _notification_engine is not None:
        return _notification_engine
    from sylion.monitoring.notification_engine import get_notification_engine
    _notification_engine = get_notification_engine()
    return _notification_engine


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateChannelRequest(BaseModel):
    name: str
    channel_type: str
    config_json: str | dict | None = None


class UpdateChannelRequest(BaseModel):
    name: str | None = None
    channel_type: str | None = None
    config_json: str | dict | None = None
    enabled: bool | None = None


class CreateRuleRequest(BaseModel):
    name: str
    channel_id: str
    trigger_condition_json: str | dict | None = None
    severity_filter: str | None = None


class UpdateRuleRequest(BaseModel):
    name: str | None = None
    channel_id: str | None = None
    trigger_condition_json: str | dict | None = None
    severity_filter: str | None = None
    enabled: bool | None = None


class SendNotificationRequest(BaseModel):
    rule_id: str
    title: str
    message: str
    severity: str = "info"
    metadata_json: str | dict | None = None


# ---------------------------------------------------------------------------
# Channel CRUD
# ---------------------------------------------------------------------------

@router.post("/channels", status_code=201)
def create_channel(body: CreateChannelRequest):
    """Create a new notification channel."""
    eng = _get_notification_engine()
    try:
        return eng.create_channel(
            name=body.name,
            channel_type=body.channel_type,
            config_json=body.config_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/channels/{channel_id}")
def update_channel(channel_id: str, body: UpdateChannelRequest):
    """Update a notification channel."""
    eng = _get_notification_engine()
    try:
        result = eng.update_channel(
            channel_id,
            name=body.name,
            channel_type=body.channel_type,
            config_json=body.config_json,
            enabled=body.enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    return result


@router.delete("/channels/{channel_id}")
def delete_channel(channel_id: str):
    """Delete a notification channel."""
    eng = _get_notification_engine()
    ok = eng.delete_channel(channel_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    return {"channel_id": channel_id, "removed": True}


@router.get("/channels")
def list_channels(channel_type: str | None = None):
    """List notification channels, optionally filtered by type."""
    eng = _get_notification_engine()
    return {"channels": eng.list_channels(channel_type=channel_type)}


# ---------------------------------------------------------------------------
# Rule CRUD
# ---------------------------------------------------------------------------

@router.post("/rules", status_code=201)
def create_rule(body: CreateRuleRequest):
    """Create a notification rule linking conditions to a channel."""
    eng = _get_notification_engine()
    return eng.create_rule(
        name=body.name,
        channel_id=body.channel_id,
        trigger_condition_json=body.trigger_condition_json,
        severity_filter=body.severity_filter,
    )


@router.put("/rules/{rule_id}")
def update_rule(rule_id: str, body: UpdateRuleRequest):
    """Update a notification rule."""
    eng = _get_notification_engine()
    result = eng.update_rule(
        rule_id,
        name=body.name,
        channel_id=body.channel_id,
        trigger_condition_json=body.trigger_condition_json,
        severity_filter=body.severity_filter,
        enabled=body.enabled,
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return result


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str):
    """Delete a notification rule."""
    eng = _get_notification_engine()
    ok = eng.delete_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return {"rule_id": rule_id, "removed": True}


@router.get("/rules")
def list_rules(channel_id: str | None = None):
    """List notification rules, optionally filtered by channel_id."""
    eng = _get_notification_engine()
    return {"rules": eng.list_rules(channel_id=channel_id)}


# ---------------------------------------------------------------------------
# Send / Read notifications
# ---------------------------------------------------------------------------

@router.post("/send", status_code=201)
def send_notification(body: SendNotificationRequest):
    """Create and deliver a notification through the rule's channel."""
    eng = _get_notification_engine()
    try:
        return eng.send_notification(
            rule_id=body.rule_id,
            title=body.title,
            message=body.message,
            severity=body.severity,
            metadata_json=body.metadata_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
def get_notifications(status: str | None = None, limit: int = 100):
    """List notifications, optionally filtered by status."""
    eng = _get_notification_engine()
    return {"notifications": eng.get_notifications(status=status, limit=limit)}


@router.post("/{notification_id}/read")
def mark_read(notification_id: str):
    """Mark a notification as read."""
    eng = _get_notification_engine()
    result = eng.mark_read(notification_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Notification {notification_id} not found or already read")
    return result


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_stats():
    """Aggregate notification statistics."""
    eng = _get_notification_engine()
    return eng.get_stats()
