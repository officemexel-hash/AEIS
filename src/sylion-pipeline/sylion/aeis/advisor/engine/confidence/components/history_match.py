"""History match: similar past recommendations and their acceptance rate."""

from __future__ import annotations

from typing import Any


def score(history_snapshot: dict[str, Any] | None) -> float:
    if not history_snapshot:
        return 0.5
    accepted = history_snapshot.get("similar_accepted_count")
    rejected = history_snapshot.get("similar_rejected_count")
    if isinstance(accepted, (int, float)) and isinstance(rejected, (int, float)):
        total = float(accepted) + float(rejected)
        if total > 0:
            return max(0.0, min(1.0, float(accepted) / total))
    explicit = history_snapshot.get("similar_acceptance_rate")
    if isinstance(explicit, (int, float)):
        return max(0.0, min(1.0, float(explicit)))
    return 0.5
