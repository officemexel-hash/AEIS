"""
SYLION gRPC -- Governance Service Servers

Implements gRPC service servers for governance modules:
- GovernanceService
- CouncilService

Wraps existing SQLite-backed services to serve proto-defined RPCs.
"""

from __future__ import annotations

import logging

import grpc

from sylion.governance.decision_ladder import get_decision_ladder, DecisionProposal
from sylion.governance.council_workflow import (
    get_council_workflow, CouncilSession, Vote as CouncilVote, VoteValue,
)

log = logging.getLogger("sylion.grpc.governance_server")

try:
    from sylion.grpc_stubs import sylion_governance_pb2
    from sylion.grpc_stubs import sylion_governance_pb2_grpc
    from sylion.grpc_stubs import sylion_common_pb2
    _HAS_STUBS = True
except ImportError:
    _HAS_STUBS = False
    log.warning("gRPC stubs not available, governance servers disabled")


if _HAS_STUBS:

    class GovernanceServicer(sylion_governance_pb2_grpc.GovernanceServiceServicer):
        """gRPC server for Governance (Decision Ladder)."""

        def __init__(self):
            self._ladder = get_decision_ladder()

        def ClassifyDecision(self, request, context):
            proposal = DecisionProposal(
                title=request.title,
                description=request.description,
            )
            result = self._ladder.propose(proposal)
            dc = result.get("decision_class", "D0")
            class_map = {
                "D0": sylion_common_pb2.D0_ROUTINE,
                "D1": sylion_common_pb2.D1_LOW_RISK,
                "D2": sylion_common_pb2.D2_MODERATE,
                "D3": sylion_common_pb2.D3_SIGNIFICANT,
                "D4": sylion_common_pb2.D4_HIGH_RISK,
                "D5": sylion_common_pb2.D5_CRITICAL,
            }
            return sylion_governance_pb2.ClassifyDecisionResponse(
                decision_class=class_map.get(dc, sylion_common_pb2.D0_ROUTINE),
                confidence=0.8,
                rationale=dc,
            )

        def CreateProposal(self, request, context):
            proposal = DecisionProposal(
                title=request.title,
                description=request.description,
                proposed_by=request.proposer,
                blast_radius=",".join(request.blast_radius) if request.blast_radius else "low",
            )
            result = self._ladder.propose(proposal)
            return sylion_governance_pb2.CreateProposalResponse(
                proposal=sylion_governance_pb2.Proposal(
                    proposal_id=result.get("proposal_id", ""),
                    title=request.title,
                    description=request.description,
                    proposer=request.proposer,
                )
            )

        def GetProposal(self, request, context):
            result = self._ladder.get_proposal(request.proposal_id)
            if not result:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Proposal {request.proposal_id} not found")
                return sylion_governance_pb2.GetProposalResponse()
            return sylion_governance_pb2.GetProposalResponse(
                proposal=sylion_governance_pb2.Proposal(
                    proposal_id=result.get("proposal_id", ""),
                    title=result.get("title", ""),
                    description=result.get("description", ""),
                    proposer=result.get("proposed_by", ""),
                )
            )

        def ListProposals(self, request, context):
            results = self._ladder.list_proposals()
            proposals = []
            for r in results:
                proposals.append(sylion_governance_pb2.Proposal(
                    proposal_id=r.get("proposal_id", ""),
                    title=r.get("title", ""),
                    description=r.get("description", ""),
                    proposer=r.get("proposed_by", ""),
                ))
            return sylion_governance_pb2.ListProposalsResponse(proposals=proposals)

        def ApproveProposal(self, request, context):
            try:
                result = self._ladder.approve(
                    request.proposal_id,
                    approved_by=request.actor,
                    notes=request.reason,
                )
            except Exception as exc:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(str(exc))
                return sylion_governance_pb2.ProposalActionResponse()
            return sylion_governance_pb2.ProposalActionResponse(
                proposal=sylion_governance_pb2.Proposal(
                    proposal_id=result.get("proposal_id", ""),
                    title=result.get("title", ""),
                )
            )

        def RejectProposal(self, request, context):
            try:
                result = self._ladder.reject(
                    request.proposal_id,
                    rejected_by=request.actor,
                    reason=request.reason,
                )
            except Exception as exc:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(str(exc))
                return sylion_governance_pb2.ProposalActionResponse()
            return sylion_governance_pb2.ProposalActionResponse(
                proposal=sylion_governance_pb2.Proposal(
                    proposal_id=result.get("proposal_id", ""),
                    title=result.get("title", ""),
                )
            )

    class CouncilServicer(sylion_governance_pb2_grpc.CouncilServiceServicer):
        """gRPC server for Council Workflow."""

        def __init__(self):
            self._council = get_council_workflow()

        def CreateSession(self, request, context):
            session = CouncilSession(
                proposal_id=request.proposal_id,
                required_quorum=request.quorum or 4,
            )
            result = self._council.open_session(session)
            return sylion_governance_pb2.CreateSessionResponse(
                session=sylion_governance_pb2.CouncilSession(
                    session_id=result.get("session_id", ""),
                    proposal_id=request.proposal_id,
                    quorum=request.quorum or 4,
                )
            )

        def CastVote(self, request, context):
            vote_map = {
                sylion_governance_pb2.YES: VoteValue.APPROVE,
                sylion_governance_pb2.NO: VoteValue.REJECT,
                sylion_governance_pb2.ABSTAIN: VoteValue.ABSTAIN,
            }
            value = vote_map.get(request.vote, VoteValue.ABSTAIN)
            vote = CouncilVote(
                session_id=request.session_id,
                member_id=request.voter,
                value=value,
                rationale=request.rationale,
            )
            result = self._council.cast_vote(vote)
            return sylion_governance_pb2.CastVoteResponse(
                accepted=result.get("accepted", False),
            )

        def TallyVotes(self, request, context):
            result = self._council.tally(request.session_id)
            return sylion_governance_pb2.TallyVotesResponse(
                yes_votes=result.get("approves", 0),
                no_votes=result.get("rejects", 0),
                abstentions=result.get("abstains", 0),
                quorum_reached=result.get("resolved", False),
            )

        def HumanGate(self, request, context):
            session = CouncilSession(
                proposal_id=request.proposal_id,
                required_quorum=1,
            )
            result = self._council.open_session(session)
            return sylion_governance_pb2.HumanGateResponse(
                session_id=result.get("session_id", ""),
            )
