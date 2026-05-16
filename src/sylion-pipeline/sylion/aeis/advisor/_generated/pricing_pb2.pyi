import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Source(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SOURCE_UNSPECIFIED: _ClassVar[Source]
    SOURCE_ASSUMPTION: _ClassVar[Source]
    SOURCE_PROFILE: _ClassVar[Source]
    SOURCE_MEASURED: _ClassVar[Source]
SOURCE_UNSPECIFIED: Source
SOURCE_ASSUMPTION: Source
SOURCE_PROFILE: Source
SOURCE_MEASURED: Source

class GetCostRequest(_message.Message):
    __slots__ = ("model_id", "input_tokens", "output_tokens", "cache_hit_tokens")
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    INPUT_TOKENS_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_TOKENS_FIELD_NUMBER: _ClassVar[int]
    CACHE_HIT_TOKENS_FIELD_NUMBER: _ClassVar[int]
    model_id: str
    input_tokens: int
    output_tokens: int
    cache_hit_tokens: int
    def __init__(self, model_id: _Optional[str] = ..., input_tokens: _Optional[int] = ..., output_tokens: _Optional[int] = ..., cache_hit_tokens: _Optional[int] = ...) -> None: ...

class CostEstimate(_message.Message):
    __slots__ = ("model_id", "provider_id", "total_cost_usd", "input_cost_usd", "output_cost_usd", "cache_cost_usd", "source", "is_assumption", "assumption_note", "pricing_effective_from", "pricing_id")
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_ID_FIELD_NUMBER: _ClassVar[int]
    TOTAL_COST_USD_FIELD_NUMBER: _ClassVar[int]
    INPUT_COST_USD_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_COST_USD_FIELD_NUMBER: _ClassVar[int]
    CACHE_COST_USD_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    IS_ASSUMPTION_FIELD_NUMBER: _ClassVar[int]
    ASSUMPTION_NOTE_FIELD_NUMBER: _ClassVar[int]
    PRICING_EFFECTIVE_FROM_FIELD_NUMBER: _ClassVar[int]
    PRICING_ID_FIELD_NUMBER: _ClassVar[int]
    model_id: str
    provider_id: str
    total_cost_usd: str
    input_cost_usd: str
    output_cost_usd: str
    cache_cost_usd: str
    source: Source
    is_assumption: bool
    assumption_note: str
    pricing_effective_from: _timestamp_pb2.Timestamp
    pricing_id: str
    def __init__(self, model_id: _Optional[str] = ..., provider_id: _Optional[str] = ..., total_cost_usd: _Optional[str] = ..., input_cost_usd: _Optional[str] = ..., output_cost_usd: _Optional[str] = ..., cache_cost_usd: _Optional[str] = ..., source: _Optional[_Union[Source, str]] = ..., is_assumption: bool = ..., assumption_note: _Optional[str] = ..., pricing_effective_from: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., pricing_id: _Optional[str] = ...) -> None: ...

class RefreshPricingRequest(_message.Message):
    __slots__ = ("provider_id", "force")
    PROVIDER_ID_FIELD_NUMBER: _ClassVar[int]
    FORCE_FIELD_NUMBER: _ClassVar[int]
    provider_id: str
    force: bool
    def __init__(self, provider_id: _Optional[str] = ..., force: bool = ...) -> None: ...

class RefreshPricingResponse(_message.Message):
    __slots__ = ("refreshed_count", "failed_count", "used_live", "assumption_fallback")
    REFRESHED_COUNT_FIELD_NUMBER: _ClassVar[int]
    FAILED_COUNT_FIELD_NUMBER: _ClassVar[int]
    USED_LIVE_FIELD_NUMBER: _ClassVar[int]
    ASSUMPTION_FALLBACK_FIELD_NUMBER: _ClassVar[int]
    refreshed_count: int
    failed_count: int
    used_live: bool
    assumption_fallback: bool
    def __init__(self, refreshed_count: _Optional[int] = ..., failed_count: _Optional[int] = ..., used_live: bool = ..., assumption_fallback: bool = ...) -> None: ...

class ListProvidersRequest(_message.Message):
    __slots__ = ("active_only",)
    ACTIVE_ONLY_FIELD_NUMBER: _ClassVar[int]
    active_only: bool
    def __init__(self, active_only: bool = ...) -> None: ...

class ListProvidersResponse(_message.Message):
    __slots__ = ("providers",)
    PROVIDERS_FIELD_NUMBER: _ClassVar[int]
    providers: _containers.RepeatedCompositeFieldContainer[Provider]
    def __init__(self, providers: _Optional[_Iterable[_Union[Provider, _Mapping]]] = ...) -> None: ...

class Provider(_message.Message):
    __slots__ = ("provider_id", "display_name", "is_local", "is_active", "metadata_url")
    PROVIDER_ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    IS_LOCAL_FIELD_NUMBER: _ClassVar[int]
    IS_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    METADATA_URL_FIELD_NUMBER: _ClassVar[int]
    provider_id: str
    display_name: str
    is_local: bool
    is_active: bool
    metadata_url: str
    def __init__(self, provider_id: _Optional[str] = ..., display_name: _Optional[str] = ..., is_local: bool = ..., is_active: bool = ..., metadata_url: _Optional[str] = ...) -> None: ...

class ListModelsRequest(_message.Message):
    __slots__ = ("provider_id", "include_deprecated")
    PROVIDER_ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_DEPRECATED_FIELD_NUMBER: _ClassVar[int]
    provider_id: str
    include_deprecated: bool
    def __init__(self, provider_id: _Optional[str] = ..., include_deprecated: bool = ...) -> None: ...

class ListModelsResponse(_message.Message):
    __slots__ = ("models",)
    MODELS_FIELD_NUMBER: _ClassVar[int]
    models: _containers.RepeatedCompositeFieldContainer[Model]
    def __init__(self, models: _Optional[_Iterable[_Union[Model, _Mapping]]] = ...) -> None: ...

class Model(_message.Message):
    __slots__ = ("model_id", "provider_id", "display_name", "context_window", "is_local", "capabilities", "is_default_judge", "is_default_local", "is_deprecated", "sample_cost_per_1k")
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_WINDOW_FIELD_NUMBER: _ClassVar[int]
    IS_LOCAL_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    IS_DEFAULT_JUDGE_FIELD_NUMBER: _ClassVar[int]
    IS_DEFAULT_LOCAL_FIELD_NUMBER: _ClassVar[int]
    IS_DEPRECATED_FIELD_NUMBER: _ClassVar[int]
    SAMPLE_COST_PER_1K_FIELD_NUMBER: _ClassVar[int]
    model_id: str
    provider_id: str
    display_name: str
    context_window: int
    is_local: bool
    capabilities: _containers.RepeatedScalarFieldContainer[str]
    is_default_judge: bool
    is_default_local: bool
    is_deprecated: bool
    sample_cost_per_1k: CostEstimate
    def __init__(self, model_id: _Optional[str] = ..., provider_id: _Optional[str] = ..., display_name: _Optional[str] = ..., context_window: _Optional[int] = ..., is_local: bool = ..., capabilities: _Optional[_Iterable[str]] = ..., is_default_judge: bool = ..., is_default_local: bool = ..., is_deprecated: bool = ..., sample_cost_per_1k: _Optional[_Union[CostEstimate, _Mapping]] = ...) -> None: ...

class RegisterAdapterRequest(_message.Message):
    __slots__ = ("provider_id", "display_name", "is_local", "metadata_url", "adapter_class_path")
    PROVIDER_ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    IS_LOCAL_FIELD_NUMBER: _ClassVar[int]
    METADATA_URL_FIELD_NUMBER: _ClassVar[int]
    ADAPTER_CLASS_PATH_FIELD_NUMBER: _ClassVar[int]
    provider_id: str
    display_name: str
    is_local: bool
    metadata_url: str
    adapter_class_path: str
    def __init__(self, provider_id: _Optional[str] = ..., display_name: _Optional[str] = ..., is_local: bool = ..., metadata_url: _Optional[str] = ..., adapter_class_path: _Optional[str] = ...) -> None: ...

class RegisterAdapterResponse(_message.Message):
    __slots__ = ("success", "error_message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    error_message: str
    def __init__(self, success: bool = ..., error_message: _Optional[str] = ...) -> None: ...

class GetPricingHistoryRequest(_message.Message):
    __slots__ = ("model_id", "since", "limit")
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    SINCE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    model_id: str
    since: _timestamp_pb2.Timestamp
    limit: int
    def __init__(self, model_id: _Optional[str] = ..., since: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., limit: _Optional[int] = ...) -> None: ...

class GetPricingHistoryResponse(_message.Message):
    __slots__ = ("snapshots",)
    SNAPSHOTS_FIELD_NUMBER: _ClassVar[int]
    snapshots: _containers.RepeatedCompositeFieldContainer[PricingSnapshot]
    def __init__(self, snapshots: _Optional[_Iterable[_Union[PricingSnapshot, _Mapping]]] = ...) -> None: ...

class PricingSnapshot(_message.Message):
    __slots__ = ("history_id", "model_id", "fetched_at", "source", "is_assumption", "error_message")
    HISTORY_ID_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    FETCHED_AT_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    IS_ASSUMPTION_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    history_id: str
    model_id: str
    fetched_at: _timestamp_pb2.Timestamp
    source: Source
    is_assumption: bool
    error_message: str
    def __init__(self, history_id: _Optional[str] = ..., model_id: _Optional[str] = ..., fetched_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., source: _Optional[_Union[Source, str]] = ..., is_assumption: bool = ..., error_message: _Optional[str] = ...) -> None: ...

class GetProviderRequest(_message.Message):
    __slots__ = ("provider_id",)
    PROVIDER_ID_FIELD_NUMBER: _ClassVar[int]
    provider_id: str
    def __init__(self, provider_id: _Optional[str] = ...) -> None: ...

class GetModelRequest(_message.Message):
    __slots__ = ("model_id",)
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    model_id: str
    def __init__(self, model_id: _Optional[str] = ...) -> None: ...
