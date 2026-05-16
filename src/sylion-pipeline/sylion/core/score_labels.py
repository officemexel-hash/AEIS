from __future__ import annotations


def score_to_label(score: float, thresholds: dict[str, float] | None = None) -> str:
    limits = thresholds or {"low": 0.3, "medium": 0.7}
    if score < limits["low"]:
        return "low"
    if score < limits["medium"]:
        return "medium"
    return "high"
