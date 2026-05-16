"""Mobile Field Inspector — model validators."""
from __future__ import annotations

import pytest

from sylion.demo.mobile_field_inspector import (
    FieldInspection, GpsCoord, InspectionStatus,
    PhotoEvidence, SignatureEvidence,
)
from sylion.demo.mobile_field_inspector.models import (
    MAX_PHOTO_BYTES, MIN_LAT, MIN_LON, MIN_PHOTO_BYTES,
)


# -------- GpsCoord --------

def test_gps_valid():
    g = GpsCoord(lat=52.0, lon=21.0, accuracy_m=10.0)
    assert g.lat == 52.0


def test_gps_lat_out_of_range_high():
    with pytest.raises(ValueError, match="lat"):
        GpsCoord(lat=60.0, lon=20.0)


def test_gps_lat_out_of_range_low():
    with pytest.raises(ValueError, match="lat"):
        GpsCoord(lat=40.0, lon=20.0)


def test_gps_lon_out_of_range():
    with pytest.raises(ValueError, match="lon"):
        GpsCoord(lat=52.0, lon=30.0)


def test_gps_accuracy_negative():
    with pytest.raises(ValueError, match="accuracy"):
        GpsCoord(lat=52.0, lon=20.0, accuracy_m=-1.0)


def test_gps_accuracy_huge():
    with pytest.raises(ValueError, match="accuracy"):
        GpsCoord(lat=52.0, lon=20.0, accuracy_m=2000.0)


# -------- PhotoEvidence --------

def test_photo_valid():
    p = PhotoEvidence(
        inspection_id="insp_x",
        sha256="a" * 64,
        size_bytes=2048,
    )
    assert p.size_bytes == 2048


def test_photo_short_sha_rejected():
    with pytest.raises(ValueError, match="sha256"):
        PhotoEvidence(inspection_id="insp_x", sha256="abc", size_bytes=2048)


def test_photo_too_small_rejected():
    with pytest.raises(ValueError, match="below minimum"):
        PhotoEvidence(
            inspection_id="x", sha256="a" * 64,
            size_bytes=MIN_PHOTO_BYTES - 1,
        )


def test_photo_too_large_rejected():
    with pytest.raises(ValueError, match="exceeds maximum"):
        PhotoEvidence(
            inspection_id="x", sha256="a" * 64,
            size_bytes=MAX_PHOTO_BYTES + 1,
        )


# -------- SignatureEvidence --------

def test_signature_valid():
    s = SignatureEvidence(
        inspection_id="insp_x",
        signer_id="op_1",
        signature_data_b64="x" * 100,
    )
    assert s.signer_id == "op_1"


def test_signature_no_signer_rejected():
    with pytest.raises(ValueError, match="signer_id"):
        SignatureEvidence(
            inspection_id="x", signer_id="",
            signature_data_b64="y" * 50,
        )


def test_signature_short_data_rejected():
    with pytest.raises(ValueError, match="signature_data_b64 too short"):
        SignatureEvidence(
            inspection_id="x", signer_id="op", signature_data_b64="abc",
        )


# -------- FieldInspection --------

def test_inspection_valid():
    i = FieldInspection(inspector_id="op_1", project_id="proj_x")
    assert i.status == "draft"
    assert i.revision == 0


def test_inspection_no_inspector_rejected():
    with pytest.raises(ValueError, match="inspector_id"):
        FieldInspection(inspector_id="")


def test_inspection_invalid_status_rejected():
    with pytest.raises(ValueError, match="invalid status"):
        FieldInspection(inspector_id="op_1", status="bogus")


def test_inspection_status_enum_complete():
    expected = {
        "draft", "ready_to_sync", "syncing",
        "synced", "failed", "rejected",
    }
    actual = {s.value for s in InspectionStatus}
    assert actual == expected
