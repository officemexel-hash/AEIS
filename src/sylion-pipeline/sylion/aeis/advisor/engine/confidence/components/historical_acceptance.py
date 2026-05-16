"""4th confidence component: rate of similar past cards accepted by this operator."""

from __future__ import annotations

from typing import Any


def score(history_snapshot: dict[str, Any] | None) -> float:
    if not history_snapshot:
        return 0.5
    rate = history_snapshot.get("operator_acceptance_rate_for_type")
    if isinstance(rate, (int, float)):
        return max(0.0, min(1.0, float(rate)))
    accepted = history_snapshot.get("operator_accepted_count")
    rejected = history_snapshot.get("operator_rejected_count")
    if isinstance(accepted, (int, float)) and isinstance(rejected, (int, float)):
        total = float(accepted) + float(rejected)
        if total > 0:
            return max(0.0, min(1.0, float(accepted) / total))
    return 0.5
