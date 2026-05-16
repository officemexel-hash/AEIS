"""Mobile Field Inspector — service workflow + W14 guards."""
from __future__ import annotations

import pytest

from sylion.demo.mobile_field_inspector import (
    GpsCoord, InspectorService, InspectorStore,
)


@pytest.fixture
def store():
    return InspectorStore()


@pytest.fixture
def svc(store):
    return InspectorService(store=store)


def _make(svc) -> str:
    insp = svc.create_inspection(inspector_id="op_1", project_id="proj_x")
    return insp.inspection_id


# -------- create + get --------

def test_create_inspection_persists(svc, store):
    insp = svc.create_inspection(
        inspector_id="op_1", project_id="proj_x",
        location_label="Site A", notes="initial",
    )
    fetched = store.get_inspection(insp.inspection_id)
    assert fetched is not None
    assert fetched.inspector_id == "op_1"
    assert fetched.location_label == "Site A"


# -------- transition lifecycle --------

def test_transition_draft_to_ready_requires_evidence(svc):
    iid = _make(svc)
    with pytest.raises(ValueError, match="no photo"):
        svc.transition(iid, "ready_to_sync", expected_revision=0)


def test_transition_full_lifecycle_to_synced(svc, store):
    iid = _make(svc)
    # Add photo + signature + gps
    svc.attach_photo(iid, sha256="a" * 64, size_bytes=2048)
    svc.attach_signature(iid, signer_id="op_1",
                          signature_data_b64="x" * 100)
    svc.update_gps(iid, GpsCoord(lat=52.0, lon=21.0, accuracy_m=10.0))
    insp = store.get_inspection(iid)

    svc.transition(iid, "ready_to_sync", expected_revision=insp.revision)
    insp = store.get_inspection(iid)
    assert insp.status == "ready_to_sync"

    svc.transition(iid, "syncing", expected_revision=insp.revision)
    insp = store.get_inspection(iid)
    assert insp.status == "syncing"

    svc.transition(iid, "synced", expected_revision=insp.revision)
    insp = store.get_inspection(iid)
    assert insp.status == "synced"
    assert insp.synced_at is not None


def test_transition_invalid_target_rejected(svc):
    iid = _make(svc)
    with pytest.raises(ValueError, match="invalid transition"):
        svc.transition(iid, "syncing", expected_revision=0)  # draft -> syncing not allowed


def test_transition_revision_conflict_409(svc):
    iid = _make(svc)
    svc.attach_photo(iid, sha256="a" * 64, size_bytes=2048)
    svc.attach_signature(iid, "op_1", "x" * 100)
    svc.update_gps(iid, GpsCoord(lat=52.0, lon=21.0))
    # Wrong expected_revision
    with pytest.raises(RuntimeError, match="revision conflict"):
        svc.transition(iid, "ready_to_sync", expected_revision=999)


def test_synced_is_terminal(svc, store):
    iid = _make(svc)
    svc.attach_photo(iid, "a" * 64, 2048)
    svc.attach_signature(iid, "op_1", "x" * 100)
    svc.update_gps(iid, GpsCoord(lat=52.0, lon=21.0))
    rev = store.get_inspection(iid).revision
    svc.transition(iid, "ready_to_sync", expected_revision=rev)
    rev = store.get_inspection(iid).revision
    svc.transition(iid, "syncing", expected_revision=rev)
    rev = store.get_inspection(iid).revision
    svc.transition(iid, "synced", expected_revision=rev)
    rev = store.get_inspection(iid).revision
    with pytest.raises(ValueError, match="invalid transition"):
        svc.transition(iid, "draft", expected_revision=rev)


# -------- attach_photo guards --------

def test_attach_photo_after_synced_rejected(svc, store):
    iid = _make(svc)
    svc.attach_photo(iid, "a" * 64, 2048)
    svc.attach_signature(iid, "op_1", "x" * 100)
    svc.update_gps(iid, GpsCoord(lat=52.0, lon=21.0))
    rev = store.get_inspection(iid).revision
    svc.transition(iid, "ready_to_sync", expected_revision=rev)
    rev = store.get_inspection(iid).revision
    svc.transition(iid, "syncing", expected_revision=rev)
    rev = store.get_inspection(iid).revision
    svc.transition(iid, "synced", expected_revision=rev)
    with pytest.raises(ValueError, match="cannot attach"):
        svc.attach_photo(iid, "b" * 64, 2048)


# -------- GPS spoofing detection --------

def test_gps_drift_excessive_flagged(svc):
    iid = _make(svc)
    prev = GpsCoord(lat=52.0, lon=21.0)
    new = GpsCoord(lat=52.5, lon=21.5)  # ~60km away — way > 5km limit
    result = svc.update_gps(iid, new, previous_gps=prev)
    assert result["accepted"] is False
    assert result["flagged"] is True
    assert "drift" in result["reason"]


def test_gps_low_accuracy_flagged(svc):
    iid = _make(svc)
    new = GpsCoord(lat=52.0, lon=21.0, accuracy_m=500.0)  # > 200m limit
    result = svc.update_gps(iid, new)
    assert result["flagged"] is True
    assert "accuracy" in result["reason"]


def test_gps_normal_drift_accepted(svc):
    iid = _make(svc)
    prev = GpsCoord(lat=52.0, lon=21.0)
    new = GpsCoord(lat=52.001, lon=21.001)  # ~150m drift
    result = svc.update_gps(iid, new, previous_gps=prev)
    assert result["accepted"] is True
    assert result["flagged"] is False


# -------- Sync (offline queue) --------

def test_queue_for_sync_creates_entry(svc, store):
    iid = _make(svc)
    svc.attach_photo(iid, "a" * 64, 2048)
    svc.attach_signature(iid, "op_1", "x" * 100)
    svc.update_gps(iid, GpsCoord(lat=52.0, lon=21.0))
    rev = store.get_inspection(iid).revision
    entry = svc.queue_for_sync(iid, expected_revision=rev)
    assert entry.queue_id.startswith("queue_")
    assert len(store.list_queue()) == 1


def test_sync_one_succeeds_with_full_evidence(svc, store):
    iid = _make(svc)
    svc.attach_photo(iid, "a" * 64, 2048)
    svc.attach_signature(iid, "op_1", "x" * 100)
    svc.update_gps(iid, GpsCoord(lat=52.0, lon=21.0))
    rev = store.get_inspection(iid).revision
    entry = svc.queue_for_sync(iid, expected_revision=rev)

    result = svc.sync_one(entry.queue_id)
    assert result["success"] is True
    insp = store.get_inspection(iid)
    assert insp.status == "synced"
    # Queue empty after success
    assert len(store.list_queue()) == 0


def test_sync_all_processes_multiple(svc, store):
    ids = []
    for _ in range(3):
        iid = _make(svc)
        svc.attach_photo(iid, "a" * 64, 2048)
        svc.attach_signature(iid, "op_1", "x" * 100)
        svc.update_gps(iid, GpsCoord(lat=52.0, lon=21.0))
        rev = store.get_inspection(iid).revision
        svc.queue_for_sync(iid, expected_revision=rev)
        ids.append(iid)

    result = svc.sync_all()
    assert result["total"] == 3
    assert result["success"] == 3
    assert all(store.get_inspection(i).status == "synced" for i in ids)
