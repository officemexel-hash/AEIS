"""Bidirectional matcher: idea <-> grants, with gap analysis."""

from sylion.aeis.advisor.funding.matcher.gap_analyzer import (
    analyze_gaps,
)
from sylion.aeis.advisor.funding.matcher.grants_to_ideas import (
    list_matching_ideas,
)
from sylion.aeis.advisor.funding.matcher.idea_to_grants import (
    list_eligible_grants,
)

__all__ = [
    "analyze_gaps",
    "list_eligible_grants",
    "list_matching_ideas",
]
