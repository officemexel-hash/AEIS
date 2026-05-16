import datetime

from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CardAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CARD_ACTION_UNSPECIFIED: _ClassVar[CardAction]
    CARD_ACTION_ACCEPT: _ClassVar[CardAction]
    CARD_ACTION_REJECT: _ClassVar[CardAction]
    CARD_ACTION_MODIFY: _ClassVar[CardAction]
    CARD_ACTION_REMIND_LATER: _ClassVar[CardAction]
    CARD_ACTION_NOT_USEFUL: _ClassVar[CardAction]
    CARD_ACTION_CONVERT_TO_HUMAN_GATE: _ClassVar[CardAction]
    CARD_ACTION_CONVERT_TO_MASTERPLAN_CHANGE: _ClassVar[CardAction]
    CARD_ACTION_SAVE_AS_PREFERENCE: _ClassVar[CardAction]
    CARD_ACTION_DONT_LEARN_FROM_THIS: _ClassVar[CardAction]
CARD_ACTION_UNSPECIFIED: CardAction
CARD_ACTION_ACCEPT: CardAction
CARD_ACTION_REJECT: CardAction
CARD_ACTION_MODIFY: CardAction
CARD_ACTION_REMIND_LATER: CardAction
CARD_ACTION_NOT_USEFUL: CardAction
CARD_ACTION_CONVERT_TO_HUMAN_GATE: CardAction
CARD_ACTION_CONVERT_TO_MASTERPLAN_CHANGE: CardAction
CARD_ACTION_SAVE_AS_PREFERENCE: CardAction
CARD_ACTION_DONT_LEARN_FROM_THIS: CardAction

class HandleActionRequest(_message.Message):
    __slots__ = ("card_id", "action", "operator_id", "operator_note", "modified_recommendation", "preference_key", "preference_project_type", "preference_project_domain", "preference_value", "dont_learn_flag")
    CARD_ID_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    OPERATOR_ID_FIELD_NUMBER: _ClassVar[int]
    OPERATOR_NOTE_FIELD_NUMBER: _ClassVar[int]
    MODIFIED_RECOMMENDATION_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_KEY_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_PROJECT_TYPE_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_PROJECT_DOMAIN_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_VALUE_FIELD_NUMBER: _ClassVar[int]
    DONT_LEARN_FLAG_FIELD_NUMBER: _ClassVar[int]
    card_id: str
    action: CardAction
    operator_id: str
    operator_note: str
    modified_recommendation: str
    preference_key: str
    preference_project_type: str
    preference_project_domain: str
    preference_value: _struct_pb2.Value
    dont_learn_flag: bool
    def __init__(self, card_id: _Optional[str] = ..., action: _Optional[_Union[CardAction, str]] = ..., operator_id: _Optional[str] = ..., operator_note: _Optional[str] = ..., modified_recommendation: _Optional[str] = ..., preference_key: _Optional[str] = ..., preference_project_type: _Optional[str] = ..., preference_project_domain: _Optional[str] = ..., preference_value: _Optional[_Union[_struct_pb2.Value, _Mapping]] = ..., dont_learn_flag: bool = ...) -> None: ...

class HandleActionResponse(_message.Message):
    __slots__ = ("action_event_id", "recorded_at", "soft_learning_triggered", "hard_learning_pending_confirmation", "created_human_gate_ticket_id", "created_masterplan_proposal_id", "saved_preference_id", "error_message")
    ACTION_EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    RECORDED_AT_FIELD_NUMBER: _ClassVar[int]
    SOFT_LEARNING_TRIGGERED_FIELD_NUMBER: _ClassVar[int]
    HARD_LEARNING_PENDING_CONFIRMATION_FIELD_NUMBER: _ClassVar[int]
    CREATED_HUMAN_GATE_TICKET_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_MASTERPLAN_PROPOSAL_ID_FIELD_NUMBER: _ClassVar[int]
    SAVED_PREFERENCE_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    action_event_id: str
    recorded_at: _timestamp_pb2.Timestamp
    soft_learning_triggered: bool
    hard_learning_pending_confirmation: bool
    created_human_gate_ticket_id: str
    created_masterplan_proposal_id: str
    saved_preference_id: str
    error_message: str
    def __init__(self, action_event_id: _Optional[str] = ..., recorded_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., soft_learning_triggered: bool = ..., hard_learning_pending_confirmation: bool = ..., created_human_gate_ticket_id: _Optional[str] = ..., created_masterplan_proposal_id: _Optional[str] = ..., saved_preference_id: _Optional[str] = ..., error_message: _Optional[str] = ...) -> None: ...

class RetryFailedRequest(_message.Message):
    __slots__ = ("route_audit_id",)
    ROUTE_AUDIT_ID_FIELD_NUMBER: _ClassVar[int]
    route_audit_id: str
    def __init__(self, route_audit_id: _Optional[str] = ...) -> None: ...

class RetryFailedResponse(_message.Message):
    __slots__ = ("success", "status", "error_message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    status: str
    error_message: str
    def __init__(self, success: bool = ..., status: _Optional[str] = ..., error_message: _Optional[str] = ...) -> None: ...

class GetRoutingAuditRequest(_message.Message):
    __slots__ = ("card_id",)
    CARD_ID_FIELD_NUMBER: _ClassVar[int]
    card_id: str
    def __init__(self, card_id: _Optional[str] = ...) -> None: ...

class GetRoutingAuditResponse(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[RouteAuditEntry]
    def __init__(self, entries: _Optional[_Iterable[_Union[RouteAuditEntry, _Mapping]]] = ...) -> None: ...

class RouteAuditEntry(_message.Message):
    __slots__ = ("route_audit_id", "card_id", "action", "routed_to_module", "routed_target_id", "payload_sent", "response", "status", "error_message", "routed_at")
    ROUTE_AUDIT_ID_FIELD_NUMBER: _ClassVar[int]
    CARD_ID_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    ROUTED_TO_MODULE_FIELD_NUMBER: _ClassVar[int]
    ROUTED_TARGET_ID_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_SENT_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ROUTED_AT_FIELD_NUMBER: _ClassVar[int]
    route_audit_id: str
    card_id: str
    action: CardAction
    routed_to_module: str
    routed_target_id: str
    payload_sent: _struct_pb2.Value
    response: _struct_pb2.Value
    status: str
    error_message: str
    routed_at: _timestamp_pb2.Timestamp
    def __init__(self, route_audit_id: _Optional[str] = ..., card_id: _Optional[str] = ..., action: _Optional[_Union[CardAction, str]] = ..., routed_to_module: _Optional[str] = ..., routed_target_id: _Optional[str] = ..., payload_sent: _Optional[_Union[_struct_pb2.Value, _Mapping]] = ..., response: _Optional[_Union[_struct_pb2.Value, _Mapping]] = ..., status: _Optional[str] = ..., error_message: _Optional[str] = ..., routed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
