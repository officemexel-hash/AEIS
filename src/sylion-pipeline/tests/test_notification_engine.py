"""Tests for SYLION Monitoring -- Notification Engine.

40 tests covering channel CRUD, rule CRUD, notification send/read,
severity filtering, stats, EventBus integration, singleton, and edge cases.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.monitoring.notification_engine import (
    NotificationEngine,
    get_notification_engine,
    reset_notification_engine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_notification_engine()
    yield
    reset_notification_engine()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def ne(bus):
    return NotificationEngine(db_path=":memory:", event_bus=bus)


@pytest.fixture
def ne_no_bus():
    return NotificationEngine(db_path=":memory:")


# ===========================================================================
# 1. Channel CRUD
# ===========================================================================

class TestChannelCRUD:
    def test_create_channel_returns_dict(self, ne):
        ch = ne.create_channel("ops-email", "email", '{"to": "ops@example.com"}')
        assert ch["channel_id"]
        assert ch["name"] == "ops-email"
        assert ch["channel_type"] == "email"
        assert ch["enabled"] is True
        assert ch["created_at"] > 0

    def test_create_channel_invalid_type_raises(self, ne):
        with pytest.raises(ValueError, match="Invalid channel_type"):
            ne.create_channel("bad", "carrier_pigeon")

    def test_create_channel_with_dict_config(self, ne):
        ch = ne.create_channel("webhook", "webhook", {"url": "http://hook.test"})
        assert ch["config"] is not None

    def test_create_channel_with_none_config(self, ne):
        ch = ne.create_channel("in-app", "in_app", None)
        assert ch["channel_id"]

    def test_update_channel_name(self, ne):
        ch = ne.create_channel("orig", "email")
        updated = ne.update_channel(ch["channel_id"], name="renamed")
        assert updated["name"] == "renamed"

    def test_update_channel_config(self, ne):
        ch = ne.create_channel("cfg", "webhook", {"old": 1})
        updated = ne.update_channel(ch["channel_id"],
                                     config_json={"new": 2})
        assert updated is not None

    def test_update_channel_enabled(self, ne):
        ch = ne.create_channel("tog", "slack")
        updated = ne.update_channel(ch["channel_id"], enabled=False)
        assert updated["enabled"] == 0

    def test_update_nonexistent_channel_returns_none(self, ne):
        assert ne.update_channel("nope", name="x") is None

    def test_update_channel_invalid_type_raises(self, ne):
        ch = ne.create_channel("x", "email")
        with pytest.raises(ValueError, match="Invalid channel_type"):
            ne.update_channel(ch["channel_id"], channel_type="fax")

    def test_delete_channel_exists(self, ne):
        ch = ne.create_channel("del-me", "email")
        assert ne.delete_channel(ch["channel_id"]) is True

    def test_delete_channel_not_exists(self, ne):
        assert ne.delete_channel("ghost") is False

    def test_list_channels_all(self, ne):
        ne.create_channel("a", "email")
        ne.create_channel("b", "webhook")
        channels = ne.list_channels()
        assert len(channels) == 2

    def test_list_channels_filtered_by_type(self, ne):
        ne.create_channel("email1", "email")
        ne.create_channel("hook1", "webhook")
        ne.create_channel("email2", "email")
        email_chs = ne.list_channels(channel_type="email")
        assert len(email_chs) == 2
        assert all(c["channel_type"] == "email" for c in email_chs)

    def test_list_channels_empty(self, ne):
        assert ne.list_channels() == []


# ===========================================================================
# 2. Rule CRUD
# ===========================================================================

class TestRuleCRUD:
    def test_create_rule_returns_dict(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("high-sev", ch["channel_id"],
                              '{"severity": "critical"}', "critical")
        assert rule["rule_id"]
        assert rule["name"] == "high-sev"
        assert rule["channel_id"] == ch["channel_id"]
        assert rule["enabled"] is True

    def test_create_rule_with_dict_condition(self, ne):
        ch = ne.create_channel("ch2", "webhook")
        rule = ne.create_rule("dict-cond", ch["channel_id"],
                              {"metric": "cpu", "gt": 90})
        assert rule["trigger_condition"] is not None

    def test_create_rule_no_condition(self, ne):
        ch = ne.create_channel("ch3", "in_app")
        rule = ne.create_rule("bare", ch["channel_id"])
        assert rule["rule_id"]

    def test_update_rule_name(self, ne):
        ch = ne.create_channel("ch4", "slack")
        rule = ne.create_rule("orig", ch["channel_id"])
        updated = ne.update_rule(rule["rule_id"], name="new-name")
        assert updated["name"] == "new-name"

    def test_update_rule_severity_filter(self, ne):
        ch = ne.create_channel("ch5", "email")
        rule = ne.create_rule("sf", ch["channel_id"])
        updated = ne.update_rule(rule["rule_id"], severity_filter="critical")
        assert updated["severity_filter"] == "critical"

    def test_update_rule_disabled(self, ne):
        ch = ne.create_channel("ch6", "webhook")
        rule = ne.create_rule("dis", ch["channel_id"])
        updated = ne.update_rule(rule["rule_id"], enabled=False)
        assert updated["enabled"] == 0

    def test_update_nonexistent_rule_returns_none(self, ne):
        assert ne.update_rule("nope", name="x") is None

    def test_delete_rule_exists(self, ne):
        ch = ne.create_channel("ch7", "email")
        rule = ne.create_rule("del", ch["channel_id"])
        assert ne.delete_rule(rule["rule_id"]) is True

    def test_delete_rule_not_exists(self, ne):
        assert ne.delete_rule("ghost") is False

    def test_list_rules_all(self, ne):
        ch = ne.create_channel("ch8", "slack")
        ne.create_rule("r1", ch["channel_id"])
        ne.create_rule("r2", ch["channel_id"])
        assert len(ne.list_rules()) == 2

    def test_list_rules_filtered_by_channel(self, ne):
        ch_a = ne.create_channel("ca", "email")
        ch_b = ne.create_channel("cb", "webhook")
        ne.create_rule("ra", ch_a["channel_id"])
        ne.create_rule("rb", ch_b["channel_id"])
        rules_a = ne.list_rules(channel_id=ch_a["channel_id"])
        assert len(rules_a) == 1
        assert rules_a[0]["name"] == "ra"


# ===========================================================================
# 3. Send notification
# ===========================================================================

class TestSendNotification:
    def test_send_notification_basic(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        result = ne.send_notification(rule["rule_id"], "Test", "Body",
                                       "info")
        assert result["notification_id"]
        assert result["status"] == "unread"
        assert result["title"] == "Test"

    def test_send_notification_with_metadata(self, ne):
        ch = ne.create_channel("ch", "webhook")
        rule = ne.create_rule("r", ch["channel_id"])
        result = ne.send_notification(rule["rule_id"], "T", "M", "warning",
                                       metadata_json={"key": "val"})
        assert result["notification_id"]

    def test_send_notification_invalid_severity(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        with pytest.raises(ValueError, match="Invalid severity"):
            ne.send_notification(rule["rule_id"], "T", "M", "extreme")

    def test_send_notification_invalid_rule(self, ne):
        with pytest.raises(ValueError, match="not found"):
            ne.send_notification("nonexistent", "T", "M")

    def test_send_notification_disabled_rule(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        ne.update_rule(rule["rule_id"], enabled=False)
        with pytest.raises(ValueError, match="disabled"):
            ne.send_notification(rule["rule_id"], "T", "M")

    def test_send_notification_severity_filtered(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"],
                              severity_filter="critical")
        result = ne.send_notification(rule["rule_id"], "T", "M", "info")
        assert result["status"] == "filtered"
        assert result["notification_id"] is None

    def test_send_notification_severity_passes_filter(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"],
                              severity_filter="warning")
        result = ne.send_notification(rule["rule_id"], "T", "M", "critical")
        assert result["notification_id"]
        assert result["status"] == "unread"

    def test_send_notification_severity_exact_filter(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"],
                              severity_filter="warning")
        result = ne.send_notification(rule["rule_id"], "T", "M", "warning")
        assert result["notification_id"]
        assert result["status"] == "unread"

    def test_send_creates_log_entry(self, ne):
        ch = ne.create_channel("ch", "slack")
        rule = ne.create_rule("r", ch["channel_id"])
        ne.send_notification(rule["rule_id"], "T", "M")
        stats = ne.get_stats()
        assert stats["total_log_entries"] == 1

    def test_send_all_valid_severities(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        for sev in ("info", "warning", "urgent", "critical"):
            result = ne.send_notification(rule["rule_id"], "T", "M", sev)
            assert result["severity"] == sev


# ===========================================================================
# 4. Get notifications / mark read
# ===========================================================================

class TestNotifications:
    def test_get_notifications_all(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        ne.send_notification(rule["rule_id"], "A", "a")
        ne.send_notification(rule["rule_id"], "B", "b")
        notifs = ne.get_notifications()
        assert len(notifs) == 2

    def test_get_notifications_by_status(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        r1 = ne.send_notification(rule["rule_id"], "A", "a")
        ne.mark_read(r1["notification_id"])
        unread = ne.get_notifications(status="unread")
        read = ne.get_notifications(status="read")
        assert len(unread) == 0
        assert len(read) == 1

    def test_get_notifications_limit(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        for i in range(10):
            ne.send_notification(rule["rule_id"], f"T{i}", "m")
        notifs = ne.get_notifications(limit=3)
        assert len(notifs) == 3

    def test_mark_read(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        sent = ne.send_notification(rule["rule_id"], "T", "m")
        result = ne.mark_read(sent["notification_id"])
        assert result["status"] == "read"
        assert result["read_at"] > 0

    def test_mark_read_already_read_returns_none(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        sent = ne.send_notification(rule["rule_id"], "T", "m")
        ne.mark_read(sent["notification_id"])
        assert ne.mark_read(sent["notification_id"]) is None

    def test_mark_read_nonexistent_returns_none(self, ne):
        assert ne.mark_read("ghost") is None

    def test_notifications_newest_first(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        import time
        ne.send_notification(rule["rule_id"], "First", "m")
        time.sleep(0.01)
        ne.send_notification(rule["rule_id"], "Second", "m")
        notifs = ne.get_notifications()
        assert notifs[0]["title"] == "Second"


# ===========================================================================
# 5. Stats
# ===========================================================================

class TestGetStats:
    def test_stats_empty(self, ne):
        stats = ne.get_stats()
        assert stats["total_channels"] == 0
        assert stats["total_rules"] == 0
        assert stats["total_notifications"] == 0

    def test_stats_with_data(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        ne.send_notification(rule["rule_id"], "T1", "m", "info")
        ne.send_notification(rule["rule_id"], "T2", "m", "critical")
        stats = ne.get_stats()
        assert stats["total_channels"] == 1
        assert stats["total_rules"] == 1
        assert stats["total_notifications"] == 2
        assert stats["by_severity"]["info"] == 1
        assert stats["by_severity"]["critical"] == 1

    def test_stats_by_status(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        r1 = ne.send_notification(rule["rule_id"], "T", "m")
        ne.send_notification(rule["rule_id"], "T2", "m")
        ne.mark_read(r1["notification_id"])
        stats = ne.get_stats()
        assert stats["by_status"]["read"] == 1
        assert stats["by_status"]["unread"] == 1

    def test_stats_by_channel_type(self, ne):
        ne.create_channel("em", "email")
        ne.create_channel("sl", "slack")
        ne.create_channel("em2", "email")
        stats = ne.get_stats()
        assert stats["by_channel_type"]["email"] == 2
        assert stats["by_channel_type"]["slack"] == 1


# ===========================================================================
# 6. EventBus integration
# ===========================================================================

class TestEventBusIntegration:
    def test_create_channel_emits_event(self, ne, bus):
        events = []
        bus.subscribe("channel_created", events.append)
        ne.create_channel("ev-ch", "email")
        assert len(events) == 1
        assert events[0].payload["channel_type"] == "email"

    def test_send_notification_emits_event(self, ne, bus):
        events = []
        bus.subscribe("notification_sent", events.append)
        ch = ne.create_channel("ch", "webhook")
        rule = ne.create_rule("r", ch["channel_id"])
        ne.send_notification(rule["rule_id"], "T", "M")
        assert len(events) == 1
        assert events[0].payload["severity"] == "info"

    def test_mark_read_emits_event(self, ne, bus):
        events = []
        bus.subscribe("notification_read", events.append)
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        sent = ne.send_notification(rule["rule_id"], "T", "M")
        ne.mark_read(sent["notification_id"])
        assert len(events) == 1
        assert events[0].payload["notification_id"] == sent["notification_id"]

    def test_no_events_without_bus(self, ne_no_bus):
        ch = ne_no_bus.create_channel("ch", "email")
        rule = ne_no_bus.create_rule("r", ch["channel_id"])
        ne_no_bus.send_notification(rule["rule_id"], "T", "M")
        # No crash = success


# ===========================================================================
# 7. Thread safety
# ===========================================================================

class TestThreadSafety:
    def test_concurrent_channel_creation(self, ne):
        errors = []

        def create(i):
            try:
                ne.create_channel(f"ch-{i}", "email")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(ne.list_channels()) == 20

    def test_concurrent_send_notifications(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        errors = []

        def send(i):
            try:
                ne.send_notification(rule["rule_id"], f"T{i}", "m")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=send, args=(i,))
                   for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(ne.get_notifications()) == 30

    def test_concurrent_mark_read(self, ne):
        ch = ne.create_channel("ch", "email")
        rule = ne.create_rule("r", ch["channel_id"])
        ids = []
        for i in range(10):
            r = ne.send_notification(rule["rule_id"], f"T{i}", "m")
            ids.append(r["notification_id"])

        errors = []

        def mark(nid):
            try:
                ne.mark_read(nid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=mark, args=(nid,))
                   for nid in ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(ne.get_notifications(status="read")) == 10


# ===========================================================================
# 8. Singleton
# ===========================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        import sylion.monitoring.notification_engine as mod
        mod._instance = None
        inst = get_notification_engine()
        assert isinstance(inst, NotificationEngine)
        mod._instance = None

    def test_singleton_reuses_same(self):
        import sylion.monitoring.notification_engine as mod
        mod._instance = None
        a = get_notification_engine()
        b = get_notification_engine()
        assert a is b
        mod._instance = None

    def test_reset_clears_singleton(self):
        import sylion.monitoring.notification_engine as mod
        mod._instance = None
        a = get_notification_engine()
        reset_notification_engine()
        assert mod._instance is None
        b = get_notification_engine()
        assert b is not a
        mod._instance = None
