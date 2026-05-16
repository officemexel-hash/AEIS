"""Adversarial tests — domain-specific human errors from manifest."""
from __future__ import annotations

import pytest

from sylion.demo.mobile_field_inspector import (
    GpsCoord, InspectorService, InspectorStore,
)


@pytest.fixture
def svc():
    return InspectorService(store=InspectorStore())


# -------- gps_spoofing_attempt (manifest error class wrong_context, D4) --------

def test_adv_gps_jump_within_range_flagged(svc):
    insp = svc.create_inspection(inspector_id="op_1")
    # Captured at Warsaw (52.23, 21.01)
    prev = GpsCoord(lat=52.23, lon=21.01)
    # Spoofed jump to Wrocław (~340km) — within Poland but way past 5km drift limit
    spoofed = GpsCoord(lat=51.10, lon=17.04)
    result = svc.update_gps(insp.inspection_id, spoofed, previous_gps=prev)
    assert result["flagged"] is True
    assert "drift" in result["reason"]


def test_adv_gps_outside_poland_rejected_at_construction():
    """GpsCoord constructor itself rejects out-of-range — defense in depth."""
    with pytest.raises(ValueError):
        GpsCoord(lat=40.7, lon=-74.0)  # New York: way out


# -------- photo_evidence_corruption_unverified (premature_action, D3) --------

def test_adv_photo_corrupt_truncated_rejected(svc):
    insp = svc.create_inspection(inspector_id="op_1")
    # Truncated photo (< 1 KB) — likely corrupted
    with pytest.raises(ValueError, match="below minimum"):
        svc.attach_photo(insp.inspection_id, sha256="b" * 64, size_bytes=500)


def test_adv_photo_no_sha_rejected(svc):
    insp = svc.create_inspection(inspector_id="op_1")
    with pytest.raises(ValueError, match="sha256"):
        svc.attach_photo(insp.inspection_id, sha256="", size_bytes=2048)


def test_adv_sync_without_signature_rejected(svc):
    """Sync must have signature — unsigned evidence isn't trusted."""
    insp = svc.create_inspection(inspector_id="op_1")
    svc.attach_photo(insp.inspection_id, "a" * 64, 2048)
    svc.update_gps(insp.inspection_id, GpsCoord(lat=52.0, lon=21.0))
    with pytest.raises(ValueError, match="no signature"):
        svc.transition(insp.inspection_id, "ready_to_sync",
                       expected_revision=svc._store.get_inspection(insp.inspection_id).revision)


# -------- lost_connectivity_during_approval (stale_data_action, D3) --------

def test_adv_multitab_revision_conflict(svc):
    """Two tabs editing same inspection — second one gets 409 by stale rev."""
    insp = svc.create_inspection(inspector_id="op_1")
    iid = insp.inspection_id
    svc.attach_photo(iid, "a" * 64, 2048)
    svc.attach_signature(iid, "op_1", "x" * 100)
    svc.update_gps(iid, GpsCoord(lat=52.0, lon=21.0))
    stale_rev = svc._store.get_inspection(iid).revision
    # Tab A: ready_to_sync (advances revision)
    svc.transition(iid, "ready_to_sync", expected_revision=stale_rev)
    # Tab B: tries reject with stale rev — should 409
    with pytest.raises(RuntimeError, match="revision conflict"):
        svc.transition(iid, "rejected", expected_revision=stale_rev)


def test_adv_sync_after_inspection_deleted_handled(svc):
    """If inspection vanishes between queue and sync — graceful failure."""
    insp = svc.create_inspection(inspector_id="op_1")
    iid = insp.inspection_id
    svc.attach_photo(iid, "a" * 64, 2048)
    svc.attach_signature(iid, "op_1", "x" * 100)
    svc.update_gps(iid, GpsCoord(lat=52.0, lon=21.0))
    rev = svc._store.get_inspection(iid).revision
    entry = svc.queue_for_sync(iid, expected_revision=rev)

    # Delete inspection from store directly (simulating vanish)
    svc._store._conn.execute(
        "DELETE FROM field_inspections WHERE inspection_id = ?", (iid,),
    )
    svc._store._conn.commit()

    result = svc.sync_one(entry.queue_id)
    assert result["success"] is False
    assert "vanished" in result["reason"]


# -------- offline queue retry --------

def test_adv_failed_sync_marked_with_error(svc):
    """A failed sync increments attempt_count and stores error."""
    insp = svc.create_inspection(inspector_id="op_1")
    iid = insp.inspection_id
    svc.attach_photo(iid, "a" * 64, 2048)
    svc.attach_signature(iid, "op_1", "x" * 100)
    svc.update_gps(iid, GpsCoord(lat=52.0, lon=21.0))
    rev = svc._store.get_inspection(iid).revision
    entry = svc.queue_for_sync(iid, expected_revision=rev)

    # Force failure: change inspection status to draft (not ready_to_sync)
    svc._store._conn.execute(
        "UPDATE field_inspections SET status='draft' WHERE inspection_id = ?",
        (iid,),
    )
    svc._store._conn.commit()

    result = svc.sync_one(entry.queue_id)
    assert result["success"] is False
    queue = svc._store.list_queue()
    assert len(queue) == 1
    assert queue[0].attempt_count == 1
    assert queue[0].last_error
