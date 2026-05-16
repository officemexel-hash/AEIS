"""FactoryService — D5 safety guards for industrial automation."""
from __future__ import annotations

import time
from typing import Any

from sylion.demo.factory_automation_panel.models import (
    Cabinet, EmergencyStop, IOMapping, ProgramUpload, SafetyInterlock,
)
from sylion.demo.factory_automation_panel.store import FactoryStore


# Backup must be < 24h old to upload (industrial backup freshness)
BACKUP_MAX_AGE_S = 24 * 3600

# E-stop test must be < 7 days old (industrial standard)
ESTOP_MAX_AGE_S = 7 * 24 * 3600


class FactoryService:
    def __init__(self, store: FactoryStore, event_bus: Any = None) -> None:
        self._store = store
        self._event_bus = event_bus

    def register_cabinet(
        self, plant_id: str, name: str, plc_serial: str,
        firmware_version: str = "",
    ) -> Cabinet:
        c = Cabinet(plant_id=plant_id, name=name, plc_serial=plc_serial,
                    firmware_version=firmware_version)
        return self._store.create_cabinet(c)

    def take_backup(self, cabinet_id: str) -> str:
        if self._store.get_cabinet(cabinet_id) is None:
            raise ValueError(f"cabinet not found: {cabinet_id}")
        backup_id = f"bak_{int(time.time())}_{cabinet_id[-6:]}"
        self._store.update_cabinet_backup(cabinet_id, time.time())
        return backup_id

    def test_estop(
        self, cabinet_id: str, operator_id: str,
        response_time_ms: float, passed: bool = True,
    ) -> EmergencyStop:
        if self._store.get_cabinet(cabinet_id) is None:
            raise ValueError(f"cabinet not found: {cabinet_id}")
        e = EmergencyStop(
            cabinet_id=cabinet_id, operator_id=operator_id,
            passed=passed, response_time_ms=response_time_ms,
        )
        return self._store.add_estop(e)

    def define_iomap(
        self, cabinet_id: str, program_id: str,
        expected_plc_serial: str, io_signature: str,
    ) -> IOMapping:
        m = IOMapping(
            cabinet_id=cabinet_id, program_id=program_id,
            expected_plc_serial=expected_plc_serial,
            io_signature=io_signature,
        )
        return self._store.add_iomap(m)

    def attempt_upload(
        self, cabinet_id: str, mapping_id: str,
        program_sha256: str, operator_id: str,
        dryrun_passed: bool = False,
    ) -> ProgramUpload:
        """Attempt upload — D5 safety chain mandatory."""
        cabinet = self._store.get_cabinet(cabinet_id)
        if cabinet is None:
            raise ValueError(f"cabinet not found: {cabinet_id}")

        mapping = self._store.get_iomap(mapping_id)
        if mapping is None:
            raise ValueError(f"io_mapping not found: {mapping_id}")

        # Hard guard 1: cabinet_id MUST match mapping (anti wrong-cabinet upload)
        if mapping.cabinet_id != cabinet_id:
            raise ValueError(
                f"WRONG CABINET: mapping targets {mapping.cabinet_id}, "
                f"upload to {cabinet_id}"
            )
        # Hard guard 2: PLC serial must match
        if mapping.expected_plc_serial != cabinet.plc_serial:
            raise ValueError(
                f"PLC SERIAL MISMATCH: mapping expects "
                f"{mapping.expected_plc_serial}, cabinet has {cabinet.plc_serial}"
            )

        # Hard guard 3: backup freshness (no upload without recent backup)
        if cabinet.last_backup_at is None:
            raise ValueError("BACKUP MISSING: take_backup() required before upload")
        backup_age = time.time() - cabinet.last_backup_at
        if backup_age > BACKUP_MAX_AGE_S:
            raise ValueError(
                f"BACKUP STALE: {backup_age/3600:.1f}h old, "
                f"max {BACKUP_MAX_AGE_S/3600:.0f}h"
            )

        # Hard guard 4: e-stop test mandatory + recent
        if cabinet.last_estop_test_at is None:
            raise ValueError(
                "EMERGENCY STOP NOT TESTED: test_estop() required"
            )
        estop_age = time.time() - cabinet.last_estop_test_at
        if estop_age > ESTOP_MAX_AGE_S:
            raise ValueError(
                f"E-STOP TEST STALE: {estop_age/3600:.1f}h old"
            )

        # Hard guard 5: dryrun must pass
        if not dryrun_passed:
            raise ValueError("DRY-RUN MUST PASS before staged upload")

        # All guards passed
        u = ProgramUpload(
            cabinet_id=cabinet_id, mapping_id=mapping_id,
            program_sha256=program_sha256, status="ready",
            operator_id=operator_id,
            backup_id=f"bak_{int(cabinet.last_backup_at)}_{cabinet_id[-6:]}",
            dryrun_passed=True,
        )
        return self._store.add_upload(u)

    def execute_upload(self, upload_id: str) -> dict:
        """Stage upload: ready -> uploading -> uploaded."""
        self._store.update_upload_status(upload_id, "uploading")
        # Simulated PLC programming time
        self._store.update_upload_status(
            upload_id, "uploaded", uploaded_at=time.time(),
        )
        return {"upload_id": upload_id, "status": "uploaded"}

    def override_interlock(
        self, cabinet_id: str, name: str,
        council_session_id: str, reason: str,
    ) -> SafetyInterlock:
        """D5 override — REQUIRES Council session (no exceptions)."""
        if not council_session_id:
            raise ValueError(
                "Safety interlock override REQUIRES council_session_id"
            )
        i = SafetyInterlock(
            cabinet_id=cabinet_id, name=name, active=True,
            overridden=True,
            override_council_session=council_session_id,
            override_reason=reason,
        )
        return self._store.add_interlock(i)


__all__ = ["FactoryService", "BACKUP_MAX_AGE_S", "ESTOP_MAX_AGE_S"]
