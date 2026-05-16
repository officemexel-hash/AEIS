"""Persona catalog — 10 simulated operators for advisor testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Persona:
    """A simulated operator with heuristic decision profile."""

    id: str
    name: str
    role: str
    tech_skill: int          # 1-5
    risk_appetite: int       # 1-5
    council_preference: int  # 3-9
    typical_actions: list[str]
    decision_speed_p50: float  # median seconds to decide

    # Heuristic attributes derived from spec
    hard_change_policy: str = "mostly_confirm"   # always_confirm | mostly_confirm | always_reject
    default_distribution: dict[str, float] = field(default_factory=dict)
    cost_sensitivity: str = "medium"             # low | medium | high
    autonomy_level: str = "suggest"              # auto | suggest | manual
    funding_preference: bool = False

    def __post_init__(self):
        if not self.default_distribution:
            self.default_distribution = {"accept": 0.65, "modify": 0.20, "reject": 0.10, "remind_later": 0.05}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "tech_skill": self.tech_skill,
            "risk_appetite": self.risk_appetite,
            "council_preference": self.council_preference,
            "typical_actions": self.typical_actions,
            "decision_speed_p50": self.decision_speed_p50,
            "hard_change_policy": self.hard_change_policy,
            "default_distribution": self.default_distribution,
            "cost_sensitivity": self.cost_sensitivity,
            "autonomy_level": self.autonomy_level,
            "funding_preference": self.funding_preference,
        }


# ---------------------------------------------------------------------------
# 10 personas — business-facing roles mapped from spec behaviour profiles
# ---------------------------------------------------------------------------

PERSONAS: list[Persona] = [
    Persona(
        id="p1_solo_indie",
        name="Solo Indie Hacker",
        role="solo",
        tech_skill=4,
        risk_appetite=3,
        council_preference=3,
        typical_actions=["accept", "modify", "reject"],
        decision_speed_p50=2.0,
        hard_change_policy="mostly_confirm",
        default_distribution={"accept": 0.70, "modify": 0.15, "reject": 0.10, "remind_later": 0.05},
        cost_sensitivity="medium",
        autonomy_level="suggest",
        funding_preference=False,
    ),
    Persona(
        id="p2_small_team_lead",
        name="Small Team Lead (3-5)",
        role="team_lead",
        tech_skill=4,
        risk_appetite=3,
        council_preference=5,
        typical_actions=["accept", "batch_process", "modify"],
        decision_speed_p50=5.0,
        hard_change_policy="always_confirm",
        default_distribution={"accept": 0.65, "modify": 0.20, "reject": 0.05, "convert_to_human_gate": 0.10},
        cost_sensitivity="medium",
        autonomy_level="suggest",
        funding_preference=False,
    ),
    Persona(
        id="p3_consultant",
        name="AI Consultant (B2B)",
        role="consultant",
        tech_skill=5,
        risk_appetite=2,
        council_preference=7,
        typical_actions=["accept", "modify", "convert_to_human_gate"],
        decision_speed_p50=8.0,
        hard_change_policy="always_confirm",
        default_distribution={"accept": 0.50, "modify": 0.25, "reject": 0.05, "convert_to_human_gate": 0.20},
        cost_sensitivity="low",
        autonomy_level="manual",
        funding_preference=False,
    ),
    Persona(
        id="p4_research_lead",
        name="Research Lead",
        role="research_lead",
        tech_skill=5,
        risk_appetite=2,
        council_preference=5,
        typical_actions=["accept", "modify", "reject", "not_useful"],
        decision_speed_p50=6.0,
        hard_change_policy="mostly_confirm",
        default_distribution={"accept": 0.65, "modify": 0.20, "reject": 0.10, "remind_later": 0.05},
        cost_sensitivity="medium",
        autonomy_level="suggest",
        funding_preference=False,
    ),
    Persona(
        id="p5_grant_pm",
        name="Grant Project Manager",
        role="grant_pm",
        tech_skill=3,
        risk_appetite=3,
        council_preference=5,
        typical_actions=["accept", "modify", "convert_to_human_gate"],
        decision_speed_p50=7.0,
        hard_change_policy="always_confirm",
        default_distribution={"accept": 0.80, "modify": 0.15, "reject": 0.05},
        cost_sensitivity="low",
        autonomy_level="suggest",
        funding_preference=True,
    ),
    Persona(
        id="p6_startup_cto",
        name="Startup CTO",
        role="startup_cto",
        tech_skill=5,
        risk_appetite=4,
        council_preference=5,
        typical_actions=["accept", "modify", "override"],
        decision_speed_p50=3.0,
        hard_change_policy="mostly_confirm",
        default_distribution={"accept": 0.70, "modify": 0.15, "reject": 0.05, "convert_to_human_gate": 0.10},
        cost_sensitivity="medium",
        autonomy_level="auto",
        funding_preference=False,
    ),
    Persona(
        id="p7_enterprise_arch",
        name="Enterprise Architect",
        role="enterprise_arch",
        tech_skill=5,
        risk_appetite=2,
        council_preference=9,
        typical_actions=["accept", "modify", "convert_to_human_gate"],
        decision_speed_p50=10.0,
        hard_change_policy="always_confirm",
        default_distribution={"accept": 0.40, "modify": 0.20, "reject": 0.05, "convert_to_human_gate": 0.35},
        cost_sensitivity="low",
        autonomy_level="manual",
        funding_preference=False,
    ),
    Persona(
        id="p8_compliance_off",
        name="Compliance Officer",
        role="compliance",
        tech_skill=3,
        risk_appetite=1,
        council_preference=9,
        typical_actions=["accept", "convert_to_human_gate", "reject"],
        decision_speed_p50=12.0,
        hard_change_policy="always_confirm",
        default_distribution={"accept": 0.25, "modify": 0.15, "reject": 0.10, "convert_to_human_gate": 0.50},
        cost_sensitivity="low",
        autonomy_level="manual",
        funding_preference=False,
    ),
    Persona(
        id="p9_devrel",
        name="DevRel / Educator",
        role="devrel",
        tech_skill=4,
        risk_appetite=3,
        council_preference=3,
        typical_actions=["accept", "modify", "dont_learn_from_this"],
        decision_speed_p50=4.0,
        hard_change_policy="mostly_confirm",
        default_distribution={"accept": 0.75, "modify": 0.15, "reject": 0.05, "remind_later": 0.05},
        cost_sensitivity="medium",
        autonomy_level="suggest",
        funding_preference=False,
    ),
    Persona(
        id="p10_ai_agency",
        name="AI Agency Owner",
        role="agency_owner",
        tech_skill=4,
        risk_appetite=3,
        council_preference=5,
        typical_actions=["accept", "batch_process", "modify"],
        decision_speed_p50=5.0,
        hard_change_policy="mostly_confirm",
        default_distribution={"accept": 0.70, "modify": 0.15, "reject": 0.05, "convert_to_human_gate": 0.10},
        cost_sensitivity="high",
        autonomy_level="auto",
        funding_preference=True,
    ),
]


# Lookup helpers
_BY_ID: dict[str, Persona] = {p.id: p for p in PERSONAS}


def get_persona(persona_id: str) -> Persona:
    if persona_id not in _BY_ID:
        raise KeyError(f"Unknown persona: {persona_id}")
    return _BY_ID[persona_id]


def list_persona_ids() -> list[str]:
    return list(_BY_ID.keys())
