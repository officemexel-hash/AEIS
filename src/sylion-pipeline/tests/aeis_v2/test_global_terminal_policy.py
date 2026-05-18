from __future__ import annotations

from fastapi.testclient import TestClient

from sylion.aeis_v2.terminal.command_router import execute_terminal_intent
from sylion.aeis_v2.terminal.global_policy import (
    GlobalCommandPolicyRequest,
    GlobalTerminalPolicy,
    reset_global_terminal_policy,
)
from sylion.api.app import app
from sylion.core.evidence_spine import EvidenceSpine
from sylion.governance.ticket import TicketStore, reset_ticket_store


def _policy() -> tuple[GlobalTerminalPolicy, TicketStore]:
    ticket_store = TicketStore(":memory:")
    service = GlobalTerminalPolicy(
        ":memory:",
        evidence_spine=EvidenceSpine(":memory:"),
        ticket_store=ticket_store,
    )
    return service, ticket_store


def _request(line: str, ctx: dict, command_id: str = "cmd_1") -> GlobalCommandPolicyRequest:
    return GlobalCommandPolicyRequest.from_context(line, ctx, command_id=command_id)


def test_global_terminal_policy_blocks_missing_required_metadata():
    service, _ = _policy()

    result = service.evaluate(_request("restart system", {}, "cmd_missing"))

    assert result["status"] == "blocked_metadata"
    assert result["checks"]["actor_present"] is False
    assert result["checks"]["environment_id_present"] is False
    assert result["checks"]["risk_class_present"] is False
    assert result["checks"]["rollback_hint_present"] is False
    assert result["evidence_id"]


def test_d4_global_command_creates_human_gate_ticket_and_blocks():
    service, ticket_store = _policy()

    result = service.evaluate(_request(
        "restart system",
        {
            "actor": "ops",
            "environment_id": "prod-eu",
            "risk_class": "D4",
            "rollback_hint": "restore previous supervisor unit",
        },
        "cmd_restart",
    ))

    assert result["status"] == "pending_human_gate"
    assert result["requires_human_gate"] is True
    assert len(result["ticket_ids"]) == 1
    ticket = ticket_store.get(result["ticket_ids"][0])
    assert ticket is not None
    assert ticket.origin == "global"
    assert ticket.project_id is None
    assert ticket.decision_class == "D4"
    assert ticket.payload["terminal_action"] == "restart"
    assert ticket.payload["environment_id"] == "prod-eu"
    assert ticket.payload["rollback_hint"] == "restore previous supervisor unit"


def test_approved_global_ticket_allows_command_and_replay_is_isolated():
    service, ticket_store = _policy()
    pending = service.evaluate(_request(
        "policy update runtime",
        {
            "actor": "ops",
            "environment_id": "prod-eu",
            "risk_class": "D4",
            "rollback_hint": "restore policy bundle v1",
        },
        "cmd_policy_gate",
    ))
    ticket_id = pending["ticket_ids"][0]
    assert ticket_store.resolve(
        ticket_id,
        "approved",
        reviewer="lead",
        reason="approved global policy update",
    ) is True

    accepted = service.evaluate(_request(
        "policy update runtime",
        {
            "actor": "ops",
            "environment_id": "prod-eu",
            "risk_class": "D4",
            "rollback_hint": "restore policy bundle v1",
            "approval_ticket_id": ticket_id,
        },
        "cmd_policy_apply",
    ))
    service.evaluate(_request(
        "rebuild system",
        {
            "actor": "ops",
            "environment_id": "staging",
            "risk_class": "D1",
            "rollback_hint": "restore staging image",
        },
        "cmd_policy_apply",
    ))

    replay = service.replay_isolated("cmd_policy_apply", environment_id="prod-eu")

    assert accepted["status"] == "approved"
    assert replay["isolation_valid"] is True
    assert replay["record_count"] == 1
    assert replay["mixed_environment_records"] == 1
    assert replay["records"][0]["environment_id"] == "prod-eu"
    assert replay["records"][0]["replay_scope"] == "isolated"


def test_multi_project_global_command_creates_ticket_per_project():
    service, ticket_store = _policy()

    result = service.evaluate(_request(
        "rebuild system",
        {
            "actor": "ops",
            "environment_id": "prod-eu",
            "risk_class": "D4",
            "rollback_hint": "restore previous container image",
            "project_ids": ["proj_easy", "proj_hard"],
        },
        "cmd_batch",
    ))

    assert result["status"] == "pending_human_gate"
    assert len(result["ticket_ids"]) == 2
    projects = {ticket_store.get(ticket_id).project_id for ticket_id in result["ticket_ids"]}
    assert projects == {"proj_easy", "proj_hard"}


def test_command_router_routes_global_mutation_through_policy(monkeypatch, tmp_path):
    ticket_store = reset_ticket_store(":memory:")
    reset_global_terminal_policy(
        tmp_path / "global_terminal.sqlite",
        evidence_spine=EvidenceSpine(":memory:"),
        ticket_store=ticket_store,
    )

    execution = execute_terminal_intent(
        "restart system",
        {
            "actor": "ops",
            "environment_id": "prod-eu",
            "risk_class": "D4",
            "rollback_hint": "restore previous supervisor unit",
        },
    )
    response = execution.to_response()

    assert response["kind"] == "text"
    assert response["meta"]["command_route"]["owner"] == "terminal.global_policy"
    assert response["meta"]["command_route"]["target_action"] == "restart_environment"
    assert response["meta"]["command_execution"]["status"] == "pending_human_gate"
    assert response["meta"]["global_terminal_policy"]["ticket_ids"]


def test_global_terminal_policy_routes_expose_isolated_replay(tmp_path):
    ticket_store = reset_ticket_store(":memory:")
    reset_global_terminal_policy(
        tmp_path / "global_terminal.sqlite",
        evidence_spine=EvidenceSpine(":memory:"),
        ticket_store=ticket_store,
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/terminal/exec",
        json={
            "line": "restart system",
            "ctx": {
                "actor": "ops",
                "environment_id": "prod-eu",
                "risk_class": "D4",
                "rollback_hint": "restore previous supervisor unit",
            },
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    command_id = body["meta"]["command_intent"]["command_id"]
    replay = client.get(
        f"/api/v1/terminal/global/replay/{command_id}",
        params={"environment_id": "prod-eu"},
    )

    assert replay.status_code == 200, replay.text
    assert replay.json()["isolation_valid"] is True
