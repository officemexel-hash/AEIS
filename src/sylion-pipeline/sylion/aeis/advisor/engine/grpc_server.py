"""gRPC facade for the advisor engine service."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

from sylion.aeis.advisor.actions.service import get_actions_service
from sylion.aeis.advisor.engine.service import AdvisorEngineService, get_engine_service

log = logging.getLogger("sylion.aeis.advisor.engine.grpc_server")

try:
    from sylion.aeis.advisor._generated import engine_pb2, engine_pb2_grpc
    _HAS_STUBS = True
except ImportError:
    engine_pb2 = None
    engine_pb2_grpc = None
    _HAS_STUBS = False


_BaseServicer = engine_pb2_grpc.EngineServiceServicer if _HAS_STUBS else object


class EngineServicer(_BaseServicer):
    """Thin RPC bridge to the in-process engine service."""

    def __init__(self, service: AdvisorEngineService | None = None) -> None:
        self._service = service or get_engine_service()
        self._actions = get_actions_service()

    def ListRecommendations(self, request, context=None):
        items = self._service.list_recommendations(
            operator_id=getattr(request, "operator_id", ""),
            limit=getattr(request, "limit", 50) or 50,
        )
        return _message(
            "ListRecommendationsResponse",
            recommendations=[_card_message(item) for item in items],
        )

    def GetCard(self, request, context=None):
        card = self._service.get_recommendation(card_id=getattr(request, "card_id", ""))
        if card is None:
            _set_not_found(context, f"Card {getattr(request, 'card_id', '')} not found")
            return _message("GetCardResponse", card=_card_message({}))
        return _message("GetCardResponse", card=_card_message(card))

    def RecordAction(self, request, context=None):
        result = self._actions.HandleAction(
            SimpleNamespace(
                card_id=getattr(request, "card_id", ""),
                action=getattr(request, "action", "accept"),
                operator_id=getattr(request, "operator_id", ""),
                operator_note=getattr(request, "operator_note", ""),
                modified_recommendation=getattr(request, "modified_recommendation", ""),
                preference_key=getattr(request, "preference_key", ""),
                preference_project_type=getattr(request, "preference_project_type", ""),
                preference_project_domain=getattr(request, "preference_project_domain", ""),
                preference_value=getattr(request, "preference_value", None),
                dont_learn_flag=getattr(request, "dont_learn_flag", False),
            ),
            context,
        )
        return _message(
            "RecordActionResponse",
            action_event_id=result.action_event_id,
            soft_learning_triggered=result.soft_learning_triggered,
            hard_learning_pending_confirmation=result.hard_learning_pending_confirmation,
            created_human_gate_ticket_id=result.created_human_gate_ticket_id,
            created_masterplan_proposal_id=result.created_masterplan_proposal_id,
            saved_preference_id=result.saved_preference_id,
            error_message=result.error_message,
            recorded_at=getattr(result, "recorded_at", None),
        )

    def FinalizeEvidence(self, request, context=None):
        pack_id = getattr(request, "evidence_pack_id", "") or getattr(request, "pack_id", "")
        ok = self._service.finalize_evidence_pack(pack_id=pack_id)
        return _message(
            "FinalizeEvidenceResponse",
            ok=ok,
            error_message="" if ok else "evidence_pack_not_found",
        )


def register_engine_service(server, service: AdvisorEngineService | None = None) -> bool:
    if not _HAS_STUBS:
        return False
    engine_pb2_grpc.add_EngineServiceServicer_to_server(EngineServicer(service), server)
    return True


def serve(host: str = "127.0.0.1", port: int = 50051) -> None:
    """Run the engine gRPC server when generated stubs are present."""
    if not _HAS_STUBS:
        log.warning(
            "engine grpc_server.serve() cannot start because engine_pb2 stubs are unavailable; "
            "use get_engine_service() in-process for now"
        )
        get_engine_service()
        return

    import grpc
    from concurrent import futures

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    register_engine_service(server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    server.wait_for_termination()


def get_service():
    return get_engine_service()


def _message(name: str, **fields: Any):
    if _HAS_STUBS and hasattr(engine_pb2, name):
        return getattr(engine_pb2, name)(**fields)
    return SimpleNamespace(**fields)


def _card_message(card: dict[str, Any]):
    return SimpleNamespace(**card)


def _set_not_found(context: Any, details: str) -> None:
    if context is None:
        return
    try:
        import grpc

        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details(details)
    except Exception:
        return
