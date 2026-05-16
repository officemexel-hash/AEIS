"""SYLION AEIS Advisor — Funding module (opt-in).

Per-grant scoring profiles. Each grant has its own profile referencing the
universal component pool. Same company + same idea can produce different scores
across grants because each profile owns its weights, hard floors, and custom
criteria.

Entry point: `get_funding_service()` returns the singleton facade.
"""

from sylion.aeis.advisor.funding.service import (
    AdvisorFundingService,
    get_funding_service,
    reset_funding_service,
)

__all__ = [
    "AdvisorFundingService",
    "get_funding_service",
    "reset_funding_service",
]
