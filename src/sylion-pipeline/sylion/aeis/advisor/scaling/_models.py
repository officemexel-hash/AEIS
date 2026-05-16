"""AEIS Advisor — Scaling models."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScalingCard:
    """A scaling recommendation card."""

    card_id: str = ""
    operator_id: str = ""
    project_id: str = ""
    recommended: str = ""  # local_only | local_plus_vps | multi_vps | vps_only
    alternatives: list[str] = field(default_factory=list)
    d_level: str = "D2"
    evidence_pack_id: str | None = None
    human_gate_required: bool = False
    impacts: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.card_id:
            self.card_id = uuid.uuid4().hex

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "operator_id": self.operator_id,
            "project_id": self.project_id,
            "recommended": self.recommended,
            "alternatives": self.alternatives,
            "d_level": self.d_level,
            "evidence_pack_id": self.evidence_pack_id,
            "human_gate_required": self.human_gate_required,
            "impacts": self.impacts,
        }


@dataclass
class Env:
    """A registered environment."""

    env_id: str = ""
    operator_id: str = ""
    name: str = ""
    kind: str = ""  # local | vps | hybrid
    capacity_tokens_per_day: int = 0
    registered_at: float = 0.0

    def __post_init__(self):
        if not self.env_id:
            self.env_id = uuid.uuid4().hex
        if not self.registered_at:
            self.registered_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "env_id": self.env_id,
            "operator_id": self.operator_id,
            "name": self.name,
            "kind": self.kind,
            "capacity_tokens_per_day": self.capacity_tokens_per_day,
            "registered_at": self.registered_at,
        }


@dataclass
class StagingPlan:
    """A staging plan for topology migration."""

    plan_id: str = ""
    current_topology: str = ""
    target_topology: str = ""
    phases: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.plan_id:
            self.plan_id = uuid.uuid4().hex

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "current_topology": self.current_topology,
            "target_topology": self.target_topology,
            "phases": self.phases,
        }
