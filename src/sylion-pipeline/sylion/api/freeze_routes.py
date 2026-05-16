"""
SYLION API -- Contract Freeze routes

Manages contract freeze lifecycle for distributed parallel builds.
"""

from fastapi import APIRouter, HTTPException

from sylion.contracts.freeze_manager import get_freeze_manager

router = APIRouter(prefix="/api/v1")


def _get_freeze_manager() -> ContractFreezeManager:
    return get_freeze_manager()


@router.get("/contracts/freeze/status")
def freeze_status():
    """Get current contract freeze status."""
    return _get_freeze_manager().status()


@router.post("/contracts/freeze")
def freeze_contracts(body: dict):
    """Freeze contracts for a build.

    Body: {"build_id": str, "frozen_by": str, "contracts": [], "events": [], "dependencies": []}
    """
    try:
        return _get_freeze_manager().freeze(
            build_id=body["build_id"],
            frozen_by=body["frozen_by"],
            contracts=body.get("contracts", []),
            events=body.get("events", []),
            dependencies=body.get("dependencies", []),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/contracts/freeze/thaw")
def thaw_contracts(body: dict):
    """Thaw frozen contracts.

    Body: {"requested_by": str, "force": bool}
    """
    try:
        return _get_freeze_manager().thaw(
            requested_by=body.get("requested_by", "unknown"),
            force=body.get("force", False),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/contracts/freeze/check")
def check_change_permission(module_id: str, change_type: str):
    """Check if a change is permitted under current freeze."""
    return _get_freeze_manager().check_change_permission(module_id, change_type)


@router.get("/contracts/freeze/snapshot")
def frozen_snapshot():
    """Get full frozen snapshot for workers."""
    return _get_freeze_manager().get_frozen_snapshot()
