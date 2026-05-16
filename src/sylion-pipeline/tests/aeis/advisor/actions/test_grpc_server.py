"""Tests for advisor actions gRPC wrapper."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from sylion.aeis.advisor.actions.grpc_server import ActionsServicer
from sylion.aeis.advisor.actions._models import CardAction, RouteAuditRow, RouteStatus


def test_handle_action_maps_result_to_proto():
    service = SimpleNamespace(
        HandleAction=lambda request: SimpleNamespace(
            action_event_id="evt-1",
            recorded_at=datetime.now(timezone.utc),
            soft_learning_triggered=True,
            hard_learning_pending_confirmation=False,
            created_human_gate_ticket_id="",
            created_masterplan_proposal_id="",
            saved_preference_id="pref-1",
            error_message="",
        )
    )
    response = ActionsServicer(service=service).HandleAction(
        SimpleNamespace(
            card_id="card-1",
            action=8,
            operator_id="op-1",
            operator_note="",
            modified_recommendation="",
            preference_key="cost_sensitivity",
            preference_project_type="",
            preference_project_domain="",
            preference_value=SimpleNamespace(ListFields=lambda: []),
            dont_learn_flag=False,
        ),
        None,
    )
    assert response.action_event_id == "evt-1"
    assert response.saved_preference_id == "pref-1"


def test_get_routing_audit_maps_entries():
    row = RouteAuditRow(
        route_audit_id="route-1",
        card_id="card-1",
        action=CardAction.ACCEPT,
        routed_to_module="sylion.test",
        routed_target_id="target-1",
        payload_sent={"ok": True},
        response={"done": True},
        status=RouteStatus.SUCCESS,
        error_message=None,
        routed_at=datetime.now(timezone.utc),
    )
    service = SimpleNamespace(
        GetRoutingAudit=lambda request: SimpleNamespace(entries=[row])
    )
    response = ActionsServicer(service=service).GetRoutingAudit(
        SimpleNamespace(card_id="card-1"),
        None,
    )
    assert response.entries[0].route_audit_id == "route-1"
    assert response.entries[0].routed_to_module == "sylion.test"
