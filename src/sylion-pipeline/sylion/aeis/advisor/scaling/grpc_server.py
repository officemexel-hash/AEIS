"""gRPC facade for the advisor scaling service."""

from __future__ import annotations

import json
from types import SimpleNamespace

from sylion.aeis.advisor.scaling.service import ScalingService, get_scaling_service

try:
    from sylion.aeis.advisor._generated import scaling_pb2, scaling_pb2_grpc
    _HAS_STUBS = True
except ImportError:
    scaling_pb2 = None
    scaling_pb2_grpc = None
    _HAS_STUBS = False


_BaseServicer = scaling_pb2_grpc.ScalingServiceServicer if _HAS_STUBS else object


class ScalingServicer(_BaseServicer):
    """gRPC servicer for ScalingService."""

    def __init__(self, service: ScalingService | None = None):
        self._service = service or get_scaling_service()

    def RecommendTopology(self, request, context):
        raw = getattr(request, "workload_profile", None)
        workload_profile = {
            "estimated_tokens_per_day": getattr(raw, "estimated_tokens_per_day", 0),
            "parallelism": getattr(raw, "parallelism", 0),
            "latency_target_seconds": getattr(raw, "latency_target_seconds", 0.0),
        }
        return _scaling_card_message(
            self._service.recommend_topology(
                operator_id=getattr(request, "operator_id", ""),
                project_id=getattr(request, "project_id", ""),
                workload_profile=workload_profile,
            )
        )

    def ProposeStagingPlan(self, request, context):
        plan = self._service.propose_staging_plan(
            current_topology=getattr(request, "current_topology", ""),
            target_topology=getattr(request, "target_topology", ""),
        )
        return _message(
            "StagingPlan",
            plan_id=plan.plan_id,
            current_topology=plan.current_topology,
            target_topology=plan.target_topology,
            phases=[_phase_message(item) for item in plan.phases],
        )

    def GetEnvInventory(self, request, context):
        envs = self._service.get_env_inventory(operator_id=getattr(request, "operator_id", ""))
        return _message("GetEnvInventoryResponse", envs=[_env_message(item) for item in envs])

    def RegisterEnv(self, request, context):
        raw = getattr(request, "env", None)
        env = self._service.register_env(
            {
                "env_id": getattr(raw, "env_id", ""),
                "operator_id": getattr(raw, "operator_id", ""),
                "name": getattr(raw, "name", ""),
                "kind": getattr(raw, "kind", ""),
                "capacity_tokens_per_day": getattr(raw, "capacity_tokens_per_day", 0),
                "registered_at": getattr(raw, "registered_at", 0.0),
            }
        )
        return _message("RegisterEnvResponse", env_id=env["env_id"])


def register_scaling_service(server, service: ScalingService | None = None) -> bool:
    if not _HAS_STUBS:
        return False
    scaling_pb2_grpc.add_ScalingServiceServicer_to_server(ScalingServicer(service), server)
    return True


def _scaling_card_message(card):
    return _message(
        "ScalingCard",
        card_id=card.card_id,
        operator_id=card.operator_id,
        project_id=card.project_id,
        recommended=card.recommended,
        alternatives=card.alternatives,
        d_level=card.d_level,
        evidence_pack_id=card.evidence_pack_id or "",
        human_gate_required=card.human_gate_required,
        impacts_json=json.dumps(card.impacts, sort_keys=True),
    )


def _phase_message(item):
    if isinstance(item, dict):
        return _message(
            "StagingPhase",
            phase=int(item.get("phase", 0) or 0),
            action=item.get("action", ""),
            topology=item.get("topology", ""),
            description=item.get("description", ""),
        )
    return _message("StagingPhase", **item.__dict__)


def _env_message(item):
    if isinstance(item, dict):
        return _message("Env", **item)
    return _message("Env", **item.__dict__)


def _message(name: str, **fields):
    if _HAS_STUBS and hasattr(scaling_pb2, name):
        return getattr(scaling_pb2, name)(**fields)
    return SimpleNamespace(**fields)
