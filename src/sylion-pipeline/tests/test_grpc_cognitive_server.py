"""Tests for grpc.cognitive_server module."""

import pytest

try:
    from sylion.grpc_stubs import sylion_cognitive_pb2
    _HAS_STUBS = True
except ImportError:
    _HAS_STUBS = False

pytestmark = pytest.mark.skipif(not _HAS_STUBS, reason="gRPC stubs not available")


if _HAS_STUBS:
    from sylion.grpc.cognitive_server import ModelRouterServicer, PlanServicer

    class MockContext:
        def __init__(self):
            self.code = None
            self.details = None
        def set_code(self, code):
            self.code = code
        def set_details(self, details):
            self.details = details

    class TestModelRouterServicer:
        @pytest.fixture
        def servicer(self):
            return ModelRouterServicer()

        @pytest.fixture
        def ctx(self):
            return MockContext()

        def test_register_model(self, servicer, ctx):
            req = sylion_cognitive_pb2.RegisterModelRequest(
                model_id="gpt-4",
                provider="openai",
                display_name="GPT-4",
            )
            resp = servicer.RegisterModel(req, ctx)
            assert ctx.code is None
            assert resp.model.model_id == "gpt-4"

        def test_route_request(self, servicer, ctx):
            servicer.RegisterModel(sylion_cognitive_pb2.RegisterModelRequest(
                model_id="route-model", provider="test", display_name="RM",
            ), ctx)
            req = sylion_cognitive_pb2.RouteRequestRequest(prompt="test task")
            resp = servicer.RouteRequest(req, ctx)
            assert ctx.code is None

        def test_list_models(self, servicer, ctx):
            servicer.RegisterModel(sylion_cognitive_pb2.RegisterModelRequest(
                model_id="list-model", provider="test", display_name="LM",
            ), ctx)
            req = sylion_cognitive_pb2.ListModelsRequest()
            resp = servicer.ListModels(req, ctx)
            assert len(resp.models) >= 1

        def test_get_usage_stats(self, servicer, ctx):
            req = sylion_cognitive_pb2.GetUsageStatsRequest(model_id="test")
            resp = servicer.GetUsageStats(req, ctx)
            assert ctx.code is None

    class TestPlanServicer:
        @pytest.fixture
        def servicer(self):
            return PlanServicer()

        @pytest.fixture
        def ctx(self):
            return MockContext()

        def test_create_plan(self, servicer, ctx):
            req = sylion_cognitive_pb2.CreatePlanRequest(
                title="Test Plan",
                goal="Test goal",
            )
            resp = servicer.CreatePlan(req, ctx)
            assert ctx.code is None
            assert resp.plan.plan_id != ""
            assert resp.plan.title == "Test Plan"

        def test_decompose_plan(self, servicer, ctx):
            req = sylion_cognitive_pb2.DecomposePlanRequest(
                plan_id="any",
                max_subtasks=3,
            )
            resp = servicer.DecomposePlan(req, ctx)
            assert ctx.code is None

        def test_get_next_task(self, servicer, ctx):
            create_resp = servicer.CreatePlan(
                sylion_cognitive_pb2.CreatePlanRequest(title="next-task-plan"), ctx,
            )
            plan_id = create_resp.plan.plan_id
            req = sylion_cognitive_pb2.GetNextTaskRequest(plan_id=plan_id)
            resp = servicer.GetNextTask(req, ctx)
            # May be NOT_FOUND if no tasks yet
            # Just verify no crash
