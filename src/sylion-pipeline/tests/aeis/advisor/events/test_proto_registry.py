"""Tests for advisor event proto registry stub."""

from __future__ import annotations

from sylion.aeis.advisor.events.proto_registry import ProtoRegistry


def test_unknown_event_defaults_to_valid():
    registry = ProtoRegistry()
    assert registry.validate("aeis.advisor.test.placeholder", {"ok": True}) == (True, [])


def test_custom_validator_rejects_payload():
    registry = ProtoRegistry()
    registry.register(
        event_type="aeis.advisor.test.placeholder",
        proto_message_type="stub.PlaceholderEvent",
        validator=lambda payload: ["missing_card_id"] if "card_id" not in payload else True,
    )
    assert registry.validate("aeis.advisor.test.placeholder", {"ok": True}) == (
        False,
        ["missing_card_id"],
    )
