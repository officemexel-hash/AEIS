"""Funding domain models — deadline + signature + attachment guards."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

APP_STATUS = ("draft", "pending_signature", "ready_to_submit",
              "submitted", "accepted", "rejected", "withdrawn")

# Hard limits per grant portal standards
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024     # 20 MB per file
MAX_TOTAL_ATTACHMENT_BYTES = 100 * 1024 * 1024  # 100 MB per application

# Signature freshness (signed within 30 days)
SIGNATURE_MAX_AGE_S = 30 * 24 * 3600


@dataclass
class GrantApplication:
    application_id: str = field(
        default_factory=lambda: f"grant_{uuid.uuid4().hex[:12]}"
    )
    project_id: str = ""
    grant_program: str = ""
    title: str = ""
    submitter_id: str = ""
    deadline_ts: float = 0.0     # epoch seconds, hard cutoff
    requested_amount_eur: float = 0.0
    status: str = "draft"
    created_at: float = field(default_factory=time.time)
    submitted_at: float | None = None

    def __post_init__(self) -> None:
        if not self.grant_program:
            raise ValueError("grant_program required")
        if not self.submitter_id:
            raise ValueError("submitter_id required")
        if self.requested_amount_eur < 0:
            raise ValueError("requested_amount_eur must be non-negative")
        if self.status not in APP_STATUS:
            raise ValueError(f"invalid status: {self.status}")
        if self.deadline_ts <= 0:
            raise ValueError("deadline_ts required (> 0)")


@dataclass
class Attachment:
    attachment_id: str = field(
        default_factory=lambda: f"att_{uuid.uuid4().hex[:12]}"
    )
    application_id: str = ""
    filename: str = ""
    sha256: str = ""
    size_bytes: int = 0
    mime_type: str = "application/pdf"
    uploaded_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.filename:
            raise ValueError("filename required")
        if len(self.sha256) != 64:
            raise ValueError("sha256 must be 64-char hex")
        if self.size_bytes <= 0:
            raise ValueError("size_bytes must be positive")
        if self.size_bytes > MAX_ATTACHMENT_BYTES:
            raise ValueError(
                f"attachment too large: {self.size_bytes} > "
                f"{MAX_ATTACHMENT_BYTES} (no silent truncation!)"
            )


@dataclass
class GrantSignature:
    signature_id: str = field(
        default_factory=lambda: f"gsig_{uuid.uuid4().hex[:12]}"
    )
    application_id: str = ""
    signer_id: str = ""
    signer_role: str = ""        # CEO, Legal, Finance
    cert_serial: str = ""        # certificate serial number
    signed_at: float = field(default_factory=time.time)
    expires_at: float = 0.0      # certificate expiry

    def __post_init__(self) -> None:
        if not self.signer_id or not self.signer_role:
            raise ValueError("signer_id and signer_role required")
        if not self.cert_serial:
            raise ValueError("cert_serial required (signature must use cert)")
        if self.expires_at <= self.signed_at:
            raise ValueError(
                "expires_at must be after signed_at (no expired-at-signing)"
            )


@dataclass
class SubmissionAttempt:
    attempt_id: str = field(
        default_factory=lambda: f"subatt_{uuid.uuid4().hex[:12]}"
    )
    application_id: str = ""
    attempted_at: float = field(default_factory=time.time)
    success: bool = False
    error: str = ""
    portal_response_code: int = 0


__all__ = [
    "GrantApplication", "Attachment", "GrantSignature",
    "SubmissionAttempt", "APP_STATUS",
    "MAX_ATTACHMENT_BYTES", "MAX_TOTAL_ATTACHMENT_BYTES",
    "SIGNATURE_MAX_AGE_S",
]
