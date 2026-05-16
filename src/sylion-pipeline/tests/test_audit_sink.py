"""
Tests for sylion.security.audit_sink -- AuditSink

~35 tests covering subscription CRUD, event delivery, retry,
list/delivery filtering, statistics, error handling, EventBus
emissions, concurrency, and singleton lifecycle.
"""

from __future__ import annotations

import threading

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.security.audit_sink import (
    AuditSink,
    get_audit_sink,
    reset_audit_sink,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_audit_sink()
    yield
    reset_audit_sink()


@pytest.fixture
def bus():
    eb = EventBus()
    eb._captured: list[SylionEvent] = []
    _orig = eb.publish

    def _capture(event: SylionEvent):
        eb._captured.append(event)
        return _orig(event)

    eb.publish = _capture
    return eb


@pytest.fixture
def sink(bus):
    return AuditSink(event_bus=bus)


@pytest.fixture
def plain_sink():
    return AuditSink()


# ===========================================================================
# 1. Create subscription
# ===========================================================================

class TestCreateSubscription:
    def test_returns_sub_id(self, sink):
        r = sink.create_subscription("webhook-sub", "security.*", "webhook")
        assert isinstance(r["sub_id"], str) and len(r["sub_id"]) > 0

    def test_returns_name(self, sink):
        r = sink.create_subscription("my-sub", "audit.*", "file")
        assert r["name"] == "my-sub"

    def test_returns_topic_pattern(self, sink):
        r = sink.create_subscription("s", "security.login", "webhook")
        assert r["topic_pattern"] == "security.login"

    def test_returns_delivery_type(self, sink):
        r = sink.create_subscription("s", "t", "database")
        assert r["delivery_type"] == "database"

    def test_returns_config_json(self, sink):
        cfg = {"url": "https://example.com/hook"}
        r = sink.create_subscription("s", "t", "webhook", config_json=cfg)
        assert r["config_json"] == cfg

    def test_default_config_json_empty(self, sink):
        r = sink.create_subscription("s", "t", "file")
        assert r["config_json"] == {}

    def test_enabled_true(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        assert r["enabled"] is True

    def test_invalid_delivery_type_raises(self, sink):
        with pytest.raises(ValueError, match="Invalid delivery_type"):
            sink.create_subscription("s", "t", "carrier_pigeon")

    def test_emits_subscription_created(self, sink, bus):
        sink.create_subscription("s", "t", "webhook")
        topics = [e.topic for e in bus._captured]
        assert "subscription_created" in topics

    def test_emitted_payload_has_sub_id(self, sink, bus):
        r = sink.create_subscription("s", "t", "webhook")
        ev = [e for e in bus._captured if e.topic == "subscription_created"][0]
        assert ev.payload["sub_id"] == r["sub_id"]


# ===========================================================================
# 2. Update subscription
# ===========================================================================

class TestUpdateSubscription:
    def test_update_name(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        updated = sink.update_subscription(r["sub_id"], name="new-name")
        assert updated["name"] == "new-name"

    def test_update_topic_pattern(self, sink):
        r = sink.create_subscription("s", "old.*", "webhook")
        updated = sink.update_subscription(r["sub_id"], topic_pattern="new.*")
        assert updated["topic_pattern"] == "new.*"

    def test_update_delivery_type(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        updated = sink.update_subscription(r["sub_id"], delivery_type="file")
        assert updated["delivery_type"] == "file"

    def test_update_config_json(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        updated = sink.update_subscription(r["sub_id"],
                                           config_json={"url": "http://x"})
        assert updated is not None

    def test_update_nonexistent_returns_none(self, sink):
        assert sink.update_subscription("nonexistent", name="x") is None

    def test_update_invalid_delivery_type_raises(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        with pytest.raises(ValueError, match="Invalid delivery_type"):
            sink.update_subscription(r["sub_id"], delivery_type="bad")


# ===========================================================================
# 3. Delete subscription
# ===========================================================================

class TestDeleteSubscription:
    def test_delete_existing(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        assert sink.delete_subscription(r["sub_id"]) is True

    def test_delete_nonexistent(self, sink):
        assert sink.delete_subscription("nonexistent") is False

    def test_delete_removes_from_list(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        sink.delete_subscription(r["sub_id"])
        subs = sink.list_subscriptions()
        assert all(s["sub_id"] != r["sub_id"] for s in subs)


# ===========================================================================
# 4. List subscriptions
# ===========================================================================

class TestListSubscriptions:
    def test_empty_list(self, sink):
        assert sink.list_subscriptions() == []

    def test_lists_all(self, sink):
        sink.create_subscription("a", "t1", "webhook")
        sink.create_subscription("b", "t2", "file")
        assert len(sink.list_subscriptions()) == 2

    def test_filter_by_topic_pattern(self, sink):
        sink.create_subscription("a", "security.*", "webhook")
        sink.create_subscription("b", "audit.*", "file")
        result = sink.list_subscriptions(topic_pattern="security.*")
        assert len(result) == 1
        assert result[0]["topic_pattern"] == "security.*"

    def test_filter_no_match_returns_empty(self, sink):
        sink.create_subscription("a", "security.*", "webhook")
        assert sink.list_subscriptions(topic_pattern="nonexistent") == []


# ===========================================================================
# 5. Deliver event
# ===========================================================================

class TestDeliverEvent:
    def test_returns_delivery_id(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        d = sink.deliver_event(r["sub_id"], {"type": "login", "actor": "a"})
        assert isinstance(d["delivery_id"], str) and len(d["delivery_id"]) > 0

    def test_returns_pending_status(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        d = sink.deliver_event(r["sub_id"], {"type": "login"})
        assert d["status"] == "pending"

    def test_zero_attempts(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        d = sink.deliver_event(r["sub_id"], {"type": "login"})
        assert d["attempts"] == 0

    def test_invalid_sub_raises(self, sink):
        with pytest.raises(ValueError, match="not found"):
            sink.deliver_event("nonexistent", {"type": "x"})

    def test_emits_event_delivered(self, sink, bus):
        r = sink.create_subscription("s", "t", "webhook")
        sink.deliver_event(r["sub_id"], {"type": "login"})
        topics = [e.topic for e in bus._captured]
        assert "event_delivered" in topics


# ===========================================================================
# 6. List deliveries
# ===========================================================================

class TestListDeliveries:
    def test_empty_list(self, sink):
        assert sink.list_deliveries() == []

    def test_lists_all_deliveries(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        sink.deliver_event(r["sub_id"], {"a": 1})
        sink.deliver_event(r["sub_id"], {"b": 2})
        assert len(sink.list_deliveries()) == 2

    def test_filter_by_sub_id(self, sink):
        r1 = sink.create_subscription("s1", "t1", "webhook")
        r2 = sink.create_subscription("s2", "t2", "file")
        sink.deliver_event(r1["sub_id"], {"a": 1})
        sink.deliver_event(r2["sub_id"], {"b": 2})
        result = sink.list_deliveries(sub_id=r1["sub_id"])
        assert len(result) == 1

    def test_filter_by_status(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        sink.deliver_event(r["sub_id"], {"a": 1})
        result = sink.list_deliveries(status="pending")
        assert len(result) == 1

    def test_limit(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        for i in range(10):
            sink.deliver_event(r["sub_id"], {"i": i})
        assert len(sink.list_deliveries(limit=3)) == 3


# ===========================================================================
# 7. Retry delivery
# ===========================================================================

class TestRetryDelivery:
    def test_retry_increments_attempts(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        d = sink.deliver_event(r["sub_id"], {"a": 1})
        retried = sink.retry_delivery(d["delivery_id"])
        assert retried["attempts"] == 1

    def test_retry_resets_to_pending(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        d = sink.deliver_event(r["sub_id"], {"a": 1})
        retried = sink.retry_delivery(d["delivery_id"])
        assert retried["status"] == "pending"

    def test_retry_nonexistent_returns_none(self, sink):
        assert sink.retry_delivery("nonexistent") is None

    def test_retry_sets_last_attempt_at(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        d = sink.deliver_event(r["sub_id"], {"a": 1})
        retried = sink.retry_delivery(d["delivery_id"])
        assert retried["last_attempt_at"] is not None


# ===========================================================================
# 8. Statistics
# ===========================================================================

class TestGetSinkStats:
    def test_empty_stats(self, plain_sink):
        stats = plain_sink.get_sink_stats()
        assert stats["total_subscriptions"] == 0
        assert stats["total_deliveries"] == 0
        assert stats["deliveries_by_status"] == {}
        assert stats["subscriptions_by_type"] == {}

    def test_counts_subscriptions(self, sink):
        sink.create_subscription("s1", "t1", "webhook")
        sink.create_subscription("s2", "t2", "file")
        stats = sink.get_sink_stats()
        assert stats["total_subscriptions"] == 2

    def test_counts_deliveries(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        sink.deliver_event(r["sub_id"], {"a": 1})
        sink.deliver_event(r["sub_id"], {"b": 2})
        stats = sink.get_sink_stats()
        assert stats["total_deliveries"] == 2

    def test_by_type_breakdown(self, sink):
        sink.create_subscription("s1", "t1", "webhook")
        sink.create_subscription("s2", "t2", "file")
        stats = sink.get_sink_stats()
        assert stats["subscriptions_by_type"]["webhook"] == 1
        assert stats["subscriptions_by_type"]["file"] == 1

    def test_by_status_breakdown(self, sink):
        r = sink.create_subscription("s", "t", "webhook")
        sink.deliver_event(r["sub_id"], {"a": 1})
        stats = sink.get_sink_stats()
        assert stats["deliveries_by_status"]["pending"] == 1


# ===========================================================================
# 9. Concurrency
# ===========================================================================

class TestConcurrency:
    def test_concurrent_create_subscriptions(self, plain_sink):
        errors = []

        def worker(i):
            try:
                plain_sink.create_subscription(f"sub-{i}", f"topic-{i}",
                                               "webhook")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(plain_sink.list_subscriptions()) == 10


# ===========================================================================
# 10. Singleton
# ===========================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        inst = get_audit_sink()
        assert isinstance(inst, AuditSink)

    def test_get_is_idempotent(self):
        a = get_audit_sink()
        b = get_audit_sink()
        assert a is b

    def test_reset_clears_singleton(self):
        a = get_audit_sink()
        reset_audit_sink()
        b = get_audit_sink()
        assert a is not b

    def test_double_reset_is_safe(self):
        reset_audit_sink()
        reset_audit_sink()
        inst = get_audit_sink()
        assert isinstance(inst, AuditSink)
