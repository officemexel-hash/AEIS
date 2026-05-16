"""
SYLION API -- Hardened Audit routes.

Endpoints for the HardenedAuditLogger module:
  log_event, verify_chain, tamper_check, get_events,
  export_events, get_chain.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/hardened-audit", tags=["Hardened Audit"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_hardened_audit = None


def _get_hardened_audit():
    global _hardened_audit
    if _hardened_audit is not None:
        return _hardened_audit
    from sylion.security.hardened_audit import get_hardened_audit
    _hardened_audit = get_hardened_audit()
    return _hardened_audit


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class LogEventRequest(BaseModel):
    event_type: str
    actor: str
    action: str
    resource: str = ""
    details_json: dict | str | None = None
    severity: str = "info"


class VerifyChainRequest(BaseModel):
    chain_id: str | None = None


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

@router.post("/events", status_code=201)
def log_event(body: LogEventRequest):
    """Record a tamper-evident audit event."""
    logger = _get_hardened_audit()
    try:
        return logger.log_event(
            event_type=body.event_type,
            actor=body.actor,
            action=body.action,
            resource=body.resource,
            details_json=body.details_json,
            severity=body.severity,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Chain operations -- static paths before dynamic /{...} paths
# ---------------------------------------------------------------------------

@router.post("/chain/verify")
def verify_chain(body: VerifyChainRequest):
    """Verify entire chain integrity."""
    logger = _get_hardened_audit()
    return logger.verify_chain(chain_id=body.chain_id)


@router.post("/chain/tamper-check")
def tamper_check():
    """Run a full tamper check on the audit chain."""
    logger = _get_hardened_audit()
    return logger.tamper_check()


# ---------------------------------------------------------------------------
# Querying -- static paths before dynamic /{...} paths
# ---------------------------------------------------------------------------

@router.get("/events")
def get_events(
    event_type: str | None = None,
    actor: str | None = None,
    limit: int = 100,
):
    """Get events with optional filters (newest first)."""
    logger = _get_hardened_audit()
    results = logger.get_events(
        event_type=event_type,
        actor=actor,
        limit=limit,
    )
    return {"events": results, "count": len(results)}


@router.get("/events/export")
def export_events(since: float | None = None):
    """Export events in chronological order, optionally since timestamp."""
    logger = _get_hardened_audit()
    results = logger.export_events(since=since)
    return {"events": results, "count": len(results)}


@router.get("/chains/{chain_id}")
def get_chain(chain_id: str):
    """Return chain metadata by chain_id."""
    logger = _get_hardened_audit()
    result = logger.get_chain(chain_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Chain {chain_id} not found")
    return result
