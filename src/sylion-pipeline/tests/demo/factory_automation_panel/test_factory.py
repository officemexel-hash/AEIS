"""Factory Automation Panel — D5 safety adversarial."""
from __future__ import annotations

import time

import pytest

from sylion.demo.factory_automation_panel import (
    FactoryService, FactoryStore, IOMapping, ProgramUpload, SafetyInterlock,
)


@pytest.fixture
def store():
    return FactoryStore()


@pytest.fixture
def svc(store):
    return FactoryService(store=store)


# -------- Models --------

def test_cabinet_requires_serial():
    from sylion.demo.factory_automation_panel import Cabinet
    with pytest.raises(ValueError, match="plc_serial"):
        Cabinet(plant_id="p1", name="n", plc_serial="abc")


def test_iomap_requires_64char_signature():
    with pytest.raises(ValueError, match="io_signature"):
        IOMapping(cabinet_id="c", program_id="p",
                  expected_plc_serial="serial",
                  io_signature="too_short")


def test_estop_response_time_capped():
    """Industrial standard: e-stop must respond < 500ms."""
    from sylion.demo.factory_automation_panel import EmergencyStop
    with pytest.raises(ValueError, match="too slow"):
        EmergencyStop(
            cabinet_id="c", operator_id="op",
            passed=True, response_time_ms=750.0,
        )


def test_upload_status_validated():
    with pytest.raises(ValueError, match="invalid status"):
        ProgramUpload(cabinet_id="c", mapping_id="m",
                      program_sha256="a"*64, status="bogus",
                      operator_id="op")


def test_interlock_override_requires_council():
    """D5 rule: override without Council = constructor rejected."""
    with pytest.raises(ValueError, match="Council"):
        SafetyInterlock(
            cabinet_id="c", name="door", active=True,
            overridden=True,
            override_council_session=None,
        )


# -------- Service: full safety chain --------

def _setup_cabinet(svc, with_backup=True, with_estop=True):
    c = svc.register_cabinet(plant_id="plant1", name="Line A",
                              plc_serial="PLC-12345")
    if with_backup:
        svc.take_backup(c.cabinet_id)
    if with_estop:
        svc.test_estop(c.cabinet_id, "op_1", response_time_ms=120.0)
    return c


def test_attempt_upload_happy_path(svc):
    c = _setup_cabinet(svc)
    m = svc.define_iomap(
        cabinet_id=c.cabinet_id, program_id="prog1",
        expected_plc_serial="PLC-12345",
        io_signature="b"*64,
    )
    u = svc.attempt_upload(
        cabinet_id=c.cabinet_id, mapping_id=m.mapping_id,
        program_sha256="a"*64, operator_id="op_1",
        dryrun_passed=True,
    )
    assert u.status == "ready"


# -------- D5 adversarial guards --------

def test_adv_wrong_cabinet_upload_blocked(svc):
    c1 = _setup_cabinet(svc)
    c2 = _setup_cabinet(svc)
    # IO map for c1
    m = svc.define_iomap(
        cabinet_id=c1.cabinet_id, program_id="p1",
        expected_plc_serial=c1.plc_serial, io_signature="b"*64,
    )
    # Try to upload to c2 with c1 mapping
    with pytest.raises(ValueError, match="WRONG CABINET"):
        svc.attempt_upload(
            cabinet_id=c2.cabinet_id, mapping_id=m.mapping_id,
            program_sha256="a"*64, operator_id="op_1",
            dryrun_passed=True,
        )


def test_adv_plc_serial_mismatch_blocked(svc):
    c = _setup_cabinet(svc)
    m = svc.define_iomap(
        cabinet_id=c.cabinet_id, program_id="p1",
        expected_plc_serial="DIFFERENT-SERIAL",
        io_signature="b"*64,
    )
    with pytest.raises(ValueError, match="PLC SERIAL MISMATCH"):
        svc.attempt_upload(
            cabinet_id=c.cabinet_id, mapping_id=m.mapping_id,
            program_sha256="a"*64, operator_id="op_1",
            dryrun_passed=True,
        )


def test_adv_no_backup_blocked(svc):
    c = _setup_cabinet(svc, with_backup=False)
    m = svc.define_iomap(
        cabinet_id=c.cabinet_id, program_id="p1",
        expected_plc_serial=c.plc_serial, io_signature="b"*64,
    )
    with pytest.raises(ValueError, match="BACKUP MISSING"):
        svc.attempt_upload(
            cabinet_id=c.cabinet_id, mapping_id=m.mapping_id,
            program_sha256="a"*64, operator_id="op_1",
            dryrun_passed=True,
        )


def test_adv_no_estop_test_blocked(svc):
    c = _setup_cabinet(svc, with_estop=False)
    m = svc.define_iomap(
        cabinet_id=c.cabinet_id, program_id="p1",
        expected_plc_serial=c.plc_serial, io_signature="b"*64,
    )
    with pytest.raises(ValueError, match="EMERGENCY STOP NOT TESTED"):
        svc.attempt_upload(
            cabinet_id=c.cabinet_id, mapping_id=m.mapping_id,
            program_sha256="a"*64, operator_id="op_1",
            dryrun_passed=True,
        )


def test_adv_dryrun_required(svc):
    c = _setup_cabinet(svc)
    m = svc.define_iomap(
        cabinet_id=c.cabinet_id, program_id="p1",
        expected_plc_serial=c.plc_serial, io_signature="b"*64,
    )
    with pytest.raises(ValueError, match="DRY-RUN MUST PASS"):
        svc.attempt_upload(
            cabinet_id=c.cabinet_id, mapping_id=m.mapping_id,
            program_sha256="a"*64, operator_id="op_1",
            dryrun_passed=False,
        )


def test_adv_safety_interlock_override_requires_council(svc):
    c = _setup_cabinet(svc)
    with pytest.raises(ValueError, match="REQUIRES council"):
        svc.override_interlock(
            cabinet_id=c.cabinet_id, name="door_lock",
            council_session_id="", reason="urgency",
        )


def test_safety_interlock_override_with_council_succeeds(svc):
    c = _setup_cabinet(svc)
    interlock = svc.override_interlock(
        cabinet_id=c.cabinet_id, name="door_lock",
        council_session_id="cs_d5_emergency_001",
        reason="approved emergency maintenance",
    )
    assert interlock.overridden
    assert interlock.override_council_session == "cs_d5_emergency_001"


def test_execute_upload_marks_uploaded(svc):
    c = _setup_cabinet(svc)
    m = svc.define_iomap(
        cabinet_id=c.cabinet_id, program_id="p1",
        expected_plc_serial=c.plc_serial, io_signature="b"*64,
    )
    u = svc.attempt_upload(
        cabinet_id=c.cabinet_id, mapping_id=m.mapping_id,
        program_sha256="a"*64, operator_id="op_1",
        dryrun_passed=True,
    )
    result = svc.execute_upload(u.upload_id)
    assert result["status"] == "uploaded"
