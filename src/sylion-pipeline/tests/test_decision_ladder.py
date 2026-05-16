"""
SYLION Governance -- Decision Ladder Tests

Tests for DecisionLadder: propose, approve, reject, execute lifecycle,
CRUD operations, filtering, error handling, and event emission.
"""

from __future__ import annotations

import pytest

from sylion.core.decision_gate_engine import DecisionGateEngine, DecisionClass
from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.evidence_spine import EvidenceSpine
from sylion.governance.decision_ladder import (
    DecisionLadder,
    DecisionProposal,
    DecisionStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def spine():
    return EvidenceSpine()


@pytest.fixture
def ladder(bus, spine):
    return DecisionLadder(
        gate_engine=DecisionGateEngine(),
        evidence_spine=spine,
        event_bus=bus,
    )


@pytest.fixture
def sample_proposal():
    return DecisionProposal(
        title="Upgrade auth module",
        description="Replace JWT with Ed25519 tokens",
        source_plan="P12",
        module_id="auth",
        change_type="module",
        blast_radius="medium",
        reversible=True,
        proposed_by="agent-7",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDecisionLadderPropose:

    def test_propose_classifies_and_stores(self, ladder, sample_proposal):
        result = ladder.propose(sample_proposal)
        assert result["proposal_id"] == sample_proposal.proposal_id
        assert result["status"] == DecisionStatus.CLASSIFIED.value
        assert result["decision_class"] in ("D0", "D1", "D2", "D3", "D4", "D5")

    def test_propose_stores_in_db(self, ladder, sample_proposal):
        ladder.propose(sample_proposal)
        row = ladder.get_proposal(sample_proposal.proposal_id)
        assert row is not None
        assert row["title"] == "Upgrade auth module"
        assert row["status"] == DecisionStatus.CLASSIFIED.value

    def test_propose_emits_event(self, ladder, sample_proposal):
        events = []
        ladder._event_bus.subscribe("decision.proposed", lambda e: events.append(e))
        ladder.propose(sample_proposal)
        assert len(events) == 1
        assert events[0].payload["proposal_id"] == sample_proposal.proposal_id

    def test_propose_records_in_evidence_spine(self, ladder, spine, sample_proposal):
        ladder.propose(sample_proposal)
        entries = spine.query(source_plan="P12")
        assert len(entries) == 1
        assert entries[0]["event_type"] == "decision.proposed"

    def test_propose_d0_informational(self, ladder):
        prop = DecisionProposal(
            title="Update README",
            description="Docs only",
            source_plan="P01",
            change_type="config",
            blast_radius="low",
            reversible=True,
        )
        result = ladder.propose(prop)
        assert result["decision_class"] == "D1"

    def test_propose_d5_kernel(self, ladder):
        prop = DecisionProposal(
            title="Kernel rewrite",
            description="Full kernel refactor",
            source_plan="P99",
            change_type="system",
            blast_radius="critical",
            affects_kernel=True,
        )
        result = ladder.propose(prop)
        assert result["decision_class"] == "D5"


class TestDecisionLadderApproveReject:

    def test_approve_classified_proposal(self, ladder, sample_proposal):
        ladder.propose(sample_proposal)
        result = ladder.approve(sample_proposal.proposal_id, approved_by="council-lead")
        assert result["approved"] is True
        assert result["status"] == DecisionStatus.APPROVED.value

    def test_approve_updates_db_status(self, ladder, sample_proposal):
        ladder.propose(sample_proposal)
        ladder.approve(sample_proposal.proposal_id)
        row = ladder.get_proposal(sample_proposal.proposal_id)
        assert row["status"] == DecisionStatus.APPROVED.value

    def test_reject_classified_proposal(self, ladder, sample_proposal):
        ladder.propose(sample_proposal)
        result = ladder.reject(sample_proposal.proposal_id, reason="Risk too high")
        assert result["rejected"] is True

    def test_approve_nonexistent_proposal(self, ladder):
        result = ladder.approve("ghost-id")
        assert result["approved"] is False
        assert "not found" in result["message"]

    def test_approve_already_approved_proposal(self, ladder, sample_proposal):
        ladder.propose(sample_proposal)
        ladder.approve(sample_proposal.proposal_id)
        result = ladder.approve(sample_proposal.proposal_id)
        assert result["approved"] is False
        assert "not classified" in result["message"]

    def test_reject_nonexistent_proposal(self, ladder):
        result = ladder.reject("ghost-id")
        assert result["rejected"] is False


class TestDecisionLadderExecute:

    def test_execute_approved_proposal(self, ladder, sample_proposal):
        ladder.propose(sample_proposal)
        ladder.approve(sample_proposal.proposal_id)
        result = ladder.execute(sample_proposal.proposal_id)
        assert result["executed"] is True

    def test_execute_updates_db_status(self, ladder, sample_proposal):
        ladder.propose(sample_proposal)
        ladder.approve(sample_proposal.proposal_id)
        ladder.execute(sample_proposal.proposal_id)
        row = ladder.get_proposal(sample_proposal.proposal_id)
        assert row["status"] == DecisionStatus.EXECUTED.value

    def test_execute_unapproved_proposal_fails(self, ladder, sample_proposal):
        ladder.propose(sample_proposal)
        result = ladder.execute(sample_proposal.proposal_id)
        assert result["executed"] is False

    def test_execute_nonexistent_proposal(self, ladder):
        result = ladder.execute("ghost-id")
        assert result["executed"] is False


class TestDecisionLadderQuery:

    def test_get_proposal_not_found(self, ladder):
        assert ladder.get_proposal("nonexistent") is None

    def test_list_proposals_filter_by_status(self, ladder):
        p1 = DecisionProposal(title="A", description="a", source_plan="P1", change_type="config")
        p2 = DecisionProposal(title="B", description="b", source_plan="P2", change_type="module")
        ladder.propose(p1)
        ladder.propose(p2)
        ladder.approve(p1.proposal_id)

        classified = ladder.list_proposals(status=DecisionStatus.CLASSIFIED.value)
        approved = ladder.list_proposals(status=DecisionStatus.APPROVED.value)
        assert len(classified) == 1
        assert len(approved) == 1

    def test_list_proposals_filter_by_class(self, ladder):
        p1 = DecisionProposal(
            title="Low risk", description="d", source_plan="P1",
            change_type="config", blast_radius="low",
        )
        ladder.propose(p1)
        dc = ladder.get_proposal(p1.proposal_id)["decision_class"]
        results = ladder.list_proposals(decision_class=dc)
        assert len(results) >= 1

    def test_list_proposals_filter_by_source_plan(self, ladder):
        p1 = DecisionProposal(title="X", description="d", source_plan="PLAN-X", change_type="config")
        p2 = DecisionProposal(title="Y", description="d", source_plan="PLAN-Y", change_type="config")
        ladder.propose(p1)
        ladder.propose(p2)
        results = ladder.list_proposals(source_plan="PLAN-X")
        assert len(results) == 1
        assert results[0]["source_plan"] == "PLAN-X"

    def test_list_proposals_returns_all_unfiltered(self, ladder):
        for i in range(5):
            p = DecisionProposal(
                title=f"P-{i}", description=f"d{i}", source_plan=f"SP{i}",
                change_type="config",
            )
            ladder.propose(p)
        all_proposals = ladder.list_proposals()
        assert len(all_proposals) == 5
