"""
SYLION API -- Code Snapshot routes.

Endpoints for: code_snapshot engine (create, list, diff, rollback, delete).
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/snapshots", tags=["snapshots"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_snapshot_engine = None


def _get_snapshot_engine():
    global _snapshot_engine
    if _snapshot_engine is not None:
        return _snapshot_engine
    from sylion.core.code_snapshot import get_code_snapshot_engine
    _snapshot_engine = get_code_snapshot_engine()
    return _snapshot_engine


# ---------------------------------------------------------------------------
# Endpoints
# (static routes before parameterized /{snapshot_id} routes)
# ---------------------------------------------------------------------------

@router.get("/latest/{module_id}")
def get_latest_snapshot(module_id: str):
    """Get the latest snapshot for a module."""
    result = _get_snapshot_engine().get_latest_snapshot(module_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"No snapshot found for module {module_id}")
    return result


@router.get("/")
def list_snapshots(module_id: str | None = None, limit: int = 100):
    """List snapshots, optionally filtered by module."""
    return {"snapshots": _get_snapshot_engine().list_snapshots(
        module_id=module_id, limit=limit,
    )}


@router.post("/", status_code=201)
def create_snapshot(module_id: str, version: str, file_path: str,
                    content: str, metadata: str = ""):
    """Create a new code snapshot."""
    import json as _json
    md = _json.loads(metadata) if metadata else None
    return _get_snapshot_engine().create_snapshot(
        module_id, version, file_path, content, metadata=md,
    )


@router.post("/{from_id}/diff/{to_id}")
def diff_snapshots(from_id: str, to_id: str):
    """Compute diff between two snapshots."""
    engine = _get_snapshot_engine()
    try:
        return engine.diff_snapshots(from_id, to_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{snapshot_id}/rollback")
def rollback_snapshot(snapshot_id: str):
    """Roll back to a specific snapshot."""
    result = _get_snapshot_engine().rollback_to_snapshot(snapshot_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Snapshot {snapshot_id} not found")
    return result


@router.get("/{snapshot_id}")
def get_snapshot(snapshot_id: str):
    """Get a single snapshot by ID."""
    result = _get_snapshot_engine().get_snapshot(snapshot_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Snapshot {snapshot_id} not found")
    return result


@router.delete("/{snapshot_id}")
def delete_snapshot(snapshot_id: str):
    """Delete a snapshot."""
    deleted = _get_snapshot_engine().delete_snapshot(snapshot_id)
    if not deleted:
        raise HTTPException(status_code=404,
                            detail=f"Snapshot {snapshot_id} not found")
    return {"deleted": snapshot_id}
