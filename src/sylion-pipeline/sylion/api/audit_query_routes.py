"""
SYLION API -- Audit Query routes.

Endpoints for the AuditQuery module:
  index_event, query_events, get_event, get_actor_history,
  get_resource_timeline, get_query_stats, purge_index.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/audit-query", tags=["Audit Query"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_audit_query = None


def _get_audit_query():
    global _audit_query
    if _audit_query is not None:
        return _audit_query
    from sylion.security.audit_query import get_audit_query
    _audit_query = get_audit_query()
    return _audit_query


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class IndexEventRequest(BaseModel):
    event_id: str
    event_type: str
    actor: str
    resource: str
    timestamp: float
    tags_json: dict | None = None


class QueryEventsRequest(BaseModel):
    event_type: str | None = None
    actor: str | None = None
    resource: str | None = None
    since: float | None = None
    until: float | None = None
    tag_key: str | None = None
    tag_value: str | None = None
    limit: int = 100


class PurgeRequest(BaseModel):
    older_than_seconds: int


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

@router.post("/events", status_code=201)
def index_event(body: IndexEventRequest):
    """Index an audit event for fast querying."""
    aq = _get_audit_query()
    return aq.index_event(
        event_id=body.event_id,
        event_type=body.event_type,
        actor=body.actor,
        resource=body.resource,
        timestamp=body.timestamp,
        tags_json=body.tags_json,
    )


# ---------------------------------------------------------------------------
# Retrieval -- static paths before dynamic /{event_id} paths
# ---------------------------------------------------------------------------

@router.post("/events/query")
def query_events(body: QueryEventsRequest):
    """Query indexed events with filter criteria."""
    aq = _get_audit_query()
    filters = {
        k: v for k, v in {
            "event_type": body.event_type,
            "actor": body.actor,
            "resource": body.resource,
            "since": body.since,
            "until": body.until,
            "tag_key": body.tag_key,
            "tag_value": body.tag_value,
            "limit": body.limit,
        }.items() if v is not None
    }
    return {"events": aq.query_events(filters_json=filters)}


@router.get("/actors/{actor}/history")
def get_actor_history(actor: str, limit: int = 100):
    """Get event history for a specific actor."""
    aq = _get_audit_query()
    return {"events": aq.get_actor_history(actor, limit=limit)}


@router.get("/resources/{resource}/timeline")
def get_resource_timeline(resource: str, limit: int = 100):
    """Get event timeline for a specific resource."""
    aq = _get_audit_query()
    return {"events": aq.get_resource_timeline(resource, limit=limit)}


@router.get("/stats")
def get_query_stats():
    """Get aggregate statistics for the query index."""
    aq = _get_audit_query()
    return aq.get_query_stats()


@router.get("/events/{event_id}")
def get_event(event_id: str):
    """Get a single indexed event by ID."""
    aq = _get_audit_query()
    result = aq.get_event(event_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Event {event_id} not found")
    return result


# ---------------------------------------------------------------------------
# Purge
# ---------------------------------------------------------------------------

@router.post("/purge")
def purge_index(body: PurgeRequest):
    """Purge index entries older than the given number of seconds."""
    aq = _get_audit_query()
    removed = aq.purge_index(older_than_seconds=body.older_than_seconds)
    return {"removed": removed}
