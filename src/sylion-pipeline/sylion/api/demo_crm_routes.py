"""REST routes for Operator CRM demo (W14 E11, D4 PII)."""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("sylion.api.demo_crm")
router = APIRouter(prefix="/api/v1/reference/crm", tags=["reference:crm"])

_svc: Any = None


def _service():
    global _svc
    if _svc is None:
        from sylion.demo.operator_crm import CrmService, CrmStore
        db_path = os.environ.get("SYLION_DEMO_CRM_DB", "sylion_aeis.db")
        _svc = CrmService(store=CrmStore(db_path=db_path))
    return _svc


class CreateContactIn(BaseModel):
    actor_id: str
    full_name: str
    email: str
    phone: str = ""
    role: str = "lead"


class GdprDeleteIn(BaseModel):
    actor_id: str
    hg_ticket_id: str


class MergeIn(BaseModel):
    actor_id: str
    survivor_id: str
    merged_id: str
    conflict_resolution: dict | None = None


class RoleChangeIn(BaseModel):
    actor_id: str
    new_role: str
    actor_role: str = "operator"
    hg_ticket_id: str | None = None


@router.get("/health")
def health() -> dict:
    try:
        return {"ok": True, **_service()._store.health()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/contacts", status_code=201)
def create_contact(body: CreateContactIn) -> dict:
    try:
        c = _service().create_contact(
            body.actor_id, body.full_name, body.email,
            body.phone, body.role,
        )
        return {"contact_id": c.contact_id, "email": c.email,
                "role": c.role, "status": c.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/contacts")
def list_contacts(status: str | None = None, limit: int = 100) -> dict:
    items = _service()._store.list_contacts(status=status, limit=limit)
    return {
        "items": [
            {"contact_id": c.contact_id, "full_name": c.full_name,
             "email": c.email, "role": c.role, "status": c.status}
            for c in items
        ],
        "total": len(items),
    }


@router.get("/contacts/{contact_id}")
def get_contact(contact_id: str) -> dict:
    c = _service()._store.get_contact(contact_id)
    if c is None:
        raise HTTPException(status_code=404, detail="not found")
    return {
        "contact_id": c.contact_id, "full_name": c.full_name,
        "email": c.email, "phone": c.phone, "role": c.role,
        "status": c.status, "merged_into": c.merged_into,
        "deleted_at": c.deleted_at,
    }


@router.delete("/contacts/{contact_id}")
def gdpr_delete(contact_id: str, body: GdprDeleteIn) -> dict:
    """D4 GDPR delete â€” REQUIRES hg_ticket_id."""
    try:
        _service().gdpr_delete(body.actor_id, contact_id,
                                hg_ticket_id=body.hg_ticket_id)
        return {"contact_id": contact_id, "status": "deleted_gdpr"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/contacts/merge")
def merge_contacts(body: MergeIn) -> dict:
    try:
        survivor = _service().merge_contacts(
            body.actor_id, body.survivor_id, body.merged_id,
            conflict_resolution=body.conflict_resolution,
        )
        return {
            "survivor_id": survivor.contact_id,
            "merged_id": body.merged_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/contacts/{contact_id}/role")
def change_role(contact_id: str, body: RoleChangeIn) -> dict:
    """D4 role escalation to VIP requires admin + hg_ticket_id."""
    try:
        c = _service().change_role(
            body.actor_id, contact_id, body.new_role,
            actor_role=body.actor_role,
            hg_ticket_id=body.hg_ticket_id,
        )
        return {"contact_id": c.contact_id, "role": c.role}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/contacts/{contact_id}/audit")
def list_audit(contact_id: str) -> dict:
    items = _service()._store.list_audit_for_target(contact_id)
    return {
        "items": [
            {"entry_id": e.entry_id, "actor_id": e.actor_id,
             "action": e.action, "payload_redacted": e.payload_redacted,
             "created_at": e.created_at}
            for e in items
        ],
        "total": len(items),
    }


__all__ = ["router"]

