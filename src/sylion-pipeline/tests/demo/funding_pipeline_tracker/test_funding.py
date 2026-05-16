"""Funding pipeline tracker — deadline + signature + attachment guards."""
from __future__ import annotations

import time
import pytest

from sylion.demo.funding_pipeline_tracker import (
    Attachment, FundingService, FundingStore,
    GrantApplication, GrantSignature,
)
from sylion.demo.funding_pipeline_tracker.models import (
    MAX_ATTACHMENT_BYTES, MAX_TOTAL_ATTACHMENT_BYTES,
)


@pytest.fixture
def store():
    return FundingStore()


@pytest.fixture
def svc(store):
    return FundingService(store=store)


# -------- Models --------

def test_application_requires_future_deadline_dataclass():
    """Constructor allows past, but service guards future."""
    GrantApplication(
        grant_program="HORIZON", submitter_id="op_1",
        deadline_ts=time.time() + 86400,
    )


def test_application_invalid_status():
    with pytest.raises(ValueError, match="status"):
        GrantApplication(
            grant_program="HORIZON", submitter_id="op_1",
            deadline_ts=time.time() + 86400, status="invalid",
        )


def test_attachment_per_file_cap_hard():
    with pytest.raises(ValueError, match="too large"):
        Attachment(
            filename="big.pdf", sha256="a"*64,
            size_bytes=MAX_ATTACHMENT_BYTES + 1,
        )


def test_signature_expires_after_signing():
    now = time.time()
    with pytest.raises(ValueError, match="expires_at must be after"):
        GrantSignature(
            application_id="x", signer_id="s", signer_role="CEO",
            cert_serial="C001", signed_at=now, expires_at=now - 1000,
        )


# -------- Service: create + attach --------

def test_create_application_succeeds(svc):
    app = svc.create_application(
        submitter_id="op_1", grant_program="HORIZON-EU",
        title="AI for healthcare",
        deadline_ts=time.time() + 30 * 86400,
        requested_amount_eur=500_000.0,
    )
    assert app.application_id.startswith("grant_")


def test_create_app_with_past_deadline_rejected(svc):
    with pytest.raises(ValueError, match="future"):
        svc.create_application(
            submitter_id="op_1", grant_program="X", title="late",
            deadline_ts=time.time() - 100,
        )


def test_attach_file_succeeds(svc):
    app = svc.create_application(
        submitter_id="op_1", grant_program="X", title="t",
        deadline_ts=time.time() + 86400,
    )
    a = svc.attach_file(
        app.application_id, filename="proposal.pdf",
        sha256="b"*64, size_bytes=1024 * 1024,
    )
    assert a.attachment_id.startswith("att_")


def test_adv_attach_file_oversized_rejected(svc):
    app = svc.create_application(
        submitter_id="op_1", grant_program="X", title="t",
        deadline_ts=time.time() + 86400,
    )
    with pytest.raises(ValueError, match="too large"):
        svc.attach_file(
            app.application_id, filename="huge.pdf",
            sha256="b"*64, size_bytes=MAX_ATTACHMENT_BYTES + 1,
        )


def test_adv_attach_file_total_limit_exceeded(svc):
    app = svc.create_application(
        submitter_id="op_1", grant_program="X", title="t",
        deadline_ts=time.time() + 86400,
    )
    # Add 5 files of 19 MB each = 95 MB; 6th file 19 MB pushes over 100 MB
    for i in range(5):
        svc.attach_file(
            app.application_id, filename=f"f{i}.pdf",
            sha256=f"{i:064x}", size_bytes=19 * 1024 * 1024,
        )
    with pytest.raises(ValueError, match="TOTAL ATTACHMENT LIMIT"):
        svc.attach_file(
            app.application_id, filename="last.pdf",
            sha256="f"*64, size_bytes=19 * 1024 * 1024,
        )


# -------- Submit to external portal (D4) --------

def _setup_ready(svc, deadline_offset: float = 86400):
    """Create app with attachment + signature ready to submit."""
    app = svc.create_application(
        submitter_id="op_1", grant_program="HORIZON",
        title="t", deadline_ts=time.time() + deadline_offset,
    )
    svc.attach_file(app.application_id, "proposal.pdf",
                    "a"*64, 1024 * 1024)
    svc.add_signature(
        app.application_id, signer_id="ceo_1", signer_role="CEO",
        cert_serial="C001", expires_at=time.time() + 365 * 86400,
    )
    return app


def test_submit_happy_path(svc):
    app = _setup_ready(svc)
    result = svc.submit_to_external_portal(
        app.application_id, hg_ticket_id="hg_d4_external_001",
    )
    assert result["status"] == "submitted"


def test_adv_submit_without_hg_blocked(svc):
    app = _setup_ready(svc)
    with pytest.raises(PermissionError, match="hg_ticket_id"):
        svc.submit_to_external_portal(app.application_id, hg_ticket_id="")


def test_adv_submit_after_deadline_blocked(svc):
    app = _setup_ready(svc, deadline_offset=1.0)
    time.sleep(1.5)  # past deadline
    with pytest.raises(ValueError, match="DEADLINE PASSED"):
        svc.submit_to_external_portal(
            app.application_id, hg_ticket_id="hg_1",
        )


def test_adv_submit_with_expired_signature_blocked(svc):
    app = svc.create_application(
        submitter_id="op_1", grant_program="X", title="t",
        deadline_ts=time.time() + 86400,
    )
    svc.attach_file(app.application_id, "p.pdf", "a"*64, 2048)
    # Sign with cert that expires in the past — will fail at signature creation
    # Use trick: sign with cert that expires very soon (1 sec)
    svc.add_signature(
        app.application_id, signer_id="ceo", signer_role="CEO",
        cert_serial="C002", expires_at=time.time() + 1.0,
    )
    time.sleep(1.5)  # cert expired
    with pytest.raises(ValueError, match="EXPIRED SIGNATURE"):
        svc.submit_to_external_portal(
            app.application_id, hg_ticket_id="hg_1",
        )


def test_adv_submit_without_signature_blocked(svc):
    app = svc.create_application(
        submitter_id="op_1", grant_program="X", title="t",
        deadline_ts=time.time() + 86400,
    )
    svc.attach_file(app.application_id, "p.pdf", "a"*64, 2048)
    with pytest.raises(ValueError, match="signature required"):
        svc.submit_to_external_portal(
            app.application_id, hg_ticket_id="hg_1",
        )


def test_failed_submit_records_attempt(svc, store):
    app = _setup_ready(svc)
    # Force a failure by removing signatures (already created — manipulate DB)
    svc._store._conn.execute(
        "DELETE FROM funding_signatures WHERE application_id = ?",
        (app.application_id,),
    )
    svc._store._conn.commit()
    with pytest.raises(ValueError):
        svc.submit_to_external_portal(app.application_id,
                                       hg_ticket_id="hg_1")


def test_store_health(store):
    h = store.health()
    assert h["ok"] is True
