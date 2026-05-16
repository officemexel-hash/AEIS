"""
SYLION gRPC -- AEIS Service Servers

Implements gRPC service servers for AEIS modules:
- AutonomyService
- ExplanationService
- ImprovementService

Wraps existing SQLite-backed services to serve proto-defined RPCs.
"""

from __future__ import annotations

import logging

import grpc

from sylion.aeis.autonomy_controller import get_autonomy_controller
from sylion.aeis.explanation_engine import get_explanation_engine
from sylion.aeis.improvement_queue import get_improvement_queue

log = logging.getLogger("sylion.grpc.aeis_server")

try:
    from sylion.grpc_stubs import sylion_aeis_pb2
    from sylion.grpc_stubs import sylion_aeis_pb2_grpc
    _HAS_STUBS = True
except ImportError:
    _HAS_STUBS = False
    log.warning("gRPC stubs not available, AEIS servers disabled")


if _HAS_STUBS:

    _AUTONOMY_STAGE_MAP = {
        "observe": sylion_aeis_pb2.AUTONOMY_S1_OBSERVE,
        "propose": sylion_aeis_pb2.AUTONOMY_S2_SUGGEST,
        "sandbox": sylion_aeis_pb2.AUTONOMY_S3_AUTOMATE,
        "limited_prod": sylion_aeis_pb2.AUTONOMY_S4_GOVERN,
        "full_governed": sylion_aeis_pb2.AUTONOMY_S5_EVOLVE,
    }

    class AutonomyServicer(sylion_aeis_pb2_grpc.AutonomyServiceServicer):
        """gRPC server for Autonomy Controller."""

        def __init__(self):
            self._ctrl = get_autonomy_controller()

        def GetStatus(self, request, context):
            stage = self._ctrl.get_stage()
            stats = self._ctrl.get_stats()
            stage_str = stage.value if hasattr(stage, "value") else "observe"
            pb_stage = _AUTONOMY_STAGE_MAP.get(stage_str, sylion_aeis_pb2.AUTONOMY_S1_OBSERVE)
            return sylion_aeis_pb2.GetStatusResponse(
                status=sylion_aeis_pb2.AutonomyStatus(
                    current_stage=pb_stage,
                    readiness_pct=stats.get("allowed_actions", 0) / max(stats.get("total_actions", 1), 1) * 100,
                )
            )

        def GetStages(self, request, context):
            stage_names = ["observe", "propose", "sandbox", "limited_prod", "full_governed"]
            stages = []
            for name in stage_names:
                stages.append(sylion_aeis_pb2.AutonomyStageDetail(
                    stage=_AUTONOMY_STAGE_MAP.get(name, sylion_aeis_pb2.AUTONOMY_S1_OBSERVE),
                    name=name,
                    description=f"S{stage_names.index(name)+1}: {name}",
                ))
            return sylion_aeis_pb2.GetStagesResponse(stages=stages)

        def AdvanceStage(self, request, context):
            result = self._ctrl.advance_stage({"reason": request.reason})
            stage_str = result.get("to_stage", result.get("current_stage", "observe"))
            pb_stage = _AUTONOMY_STAGE_MAP.get(stage_str, sylion_aeis_pb2.AUTONOMY_S1_OBSERVE)
            return sylion_aeis_pb2.AdvanceStageResponse(
                status=sylion_aeis_pb2.AutonomyStatus(
                    current_stage=pb_stage,
                )
            )

        def GetActions(self, request, context):
            actions = [
                sylion_aeis_pb2.AutonomyAction(
                    action_id="read",
                    title="Read",
                    description="Read-only access",
                    category="observe",
                    min_stage=sylion_aeis_pb2.AUTONOMY_S1_OBSERVE,
                    enabled=True,
                ),
                sylion_aeis_pb2.AutonomyAction(
                    action_id="propose",
                    title="Propose",
                    description="Propose changes",
                    category="suggest",
                    min_stage=sylion_aeis_pb2.AUTONOMY_S2_SUGGEST,
                    enabled=True,
                ),
                sylion_aeis_pb2.AutonomyAction(
                    action_id="execute_sandbox",
                    title="Execute Sandbox",
                    description="Execute in sandbox",
                    category="automate",
                    min_stage=sylion_aeis_pb2.AUTONOMY_S3_AUTOMATE,
                    enabled=True,
                ),
            ]
            return sylion_aeis_pb2.GetActionsResponse(actions=actions)

    class ExplanationServicer(sylion_aeis_pb2_grpc.ExplanationServiceServicer):
        """gRPC server for Explanation Engine."""

        def __init__(self):
            self._engine = get_explanation_engine()

        def CreateExplanation(self, request, context):
            result = self._engine.record_explanation(
                decision_id=request.subject_id,
                explanation_text=request.summary,
                confidence_score=request.confidence,
                decision_class="",
            )
            type_names = {1: "decision_rationale", 2: "system_behavior",
                         3: "model_output", 4: "incident_root_cause", 5: "architecture_change"}
            audience_names = {1: "developer", 2: "operator", 3: "stakeholder", 4: "auditor"}
            return sylion_aeis_pb2.CreateExplanationResponse(
                explanation=sylion_aeis_pb2.Explanation(
                    explanation_id=result.get("explanation_id", ""),
                    type=request.type,
                    audience=request.audience,
                    subject_id=request.subject_id,
                    summary=request.summary,
                    detail=request.detail,
                    confidence=request.confidence,
                )
            )

        def ListExplanations(self, request, context):
            stats = self._engine.get_accuracy_stats()
            return sylion_aeis_pb2.ListExplanationsResponse(
                explanations=[],
                next_token="",
            )

        def GetExplanation(self, request, context):
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Explanation {request.explanation_id} not found")
            return sylion_aeis_pb2.GetExplanationResponse()

    class ImprovementServicer(sylion_aeis_pb2_grpc.ImprovementServiceServicer):
        """gRPC server for Improvement Queue."""

        def __init__(self):
            self._queue = get_improvement_queue()

        def CreateImprovement(self, request, context):
            result = self._queue.submit(
                title=request.title,
                description=request.description,
                priority=0,
            )
            return sylion_aeis_pb2.CreateImprovementResponse(
                improvement=sylion_aeis_pb2.Improvement(
                    improvement_id=result.get("improvement_id", ""),
                    title=result.get("title", ""),
                    description=result.get("description", ""),
                )
            )

        def ListImprovements(self, request, context):
            results = self._queue.list_improvements()
            imps = []
            for r in results:
                imps.append(sylion_aeis_pb2.Improvement(
                    improvement_id=r.get("improvement_id", ""),
                    title=r.get("title", ""),
                    description=r.get("description", ""),
                ))
            return sylion_aeis_pb2.ListImprovementsResponse(improvements=imps)

        def GetNext(self, request, context):
            result = self._queue.get_next()
            if not result:
                return sylion_aeis_pb2.GetNextResponse()
            return sylion_aeis_pb2.GetNextResponse(
                improvement=sylion_aeis_pb2.Improvement(
                    improvement_id=result.get("improvement_id", ""),
                    title=result.get("title", ""),
                    description=result.get("description", ""),
                )
            )

        def StartImprovement(self, request, context):
            result = self._queue.start(request.improvement_id)
            return sylion_aeis_pb2.StartImprovementResponse(
                improvement=sylion_aeis_pb2.Improvement(
                    improvement_id=result.get("improvement_id", ""),
                    title=result.get("title", ""),
                )
            )

        def CompleteImprovement(self, request, context):
            result = self._queue.complete(
                request.improvement_id,
                result=request.result.decode("utf-8", errors="replace") if request.result else "",
            )
            return sylion_aeis_pb2.CompleteImprovementResponse(
                improvement=sylion_aeis_pb2.Improvement(
                    improvement_id=result.get("improvement_id", ""),
                )
            )

        def RejectImprovement(self, request, context):
            result = self._queue.reject(
                request.improvement_id,
                reason=request.reason,
            )
            return sylion_aeis_pb2.RejectImprovementResponse(
                improvement=sylion_aeis_pb2.Improvement(
                    improvement_id=result.get("improvement_id", ""),
                )
            )
