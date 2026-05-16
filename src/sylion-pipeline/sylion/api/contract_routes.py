"""
SYLION API -- Contract Registry routes.

Endpoints for the ContractRegistry module:
  register_contract, update_contract, deprecate_contract,
  get_contract, list_contracts,
  bind_contract, unbind, get_bindings, validate_binding.
"""

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/contracts", tags=["Contracts"])
manifest_router = APIRouter(prefix="/api/v1/manifests", tags=["Manifests"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_contract_registry = None


def _get_contract_registry():
    global _contract_registry
    if _contract_registry is not None:
        return _contract_registry
    from sylion.core.contract_registry import get_contract_registry
    _contract_registry = get_contract_registry()
    return _contract_registry


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RegisterContractRequest(BaseModel):
    name: str
    version: str
    spec_json: str | dict = "{}"


class UpdateContractRequest(BaseModel):
    new_version: str
    spec_json: str | dict = "{}"
    breaking_changes: str = ""


class BindContractRequest(BaseModel):
    contract_id: str
    consumer_module: str
    provider_module: str


class ValidateBindingRequest(BaseModel):
    contract_id: str
    consumer: str
    provider: str


# ---------------------------------------------------------------------------
# Contract CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def register_contract(
    body: RegisterContractRequest | None = Body(default=None),
    name: str | None = None,
    version: str = "1.0.0",
    spec_json: str | dict = "{}",
    contract_type: str = "grpc_service",
    producer_module: str = "",
    consumer_modules: str = "",
):
    """Register a new interface contract."""
    reg = _get_contract_registry()
    payload = body
    if payload is None:
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        spec_payload = spec_json
        if spec_payload == "{}" and (contract_type or producer_module or consumer_modules):
            spec_payload = {
                "contract_type": contract_type,
                "producer_module": producer_module,
                "consumer_modules": [
                    item.strip()
                    for item in consumer_modules.split(",")
                    if item.strip()
                ],
            }
        payload = RegisterContractRequest(
            name=name,
            version=version,
            spec_json=spec_payload,
        )
    try:
        return reg.register_contract(
            name=payload.name,
            version=payload.version,
            spec_json=payload.spec_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{contract_id}")
def update_contract(contract_id: str, body: UpdateContractRequest):
    """Update a contract with a new version (archives old version)."""
    reg = _get_contract_registry()
    try:
        result = reg.update_contract(
            contract_id=contract_id,
            new_version=body.new_version,
            spec_json=body.spec_json,
            breaking_changes=body.breaking_changes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    return result


@router.post("/{contract_id}/deprecate")
def deprecate_contract(contract_id: str):
    """Mark a contract as deprecated."""
    reg = _get_contract_registry()
    try:
        ok = reg.deprecate_contract(contract_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found or already deprecated")
    return {"contract_id": contract_id, "status": "deprecated"}


# ---------------------------------------------------------------------------
# Retrieval -- static paths before dynamic /{contract_id} paths
# ---------------------------------------------------------------------------

@router.get("")
@router.get("/list")
def list_contracts(active_only: bool = False, limit: int = 500):
    """List contracts, optionally filtering to active only."""
    reg = _get_contract_registry()
    return {"contracts": reg.list_contracts(active_only=active_only, limit=limit)}


@router.get("/{contract_id}/versions")
def list_contract_versions(contract_id: str):
    """Return versions for a contract name or id for dashboard history views."""
    reg = _get_contract_registry()
    versions = reg.list_versions(contract_id)
    if not versions:
        contract = reg.get_contract(contract_id)
        versions = [contract] if contract else []
    return {"contract_id": contract_id, "versions": versions}


@router.get("/{contract_id}/compatibility")
def check_contract_compatibility(contract_id: str, new_version: str):
    """Check whether a proposed version is compatible with the latest one."""
    reg = _get_contract_registry()
    return reg.check_compatibility(contract_id, new_version)


@router.get("/{contract_id}")
def get_contract(contract_id: str):
    """Retrieve a single contract by ID or latest-by-name."""
    reg = _get_contract_registry()
    result = reg.get_contract(contract_id) or reg.get(contract_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    return result


# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------

@router.post("/bindings", status_code=201)
def bind_contract(body: BindContractRequest):
    """Bind a consumer and provider module to a contract."""
    reg = _get_contract_registry()
    try:
        return reg.bind_contract(
            contract_id=body.contract_id,
            consumer_module=body.consumer_module,
            provider_module=body.provider_module,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/bindings/{binding_id}")
def unbind(binding_id: str):
    """Remove a binding by binding_id."""
    reg = _get_contract_registry()
    ok = reg.unbind(binding_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Binding {binding_id} not found")
    return {"binding_id": binding_id, "removed": True}


@router.get("/bindings")
def get_bindings(contract_id: str | None = None):
    """List bindings, optionally filtered by contract_id."""
    reg = _get_contract_registry()
    return {"bindings": reg.get_bindings(contract_id=contract_id)}


@router.post("/bindings/validate")
def validate_binding(body: ValidateBindingRequest):
    """Check if consumer/provider are bound and the contract is active."""
    reg = _get_contract_registry()
    return reg.validate_binding(
        contract_id=body.contract_id,
        consumer=body.consumer,
        provider=body.provider,
    )


# ---------------------------------------------------------------------------
# Manifest compatibility routes
# ---------------------------------------------------------------------------

@manifest_router.get("")
def list_manifests(kind: str | None = None, milestone: str | None = None,
                   lifecycle: str | None = None):
    """List module manifests from the core module registry."""
    from sylion.core.module_registry import get_registry

    registry = get_registry()
    return {"manifests": registry.list_modules(kind=kind,
                                               milestone=milestone,
                                               lifecycle=lifecycle)}


@manifest_router.post("/validate")
def validate_manifest(module_id: str, module_kind: str, owner_plan: str,
                      description: str = ""):
    """Validate a module manifest payload without registering it."""
    from sylion.core.module_registry import ModuleKind, ModuleManifest

    try:
        manifest = ModuleManifest(
            module_id=module_id,
            module_kind=ModuleKind(module_kind),
            owner_plan=owner_plan,
            description=description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"valid": True, "manifest": manifest.to_dict()}
