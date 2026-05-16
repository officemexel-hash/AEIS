"""
SYLION API -- VPS (Virtual Provider Substrate) routes.

Endpoints for ProviderManager:
  create_provider, get_provider, list_providers, update_provider,
  transition_state, delete_provider,
  allocate, release_allocation, list_allocations,
  update_certification, list_certifications,
  record_probe, list_probes,
  get_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/vps", tags=["VPS"])

_manager = None


def _get_manager():
    global _manager
    if _manager is not None:
        return _manager
    from sylion.vps.provider_manager import get_provider_manager
    _manager = get_provider_manager()
    return _manager


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateProviderRequest(BaseModel):
    name: str
    tier: str = "STANDARD"
    region: str = ""
    vcpu_total: int = 0
    ram_gb_total: int = 0
    storage_gb_total: int = 0
    price_vcpu_h_usd: float = 0.0


class UpdateProviderRequest(BaseModel):
    name: str | None = None
    tier: str | None = None
    region: str | None = None
    vcpu_total: int | None = None
    ram_gb_total: int | None = None
    storage_gb_total: int | None = None
    price_vcpu_h_usd: float | None = None
    rebuild_role: str | None = None
    cutover_strategy: str | None = None


class AllocateRequest(BaseModel):
    provider_id: str
    run_id: str
    vcpu: int
    ram_gb: int


class CertUpdateRequest(BaseModel):
    state: str
    decision_class: str = ""
    reviewer_id: str = ""


class ProbeRequest(BaseModel):
    up: bool = True
    latency_ms: int = 0
    cpu_pct: float = 0.0
    ram_pct: float = 0.0
    iops: int = 0
    error_code: str = ""


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

@router.post("/providers", status_code=201)
def create_provider(body: CreateProviderRequest):
    """Register a new VPS provider."""
    mgr = _get_manager()
    try:
        return mgr.create_provider(
            name=body.name,
            tier=body.tier,
            region=body.region,
            vcpu_total=body.vcpu_total,
            ram_gb_total=body.ram_gb_total,
            storage_gb_total=body.storage_gb_total,
            price_vcpu_h_usd=body.price_vcpu_h_usd,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/providers")
def list_providers(state: str | None = None, tier: str | None = None, limit: int = 500):
    """List providers with optional filters."""
    mgr = _get_manager()
    return {"providers": mgr.list_providers(state=state, tier=tier, limit=limit)}


@router.get("/providers/{provider_id}")
def get_provider(provider_id: str):
    """Get a provider by ID."""
    mgr = _get_manager()
    result = mgr.get_provider(provider_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    return result


@router.patch("/providers/{provider_id}")
def update_provider(provider_id: str, body: UpdateProviderRequest):
    """Update provider fields."""
    mgr = _get_manager()
    result = mgr.update_provider(provider_id, **body.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    return result


@router.post("/providers/{provider_id}/transition")
def transition_provider_state(provider_id: str, new_state: str):
    """Transition provider state (candidate->qualified->approved->review->blocked)."""
    mgr = _get_manager()
    try:
        return mgr.transition_state(provider_id, new_state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: str):
    """Delete a provider."""
    mgr = _get_manager()
    deleted = mgr.delete_provider(provider_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    return {"deleted": True, "provider_id": provider_id}


# ---------------------------------------------------------------------------
# Allocations
# ---------------------------------------------------------------------------

@router.post("/allocations", status_code=201)
def allocate(body: AllocateRequest):
    """Allocate resources on a provider."""
    mgr = _get_manager()
    return mgr.allocate(
        provider_id=body.provider_id,
        run_id=body.run_id,
        vcpu=body.vcpu,
        ram_gb=body.ram_gb,
    )


@router.post("/allocations/{alloc_id}/release")
def release_allocation(alloc_id: str):
    """Release an active allocation."""
    mgr = _get_manager()
    released = mgr.release_allocation(alloc_id)
    if not released:
        raise HTTPException(status_code=404, detail=f"Allocation {alloc_id} not found or already released")
    return {"released": True, "alloc_id": alloc_id}


@router.get("/allocations")
def list_allocations(provider_id: str | None = None, run_id: str | None = None,
                     state: str | None = None, limit: int = 500):
    """List allocations."""
    mgr = _get_manager()
    return {"allocations": mgr.list_allocations(provider_id=provider_id, run_id=run_id,
                                                state=state, limit=limit)}


# ---------------------------------------------------------------------------
# Certifications
# ---------------------------------------------------------------------------

@router.get("/providers/{provider_id}/certifications")
def list_certifications(provider_id: str):
    """List certification stages for a provider."""
    mgr = _get_manager()
    return {"certifications": mgr.list_certifications(provider_id)}


@router.patch("/certifications/{stage_id}")
def update_certification(stage_id: str, body: CertUpdateRequest):
    """Update certification stage state."""
    mgr = _get_manager()
    result = mgr.update_certification(
        stage_id=stage_id,
        state=body.state,
        decision_class=body.decision_class,
        reviewer_id=body.reviewer_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Certification stage {stage_id} not found")
    return result


# ---------------------------------------------------------------------------
# Health probes
# ---------------------------------------------------------------------------

@router.post("/providers/{provider_id}/probes", status_code=201)
def record_probe(provider_id: str, body: ProbeRequest):
    """Record a health probe for a provider."""
    mgr = _get_manager()
    return mgr.record_probe(
        provider_id=provider_id,
        up=body.up,
        latency_ms=body.latency_ms,
        cpu_pct=body.cpu_pct,
        ram_pct=body.ram_pct,
        iops=body.iops,
        error_code=body.error_code,
    )


@router.get("/providers/{provider_id}/probes")
def list_probes(provider_id: str, limit: int = 100):
    """List health probes for a provider."""
    mgr = _get_manager()
    return {"probes": mgr.list_probes(provider_id, limit=limit)}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def vps_stats():
    """Get VPS aggregate statistics."""
    mgr = _get_manager()
    return mgr.get_stats()
