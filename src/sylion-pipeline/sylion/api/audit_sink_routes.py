"""
SYLION API -- Audit Sink routes.

Endpoints for the AuditSink module:
  create_subscription, update_subscription, delete_subscription,
  list_subscriptions, deliver_event, list_deliveries,
  retry_delivery, get_sink_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/audit-sink", tags=["Audit Sink"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_audit_sink = None


def _get_audit_sink():
    global _audit_sink
    if _audit_sink is not None:
        return _audit_sink
    from sylion.security.audit_sink import get_audit_sink
    _audit_sink = get_audit_sink()
    return _audit_sink


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateSubscriptionRequest(BaseModel):
    name: str
    topic_pattern: str
    delivery_type: str
    config_json: dict | None = None


class UpdateSubscriptionRequest(BaseModel):
    name: str | None = None
    topic_pattern: str | None = None
    delivery_type: str | None = None
    config_json: dict | None = None


class DeliverEventRequest(BaseModel):
    sub_id: str
    event_json: dict


# ---------------------------------------------------------------------------
# Subscription CRUD
# ---------------------------------------------------------------------------

@router.post("/subscriptions", status_code=201)
def create_subscription(body: CreateSubscriptionRequest):
    """Create a new audit event subscription."""
    sink = _get_audit_sink()
    try:
        return sink.create_subscription(
            name=body.name,
            topic_pattern=body.topic_pattern,
            delivery_type=body.delivery_type,
            config_json=body.config_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/subscriptions/{sub_id}")
def update_subscription(sub_id: str, body: UpdateSubscriptionRequest):
    """Update an existing subscription."""
    sink = _get_audit_sink()
    try:
        result = sink.update_subscription(
            sub_id=sub_id,
            name=body.name,
            topic_pattern=body.topic_pattern,
            delivery_type=body.delivery_type,
            config_json=body.config_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Subscription {sub_id} not found")
    return result


@router.delete("/subscriptions/{sub_id}")
def delete_subscription(sub_id: str):
    """Delete a subscription."""
    sink = _get_audit_sink()
    deleted = sink.delete_subscription(sub_id)
    if not deleted:
        raise HTTPException(status_code=404,
                            detail=f"Subscription {sub_id} not found")
    return {"deleted": True}


@router.get("/subscriptions")
def list_subscriptions(topic_pattern: str | None = None):
    """List subscriptions, optionally filtered by topic pattern."""
    sink = _get_audit_sink()
    return sink.list_subscriptions(topic_pattern=topic_pattern)


# ---------------------------------------------------------------------------
# Event delivery
# ---------------------------------------------------------------------------

@router.post("/deliver", status_code=201)
def deliver_event(body: DeliverEventRequest):
    """Deliver an event to a subscription (creates a delivery record)."""
    sink = _get_audit_sink()
    try:
        return sink.deliver_event(
            sub_id=body.sub_id,
            event_json=body.event_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Deliveries -- static paths before dynamic /{delivery_id} paths
# ---------------------------------------------------------------------------

@router.get("/deliveries")
def list_deliveries(
    sub_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
):
    """List deliveries with optional filters."""
    sink = _get_audit_sink()
    return sink.list_deliveries(sub_id=sub_id, status=status, limit=limit)


@router.post("/deliveries/{delivery_id}/retry")
def retry_delivery(delivery_id: str):
    """Retry a failed delivery."""
    sink = _get_audit_sink()
    result = sink.retry_delivery(delivery_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Delivery {delivery_id} not found")
    return result


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_sink_stats():
    """Aggregate statistics across all subscriptions and deliveries."""
    sink = _get_audit_sink()
    return sink.get_sink_stats()
