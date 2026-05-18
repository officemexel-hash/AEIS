"""
SYLION API -- Operator Mobile routes.

Thin mobile bridge over unified governance tickets. Mobile is a frontend to the
shared governance plane, not a second Human Gate.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sylion.operator_mobile import get_operator_mobile_bridge

log = logging.getLogger("sylion.api.operator_mobile_routes")

router = APIRouter(prefix="/api/v1/mobile", tags=["Operator Mobile"])
legacy_router = APIRouter(
    prefix="/api/v1/operator-mobile/v1",
    tags=["Operator Mobile"],
    include_in_schema=False,
)


def _get_bridge():
    return get_operator_mobile_bridge()


def _get_governance_hooks():
    try:
        from sylion.governance.tickets import fetch_by_id, fetch_pending, resolve
    except ImportError as exc:  # pragma: no cover - defensive fallback
        raise HTTPException(
            status_code=503,
            detail="governance tickets unavailable",
        ) from exc
    return fetch_by_id, fetch_pending, resolve


class BindDeviceRequest(BaseModel):
    operator_id: str
    device_token: str
    platform: str
    device_label: str = ""


class MobileDecisionRequest(BaseModel):
    decision: str
    reviewer: str
    reason: str = ""
    device_id: str = ""
    auth_method: str = ""
    geo: dict[str, Any] | None = None


def _serialize_ticket(ticket: Any, bridge_operator_id: str = "") -> dict[str, Any]:
    payload = ticket.to_dict() if hasattr(ticket, "to_dict") else dict(ticket)
    if bridge_operator_id:
        bridge = _get_bridge()
        payload["delivery_targets"] = len(bridge.list_devices(bridge_operator_id))
    return payload


def _requires_bound_device(ticket: Any, decision: str) -> bool:
    return (
        str(getattr(ticket, "decision_class", "")).upper() in {"D3", "D4", "D5"}
        and decision in {"approved", "rejected"}
    )


def _validate_bound_device(
    *,
    reviewer: str,
    device_id: str,
) -> dict[str, Any]:
    if not device_id.strip():
        raise HTTPException(
            status_code=422,
            detail="device_id is required for D3+ mobile governance decisions",
        )
    devices = _get_bridge().list_devices(reviewer)
    for device in devices:
        if str(device.get("device_id") or "") == device_id:
            return device
    raise HTTPException(
        status_code=403,
        detail="device_id is not bound to reviewer",
    )


def _record_mobile_decision_audit(
    *,
    ticket: Any,
    body: MobileDecisionRequest,
    device: dict[str, Any] | None,
) -> None:
    try:
        from sylion.security.audit_trail_aggregator import get_audit_trail_aggregator

        ticket_id = str(getattr(ticket, "ticket_id", "") or "")
        device_id = str((device or {}).get("device_id") or body.device_id or "")
        get_audit_trail_aggregator().record(
            source="operator_mobile",
            action="operator_mobile.ticket.decision",
            actor=body.reviewer,
            resource=f"ticket:{ticket_id}",
            outcome="success" if body.decision == "approved" else "denied",
            metadata={
                "ticket_id": ticket_id,
                "decision": body.decision,
                "reason": body.reason,
                "device_id": device_id,
                "platform": (device or {}).get("platform", ""),
                "device_label": (device or {}).get("device_label", ""),
                "auth_method": body.auth_method,
                "geo": body.geo or {},
                "decision_class": str(getattr(ticket, "decision_class", "") or ""),
                "project_id": getattr(ticket, "project_id", None),
            },
            entry_id=f"operator_mobile.ticket.{ticket_id}.{body.decision}.{device_id or 'unbound'}",
        )
    except Exception:  # noqa: BLE001
        log.warning("operator mobile decision audit failed", exc_info=True)


@router.post("/v1/devices/bind", status_code=201, include_in_schema=False)
@router.post("/devices/bind", status_code=201)
def bind_device(body: BindDeviceRequest):
    bridge = _get_bridge()
    try:
        bridge.bind_device(
            operator_id=body.operator_id,
            device_token=body.device_token,
            platform=body.platform,
            device_label=body.device_label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    devices = bridge.list_devices(body.operator_id)
    device = next(
        (
            item for item in devices
            if item.get("device_token") == body.device_token
        ),
        None,
    )
    return {
        "ok": True,
        "device": device,
        "count": len(devices),
    }


@router.get("/v1/devices", include_in_schema=False)
@router.get("/devices")
def list_devices(operator_id: str = Query(...)):
    bridge = _get_bridge()
    devices = bridge.list_devices(operator_id)
    return {"devices": devices, "count": len(devices)}


@router.delete("/v1/devices/{device_id}", include_in_schema=False)
@router.delete("/devices/{device_id}")
def unbind_device(device_id: str, operator_id: str | None = None):
    bridge = _get_bridge()
    removed = bridge.unbind_device(device_id, operator_id=operator_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"device {device_id} not found")
    return {"device_id": device_id, "removed": True}


@router.get("/v1/queue", include_in_schema=False)
@router.get("/queue")
def list_mobile_queue(
    operator_id: str = Query(...),
    project_id: str | None = None,
    priority: str | None = None,
):
    _, fetch_pending, _ = _get_governance_hooks()
    tickets = fetch_pending(
        operator_id=operator_id,
        project_id=project_id,
        priority=priority,
    )
    return {
        "tickets": [
            _serialize_ticket(ticket, bridge_operator_id=operator_id)
            for ticket in tickets
        ],
        "count": len(tickets),
    }


@router.get("/v1/queue/{ticket_id}", include_in_schema=False)
@router.get("/queue/{ticket_id}")
def get_mobile_queue_ticket(ticket_id: str, operator_id: str = Query(...)):
    fetch_by_id, _, _ = _get_governance_hooks()
    ticket = fetch_by_id(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"ticket {ticket_id} not found")
    return _serialize_ticket(ticket, bridge_operator_id=operator_id)


@router.post("/v1/queue/{ticket_id}/decision", include_in_schema=False)
@router.post("/queue/{ticket_id}/decision")
def resolve_mobile_ticket(ticket_id: str, body: MobileDecisionRequest):
    if body.decision not in {"approved", "rejected", "expired"}:
        raise HTTPException(
            status_code=422,
            detail="decision must be approved|rejected|expired",
        )
    fetch_by_id, _, resolve = _get_governance_hooks()
    ticket_before = fetch_by_id(ticket_id)
    if ticket_before is None:
        raise HTTPException(status_code=404, detail=f"ticket {ticket_id} not found")
    bound_device = None
    if _requires_bound_device(ticket_before, body.decision):
        bound_device = _validate_bound_device(
            reviewer=body.reviewer,
            device_id=body.device_id,
        )
    try:
        changed = resolve(
            ticket_id=ticket_id,
            decision=body.decision,
            reason=body.reason,
            reviewer=body.reviewer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not changed:
        raise HTTPException(
            status_code=409,
            detail=f"ticket {ticket_id} missing or already final",
        )
    ticket = fetch_by_id(ticket_id)
    _record_mobile_decision_audit(
        ticket=ticket or ticket_before,
        body=body,
        device=bound_device,
    )
    return ticket.to_dict() if ticket else {"ticket_id": ticket_id, "state": body.decision}


@router.post("/v1/queue/{ticket_id}/approve", include_in_schema=False)
@router.post("/queue/{ticket_id}/approve")
def approve_mobile_ticket(ticket_id: str, body: dict[str, Any]):
    """Compatibility alias for dashboard approve buttons."""
    reviewer = str(body.get("operator_id") or body.get("reviewer") or "operator")
    reason = str(body.get("comment") or body.get("reason") or "approved from mobile queue")
    device_id = str(body.get("device_id") or "")
    auth_method = str(body.get("auth_method") or "")
    return resolve_mobile_ticket(
        ticket_id,
        MobileDecisionRequest(
            decision="approved",
            reviewer=reviewer,
            reason=reason,
            device_id=device_id,
            auth_method=auth_method,
        ),
    )


@router.post("/v1/queue/{ticket_id}/reject", include_in_schema=False)
@router.post("/queue/{ticket_id}/reject")
def reject_mobile_ticket(ticket_id: str, body: dict[str, Any]):
    """Compatibility alias for dashboard reject buttons."""
    reviewer = str(body.get("operator_id") or body.get("reviewer") or "operator")
    reason = str(body.get("comment") or body.get("reason") or "rejected from mobile queue")
    device_id = str(body.get("device_id") or "")
    auth_method = str(body.get("auth_method") or "")
    return resolve_mobile_ticket(
        ticket_id,
        MobileDecisionRequest(
            decision="rejected",
            reviewer=reviewer,
            reason=reason,
            device_id=device_id,
            auth_method=auth_method,
        ),
    )


@legacy_router.post("/devices/bind", status_code=201)
def bind_device_legacy(body: BindDeviceRequest):
    return bind_device(body)


@legacy_router.get("/devices")
def list_devices_legacy(operator_id: str = Query(...)):
    return list_devices(operator_id)


@legacy_router.delete("/devices/{device_id}")
def unbind_device_legacy(device_id: str, operator_id: str | None = None):
    return unbind_device(device_id, operator_id)


@legacy_router.get("/queue")
def list_mobile_queue_legacy(
    operator_id: str = Query(...),
    project_id: str | None = None,
    priority: str | None = None,
):
    return list_mobile_queue(operator_id=operator_id, project_id=project_id, priority=priority)


@legacy_router.get("/queue/{ticket_id}")
def get_mobile_queue_ticket_legacy(ticket_id: str, operator_id: str = Query(...)):
    return get_mobile_queue_ticket(ticket_id, operator_id)


@legacy_router.post("/queue/{ticket_id}/decision")
def resolve_mobile_ticket_legacy(ticket_id: str, body: MobileDecisionRequest):
    return resolve_mobile_ticket(ticket_id, body)


@legacy_router.post("/queue/{ticket_id}/approve")
def approve_mobile_ticket_legacy(ticket_id: str, body: dict[str, Any]):
    return approve_mobile_ticket(ticket_id, body)


@legacy_router.post("/queue/{ticket_id}/reject")
def reject_mobile_ticket_legacy(ticket_id: str, body: dict[str, Any]):
    return reject_mobile_ticket(ticket_id, body)
