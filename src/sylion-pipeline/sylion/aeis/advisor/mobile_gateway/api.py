"""FastAPI router for the mobile gateway (`/mobile/v1`).

Etap 1 stub. Endpoints are sync-first (per `08_audit_revisions.md` Revision 3).
Each successful request emits ``aeis.advisor.mobile_gateway.request_handled``;
auth failures emit ``aeis.advisor.mobile_gateway.auth_failure``; D3+ step-up
emits ``aeis.advisor.mobile_gateway.biometric_step_up_triggered``. Bus failures
are swallowed so they never break the request path.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request

from sylion.aeis.advisor.mobile_gateway import translator
from sylion.aeis.advisor.mobile_gateway._models import (
    CardActionRequest,
    CardActionResponse,
    CardListResponse,
    FundingDeadlinesResponse,
    HumanGateDecisionRequest,
    HumanGateListResponse,
    PreferenceListResponse,
    PreferencePutRequest,
    PreferenceValueResponse,
    ProjectLifecycleResponse,
    ProjectListResponse,
    SyncSnapshotResponse,
)
from sylion.aeis.advisor.mobile_gateway.auth import (
    AuthError,
    MobilePrincipal,
    authenticate,
    biometric_required_for_d_level,
)
from sylion.core.event_bus import SylionEvent

log = logging.getLogger("sylion.aeis.advisor.mobile_gateway.api")

_PREFIX = "/mobile/v1"
_SOURCE_MODULE = "sylion.aeis.advisor.mobile_gateway"

_router_lock = threading.Lock()
_router_singleton: Optional[APIRouter] = None


def build_mobile_router() -> APIRouter:
    """Singleton FastAPI router with all mobile gateway endpoints."""
    global _router_singleton
    if _router_singleton is not None:
        return _router_singleton
    with _router_lock:
        if _router_singleton is not None:
            return _router_singleton
        _router_singleton = _build()
    return _router_singleton


def reset_mobile_router() -> None:
    """For tests: drop the cached router so the next build_mobile_router() runs fresh."""
    global _router_singleton
    with _router_lock:
        _router_singleton = None


# ---------------------------------------------------------------------------
# Event emission helpers
# ---------------------------------------------------------------------------


def _publish(topic: str, payload: dict[str, Any]) -> None:
    """Best-effort emit on the shared event backbone; never raise."""
    try:
        from sylion.core.event_backbone import get_event_backbone

        event = SylionEvent(
            event_id=str(uuid.uuid4()),
            topic=topic,
            payload=payload,
            source_module=_SOURCE_MODULE,
            timestamp=time.time(),
        )
        get_event_backbone().publish(event)
    except Exception:
        log.warning("mobile_gateway: event emission failed for %s", topic, exc_info=True)


def _emit_request_handled(path: str, status_code: int, operator_id: str) -> None:
    _publish(
        "aeis.advisor.mobile_gateway.request_handled",
        {"path": path, "status_code": status_code, "operator_id": operator_id},
    )


def _emit_auth_failure(path: str, reason: str) -> None:
    _publish(
        "aeis.advisor.mobile_gateway.auth_failure",
        {"path": path, "reason": reason},
    )


def _emit_biometric_step_up(card_id: str, operator_id: str, d_level: str) -> None:
    _publish(
        "aeis.advisor.mobile_gateway.biometric_step_up_triggered",
        {"card_id": card_id, "operator_id": operator_id, "d_level": d_level},
    )


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _authenticate(
    request: Request,
    authorization: Optional[str],
    biometric_header: Optional[str],
) -> MobilePrincipal:
    try:
        return authenticate(authorization, biometric_header)
    except AuthError as exc:
        _emit_auth_failure(request.url.path, str(exc))
        raise HTTPException(status_code=401, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Router builder
# ---------------------------------------------------------------------------


def _build() -> APIRouter:
    router = APIRouter(prefix=_PREFIX, tags=["Advisor Mobile Gateway"])

    @router.get("/cards", response_model=CardListResponse)
    def list_cards(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_biometric_verified: Optional[str] = Header(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> CardListResponse:
        principal = _authenticate(request, authorization, x_biometric_verified)
        cards = translator.list_recent_cards(operator_id=principal.operator_id, limit=limit)
        _emit_request_handled(request.url.path, 200, principal.operator_id)
        return CardListResponse(cards=cards, total=len(cards))

    @router.get("/cards/{card_id}")
    def get_card(
        card_id: str,
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_biometric_verified: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        principal = _authenticate(request, authorization, x_biometric_verified)
        envelope = translator.get_card(card_id)
        if envelope is None:
            _emit_request_handled(request.url.path, 404, principal.operator_id)
            raise HTTPException(status_code=404, detail="card not found")
        _emit_request_handled(request.url.path, 200, principal.operator_id)
        return envelope

    @router.post("/cards/{card_id}/actions", response_model=CardActionResponse)
    def submit_card_action(
        card_id: str,
        body: CardActionRequest,
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_biometric_verified: Optional[str] = Header(default=None),
    ) -> CardActionResponse:
        principal = _authenticate(request, authorization, x_biometric_verified)
        envelope = translator.get_card(card_id)
        if envelope is None:
            _emit_request_handled(request.url.path, 404, principal.operator_id)
            raise HTTPException(status_code=404, detail="card not found")

        d_level = translator.card_d_level(envelope)
        if biometric_required_for_d_level(d_level) and not principal.biometric_verified:
            _emit_biometric_step_up(card_id, principal.operator_id, d_level)
            _emit_request_handled(request.url.path, 401, principal.operator_id)
            raise HTTPException(
                status_code=401,
                detail="biometric step-up required (X-Biometric-Verified header)",
            )

        # Etap 2: route to actions service for execution. Etap 1 records intent only.
        log.info(
            "mobile_gateway: action=%s card=%s operator=%s",
            body.action, card_id, principal.operator_id,
        )
        _emit_request_handled(request.url.path, 200, principal.operator_id)
        return CardActionResponse(
            card_id=card_id,
            action=body.action,
            accepted=True,
            biometric_required=biometric_required_for_d_level(d_level),
        )

    @router.get("/projects", response_model=ProjectListResponse)
    def list_projects(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_biometric_verified: Optional[str] = Header(default=None),
    ) -> ProjectListResponse:
        principal = _authenticate(request, authorization, x_biometric_verified)
        _emit_request_handled(request.url.path, 200, principal.operator_id)
        return ProjectListResponse(projects=[])

    @router.get("/projects/{project_id}/lifecycle", response_model=ProjectLifecycleResponse)
    def project_lifecycle(
        project_id: str,
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_biometric_verified: Optional[str] = Header(default=None),
    ) -> ProjectLifecycleResponse:
        principal = _authenticate(request, authorization, x_biometric_verified)
        skeleton = translator.project_lifecycle_skeleton(project_id)
        _emit_request_handled(request.url.path, 200, principal.operator_id)
        return ProjectLifecycleResponse(**skeleton)

    @router.get("/human_gate/pending", response_model=HumanGateListResponse)
    def human_gate_pending(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_biometric_verified: Optional[str] = Header(default=None),
    ) -> HumanGateListResponse:
        principal = _authenticate(request, authorization, x_biometric_verified)
        _emit_request_handled(request.url.path, 200, principal.operator_id)
        return HumanGateListResponse(tickets=[])

    @router.post("/human_gate/{ticket_id}/decide")
    def human_gate_decide(
        ticket_id: str,
        body: HumanGateDecisionRequest,
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_biometric_verified: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        principal = _authenticate(request, authorization, x_biometric_verified)
        _emit_request_handled(request.url.path, 501, principal.operator_id)
        raise HTTPException(
            status_code=501,
            detail="human_gate decision flow lands in Etap 2 (mobile actions service)",
        )

    @router.get("/funding/deadlines", response_model=FundingDeadlinesResponse)
    def funding_deadlines(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_biometric_verified: Optional[str] = Header(default=None),
    ) -> FundingDeadlinesResponse:
        principal = _authenticate(request, authorization, x_biometric_verified)
        _emit_request_handled(request.url.path, 200, principal.operator_id)
        return FundingDeadlinesResponse(deadlines=[])

    @router.get("/preferences", response_model=PreferenceListResponse)
    def list_preferences(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_biometric_verified: Optional[str] = Header(default=None),
    ) -> PreferenceListResponse:
        principal = _authenticate(request, authorization, x_biometric_verified)
        _emit_request_handled(request.url.path, 200, principal.operator_id)
        return PreferenceListResponse(operator_id=principal.operator_id, preferences={})

    @router.get("/preferences/{key}", response_model=PreferenceValueResponse)
    def get_preference(
        key: str,
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_biometric_verified: Optional[str] = Header(default=None),
    ) -> PreferenceValueResponse:
        principal = _authenticate(request, authorization, x_biometric_verified)
        _emit_request_handled(request.url.path, 200, principal.operator_id)
        return PreferenceValueResponse(key=key, value=None, source="default")

    @router.put("/preferences/{key}")
    def put_preference(
        key: str,
        body: PreferencePutRequest,
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_biometric_verified: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        principal = _authenticate(request, authorization, x_biometric_verified)
        _emit_request_handled(request.url.path, 501, principal.operator_id)
        raise HTTPException(
            status_code=501,
            detail="preference mutation owned by preferences gRPC (Etap 2)",
        )

    @router.get("/sync/snapshot", response_model=SyncSnapshotResponse)
    def sync_snapshot(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_biometric_verified: Optional[str] = Header(default=None),
    ) -> SyncSnapshotResponse:
        principal = _authenticate(request, authorization, x_biometric_verified)
        snapshot = translator.build_offline_snapshot(operator_id=principal.operator_id)
        _emit_request_handled(request.url.path, 200, principal.operator_id)
        return SyncSnapshotResponse(**snapshot)

    return router
