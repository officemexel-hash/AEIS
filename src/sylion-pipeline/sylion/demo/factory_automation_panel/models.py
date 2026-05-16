"""Factory automation domain models — D5 safety-critical."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

UPLOAD_STATUS = ("pending_backup", "pending_estop", "pending_dryrun",
                 "ready", "uploading", "uploaded", "failed", "rolled_back")


@dataclass
class Cabinet:
    cabinet_id: str = field(
        default_factory=lambda: f"cab_{uuid.uuid4().hex[:12]}"
    )
    plant_id: str = ""
    name: str = ""
    plc_serial: str = ""
    firmware_version: str = ""
    last_backup_at: float | None = None
    last_estop_test_at: float | None = None
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.plant_id:
            raise ValueError("plant_id required")
        if not self.plc_serial or len(self.plc_serial) < 4:
            raise ValueError("plc_serial required (min 4 chars)")
        if not self.name:
            raise ValueError("name required")


@dataclass
class IOMapping:
    """IO map asserts which cabinet a program targets."""
    mapping_id: str = field(
        default_factory=lambda: f"iomap_{uuid.uuid4().hex[:12]}"
    )
    cabinet_id: str = ""
    program_id: str = ""
    expected_plc_serial: str = ""  # MUST match cabinet.plc_serial pre-upload
    io_signature: str = ""         # sha256 of IO declarations
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.expected_plc_serial:
            raise ValueError("expected_plc_serial required")
        if len(self.io_signature) != 64:
            raise ValueError("io_signature must be 64-char sha256 hex")


@dataclass
class EmergencyStop:
    """E-stop test record. Must precede upload."""
    test_id: str = field(default_factory=lambda: f"estop_{uuid.uuid4().hex[:12]}")
    cabinet_id: str = ""
    operator_id: str = ""
    passed: bool = False
    response_time_ms: float = 0.0
    tested_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.operator_id:
            raise ValueError("operator_id required")
        # Industrial standard: e-stop must respond within 500ms
        if self.passed and self.response_time_ms > 500:
            raise ValueError(
                f"e-stop response too slow: {self.response_time_ms}ms > 500ms"
            )


@dataclass
class ProgramUpload:
    upload_id: str = field(
        default_factory=lambda: f"upload_{uuid.uuid4().hex[:12]}"
    )
    cabinet_id: str = ""
    mapping_id: str = ""
    program_sha256: str = ""
    status: str = "pending_backup"
    operator_id: str = ""
    backup_id: str | None = None
    estop_test_id: str | None = None
    dryrun_passed: bool | None = None
    council_session_id: str | None = None  # required for safety override
    created_at: float = field(default_factory=time.time)
    uploaded_at: float | None = None

    def __post_init__(self) -> None:
        if self.status not in UPLOAD_STATUS:
            raise ValueError(f"invalid status: {self.status}")
        if not self.operator_id:
            raise ValueError("operator_id required")
        if len(self.program_sha256) != 64:
            raise ValueError("program_sha256 must be 64-char hex")


@dataclass
class SafetyInterlock:
    """Safety interlock state. Override requires Council session."""
    interlock_id: str = field(
        default_factory=lambda: f"lock_{uuid.uuid4().hex[:12]}"
    )
    cabinet_id: str = ""
    name: str = ""
    active: bool = True
    overridden: bool = False
    override_council_session: str | None = None
    override_reason: str = ""

    def __post_init__(self) -> None:
        if self.overridden and not self.override_council_session:
            raise ValueError(
                "interlock override REQUIRES Council session_id (D5 rule)"
            )


__all__ = [
    "Cabinet", "EmergencyStop", "IOMapping",
    "ProgramUpload", "SafetyInterlock", "UPLOAD_STATUS",
]
