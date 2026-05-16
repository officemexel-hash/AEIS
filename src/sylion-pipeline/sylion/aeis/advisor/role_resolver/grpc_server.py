"""gRPC facade for the advisor role resolver service."""

from __future__ import annotations

from types import SimpleNamespace

from sylion.aeis.advisor.role_resolver.service import (
    RoleResolverService,
    get_role_resolver_service,
)

try:
    from sylion.aeis.advisor._generated import role_resolver_pb2, role_resolver_pb2_grpc
    _HAS_STUBS = True
except ImportError:
    role_resolver_pb2 = None
    role_resolver_pb2_grpc = None
    _HAS_STUBS = False


_BaseServicer = role_resolver_pb2_grpc.RoleResolverServiceServicer if _HAS_STUBS else object


class RoleResolverServicer(_BaseServicer):
    """gRPC servicer for RoleResolverService."""

    def __init__(self, service: RoleResolverService | None = None):
        self._service = service or get_role_resolver_service()

    def ResolveRole(self, request, context):
        return _model_choice_message(
            self._service.resolve_role(
                operator_id=getattr(request, "operator_id", ""),
                role=getattr(request, "role", ""),
                risk_level=getattr(request, "risk_level", ""),
                project_domain=getattr(request, "project_domain", ""),
                project_type=getattr(request, "project_type", ""),
            )
        )

    def ResolveJudgeModel(self, request, context):
        return _model_choice_message(
            self._service.resolve_judge(
                operator_id=getattr(request, "operator_id", ""),
                judge_purpose=getattr(request, "judge_purpose", ""),
                risk_level=getattr(request, "risk_level", ""),
            )
        )

    def ListAvailableRoles(self, request, context):
        roles = self._service.list_available_roles()
        return _message(
            "ListAvailableRolesResponse",
            roles=[_message("Role", **role.__dict__) for role in roles],
        )

    def GetRoutingMatrix(self, request, context):
        entries = self._service.get_routing_matrix()
        return _message(
            "GetRoutingMatrixResponse",
            entries=[
                _message(
                    "RoutingEntry",
                    purpose_or_role=item.purpose_or_role,
                    risk_level=item.risk_level,
                    model_id=item.model_id if isinstance(item.model_id, str) else ",".join(item.model_id),
                    description=item.description,
                )
                for item in entries
            ],
        )

    def PreviewRouting(self, request, context):
        preview = self._service.preview_routing(
            operator_id=getattr(request, "operator_id", ""),
            scenario=getattr(request, "scenario", ""),
        )
        return _message(
            "RoutingPreview",
            operator_id=preview.operator_id,
            scenario=preview.scenario,
            resolved=_model_choice_message(preview.resolved),
            alternatives=[_model_choice_message(item) for item in preview.alternatives],
        )


def register_role_resolver_service(server, service: RoleResolverService | None = None) -> bool:
    if not _HAS_STUBS:
        return False
    role_resolver_pb2_grpc.add_RoleResolverServiceServicer_to_server(
        RoleResolverServicer(service), server
    )
    return True


def _model_choice_message(choice):
    return _message(
        "ModelChoice",
        model_id=choice.model_id,
        reason=choice.reason,
        is_local_fallback=choice.is_local_fallback,
        confidence=choice.confidence,
        estimated_cost_usd=choice.estimated_cost_usd,
    )


def _message(name: str, **fields):
    if _HAS_STUBS and hasattr(role_resolver_pb2, name):
        return getattr(role_resolver_pb2, name)(**fields)
    return SimpleNamespace(**fields)
