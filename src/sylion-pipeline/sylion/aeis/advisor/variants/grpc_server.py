"""gRPC facade for the advisor variants service."""

from __future__ import annotations

from types import SimpleNamespace

from sylion.aeis.advisor.variants.service import VariantsService, get_variants_service

try:
    from sylion.aeis.advisor._generated import variants_pb2, variants_pb2_grpc
    _HAS_STUBS = True
except ImportError:
    variants_pb2 = None
    variants_pb2_grpc = None
    _HAS_STUBS = False


_BaseServicer = variants_pb2_grpc.VariantsServiceServicer if _HAS_STUBS else object


class VariantsServicer(_BaseServicer):
    """gRPC servicer for VariantsService."""

    def __init__(self, service: VariantsService | None = None):
        self._service = service or get_variants_service()

    def GenerateVariants(self, request, context):
        parameters = dict(getattr(request, "parameters", {}) or {})
        context_id = getattr(request, "context_id", "")
        if context_id:
            parameters.setdefault("context_id", context_id)
        result = self._service.generate_variants(parameters)
        return _message(
            "VariantSet",
            context_id=result.context_id,
            variants=[_variant_message(item) for item in result.variants],
            generated_at=result.generated_at,
        )

    def CompareVariants(self, request, context):
        result = self._service.compare_variants(
            variant_ids=list(getattr(request, "variant_ids", []) or []),
            context_id=getattr(request, "context_id", "") or None,
        )
        return _message(
            "ComparisonMatrix",
            variant_ids=list(result.get("variant_ids", [])),
            dimensions=[_dimension_message(item) for item in result.get("dimensions", [])],
        )


def register_variants_service(server, service: VariantsService | None = None) -> bool:
    if not _HAS_STUBS:
        return False
    variants_pb2_grpc.add_VariantsServiceServicer_to_server(VariantsServicer(service), server)
    return True


def _variant_message(item):
    return _message(
        "Variant",
        variant_id=item.variant_id,
        name=item.name,
        description=item.description,
        parameters={k: str(v) for k, v in item.parameters.items()},
        estimated_cost_usd=item.estimated_cost_usd,
        estimated_time_hours=item.estimated_time_hours,
        risk_level=item.risk_level,
        quality_projection=item.quality_projection,
    )


def _dimension_message(item):
    values = dict(item)
    return _message(
        "ComparisonDimension",
        dimension=values.get("dimension", ""),
        values={k: float(v) for k, v in values.get("values", {}).items()},
        winner=values.get("winner", ""),
    )


def _message(name: str, **fields):
    if _HAS_STUBS and hasattr(variants_pb2, name):
        return getattr(variants_pb2, name)(**fields)
    return SimpleNamespace(**fields)
