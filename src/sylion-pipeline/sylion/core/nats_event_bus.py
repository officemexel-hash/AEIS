"""
SYLION Core -- NATS JetStream Event Bus Adapter (Phase 2)

Drop-in adapter that provides the same interface as EventBus but backs onto
NATS JetStream for durable, distributed pub/sub.

When nats-py is not installed or the NATS server is unreachable the adapter
gracefully falls back to an in-memory SQLite store so callers never crash.

API (identical to EventBus convenience surface):
    publish(topic, payload, source_module) -> str
    subscribe(topic, handler)              -> str  (subscription_id)
    unsubscribe(subscription_id)           -> None
    get_events(topic=None, limit=100)      -> list[dict]
    ack(event_id)                          -> bool

Mode selection:
    SYLION_EVENT_MODE=sqlite   -> SQLiteEventBus  (default)
    SYLION_EVENT_MODE=nats     -> NATSEventBus

Factory:
    get_event_bus(mode=None)   -> EventBus-like instance
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("sylion.core.nats_event_bus")

# Re-export SylionEvent and EventHandler so callers only need this module.
from sylion.core.event_bus import SylionEvent, EventHandler  # noqa: F401

# ---------------------------------------------------------------------------
# Subscription handle
# ---------------------------------------------------------------------------

_sub_counter = 0
_sub_lock = threading.Lock()


def _next_sub_id() -> str:
    global _sub_counter
    with _sub_lock:
        _sub_counter += 1
        return f"sub-{_sub_counter}"


# ---------------------------------------------------------------------------
# SQLiteEventBus  -- thin convenience wrapper around the original EventBus
# ---------------------------------------------------------------------------

class SQLiteEventBus:
    """SQLite-backed event bus with the convenience publish(topic, payload, source_module) API.

    Wraps the original EventBus internally but exposes the simpler signature
    expected by the dual-mode factory.
    """

    def __init__(self, db_path: str | None = None):
        # Lazy import to avoid circular dependency at module level
        from sylion.core.event_bus import EventBus
        self._bus = EventBus(db_path=db_path)
        self._subs: dict[str, tuple[str, EventHandler]] = {}  # sub_id -> (topic, handler)

    # --- Convenience publish ---------------------------------------------------

    def publish(self, topic: str, payload: dict[str, Any] | None = None,
                source_module: str = "") -> str:
        """Publish an event. Returns event_id."""
        event = SylionEvent(
            event_id="",
            topic=topic,
            payload=payload or {},
            source_module=source_module,
        )
        return self._bus.publish(event)

    # --- Subscribe / unsubscribe -----------------------------------------------

    def subscribe(self, topic: str, handler: EventHandler) -> str:
        """Subscribe *handler* to *topic*. Returns a subscription_id."""
        sub_id = _next_sub_id()
        self._bus.subscribe(topic, handler)
        self._subs[sub_id] = (topic, handler)
        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription by its id."""
        if subscription_id not in self._subs:
            return
        topic, handler = self._subs.pop(subscription_id)
        handlers = self._bus._subscribers.get(topic)
        if handlers and handler in handlers:
            handlers.remove(handler)
        elif topic == "*":
            if handler in self._bus._wildcard_subs:
                self._bus._wildcard_subs.remove(handler)

    # --- get_events (alias for query) ------------------------------------------

    def get_events(self, topic: str | None = None, limit: int = 100) -> list[dict]:
        """Retrieve stored events, newest first."""
        return self._bus.query(topic=topic, limit=limit)

    # --- Ack -------------------------------------------------------------------

    def ack(self, event_id: str) -> bool:
        return self._bus.ack(event_id)

    # --- Passthrough for advanced callers --------------------------------------

    @property
    def _inner(self):
        """Access the underlying EventBus if needed."""
        return self._bus


# ---------------------------------------------------------------------------
# NATSEventBus  -- NATS JetStream backend with graceful fallback
# ---------------------------------------------------------------------------

_NATS_AVAILABLE = True
try:
    import nats as _nats_mod  # noqa: F401 -- presence check only
except ImportError:
    _NATS_AVAILABLE = False


class NATSEventBus:
    """NATS JetStream-backed event bus with the same convenience API.

    Features:
      - Durable JetStream storage (per-topic streams)
      - Push subscriptions for real-time handlers
      - KV-based idempotency (dedup by idempotency_key)
      - Graceful fallback: if NATS is unreachable the bus degrades to an
        in-memory SQLite store transparently.

    All public methods are **synchronous** so the call-site matches EventBus.
    """

    STREAM_PREFIX = "SYLION_"
    KV_BUCKET = "sylion_event_dedup"

    def __init__(self, nats_url: str = "nats://localhost:4222"):
        self._nats_url = nats_url
        self._nc = None
        self._js = None
        self._kv = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected = False
        self._fallback = False  # True when degraded to SQLite

        # Subscriber bookkeeping
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_subs: list[EventHandler] = []
        self._nats_push_subs: list[Any] = []
        self._sub_map: dict[str, tuple[str, EventHandler]] = {}

        # Fallback SQLite (created lazily)
        self._fb_conn: sqlite3.Connection | None = None
        self._fb_lock = threading.Lock()

    # ------------------------------------------------------------------ fallback

    def _ensure_fallback_db(self):
        """Create in-memory SQLite for degraded mode."""
        if self._fb_conn is not None:
            return
        self._fb_conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._fb_conn.row_factory = sqlite3.Row
        self._fb_conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id      TEXT PRIMARY KEY,
                topic         TEXT NOT NULL,
                payload       TEXT NOT NULL DEFAULT '{}',
                source_module TEXT NOT NULL DEFAULT '',
                timestamp     REAL NOT NULL,
                idempotency_key TEXT NOT NULL DEFAULT '',
                acked         INTEGER NOT NULL DEFAULT 0
            )
        """)
        self._fb_conn.execute("CREATE INDEX IF NOT EXISTS idx_fb_topic ON events(topic)")
        self._fb_conn.execute("CREATE INDEX IF NOT EXISTS idx_fb_ts ON events(timestamp)")
        self._fb_conn.commit()

    # ------------------------------------------------------- async helpers ------

    def _run_async(self, coro):
        """Run *coro* synchronously, dispatching to a thread if needed."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return asyncio.run(coro)

    # ------------------------------------------------------- lifecycle ----------

    async def connect(self):
        """Connect to NATS and set up JetStream. On failure, enable fallback."""
        if not _NATS_AVAILABLE:
            log.warning("nats-py not installed -- falling back to in-memory store")
            self._fallback = True
            self._ensure_fallback_db()
            return

        try:
            import nats
            self._nc = await nats.connect(self._nats_url, connect_timeout=3)
            self._js = self._nc.jetstream()

            # KV bucket for idempotency
            try:
                self._kv = await self._js.key_value(bucket=self.KV_BUCKET)
            except Exception:
                try:
                    from nats.js.api import KeyValueConfig
                    self._kv = await self._js.create_key_value(KeyValueConfig(
                        bucket=self.KV_BUCKET,
                        max_value_size=256,
                        history=1,
                        ttl=86400 * 7,
                    ))
                except Exception:
                    log.warning("KV bucket creation failed -- dedup disabled")
                    self._kv = None

            self._connected = True
            log.info("NATS JetStream connected to %s", self._nats_url)
        except Exception:
            log.warning("NATS connection failed -- falling back to in-memory store", exc_info=True)
            self._fallback = True
            self._ensure_fallback_db()

    async def close(self):
        if self._nc and self._connected:
            try:
                await self._nc.close()
            except Exception:
                pass
        self._connected = False
        if self._fb_conn:
            try:
                self._fb_conn.close()
            except Exception:
                pass
            self._fb_conn = None

    # -------------------------------------------------- stream management -------

    async def _ensure_stream(self, topic: str):
        """Create a JetStream stream for the given topic if it doesn't exist."""
        if not self._connected or self._js is None:
            return
        stream_name = self._stream_name(topic)
        subject = f"sylion.{topic}"
        try:
            await self._js.stream_info(stream_name)
        except Exception:
            try:
                from nats.js.api import StreamConfig, RetentionPolicy, StorageType
                await self._js.add_stream(StreamConfig(
                    name=stream_name,
                    subjects=[subject],
                    retention=RetentionPolicy.LIMITS,
                    storage=StorageType.FILE,
                    max_msgs=50_000,
                    max_age=86400 * 30,
                ))
                log.debug("created stream %s for topic %s", stream_name, topic)
            except Exception:
                log.debug("stream creation failed for %s (may already exist)", stream_name)

    @classmethod
    def _stream_name(cls, topic: str) -> str:
        """Convert dotted topic to a valid NATS stream name."""
        return f"{cls.STREAM_PREFIX}{topic.replace('.', '_').upper()}"

    # --------------------------------------------------- serialisation ----------

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

    # --------------------------------------------------- publish ----------------

    def publish(self, topic: str, payload: dict[str, Any] | None = None,
                source_module: str = "") -> str:
        """Publish an event. Returns event_id. Idempotent via idempotency_key."""
        event = SylionEvent(
            event_id="",
            topic=topic,
            payload=payload or {},
            source_module=source_module,
        )
        if self._fallback or not self._connected:
            return self._publish_fallback(event)
        try:
            return self._run_async(self._publish_nats(event))
        except Exception:
            log.warning("NATS publish failed -- falling back to in-memory", exc_info=True)
            self._fallback = True
            self._ensure_fallback_db()
            return self._publish_fallback(event)

    async def _publish_nats(self, event: SylionEvent) -> str:
        if not event.event_id:
            event.event_id = uuid.uuid4().hex
        if not event.timestamp:
            event.timestamp = time.time()
        if not event.idempotency_key:
            event.idempotency_key = event.event_id

        # Idempotency check via KV
        if self._kv is not None:
            try:
                existing = await self._kv.get(event.idempotency_key)
                if existing and existing.value:
                    existing_id = existing.value.decode("utf-8")
                    log.debug("dedup event %s (idem_key=%s)", event.event_id, event.idempotency_key)
                    return existing_id
            except Exception:
                pass

        await self._ensure_stream(event.topic)
        subject = f"sylion.{event.topic}"

        ack = await self._js.publish(
            subject,
            self._event_to_bytes(event),
            headers={"Nats-Msg-Id": event.idempotency_key},
        )
        log.debug("published %s to %s (seq=%s)", event.event_id, subject, ack.seq)

        # Store idempotency key
        if self._kv is not None:
            try:
                await self._kv.put(event.idempotency_key, event.event_id.encode("utf-8"))
            except Exception:
                log.warning("failed to store idempotency key %s", event.idempotency_key)

        # Local dispatch
        self._dispatch(event)
        return event.event_id

    def _publish_fallback(self, event: SylionEvent) -> str:
        """In-memory publish when NATS is unavailable."""
        if not event.event_id:
            event.event_id = uuid.uuid4().hex
        if not event.timestamp:
            event.timestamp = time.time()
        if not event.idempotency_key:
            event.idempotency_key = event.event_id

        with self._fb_lock:
            # Idempotency
            existing = self._fb_conn.execute(
                "SELECT event_id FROM events WHERE idempotency_key = ?",
                (event.idempotency_key,),
            ).fetchone()
            if existing:
                return existing["event_id"]

            self._fb_conn.execute(
                "INSERT INTO events (event_id, topic, payload, source_module, timestamp, idempotency_key) VALUES (?,?,?,?,?,?)",
                (event.event_id, event.topic, json.dumps(event.payload, default=str),
                 event.source_module, event.timestamp, event.idempotency_key),
            )
            self._fb_conn.commit()

        self._dispatch(event)
        return event.event_id

    # --------------------------------------------------- dispatch ---------------

    def _dispatch(self, event: SylionEvent):
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

    # --------------------------------------------------- subscribe --------------

    def subscribe(self, topic: str, handler: EventHandler) -> str:
        """Subscribe to *topic* (use '*' for all). Returns subscription_id."""
        sub_id = _next_sub_id()
        if topic == "*":
            self._wildcard_subs.append(handler)
        else:
            self._subscribers[topic].append(handler)
        self._sub_map[sub_id] = (topic, handler)

        # Set up NATS push subscription when connected
        if self._connected and not self._fallback:
            try:
                self._run_async(self._subscribe_nats(topic))
            except Exception:
                log.debug("NATS push subscription setup failed for %s", topic)

        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription by its id."""
        if subscription_id not in self._sub_map:
            return
        topic, handler = self._sub_map.pop(subscription_id)
        if topic == "*":
            if handler in self._wildcard_subs:
                self._wildcard_subs.remove(handler)
        else:
            handlers = self._subscribers.get(topic)
            if handlers and handler in handlers:
                handlers.remove(handler)

    async def _subscribe_nats(self, topic: str):
        if not self._connected or self._js is None:
            return
        subject = "sylion.>" if topic == "*" else f"sylion.{topic}"

        async def _cb(msg):
            event = self._bytes_to_event(msg.data)
            self._dispatch(event)

        try:
            stream_name = "SYLION_WILDCARD" if topic == "*" else self._stream_name(topic)
            # Ensure a wildcard stream exists
            if topic == "*":
                try:
                    await self._js.stream_info(stream_name)
                except Exception:
                    from nats.js.api import StreamConfig, RetentionPolicy, StorageType
                    await self._js.add_stream(StreamConfig(
                        name=stream_name,
                        subjects=["sylion.>"],
                        retention=RetentionPolicy.LIMITS,
                        storage=StorageType.FILE,
                        max_msgs=100_000,
                        max_age=86400 * 30,
                    ))
            sub = await self._js.subscribe(subject, cb=_cb, stream=stream_name)
            self._nats_push_subs.append(sub)
        except Exception:
            log.debug("push subscription failed for %s", subject)

    # --------------------------------------------------- ack --------------------

    def ack(self, event_id: str) -> bool:
        """Acknowledge an event. In NATS mode this is a no-op (JetStream acks)."""
        if self._fallback and self._fb_conn:
            with self._fb_lock:
                updated = self._fb_conn.execute(
                    "UPDATE events SET acked = 1 WHERE event_id = ?",
                    (event_id,),
                ).rowcount
                self._fb_conn.commit()
            return bool(updated)
        # NATS mode: no-op
        return True

    # --------------------------------------------------- get_events -------------

    def get_events(self, topic: str | None = None, limit: int = 100) -> list[dict]:
        """Retrieve stored events, newest first."""
        if self._fallback or not self._connected:
            return self._get_events_fallback(topic, limit)
        try:
            return self._run_async(self._get_events_nats(topic, limit))
        except Exception:
            return self._get_events_fallback(topic, limit)

    def _get_events_fallback(self, topic: str | None, limit: int) -> list[dict]:
        if self._fb_conn is None:
            return []
        q = "SELECT * FROM events WHERE 1=1"
        params: list[Any] = []
        if topic:
            q += " AND topic = ?"
            params.append(topic)
        q += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        with self._fb_lock:
            return [dict(r) for r in self._fb_conn.execute(q, params).fetchall()]

    async def _get_events_nats(self, topic: str | None, limit: int) -> list[dict]:
        if not self._connected or self._js is None:
            return []
        results: list[dict] = []
        try:
            subject = "sylion.>" if not topic else f"sylion.{topic}"
            stream_name = "SYLION_WILDCARD" if not topic else self._stream_name(topic)

            # Ensure wildcard stream
            if not topic:
                try:
                    await self._js.stream_info(stream_name)
                except Exception:
                    from nats.js.api import StreamConfig, RetentionPolicy, StorageType
                    await self._js.add_stream(StreamConfig(
                        name=stream_name,
                        subjects=["sylion.>"],
                        retention=RetentionPolicy.LIMITS,
                        storage=StorageType.FILE,
                        max_msgs=100_000,
                        max_age=86400 * 30,
                    ))

            sub = await self._js.pull_subscribe(
                subject,
                durable="sylion_query",
                stream=stream_name,
            )
            try:
                msgs = await sub.fetch(limit, timeout=2)
                for msg in msgs:
                    event_dict = json.loads(msg.data.decode("utf-8"))
                    results.append(event_dict)
                    await msg.ack()
            except asyncio.TimeoutError:
                pass
            finally:
                await sub.unsubscribe()
        except Exception:
            log.debug("NATS query failed", exc_info=True)

        results.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return results[:limit]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_bus_instance: SQLiteEventBus | NATSEventBus | None = None
_factory_lock = threading.Lock()


def get_event_bus(mode: str | None = None, **kwargs) -> SQLiteEventBus | NATSEventBus:
    """Return the singleton event bus for the given mode.

    Args:
        mode: "sqlite" or "nats". If None, reads SYLION_EVENT_MODE env var.
              Defaults to "sqlite".
        **kwargs:
            nats_url (str): NATS server URL (default "nats://localhost:4222")
            db_path  (str): SQLite DB path (default ":memory:")

    Returns:
        SQLiteEventBus or NATSEventBus instance (same public API).
    """
    global _bus_instance

    if mode is None:
        mode = os.environ.get("SYLION_EVENT_MODE", "sqlite").lower().strip()

    if mode not in ("sqlite", "nats"):
        log.warning("invalid SYLION_EVENT_MODE=%r, falling back to 'sqlite'", mode)
        mode = "sqlite"

    with _factory_lock:
        if _bus_instance is not None:
            return _bus_instance

        if mode == "sqlite":
            db_path = kwargs.get("db_path", None)
            _bus_instance = SQLiteEventBus(db_path=db_path)
            log.debug("created SQLiteEventBus singleton")
        else:
            nats_url = kwargs.get("nats_url", "nats://localhost:4222")
            _bus_instance = NATSEventBus(nats_url=nats_url)
            log.debug("created NATSEventBus singleton (call connect() before use)")

        return _bus_instance


def reset_event_bus():
    """Clear the singleton. For testing only."""
    global _bus_instance
    with _factory_lock:
        _bus_instance = None
