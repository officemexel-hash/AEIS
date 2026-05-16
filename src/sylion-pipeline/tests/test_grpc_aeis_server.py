"""Tests for grpc.aeis_server module."""

import pytest

try:
    from sylion.grpc_stubs import sylion_aeis_pb2
    _HAS_STUBS = True
except ImportError:
    _HAS_STUBS = False

pytestmark = pytest.mark.skipif(not _HAS_STUBS, reason="gRPC stubs not available")


if _HAS_STUBS:
    from sylion.grpc.aeis_server import AutonomyServicer, ExplanationServicer, ImprovementServicer

    class MockContext:
        def __init__(self):
            self.code = None
            self.details = None
        def set_code(self, code):
            self.code = code
        def set_details(self, details):
            self.details = details

    class TestAutonomyServicer:
        @pytest.fixture
        def servicer(self):
            return AutonomyServicer()

        @pytest.fixture
        def ctx(self):
            return MockContext()

        def test_get_status(self, servicer, ctx):
            req = sylion_aeis_pb2.GetStatusRequest()
            resp = servicer.GetStatus(req, ctx)
            assert ctx.code is None
            assert resp.status.current_stage != 0

        def test_get_stages(self, servicer, ctx):
            req = sylion_aeis_pb2.GetStagesRequest()
            resp = servicer.GetStages(req, ctx)
            assert ctx.code is None
            assert len(resp.stages) == 5

        def test_advance_stage(self, servicer, ctx):
            req = sylion_aeis_pb2.AdvanceStageRequest(reason="testing")
            resp = servicer.AdvanceStage(req, ctx)
            assert ctx.code is None
            assert resp.status.current_stage != 0

        def test_get_actions(self, servicer, ctx):
            req = sylion_aeis_pb2.GetActionsRequest()
            resp = servicer.GetActions(req, ctx)
            assert ctx.code is None
            assert len(resp.actions) >= 3

    class TestExplanationServicer:
        @pytest.fixture
        def servicer(self):
            return ExplanationServicer()

        @pytest.fixture
        def ctx(self):
            return MockContext()

        def test_create_explanation(self, servicer, ctx):
            req = sylion_aeis_pb2.CreateExplanationRequest(
                type=sylion_aeis_pb2.EXPL_DECISION_RATIONALE,
                audience=sylion_aeis_pb2.AUD_DEVELOPER,
                subject_id="dec-123",
                summary="Because X",
                detail="Full rationale here",
                confidence=0.9,
            )
            resp = servicer.CreateExplanation(req, ctx)
            assert ctx.code is None
            assert resp.explanation.explanation_id != ""
            assert resp.explanation.summary == "Because X"

        def test_list_explanations(self, servicer, ctx):
            req = sylion_aeis_pb2.ListExplanationsRequest()
            resp = servicer.ListExplanations(req, ctx)
            assert ctx.code is None

        def test_get_explanation_not_found(self, servicer, ctx):
            req = sylion_aeis_pb2.GetExplanationRequest(explanation_id="nonexistent")
            resp = servicer.GetExplanation(req, ctx)
            assert ctx.code is not None

    class TestImprovementServicer:
        @pytest.fixture
        def servicer(self):
            return ImprovementServicer()

        @pytest.fixture
        def ctx(self):
            return MockContext()

        def test_create_improvement(self, servicer, ctx):
            req = sylion_aeis_pb2.CreateImprovementRequest(
                title="Improve X",
                description="Make X better",
                risk=sylion_aeis_pb2.RISK_LOW,
            )
            resp = servicer.CreateImprovement(req, ctx)
            assert ctx.code is None
            assert resp.improvement.improvement_id != ""

        def test_list_improvements(self, servicer, ctx):
            for i in range(3):
                servicer.CreateImprovement(sylion_aeis_pb2.CreateImprovementRequest(
                    title=f"List {i}", description="d",
                ), ctx)
            req = sylion_aeis_pb2.ListImprovementsRequest()
            resp = servicer.ListImprovements(req, ctx)
            assert len(resp.improvements) >= 3

        def test_get_next(self, servicer, ctx):
            servicer.CreateImprovement(sylion_aeis_pb2.CreateImprovementRequest(
                title="Next item", description="d",
            ), ctx)
            req = sylion_aeis_pb2.GetNextRequest(worker_id="w1")
            resp = servicer.GetNext(req, ctx)
            assert ctx.code is None

        def test_start_improvement(self, servicer, ctx):
            create_resp = servicer.CreateImprovement(
                sylion_aeis_pb2.CreateImprovementRequest(title="Start me", description="d"), ctx,
            )
            req = sylion_aeis_pb2.StartImprovementRequest(
                improvement_id=create_resp.improvement.improvement_id,
                assigned_to="worker-1",
            )
            resp = servicer.StartImprovement(req, ctx)
            assert ctx.code is None

        def test_complete_improvement(self, servicer, ctx):
            create_resp = servicer.CreateImprovement(
                sylion_aeis_pb2.CreateImprovementRequest(title="Complete me", description="d"), ctx,
            )
            imp_id = create_resp.improvement.improvement_id
            servicer.StartImprovement(sylion_aeis_pb2.StartImprovementRequest(
                improvement_id=imp_id, assigned_to="w1",
            ), ctx)
            req = sylion_aeis_pb2.CompleteImprovementRequest(
                improvement_id=imp_id, result=b"done",
            )
            resp = servicer.CompleteImprovement(req, ctx)
            assert ctx.code is None

        def test_reject_improvement(self, servicer, ctx):
            create_resp = servicer.CreateImprovement(
                sylion_aeis_pb2.CreateImprovementRequest(title="Reject me", description="d"), ctx,
            )
            req = sylion_aeis_pb2.RejectImprovementRequest(
                improvement_id=create_resp.improvement.improvement_id,
                reason="not viable",
            )
            resp = servicer.RejectImprovement(req, ctx)
            assert ctx.code is None
