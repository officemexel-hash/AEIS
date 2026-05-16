"""SYLION AEIS v2 — GDPR DSR REST routes.

Sprint 2 day 5 — Article 15 (ACCESS), 16 (RECTIFICATION), 17 (ERASURE),
20 (PORTABILITY) for the data subject. RBAC: every action requires the
``operator`` role at minimum (the operator runs DSR on behalf of the
data subject); ``owner`` always passes per the canonical RBAC matrix.

Endpoints (prefix ``/api/v1/gdpr``):

    GET    /dsr/access/{user_id}              — Article 15
    POST   /dsr/rectification/{user_id}       — Article 16
    DELETE /dsr/erasure/{user_id}             — Article 17 (soft delete)
    GET    /dsr/portability/{user_id}         — Article 20
    GET    /dsr/audit/recent?limit=N          — DPO ledger view (auditor role)

The 5th endpoint (``audit/recent``) is the DPO's read into the JSONL
ledger — it is bound to the ``auditor`` role rather than ``operator``
so the same person who runs DSR cannot also alter / read the audit
trail (separation of duties per W17 evidence-spine charter).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sylion.aeis_v2.gdpr_v2 import get_dsr_service
from sylion.security.rbac import requires_role

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/gdpr", tags=["gdpr_v2"])


class DsrRectifyRequest(BaseModel):
    """Body for POST /dsr/rectification/{user_id}."""

    patch: dict[str, Any] = Field(
        default_factory=dict,
        description="Partial user record to merge (excluding user_id).",
    )


@router.get(
    "/dsr/access/{user_id}",
    dependencies=[Depends(requires_role("operator", "owner", "auditor"))],
)
def dsr_access(user_id: str) -> dict[str, Any]:
    """GDPR Article 15 — return everything we hold for the user."""
    result = get_dsr_service().access(user_id)
    if not result.success:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "user not found or already erased",
                "user_id": user_id,
                "audit_event_id": result.audit_event_id,
            },
        )
    return result.to_dict()


@router.post(
    "/dsr/rectification/{user_id}",
    dependencies=[Depends(requires_role("operator", "owner"))],
)
def dsr_rectification(user_id: str, req: DsrRectifyRequest) -> dict[str, Any]:
    """GDPR Article 16 — apply a partial patch to the user record.

    Reverses a soft-delete if the user was previously erased — this is
    the GDPR Article 12.3 reversal path, audited as a rectification.
    """
    result = get_dsr_service().rectify(user_id, req.patch)
    if not result.success:
        raise HTTPException(
            status_code=400,
            detail={
                "error": (result.payload or {}).get("error", "rectification failed"),
                "user_id": user_id,
                "audit_event_id": result.audit_event_id,
            },
        )
    return result.to_dict()


@router.delete(
    "/dsr/erasure/{user_id}",
    dependencies=[Depends(requires_role("owner"))],
)
def dsr_erasure(user_id: str) -> dict[str, Any]:
    """GDPR Article 17 — soft-delete the user (30-day hard-purge cron).

    ``owner``-only because erasure is irreversible after the 30-day
    window — the canonical RBAC matrix does not give ``operator`` the
    keys to that drawer.
    """
    result = get_dsr_service().erase(user_id)
    if not result.success:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "user not found",
                "user_id": user_id,
                "audit_event_id": result.audit_event_id,
            },
        )
    return result.to_dict()


@router.get(
    "/dsr/portability/{user_id}",
    dependencies=[Depends(requires_role("operator", "owner", "auditor"))],
)
def dsr_portability(user_id: str) -> dict[str, Any]:
    """GDPR Article 20 — machine-readable export."""
    result = get_dsr_service().portability(user_id)
    if not result.success:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "user not found",
                "user_id": user_id,
                "audit_event_id": result.audit_event_id,
            },
        )
    return result.to_dict()


@router.get(
    "/dsr/audit/recent",
    dependencies=[Depends(requires_role("auditor", "owner"))],
)
def dsr_audit_recent(limit: int = 50) -> dict[str, Any]:
    """Tail the gdpr_dsr.jsonl ledger for the DPO.

    Returns the last ``limit`` entries (default 50, capped at 1000).
    Defensive read: missing file or unparseable lines do not raise.
    """
    if limit < 1:
        limit = 1
    if limit > 1000:
        limit = 1000

    path = (
        Path(__file__).resolve().parents[2]
        / "logs" / "v2" / "gdpr_dsr.jsonl"
    )
    if not path.exists():
        return {"entries": [], "count": 0}

    entries: list[dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError as exc:
        log.warning("gdpr_dsr: audit read failed (%s)", exc)
        return {"entries": [], "count": 0, "error": str(exc)}

    tail = entries[-limit:]
    return {"entries": tail, "count": len(tail)}
