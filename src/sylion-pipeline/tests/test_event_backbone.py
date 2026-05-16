from __future__ import annotations

import sys
import types

import pytest

from sylion.core.event_backbone import (
    EventBackboneError,
    LocalBackbone,
    NATSBackbone,
    RedisBackbone,
    reset_event_backbone,
)
from sylion.core.event_bus import EventBus, SylionEvent


class FakeNatsConnection:
    def __init__(self) -> None:
        self.callbacks: dict[str, object] = {}
        self.is_closed = False

    async def publish(self, subject: str, payload: bytes) -> None:
        callback = self.callbacks.get(subject)
        if callback is not None:
            await callback(types.SimpleNamespace(subject=subject, data=payload))

    async def flush(self) -> None:
        return None

    async def subscribe(self, subject: str, cb) -> object:
        self.callbacks[subject] = cb
        return types.SimpleNamespace(subject=subject)

    async def close(self) -> None:
        self.is_closed = True


class FakeRedisListener:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class FakeRedisPubSub:
    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}
        self.pattern_handlers: dict[str, object] = {}
        self.listener = FakeRedisListener()

    def subscribe(self, **kwargs) -> None:
        self.handlers.update(kwargs)

    def psubscribe(self, **kwargs) -> None:
        self.pattern_handlers.update(kwargs)

    def run_in_thread(self, sleep_time: float = 0.01, daemon: bool = True) -> FakeRedisListener:
        return self.listener

    def close(self) -> None:
        return None


class FakeRedisClient:
    def __init__(self) -> None:
        self._pubsub = FakeRedisPubSub()
        self.closed = False

    def pubsub(self, ignore_subscribe_messages: bool = True) -> FakeRedisPubSub:
        return self._pubsub

    def ping(self) -> bool:
        return True

    def publish(self, channel: str, payload: str) -> int:
        handler = self._pubsub.handlers.get(channel)
        if handler is not None:
            handler({"channel": channel, "data": payload})
        for pattern, pattern_handler in self._pubsub.pattern_handlers.items():
            if pattern == "*":
                pattern_handler({"pattern": pattern, "channel": channel, "data": payload})
        return 1

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_singletons():
    reset_event_backbone()
    yield
    reset_event_backbone()


def test_local_backbone_replay_replays_historical_events():
    bus = EventBus()
    backbone = LocalBackbone(event_bus=bus)
    event = SylionEvent(
        event_id="evt-local-1",
        topic="test.replay",
        payload={"value": 7},
        source_module="tests",
    )
    backbone.publish(event)

    received: list[SylionEvent] = []
    backbone.replay("test.replay", lambda replayed: received.append(replayed))

    assert len(received) == 1
    assert received[0].event_id == "evt-local-1"
    assert received[0].payload == {"value": 7}


def test_nats_publish_and_subscribe_use_live_runtime(monkeypatch: pytest.MonkeyPatch):
    fake_nc = FakeNatsConnection()

    async def _connect(*args, **kwargs):
        return fake_nc

    monkeypatch.setitem(sys.modules, "nats", types.SimpleNamespace(connect=_connect))

    backbone = NATSBackbone(url="nats://unit-test:4222")
    received: list[SylionEvent] = []
    backbone.subscribe("jobs.run", lambda event: received.append(event))

    event = SylionEvent(
        event_id="evt-nats-1",
        topic="jobs.run",
        payload={"job": "build"},
        source_module="tests",
    )
    assert backbone.publish(event) == "evt-nats-1"
    assert len(received) == 1
    assert received[0].payload == {"job": "build"}

    health = backbone.health()
    assert health["status"] == "degraded"
    assert health["ready"] is True
    assert health["capabilities"]["publish"] == "ok"
    assert health["capabilities"]["query"] == "unsupported"


def test_nats_query_raises_explicit_unsupported_error():
    backbone = NATSBackbone(url="nats://unit-test:4222")

    with pytest.raises(EventBackboneError) as exc_info:
        backbone.query(topic="jobs.run")

    assert exc_info.value.http_status == 501
    assert exc_info.value.status == "degraded"
    assert exc_info.value.operation == "query"


def test_redis_publish_and_subscribe_use_live_runtime(monkeypatch: pytest.MonkeyPatch):
    fake_client = FakeRedisClient()

    class FakeRedisModule:
        @staticmethod
        def from_url(*args, **kwargs) -> FakeRedisClient:
            return fake_client

    monkeypatch.setitem(sys.modules, "redis", FakeRedisModule())

    backbone = RedisBackbone(url="redis://unit-test:6379/0")
    received: list[SylionEvent] = []
    backbone.subscribe("jobs.run", lambda event: received.append(event))

    event = SylionEvent(
        event_id="evt-redis-1",
        topic="jobs.run",
        payload={"job": "deploy"},
        source_module="tests",
    )
    assert backbone.publish(event) == "evt-redis-1"
    assert len(received) == 1
    assert received[0].payload == {"job": "deploy"}

    health = backbone.health()
    assert health["status"] == "degraded"
    assert health["ready"] is True
    assert health["capabilities"]["subscribe"] == "ok"
    assert health["capabilities"]["catalog"] == "unsupported"


def test_redis_catalog_raises_explicit_unsupported_error():
    backbone = RedisBackbone(url="redis://unit-test:6379/0")

    with pytest.raises(EventBackboneError) as exc_info:
        backbone.get_catalog()

    assert exc_info.value.http_status == 501
    assert exc_info.value.status == "degraded"
    assert exc_info.value.operation == "catalog"
