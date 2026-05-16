"""Scenario definitions for static and dynamic simulation modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import random


@dataclass
class Scenario:
    id: str
    title: str
    events: list[dict[str, Any]]  # each event is {"topic": str, "payload": dict}
    expected_cards_min: int = 1
    expected_d_levels: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Static scenario templates — deterministic, no LLM
# ---------------------------------------------------------------------------

STATIC_SCENARIOS: list[Scenario] = [
    Scenario(
        id="idea_intake_research",
        title="Research idea intake",
        events=[
            {"topic": "aeis.idea.intake.completed", "payload": {"idea_id": "i-1", "domain": "research", "project_type": "research"}},
        ],
        expected_cards_min=1,
    ),
    Scenario(
        id="idea_intake_software",
        title="Software idea intake",
        events=[
            {"topic": "aeis.idea.intake.completed", "payload": {"idea_id": "i-2", "domain": "software", "project_type": "production"}},
        ],
        expected_cards_min=1,
    ),
    Scenario(
        id="budget_config",
        title="Budget configuration request",
        events=[
            {"topic": "aeis.system.budget_config_requested", "payload": {"operator_id": "op-1", "monthly_limit_usd": 500}},
        ],
        expected_cards_min=1,
    ),
    Scenario(
        id="model_setup",
        title="Model setup requested",
        events=[
            {"topic": "aeis.system.model_setup_requested", "payload": {"operator_id": "op-1", "provider": "anthropic", "model": "claude-sonnet"}},
        ],
        expected_cards_min=1,
    ),
    Scenario(
        id="council_formation",
        title="Council formation request",
        events=[
            {"topic": "aeis.council.formation_requested", "payload": {"operator_id": "op-1", "desired_size": 5, "project_id": "p-1"}},
        ],
        expected_cards_min=1,
    ),
    Scenario(
        id="autonomy_change",
        title="Autonomy policy change",
        events=[
            {"topic": "aeis.system.autonomy_policy_change_requested", "payload": {"operator_id": "op-1", "new_level": "auto", "project_type": "research"}},
        ],
        expected_cards_min=1,
    ),
    Scenario(
        id="runtime_topology",
        title="Runtime topology change",
        events=[
            {"topic": "aeis.system.runtime_topology_change_requested", "payload": {"operator_id": "op-1", "target": "hybrid", "project_id": "p-1"}},
        ],
        expected_cards_min=1,
    ),
    Scenario(
        id="skill_selection",
        title="Skill selection request",
        events=[
            {"topic": "aeis.system.skill_selection_requested", "payload": {"operator_id": "op-1", "skill_id": "testing", "action": "add"}},
        ],
        expected_cards_min=1,
    ),
    Scenario(
        id="production_deploy",
        title="Production deploy request",
        events=[
            {"topic": "aeis.production.deploy_requested", "payload": {"operator_id": "op-1", "project_id": "p-1", "bundle_id": "b-1"}},
        ],
        expected_cards_min=1,
    ),
    Scenario(
        id="vps_scaling",
        title="VPS scaling request",
        events=[
            {"topic": "aeis.system.vps_scaling_requested", "payload": {"operator_id": "op-1", "project_id": "p-1", "scale_up": True}},
        ],
        expected_cards_min=1,
    ),
    Scenario(
        id="api_provider_blocked",
        title="Blocked provider setup",
        events=[
            {"topic": "aeis.system.api_provider_setup_requested", "payload": {"operator_id": "op-1", "provider_id": "blocked-foo", "is_blocked": True}},
        ],
        expected_cards_min=0,
    ),
    Scenario(
        id="funding_advisor_onboard",
        title="Funding advisor onboarding",
        events=[
            {"topic": "aeis.advisor.subscription.roi_computed", "payload": {"operator_id": "op-1", "advisor_type": "funding", "roi_days": 15}},
            {"topic": "aeis.system.budget_config_requested", "payload": {"operator_id": "op-1", "monthly_limit_usd": 2000}},
        ],
        expected_cards_min=1,
    ),
    Scenario(
        id="sot_drafted",
        title="SoT drafted",
        events=[
            {"topic": "aeis.idea.sot_drafted", "payload": {"operator_id": "op-1", "idea_id": "i-3", "model_id": "claude-sonnet"}},
        ],
        expected_cards_min=1,
    ),
    Scenario(
        id="masterplan_created",
        title="Masterplan created",
        events=[
            {"topic": "aeis.masterplan.created", "payload": {"operator_id": "op-1", "project_id": "p-2", "module_count": 8}},
        ],
        expected_cards_min=1,
    ),
    Scenario(
        id="testing_completed",
        title="Testing completed",
        events=[
            {"topic": "aeis.testing.completed", "payload": {"operator_id": "op-1", "project_id": "p-1", "passed": True}},
        ],
        expected_cards_min=1,
    ),
]


# ---------------------------------------------------------------------------
# Dynamic scenario generator — time-based random events
# ---------------------------------------------------------------------------

_DYNAMIC_TOPICS = [
    "aeis.idea.intake.completed",
    "aeis.system.budget_config_requested",
    "aeis.system.model_setup_requested",
    "aeis.council.formation_requested",
    "aeis.system.autonomy_policy_change_requested",
    "aeis.system.runtime_topology_change_requested",
    "aeis.system.skill_selection_requested",
    "aeis.production.deploy_requested",
    "aeis.system.vps_scaling_requested",
    "aeis.idea.sot_drafted",
    "aeis.masterplan.created",
    "aeis.testing.completed",
]

_DYNAMIC_DOMAINS = ["software", "research", "data_analytics", "infrastructure", "legal"]
_DYNAMIC_PROJECT_TYPES = ["research", "production", "poc", "audit"]
_DYNAMIC_PROVIDERS = ["anthropic", "openai", "google", "ollama"]


def generate_dynamic_scenario(seed: int | None = None) -> Scenario:
    if seed is not None:
        random.seed(seed)
    topic = random.choice(_DYNAMIC_TOPICS)
    operator_id = f"op-{random.randint(1, 99):02d}"
    payload: dict[str, Any] = {"operator_id": operator_id}

    if "idea" in topic:
        payload["idea_id"] = f"i-{random.randint(1, 999)}"
        payload["domain"] = random.choice(_DYNAMIC_DOMAINS)
        payload["project_type"] = random.choice(_DYNAMIC_PROJECT_TYPES)
    elif "budget" in topic:
        payload["monthly_limit_usd"] = random.choice([100, 500, 1000, 2000, 5000])
    elif "model" in topic:
        payload["provider"] = random.choice(_DYNAMIC_PROVIDERS)
        payload["model"] = "claude-sonnet" if payload["provider"] == "anthropic" else "gpt-4"
    elif "council" in topic:
        payload["desired_size"] = random.randint(3, 9)
        payload["project_id"] = f"p-{random.randint(1, 99)}"
    elif "autonomy" in topic:
        payload["new_level"] = random.choice(["auto", "suggest", "manual"])
    elif "runtime" in topic or "vps" in topic or "deploy" in topic:
        payload["project_id"] = f"p-{random.randint(1, 99)}"
    elif "skill" in topic:
        payload["skill_id"] = random.choice(["testing", "security", "documentation", "performance"])
        payload["action"] = "add"
    elif "masterplan" in topic:
        payload["project_id"] = f"p-{random.randint(1, 99)}"
        payload["module_count"] = random.randint(3, 20)
    elif "testing" in topic:
        payload["project_id"] = f"p-{random.randint(1, 99)}"
        payload["passed"] = random.choice([True, False])

    scenario_id = f"dyn_{topic.replace('.', '_')}_{random.randint(1000, 9999)}"
    return Scenario(
        id=scenario_id,
        title=f"Dynamic: {topic}",
        events=[{"topic": topic, "payload": payload}],
        expected_cards_min=1,
    )


def generate_dynamic_scenarios(count: int, seed: int | None = None) -> list[Scenario]:
    if seed is not None:
        random.seed(seed)
    return [generate_dynamic_scenario() for _ in range(count)]
