"""InspectorService — business logic with W14-compliant guards.

Implements the 3 domain-specific human errors from the manifest:
  - lost_connectivity_during_approval -> sync attempt with retry+revision check
  - gps_spoofing_attempt -> GPS sanity (range + accuracy + drift)
  - photo_evidence_corruption_unverified -> sha256 mandatory before submit

Plus core W14 protections via the ontology testing layer:
  - revision check on update (multi-tab confusion guard)
  - status transition validation (premature_action guard)
"""
from __future__ import annotations

import logging
import time
from typing import Any

from sylion.demo.mobile_field_inspector.models import (
    FieldInspection, GpsCoord, InspectionStatus, OfflineQueueEntry,
    PhotoEvidence, SignatureEvidence,
)
from sylion.demo.mobile_field_inspector.store import InspectorStore

log = logging.getLogger("sylion.demo.mobile_field_inspector.service")


# Status transition graph
_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"ready_to_sync", "rejected"},
    "ready_to_sync": {"syncing", "draft", "rejected"},
    "syncing": {"synced", "failed"},
    "failed": {"ready_to_sync", "rejected"},
    "synced": set(),  # terminal
    "rejected": set(),  # terminal
}


# Max GPS drift (m) accepted between consecutive captures (anti-spoofing)
GPS_MAX_DRIFT_M = 5000.0


class InspectorService:
    """Business logic for field inspections."""

    def __init__(
        self, store: InspectorStore,
        event_bus: Any | None = None,
    ) -> None:
        self._store = store
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Inspection workflow
    # ------------------------------------------------------------------

    def create_inspection(
        self, inspector_id: str, project_id: str = "",
        location_label: str = "", notes: str = "",
        gps: GpsCoord | None = None,
    ) -> FieldInspection:
        insp = FieldInspection(
            inspector_id=inspector_id,
            project_id=project_id,
            location_label=location_label,
            notes=notes,
            gps=gps,
        )
        self._store.create_inspection(insp)
        self._emit("demo.mobile.inspection.created", {
            "inspection_id": insp.inspection_id,
            "inspector_id": inspector_id,
        })
        return insp

    def transition(
        self, inspection_id: str, new_status: str,
        expected_revision: int,
    ) -> FieldInspection:
        """Transition status with revision check + valid-transition guard."""
        if new_status not in InspectionStatus._value2member_map_:
            raise ValueError(f"unknown status: {new_status}")
        insp = self._store.get_inspection(inspection_id)
        if insp is None:
            raise ValueError(f"inspection not found: {inspection_id}")
        allowed = _TRANSITIONS.get(insp.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"invalid transition {insp.status} -> {new_status} "
                f"(allowed: {sorted(allowed)})"
            )
        # Premature: cannot mark ready_to_sync without photo + signature
        if new_status == "ready_to_sync":
            photos = self._store.list_photos(inspection_id)
            sigs = self._store.list_signatures(inspection_id)
            if not photos:
                raise ValueError("cannot mark ready_to_sync: no photo")
            if not sigs:
                raise ValueError("cannot mark ready_to_sync: no signature")
            if not insp.gps:
                raise ValueError("cannot mark ready_to_sync: no GPS")

        synced = time.time() if new_status == "synced" else None
        updated = self._store.update_inspection(
            inspection_id, expected_revision=expected_revision,
            status=new_status, synced_at=synced,
        )
        self._emit("demo.mobile.inspection.transitioned", {
            "inspection_id": inspection_id,
            "to": new_status,
        })
        return updated

    # ------------------------------------------------------------------
    # Photo evidence (anti-corruption guard)
    # ------------------------------------------------------------------

    def attach_photo(
        self, inspection_id: str, sha256: str, size_bytes: int,
        mime_type: str = "image/jpeg",
    ) -> PhotoEvidence:
        # Verify inspection exists + not yet synced
        insp = self._store.get_inspection(inspection_id)
        if insp is None:
            raise ValueError(f"inspection not found: {inspection_id}")
        if insp.status in ("synced", "rejected"):
            raise ValueError(
                f"cannot attach photo to {insp.status} inspection"
            )
        # PhotoEvidence.__post_init__ enforces sha256 + size bounds
        photo = PhotoEvidence(
            inspection_id=inspection_id,
            sha256=sha256, size_bytes=size_bytes, mime_type=mime_type,
        )
        self._store.add_photo(photo)
        self._emit("demo.mobile.photo.attached", {
            "photo_id": photo.photo_id,
            "inspection_id": inspection_id,
        })
        return photo

    # ------------------------------------------------------------------
    # Signature
    # ------------------------------------------------------------------

    def attach_signature(
        self, inspection_id: str, signer_id: str,
        signature_data_b64: str,
    ) -> SignatureEvidence:
        insp = self._store.get_inspection(inspection_id)
        if insp is None:
            raise ValueError(f"inspection not found: {inspection_id}")
        if insp.status in ("synced", "rejected"):
            raise ValueError(
                f"cannot attach signature to {insp.status} inspection"
            )
        sig = SignatureEvidence(
            inspection_id=inspection_id,
            signer_id=signer_id,
            signature_data_b64=signature_data_b64,
        )
        self._store.add_signature(sig)
        self._emit("demo.mobile.signature.attached", {
            "signature_id": sig.signature_id,
            "inspection_id": inspection_id,
        })
        return sig

    # ------------------------------------------------------------------
    # GPS spoofing detection (compare against previous capture)
    # ------------------------------------------------------------------

    def update_gps(
        self, inspection_id: str, gps: GpsCoord,
        previous_gps: GpsCoord | None = None,
    ) -> dict:
        """Update GPS, flag suspicious drift.

        Returns {'accepted': bool, 'flagged': bool, 'reason': str|None}.
        """
        insp = self._store.get_inspection(inspection_id)
        if insp is None:
            raise ValueError(f"inspection not found: {inspection_id}")

        flagged = False
        reason = None
        if previous_gps is not None:
            drift = self._haversine_m(previous_gps, gps)
            if drift > GPS_MAX_DRIFT_M:
                flagged = True
                reason = (
                    f"gps_drift_excessive: {drift:.0f}m > "
                    f"{GPS_MAX_DRIFT_M:.0f}m limit"
                )
        if gps.accuracy_m > 200:
            flagged = True
            reason = reason or f"gps_accuracy_low: {gps.accuracy_m:.0f}m"

        if flagged:
            self._emit("demo.mobile.gps.flagged", {
                "inspection_id": inspection_id,
                "reason": reason,
            })
            return {"accepted": False, "flagged": True, "reason": reason}

        # Accept: persist as JSON in inspection
        import json
        from dataclasses import asdict
        with self._store._lock:
            self._store._conn.execute(
                "UPDATE field_inspections SET gps_json = ?, "
                "revision = revision + 1, updated_at = ? "
                "WHERE inspection_id = ?",
                (json.dumps(asdict(gps)), time.time(), inspection_id),
            )
            self._store._conn.commit()
        self._emit("demo.mobile.gps.updated", {
            "inspection_id": inspection_id,
        })
        return {"accepted": True, "flagged": False, "reason": None}

    # ------------------------------------------------------------------
    # Sync (offline queue + retry)
    # ------------------------------------------------------------------

    def queue_for_sync(
        self, inspection_id: str, expected_revision: int,
    ) -> OfflineQueueEntry:
        """Mark inspection ready_to_sync and add to offline queue."""
        self.transition(inspection_id, "ready_to_sync", expected_revision)
        entry = OfflineQueueEntry(inspection_id=inspection_id)
        self._store.enqueue(entry)
        self._emit("demo.mobile.queued", {
            "inspection_id": inspection_id,
            "queue_id": entry.queue_id,
        })
        return entry

    def sync_one(self, queue_id: str) -> dict:
        """Process one queue entry. Returns {'success': bool, 'reason': str|None}."""
        # Find entry
        entries = [e for e in self._store.list_queue() if e.queue_id == queue_id]
        if not entries:
            return {"success": False, "reason": "queue_id not found"}
        entry = entries[0]
        insp = self._store.get_inspection(entry.inspection_id)
        if insp is None:
            self._store.mark_queue_attempt(
                queue_id, success=False, error="inspection vanished",
            )
            return {"success": False, "reason": "inspection vanished"}
        if insp.status not in ("ready_to_sync", "failed"):
            self._store.mark_queue_attempt(
                queue_id, success=False,
                error=f"unexpected status {insp.status}",
            )
            return {"success": False, "reason": f"unexpected status {insp.status}"}

        # Verify all evidence present (anti corruption)
        photos = self._store.list_photos(entry.inspection_id)
        sigs = self._store.list_signatures(entry.inspection_id)
        if not photos or not sigs or not insp.gps:
            self._store.mark_queue_attempt(
                queue_id, success=False, error="missing evidence",
            )
            return {"success": False, "reason": "missing evidence"}

        # Transition to syncing -> synced
        self.transition(insp.inspection_id, "syncing", insp.revision)
        self.transition(insp.inspection_id, "synced", insp.revision + 1)
        self._store.mark_queue_attempt(queue_id, success=True)
        self._emit("demo.mobile.synced", {
            "inspection_id": insp.inspection_id,
        })
        return {"success": True, "reason": None}

    def sync_all(self) -> dict:
        results: list[dict] = []
        for entry in self._store.list_queue():
            r = self.sync_one(entry.queue_id)
            results.append({"queue_id": entry.queue_id, **r})
        ok = sum(1 for r in results if r["success"])
        return {"total": len(results), "success": ok, "results": results}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine_m(a: GpsCoord, b: GpsCoord) -> float:
        from math import atan2, cos, radians, sin, sqrt
        R = 6_371_000.0
        lat1, lat2 = radians(a.lat), radians(b.lat)
        dlat = lat2 - lat1
        dlon = radians(b.lon - a.lon)
        h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return float(2 * R * atan2(sqrt(h), sqrt(1 - h)))

    def _emit(self, topic: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        try:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="demo.mobile_field_inspector",
            ))
        except Exception as e:  # pragma: no cover
            log.debug("event emit failed: %s", e)


__all__ = ["InspectorService", "GPS_MAX_DRIFT_M"]
