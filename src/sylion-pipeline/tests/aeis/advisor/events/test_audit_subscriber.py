"""Tests for advisor audit subscriber."""

from __future__ import annotations

import time
from types import SimpleNamespace

from sylion.aeis.advisor.events.audit_subscriber import (
    AdvisorAuditSubscriber,
    get_or_create_advisor_audit_subscriber,
    reset_advisor_audit_subscriber,
)
from sylion.aeis.advisor.events.proto_registry import ProtoRegistry
from sylion.core.event_bus import SylionEvent


class _FakeCursor:
    def __init__(self, statements):
        self._statements = statements

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params):
        self._statements.append((sql, params))


class _FakeConnection:
    def __init__(self, statements):
        self._statements = statements

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._statements)


class _FakePool:
    def __init__(self):
        self.statements = []

    def connection(self):
        return _FakeConnection(self.statements)


class _FakeBackbone:
    def __init__(self):
        self.subscriptions = []

    def subscribe(self, topic, handler):
        self.subscriptions.append((topic, handler))


def _install_fake_pg(monkeypatch, pool):
    monkeypatch.setenv("SYLION_ADVISOR_FORCE_PG", "1")
    monkeypatch.setattr(
        "sylion.aeis.advisor.events.audit_subscriber.get_pool",
        lambda: pool,
    )


def test_valid_event_lands_in_events_table(monkeypatch):
    pool = _FakePool()
    backbone = _FakeBackbone()
    _install_fake_pg(monkeypatch, pool)
    subscriber = AdvisorAuditSubscriber(
        event_backbone=backbone,
        proto_registry=ProtoRegistry(),
    )
    subscriber._on_event(
        SylionEvent(
            event_id="evt-1",
            topic="aeis.advisor.test.placeholder",
            payload={"card_id": "card-1"},
            source_module="tests",
            timestamp=1.0,
        )
    )
    assert backbone.subscriptions[0][0] == "*"
    assert "INSERT INTO advisor_events.events" in pool.statements[0][0]


def test_invalid_event_lands_in_validation_failures(monkeypatch):
    pool = _FakePool()
    backbone = _FakeBackbone()
    registry = ProtoRegistry()
    registry.register(
        event_type="aeis.advisor.test.placeholder",
        proto_message_type="stub.PlaceholderEvent",
        validator=lambda payload: ["missing_card_id"],
    )
    _install_fake_pg(monkeypatch, pool)
    subscriber = AdvisorAuditSubscriber(
        event_backbone=backbone,
        proto_registry=registry,
    )
    subscriber._on_event(
        SylionEvent(
            event_id="evt-2",
            topic="aeis.advisor.test.placeholder",
            payload={"nope": True},
            source_module="tests",
            timestamp=1.0,
        )
    )
    assert "INSERT INTO advisor_events.validation_failures" in pool.statements[0][0]


def test_audit_subscriber_handles_burst_load(monkeypatch):
    pool = _FakePool()
    backbone = _FakeBackbone()
    _install_fake_pg(monkeypatch, pool)
    subscriber = AdvisorAuditSubscriber(
        event_backbone=backbone,
        proto_registry=ProtoRegistry(),
    )

    started = time.perf_counter()
    for index in range(1000):
        subscriber._on_event(
            SylionEvent(
                event_id=f"evt-{index}",
                topic="aeis.advisor.test.placeholder",
                payload={"card_id": f"card-{index}"},
                source_module="tests",
                timestamp=float(index),
            )
        )
    elapsed = time.perf_counter() - started

    assert len(pool.statements) == 1000
    assert elapsed < 1.5


def test_malformed_payload_is_rejected_by_proto_registry():
    registry = ProtoRegistry()

    is_valid, errors = registry.validate("aeis.advisor.test.placeholder", "not-a-dict")  # type: ignore[arg-type]

    assert is_valid is False
    assert errors == ["payload_must_be_object"]


def test_event_replay_after_restart_reuses_singleton(monkeypatch):
    pool = _FakePool()
    backbone = _FakeBackbone()
    _install_fake_pg(monkeypatch, pool)

    reset_advisor_audit_subscriber()
    first = get_or_create_advisor_audit_subscriber(
        event_backbone=backbone,
        proto_registry=ProtoRegistry(),
    )
    first._on_event(
        SylionEvent(
            event_id="evt-replay-1",
            topic="aeis.advisor.test.placeholder",
            payload={"card_id": "card-1"},
            source_module="tests",
            timestamp=1.0,
        )
    )

    reset_advisor_audit_subscriber()
    restarted = get_or_create_advisor_audit_subscriber(
        event_backbone=backbone,
        proto_registry=ProtoRegistry(),
    )
    restarted._on_event(
        SylionEvent(
            event_id="evt-replay-2",
            topic="aeis.advisor.test.placeholder",
            payload={"card_id": "card-2"},
            source_module="tests",
            timestamp=2.0,
        )
    )

    assert first is not restarted
    assert len(backbone.subscriptions) == 2
    assert len(pool.statements) == 2
