"""REST routes for Mobile Field Inspector demo (W14 E11)."""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("sylion.api.demo_mobile_inspector")

router = APIRouter(
    prefix="/api/v1/reference/mobile-inspector",
    tags=["reference:mobile-inspector"],
)

_store_singleton: Any = None
_service_singleton: Any = None


def _service():
    global _store_singleton, _service_singleton
    if _service_singleton is None:
        from sylion.demo.mobile_field_inspector import InspectorService, InspectorStore
        db_path = os.environ.get("SYLION_DEMO_MOBILE_DB", "sylion_aeis.db")
        _store_singleton = InspectorStore(db_path=db_path)
        _service_singleton = InspectorService(store=_store_singleton)
    return _service_singleton


# -------- Request models --------

class GpsIn(BaseModel):
    lat: float
    lon: float
    accuracy_m: float = 50.0


class CreateInspectionIn(BaseModel):
    inspector_id: str
    project_id: str = ""
    location_label: str = ""
    notes: str = ""
    gps: GpsIn | None = None


class TransitionIn(BaseModel):
    new_status: str
    expected_revision: int


class PhotoIn(BaseModel):
    sha256: str
    size_bytes: int
    mime_type: str = "image/jpeg"


class SignatureIn(BaseModel):
    signer_id: str
    signature_data_b64: str


class GpsUpdateIn(BaseModel):
    new_gps: GpsIn
    previous_gps: GpsIn | None = None


# -------- Endpoints --------

@router.get("/health")
def health() -> dict:
    try:
        from sylion.demo.mobile_field_inspector import InspectorStore
        store = _service()._store  # type: ignore[union-attr]
        return {"ok": True, **store.health()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/inspections", status_code=201)
def create_inspection(body: CreateInspectionIn) -> dict:
    from sylion.demo.mobile_field_inspector import GpsCoord
    try:
        gps = (
            GpsCoord(lat=body.gps.lat, lon=body.gps.lon,
                     accuracy_m=body.gps.accuracy_m)
            if body.gps else None
        )
        insp = _service().create_inspection(
            inspector_id=body.inspector_id,
            project_id=body.project_id,
            location_label=body.location_label,
            notes=body.notes,
            gps=gps,
        )
        return {
            "inspection_id": insp.inspection_id,
            "status": insp.status,
            "revision": insp.revision,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/inspections")
def list_inspections(
    inspector_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> dict:
    items = _service()._store.list_inspections(
        inspector_id=inspector_id, status=status, limit=limit,
    )
    return {
        "items": [
            {
                "inspection_id": i.inspection_id,
                "inspector_id": i.inspector_id,
                "project_id": i.project_id,
                "location_label": i.location_label,
                "status": i.status,
                "revision": i.revision,
                "created_at": i.created_at,
                "synced_at": i.synced_at,
                "has_gps": i.gps is not None,
            } for i in items
        ],
        "total": len(items),
    }


@router.get("/inspections/{inspection_id}")
def get_inspection(inspection_id: str) -> dict:
    insp = _service()._store.get_inspection(inspection_id)
    if insp is None:
        raise HTTPException(status_code=404, detail="inspection not found")
    photos = _service()._store.list_photos(inspection_id)
    sigs = _service()._store.list_signatures(inspection_id)
    return {
        "inspection_id": insp.inspection_id,
        "inspector_id": insp.inspector_id,
        "project_id": insp.project_id,
        "location_label": insp.location_label,
        "notes": insp.notes,
        "status": insp.status,
        "revision": insp.revision,
        "gps": (
            {"lat": insp.gps.lat, "lon": insp.gps.lon,
             "accuracy_m": insp.gps.accuracy_m} if insp.gps else None
        ),
        "photos": [{"photo_id": p.photo_id, "sha256": p.sha256,
                     "size_bytes": p.size_bytes} for p in photos],
        "signatures": [{"signature_id": s.signature_id,
                         "signer_id": s.signer_id} for s in sigs],
        "created_at": insp.created_at,
        "updated_at": insp.updated_at,
        "synced_at": insp.synced_at,
    }


@router.post("/inspections/{inspection_id}/transition")
def transition(inspection_id: str, body: TransitionIn) -> dict:
    try:
        updated = _service().transition(
            inspection_id, body.new_status, body.expected_revision,
        )
        return {
            "inspection_id": updated.inspection_id,
            "status": updated.status,
            "revision": updated.revision,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # revision conflict -> 409 (multi-tab confusion guard)
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/inspections/{inspection_id}/photo", status_code=201)
def attach_photo(inspection_id: str, body: PhotoIn) -> dict:
    try:
        photo = _service().attach_photo(
            inspection_id, body.sha256, body.size_bytes, body.mime_type,
        )
        return {
            "photo_id": photo.photo_id,
            "sha256": photo.sha256,
            "size_bytes": photo.size_bytes,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/inspections/{inspection_id}/signature", status_code=201)
def attach_signature(inspection_id: str, body: SignatureIn) -> dict:
    try:
        sig = _service().attach_signature(
            inspection_id, body.signer_id, body.signature_data_b64,
        )
        return {"signature_id": sig.signature_id, "signer_id": sig.signer_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/inspections/{inspection_id}/gps")
def update_gps(inspection_id: str, body: GpsUpdateIn) -> dict:
    from sylion.demo.mobile_field_inspector import GpsCoord
    try:
        new_gps = GpsCoord(
            lat=body.new_gps.lat, lon=body.new_gps.lon,
            accuracy_m=body.new_gps.accuracy_m,
        )
        prev_gps = (
            GpsCoord(lat=body.previous_gps.lat, lon=body.previous_gps.lon,
                     accuracy_m=body.previous_gps.accuracy_m)
            if body.previous_gps else None
        )
        return _service().update_gps(inspection_id, new_gps, prev_gps)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/inspections/{inspection_id}/queue", status_code=201)
def queue_for_sync(
    inspection_id: str, expected_revision: int = 0,
) -> dict:
    try:
        entry = _service().queue_for_sync(inspection_id, expected_revision)
        return {"queue_id": entry.queue_id, "queued_at": entry.queued_at}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/queue")
def list_queue() -> dict:
    items = _service()._store.list_queue()
    return {
        "items": [
            {
                "queue_id": q.queue_id,
                "inspection_id": q.inspection_id,
                "queued_at": q.queued_at,
                "attempt_count": q.attempt_count,
                "last_error": q.last_error,
            } for q in items
        ],
        "total": len(items),
    }


@router.post("/queue/sync")
def sync_all() -> dict:
    return _service().sync_all()


__all__ = ["router"]

