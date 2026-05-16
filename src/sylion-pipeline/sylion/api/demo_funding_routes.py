"""REST routes for Funding Pipeline Tracker demo (W14 E11, D4 external_action)."""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("sylion.api.demo_funding")
router = APIRouter(prefix="/api/v1/reference/funding", tags=["reference:funding"])

_svc: Any = None


def _service():
    global _svc
    if _svc is None:
        from sylion.demo.funding_pipeline_tracker import (
            FundingService, FundingStore,
        )
        db_path = os.environ.get("SYLION_DEMO_FUNDING_DB", "sylion_aeis.db")
        _svc = FundingService(store=FundingStore(db_path=db_path))
    return _svc


class CreateAppIn(BaseModel):
    submitter_id: str
    grant_program: str
    title: str
    deadline_ts: float
    requested_amount_eur: float = 0.0
    project_id: str = ""


class AttachIn(BaseModel):
    filename: str
    sha256: str
    size_bytes: int
    mime_type: str = "application/pdf"


class SignatureIn(BaseModel):
    signer_id: str
    signer_role: str
    cert_serial: str
    expires_at: float


class SubmitIn(BaseModel):
    hg_ticket_id: str


@router.get("/health")
def health() -> dict:
    try:
        return {"ok": True, **_service()._store.health()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/applications", status_code=201)
def create_application(body: CreateAppIn) -> dict:
    try:
        app = _service().create_application(
            body.submitter_id, body.grant_program, body.title,
            body.deadline_ts, body.requested_amount_eur, body.project_id,
        )
        return {"application_id": app.application_id, "status": app.status,
                "deadline_ts": app.deadline_ts}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/applications/{application_id}")
def get_application(application_id: str) -> dict:
    app = _service()._store.get_app(application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="not found")
    attachments = _service()._store.list_attachments(application_id)
    sigs = _service()._store.list_signatures(application_id)
    return {
        "application_id": app.application_id,
        "grant_program": app.grant_program, "title": app.title,
        "submitter_id": app.submitter_id, "deadline_ts": app.deadline_ts,
        "requested_amount_eur": app.requested_amount_eur,
        "status": app.status, "submitted_at": app.submitted_at,
        "attachments": [
            {"attachment_id": a.attachment_id, "filename": a.filename,
             "size_bytes": a.size_bytes} for a in attachments
        ],
        "signatures": [
            {"signature_id": s.signature_id, "signer_role": s.signer_role,
             "expires_at": s.expires_at} for s in sigs
        ],
    }


@router.post("/applications/{application_id}/attachments", status_code=201)
def attach_file(application_id: str, body: AttachIn) -> dict:
    try:
        a = _service().attach_file(
            application_id, body.filename, body.sha256,
            body.size_bytes, body.mime_type,
        )
        return {"attachment_id": a.attachment_id,
                "size_bytes": a.size_bytes}
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))


@router.post("/applications/{application_id}/signatures", status_code=201)
def add_signature(application_id: str, body: SignatureIn) -> dict:
    try:
        s = _service().add_signature(
            application_id, body.signer_id, body.signer_role,
            body.cert_serial, body.expires_at,
        )
        return {"signature_id": s.signature_id,
                "expires_at": s.expires_at}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/applications/{application_id}/submit")
def submit_external(application_id: str, body: SubmitIn) -> dict:
    """D4 external_action â€” REQUIRES hg_ticket_id."""
    try:
        return _service().submit_to_external_portal(
            application_id, body.hg_ticket_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


__all__ = ["router"]

