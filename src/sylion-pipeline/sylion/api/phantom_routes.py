"""
SYLION API -- Phantom Session routes.

Endpoints for the PhantomWrapper module:
  create_session, validate_session, record_operation,
  revoke_session, get_session, list_sessions, get_session_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/phantom", tags=["Phantom Sessions"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_phantom_wrapper = None


def _get_phantom_wrapper():
    global _phantom_wrapper
    if _phantom_wrapper is not None:
        return _phantom_wrapper
    from sylion.security.phantom_wrapper import get_phantom_wrapper
    _phantom_wrapper = get_phantom_wrapper()
    return _phantom_wrapper


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    user_id: str
    scope: str = ""
    ttl_seconds: int = 3600


class ValidateSessionRequest(BaseModel):
    session_id: str
    operation: str = ""


class RecordOperationRequest(BaseModel):
    session_id: str
    operation: str
    resource: str = ""
    result: str = ""


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

@router.post("/sessions", status_code=201)
def create_session(body: CreateSessionRequest):
    """Create an ephemeral scoped session."""
    wrapper = _get_phantom_wrapper()
    return wrapper.create_session(
        user_id=body.user_id,
        scope=body.scope,
        ttl_seconds=body.ttl_seconds,
    )


@router.post("/sessions/validate")
def validate_session(body: ValidateSessionRequest):
    """Validate a session for a given operation."""
    wrapper = _get_phantom_wrapper()
    return wrapper.validate_session(
        session_id=body.session_id,
        operation=body.operation,
    )


@router.post("/sessions/revoke")
def revoke_session(body: ValidateSessionRequest):
    """Revoke an active session."""
    wrapper = _get_phantom_wrapper()
    revoked = wrapper.revoke_session(body.session_id)
    if not revoked:
        raise HTTPException(status_code=404,
                            detail=f"Session {body.session_id} not found or already revoked")
    return {"revoked": True, "session_id": body.session_id}


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

@router.post("/operations/record", status_code=201)
def record_operation(body: RecordOperationRequest):
    """Record an operation within a session."""
    wrapper = _get_phantom_wrapper()
    try:
        return wrapper.record_operation(
            session_id=body.session_id,
            operation=body.operation,
            resource=body.resource,
            result=body.result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Retrieval -- static paths before dynamic /{...} paths
# ---------------------------------------------------------------------------

@router.get("/sessions")
def list_sessions(
    user_id: str | None = None,
    is_active: int | None = None,
):
    """List sessions, optionally filtered by user_id and/or active status."""
    wrapper = _get_phantom_wrapper()
    results = wrapper.list_sessions(user_id=user_id, is_active=is_active)
    return {"sessions": results, "count": len(results)}


@router.get("/sessions/stats")
def get_session_stats():
    """Return summary statistics for phantom sessions."""
    wrapper = _get_phantom_wrapper()
    return wrapper.get_session_stats()


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Return a single session by ID."""
    wrapper = _get_phantom_wrapper()
    result = wrapper.get_session(session_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Session {session_id} not found")
    return result
