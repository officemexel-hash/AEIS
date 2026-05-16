"""
SYLION Core — NATS JetStream Event Bus Adapter

Drop-in async replacement for the SQLite-backed EventBus.
Uses NATS JetStream for persistent pub/sub with the same SylionEvent interface.

When nats-py is not installed, the class can still be imported (for type checking)
but connect() will raise ImportError.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from typing import Any, Callable

from sylion.core.event_bus import EventBus, EventHandler, SylionEvent

log = logging.getLogger("sylion.core.nats_adapter")

# ---------------------------------------------------------------------------
# UUIDv7 helper
# ---------------------------------------------------------------------------

def _uuid_v7() -> str:
    """Generate a UUIDv7 (time-ordered, milliseconds precision).

    Layout (RFC 9562):
      - 48 bits  : unix_ts_ms
      - 4 bits   : version (0111)
      - 12 bits  : rand_a
      - 2 bits   : variant (10)
      - 62 bits  : rand_b
    """
    import struct
    import os

    ts_ms = int(time.time() * 1000)
    rand_bytes = bytearray(os.urandom(10))  # 80 random bits (we need 74)

    # Pack timestamp (48 bits big-endian)
    ts_bytes = struct.pack(">Q", ts_ms)[2:]  # last 6 bytes = 48 bits

    # Build 16-byte UUID
    buf = bytearray(16)
    buf[0:6] = ts_bytes
    buf[6] = (0x70 | (rand_bytes[0] & 0x0F))  # version 7
    buf[7] = rand_bytes[1]
    buf[8] = (0x80 | (rand_bytes[2] & 0x3F))  # variant 10
    buf[9:] = rand_bytes[3:10]

    return str(uuid.UUID(bytes=bytes(buf)))


# ---------------------------------------------------------------------------
# NATSEventBus
# ---------------------------------------------------------------------------

class NATSEventBus:
    """NATS JetStream-backed event bus — same interface as EventBus.

    Usage::

        bus = NATSEventBus("nats://localhost:4222")
        await bus.connect()
        bus.publish(SylionEvent(...))
        await bus.close()

    All publish/subscribe/query/replay methods are synchronous (blocking)
    wrappers around the async NATS calls, matching the EventBus API exactly.
    Internally they run coroutines on a dedicated event loop.
    """

    STREAM_NAME = "SYLION_EVENTS"
    KV_BUCKET = "sylion_event_dedup"

    def __init__(self, nats_url: str = "nats://localhost:4222"):
        self._nats_url = nats_url
        self._nc = None          # nats.NATS connection
        self._js = None          # JetStream context
        self._kv = None          # KV bucket for idempotency
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_subs: list[EventHandler] = []
        self._nats_subs: list[Any] = []     # NATS subscription handles
        self._connected = False

    # --- Lifecycle ---

    async def connect(self):
        """Connect to NATS server and set up JetStream stream + KV bucket."""
        try:
            import nats
        except ImportError:
            raise ImportError(
                "nats-py is required for NATS mode. "
                "Install with: pip install nats-py"
            )

        self._nc = await nats.connect(self._nats_url)
        self._js = self._nc.jetstream()

        # Ensure stream exists
        try:
            await self._js.stream_info(self.STREAM_NAME)
        except Exception:
            from nats.js.api import StreamConfig, RetentionPolicy, StorageType
            await self._js.add_stream(StreamConfig(
                name=self.STREAM_NAME,
                subjects=["sylion.>"],
                retention=RetentionPolicy.LIMITS,
                storage=StorageType.FILE,
                max_msgs=100_000,
                max_age=86400 * 30,  # 30 days
            ))
            log.info("created JetStream stream %s", self.STREAM_NAME)

        # KV bucket for idempotency dedup
        try:
            self._kv = await self._js.key_value(bucket=self.KV_BUCKET)
        except Exception:
            from nats.js.api import KeyValueConfig
            self._kv = await self._js.create_key_value(KeyValueConfig(
                bucket=self.KV_BUCKET,
                max_value_size=256,
                history=1,
                ttl=86400 * 7,  # 7 days
            ))
            log.info("created KV bucket %s for dedup", self.KV_BUCKET)

        self._connected = True
        log.info("NATS connected to %s", self._nats_url)

    async def close(self):
        """Close NATS connection."""
        if self._nc and self._connected:
            await self._nc.close()
            self._connected = False
            log.info("NATS connection closed")

    # --- Internal async runners ---

    def _run_async(self, coro):
        """Run an async coroutine synchronously using a dedicated loop."""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
                # We're inside an existing event loop — create a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, coro).result()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()

        if self._loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()

        return self._loop.run_until_complete(coro)

    # --- SylionEvent helpers ---

    @staticmethod
    def _event_to_nats_subject(event: SylionEvent) -> str:
        """Convert topic like 'module.registered' to NATS subject 'sylion.module.registered'."""
        return f"sylion.{event.topic}"

    @staticmethod
    def _event_to_bytes(event: SylionEvent) -> bytes:
        return json.dumps(event.to_dict(), default=str).encode("utf-8")

    @staticmethod
    def _bytes_to_event(data: bytes) -> SylionEvent:
        d = json.loads(data.decode("utf-8"))
        return SylionEvent(
            event_id=d.get("event_id", ""),
            topic=d.get("topic", ""),
            payload=d.get("payload", {}),
            source_module=d.get("source_module", ""),
            timestamp=d.get("timestamp", 0.0),
            idempotency_key=d.get("idempotency_key", ""),
        )

    # --- Publish (sync wrapper) ---

    def publish(self, event: SylionEvent) -> str:
        """Publish event via NATS JetStream. Returns event_id. Deduplicates by idempotency_key."""
        return self._run_async(self._publish_async(event))

    async def _publish_async(self, event: SylionEvent) -> str:
        self._ensure_connected()

        # Ensure event has UUIDv7 (replace uuid4 hex from __post_init__)
        if not event.event_id or len(event.event_id) == 32:
            event.event_id = _uuid_v7()
        if not event.idempotency_key:
            event.idempotency_key = event.event_id
        # Always refresh timestamp to publish time
        event.timestamp = time.time()

        # Idempotency: check KV bucket
        try:
            existing = await self._kv.get(event.idempotency_key)
            if existing and existing.value:
                existing_id = existing.value.decode("utf-8")
                log.debug("dedup event %s (idem_key=%s)", event.event_id, event.idempotency_key)
                return existing_id
        except Exception:
            pass  # Key not found — proceed with publish

        # Publish to JetStream
        subject = self._event_to_nats_subject(event)
        ack = await self._js.publish(
            subject,
            self._event_to_bytes(event),
            headers={"Nats-Msg-Id": event.idempotency_key},
        )
        log.debug("published event %s to %s (seq=%s)", event.event_id, subject, ack.seq)

        # Store idempotency key
        try:
            await self._kv.put(event.idempotency_key, event.event_id.encode("utf-8"))
        except Exception:
            log.warning("failed to store idempotency key %s", event.idempotency_key)

        # Dispatch to local in-process subscribers
        self._dispatch(event)
        return event.event_id

    # --- Subscribe (sync wrapper) ---

    def subscribe(self, topic: str, handler: EventHandler):
        """Subscribe to a topic. Use '*' for all events (NATS wildcard 'sylion.>')."""
        if topic == "*":
            self._wildcard_subs.append(handler)
        else:
            self._subscribers[topic].append(handler)
        log.debug("subscribed to %s", topic)

        # If connected, also set up NATS push subscription
        if self._connected:
            self._run_async(self._subscribe_nats(topic))

    async def _subscribe_nats(self, topic: str):
        """Set up a NATS push subscription that dispatches to local handlers."""
        self._ensure_connected()
        subject = "sylion.>" if topic == "*" else f"sylion.{topic}"

        async def _callback(msg):
            event = self._bytes_to_event(msg.data)
            self._dispatch(event)

        sub = await self._js.subscribe(subject, cb=_callback, stream=self.STREAM_NAME)
        self._nats_subs.append(sub)
        log.debug("NATS subscription active on %s", subject)

    # --- Dispatch to local subscribers ---

    def _dispatch(self, event: SylionEvent):
        """Dispatch event to in-process subscribers (same as EventBus)."""
        for handler in self._subscribers.get(event.topic, []):
            try:
                handler(event)
            except Exception:
                log.exception("subscriber error for topic %s", event.topic)

        for handler in self._wildcard_subs:
            try:
                handler(event)
            except Exception:
                log.exception("wildcard subscriber error")

    # --- Ack ---

    def ack(self, event_id: str) -> bool:
        """Ack an event (no-op in NATS mode; JetStream manages acks)."""
        log.debug("ack(%s) — no-op in NATS mode", event_id)
        return True

    # --- Query (sync wrapper) ---

    def query(self, topic: str | None = None, since: float | None = None,
              limit: int = 100) -> list[dict]:
        """Query events from JetStream."""
        return self._run_async(self._query_async(topic, since, limit))

    async def _query_async(self, topic: str | None = None,
                           since: float | None = None,
                           limit: int = 100) -> list[dict]:
        self._ensure_connected()
        results: list[dict] = []

        subject = "sylion.>" if not topic else f"sylion.{topic}"

        try:
            # Use JetStream consumer to read messages
            from nats.js.api import ConsumerConfig, DeliverPolicy

            deliver_policy = DeliverPolicy.ALL
            opt_start_time = None
            if since:
                import datetime
                opt_start_time = datetime.datetime.fromtimestamp(since, tz=datetime.timezone.utc)
                deliver_policy = DeliverPolicy.BY_START_TIME

            consumer_config = ConsumerConfig(
                deliver_policy=deliver_policy,
                opt_start_time=opt_start_time,
                ack_policy="explicit",
            )

            # Read from stream using pull consumer
            sub = await self._js.pull_subscribe(
                subject,
                durable="sylion_query",
                stream=self.STREAM_NAME,
                config=consumer_config,
            )

            try:
                msgs = await sub.fetch(limit, timeout=2)
                for msg in msgs:
                    event_dict = json.loads(msg.data.decode("utf-8"))
                    if since and event_dict.get("timestamp", 0) < since:
                        continue
                    results.append(event_dict)
                    await msg.ack()
            except asyncio.TimeoutError:
                pass  # No messages available
            finally:
                await sub.unsubscribe()

        except Exception:
            log.exception("query failed")
            # Fall back to empty result on error

        # Sort by timestamp DESC
        results.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return results[:limit]

    # --- Replay (sync wrapper) ---

    def replay(self, since: float | None = None, topic: str | None = None) -> int:
        """Replay events from JetStream to subscribers."""
        return self._run_async(self._replay_async(since, topic))

    async def _replay_async(self, since: float | None = None,
                            topic: str | None = None) -> int:
        events = await self._query_async(topic=topic, since=since, limit=10000)
        count = 0
        for ev_dict in reversed(events):  # chronological order
            event = SylionEvent(
                event_id=ev_dict["event_id"],
                topic=ev_dict["topic"],
                payload=ev_dict.get("payload", {}),
                source_module=ev_dict.get("source_module", ""),
                timestamp=ev_dict.get("timestamp", 0.0),
            )
            self._dispatch(event)
            count += 1
        log.info("replayed %d events (since=%s, topic=%s)", count, since, topic)
        return count

    # --- Catalog ---

    def get_catalog(self) -> dict[str, int]:
        """Get event counts per topic from JetStream."""
        return self._run_async(self._get_catalog_async())

    async def _get_catalog_async(self) -> dict[str, int]:
        self._ensure_connected()
        catalog: dict[str, int] = defaultdict(int)

        try:
            sub = await self._js.pull_subscribe(
                "sylion.>",
                durable="sylion_catalog",
                stream=self.STREAM_NAME,
            )

            try:
                msgs = await sub.fetch(10000, timeout=2)
                for msg in msgs:
                    d = json.loads(msg.data.decode("utf-8"))
                    topic = d.get("topic", "unknown")
                    catalog[topic] += 1
                    await msg.ack()
            except asyncio.TimeoutError:
                pass
            finally:
                await sub.unsubscribe()

        except Exception:
            log.exception("catalog query failed")

        return dict(catalog)

    # --- Helpers ---

    def _ensure_connected(self):
        if not self._connected or self._nc is None:
            raise RuntimeError("NATSEventBus is not connected. Call connect() first.")
