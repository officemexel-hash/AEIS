"""gRPC facade for advisor actions."""
from __future__ import annotations

from datetime import timezone
from types import SimpleNamespace

from google.protobuf.json_format import ParseDict

from sylion.aeis.advisor.actions.service import get_actions_service
from sylion.aeis.advisor._generated import actions_pb2, actions_pb2_grpc


_PROTO_TO_ACTION = {
    actions_pb2.CARD_ACTION_ACCEPT: "accept",
    actions_pb2.CARD_ACTION_REJECT: "reject",
    actions_pb2.CARD_ACTION_MODIFY: "modify",
    actions_pb2.CARD_ACTION_REMIND_LATER: "remind_later",
    actions_pb2.CARD_ACTION_NOT_USEFUL: "not_useful",
    actions_pb2.CARD_ACTION_CONVERT_TO_HUMAN_GATE: "convert_to_human_gate",
    actions_pb2.CARD_ACTION_CONVERT_TO_MASTERPLAN_CHANGE: "convert_to_masterplan_change",
    actions_pb2.CARD_ACTION_SAVE_AS_PREFERENCE: "save_as_preference",
    actions_pb2.CARD_ACTION_DONT_LEARN_FROM_THIS: "dont_learn_from_this",
}


class ActionsServicer(actions_pb2_grpc.ActionsServiceServicer):
    """Generated gRPC surface for advisor actions."""

    def __init__(self, service=None) -> None:
        self._service = service or get_actions_service()

    def HandleAction(self, request, context):
        result = self._service.HandleAction(
            SimpleNamespace(
                card_id=request.card_id,
                action=_PROTO_TO_ACTION.get(request.action, "accept"),
                operator_id=request.operator_id,
                operator_note=request.operator_note,
                modified_recommendation=request.modified_recommendation,
                preference_key=request.preference_key,
                preference_project_type=request.preference_project_type,
                preference_project_domain=request.preference_project_domain,
                preference_value=_unwrap_value(request.preference_value),
                dont_learn_flag=request.dont_learn_flag,
            )
        )
        response = actions_pb2.HandleActionResponse(
            action_event_id=result.action_event_id,
            soft_learning_triggered=result.soft_learning_triggered,
            hard_learning_pending_confirmation=result.hard_learning_pending_confirmation,
            created_human_gate_ticket_id=result.created_human_gate_ticket_id,
            created_masterplan_proposal_id=result.created_masterplan_proposal_id,
            saved_preference_id=result.saved_preference_id,
            error_message=result.error_message,
        )
        response.recorded_at.FromDatetime(result.recorded_at.astimezone(timezone.utc))
        return response

    def RetryFailed(self, request, context):
        result = self._service.RetryFailed(request)
        return actions_pb2.RetryFailedResponse(
            success=result.success,
            status=result.status,
            error_message=result.error_message,
        )

    def GetRoutingAudit(self, request, context):
        result = self._service.GetRoutingAudit(request)
        response = actions_pb2.GetRoutingAuditResponse()
        for row in result.entries:
            item = response.entries.add()
            item.route_audit_id = row.route_audit_id
            item.card_id = row.card_id
            item.action = _action_to_proto(row.action.value)
            item.routed_to_module = row.routed_to_module
            item.routed_target_id = row.routed_target_id or ""
            ParseDict(row.payload_sent or {}, item.payload_sent)
            ParseDict(row.response or {}, item.response)
            item.status = row.status.value
            item.error_message = row.error_message or ""
            item.routed_at.FromDatetime(row.routed_at.astimezone(timezone.utc))
        return response


def register_actions_service(server, service=None) -> bool:
    """Register advisor actions on a gRPC server."""
    actions_pb2_grpc.add_ActionsServiceServicer_to_server(ActionsServicer(service), server)
    return True


def get_service():
    return get_actions_service()


def _unwrap_value(message):
    if not hasattr(message, "HasField"):
        return None
    if getattr(message, "null_value", None) == 0 and not message.ListFields():
        return None
    if message.HasField("string_value"):
        return message.string_value
    if message.HasField("number_value"):
        return message.number_value
    if message.HasField("bool_value"):
        return message.bool_value
    if message.HasField("struct_value"):
        return {}
    if message.HasField("list_value"):
        return []
    return None


def _action_to_proto(action: str) -> int:
    reverse = {
        "accept": actions_pb2.CARD_ACTION_ACCEPT,
        "reject": actions_pb2.CARD_ACTION_REJECT,
        "modify": actions_pb2.CARD_ACTION_MODIFY,
        "remind_later": actions_pb2.CARD_ACTION_REMIND_LATER,
        "not_useful": actions_pb2.CARD_ACTION_NOT_USEFUL,
        "convert_to_human_gate": actions_pb2.CARD_ACTION_CONVERT_TO_HUMAN_GATE,
        "convert_to_masterplan_change": actions_pb2.CARD_ACTION_CONVERT_TO_MASTERPLAN_CHANGE,
        "save_as_preference": actions_pb2.CARD_ACTION_SAVE_AS_PREFERENCE,
        "dont_learn_from_this": actions_pb2.CARD_ACTION_DONT_LEARN_FROM_THIS,
    }
    return reverse[action]
