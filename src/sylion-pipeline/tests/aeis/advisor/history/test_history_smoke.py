"""Smoke tests for advisor.history — golden minimums per manifest §9.

Mirror the engine smoke-test setup (isolated SQLite + singleton reset). The
preferences module is intentionally not wired here; soft_learning therefore
falls back to `applied=false, reason=preferences_grpc_unreachable`, which is
the documented stub-mode behaviour for WP6.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SYLION_RBAC_DISABLED", "1")
os.environ.setdefault("SYLION_RATE_LIMIT_DISABLED", "1")

from sylion.aeis.advisor.history.confidence_provider.historical_acceptance import (
    get_historical_acceptance_snapshot,
)
from sylion.aeis.advisor.history.confidence_provider.history_match import (
    get_history_match_snapshot,
)
from sylion.aeis.advisor.history.partition_manager import create_next_partitions
from sylion.aeis.advisor.history.service import (
    HISTORY_SUBSCRIBED_TOPICS,
    get_history_service,
)
from sylion.core.event_bus import EventBus, SylionEvent


class _CapturingBus:
    """Minimal event_bus shim that records publishes and dispatches subscribes."""

    def __init__(self):
        self.events: list[SylionEvent] = []
        self._subs: dict[str, list] = {}

    def publish(self, event):
        self.events.append(event)
        for handler in self._subs.get(event.topic, []):
            handler(event)
        return event.event_id

    def subscribe(self, topic, handler):
        self._subs.setdefault(topic, []).append(handler)


def _accept_context(rec_type: str = "REC_TYPE_PURCHASE_PLAN", **extra) -> dict:
    ctx = {
        "recommendation_type": rec_type,
        "project_type": "research",
        "project_domain": "funding",
    }
    ctx.update(extra)
    return ctx


def test_record_action_persists_row_and_emits_event():
    """Golden: record_action_persists_row_and_emits_event."""
    bus = _CapturingBus()
    svc = get_history_service()
    svc.attach_to_event_bus(bus)

    aid = svc.record_action(
        card_id="c-1",
        operator_id="op-1",
        action="accept",
        context=_accept_context(),
    )
    assert aid

    actions = svc.list_actions_for_card("c-1")
    assert len(actions) == 1
    assert actions[0].action == "accept"
    assert actions[0].operator_id == "op-1"
    assert actions[0].context["recommendation_type"] == "REC_TYPE_PURCHASE_PLAN"

    topics = [e.topic for e in bus.events]
    assert "aeis.advisor.history.action_recorded" in topics


def test_dont_learn_flag_skips_learning_signal_creation():
    """Golden: dont_learn_flag_skips_learning_signal_creation."""
    bus = _CapturingBus()
    svc = get_history_service()
    svc.attach_to_event_bus(bus)

    # Build a streak that would normally trigger soft learning, then mark
    # one with dont_learn=true and confirm the skip path fires.
    for i in range(4):
        svc.record_action(
            card_id=f"c-{i}",
            operator_id="op-1",
            action="accept",
            context=_accept_context(),
        )

    bus.events.clear()
    svc.record_action(
        card_id="c-skip",
        operator_id="op-1",
        action="accept",
        context=_accept_context(dont_learn=True),
    )

    topics = [e.topic for e in bus.events]
    assert "aeis.advisor.history.action_recorded" in topics
    assert "aeis.advisor.history.skip_learning_recorded" in topics
    assert "aeis.advisor.history.learning_signal_emitted" not in topics

    signals = svc.list_learning_signals("op-1")
    # No new signal from the skipped row (signals from earlier rows may exist).
    for s in signals:
        assert s.source_card_id != "c-skip"


def test_soft_learning_triggers_after_threshold_accept_streak():
    """Golden: soft_learning_triggers_after_threshold_accept_streak."""
    bus = _CapturingBus()
    svc = get_history_service()
    svc.attach_to_event_bus(bus)

    for i in range(5):
        svc.record_action(
            card_id=f"c-{i}",
            operator_id="op-1",
            action="accept",
            context=_accept_context(),
        )

    topics = [e.topic for e in bus.events]
    assert "aeis.advisor.history.learning_signal_emitted" in topics
    assert "aeis.advisor.history.soft_learning_applied" in topics

    signals = svc.list_learning_signals("op-1")
    assert any(s.signal_type == "card_acceptance" for s in signals)
    assert any(s.signal_strength >= 0.7 for s in signals)

    # Preferences module isn't wired here -> applied=False is the documented
    # stub-mode behaviour.
    soft_events = [
        e for e in bus.events if e.topic == "aeis.advisor.history.soft_learning_applied"
    ]
    assert soft_events
    assert any(
        e.payload.get("reason") == "preferences_grpc_unreachable"
        for e in soft_events
    )


def test_hard_change_request_emits_event_and_pendable_for_confirmation():
    """Golden: hard_change_request_emits_event_and_pendable_for_confirmation."""
    bus = _CapturingBus()
    svc = get_history_service()
    svc.attach_to_event_bus(bus)

    svc.record_action(
        card_id="c-save",
        operator_id="op-1",
        action="save_as_preference",
        context=_accept_context(preference_key="prefer_local_models"),
    )

    topics = [e.topic for e in bus.events]
    assert "aeis.advisor.history.hard_change_requested" in topics

    pending = svc.list_pending_hard_change_requests("op-1")
    assert len(pending) == 1
    signal_id = pending[0]["signal_id"]
    assert pending[0]["preference_key"] == "prefer_local_models"

    # Reject path -> status flips, no further apply attempt.
    rejected = svc.reject_hard_change(signal_id=signal_id, operator_id="op-1")
    assert rejected is True
    assert not svc.list_pending_hard_change_requests("op-1")

    # Second save -> confirm path.
    svc.record_action(
        card_id="c-save-2",
        operator_id="op-1",
        action="save_as_preference",
        context=_accept_context(preference_key="prefer_local_models_v2"),
    )
    pending_2 = svc.list_pending_hard_change_requests("op-1")
    assert len(pending_2) == 1
    confirmed = svc.confirm_hard_change(
        signal_id=pending_2[0]["signal_id"], operator_id="op-1"
    )
    assert confirmed is True
    assert not svc.list_pending_hard_change_requests("op-1")


def test_confidence_provider_history_match_returns_expected_shape():
    """Golden: confidence_provider_history_match_returns_expected_shape."""
    svc = get_history_service()

    svc.record_action(
        card_id="c-a", operator_id="op-1", action="accept", context=_accept_context()
    )
    svc.record_action(
        card_id="c-b", operator_id="op-1", action="accept", context=_accept_context()
    )
    svc.record_action(
        card_id="c-c", operator_id="op-1", action="reject", context=_accept_context()
    )

    snap = get_history_match_snapshot(
        operator_id="op-1",
        recommendation_type="REC_TYPE_PURCHASE_PLAN",
        project_type="research",
        project_domain="funding",
    )
    assert set(snap.keys()) == {
        "similar_accepted_count",
        "similar_rejected_count",
        "similar_acceptance_rate",
    }
    assert snap["similar_accepted_count"] == 2
    assert snap["similar_rejected_count"] == 1
    assert snap["similar_acceptance_rate"] == pytest.approx(2 / 3)

    # Unknown operator -> zero / 0.0 (not a crash, not a divide-by-zero).
    empty = get_history_match_snapshot(
        operator_id="op-empty",
        recommendation_type="REC_TYPE_PURCHASE_PLAN",
    )
    assert empty["similar_acceptance_rate"] == 0.0


def test_confidence_provider_historical_acceptance_returns_expected_shape():
    """Golden: confidence_provider_historical_acceptance_returns_expected_shape."""
    svc = get_history_service()

    for i in range(3):
        svc.record_action(
            card_id=f"a-{i}",
            operator_id="op-1",
            action="accept",
            context=_accept_context(),
        )
    svc.record_action(
        card_id="r-1", operator_id="op-1", action="reject", context=_accept_context()
    )

    snap = get_historical_acceptance_snapshot(
        operator_id="op-1", recommendation_type="REC_TYPE_PURCHASE_PLAN"
    )
    assert set(snap.keys()) == {
        "operator_accepted_count",
        "operator_rejected_count",
        "operator_acceptance_rate_for_type",
    }
    assert snap["operator_accepted_count"] == 3
    assert snap["operator_rejected_count"] == 1
    assert snap["operator_acceptance_rate_for_type"] == pytest.approx(0.75)


def test_partition_manager_noop_on_sqlite_returns_zero():
    """Golden: partition_manager_noop_on_sqlite_returns_zero."""
    # SYLION_ADVISOR_HISTORY_SQLITE is set by the autouse fixture -> SQLite mode.
    created = create_next_partitions(months_ahead=3)
    assert created == 0


def test_inbound_action_routed_subscription_records_action():
    """Sanity: actions.action_routed -> recorder triggers."""
    bus = _CapturingBus()
    svc = get_history_service()
    n = svc.attach_to_event_bus(bus)
    assert n >= len(HISTORY_SUBSCRIBED_TOPICS)

    inbound = SylionEvent(
        event_id="e-1",
        topic="aeis.advisor.actions.action_routed",
        payload={
            "card_id": "c-routed-1",
            "operator_id": "op-2",
            "action": "accept",
            "context": _accept_context(),
        },
        source_module="sylion.aeis.advisor.actions",
        timestamp=0.0,
    )
    bus.publish(inbound)

    actions = svc.list_actions_for_card("c-routed-1")
    assert len(actions) == 1
    topics = [e.topic for e in bus.events]
    assert "aeis.advisor.history.action_recorded" in topics


def test_real_event_bus_publish_subscribe_round_trip():
    """Use the real `EventBus` to confirm we work with the production class."""
    bus = EventBus()
    try:
        svc = get_history_service()
        svc.attach_to_event_bus(bus)
        svc.record_action(
            card_id="c-real",
            operator_id="op-real",
            action="accept",
            context=_accept_context(),
        )
        actions = svc.list_actions_for_card("c-real")
        assert len(actions) == 1
    finally:
        bus._conn.close()
