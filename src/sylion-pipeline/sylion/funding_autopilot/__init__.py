"""SYLION Funding Autopilot — full pillar (scan → match → submit → monitor).

Hook v1.0 (2026-04-25 D-INTEGRATE).
Re-exports the public surface so callers can write::

    from sylion.funding_autopilot import router, FundingAutopilotService

instead of reaching into submodules.
"""

from .governance_bridge import (
    submit_application_creation_ticket,
    submit_call_creation_ticket,
    submit_idea_conversion_ticket,
    submit_programme_creation_ticket,
    submit_scan_ticket,
    submit_submission_ticket,
)
from .routes import router
from .service import FundingAutopilotService
from .store import FundingAutopilotStore, get_funding_store

__all__ = [
    "FundingAutopilotService",
    "FundingAutopilotStore",
    "get_funding_store",
    "router",
    "submit_application_creation_ticket",
    "submit_call_creation_ticket",
    "submit_idea_conversion_ticket",
    "submit_programme_creation_ticket",
    "submit_scan_ticket",
    "submit_submission_ticket",
]
