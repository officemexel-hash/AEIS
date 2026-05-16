"""
Tests for sylion.funding_autopilot.governance_bridge (K2).

Validates that funding actions correctly submit governance tickets
with appropriate decision classes, gate types, and priorities.
"""

from __future__ import annotations

import pytest

from sylion.funding_autopilot.governance_bridge import (
    approve_for_test,
    check_approved,
    check_pending,
    submit_application_creation_ticket,
    submit_call_creation_ticket,
    submit_idea_conversion_ticket,
    submit_programme_creation_ticket,
    submit_scan_ticket,
    submit_submission_ticket,
)
from sylion.governance.tickets import fetch_by_id, fetch_pending
from sylion.governance.ticket import reset_ticket_store


@pytest.fixture(autouse=True)
def _fresh_ticket_store():
    """Reset the governance ticket store before each test."""
    reset_ticket_store()
    yield


class TestSubmitScanTicket:
    def test_creates_ticket(self):
        tid = submit_scan_ticket("job_abc123", force_refresh=False, since_days=30, calls_found=12)
        assert len(tid) == 32  # uuid hex
        t = fetch_by_id(tid)
        assert t is not None
        assert t.origin == "funding"
        assert t.decision_class == "D2"
        assert t.gate_type == "non_blocking"
        assert t.priority == "P2"
        assert "scan triggered" in t.title.lower()
        assert t.payload["action"] == "scan_trigger"
        assert t.payload["calls_found"] == 12
        assert t.requested_by == "funding_autopilot"

    def test_force_refresh_raises_priority_and_gate(self):
        tid = submit_scan_ticket("job_def456", force_refresh=True, since_days=7, calls_found=0)
        t = fetch_by_id(tid)
        assert t.gate_type == "blocking"
        assert t.priority == "P1"


class TestSubmitCallCreationTicket:
    def test_creates_ticket(self):
        tid = submit_call_creation_ticket({
            "title": "Horizon Europe 2027",
            "code": "HE-2027-CL4",
            "country": "EU",
        })
        t = fetch_by_id(tid)
        assert t.decision_class == "D2"
        assert t.gate_type == "blocking"
        assert t.priority == "P2"
        assert "Horizon Europe 2027" in t.title
        assert t.payload["action"] == "call_creation"


class TestSubmitProgrammeCreationTicket:
    def test_creates_ticket(self):
        tid = submit_programme_creation_ticket({
            "name": "NCBR Smart Growth",
            "country": "PL",
        })
        t = fetch_by_id(tid)
        assert t.decision_class == "D2"
        assert t.gate_type == "blocking"
        assert "NCBR Smart Growth" in t.title
        assert t.payload["action"] == "programme_creation"


class TestSubmitIdeaConversionTicket:
    def test_creates_d3_ticket(self):
        tid = submit_idea_conversion_ticket(
            idea_id="idea_abc123",
            project_id="proj_def456",
            call_id="call_ghi789",
        )
        t = fetch_by_id(tid)
        assert t.decision_class == "D3"
        assert t.gate_type == "blocking"
        assert t.priority == "P2"
        assert t.project_id == "proj_def456"
        assert t.payload["action"] == "idea_conversion"
        assert t.payload["idea_id"] == "idea_abc123"


class TestSubmitApplicationCreationTicket:
    def test_creates_d3_ticket(self):
        tid = submit_application_creation_ticket(
            application_id="app_abc123",
            project_id="proj_def456",
            call_id="call_ghi789",
            amount=250_000.0,
        )
        t = fetch_by_id(tid)
        assert t.decision_class == "D3"
        assert t.gate_type == "financial"
        assert t.priority == "P2"
        assert t.payload["amount"] == 250_000.0

    def test_high_amount_raises_priority(self):
        tid = submit_application_creation_ticket(
            application_id="app_big",
            project_id="proj_1",
            amount=750_000.0,
        )
        t = fetch_by_id(tid)
        assert t.priority == "P1"


class TestSubmitSubmissionTicket:
    def test_creates_d4_ticket(self):
        tid = submit_submission_ticket(
            application_id="app_abc123",
            session_id="sess_def456",
            portal="EC Portal",
            amount=1_200_000.0,
        )
        t = fetch_by_id(tid)
        assert t.decision_class == "D4"
        assert t.gate_type == "financial"
        assert t.priority == "P0"
        assert "final submission" in t.title.lower()
        assert t.payload["action"] == "final_submission"

    def test_lower_amount_is_p1(self):
        tid = submit_submission_ticket(
            application_id="app_small",
            session_id="sess_1",
            amount=100_000.0,
        )
        t = fetch_by_id(tid)
        assert t.priority == "P1"


class TestApprovalHelpers:
    def test_check_pending_and_approved(self):
        tid = submit_scan_ticket("job_xyz", calls_found=5)
        assert check_pending(tid) is True
        assert check_approved(tid) is False

        approve_for_test(tid, reviewer="operator_a")

        assert check_pending(tid) is False
        assert check_approved(tid) is True

    def test_check_missing_ticket(self):
        assert check_approved("nonexistent") is False
        assert check_pending("nonexistent") is False


class TestIntegrationWithPendingList:
    def test_tickets_appear_in_fetch_pending(self):
        submit_scan_ticket("job_a", calls_found=3)
        submit_scan_ticket("job_b", calls_found=7)
        submit_application_creation_ticket("app_1", "proj_1", amount=100_000)

        pending = fetch_pending(origin="funding")
        assert len(pending) == 3
        # All should be funding origin
        assert all(t.origin == "funding" for t in pending)
