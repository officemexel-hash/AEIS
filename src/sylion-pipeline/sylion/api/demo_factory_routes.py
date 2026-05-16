"""REST routes for Factory Automation Panel demo (W14 E11, D5)."""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("sylion.api.demo_factory")
router = APIRouter(prefix="/api/v1/reference/factory", tags=["reference:factory"])

_svc: Any = None


def _service():
    global _svc
    if _svc is None:
        from sylion.demo.factory_automation_panel import (
            FactoryService, FactoryStore,
        )
        db_path = os.environ.get("SYLION_DEMO_FACTORY_DB", "sylion_aeis.db")
        _svc = FactoryService(store=FactoryStore(db_path=db_path))
    return _svc


class RegisterCabinetIn(BaseModel):
    plant_id: str
    name: str
    plc_serial: str
    firmware_version: str = ""


class EstopIn(BaseModel):
    operator_id: str
    response_time_ms: float
    passed: bool = True


class IOMapIn(BaseModel):
    program_id: str
    expected_plc_serial: str
    io_signature: str


class UploadIn(BaseModel):
    mapping_id: str
    program_sha256: str
    operator_id: str
    dryrun_passed: bool = False


class InterlockIn(BaseModel):
    name: str
    council_session_id: str
    reason: str


@router.get("/health")
def health() -> dict:
    try:
        return {"ok": True, **_service()._store.health()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/cabinets", status_code=201)
def register_cabinet(body: RegisterCabinetIn) -> dict:
    try:
        c = _service().register_cabinet(
            body.plant_id, body.name, body.plc_serial,
            body.firmware_version,
        )
        return {"cabinet_id": c.cabinet_id, "plc_serial": c.plc_serial}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cabinets/{cabinet_id}")
def get_cabinet(cabinet_id: str) -> dict:
    c = _service()._store.get_cabinet(cabinet_id)
    if c is None:
        raise HTTPException(status_code=404, detail="cabinet not found")
    return {
        "cabinet_id": c.cabinet_id, "plant_id": c.plant_id, "name": c.name,
        "plc_serial": c.plc_serial, "firmware_version": c.firmware_version,
        "last_backup_at": c.last_backup_at,
        "last_estop_test_at": c.last_estop_test_at,
    }


@router.post("/cabinets/{cabinet_id}/backup", status_code=201)
def take_backup(cabinet_id: str) -> dict:
    try:
        bid = _service().take_backup(cabinet_id)
        return {"backup_id": bid, "cabinet_id": cabinet_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cabinets/{cabinet_id}/estop", status_code=201)
def test_estop(cabinet_id: str, body: EstopIn) -> dict:
    try:
        e = _service().test_estop(
            cabinet_id, body.operator_id,
            body.response_time_ms, body.passed,
        )
        return {"test_id": e.test_id, "passed": e.passed}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cabinets/{cabinet_id}/iomap", status_code=201)
def define_iomap(cabinet_id: str, body: IOMapIn) -> dict:
    try:
        m = _service().define_iomap(
            cabinet_id, body.program_id,
            body.expected_plc_serial, body.io_signature,
        )
        return {"mapping_id": m.mapping_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cabinets/{cabinet_id}/upload", status_code=201)
def attempt_upload(cabinet_id: str, body: UploadIn) -> dict:
    """D5 safety chain â€” all 5 hard checks enforced server-side."""
    try:
        u = _service().attempt_upload(
            cabinet_id, body.mapping_id, body.program_sha256,
            body.operator_id, body.dryrun_passed,
        )
        return {"upload_id": u.upload_id, "status": u.status}
    except ValueError as e:
        # 422 = unprocessable (failed safety guards)
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/uploads/{upload_id}/execute")
def execute_upload(upload_id: str) -> dict:
    return _service().execute_upload(upload_id)


@router.post("/cabinets/{cabinet_id}/interlock-override", status_code=201)
def override_interlock(cabinet_id: str, body: InterlockIn) -> dict:
    """D5: requires council_session_id."""
    try:
        i = _service().override_interlock(
            cabinet_id, body.name,
            body.council_session_id, body.reason,
        )
        return {
            "interlock_id": i.interlock_id, "overridden": i.overridden,
            "council_session_id": i.override_council_session,
        }
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


__all__ = ["router"]

