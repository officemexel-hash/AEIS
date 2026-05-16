"""
Comprehensive tests for sylion.core.event_bus — EventBus class.
Tests: publish, subscribe, ack, query, replay, get_catalog, dedup, wildcards, edge cases.
"""
from __future__ import annotations

import time
import threading
import uuid

import pytest

from sylion.core.event_bus import (
    EventBus,
    EventDomain,
    SylionEvent,
    get_event_bus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(topic: str = "test.topic", payload: dict | None = None,
           source: str = "test", event_id: str = "") -> SylionEvent:
    return SylionEvent(
        event_id=event_id,
        topic=topic,
        payload=payload or {},
        source_module=source,
    )


def _bus() -> EventBus:
    return EventBus()


# ---------------------------------------------------------------------------
# SylionEvent dataclass
# ---------------------------------------------------------------------------

class TestSylionEvent:

    def test_auto_event_id(self):
        ev = SylionEvent(event_id="", topic="x")
        assert ev.event_id != ""

    def test_auto_timestamp(self):
        ev = SylionEvent(event_id="abc", topic="x")
        assert ev.timestamp > 0

    def test_auto_idempotency_key(self):
        ev = SylionEvent(event_id="my-id", topic="x")
        assert ev.idempotency_key == "my-id"

    def test_explicit_fields_preserved(self):
        ev = SylionEvent(event_id="e1", topic="t1", payload={"a": 1},
                         source_module="mod", timestamp=100.0, idempotency_key="ik")
        assert ev.event_id == "e1"
        assert ev.topic == "t1"
        assert ev.payload == {"a": 1}
        assert ev.source_module == "mod"
        assert ev.timestamp == 100.0
        assert ev.idempotency_key == "ik"

    def test_to_dict(self):
        ev = SylionEvent(event_id="e2", topic="t2")
        d = ev.to_dict()
        assert d["event_id"] == "e2"
        assert d["topic"] == "t2"
        assert "payload" in d
        assert "timestamp" in d

    def test_default_payload_empty_dict(self):
        ev = SylionEvent(event_id="e3", topic="t3")
        assert ev.payload == {}


# ---------------------------------------------------------------------------
# EventDomain enum
# ---------------------------------------------------------------------------

class TestEventDomain:

    def test_domain_values(self):
        assert EventDomain.MODULE.value == "module"
        assert EventDomain.DECISION.value == "decision"
        assert EventDomain.COGNITIVE.value == "cognitive"
        assert EventDomain.SYSTEM.value == "system"

    def test_all_domains_exist(self):
        assert len(EventDomain) >= 10


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

class TestPublish:

    def test_publish_returns_event_id(self):
        bus = _bus()
        ev = _event(event_id="pub1")
        result = bus.publish(ev)
        assert result == "pub1"

    def test_publish_stores_in_db(self):
        bus = _bus()
        bus.publish(_event(topic="store.check", payload={"k": "v"}, event_id="s1"))
        rows = bus.query(topic="store.check")
        assert len(rows) == 1
        assert rows[0]["event_id"] == "s1"

    def test_publish_dedup_by_idempotency_key(self):
        bus = _bus()
        ev1 = _event(event_id="id1", topic="dedup")
        ev1.idempotency_key = "shared-key"
        ev2 = _event(event_id="id2", topic="dedup")
        ev2.idempotency_key = "shared-key"
        bus.publish(ev1)
        returned = bus.publish(ev2)
        assert returned == "id1"
        assert len(bus.query(topic="dedup")) == 1

    def test_publish_multiple_topics(self):
        bus = _bus()
        bus.publish(_event(topic="a.1", event_id="ea"))
        bus.publish(_event(topic="b.2", event_id="eb"))
        assert len(bus.query(topic="a.1")) == 1
        assert len(bus.query(topic="b.2")) == 1

    def test_publish_payload_json_serialization(self):
        bus = _bus()
        bus.publish(_event(topic="json.test", payload={"num": 42, "nested": {"x": True}}, event_id="j1"))
        rows = bus.query(topic="json.test")
        import json
        parsed = json.loads(rows[0]["payload"])
        assert parsed["num"] == 42
        assert parsed["nested"]["x"] is True


# ---------------------------------------------------------------------------
# Subscribe + dispatch
# ---------------------------------------------------------------------------

class TestSubscribe:

    def test_exact_topic_subscriber(self):
        bus = _bus()
        received = []
        bus.subscribe("sub.test", lambda ev: received.append(ev))
        bus.publish(_event(topic="sub.test", event_id="sub1"))
        assert len(received) == 1
        assert received[0].event_id == "sub1"

    def test_wildcard_subscriber(self):
        bus = _bus()
        received = []
        bus.subscribe("*", lambda ev: received.append(ev))
        bus.publish(_event(topic="wild.a", event_id="w1"))
        bus.publish(_event(topic="wild.b", event_id="w2"))
        assert len(received) == 2

    def test_subscriber_error_does_not_crash(self):
        bus = _bus()
        def bad_handler(ev):
            raise RuntimeError("boom")
        bus.subscribe("err.topic", bad_handler)
        bus.publish(_event(topic="err.topic", event_id="e1"))
        assert len(bus.query(topic="err.topic")) == 1

    def test_multiple_subscribers_same_topic(self):
        bus = _bus()
        r1, r2 = [], []
        bus.subscribe("multi.topic", lambda ev: r1.append(ev))
        bus.subscribe("multi.topic", lambda ev: r2.append(ev))
        bus.publish(_event(topic="multi.topic", event_id="m1"))
        assert len(r1) == 1
        assert len(r2) == 1

    def test_no_dispatch_for_different_topic(self):
        bus = _bus()
        received = []
        bus.subscribe("only.this", lambda ev: received.append(ev))
        bus.publish(_event(topic="other.topic", event_id="ot1"))
        assert len(received) == 0


# ---------------------------------------------------------------------------
# Ack
# ---------------------------------------------------------------------------

class TestAck:

    def test_ack_existing_event(self):
        bus = _bus()
        bus.publish(_event(event_id="ack1", topic="ack.topic"))
        result = bus.ack("ack1")
        assert result is True

    def test_ack_nonexistent_event(self):
        bus = _bus()
        result = bus.ack("nonexistent-id")
        assert result is False

    def test_ack_updates_acked_flag(self):
        bus = _bus()
        bus.publish(_event(event_id="ack2", topic="ack.idem"))
        assert bus.ack("ack2") is True
        # ack sets acked=1; calling again still updates the row (rowcount=1)
        assert bus.ack("ack2") is True


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

class TestQuery:

    def test_query_all(self):
        bus = _bus()
        bus.publish(_event(topic="q.a", event_id="qa"))
        bus.publish(_event(topic="q.b", event_id="qb"))
        all_events = bus.query()
        assert len(all_events) >= 2

    def test_query_by_topic(self):
        bus = _bus()
        bus.publish(_event(topic="filter.me", event_id="fm1"))
        bus.publish(_event(topic="other", event_id="ot1"))
        results = bus.query(topic="filter.me")
        assert len(results) == 1
        assert results[0]["topic"] == "filter.me"

    def test_query_by_since(self):
        bus = _bus()
        bus.publish(_event(topic="ts.old", event_id="ts1"))
        cutoff = time.time() + 0.001
        time.sleep(0.01)
        bus.publish(_event(topic="ts.new", event_id="ts2"))
        results = bus.query(since=cutoff)
        assert any(r["event_id"] == "ts2" for r in results)
        assert not any(r["event_id"] == "ts1" for r in results)

    def test_query_limit(self):
        bus = _bus()
        for i in range(10):
            bus.publish(_event(topic="lim.test", event_id=f"lim{i}"))
        results = bus.query(topic="lim.test", limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

class TestReplay:

    def test_replay_all(self):
        bus = _bus()
        received = []
        bus.subscribe("*", lambda ev: received.append(ev))
        bus.publish(_event(topic="rp.a", event_id="rp1"))
        bus.publish(_event(topic="rp.b", event_id="rp2"))
        received.clear()
        count = bus.replay()
        assert count == 2
        assert len(received) == 2

    def test_replay_by_topic(self):
        bus = _bus()
        received = []
        bus.subscribe("rp.only", lambda ev: received.append(ev))
        bus.publish(_event(topic="rp.only", event_id="ro1"))
        bus.publish(_event(topic="rp.other", event_id="ro2"))
        received.clear()
        count = bus.replay(topic="rp.only")
        assert count == 1

    def test_replay_empty(self):
        bus = _bus()
        count = bus.replay()
        assert count == 0

    def test_replay_since(self):
        bus = _bus()
        bus.publish(_event(topic="rs.old", event_id="rs1"))
        cutoff = time.time() + 0.001
        time.sleep(0.01)
        bus.publish(_event(topic="rs.new", event_id="rs2"))
        received = []
        bus.subscribe("*", lambda ev: received.append(ev))
        count = bus.replay(since=cutoff)
        assert count == 1


# ---------------------------------------------------------------------------
# get_catalog
# ---------------------------------------------------------------------------

class TestGetCatalog:

    def test_catalog_counts(self):
        bus = _bus()
        bus.publish(_event(topic="cat.a", event_id="ca1"))
        bus.publish(_event(topic="cat.a", event_id="ca2"))
        bus.publish(_event(topic="cat.b", event_id="cb1"))
        cat = bus.get_catalog()
        assert cat["cat.a"] == 2
        assert cat["cat.b"] == 1

    def test_catalog_empty(self):
        bus = _bus()
        cat = bus.get_catalog()
        assert cat == {}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_event_bus_returns_instance(self):
        # Reset singleton for test isolation
        import sylion.core.event_bus as mod
        mod._bus = None
        bus = get_event_bus()
        assert isinstance(bus, EventBus)
        mod._bus = None  # cleanup


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_publish(self):
        bus = _bus()
        errors = []

        def publish_n(n):
            try:
                for i in range(20):
                    bus.publish(_event(topic=f"concurrent.{n}", event_id=f"c{n}_{i}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=publish_n, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        total = sum(bus.get_catalog().values())
        assert total == 100
