"""Pricing quality: data freshness/source quality of cost estimates.

Mapping:
    measured / live -> 1.0
    profile         -> 0.6
    assumption      -> 0.2
    no_data         -> 0.5  (neutral)
"""

from __future__ import annotations

from typing import Any


_MAP = {
    "measured": 1.0,
    "live": 1.0,
    "live_provider_metadata": 1.0,
    "profile": 0.6,
    "pricing_profile": 0.6,
    "manual_table": 0.55,
    "assumption": 0.2,
}


def score(pricing_snapshot: dict[str, Any] | None) -> float:
    if not pricing_snapshot:
        return 0.5
    label = (pricing_snapshot.get("source_label") or "").lower()
    if label in _MAP:
        return _MAP[label]
    if pricing_snapshot.get("is_assumption"):
        return _MAP["assumption"]
    confidence_label = (pricing_snapshot.get("estimate_confidence") or "").lower()
    if confidence_label in _MAP:
        return _MAP[confidence_label]
    return 0.5
