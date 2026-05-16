"""AEIS Advisor — Role Resolver models."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelChoice:
    """Result of resolving a role/purpose to a concrete model."""

    model_id: str
    reason: str = "default_routing"
    is_local_fallback: bool = False
    confidence: float = 1.0
    estimated_cost_usd: float = 0.0
    used_subscription: bool = False
    budget_exceeded: bool = False
    suggested_alternative: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "reason": self.reason,
            "is_local_fallback": self.is_local_fallback,
            "confidence": self.confidence,
            "estimated_cost_usd": self.estimated_cost_usd,
            "used_subscription": self.used_subscription,
            "budget_exceeded": self.budget_exceeded,
            "suggested_alternative": self.suggested_alternative,
        }


@dataclass
class Role:
    """An abstract role that can be mapped to a model."""

    role_id: str
    name: str
    description: str = ""


@dataclass
class RoutingEntry:
    """A single entry in the routing matrix."""

    purpose_or_role: str
    risk_level: str
    model_id: str | list[str]
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "purpose_or_role": self.purpose_or_role,
            "risk_level": self.risk_level,
            "model_id": self.model_id,
            "description": self.description,
        }


@dataclass
class RoutingPreview:
    """Preview of routing decision for a scenario."""

    operator_id: str
    scenario: str
    resolved: ModelChoice
    alternatives: list[ModelChoice] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "scenario": self.scenario,
            "resolved": self.resolved.to_dict(),
            "alternatives": [a.to_dict() for a in self.alternatives],
        }
