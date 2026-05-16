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

class ResolutionLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RESOLUTION_LEVEL_UNSPECIFIED: _ClassVar[ResolutionLevel]
    RESOLUTION_LEVEL_SPECIFIC: _ClassVar[ResolutionLevel]
    RESOLUTION_LEVEL_TYPE_ONLY: _ClassVar[ResolutionLevel]
    RESOLUTION_LEVEL_DOMAIN_ONLY: _ClassVar[ResolutionLevel]
    RESOLUTION_LEVEL_USER_DEFAULT: _ClassVar[ResolutionLevel]
    RESOLUTION_LEVEL_SYSTEM_DEFAULT: _ClassVar[ResolutionLevel]

class CatalogType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CATALOG_TYPE_UNSPECIFIED: _ClassVar[CatalogType]
    CATALOG_TYPE_PROJECT_DOMAIN: _ClassVar[CatalogType]
    CATALOG_TYPE_PROJECT_TYPE: _ClassVar[CatalogType]
    CATALOG_TYPE_PREFERENCE_KEY: _ClassVar[CatalogType]
RESOLUTION_LEVEL_UNSPECIFIED: ResolutionLevel
RESOLUTION_LEVEL_SPECIFIC: ResolutionLevel
RESOLUTION_LEVEL_TYPE_ONLY: ResolutionLevel
RESOLUTION_LEVEL_DOMAIN_ONLY: ResolutionLevel
RESOLUTION_LEVEL_USER_DEFAULT: ResolutionLevel
RESOLUTION_LEVEL_SYSTEM_DEFAULT: ResolutionLevel
CATALOG_TYPE_UNSPECIFIED: CatalogType
CATALOG_TYPE_PROJECT_DOMAIN: CatalogType
CATALOG_TYPE_PROJECT_TYPE: CatalogType
CATALOG_TYPE_PREFERENCE_KEY: CatalogType

class PreferenceValue(_message.Message):
    __slots__ = ("user_id", "project_type", "project_domain", "preference_key", "value_json", "set_by", "created_at", "updated_at", "resolution_level")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PROJECT_TYPE_FIELD_NUMBER: _ClassVar[int]
    PROJECT_DOMAIN_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_JSON_FIELD_NUMBER: _ClassVar[int]
    SET_BY_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    RESOLUTION_LEVEL_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    project_type: str
    project_domain: str
    preference_key: str
    value_json: _struct_pb2.Value
    set_by: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    resolution_level: ResolutionLevel
    def __init__(self, user_id: _Optional[str] = ..., project_type: _Optional[str] = ..., project_domain: _Optional[str] = ..., preference_key: _Optional[str] = ..., value_json: _Optional[_Union[_struct_pb2.Value, _Mapping]] = ..., set_by: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., resolution_level: _Optional[_Union[ResolutionLevel, str]] = ...) -> None: ...

class GetEffectiveRequest(_message.Message):
    __slots__ = ("user_id", "project_type", "project_domain", "preference_key")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PROJECT_TYPE_FIELD_NUMBER: _ClassVar[int]
    PROJECT_DOMAIN_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_KEY_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    project_type: str
    project_domain: str
    preference_key: str
    def __init__(self, user_id: _Optional[str] = ..., project_type: _Optional[str] = ..., project_domain: _Optional[str] = ..., preference_key: _Optional[str] = ...) -> None: ...

class GetExplicitRequest(_message.Message):
    __slots__ = ("user_id", "project_type", "project_domain", "preference_key")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PROJECT_TYPE_FIELD_NUMBER: _ClassVar[int]
    PROJECT_DOMAIN_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_KEY_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    project_type: str
    project_domain: str
    preference_key: str
    def __init__(self, user_id: _Optional[str] = ..., project_type: _Optional[str] = ..., project_domain: _Optional[str] = ..., preference_key: _Optional[str] = ...) -> None: ...

class SetRequest(_message.Message):
    __slots__ = ("user_id", "project_type", "project_domain", "preference_key", "value_json", "set_by", "reason")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PROJECT_TYPE_FIELD_NUMBER: _ClassVar[int]
    PROJECT_DOMAIN_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_JSON_FIELD_NUMBER: _ClassVar[int]
    SET_BY_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    project_type: str
    project_domain: str
    preference_key: str
    value_json: _struct_pb2.Value
    set_by: str
    reason: str
    def __init__(self, user_id: _Optional[str] = ..., project_type: _Optional[str] = ..., project_domain: _Optional[str] = ..., preference_key: _Optional[str] = ..., value_json: _Optional[_Union[_struct_pb2.Value, _Mapping]] = ..., set_by: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class SetResponse(_message.Message):
    __slots__ = ("success", "requires_hard_confirmation", "hard_change_request_id", "error_message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    REQUIRES_HARD_CONFIRMATION_FIELD_NUMBER: _ClassVar[int]
    HARD_CHANGE_REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    requires_hard_confirmation: bool
    hard_change_request_id: str
    error_message: str
    def __init__(self, success: bool = ..., requires_hard_confirmation: bool = ..., hard_change_request_id: _Optional[str] = ..., error_message: _Optional[str] = ...) -> None: ...

class ResetRequest(_message.Message):
    __slots__ = ("user_id", "project_type", "project_domain", "preference_key", "reason")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PROJECT_TYPE_FIELD_NUMBER: _ClassVar[int]
    PROJECT_DOMAIN_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_KEY_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    project_type: str
    project_domain: str
    preference_key: str
    reason: str
    def __init__(self, user_id: _Optional[str] = ..., project_type: _Optional[str] = ..., project_domain: _Optional[str] = ..., preference_key: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class ResetResponse(_message.Message):
    __slots__ = ("success", "error_message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    error_message: str
    def __init__(self, success: bool = ..., error_message: _Optional[str] = ...) -> None: ...

class DisableRequest(_message.Message):
    __slots__ = ("user_id", "preference_key", "reason")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_KEY_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    preference_key: str
    reason: str
    def __init__(self, user_id: _Optional[str] = ..., preference_key: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class DisableResponse(_message.Message):
    __slots__ = ("success", "levels_cleared")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    LEVELS_CLEARED_FIELD_NUMBER: _ClassVar[int]
    success: bool
    levels_cleared: int
    def __init__(self, success: bool = ..., levels_cleared: _Optional[int] = ...) -> None: ...

class ListRequest(_message.Message):
    __slots__ = ("user_id", "filter_project_type", "filter_project_domain", "filter_preference_key")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    FILTER_PROJECT_TYPE_FIELD_NUMBER: _ClassVar[int]
    FILTER_PROJECT_DOMAIN_FIELD_NUMBER: _ClassVar[int]
    FILTER_PREFERENCE_KEY_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    filter_project_type: str
    filter_project_domain: str
    filter_preference_key: str
    def __init__(self, user_id: _Optional[str] = ..., filter_project_type: _Optional[str] = ..., filter_project_domain: _Optional[str] = ..., filter_preference_key: _Optional[str] = ...) -> None: ...

class ListResponse(_message.Message):
    __slots__ = ("preferences",)
    PREFERENCES_FIELD_NUMBER: _ClassVar[int]
    preferences: _containers.RepeatedCompositeFieldContainer[PreferenceValue]
    def __init__(self, preferences: _Optional[_Iterable[_Union[PreferenceValue, _Mapping]]] = ...) -> None: ...

class GetAuditRequest(_message.Message):
    __slots__ = ("user_id", "since", "limit", "filter_preference_key")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SINCE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    FILTER_PREFERENCE_KEY_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    since: _timestamp_pb2.Timestamp
    limit: int
    filter_preference_key: str
    def __init__(self, user_id: _Optional[str] = ..., since: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., limit: _Optional[int] = ..., filter_preference_key: _Optional[str] = ...) -> None: ...

class GetAuditResponse(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[AuditEntry]
    def __init__(self, entries: _Optional[_Iterable[_Union[AuditEntry, _Mapping]]] = ...) -> None: ...

class AuditEntry(_message.Message):
    __slots__ = ("audit_id", "user_id", "project_type", "project_domain", "preference_key", "old_value", "new_value", "change_type", "changed_by", "changed_at", "reason")
    AUDIT_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PROJECT_TYPE_FIELD_NUMBER: _ClassVar[int]
    PROJECT_DOMAIN_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_KEY_FIELD_NUMBER: _ClassVar[int]
    OLD_VALUE_FIELD_NUMBER: _ClassVar[int]
    NEW_VALUE_FIELD_NUMBER: _ClassVar[int]
    CHANGE_TYPE_FIELD_NUMBER: _ClassVar[int]
    CHANGED_BY_FIELD_NUMBER: _ClassVar[int]
    CHANGED_AT_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    audit_id: str
    user_id: str
    project_type: str
    project_domain: str
    preference_key: str
    old_value: _struct_pb2.Value
    new_value: _struct_pb2.Value
    change_type: str
    changed_by: str
    changed_at: _timestamp_pb2.Timestamp
    reason: str
    def __init__(self, audit_id: _Optional[str] = ..., user_id: _Optional[str] = ..., project_type: _Optional[str] = ..., project_domain: _Optional[str] = ..., preference_key: _Optional[str] = ..., old_value: _Optional[_Union[_struct_pb2.Value, _Mapping]] = ..., new_value: _Optional[_Union[_struct_pb2.Value, _Mapping]] = ..., change_type: _Optional[str] = ..., changed_by: _Optional[str] = ..., changed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., reason: _Optional[str] = ...) -> None: ...

class SoftLearningTickRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class SoftLearningTickResponse(_message.Message):
    __slots__ = ("applied_count", "pending_hard_confirmations", "applied_preference_keys")
    APPLIED_COUNT_FIELD_NUMBER: _ClassVar[int]
    PENDING_HARD_CONFIRMATIONS_FIELD_NUMBER: _ClassVar[int]
    APPLIED_PREFERENCE_KEYS_FIELD_NUMBER: _ClassVar[int]
    applied_count: int
    pending_hard_confirmations: int
    applied_preference_keys: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, applied_count: _Optional[int] = ..., pending_hard_confirmations: _Optional[int] = ..., applied_preference_keys: _Optional[_Iterable[str]] = ...) -> None: ...

class RequestHardChangeRequest(_message.Message):
    __slots__ = ("user_id", "project_type", "project_domain", "preference_key", "proposed_value", "source_card_id", "rationale")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PROJECT_TYPE_FIELD_NUMBER: _ClassVar[int]
    PROJECT_DOMAIN_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_KEY_FIELD_NUMBER: _ClassVar[int]
    PROPOSED_VALUE_FIELD_NUMBER: _ClassVar[int]
    SOURCE_CARD_ID_FIELD_NUMBER: _ClassVar[int]
    RATIONALE_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    project_type: str
    project_domain: str
    preference_key: str
    proposed_value: _struct_pb2.Value
    source_card_id: str
    rationale: str
    def __init__(self, user_id: _Optional[str] = ..., project_type: _Optional[str] = ..., project_domain: _Optional[str] = ..., preference_key: _Optional[str] = ..., proposed_value: _Optional[_Union[_struct_pb2.Value, _Mapping]] = ..., source_card_id: _Optional[str] = ..., rationale: _Optional[str] = ...) -> None: ...

class RequestHardChangeResponse(_message.Message):
    __slots__ = ("request_id", "expires_at")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, request_id: _Optional[str] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ConfirmHardChangeRequest(_message.Message):
    __slots__ = ("request_id", "operator_signature", "confirmed")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    OPERATOR_SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    CONFIRMED_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    operator_signature: str
    confirmed: bool
    def __init__(self, request_id: _Optional[str] = ..., operator_signature: _Optional[str] = ..., confirmed: bool = ...) -> None: ...

class ConfirmHardChangeResponse(_message.Message):
    __slots__ = ("success", "error_message", "applied_value")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    APPLIED_VALUE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    error_message: str
    applied_value: PreferenceValue
    def __init__(self, success: bool = ..., error_message: _Optional[str] = ..., applied_value: _Optional[_Union[PreferenceValue, _Mapping]] = ...) -> None: ...

class GetCatalogRequest(_message.Message):
    __slots__ = ("catalog_type", "include_custom")
    CATALOG_TYPE_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_CUSTOM_FIELD_NUMBER: _ClassVar[int]
    catalog_type: CatalogType
    include_custom: bool
    def __init__(self, catalog_type: _Optional[_Union[CatalogType, str]] = ..., include_custom: bool = ...) -> None: ...

class GetCatalogResponse(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[CatalogEntry]
    def __init__(self, entries: _Optional[_Iterable[_Union[CatalogEntry, _Mapping]]] = ...) -> None: ...

class CatalogEntry(_message.Message):
    __slots__ = ("entry_id", "display_name", "description", "is_system", "is_immutable", "metadata_json")
    ENTRY_ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    IS_SYSTEM_FIELD_NUMBER: _ClassVar[int]
    IS_IMMUTABLE_FIELD_NUMBER: _ClassVar[int]
    METADATA_JSON_FIELD_NUMBER: _ClassVar[int]
    entry_id: str
    display_name: str
    description: str
    is_system: bool
    is_immutable: bool
    metadata_json: _struct_pb2.Struct
    def __init__(self, entry_id: _Optional[str] = ..., display_name: _Optional[str] = ..., description: _Optional[str] = ..., is_system: bool = ..., is_immutable: bool = ..., metadata_json: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class AddCustomCatalogEntryRequest(_message.Message):
    __slots__ = ("catalog_type", "entry_id", "display_name", "description", "created_by")
    CATALOG_TYPE_FIELD_NUMBER: _ClassVar[int]
    ENTRY_ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CREATED_BY_FIELD_NUMBER: _ClassVar[int]
    catalog_type: CatalogType
    entry_id: str
    display_name: str
    description: str
    created_by: str
    def __init__(self, catalog_type: _Optional[_Union[CatalogType, str]] = ..., entry_id: _Optional[str] = ..., display_name: _Optional[str] = ..., description: _Optional[str] = ..., created_by: _Optional[str] = ...) -> None: ...

class AddCustomCatalogEntryResponse(_message.Message):
    __slots__ = ("success", "error_message", "entry")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ENTRY_FIELD_NUMBER: _ClassVar[int]
    success: bool
    error_message: str
    entry: CatalogEntry
    def __init__(self, success: bool = ..., error_message: _Optional[str] = ..., entry: _Optional[_Union[CatalogEntry, _Mapping]] = ...) -> None: ...
