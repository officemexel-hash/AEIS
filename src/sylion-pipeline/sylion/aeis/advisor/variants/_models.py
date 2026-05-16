"""AEIS Advisor — Variants models."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VariantParameter:
    """A single variant parameter."""

    key: str
    value: Any


@dataclass
class Variant:
    """A strategic variant for project execution."""

    variant_id: str = ""
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    estimated_cost_usd: float = 0.0
    estimated_time_hours: float = 0.0
    risk_level: str = "medium"
    quality_projection: float = 0.0  # 0.0–1.0

    def __post_init__(self):
        if not self.variant_id:
            self.variant_id = uuid.uuid4().hex

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "estimated_cost_usd": self.estimated_cost_usd,
            "estimated_time_hours": self.estimated_time_hours,
            "risk_level": self.risk_level,
            "quality_projection": self.quality_projection,
        }


@dataclass
class VariantSet:
    """Set of generated variants."""

    context_id: str = ""
    variants: list[Variant] = field(default_factory=list)
    generated_at: float = 0.0

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "variants": [v.to_dict() for v in self.variants],
            "generated_at": self.generated_at,
        }


@dataclass
class ComparisonDimension:
    """A single dimension in the comparison matrix."""

    dimension: str
    variant_a_value: Any
    variant_b_value: Any
    winner: str = ""


@dataclass
class ComparisonMatrix:
    """Comparison matrix between variants."""

    variant_ids: list[str] = field(default_factory=list)
    dimensions: list[ComparisonDimension] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_ids": self.variant_ids,
            "dimensions": [d.__dict__ for d in self.dimensions],
        }
