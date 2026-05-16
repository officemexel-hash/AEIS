from __future__ import annotations

from sylion.aeis.advisor.actions._models import ActionContext, CardAction
from sylion.aeis.advisor.actions.handlers.accept_handler import AcceptHandler
from sylion.aeis.advisor.actions.handlers.human_gate_handler import HumanGateHandler
from sylion.aeis.advisor.actions.handlers.preference_handler import PreferenceHandler


def test_accept_handler_triggers_soft_learning(monkeypatch):
    monkeypatch.setattr(
        "sylion.aeis.advisor.actions.handlers.accept_handler.append_card_tag",
        lambda card_id, tag: (card_id, tag),
    )
    result = AcceptHandler().handle(
        ActionContext(card_id="card-1", action=CardAction.ACCEPT, operator_id="op-1")
    )
    assert result.success is True
    assert result.soft_learning_triggered is True


def test_human_gate_handler_creates_ticket(monkeypatch):
    monkeypatch.setattr(
        "sylion.aeis.advisor.actions.handlers.human_gate_handler.fetch_card_snapshot",
        lambda card_id: (card_id, "Title", "Why", "D3", None, "project-1", {}),
    )
    result = HumanGateHandler().handle(
        ActionContext(
            card_id="card-1",
            action=CardAction.CONVERT_TO_HUMAN_GATE,
            operator_id="op-1",
        )
    )
    assert result.success is True
    assert result.routed_to_module == "human_gate"
    assert result.routed_target_id


def test_preference_handler_requires_module(monkeypatch):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "sylion.aeis.advisor.preferences.service":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    result = PreferenceHandler().handle(
        ActionContext(
            card_id="card-1",
            action=CardAction.SAVE_AS_PREFERENCE,
            operator_id="op-1",
            preference_key="cost_sensitivity",
            preference_value="high",
        )
    )
    assert result.success is False
    assert result.error_message == "preferences_module_unavailable"
