from __future__ import annotations

from sylion.api import (
    ai_providers_routes,
    bundle_routes,
    deployment_routes,
    governance_routes,
    idea_routes,
    monitoring_budget_routes,
    skills_routes,
)
from sylion.governance.council_workflow import CouncilSession, CouncilWorkflow
from sylion.core.decision_gate_engine import DecisionClass


def test_budget_configure_emits(monkeypatch):
    events: list[tuple[str, dict]] = []

    class Tracker:
        def get_budget(self, model_id: str):
            assert model_id == "gpt-5"
            return {"budget_limit": 4.0}

        def configure(self, *args, **kwargs):
            return {"ok": True}

    monkeypatch.setattr(monitoring_budget_routes, "_tracker", Tracker())
    monkeypatch.setattr(
        monitoring_budget_routes,
        "publish_lifecycle_event",
        lambda topic, payload, **kwargs: events.append((topic, payload)) or "evt-1",
    )

    result = monitoring_budget_routes.configure_budget(
        monitoring_budget_routes.ConfigureBudgetRequest(
            model_id="gpt-5",
            budget_limit=10.0,
            provider="openai",
            fallback_model_id="",
        )
    )

    assert result == {"ok": True}
    assert events[0][0] == "aeis.system.budget_config_requested"
    assert events[0][1]["old_threshold_usd"] == 4.0
    assert events[0][1]["new_threshold_usd"] == 10.0


def test_provider_test_emits_setup_hooks(monkeypatch):
    events: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        ai_providers_routes,
        "_resolve_key",
        lambda provider: "sk-openai" if provider == "openai" else "",
    )
    monkeypatch.setitem(
        ai_providers_routes.DISPATCH,
        "openai",
        lambda prompt, model, max_tokens, key: {
            "text": "pong",
            "prompt_tokens": 3,
            "completion_tokens": 5,
        },
    )
    monkeypatch.setattr(
        ai_providers_routes,
        "publish_lifecycle_event",
        lambda topic, payload, **kwargs: events.append((topic, payload)) or "evt-provider",
    )

    result = ai_providers_routes.test_provider(
        "openai",
        ai_providers_routes.ProviderTestRequest(prompt="ping", model="gpt-4o-mini"),
    )

    assert result["provider"] == "openai"
    assert [topic for topic, _payload in events] == [
        "aeis.system.model_setup_requested",
        "aeis.system.api_provider_setup_requested",
    ]
    assert "openai" in events[0][1]["current_providers"]
    assert "gpt-4o-mini" in events[0][1]["current_models"]
    assert events[1][1]["action"] == "test"
    assert events[1][1]["provider_id"] == "openai"
    assert events[1][1]["has_key"] is True


def test_create_idea_emits(monkeypatch):
    events: list[tuple[str, dict]] = []

    class Vault:
        def create_idea(self, **kwargs):
            return {"idea_id": "idea-1", **kwargs}

    monkeypatch.setattr(idea_routes, "_idea_vault", Vault())
    monkeypatch.setattr(
        idea_routes,
        "publish_lifecycle_event",
        lambda topic, payload, **kwargs: events.append((topic, payload)) or "evt-2",
    )

    result = idea_routes.create_idea(
        idea_routes.CreateIdeaRequest(title="Idea", description="Desc", author="op", tags=["x"])
    )

    assert result["idea_id"] == "idea-1"
    assert events[0][0] == "aeis.idea.intake.completed"
    assert events[0][1]["idea_id"] == "idea-1"
    assert events[0][1]["operator_id"] == "op"
    assert events[0][1]["initial_classification"] == "D1"


def test_register_skill_emits(monkeypatch):
    events: list[tuple[str, dict]] = []

    class Registry:
        def list_skills(self, domain=None, limit=500):
            _ = limit
            if domain == "project-x":
                return [{"skill_id": "skill-existing"}]
            return []

        def register(self, *args, **kwargs):
            return {"skill_id": args[0]}

    monkeypatch.setattr(skills_routes, "get_skills_registry", lambda: Registry())
    monkeypatch.setattr(
        skills_routes,
        "publish_lifecycle_event",
        lambda topic, payload, **kwargs: events.append((topic, payload)) or "evt-3",
    )

    result = skills_routes.register_skill("skill-1", "Skill", domain="project-x", owner_role="owner")

    assert result["skill_id"] == "skill-1"
    assert events[0][0] == "aeis.system.skill_selection_requested"
    assert events[0][1]["current_skills"] == ["skill-existing"]


def test_create_deployment_emits_runtime_and_scaling(monkeypatch):
    events: list[tuple[str, dict]] = []

    class Orchestrator:
        def create_deployment(self, *args, **kwargs):
            _ = args, kwargs
            return {"deployment_id": "dep-1"}

    monkeypatch.setattr(deployment_routes, "_orch", Orchestrator())
    monkeypatch.setattr(
        deployment_routes,
        "publish_lifecycle_event",
        lambda topic, payload, **kwargs: events.append((topic, payload)) or f"evt-{len(events)}",
    )

    result = deployment_routes.create_deployment("project-1", "build", "dual", strategy="canary")

    assert result["deployment_id"] == "dep-1"
    assert [event[0] for event in events] == [
        "aeis.system.runtime_topology_change_requested",
        "aeis.system.vps_scaling_requested",
    ]
    assert events[0][1]["current_topology"] == "local_only"
    assert events[0][1]["proposed_topology"] == "hybrid"
    assert events[1][1]["action"] == "add_env"
    assert events[1][1]["current_env_count"] == 1
    assert events[1][1]["target_env_count"] == 2


def test_bundle_deploy_emits(monkeypatch):
    events: list[tuple[str, dict]] = []

    class Assembler:
        def get_bundle(self, bundle_id: str):
            return {"bundle_id": bundle_id}

        def deploy_bundle(self, **kwargs):
            return {"bundle_id": kwargs["bundle_id"], "deployed": True}

    monkeypatch.setattr(bundle_routes, "_bundle_assembler", Assembler())
    monkeypatch.setattr(
        bundle_routes,
        "publish_lifecycle_event",
        lambda topic, payload, **kwargs: events.append((topic, payload)) or "evt-4",
    )
    monkeypatch.setattr(
        bundle_routes,
        "await_advisor_decision",
        lambda event_id, timeout_s=5.0: {"decision": "proceed"},
    )

    result = bundle_routes.deploy_bundle(
        bundle_routes.DeployBundleRequest(bundle_id="bundle-1", target_env="staging")
    )

    assert result["deployed"] is True
    assert events[0][0] == "aeis.production.deploy_requested"


def test_bundle_deploy_missing_bundle_does_not_emit(monkeypatch):
    events: list[tuple[str, dict]] = []

    class Assembler:
        def get_bundle(self, bundle_id):
            _ = bundle_id
            return None

    monkeypatch.setattr(bundle_routes, "_bundle_assembler", Assembler())
    monkeypatch.setattr(
        bundle_routes,
        "publish_lifecycle_event",
        lambda topic, payload, **kwargs: events.append((topic, payload)) or "evt-404",
    )

    try:
        bundle_routes.deploy_bundle(
            bundle_routes.DeployBundleRequest(bundle_id="missing-bundle", target_env="staging")
        )
    except bundle_routes.HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException for missing bundle")

    assert events == []


def test_council_open_session_emits():
    bus_events: list[str] = []

    class Bus:
        def publish(self, event):
            bus_events.append(event.topic)
            return event.event_id

    workflow = CouncilWorkflow(event_bus=Bus())
    try:
        workflow.open_session(
            CouncilSession(
                proposal_id="proposal-1",
                decision_class=DecisionClass.D3,
                title="Council",
            )
        )
    finally:
        workflow._conn.close()

    assert "aeis.council.formation_requested" in bus_events


def test_submit_governance_ticket_emits(monkeypatch):
    events: list[tuple[str, dict]] = []

    class Store:
        def submit(self, ticket):
            return "ticket-1"

    monkeypatch.setattr(governance_routes, "get_ticket_store", lambda: Store())
    monkeypatch.setattr(
        governance_routes,
        "publish_lifecycle_event",
        lambda topic, payload, **kwargs: events.append((topic, payload)) or "evt-5",
    )

    result = governance_routes.submit_governance_ticket(
        governance_routes.TicketSubmitRequest(
            origin="global",
            decision_class="D3",
            gate_type="blocking",
            priority="P2",
            title="Need approval",
            summary="Summary",
            requested_by="operator-1",
        )
    )

    assert result["ticket_id"] == "ticket-1"
    assert events[0][0] == "aeis.human_gate.ticket_pending"


def test_approve_proposal_emits(monkeypatch):
    events: list[tuple[str, dict]] = []

    class Ladder:
        def approve(self, proposal_id, approved_by="", notes=""):
            return {"approved": True, "decision_class": "D3", "module_id": "project-1"}

    monkeypatch.setattr(governance_routes, "get_decision_ladder", lambda: Ladder())
    monkeypatch.setattr(
        governance_routes,
        "publish_lifecycle_event",
        lambda topic, payload, **kwargs: events.append((topic, payload)) or "evt-6",
    )
    monkeypatch.setattr(
        governance_routes,
        "await_advisor_decision",
        lambda event_id, timeout_s=5.0: {"decision": "proceed"},
    )
    monkeypatch.setattr(governance_routes, "requires_role", lambda role: (lambda: "owner"))

    result = governance_routes.approve_proposal("proposal-1", approved_by="owner", notes="ok", _user="owner")

    assert result["approved"] is True
    assert events[0][0] == "aeis.final_approval.requested"
