"""
SYLION API -- Decision Snapshot routes.

Endpoints for: decision_snapshot manager
(create, get, list, compare, timeline).
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/v1/decision-snapshots",
    tags=["Decision Snapshots"],
)


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_snapshots = None


def _get_snapshots():
    global _snapshots
    if _snapshots is not None:
        return _snapshots
    from sylion.governance.decision_snapshot import get_decision_snapshot_manager
    _snapshots = get_decision_snapshot_manager()
    return _snapshots


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class FactorInput(BaseModel):
    name: str
    value: str = ""
    weight: float = 1.0


class CreateSnapshotRequest(BaseModel):
    decision_id: str
    context: Optional[dict] = None
    outcome: str = "approved"
    confidence: float = 1.0
    factors: Optional[list[FactorInput]] = None


class CompareSnapshotsRequest(BaseModel):
    snapshot_id_1: str
    snapshot_id_2: str


# ---------------------------------------------------------------------------
# Endpoints -- static routes before parameterized /{id} routes
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_snapshot(body: CreateSnapshotRequest):
    """Create a new decision snapshot."""
    mgr = _get_snapshots()
    try:
        factors_list = (
            [f.model_dump() for f in body.factors] if body.factors else None
        )
        return mgr.create_snapshot(
            decision_id=body.decision_id,
            context_json=body.context,
            outcome=body.outcome,
            confidence=body.confidence,
            factors_list=factors_list,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
def list_snapshots(decision_id: Optional[str] = None,
                   limit: int = 100):
    """List snapshots, optionally filtered by decision_id."""
    mgr = _get_snapshots()
    return {"snapshots": mgr.list_snapshots(decision_id=decision_id,
                                            limit=limit)}


@router.post("/compare")
def compare_snapshots(body: CompareSnapshotsRequest):
    """Compare two snapshots and return a diff."""
    mgr = _get_snapshots()
    result = mgr.compare_snapshots(body.snapshot_id_1, body.snapshot_id_2)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="One or both snapshots not found",
        )
    return result


@router.get("/timeline/{decision_id}")
def get_timeline(decision_id: str):
    """Get an ordered timeline of snapshots for a decision."""
    mgr = _get_snapshots()
    return {"timeline": mgr.get_timeline(decision_id)}


@router.get("/{snapshot_id}")
def get_snapshot(snapshot_id: str):
    """Retrieve a single snapshot with its factors."""
    mgr = _get_snapshots()
    result = mgr.get_snapshot(snapshot_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Snapshot {snapshot_id} not found",
        )
    return result
