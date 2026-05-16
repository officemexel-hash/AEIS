"""4-component confidence calculator with x0.8 multiplier on local fallback.

Formula (per audit revision binding):
    raw = 0.4 * council_match
        + 0.4 * history_match
        + 0.2 * pricing_quality
    final = (raw + historical_acceptance_rate) / 2 (averages in 4th component)
    if used_local_fallback: final *= 0.8
    final clipped to [0, 1]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sylion.aeis.advisor.engine.confidence.components import (
    council_match,
    history_match,
    pricing_quality,
    historical_acceptance,
)


LOCAL_FALLBACK_MULTIPLIER = 0.8
COMPONENT_WEIGHTS = {"council_match": 0.4, "history_match": 0.4, "pricing_quality": 0.2}


@dataclass
class ConfidenceBreakdown:
    council_match: float = 0.0
    history_match: float = 0.0
    pricing_quality: float = 0.0
    historical_acceptance_rate: float = 0.0
    used_local_fallback: bool = False
    raw_score: float = 0.0
    final_score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "council_match": self.council_match,
            "history_match": self.history_match,
            "pricing_quality": self.pricing_quality,
            "historical_acceptance_rate": self.historical_acceptance_rate,
            "used_local_fallback": self.used_local_fallback,
            "raw_score": self.raw_score,
            "final_score": self.final_score,
        }


def calculate_confidence(
    *,
    council_snapshot: dict[str, Any] | None,
    history_snapshot: dict[str, Any] | None,
    pricing_snapshot: dict[str, Any] | None,
    used_local_fallback: bool = False,
) -> ConfidenceBreakdown:
    cm = council_match.score(council_snapshot)
    hm = history_match.score(history_snapshot)
    pq = pricing_quality.score(pricing_snapshot)
    har = historical_acceptance.score(history_snapshot)

    raw = (
        COMPONENT_WEIGHTS["council_match"] * cm
        + COMPONENT_WEIGHTS["history_match"] * hm
        + COMPONENT_WEIGHTS["pricing_quality"] * pq
    )
    blended = (raw + har) / 2.0
    final = blended * (LOCAL_FALLBACK_MULTIPLIER if used_local_fallback else 1.0)
    final = max(0.0, min(1.0, final))

    return ConfidenceBreakdown(
        council_match=cm,
        history_match=hm,
        pricing_quality=pq,
        historical_acceptance_rate=har,
        used_local_fallback=used_local_fallback,
        raw_score=raw,
        final_score=final,
    )
