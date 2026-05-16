"""Domain models for Mobile Field Inspector."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class InspectionStatus(str, Enum):
    DRAFT = "draft"
    READY_TO_SYNC = "ready_to_sync"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"
    REJECTED = "rejected"


# Realistic geographic ranges (Poland-centric for this demo)
MIN_LAT, MAX_LAT = 49.0, 55.0
MIN_LON, MAX_LON = 14.0, 24.5

# Photo size limits (sec 7.3 evidence)
MIN_PHOTO_BYTES = 1024            # 1 KB minimum (avoid empty/corrupt)
MAX_PHOTO_BYTES = 25 * 1024 * 1024  # 25 MB hard cap


@dataclass
class GpsCoord:
    """GPS coordinate captured at inspection time."""
    lat: float = 0.0
    lon: float = 0.0
    accuracy_m: float = 50.0
    captured_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not (MIN_LAT <= self.lat <= MAX_LAT):
            raise ValueError(f"lat out of expected range: {self.lat}")
        if not (MIN_LON <= self.lon <= MAX_LON):
            raise ValueError(f"lon out of expected range: {self.lon}")
        if self.accuracy_m < 0 or self.accuracy_m > 1000:
            raise ValueError(f"accuracy_m must be in [0, 1000]: {self.accuracy_m}")


@dataclass
class PhotoEvidence:
    """Photo attached to inspection. Hash + size enforced for evidence."""
    photo_id: str = field(default_factory=lambda: f"photo_{uuid.uuid4().hex[:12]}")
    inspection_id: str = ""
    sha256: str = ""
    size_bytes: int = 0
    mime_type: str = "image/jpeg"
    captured_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.sha256 or len(self.sha256) != 64:
            raise ValueError("sha256 must be 64-char hex digest")
        if self.size_bytes < MIN_PHOTO_BYTES:
            raise ValueError(
                f"photo size {self.size_bytes} below minimum {MIN_PHOTO_BYTES}"
            )
        if self.size_bytes > MAX_PHOTO_BYTES:
            raise ValueError(
                f"photo size {self.size_bytes} exceeds maximum {MAX_PHOTO_BYTES}"
            )


@dataclass
class SignatureEvidence:
    """Operator signature (drawn or biometric)."""
    signature_id: str = field(
        default_factory=lambda: f"sig_{uuid.uuid4().hex[:12]}"
    )
    inspection_id: str = ""
    signer_id: str = ""
    signature_data_b64: str = ""
    signed_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.signer_id:
            raise ValueError("signer_id required")
        if not self.signature_data_b64 or len(self.signature_data_b64) < 32:
            raise ValueError("signature_data_b64 too short (min 32 chars)")


@dataclass
class FieldInspection:
    """Top-level inspection record."""
    inspection_id: str = field(
        default_factory=lambda: f"insp_{uuid.uuid4().hex[:12]}"
    )
    project_id: str = ""           # which AEIS project this belongs to
    inspector_id: str = ""         # operator id
    location_label: str = ""       # human-readable
    notes: str = ""
    gps: GpsCoord | None = None
    photos: list[str] = field(default_factory=list)       # photo_ids
    signatures: list[str] = field(default_factory=list)   # signature_ids
    status: str = InspectionStatus.DRAFT.value
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    synced_at: float | None = None
    revision: int = 0  # for multi-tab/multi-device conflict detection

    def __post_init__(self) -> None:
        if not self.inspector_id:
            raise ValueError("inspector_id required")
        if self.status not in InspectionStatus._value2member_map_:
            raise ValueError(f"invalid status: {self.status}")


@dataclass
class OfflineQueueEntry:
    """Inspection queued for sync when network returns."""
    queue_id: str = field(default_factory=lambda: f"queue_{uuid.uuid4().hex[:12]}")
    inspection_id: str = ""
    queued_at: float = field(default_factory=time.time)
    attempt_count: int = 0
    last_attempt_at: float | None = None
    last_error: str | None = None


__all__ = [
    "FieldInspection", "GpsCoord", "InspectionStatus",
    "OfflineQueueEntry", "PhotoEvidence", "SignatureEvidence",
    "MIN_LAT", "MAX_LAT", "MIN_LON", "MAX_LON",
    "MIN_PHOTO_BYTES", "MAX_PHOTO_BYTES",
]
