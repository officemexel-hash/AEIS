"""REST routes for Skills Marketplace demo (W14 E11, D5 supply-chain)."""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("sylion.api.demo_marketplace")
router = APIRouter(prefix="/api/v1/reference/marketplace", tags=["reference:marketplace"])

_svc: Any = None


def _service():
    global _svc
    if _svc is None:
        from sylion.demo.skills_marketplace import (
            MarketplaceService, MarketplaceStore,
        )
        db_path = os.environ.get("SYLION_DEMO_MARKETPLACE_DB", "sylion_aeis.db")
        _svc = MarketplaceService(store=MarketplaceStore(db_path=db_path))
    return _svc


class UploadIn(BaseModel):
    name: str
    version: str
    author_id: str
    sha256: str
    signature_pubkey: str
    description: str = ""
    cost_budget_usd: float = 10.0


class DependencyIn(BaseModel):
    dep_name: str
    dep_version_pin: str   # MUST be exact (no ranges)
    dep_sha256: str


class ScanIn(BaseModel):
    findings: list[dict] = []


class ReviewIn(BaseModel):
    reviewer_id: str
    decision: str          # approve | reject | request_changes
    rationale: str = ""


class ApproveIn(BaseModel):
    council_session_id: str


@router.get("/health")
def health() -> dict:
    try:
        return {"ok": True, **_service()._store.health()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/skills", status_code=201)
def upload_skill(body: UploadIn) -> dict:
    try:
        s = _service().upload_skill(
            body.name, body.version, body.author_id,
            body.sha256, body.signature_pubkey,
            body.description, body.cost_budget_usd,
        )
        return {"skill_id": s.skill_id, "name": s.name,
                "version": s.version, "status": s.status}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/skills")
def list_skills(name: str | None = None) -> dict:
    if name:
        items = _service()._store.find_by_name(name)
    else:
        # Use list_public if available â€” fallback: use raw conn
        store = _service()._store
        with store._lock:
            rows = store._conn.execute(
                "SELECT * FROM marketplace_skills "
                "ORDER BY created_at DESC LIMIT 100",
            ).fetchall()
        items = [store._row_to_skill(r) for r in rows]
    return {
        "items": [
            {"skill_id": s.skill_id, "name": s.name,
             "version": s.version, "author_id": s.author_id,
             "status": s.status, "cost_budget_usd": s.cost_budget_usd}
            for s in items
        ],
        "total": len(items),
    }


@router.get("/skills/{skill_id}")
def get_skill(skill_id: str) -> dict:
    s = _service()._store.get_skill(skill_id)
    if s is None:
        raise HTTPException(status_code=404, detail="not found")
    deps = _service()._store.list_dependencies(skill_id)
    scan = _service()._store.get_latest_scan(skill_id)
    return {
        "skill_id": s.skill_id, "name": s.name, "version": s.version,
        "author_id": s.author_id, "description": s.description,
        "status": s.status, "cost_budget_usd": s.cost_budget_usd,
        "council_session_id": s.council_session_id,
        "approved_at": s.approved_at,
        "dependencies": [
            {"dep_name": d.dep_name, "dep_version_pin": d.dep_version_pin,
             "dep_sha256": d.dep_sha256} for d in deps
        ],
        "latest_scan": {
            "scan_id": scan.scan_id, "severity_max": scan.severity_max,
            "findings_count": len(scan.findings),
            "scanned_at": scan.scanned_at,
        } if scan else None,
    }


@router.post("/skills/{skill_id}/dependencies", status_code=201)
def declare_dependency(skill_id: str, body: DependencyIn) -> dict:
    try:
        d = _service().declare_dependency(
            skill_id, body.dep_name, body.dep_version_pin, body.dep_sha256,
        )
        return {"dep_id": d.dep_id, "dep_name": d.dep_name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/skills/{skill_id}/scan", status_code=201)
def run_scan(skill_id: str, body: ScanIn) -> dict:
    """D5 mandatory scan. high/critical findings -> auto scan_failed."""
    try:
        scan = _service().run_static_scan(skill_id, findings=body.findings)
        return {
            "scan_id": scan.scan_id, "severity_max": scan.severity_max,
            "skill_status": _service()._store.get_skill(skill_id).status,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/skills/{skill_id}/reviews", status_code=201)
def submit_review(skill_id: str, body: ReviewIn) -> dict:
    try:
        r = _service().submit_review(
            skill_id, body.reviewer_id, body.decision, body.rationale,
        )
        return {"review_id": r.review_id, "decision": r.decision}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/skills/{skill_id}/approve")
def approve_skill(skill_id: str, body: ApproveIn) -> dict:
    """D5 approval â€” REQUIRES council_session_id."""
    try:
        s = _service().approve_skill(skill_id, body.council_session_id)
        return {"skill_id": s.skill_id, "status": s.status,
                "approved_at": s.approved_at}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/skills/{skill_id}/can-execute")
def can_execute(skill_id: str, projected_cost_usd: float = 0.0) -> dict:
    """Pre-execution budget guard (anti runaway-cost)."""
    return _service().can_execute(skill_id, projected_cost_usd)


__all__ = ["router"]

