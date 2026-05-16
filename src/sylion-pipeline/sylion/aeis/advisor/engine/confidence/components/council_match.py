"""Council match: how aligned is the recommendation with current Council weights.

Heuristic v1: if council snapshot exposes a `weighted_alignment` ratio in [0,1]
we use it. Otherwise we approximate from agree/disagree vote counts. Default
0.5 when no signal is available so the score is neither boosted nor punished.
"""

from __future__ import annotations

from typing import Any


def score(council_snapshot: dict[str, Any] | None) -> float:
    if not council_snapshot:
        return 0.5
    val = council_snapshot.get("weighted_alignment")
    if isinstance(val, (int, float)):
        return _clip(float(val))

    in_favor = council_snapshot.get("votes_in_favor")
    against = council_snapshot.get("votes_against")
    if isinstance(in_favor, (int, float)) and isinstance(against, (int, float)):
        total = float(in_favor) + float(against)
        if total > 0:
            return _clip(float(in_favor) / total)

    consensus = council_snapshot.get("consensus_reached")
    if isinstance(consensus, bool):
        return 0.85 if consensus else 0.35

    return 0.5


def _clip(v: float) -> float:
    return max(0.0, min(1.0, v))
