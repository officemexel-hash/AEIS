"""
SYLION API -- Audit Trail routes.

Endpoints for the AuditTrailAggregator module:
  record, get_entry, query, count_by_action, count_by_actor,
  verify_integrity, get_stats.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sylion.security.rbac import requires_role

router = APIRouter(prefix="/api/v1/audit", tags=["Audit Trail"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_audit_trail_aggregator = None


def _get_audit_trail_aggregator():
    global _audit_trail_aggregator
    if _audit_trail_aggregator is not None:
        return _audit_trail_aggregator
    from sylion.security.audit_trail_aggregator import get_audit_trail_aggregator
    _audit_trail_aggregator = get_audit_trail_aggregator()
    return _audit_trail_aggregator


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RecordEventRequest(BaseModel):
    source: str
    action: str
    actor: str = ""
    resource: str = ""
    outcome: str = "success"
    metadata: dict | None = None


class QueryEventsRequest(BaseModel):
    source: str | None = None
    action: str | None = None
    actor: str | None = None
    resource: str | None = None
    outcome: str | None = None
    since: float | None = None
    until: float | None = None
    limit: int = 100


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

@router.post("/events", status_code=201)
def record_event(body: RecordEventRequest):
    """Record an audit entry with SHA-256 integrity hash."""
    agg = _get_audit_trail_aggregator()
    try:
        return agg.record(
            source=body.source,
            action=body.action,
            actor=body.actor,
            resource=body.resource,
            outcome=body.outcome,
            metadata=body.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Retrieval -- static paths before dynamic /{entry_id} paths
# ---------------------------------------------------------------------------

@router.post("/events/query")
def query_events(
    source: str | None = None,
    action: str | None = None,
    actor: str | None = None,
    resource: str | None = None,
    outcome: str | None = None,
    since: float | None = None,
    until: float | None = None,
    limit: int = 100,
):
    """Query audit entries with optional filters (newest first)."""
    agg = _get_audit_trail_aggregator()
    try:
        results = agg.query(
            source=source,
            action=action,
            actor=actor,
            resource=resource,
            outcome=outcome,
            since=since,
            until=until,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"events": results}


@router.get("/health")
def health() -> dict[str, object]:
    """F-005 follow-up (Kimi review): per-module health for audit trail."""
    import time
    return {
        "status": "ok",
        "module": "audit",
        "version": "3.5.0",
        "timestamp": time.time(),
    }


@router.get("/events")
def list_events(
    source: str | None = None,
    action: str | None = None,
    actor: str | None = None,
    resource: str | None = None,
    outcome: str | None = None,
    since: float | None = None,
    until: float | None = None,
    limit: int = 100,
):
    """List audit entries with optional filters (newest first)."""
    agg = _get_audit_trail_aggregator()
    try:
        results = agg.query(
            source=source,
            action=action,
            actor=actor,
            resource=resource,
            outcome=outcome,
            since=since,
            until=until,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"events": results}


@router.get("/events/by-module/{source}")
def get_events_by_module(
    source: str,
    action: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
):
    """Get audit entries filtered by source module."""
    agg = _get_audit_trail_aggregator()
    results = agg.query(
        source=source,
        action=action,
        outcome=outcome,
        limit=limit,
    )
    return {"events": results}


@router.get("/events/by-actor/{actor}")
def get_events_by_actor(
    actor: str,
    source: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
):
    """Get audit entries filtered by actor."""
    agg = _get_audit_trail_aggregator()
    results = agg.query(
        source=source,
        actor=actor,
        outcome=outcome,
        limit=limit,
    )
    return {"events": results}


@router.get("/events/{entry_id}")
def get_entry(entry_id: str):
    """Return a single audit entry by ID."""
    agg = _get_audit_trail_aggregator()
    result = agg.get_entry(entry_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Entry {entry_id} not found")
    return result


# ---------------------------------------------------------------------------
# Integrity verification
# ---------------------------------------------------------------------------

@router.post("/integrity-check")
def get_integrity_check(since: float | None = None):
    """Verify SHA-256 hash integrity of audit entries."""
    agg = _get_audit_trail_aggregator()
    return agg.verify_integrity(since=since)


@router.get("/integrity")
def get_governance_chain_integrity():
    """Verify the governance evidence-spine SHA-256 hash chain.

    Phase 3 W2.5: replays the entire chain from genesis. Returns the
    canonical chain integrity status used by W3 alerts and DR drills.
    Response shape: {valid, broken_at, total_entries, tampered_count}.
    On a healthy chain: ``valid == True`` and ``broken_at is None``.
    """
    from sylion.governance.audit_chain import get_audit_chain
    return get_audit_chain().verify()


# ---------------------------------------------------------------------------
# Aggregations
# ---------------------------------------------------------------------------

@router.get("/summary")
def get_summary():
    """Return summary statistics across audit entries and queries."""
    agg = _get_audit_trail_aggregator()
    return agg.get_stats()


@router.get("/counts/by-action")
def count_by_action(source: str | None = None):
    """Count entries grouped by action, optionally filtered by source."""
    agg = _get_audit_trail_aggregator()
    return {"counts": agg.count_by_action(source=source)}


@router.get("/counts/by-actor")
def count_by_actor(source: str | None = None):
    """Count entries grouped by actor, optionally filtered by source."""
    agg = _get_audit_trail_aggregator()
    return {"counts": agg.count_by_actor(source=source)}


# ---------------------------------------------------------------------------
# Export & purge
# ---------------------------------------------------------------------------

@router.post("/export")
def export_trail(
    source: str | None = None,
    action: str | None = None,
    actor: str | None = None,
    resource: str | None = None,
    outcome: str | None = None,
    since: float | None = None,
    until: float | None = None,
):
    """Export audit trail entries matching filters (no limit cap)."""
    agg = _get_audit_trail_aggregator()
    results = agg.query(
        source=source,
        action=action,
        actor=actor,
        resource=resource,
        outcome=outcome,
        since=since,
        until=until,
        limit=10000,
    )
    return {"entries": results, "count": len(results)}


@router.post("/purge")
def purge_old_events(older_than_seconds: float,
                     _user: str = Depends(requires_role("owner"))):
    """Purge audit entries older than the given number of seconds from now.

    Owner-only: this destroys evidence used by compliance and forensics.
    Uses query to find entries in the time range, then deletes them directly.
    """
    import time
    agg = _get_audit_trail_aggregator()
    cutoff = time.time() - older_than_seconds
    try:
        with agg._lock:
            cursor = agg._conn.execute(
                "DELETE FROM audit_entries WHERE timestamp < ?", (cutoff,)
            )
            agg._conn.commit()
            removed = cursor.rowcount
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"removed": removed, "cutoff_timestamp": cutoff}
