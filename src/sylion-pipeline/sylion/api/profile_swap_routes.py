"""
SYLION API -- Profile Swap routes.

Endpoints for the ProfileSwapManager module:
  request_swap, approve_swap, reject_swap, execute_swap,
  get_swap, list_swaps, get_swap_audit, get_swap_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/profile-swaps", tags=["Profile Swaps"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_profile_swap = None


def _get_profile_swap():
    global _profile_swap
    if _profile_swap is not None:
        return _profile_swap
    from sylion.security.profile_swap import get_profile_swap
    _profile_swap = get_profile_swap()
    return _profile_swap


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RequestSwapRequest(BaseModel):
    target_id: str
    from_profile: str
    to_profile: str
    reason: str = ""


class ApproveSwapRequest(BaseModel):
    approver: str


class RejectSwapRequest(BaseModel):
    approver: str
    reason: str = ""


# ---------------------------------------------------------------------------
# Swap lifecycle -- static paths before dynamic /{swap_id} paths
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def request_swap(body: RequestSwapRequest):
    """Request a profile swap."""
    mgr = _get_profile_swap()
    try:
        return mgr.request_swap(
            target_id=body.target_id,
            from_profile=body.from_profile,
            to_profile=body.to_profile,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/list")
def list_swaps(status: str | None = None):
    """List swap requests, optionally filtered by status."""
    mgr = _get_profile_swap()
    try:
        return {"swaps": mgr.list_swaps(status=status)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/stats")
def get_swap_stats():
    """Get aggregate statistics about profile swaps."""
    mgr = _get_profile_swap()
    return mgr.get_swap_stats()


# ---------------------------------------------------------------------------
# Dynamic paths
# ---------------------------------------------------------------------------

@router.get("/{swap_id}")
def get_swap(swap_id: str):
    """Retrieve a swap request by ID."""
    mgr = _get_profile_swap()
    result = mgr.get_swap(swap_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Swap {swap_id} not found")
    return result


@router.post("/{swap_id}/approve")
def approve_swap(swap_id: str, body: ApproveSwapRequest):
    """Approve a pending swap request."""
    mgr = _get_profile_swap()
    try:
        result = mgr.approve_swap(swap_id, approver=body.approver)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Swap {swap_id} not found")
    return result


@router.post("/{swap_id}/reject")
def reject_swap(swap_id: str, body: RejectSwapRequest):
    """Reject a pending swap request."""
    mgr = _get_profile_swap()
    try:
        result = mgr.reject_swap(
            swap_id, approver=body.approver, reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Swap {swap_id} not found")
    return result


@router.post("/{swap_id}/execute")
def execute_swap(swap_id: str):
    """Execute an approved swap request."""
    mgr = _get_profile_swap()
    try:
        result = mgr.execute_swap(swap_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Swap {swap_id} not found")
    return result


@router.get("/{swap_id}/audit")
def get_swap_audit(swap_id: str):
    """Get the audit trail for a swap request."""
    mgr = _get_profile_swap()
    return {"audit": mgr.get_swap_audit(swap_id)}
