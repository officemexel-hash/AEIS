"""
SYLION API -- Bundle Assembler routes.

Endpoints for the BundleAssembler module:
  create_bundle, get_bundle, list_bundles,
  add_component, remove_component,
  create_version, get_version, list_versions,
  deploy_bundle.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sylion.aeis.advisor.events.lifecycle import (
    await_advisor_decision,
    publish_lifecycle_event,
)
from sylion.governance.deployment_gate import (
    ensure_production_deployment_gate,
    requires_production_gate,
)

router = APIRouter(prefix="/api/v1/bundles", tags=["Bundles"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_bundle_assembler = None


def _get_bundle_assembler():
    global _bundle_assembler
    if _bundle_assembler is not None:
        return _bundle_assembler
    from sylion.core.bundle_assembler import get_bundle_assembler
    _bundle_assembler = get_bundle_assembler()
    return _bundle_assembler


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateBundleRequest(BaseModel):
    name: str
    description: str = ""
    components: list[dict] | None = None


class AddComponentRequest(BaseModel):
    bundle_id: str
    component_type: str
    component_ref: str
    config_json: str | dict = "{}"


class CreateVersionRequest(BaseModel):
    bundle_id: str
    version_tag: str


class DeployBundleRequest(BaseModel):
    bundle_id: str
    target_env: str
    approval_ticket_id: str = ""


# ---------------------------------------------------------------------------
# Bundle CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_bundle(body: CreateBundleRequest):
    """Create a new bundle, optionally with initial components."""
    asm = _get_bundle_assembler()
    try:
        return asm.create_bundle(
            name=body.name,
            description=body.description,
            components_list=body.components,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Retrieval -- static paths before dynamic /{bundle_id} paths
# ---------------------------------------------------------------------------

@router.get("/list")
def list_bundles(status: str | None = None, limit: int = 500):
    """List bundles, optionally filtered by status."""
    asm = _get_bundle_assembler()
    return {"bundles": asm.list_bundles(status=status, limit=limit)}


@router.get("/{bundle_id}")
def get_bundle(bundle_id: str):
    """Retrieve a bundle with all its components."""
    asm = _get_bundle_assembler()
    result = asm.get_bundle(bundle_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Bundle {bundle_id} not found")
    return result


# ---------------------------------------------------------------------------
# Component management
# ---------------------------------------------------------------------------

@router.post("/components", status_code=201)
def add_component(body: AddComponentRequest):
    """Add a component to an existing bundle."""
    asm = _get_bundle_assembler()
    try:
        return asm.add_component(
            bundle_id=body.bundle_id,
            component_type=body.component_type,
            component_ref=body.component_ref,
            config_json=body.config_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/components/{bundle_id}/{component_id}")
def remove_component(bundle_id: str, component_id: str):
    """Remove a component from a bundle."""
    asm = _get_bundle_assembler()
    try:
        ok = asm.remove_component(bundle_id, component_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="Component not found in bundle")
    return {"bundle_id": bundle_id, "component_id": component_id, "removed": True}


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

@router.post("/versions", status_code=201)
def create_version(body: CreateVersionRequest):
    """Snapshot the current state of a bundle as a version."""
    asm = _get_bundle_assembler()
    try:
        result = asm.create_version(
            bundle_id=body.bundle_id,
            version_tag=body.version_tag,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Bundle {body.bundle_id} not found")
    return result


@router.get("/{bundle_id}/versions")
def list_versions(bundle_id: str):
    """List all versions for a bundle."""
    asm = _get_bundle_assembler()
    return {"versions": asm.list_versions(bundle_id)}


@router.get("/{bundle_id}/versions/{version_tag}")
def get_version(bundle_id: str, version_tag: str):
    """Retrieve a specific version of a bundle."""
    asm = _get_bundle_assembler()
    result = asm.get_version(bundle_id, version_tag)
    if not result:
        raise HTTPException(status_code=404, detail=f"Version {version_tag} not found for bundle {bundle_id}")
    return result


# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------

@router.post("/deploy", status_code=202)
def deploy_bundle(body: DeployBundleRequest):
    """Deploy a bundle to a target environment."""
    asm = _get_bundle_assembler()
    try:
        bundle = asm.get_bundle(body.bundle_id)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Bundle {body.bundle_id} not found")
        if requires_production_gate(body.target_env):
            gate = ensure_production_deployment_gate(
                action="bundle.deploy",
                target=body.target_env,
                approval_ticket_id=body.approval_ticket_id,
                payload={"bundle_id": body.bundle_id, "target_env": body.target_env},
            )
            if not gate.get("allowed"):
                raise HTTPException(status_code=423, detail=gate)
        event_id = publish_lifecycle_event(
            "aeis.production.deploy_requested",
            {
                "operator_id": "operator",
                "project_id": body.bundle_id,
                "masterplan_id": "",
                "bundle_id": body.bundle_id,
                "sot_approved": True,
                "council_approved": False,
            },
            source_module="sylion.api.bundle_routes",
            primary_key=body.bundle_id,
        )
        decision = await_advisor_decision(event_id)
        if decision.get("decision") == "block":
            raise HTTPException(status_code=423, detail=decision)
        if decision.get("decision") == "defer_to_human_gate":
            raise HTTPException(status_code=202, detail=decision)
        result = asm.deploy_bundle(
            bundle_id=body.bundle_id,
            target_env=body.target_env,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result
