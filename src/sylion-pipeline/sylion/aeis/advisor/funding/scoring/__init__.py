"""Scoring subpackage: per-grant profile resolution + component computation."""

from sylion.aeis.advisor.funding.scoring.calculator import (
    compute_score,
    score_with_profile,
)
from sylion.aeis.advisor.funding.scoring.components import (
    score_capacity,
    score_competitive_position,
    score_consortium_readiness,
    score_eligibility,
    score_regional_fit,
    score_thematic_alignment,
    score_timeline_fit,
)
from sylion.aeis.advisor.funding.scoring.profile_loader import (
    ensure_profile,
    resolve_profile,
)

__all__ = [
    "compute_score",
    "score_with_profile",
    "score_capacity",
    "score_competitive_position",
    "score_consortium_readiness",
    "score_eligibility",
    "score_regional_fit",
    "score_thematic_alignment",
    "score_timeline_fit",
    "ensure_profile",
    "resolve_profile",
]
