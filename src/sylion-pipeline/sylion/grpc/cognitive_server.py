"""
SYLION gRPC -- Cognitive Service Servers

Implements gRPC service servers for cognitive modules:
- ModelRouterService
- PlanService

Wraps existing SQLite-backed services to serve proto-defined RPCs.
"""

from __future__ import annotations

import logging

import grpc

from sylion.cognitive.model_router import get_model_router
from sylion.cognitive.planner import get_planner

log = logging.getLogger("sylion.grpc.cognitive_server")

try:
    from sylion.grpc_stubs import sylion_cognitive_pb2
    from sylion.grpc_stubs import sylion_cognitive_pb2_grpc
    _HAS_STUBS = True
except ImportError:
    _HAS_STUBS = False
    log.warning("gRPC stubs not available, cognitive servers disabled")


if _HAS_STUBS:

    class ModelRouterServicer(sylion_cognitive_pb2_grpc.ModelRouterServiceServicer):
        """gRPC server for Model Router."""

        def __init__(self):
            self._router = get_model_router()

        def RegisterModel(self, request, context):
            caps = list(request.capabilities.strengths) if request.capabilities.strengths else None
            result = self._router.register_model(
                model_id=request.model_id,
                provider=request.provider,
                model_name=request.display_name,
                capabilities=caps,
                cost_per_1k_tokens=request.capabilities.cost_per_1k_input,
            )
            return sylion_cognitive_pb2.RegisterModelResponse(
                model=sylion_cognitive_pb2.ModelEntry(
                    model_id=request.model_id,
                    provider=request.provider,
                    display_name=request.display_name,
                )
            )

        def RouteRequest(self, request, context):
            result = self._router.route_request(
                task_type=request.prompt[:100] if request.prompt else "general",
                complexity="medium",
                budget=None,
            )
            if not result:
                return sylion_cognitive_pb2.RouteRequestResponse()
            return sylion_cognitive_pb2.RouteRequestResponse(
                selected_model=result.get("model_id", ""),
                cost_estimate=result.get("estimated_cost", 0.0),
            )

        def ListModels(self, request, context):
            results = self._router.list_models(
                provider=request.provider_filter if request.provider_filter else None,
            )
            models = []
            for r in results:
                models.append(sylion_cognitive_pb2.ModelEntry(
                    model_id=r.get("model_id", ""),
                    provider=r.get("provider", ""),
                    display_name=r.get("model_name", ""),
                ))
            return sylion_cognitive_pb2.ListModelsResponse(models=models)

        def GetUsageStats(self, request, context):
            stats = self._router.get_usage_stats(
                model_id=request.model_id if request.model_id else None,
            )
            return sylion_cognitive_pb2.GetUsageStatsResponse(
                stats=sylion_cognitive_pb2.UsageStats(
                    model_id=request.model_id,
                    total_requests=stats.get("total_calls", 0),
                    total_cost=stats.get("total_cost", 0.0),
                )
            )

    class PlanServicer(sylion_cognitive_pb2_grpc.PlanServiceServicer):
        """gRPC server for Plan service."""

        def __init__(self):
            self._planner = get_planner()

        def CreatePlan(self, request, context):
            result = self._planner.create_plan(
                title=request.title,
                description=request.goal,
            )
            return sylion_cognitive_pb2.CreatePlanResponse(
                plan=sylion_cognitive_pb2.Plan(
                    plan_id=result.get("plan_id", ""),
                    title=result.get("title", ""),
                    goal=result.get("description", ""),
                )
            )

        def DecomposePlan(self, request, context):
            plan = self._planner.create_plan(title="decompose", description="sub")
            tasks_data = [{"title": f"sub-{i}", "description": f"subtask {i}"}
                         for i in range(min(request.max_subtasks or 3, 10))]
            self._planner.decompose(plan["plan_id"], tasks_data)
            tasks = self._planner.get_tasks(plan["plan_id"])
            pb_tasks = []
            for t in tasks:
                pb_tasks.append(sylion_cognitive_pb2.Task(
                    task_id=t.get("task_id", ""),
                    title=t.get("title", ""),
                    description=t.get("description", ""),
                    depends_on=t.get("depends_on", []),
                ))
            return sylion_cognitive_pb2.DecomposePlanResponse(
                decomposed_plan=sylion_cognitive_pb2.Plan(
                    plan_id=plan["plan_id"],
                    title="decompose",
                    tasks=pb_tasks,
                )
            )

        def GetNextTask(self, request, context):
            result = self._planner.get_next_task(request.plan_id)
            if not result:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("No ready tasks")
                return sylion_cognitive_pb2.GetNextTaskResponse()
            return sylion_cognitive_pb2.GetNextTaskResponse(
                task=sylion_cognitive_pb2.Task(
                    task_id=result.get("task_id", ""),
                    title=result.get("title", ""),
                    description=result.get("description", ""),
                )
            )

        def CompleteTask(self, request, context):
            result = self._planner.complete_task(request.task_id)
            if not result:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Task {request.task_id} not found")
                return sylion_cognitive_pb2.CompleteTaskResponse()
            return sylion_cognitive_pb2.CompleteTaskResponse(
                task=sylion_cognitive_pb2.Task(
                    task_id=result.get("task_id", ""),
                    title=result.get("title", ""),
                )
            )
