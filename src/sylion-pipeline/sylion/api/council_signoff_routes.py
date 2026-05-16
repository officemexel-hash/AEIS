"""SYLION AEIS v2 — Council Hybrid ADR sign-off endpoint.

Sprint 3 A1 deliverable. Single endpoint::

    POST /api/v1/council/sign-off-adr/{adr_id}

Body shape::

    {
        "votes": [
            {"role": "planner",   "verdict": "approve", "confidence": 0.9, "rationale": "…"},
            {"role": "architect", "verdict": "approve", ...},
            ...  // exactly 9 — one per canonical Council role
        ],
        "critic_signature": "<sha256 hex of the ADR document>"
    }

RBAC: ``owner`` only — flipping ADR status is a high-trust write.

The endpoint delegates all validation + file mutation to
:mod:`sylion.aeis_v2.governance_v2.adr_signoff`; this file is just the
HTTP wiring + Pydantic schemas.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sylion.aeis_v2.governance_v2 import (
    AdrSignoffRequest,
    AdrVote,
    apply_signoff,
)
from sylion.security.rbac import requires_role

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/council", tags=["council_signoff"])

#: Production decisions dir — overridden by tests via dependency injection.
DEFAULT_DECISIONS_DIR = (
    Path(__file__).resolve().parents[3] / "docs" / "v2" / "decisions"
)


class _Vote(BaseModel):
    """Single role vote on an ADR."""

    role: str = Field(..., description="canonical Council role name")
    verdict: Literal["approve", "reject", "conditional"]
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = Field(default="", max_length=2000)


class _SignoffBody(BaseModel):
    """POST /api/v1/council/sign-off-adr/{adr_id} request body."""

    votes: list[_Vote] = Field(..., min_length=9, max_length=9)
    critic_signature: str = Field(..., min_length=8, max_length=128)


def _decisions_dir() -> Path:
    """Indirection so tests can monkeypatch the dir."""
    return DEFAULT_DECISIONS_DIR


@router.post(
    "/sign-off-adr/{adr_id}",
    dependencies=[Depends(requires_role("owner"))],
)
def sign_off_adr(adr_id: str, body: _SignoffBody) -> dict[str, Any]:
    """Apply the Council Hybrid sign-off gate to an ADR.

    Returns 200 + the result dict on a successful gate flip.
    Returns 422 with the failure detail when validation fails (so the
    operator UI can surface the precise reason without re-fetching the
    ADR file).
    """
    request = AdrSignoffRequest(
        adr_id=adr_id,
        votes=[
            AdrVote(
                role=v.role,
                verdict=v.verdict,
                confidence=v.confidence,
                rationale=v.rationale,
            )
            for v in body.votes
        ],
        critic_signature=body.critic_signature,
    )
    result = apply_signoff(request, decisions_dir=_decisions_dir())

    if not result.gate_passed:
        # 422 because the request shape was valid (Pydantic accepted it)
        # but the gate refused — caller has actionable detail.
        raise HTTPException(
            status_code=422,
            detail={
                "error": result.status,
                "detail": result.detail,
                "result": result.to_dict(),
            },
        )

    return result.to_dict()
