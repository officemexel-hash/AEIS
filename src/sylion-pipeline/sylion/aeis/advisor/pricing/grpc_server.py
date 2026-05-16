"""gRPC wrapper for the pricing service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

from sylion.aeis.advisor.pricing import get_pricing
from sylion.aeis.advisor.pricing._models import CostEstimate, Model, PricingSnapshot, Provider, Source
from sylion.aeis.advisor.pricing.service import PricingService

try:
    from sylion.aeis.advisor._generated import pricing_pb2, pricing_pb2_grpc
    _HAS_STUBS = True
except ImportError:
    pricing_pb2 = None
    pricing_pb2_grpc = None
    _HAS_STUBS = False

log = logging.getLogger("sylion.aeis.advisor.pricing.grpc_server")


if _HAS_STUBS:
    class PricingServicer(pricing_pb2_grpc.PricingServiceServicer):
        """Pricing gRPC servicer."""

        def __init__(self, service: PricingService | None = None):
            self._service = service or get_pricing()

        def GetCost(self, request, context):
            estimate = self._service.get_cost(
                model_id=request.model_id,
                input_tokens=request.input_tokens,
                output_tokens=request.output_tokens,
                cache_hit_tokens=request.cache_hit_tokens,
            )
            return _cost_estimate_message(estimate)

        def RefreshPricing(self, request, context):
            result = self._service.refresh_pricing(request.provider_id, force=request.force)
            return pricing_pb2.RefreshPricingResponse(**result)

        def ListProviders(self, request, context):
            providers = self._service.list_providers(active_only=request.active_only)
            return pricing_pb2.ListProvidersResponse(
                providers=[_provider_message(item) for item in providers]
            )

        def ListModels(self, request, context):
            models = self._service.list_models(
                provider_id=request.provider_id or None,
                include_deprecated=request.include_deprecated,
            )
            return pricing_pb2.ListModelsResponse(models=[_model_message(item) for item in models])

        def RegisterAdapter(self, request, context):
            success, error = self._service.register_adapter(
                provider_id=request.provider_id,
                display_name=request.display_name,
                is_local=request.is_local,
                metadata_url=request.metadata_url,
                adapter_class_path=request.adapter_class_path,
            )
            return pricing_pb2.RegisterAdapterResponse(success=success, error_message=error)

        def GetPricingHistory(self, request, context):
            since = _timestamp_to_datetime(request.since) if request.HasField("since") else None
            snapshots = self._service.get_pricing_history(
                model_id=request.model_id,
                since=since,
                limit=request.limit or 50,
            )
            return pricing_pb2.GetPricingHistoryResponse(
                snapshots=[_pricing_snapshot_message(item) for item in snapshots]
            )

        def GetProvider(self, request, context):
            provider = self._service.get_provider(request.provider_id)
            if provider is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Provider {request.provider_id} not found")
                return pricing_pb2.Provider()
            return _provider_message(provider)

        def GetModel(self, request, context):
            model = self._service.get_model(request.model_id)
            if model is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Model {request.model_id} not found")
                return pricing_pb2.Model()
            return _model_message(model)


    def register_pricing_service(server, service: PricingService | None = None) -> bool:
        """Register the pricing gRPC service if stubs are available."""
        pricing_pb2_grpc.add_PricingServiceServicer_to_server(PricingServicer(service), server)
        return True
else:
    class PricingServicer:
        """Fallback placeholder when stubs are unavailable."""

        def __init__(self, service: PricingService | None = None):
            self._service = service or get_pricing()


    def register_pricing_service(server, service: PricingService | None = None) -> bool:
        """No-op registration when stubs are unavailable."""
        _ = server, service
        return False


def _provider_message(provider: Provider):
    return pricing_pb2.Provider(
        provider_id=provider.provider_id,
        display_name=provider.display_name,
        is_local=provider.is_local,
        is_active=provider.is_active,
        metadata_url=provider.metadata_url or "",
    )


def _model_message(model: Model):
    sample_estimate = get_pricing().get_cost(model.model_id, 1000, 1000, 0)
    return pricing_pb2.Model(
        model_id=model.model_id,
        provider_id=model.provider_id,
        display_name=model.display_name,
        context_window=model.context_window or 0,
        is_local=model.is_local,
        capabilities=model.capabilities,
        is_default_judge=model.is_default_judge,
        is_default_local=model.is_default_local,
        is_deprecated=model.is_deprecated,
        sample_cost_per_1k=_cost_estimate_message(sample_estimate),
    )


def _cost_estimate_message(estimate: CostEstimate):
    return pricing_pb2.CostEstimate(
        model_id=estimate.model_id,
        provider_id=estimate.provider_id,
        total_cost_usd=str(estimate.total_cost_usd),
        input_cost_usd=str(estimate.input_cost_usd),
        output_cost_usd=str(estimate.output_cost_usd),
        cache_cost_usd=str(estimate.cache_cost_usd),
        source=_source_enum(estimate.source),
        is_assumption=estimate.is_assumption,
        assumption_note=estimate.assumption_note or "",
        pricing_effective_from=_datetime_to_timestamp(estimate.pricing_effective_from),
        pricing_id=estimate.pricing_id,
    )


def _pricing_snapshot_message(snapshot: PricingSnapshot):
    return pricing_pb2.PricingSnapshot(
        history_id=snapshot.history_id,
        model_id=snapshot.model_id,
        fetched_at=_datetime_to_timestamp(snapshot.fetched_at),
        source=_source_enum(snapshot.source),
        is_assumption=snapshot.is_assumption,
        error_message=snapshot.error_message or "",
    )


def _source_enum(source: Source) -> int:
    mapping = {
        Source.ASSUMPTION: pricing_pb2.SOURCE_ASSUMPTION,
        Source.PROFILE: pricing_pb2.SOURCE_PROFILE,
        Source.MEASURED: pricing_pb2.SOURCE_MEASURED,
    }
    return mapping[source]


def _datetime_to_timestamp(value: datetime) -> Timestamp:
    timestamp = Timestamp()
    timestamp.FromDatetime(value.astimezone(timezone.utc))
    return timestamp


def _timestamp_to_datetime(value: Timestamp) -> datetime:
    return value.ToDatetime().astimezone(timezone.utc)
