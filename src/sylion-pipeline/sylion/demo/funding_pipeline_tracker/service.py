"""FundingService — deadline + signature + attachment guards (D4)."""
from __future__ import annotations

import logging
import time
from typing import Any

from sylion.demo.funding_pipeline_tracker.models import (
    Attachment, GrantApplication, GrantSignature, SubmissionAttempt,
    MAX_TOTAL_ATTACHMENT_BYTES, SIGNATURE_MAX_AGE_S,
)
from sylion.demo.funding_pipeline_tracker.store import FundingStore

log = logging.getLogger("sylion.demo.funding_pipeline_tracker.service")


class FundingService:
    def __init__(self, store: FundingStore, event_bus: Any = None) -> None:
        self._store = store
        self._event_bus = event_bus

    def create_application(
        self, submitter_id: str, grant_program: str, title: str,
        deadline_ts: float, requested_amount_eur: float = 0.0,
        project_id: str = "",
    ) -> GrantApplication:
        if deadline_ts <= time.time():
            raise ValueError("deadline must be in the future")
        app = GrantApplication(
            project_id=project_id, grant_program=grant_program,
            title=title, submitter_id=submitter_id,
            deadline_ts=deadline_ts,
            requested_amount_eur=requested_amount_eur,
        )
        return self._store.create_app(app)

    def attach_file(
        self, application_id: str, filename: str,
        sha256: str, size_bytes: int,
        mime_type: str = "application/pdf",
    ) -> Attachment:
        app = self._store.get_app(application_id)
        if app is None:
            raise ValueError(f"application not found: {application_id}")
        if app.status not in ("draft", "pending_signature"):
            raise ValueError(
                f"cannot attach to {app.status} application"
            )
        # Per-file cap enforced in Attachment.__post_init__.
        # Total cap enforced here.
        current_total = self._store.total_attachment_bytes(application_id)
        if current_total + size_bytes > MAX_TOTAL_ATTACHMENT_BYTES:
            raise ValueError(
                f"TOTAL ATTACHMENT LIMIT EXCEEDED: {current_total + size_bytes} > "
                f"{MAX_TOTAL_ATTACHMENT_BYTES} (no silent truncation)"
            )
        a = Attachment(
            application_id=application_id, filename=filename,
            sha256=sha256, size_bytes=size_bytes, mime_type=mime_type,
        )
        return self._store.add_attachment(a)

    def add_signature(
        self, application_id: str, signer_id: str, signer_role: str,
        cert_serial: str, expires_at: float,
    ) -> GrantSignature:
        app = self._store.get_app(application_id)
        if app is None:
            raise ValueError(f"application not found: {application_id}")
        if expires_at <= time.time():
            raise ValueError("certificate already expired (cannot sign)")
        s = GrantSignature(
            application_id=application_id, signer_id=signer_id,
            signer_role=signer_role, cert_serial=cert_serial,
            expires_at=expires_at,
        )
        self._store.add_signature(s)
        return s

    def submit_to_external_portal(
        self, application_id: str, hg_ticket_id: str,
    ) -> dict:
        """D4: external_action gate — REQUIRES HG ticket.

        Hard checks:
          1. HG ticket present (D4 governance)
          2. Deadline not passed (clock check)
          3. At least one valid (non-expired) signature
          4. Total attachments within limit
        """
        if not hg_ticket_id:
            raise PermissionError(
                "External submit REQUIRES hg_ticket_id (D4 external_action gate)"
            )
        app = self._store.get_app(application_id)
        if app is None:
            raise ValueError(f"application not found: {application_id}")

        # Deadline check (clock drift guard)
        now = time.time()
        if now >= app.deadline_ts:
            self._record_attempt(application_id, success=False,
                                  error="DEADLINE_PASSED", code=400)
            raise ValueError(
                f"DEADLINE PASSED: now={now}, deadline={app.deadline_ts}"
            )

        # Signature freshness
        signatures = self._store.list_signatures(application_id)
        if not signatures:
            raise ValueError("at least one signature required")
        valid_sigs = [
            s for s in signatures
            if s.expires_at > now
            and (now - s.signed_at) < SIGNATURE_MAX_AGE_S
        ]
        if not valid_sigs:
            self._record_attempt(application_id, success=False,
                                  error="SIGNATURE_EXPIRED", code=400)
            raise ValueError(
                "EXPIRED SIGNATURE: all signatures expired or > 30 days old"
            )

        # Attachment total
        total = self._store.total_attachment_bytes(application_id)
        if total > MAX_TOTAL_ATTACHMENT_BYTES:
            self._record_attempt(application_id, success=False,
                                  error="ATTACHMENT_LIMIT", code=413)
            raise ValueError("attachment total exceeds limit")

        # Submit
        self._store.update_app_status(
            application_id, status="submitted", submitted_at=now,
        )
        self._record_attempt(application_id, success=True,
                              error="", code=200)
        return {
            "application_id": application_id,
            "status": "submitted",
            "submitted_at": now,
        }

    def _record_attempt(
        self, application_id: str, success: bool,
        error: str, code: int,
    ) -> None:
        a = SubmissionAttempt(
            application_id=application_id, success=success,
            error=error, portal_response_code=code,
        )
        self._store.add_attempt(a)


__all__ = ["FundingService"]
