"""
SYLION API -- Version Manager routes.

Endpoints for the VersionManager module:
  create_version, get_version, list_versions, get_latest,
  deprecate_version, add_dependency, get_dependencies,
  compare_versions, get_version_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/versions", tags=["Versions"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_version_manager = None


def _get_version_manager():
    global _version_manager
    if _version_manager is not None:
        return _version_manager
    from sylion.core.version_manager import get_version_manager
    _version_manager = get_version_manager()
    return _version_manager


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateVersionRequest(BaseModel):
    module_id: str
    version: str
    spec_json: dict | str | None = None
    changelog: str | None = None


class AddDependencyRequest(BaseModel):
    version_id: str
    depends_on_version_id: str
    dep_type: str = "requires"


class CompareRequest(BaseModel):
    v1_id: str
    v2_id: str


# ---------------------------------------------------------------------------
# Version CRUD
# ---------------------------------------------------------------------------


@router.get("")
def list_versions_root(module_id: str | None = None, active_only: bool = False, limit: int = 500):
    """List versions with optional filters."""
    vm = _get_version_manager()
    return {"versions": vm.list_versions(module_id=module_id, active_only=active_only, limit=limit)}



@router.post("", status_code=201)
def create_version(body: CreateVersionRequest):
    """Register a new version for a module."""
    vm = _get_version_manager()
    try:
        return vm.create_version(
            module_id=body.module_id,
            version=body.version,
            spec_json=body.spec_json,
            changelog=body.changelog,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Retrieval -- static paths before dynamic /{version_id} paths
# ---------------------------------------------------------------------------

@router.get("/list")
def list_versions(module_id: str | None = None, active_only: bool = False, limit: int = 500):
    """List versions with optional filters."""
    vm = _get_version_manager()
    return {"versions": vm.list_versions(module_id=module_id, active_only=active_only, limit=limit)}


@router.get("/latest/{module_id}")
def get_latest(module_id: str):
    """Get the most recent active, non-deprecated version for a module."""
    vm = _get_version_manager()
    result = vm.get_latest(module_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No active version found for module '{module_id}'")
    return result


@router.get("/stats")
def get_version_stats():
    """Aggregate version statistics."""
    vm = _get_version_manager()
    return vm.get_version_stats()


@router.get("/{version_id}")
def get_version(version_id: str):
    """Retrieve a version by ID."""
    vm = _get_version_manager()
    result = vm.get_version(version_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")
    return result


# ---------------------------------------------------------------------------
# Deprecation
# ---------------------------------------------------------------------------

@router.post("/{version_id}/deprecate")
def deprecate_version(version_id: str):
    """Mark a version as deprecated."""
    vm = _get_version_manager()
    ok = vm.deprecate_version(version_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")
    return {"version_id": version_id, "deprecated": True}


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

@router.post("/dependencies", status_code=201)
def add_dependency(body: AddDependencyRequest):
    """Create a dependency edge between two versions."""
    vm = _get_version_manager()
    try:
        return vm.add_dependency(
            version_id=body.version_id,
            depends_on_version_id=body.depends_on_version_id,
            dep_type=body.dep_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{version_id}/dependencies")
def get_dependencies(version_id: str):
    """Get all dependencies for a given version."""
    vm = _get_version_manager()
    return {"dependencies": vm.get_dependencies(version_id)}


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

@router.post("/compare")
def compare_versions(body: CompareRequest):
    """Compare two versions. Returns differences and dependency overlaps."""
    vm = _get_version_manager()
    try:
        result = vm.compare_versions(body.v1_id, body.v2_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
