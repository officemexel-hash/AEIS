"""Smoke tests for advisor audit subscriber bootstrap."""

from __future__ import annotations

from types import SimpleNamespace

from sylion.api.app import _bootstrap_advisor_audit_subscriber


def test_bootstrap_initializes_subscriber(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "sylion.aeis.advisor.events.get_or_create_advisor_audit_subscriber",
        lambda **kwargs: captured.setdefault("kwargs", kwargs) or SimpleNamespace(),
    )
    _bootstrap_advisor_audit_subscriber("event-backbone")
    assert captured["kwargs"]["event_backbone"] == "event-backbone"
