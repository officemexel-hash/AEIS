"""SYLION AEIS v2 — governance plane.

Sprint 3 governance helpers. The first deliverable is the ADR sign-off
machinery used by the Council Hybrid wedge to flip a PROPOSED ADR to
ACCEPTED once 9 role votes + critic signature land.

Provides:

* :func:`compute_adr_signature` — canonical ADR document hash.
* :func:`load_adr_status` / :func:`set_adr_status` — read/write status
  inside an ADR markdown file (the ``Status:`` line in the front-matter
  block is the single source of truth).
* :class:`AdrSignoffRequest` / :class:`AdrSignoffResult` — request and
  result schemas for the sign-off endpoint.
* :func:`evaluate_signoff` — pure validation pipeline that decides
  whether the request meets the gate.
"""

from sylion.aeis_v2.governance_v2.adr_signoff import (
    AdrSignoffRequest,
    AdrSignoffResult,
    AdrSignoffStatus,
    AdrVote,
    SIGNOFF_AUDIT_LOG_PATH,
    apply_signoff,
    compute_adr_signature,
    evaluate_signoff,
    load_adr_status,
    set_adr_status,
)

__all__ = [
    "AdrSignoffRequest",
    "AdrSignoffResult",
    "AdrSignoffStatus",
    "AdrVote",
    "SIGNOFF_AUDIT_LOG_PATH",
    "apply_signoff",
    "compute_adr_signature",
    "evaluate_signoff",
    "load_adr_status",
    "set_adr_status",
]
