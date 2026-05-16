"""Service tests for advisor preferences."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from types import SimpleNamespace

from sylion.aeis.advisor.preferences.service import PreferencesService


class _FakeBus:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


def test_set_preference_emits_created(monkeypatch):
    bus = _FakeBus()
    service = PreferencesService(event_bus=bus)
    writes = []

    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service.catalog.get_preference_key_metadata",
        lambda preference_key: None,
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service._db.get_preference_row",
        lambda *args: None,
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service._db.upsert_preference",
        lambda *args: writes.append(args) or (True, None),
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service.audit.log_change",
        lambda **kwargs: "audit-1",
    )

    result = service.set_preference(
        user_id="u1",
        project_type="research",
        project_domain="software",
        preference_key="council_size",
        value=7,
    )

    assert result["success"] is True
    assert writes
    assert bus.events[-1].topic == "aeis.advisor.preferences.created"


def test_hard_change_creates_request(monkeypatch):
    bus = _FakeBus()
    service = PreferencesService(event_bus=bus)
    hard_meta = SimpleNamespace(is_hard_change=True)

    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service.catalog.get_preference_key_metadata",
        lambda preference_key: hard_meta,
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service.learning.request_hard_change",
        lambda **kwargs: SimpleNamespace(request_id="req-1"),
    )

    result = service.set_preference(
        user_id="u1",
        project_type=None,
        project_domain=None,
        preference_key="autonomy_level",
        value="auto",
    )

    assert result["requires_hard_confirmation"] is True
    assert result["hard_change_request_id"] == "req-1"
    assert bus.events[-1].topic == "aeis.advisor.preferences.hard_change_requested"


def test_get_blocked_providers_reads_effective(monkeypatch):
    service = PreferencesService(event_bus=_FakeBus())
    monkeypatch.setattr(
        service,
        "get_effective",
        lambda **kwargs: SimpleNamespace(value=["openai", "anthropic"]),
    )
    assert service.get_blocked_providers(user_id="u1") == ["openai", "anthropic"]


def test_soft_learning_tick_uses_history(monkeypatch):
    service = PreferencesService(event_bus=_FakeBus())
    signal = SimpleNamespace(
        hard_change_status="",
        preference_key="cost_sensitivity",
        proposed_value="high",
        context_project_type="research",
        context_project_domain="software",
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service.learning.apply_soft_learning",
        lambda **kwargs: (True, kwargs["preference_key"]),
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service.learning.count_pending_for_user",
        lambda user_id: 0,
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "sylion.aeis.advisor.history.service",
        SimpleNamespace(
            get_history_service=lambda: SimpleNamespace(
                list_learning_signals=lambda user_id, only_unapplied=True: [signal]
            )
        ),
    )

    result = service.soft_learning_tick(user_id="u1")
    assert result["applied_count"] == 1
    assert result["applied_preference_keys"] == ["cost_sensitivity"]


def test_concurrent_set_preference_serializes_writes_per_operator(monkeypatch):
    bus = _FakeBus()
    service = PreferencesService(event_bus=bus)
    writes: list[tuple[str, str]] = []
    overlap = {"active": 0, "detected": False}

    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service.catalog.get_preference_key_metadata",
        lambda preference_key: None,
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service._db.get_preference_row",
        lambda *args: None,
    )

    def _fake_upsert(user_id, project_type, project_domain, preference_key, value, set_by):
        overlap["active"] += 1
        if overlap["active"] > 1:
            overlap["detected"] = True
        threading.Event().wait(0.05)
        writes.append((user_id, set_by))
        overlap["active"] -= 1
        return True, None

    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service._db.upsert_preference",
        _fake_upsert,
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service.audit.log_change",
        lambda **kwargs: f"audit-{kwargs['user_id']}",
    )

    first = threading.Thread(
        target=service.set_preference,
        kwargs={
            "user_id": "op-1",
            "project_type": "research",
            "project_domain": "software",
            "preference_key": "council_size",
            "value": 5,
            "set_by": "op-1",
        },
    )
    second = threading.Thread(
        target=service.set_preference,
        kwargs={
            "user_id": "op-2",
            "project_type": "research",
            "project_domain": "software",
            "preference_key": "council_size",
            "value": 7,
            "set_by": "op-2",
        },
    )
    first.start()
    second.start()
    first.join(timeout=2)
    second.join(timeout=2)

    assert overlap["detected"] is False
    assert sorted(writes) == [("op-1", "op-1"), ("op-2", "op-2")]
    assert [event.topic for event in bus.events] == [
        "aeis.advisor.preferences.created",
        "aeis.advisor.preferences.created",
    ]


def test_reset_preference_does_not_apply_pending_hard_change(monkeypatch):
    bus = _FakeBus()
    service = PreferencesService(event_bus=bus)
    hard_meta = SimpleNamespace(is_hard_change=True)

    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service.catalog.get_preference_key_metadata",
        lambda preference_key: hard_meta,
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service.learning.request_hard_change",
        lambda **kwargs: SimpleNamespace(request_id="req-conflict"),
    )
    deleted = {
        "preference_value": "manual",
        "project_type": "research",
        "project_domain": "software",
    }
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service._db.delete_preference",
        lambda *args: deleted,
    )
    audit_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service.audit.log_change",
        lambda **kwargs: audit_calls.append(kwargs) or "audit-reset",
    )

    result = service.set_preference(
        user_id="u1",
        project_type="research",
        project_domain="software",
        preference_key="autonomy_level",
        value="full_auto",
    )
    reset = service.reset_preference(
        user_id="u1",
        project_type="research",
        project_domain="software",
        preference_key="autonomy_level",
        reason="operator_conflict_resolution",
    )

    assert result["requires_hard_confirmation"] is True
    assert result["hard_change_request_id"] == "req-conflict"
    assert reset is True
    assert audit_calls[0]["change_type"] == "RESET"
    assert audit_calls[0]["new_value"] is None
    assert [event.topic for event in bus.events] == [
        "aeis.advisor.preferences.hard_change_requested",
        "aeis.advisor.preferences.reset",
    ]


def test_duplicate_catalog_extension_returns_none(monkeypatch):
    bus = _FakeBus()
    service = PreferencesService(event_bus=bus)
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service.catalog.add_custom_entry",
        lambda **kwargs: None,
    )

    entry = service.add_custom_catalog_entry(
        catalog_type="project_domain",
        entry_id="custom:finance",
        display_name="Finance",
        description="Duplicate domain",
        created_by="op-1",
    )

    assert entry is None
    assert bus.events == []


def test_audit_history_replays_after_service_restart(monkeypatch):
    audit_rows = [
        SimpleNamespace(
            audit_id="audit-2",
            user_id="u1",
            project_type="research",
            project_domain="software",
            preference_key="cost_sensitivity",
            old_value="medium",
            new_value="high",
            change_type="UPDATE",
            changed_by="user",
            changed_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
            reason="crash_recovery_replay",
        )
    ]
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.service.audit.get_history",
        lambda *args, **kwargs: audit_rows,
    )

    first = PreferencesService(event_bus=_FakeBus())
    restarted = PreferencesService(event_bus=_FakeBus())

    assert first.get_audit(user_id="u1")[0].audit_id == "audit-2"
    assert restarted.get_audit(user_id="u1")[0].reason == "crash_recovery_replay"
