"""Tests for grpc.governance_server module."""

import pytest

try:
    from sylion.grpc_stubs import sylion_governance_pb2
    _HAS_STUBS = True
except ImportError:
    _HAS_STUBS = False

pytestmark = pytest.mark.skipif(not _HAS_STUBS, reason="gRPC stubs not available")


if _HAS_STUBS:
    from sylion.grpc.governance_server import GovernanceServicer, CouncilServicer

    class MockContext:
        def __init__(self):
            self.code = None
            self.details = None
        def set_code(self, code):
            self.code = code
        def set_details(self, details):
            self.details = details

    class TestGovernanceServicer:
        @pytest.fixture
        def servicer(self):
            return GovernanceServicer()

        @pytest.fixture
        def ctx(self):
            return MockContext()

        def test_classify_decision(self, servicer, ctx):
            req = sylion_governance_pb2.ClassifyDecisionRequest(
                title="Test Decision",
                description="Some decision",
                affected_modules=["mod-a"],
            )
            resp = servicer.ClassifyDecision(req, ctx)
            assert ctx.code is None

        def test_create_proposal(self, servicer, ctx):
            req = sylion_governance_pb2.CreateProposalRequest(
                title="Prop 1",
                description="A proposal",
                proposer="tester",
                blast_radius=["mod-a"],
            )
            resp = servicer.CreateProposal(req, ctx)
            assert ctx.code is None
            assert resp.proposal.proposal_id != ""
            assert resp.proposal.title == "Prop 1"

        def test_get_proposal(self, servicer, ctx):
            create_resp = servicer.CreateProposal(
                sylion_governance_pb2.CreateProposalRequest(
                    title="Get Prop", description="d", proposer="p",
                ), ctx,
            )
            pid = create_resp.proposal.proposal_id
            get_resp = servicer.GetProposal(
                sylion_governance_pb2.GetProposalRequest(proposal_id=pid), ctx,
            )
            assert ctx.code is None
            assert get_resp.proposal.proposal_id == pid

        def test_get_proposal_not_found(self, servicer, ctx):
            req = sylion_governance_pb2.GetProposalRequest(proposal_id="nonexistent")
            resp = servicer.GetProposal(req, ctx)
            assert ctx.code is not None

        def test_list_proposals(self, servicer, ctx):
            for i in range(3):
                servicer.CreateProposal(sylion_governance_pb2.CreateProposalRequest(
                    title=f"List {i}", description="d", proposer="p",
                ), ctx)
            req = sylion_governance_pb2.ListProposalsRequest()
            resp = servicer.ListProposals(req, ctx)
            assert len(resp.proposals) >= 3

        def test_approve_proposal(self, servicer, ctx):
            create_resp = servicer.CreateProposal(
                sylion_governance_pb2.CreateProposalRequest(
                    title="Approve Me", description="d", proposer="p",
                ), ctx,
            )
            req = sylion_governance_pb2.ProposalActionRequest(
                proposal_id=create_resp.proposal.proposal_id,
                actor="admin",
                reason="looks good",
            )
            resp = servicer.ApproveProposal(req, ctx)
            assert ctx.code is None

        def test_reject_proposal(self, servicer, ctx):
            create_resp = servicer.CreateProposal(
                sylion_governance_pb2.CreateProposalRequest(
                    title="Reject Me", description="d", proposer="p",
                ), ctx,
            )
            req = sylion_governance_pb2.ProposalActionRequest(
                proposal_id=create_resp.proposal.proposal_id,
                actor="admin",
                reason="not ready",
            )
            resp = servicer.RejectProposal(req, ctx)
            assert ctx.code is None

    class TestCouncilServicer:
        @pytest.fixture
        def servicer(self):
            return CouncilServicer()

        @pytest.fixture
        def ctx(self):
            return MockContext()

        def test_create_session(self, servicer, ctx):
            req = sylion_governance_pb2.CreateSessionRequest(
                proposal_id="prop-1",
                quorum=3,
                ttl_seconds=300,
            )
            resp = servicer.CreateSession(req, ctx)
            assert ctx.code is None
            assert resp.session.session_id != ""

        def test_cast_vote(self, servicer, ctx):
            sess_resp = servicer.CreateSession(
                sylion_governance_pb2.CreateSessionRequest(
                    proposal_id="vote-prop", quorum=3,
                ), ctx,
            )
            req = sylion_governance_pb2.CastVoteRequest(
                session_id=sess_resp.session.session_id,
                voter="voter-1",
                vote=sylion_governance_pb2.YES,
                rationale="I agree",
            )
            resp = servicer.CastVote(req, ctx)
            assert ctx.code is None

        def test_tally_votes(self, servicer, ctx):
            sess_resp = servicer.CreateSession(
                sylion_governance_pb2.CreateSessionRequest(
                    proposal_id="tally-prop", quorum=1,
                ), ctx,
            )
            sid = sess_resp.session.session_id
            servicer.CastVote(sylion_governance_pb2.CastVoteRequest(
                session_id=sid, voter="v1", vote=sylion_governance_pb2.YES,
            ), ctx)
            req = sylion_governance_pb2.TallyVotesRequest(session_id=sid)
            resp = servicer.TallyVotes(req, ctx)
            assert ctx.code is None
            assert resp.yes_votes >= 1

        def test_human_gate(self, servicer, ctx):
            req = sylion_governance_pb2.HumanGateRequest(
                proposal_id="gate-prop",
                reason="needs human review",
                timeout_secs=60,
            )
            resp = servicer.HumanGate(req, ctx)
            assert ctx.code is None
            assert resp.session_id != ""
