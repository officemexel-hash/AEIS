"""gRPC facade for the advisor funding service."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

from sylion.aeis.advisor.funding._models import IdeaContext
from sylion.aeis.advisor.funding.service import AdvisorFundingService, get_funding_service

log = logging.getLogger("sylion.aeis.advisor.funding.grpc_server")

try:
    from sylion.aeis.advisor._generated import funding_pb2, funding_pb2_grpc
    _HAS_STUBS = True
except ImportError:
    funding_pb2 = None
    funding_pb2_grpc = None
    _HAS_STUBS = False


_BaseServicer = funding_pb2_grpc.FundingServiceServicer if _HAS_STUBS else object


class FundingServicer(_BaseServicer):
    """Thin RPC bridge to the in-process funding service."""

    def __init__(self, service: AdvisorFundingService | None = None) -> None:
        self._service = service or get_funding_service()

    def ListGrants(self, request, context=None):
        grants = self._service.list_grants(
            country=_empty_to_none(getattr(request, "country", "")),
            region=_empty_to_none(getattr(request, "region", "")),
        )
        return _message("ListGrantsResponse", grants=[_as_namespace(item) for item in grants])

    def ScoreProject(self, request, context=None):
        result = self._service.compute_scoring(
            operator_id=getattr(request, "operator_id", ""),
            company_id=getattr(request, "company_id", ""),
            program_id=getattr(request, "program_id", ""),
            profile_id=getattr(request, "profile_id", ""),
            idea=_idea_from_request(getattr(request, "idea", None)),
            triggering_event=getattr(request, "triggering_event", "manual_recalc"),
        )
        return _message("ScoreProjectResponse", scoring=_as_namespace(result))

    def SimulateGrant(self, request, context=None):
        scenarios = self._service.simulate(
            operator_id=getattr(request, "operator_id", ""),
            company_id=getattr(request, "company_id", ""),
            idea=_idea_from_request(getattr(request, "idea", None)),
            program_id=getattr(request, "program_id", ""),
            mode=getattr(request, "mode", "static") or "static",
            operator_changes=_value_to_python(getattr(request, "operator_changes", None)),
        )
        return _message(
            "SimulateGrantResponse",
            scenarios=[_as_namespace(item) for item in scenarios],
        )


def register_funding_service(server, service: AdvisorFundingService | None = None) -> bool:
    if not _HAS_STUBS:
        return False
    funding_pb2_grpc.add_FundingServiceServicer_to_server(FundingServicer(service), server)
    return True


def serve(host: str = "127.0.0.1", port: int = 50061) -> None:
    """Run the funding gRPC server when generated stubs are present."""
    if not _HAS_STUBS:
        log.warning(
            "funding grpc_server.serve() cannot start because funding_pb2 stubs are unavailable; "
            "use get_funding_service() in-process for now"
        )
        get_funding_service()
        return

    import grpc
    from concurrent import futures

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    register_funding_service(server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    server.wait_for_termination()


def get_service():
    return get_funding_service()


def _message(name: str, **fields: Any):
    if _HAS_STUBS and hasattr(funding_pb2, name):
        return getattr(funding_pb2, name)(**fields)
    return SimpleNamespace(**fields)


def _idea_from_request(raw: Any) -> IdeaContext:
    if raw is None:
        return IdeaContext()
    if isinstance(raw, IdeaContext):
        return raw
    return IdeaContext(
        idea_id=getattr(raw, "idea_id", ""),
        title=getattr(raw, "title", ""),
        description=getattr(raw, "description", ""),
        domain=getattr(raw, "domain", ""),
        keywords=list(getattr(raw, "keywords", []) or []),
        rd_share_pct=float(getattr(raw, "rd_share_pct", 0.0) or 0.0),
        target_country=getattr(raw, "target_country", ""),
        target_region=getattr(raw, "target_region", ""),
        requires_consortium=bool(getattr(raw, "requires_consortium", False)),
        expected_duration_months=int(getattr(raw, "expected_duration_months", 0) or 0),
        target_budget_usd=float(getattr(raw, "target_budget_usd", 0.0) or 0.0),
    )


def _empty_to_none(value: str | None) -> str | None:
    return value or None


def _value_to_python(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "items"):
        return dict(value.items())
    return value


def _as_namespace(value: Any):
    if isinstance(value, SimpleNamespace):
        return value
    if hasattr(value, "__dict__"):
        return SimpleNamespace(**value.__dict__)
    if isinstance(value, dict):
        return SimpleNamespace(**value)
    return value
