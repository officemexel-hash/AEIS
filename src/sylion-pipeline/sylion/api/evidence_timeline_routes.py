"""
SYLION API -- Evidence Timeline routes.

Endpoints for the EvidenceTimeline governance module:
  create_timeline, get_timeline, list_timelines, delete_timeline,
  add_event, get_events, get_event, get_stats.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/evidence-timeline", tags=["Evidence Timeline"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_evidence_timeline = None


def _get_evidence_timeline():
    global _evidence_timeline
    if _evidence_timeline is not None:
        return _evidence_timeline
    from sylion.governance.evidence_timeline import get_evidence_timeline
    _evidence_timeline = get_evidence_timeline()
    return _evidence_timeline


# ---------------------------------------------------------------------------
# Timeline CRUD -- static paths before dynamic /{timeline_id} paths
# ---------------------------------------------------------------------------

@router.post("/timelines", status_code=201)
def create_timeline(name: str, description: str = ""):
    """Create a new evidence timeline."""
    et = _get_evidence_timeline()
    return et.create_timeline(name, description=description)


@router.get("/timelines")
def list_timelines(limit: int = 50):
    """List timelines ordered by most recently updated."""
    et = _get_evidence_timeline()
    return {"timelines": et.list_timelines(limit=limit)}


@router.get("/timelines/stats")
def timeline_stats():
    """Get aggregate timeline and event statistics."""
    et = _get_evidence_timeline()
    return et.get_stats()


@router.get("/timelines/{timeline_id}")
def get_timeline(timeline_id: str):
    """Get a single timeline by ID."""
    et = _get_evidence_timeline()
    result = et.get_timeline(timeline_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Timeline {timeline_id} not found")
    return result


@router.post("/timelines/{timeline_id}/verify")
def verify_timeline(timeline_id: str):
    """Verify timeline integrity for dashboard audit controls."""
    et = _get_evidence_timeline()
    timeline = et.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404,
                            detail=f"Timeline {timeline_id} not found")
    events = et.get_events(timeline_id, limit=10000)
    missing_ids = [idx for idx, event in enumerate(events) if not event.get("event_id")]
    return {
        "timeline_id": timeline_id,
        "verified": not missing_ids,
        "events_checked": len(events),
        "issues": [
            {"index": idx, "issue": "missing_event_id"}
            for idx in missing_ids
        ],
    }


@router.delete("/timelines/{timeline_id}")
def delete_timeline(timeline_id: str):
    """Delete a timeline and all its events."""
    et = _get_evidence_timeline()
    deleted = et.delete_timeline(timeline_id)
    if not deleted:
        raise HTTPException(status_code=404,
                            detail=f"Timeline {timeline_id} not found")
    return {"deleted": timeline_id}


# ---------------------------------------------------------------------------
# Events -- static paths before dynamic /{event_id} paths
# ---------------------------------------------------------------------------

@router.post("/events", status_code=201)
def add_event(
    timeline_id: str,
    event_type: str,
    title: str,
    description: str = "",
    source_module: str = "",
    actor: str = "",
    evidence_ref: str = "",
    metadata: str = "",
):
    """Add an event to a timeline.

    event_type must be one of: decision, evidence, action, observation,
    milestone, alert.
    metadata should be a JSON string if provided.
    """
    import json as _json

    et = _get_evidence_timeline()
    parsed_metadata = _json.loads(metadata) if metadata else None
    try:
        return et.add_event(
            timeline_id,
            event_type,
            title,
            description=description,
            source_module=source_module,
            actor=actor,
            evidence_ref=evidence_ref,
            metadata=parsed_metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/events")
def get_events(
    timeline_id: str,
    event_type: Optional[str] = None,
    since: Optional[float] = None,
    limit: int = 200,
):
    """List events for a timeline ordered by timestamp ascending."""
    et = _get_evidence_timeline()
    return {"events": et.get_events(
        timeline_id,
        event_type=event_type,
        since=since,
        limit=limit,
    )}


@router.get("/events/{event_id}")
def get_event(event_id: str):
    """Get a single event by ID."""
    et = _get_evidence_timeline()
    result = et.get_event(event_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Event {event_id} not found")
    return result
