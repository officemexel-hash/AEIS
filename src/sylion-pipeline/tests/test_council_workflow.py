"""
SYLION Governance -- Council Workflow Tests

Tests for CouncilWorkflow: session lifecycle, voting, tally, quorum,
human gate decisions, duplicate vote rejection, and event emission.
"""

from __future__ import annotations

import pytest

from sylion.core.decision_gate_engine import DecisionClass
from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.council_workflow import (
    COUNCIL_SIZE,
    CouncilSession,
    CouncilWorkflow,
    SessionStatus,
    Vote,
    VoteValue,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def council(bus):
    return CouncilWorkflow(event_bus=bus)


@pytest.fixture
def d3_session():
    return CouncilSession(
        proposal_id="prop-d3-001",
        decision_class=DecisionClass.D3,
        title="Refactor DB layer",
        description="Migrate from SQLite to PostgreSQL",
        evidence_ref="ev-pack-001",
    )


def _make_votes(session_id, values):
    """Helper: create Vote objects for the 4 council members."""
    members = ["m1", "m2", "m3", "m4"]
    return [
        Vote(session_id=session_id, member_id=mid, value=val)
        for mid, val in zip(members, values)
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCouncilSessionLifecycle:

    def test_open_session(self, council, d3_session):
        result = council.open_session(d3_session)
        assert result["session_id"] == d3_session.session_id
        assert result["status"] == SessionStatus.OPEN.value

    def test_open_session_stored_in_db(self, council, d3_session):
        council.open_session(d3_session)
        row = council.get_session(d3_session.session_id)
        assert row is not None
        assert row["proposal_id"] == "prop-d3-001"
        assert row["decision_class"] == "D3"

    def test_open_session_emits_event(self, council, bus, d3_session):
        events = []
        bus.subscribe("council.session_opened", lambda e: events.append(e))
        council.open_session(d3_session)
        assert len(events) == 1
        assert events[0].payload["decision_class"] == "D3"

    def test_get_session_not_found(self, council):
        assert council.get_session("nonexistent") is None

    def test_list_sessions_empty(self, council):
        assert council.list_sessions() == []

    def test_list_sessions_filter_by_status(self, council):
        s1 = CouncilSession(proposal_id="p1", decision_class=DecisionClass.D3, title="T1")
        s2 = CouncilSession(proposal_id="p2", decision_class=DecisionClass.D3, title="T2")
        council.open_session(s1)
        council.open_session(s2)
        open_sessions = council.list_sessions(status=SessionStatus.OPEN.value)
        assert len(open_sessions) == 2


class TestCouncilVoting:

    def test_cast_single_vote(self, council, d3_session):
        council.open_session(d3_session)
        vote = Vote(session_id=d3_session.session_id, member_id="m1", value=VoteValue.APPROVE)
        result = council.cast_vote(vote)
        assert result["cast"] is True
        assert "vote_id" in result

    def test_cast_vote_updates_session_to_voting(self, council, d3_session):
        council.open_session(d3_session)
        vote = Vote(session_id=d3_session.session_id, member_id="m1", value=VoteValue.APPROVE)
        council.cast_vote(vote)
        row = council.get_session(d3_session.session_id)
        assert row["status"] == SessionStatus.VOTING.value

    def test_cast_vote_emits_event(self, council, bus, d3_session):
        council.open_session(d3_session)
        events = []
        bus.subscribe("council.vote_cast", lambda e: events.append(e))
        vote = Vote(session_id=d3_session.session_id, member_id="m1", value=VoteValue.APPROVE)
        council.cast_vote(vote)
        assert len(events) == 1
        assert events[0].payload["member_id"] == "m1"

    def test_reject_duplicate_vote(self, council, d3_session):
        council.open_session(d3_session)
        v1 = Vote(session_id=d3_session.session_id, member_id="m1", value=VoteValue.APPROVE)
        v2 = Vote(session_id=d3_session.session_id, member_id="m1", value=VoteValue.REJECT)
        council.cast_vote(v1)
        result = council.cast_vote(v2)
        assert result["cast"] is False
        assert "already voted" in result["message"]

    def test_reject_vote_on_nonexistent_session(self, council):
        vote = Vote(session_id="ghost", member_id="m1", value=VoteValue.APPROVE)
        result = council.cast_vote(vote)
        assert result["cast"] is False
        assert "not found" in result["message"]


class TestCouncilTally:

    def test_unanimous_approve_resolves(self, council, d3_session):
        council.open_session(d3_session)
        for v in _make_votes(d3_session.session_id, [VoteValue.APPROVE] * 4):
            council.cast_vote(v)
        tally = council.tally(d3_session.session_id)
        assert tally["resolved"] is True
        assert tally["outcome"] == "approved"
        assert tally["approves"] == 4

    def test_unanimous_reject_resolves(self, council, d3_session):
        council.open_session(d3_session)
        for v in _make_votes(d3_session.session_id, [VoteValue.REJECT] * 4):
            council.cast_vote(v)
        tally = council.tally(d3_session.session_id)
        assert tally["resolved"] is True
        assert tally["outcome"] == "rejected"

    def test_mixed_votes_below_quorum_rejects(self, council, d3_session):
        council.open_session(d3_session)
        # 3 approve, 1 reject = below 4/4 quorum
        for v in _make_votes(d3_session.session_id, [VoteValue.APPROVE] * 3 + [VoteValue.REJECT]):
            council.cast_vote(v)
        tally = council.tally(d3_session.session_id)
        assert tally["resolved"] is True
        assert tally["outcome"] == "rejected"

    def test_tally_updates_session_status_approved(self, council, d3_session):
        council.open_session(d3_session)
        for v in _make_votes(d3_session.session_id, [VoteValue.APPROVE] * 4):
            council.cast_vote(v)
        row = council.get_session(d3_session.session_id)
        assert row["status"] == SessionStatus.CLOSED_APPROVED.value

    def test_tally_updates_session_status_rejected(self, council, d3_session):
        council.open_session(d3_session)
        for v in _make_votes(d3_session.session_id, [VoteValue.REJECT] * 4):
            council.cast_vote(v)
        row = council.get_session(d3_session.session_id)
        assert row["status"] == SessionStatus.CLOSED_REJECTED.value

    def test_tally_nonexistent_session(self, council):
        result = council.tally("ghost")
        assert result["tallied"] is False

    def test_partial_votes_not_resolved(self, council, d3_session):
        council.open_session(d3_session)
        vote = Vote(session_id=d3_session.session_id, member_id="m1", value=VoteValue.APPROVE)
        council.cast_vote(vote)
        tally = council.tally(d3_session.session_id)
        assert tally["resolved"] is False
        assert tally["total"] == 1


class TestCouncilHumanGate:

    def test_human_gate_d4_session(self, council):
        session = CouncilSession(
            proposal_id="p-d4",
            decision_class=DecisionClass.D4,
            title="Critical change",
        )
        council.open_session(session)
        row = council.get_session(session.session_id)
        assert row["human_gate_req"] == 1

    def test_human_gate_not_required_d3(self, council, d3_session):
        council.open_session(d3_session)
        row = council.get_session(d3_session.session_id)
        assert row["human_gate_req"] == 0

    def test_human_gate_decide_approve(self, council):
        session = CouncilSession(
            proposal_id="p-d4-2",
            decision_class=DecisionClass.D4,
            title="Gate test",
        )
        council.open_session(session)
        # First get council approval
        for v in _make_votes(session.session_id, [VoteValue.APPROVE] * 4):
            council.cast_vote(v)
        result = council.human_gate_decide(session.session_id, "approved", by="human-1")
        assert result["decided"] is True
        assert result["human_gate"] == "approved"

    def test_human_gate_reject_before_council_approval(self, council):
        session = CouncilSession(
            proposal_id="p-d4-3",
            decision_class=DecisionClass.D4,
            title="Early gate",
        )
        council.open_session(session)
        result = council.human_gate_decide(session.session_id, "approved")
        assert result["decided"] is False
        assert "not approved" in result["message"].lower()

    def test_human_gate_on_nonexistent_session(self, council):
        result = council.human_gate_decide("ghost", "approved")
        assert result["decided"] is False
        assert "not found" in result["message"]

    def test_human_gate_not_required_rejection(self, council, d3_session):
        council.open_session(d3_session)
        for v in _make_votes(d3_session.session_id, [VoteValue.APPROVE] * 4):
            council.cast_vote(v)
        result = council.human_gate_decide(d3_session.session_id, "approved")
        assert result["decided"] is False
        assert "no human gate" in result["message"].lower()


class TestCouncilSessionD5:

    def test_d5_session_has_external_required(self, council):
        session = CouncilSession(
            proposal_id="p-d5",
            decision_class=DecisionClass.D5,
            title="Greenfield project",
        )
        council.open_session(session)
        row = council.get_session(session.session_id)
        assert row["external_req"] == 1
        assert row["human_gate_req"] == 1

    def test_d5_full_lifecycle(self, council):
        session = CouncilSession(
            proposal_id="p-d5-full",
            decision_class=DecisionClass.D5,
            title="Full D5 flow",
        )
        council.open_session(session)
        for v in _make_votes(session.session_id, [VoteValue.APPROVE] * 4):
            council.cast_vote(v)
        row = council.get_session(session.session_id)
        assert row["status"] == SessionStatus.CLOSED_APPROVED.value
        gate = council.human_gate_decide(session.session_id, "approved", by="cto")
        assert gate["decided"] is True
