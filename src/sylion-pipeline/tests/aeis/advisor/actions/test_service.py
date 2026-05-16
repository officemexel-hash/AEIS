from __future__ import annotations

import pytest
from types import SimpleNamespace

from sylion.aeis.advisor.actions._models import ActionContext, CardAction
from sylion.aeis.advisor.actions.service import ActionsService


def test_handle_action_logs_and_emits(monkeypatch):
    events: list[str] = []
    audits: list[tuple[str, str]] = []

    class Bus:
        def publish(self, event):
            events.append(event.topic)
            return event.event_id

    monkeypatch.setattr(
        "sylion.aeis.advisor.actions.service.get_handler",
        lambda action: SimpleNamespace(
            handle=lambda ctx: SimpleNamespace(
                success=True,
                routed_to_module="advisor_engine",
                routed_target_id=ctx.card_id,
                payload_sent={"card_id": ctx.card_id},
                response={"status": "ok"},
                error_message=None,
                soft_learning_triggered=True,
                hard_learning_pending=False,
            )
        ),
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.actions.service.audit.log_route",
        lambda **kwargs: audits.append((kwargs["card_id"], kwargs["action"].value)) or "route-1",
    )
    svc = ActionsService(event_bus=Bus())
    response = svc.HandleAction(
        ActionContext(card_id="card-1", action=CardAction.ACCEPT, operator_id="op-1")
    )
    assert response.action_event_id == "route-1"
    assert audits == [("card-1", "accept")]
    assert events == ["aeis.advisor.actions.action_routed"]


def test_dont_learn_flag_stacks_before_primary(monkeypatch):
    seen: list[str] = []

    def fake_get_handler(action):
        return SimpleNamespace(
            handle=lambda ctx: seen.append(action.value) or SimpleNamespace(
                success=True,
                routed_to_module="advisor_engine",
                routed_target_id=ctx.card_id,
                payload_sent={"card_id": ctx.card_id},
                response={},
                error_message=None,
                soft_learning_triggered=False,
                hard_learning_pending=False,
            )
        )

    monkeypatch.setattr("sylion.aeis.advisor.actions.service.get_handler", fake_get_handler)
    monkeypatch.setattr("sylion.aeis.advisor.actions.service.audit.log_route", lambda **kwargs: "route-1")
    svc = ActionsService(event_bus=SimpleNamespace(publish=lambda event: event.event_id))
    svc.HandleAction(
        ActionContext(
            card_id="card-1",
            action=CardAction.ACCEPT,
            operator_id="op-1",
            dont_learn_flag=True,
        )
    )
    assert seen == ["dont_learn_from_this", "accept"]


def test_retry_failed_returns_status(monkeypatch):
    monkeypatch.setattr(
        "sylion.aeis.advisor.actions.service.retry_route",
        lambda route_audit_id: (True, "success", None),
    )
    svc = ActionsService(event_bus=SimpleNamespace(publish=lambda event: event.event_id))
    response = svc.RetryFailed(SimpleNamespace(route_audit_id="route-1"))
    assert response.success is True
    assert response.status == "success"


@pytest.mark.parametrize("action", list(CardAction))
def test_all_actions_respect_dont_learn_stacking(monkeypatch, action):
    seen: list[str] = []

    def fake_get_handler(requested_action):
        return SimpleNamespace(
            handle=lambda ctx: seen.append(requested_action.value) or SimpleNamespace(
                success=True,
                routed_to_module="advisor_engine",
                routed_target_id=f"{requested_action.value}-id",
                payload_sent={"card_id": ctx.card_id},
                response={},
                error_message=None,
                soft_learning_triggered=False,
                hard_learning_pending=False,
            )
        )

    monkeypatch.setattr("sylion.aeis.advisor.actions.service.get_handler", fake_get_handler)
    monkeypatch.setattr("sylion.aeis.advisor.actions.service.audit.log_route", lambda **kwargs: "route-1")
    svc = ActionsService(event_bus=SimpleNamespace(publish=lambda event: event.event_id))

    svc.HandleAction(
        ActionContext(
            card_id=f"card-{action.value}",
            action=action,
            operator_id="op-1",
            dont_learn_flag=True,
            preference_key="cost_sensitivity" if action == CardAction.SAVE_AS_PREFERENCE else None,
            preference_value="high" if action == CardAction.SAVE_AS_PREFERENCE else None,
        )
    )

    expected = ["dont_learn_from_this", action.value]
    if action == CardAction.DONT_LEARN_FROM_THIS:
        expected = ["dont_learn_from_this"]
    assert seen == expected


def test_convert_to_human_gate_unavailable_degrades_gracefully(monkeypatch):
    events: list[str] = []
    audits: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        "sylion.aeis.advisor.actions.service.get_handler",
        lambda action: SimpleNamespace(
            handle=lambda ctx: SimpleNamespace(
                success=False,
                routed_to_module="human_gate",
                routed_target_id=None,
                payload_sent={"card_id": ctx.card_id},
                response={"degraded": True},
                error_message="human_gate_unavailable",
                soft_learning_triggered=False,
                hard_learning_pending=False,
            )
        ),
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.actions.service.audit.log_route",
        lambda **kwargs: audits.append((kwargs["card_id"], kwargs["action"].value, kwargs["status"].value)) or "route-hg",
    )
    svc = ActionsService(event_bus=SimpleNamespace(publish=lambda event: events.append(event.topic) or event.event_id))

    response = svc.HandleAction(
        ActionContext(
            card_id="card-hg",
            action=CardAction.CONVERT_TO_HUMAN_GATE,
            operator_id="op-1",
        )
    )

    assert response.error_message == "human_gate_unavailable"
    assert response.created_human_gate_ticket_id == ""
    assert audits == [("card-hg", "convert_to_human_gate", "failed")]
    assert events == ["aeis.advisor.actions.routing_failed"]


def test_save_as_preference_unknown_key_routes_error(monkeypatch):
    events: list[str] = []

    def fake_get_handler(action):
        if action == CardAction.SAVE_AS_PREFERENCE:
            return SimpleNamespace(
                handle=lambda ctx: SimpleNamespace(
                    success=False,
                    routed_to_module="advisor_preferences",
                    routed_target_id=None,
                    payload_sent={"preference_key": ctx.preference_key},
                    response={"success": False},
                    error_message="unknown_preference_key",
                    soft_learning_triggered=False,
                    hard_learning_pending=False,
                )
            )
        return SimpleNamespace(
            handle=lambda ctx: SimpleNamespace(
                success=True,
                routed_to_module="advisor_engine",
                routed_target_id=ctx.card_id,
                payload_sent={"card_id": ctx.card_id},
                response={},
                error_message=None,
                soft_learning_triggered=False,
                hard_learning_pending=False,
            )
        )

    monkeypatch.setattr("sylion.aeis.advisor.actions.service.get_handler", fake_get_handler)
    monkeypatch.setattr("sylion.aeis.advisor.actions.service.audit.log_route", lambda **kwargs: "route-pref")
    svc = ActionsService(event_bus=SimpleNamespace(publish=lambda event: events.append(event.topic) or event.event_id))

    response = svc.HandleAction(
        ActionContext(
            card_id="card-pref",
            action=CardAction.SAVE_AS_PREFERENCE,
            operator_id="op-1",
            preference_key="not_in_catalog",
            preference_value="x",
        )
    )

    assert response.saved_preference_id == ""
    assert response.error_message == "unknown_preference_key"
    assert events == ["aeis.advisor.actions.routing_failed"]
