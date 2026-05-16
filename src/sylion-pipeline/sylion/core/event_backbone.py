"""
SYLION Core - Event Backbone

Abstraction over event transport: local SQLite, NATS, or Redis.
Selected via SYLION_EVENT_MODE env var (default: sqlite).

Backends:
  - local / sqlite -> uses the existing EventBus (single-node)
  - nats           -> real publish/subscribe runtime over NATS
  - redis          -> real publish/subscribe runtime over Redis Pub/Sub

Distributed backends expose honest runtime semantics:
  - publish/subscribe require a live transport
  - query/replay/catalog raise explicit unsupported errors instead of
    returning fake success payloads
  - health reports real transport readiness plus degraded capabilities
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, TypeVar

from sylion.core.event_bus import EventBus, EventHandler, SylionEvent

log = logging.getLogger("sylion.core.event_backbone")

T = TypeVar("T")


def _run_coro_sync(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Run an async coroutine from sync code, even if an event loop is active."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())

    result: dict[str, T] = {}
    error: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(coro_factory())
        except BaseException as exc:  # pragma: no cover - propagated below
            error["value"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if "value" in error:
        raise error["value"]
    return result["value"]


class EventBackboneError(RuntimeError):
    """Structured runtime error for event backbone operations."""

    def __init__(
        self,
        backend: str,
        operation: str,
        message: str,
        *,
        status: str = "error",
        http_status: int = 503,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.backend = backend
        self.operation = operation
        self.status = status
        self.http_status = http_status
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "backend": self.backend,
            "operation": self.operation,
            "status": self.status,
            "message": str(self),
        }
        if self.details:
            payload["details"] = self.details
        return payload


# ---------------------------------------------------------------------------
# Base backend
# ---------------------------------------------------------------------------


class BackboneBackend(ABC):
    """Abstract event backbone backend."""

    @abstractmethod
    def publish(self, event: SylionEvent) -> str:
        ...

    @abstractmethod
    def subscribe(self, topic: str, handler: EventHandler) -> None:
        ...

    @abstractmethod
    def query(
        self,
        topic: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_catalog(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def replay(self, topic: str, handler: EventHandler, since: float | None = None) -> None:
        ...

    @abstractmethod
    def health(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def close(self) -> None:
        ...


# ---------------------------------------------------------------------------
# Local / SQLite backend (wraps EventBus)
# ---------------------------------------------------------------------------


class LocalBackbone(BackboneBackend):
    """Wrap the existing SQLite EventBus for single-node deployments."""

    def __init__(self, event_bus: EventBus | None = None):
        from sylion.core.event_bus import get_event_bus

        self._bus = event_bus or get_event_bus()
        self._published = 0
        self._subscribed = 0

    def publish(self, event: SylionEvent) -> str:
        self._published += 1
        return self._bus.publish(event)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._subscribed += 1
        self._bus.subscribe(topic, handler)

    def query(
        self,
        topic: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._bus.query(topic=topic, since=since, limit=limit)

    def get_catalog(self) -> dict[str, Any]:
        return self._bus.get_catalog()

    def replay(self, topic: str, handler: EventHandler, since: float | None = None) -> None:
        events = self._bus.query(topic=topic, since=since, limit=10_000)
        for row in reversed(events):
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            handler(
                SylionEvent(
                    event_id=row["event_id"],
                    topic=row["topic"],
                    payload=payload,
                    source_module=row["source_module"],
                    timestamp=row["timestamp"],
                    idempotency_key=row.get("idempotency_key", row["event_id"]),
                )
            )

    def health(self) -> dict[str, Any]:
        catalog = self.get_catalog()
        return {
            "backend": "local",
            "status": "ok",
            "ready": True,
            "connected": True,
            "published": self._published,
            "subscribed": self._subscribed,
            "catalog_size": len(catalog),
            "capabilities": {
                "publish": "ok",
                "subscribe": "ok",
                "query": "ok",
                "catalog": "ok",
                "replay": "ok",
            },
        }

    def close(self) -> None:
        pass


class _DistributedBackbone(BackboneBackend):
    """Shared helpers for distributed runtimes."""

    backend_name = "distributed"

    def __init__(self) -> None:
        self._published = 0
        self._subscribed = 0
        self._last_error: str | None = None
        self._last_checked_at: float | None = None
        self._lock = threading.Lock()
        self._closed = False

    def _mark_error(self, exc: Exception | str) -> None:
        self._last_error = str(exc)
        self._last_checked_at = time.time()

    def _mark_ready(self) -> None:
        self._last_error = None
        self._last_checked_at = time.time()

    def _unsupported_error(self, operation: str, message: str) -> EventBackboneError:
        return EventBackboneError(
            self.backend_name,
            operation,
            message,
            status="degraded",
            http_status=501,
        )

    def _runtime_error(
        self,
        operation: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> EventBackboneError:
        return EventBackboneError(
            self.backend_name,
            operation,
            message,
            status="error",
            http_status=503,
            details=details,
        )

    @abstractmethod
    def _capabilities(self, ready: bool) -> dict[str, str]:
        ...


# ---------------------------------------------------------------------------
# NATS backend
# ---------------------------------------------------------------------------


class NATSBackbone(_DistributedBackbone):
    """NATS backend for distributed deployments."""

    backend_name = "nats"

    def __init__(self, url: str = "nats://localhost:4222", stream: str = "SYLION"):
        super().__init__()
        self._url = url
        self._stream = stream
        self._nc: Any | None = None
        self._nats_module: Any | None = None
        self._handlers: dict[str, list[EventHandler]] = {}
        self._subscriptions: dict[str, Any] = {}

    def _load_driver(self) -> Any:
        if self._nats_module is not None:
            return self._nats_module
        try:
            import nats
        except ImportError as exc:
            self._mark_error(exc)
            raise self._runtime_error(
                "connect",
                "NATS backend requires 'nats-py' and it is not installed",
                details={"dependency": "nats-py", "url": self._url},
            ) from exc
        self._nats_module = nats
        return nats

    def _is_connected(self) -> bool:
        return bool(self._nc and not getattr(self._nc, "is_closed", False))

    def _ensure_runtime(self) -> None:
        if self._closed:
            raise self._runtime_error("connect", "NATS backend has been closed")
        if self._is_connected():
            self._mark_ready()
            return

        with self._lock:
            if self._is_connected():
                self._mark_ready()
                return

            nats = self._load_driver()

            async def _connect() -> Any:
                return await nats.connect(
                    self._url,
                    connect_timeout=3,
                    reconnect=False,
                )

            try:
                self._nc = _run_coro_sync(_connect)
                self._mark_ready()
                log.info("NATS connected to %s", self._url)
            except EventBackboneError:
                raise
            except Exception as exc:
                self._nc = None
                self._mark_error(exc)
                raise self._runtime_error(
                    "connect",
                    f"unable to connect to NATS at {self._url}: {exc}",
                    details={"url": self._url},
                ) from exc

    @staticmethod
    def _serialize_event(event: SylionEvent) -> bytes:
        return json.dumps(event.to_dict(), default=str).encode("utf-8")

    @staticmethod
    def _deserialize_event(raw_payload: bytes | str, fallback_topic: str) -> SylionEvent:
        if isinstance(raw_payload, bytes):
            text = raw_payload.decode("utf-8")
        else:
            text = raw_payload
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"payload": text}
        if not isinstance(payload, dict):
            payload = {"payload": payload}

        return SylionEvent(
            event_id=str(payload.get("event_id") or ""),
            topic=str(payload.get("topic") or fallback_topic),
            payload=payload.get("payload", {}),
            source_module=str(payload.get("source_module") or ""),
            timestamp=float(payload.get("timestamp") or 0.0),
            idempotency_key=str(payload.get("idempotency_key") or ""),
        )

    def _subscribe_subject(self, topic: str) -> str:
        return ">" if topic == "*" else topic

    def publish(self, event: SylionEvent) -> str:
        self._ensure_runtime()

        async def _publish() -> None:
            await self._nc.publish(event.topic, self._serialize_event(event))
            await self._nc.flush()

        try:
            _run_coro_sync(_publish)
            self._published += 1
            self._mark_ready()
            return event.event_id
        except EventBackboneError:
            raise
        except Exception as exc:
            self._mark_error(exc)
            raise self._runtime_error(
                "publish",
                f"NATS publish failed for topic {event.topic}: {exc}",
                details={"topic": event.topic, "url": self._url},
            ) from exc

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._ensure_runtime()
        subject = self._subscribe_subject(topic)
        first_subscription = False

        with self._lock:
            if subject not in self._handlers:
                self._handlers[subject] = []
                first_subscription = True

        if first_subscription:

            async def _subscribe() -> Any:
                async def _callback(msg: Any) -> None:
                    event = self._deserialize_event(msg.data, getattr(msg, "subject", topic))
                    for registered in list(self._handlers.get(subject, [])):
                        try:
                            registered(event)
                        except Exception:
                            log.exception("NATS subscriber error for subject %s", subject)

                return await self._nc.subscribe(subject, cb=_callback)

            try:
                subscription = _run_coro_sync(_subscribe)
                with self._lock:
                    self._subscriptions[subject] = subscription
            except Exception as exc:
                with self._lock:
                    self._handlers.pop(subject, None)
                self._mark_error(exc)
                raise self._runtime_error(
                    "subscribe",
                    f"NATS subscribe failed for topic {topic}: {exc}",
                    details={"topic": topic, "url": self._url},
                ) from exc

        with self._lock:
            self._handlers.setdefault(subject, []).append(handler)
            self._subscribed += 1
        self._mark_ready()

    def query(
        self,
        topic: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        raise self._unsupported_error(
            "query",
            "NATS backbone does not provide event history query in this runtime",
        )

    def get_catalog(self) -> dict[str, Any]:
        raise self._unsupported_error(
            "catalog",
            "NATS backbone does not provide a global topic catalog in this runtime",
        )

    def replay(self, topic: str, handler: EventHandler, since: float | None = None) -> None:
        raise self._unsupported_error(
            "replay",
            "NATS backbone cannot replay historical events in this runtime",
        )

    def _capabilities(self, ready: bool) -> dict[str, str]:
        runtime_state = "ok" if ready else "unavailable"
        return {
            "publish": runtime_state,
            "subscribe": runtime_state,
            "query": "unsupported",
            "catalog": "unsupported",
            "replay": "unsupported",
        }

    def health(self) -> dict[str, Any]:
        ready = False
        try:
            self._ensure_runtime()
            ready = True
        except EventBackboneError:
            ready = False

        status = "degraded" if ready else "error"
        return {
            "backend": "nats",
            "status": status,
            "ready": ready,
            "connected": ready,
            "url": self._url,
            "stream": self._stream,
            "published": self._published,
            "subscribed": self._subscribed,
            "last_error": self._last_error,
            "last_checked_at": self._last_checked_at,
            "capabilities": self._capabilities(ready),
        }

    def close(self) -> None:
        self._closed = True
        if self._nc is None:
            return

        async def _close() -> None:
            await self._nc.close()

        try:
            _run_coro_sync(_close)
        except Exception:
            log.debug("NATS close failed", exc_info=True)
        finally:
            self._nc = None
            self._subscriptions.clear()
            self._handlers.clear()


# ---------------------------------------------------------------------------
# Redis backend
# ---------------------------------------------------------------------------


class RedisBackbone(_DistributedBackbone):
    """Redis Pub/Sub backend for distributed deployments."""

    backend_name = "redis"

    def __init__(self, url: str = "redis://localhost:6379/0"):
        super().__init__()
        self._url = url
        self._client: Any | None = None
        self._pubsub: Any | None = None
        self._listener: Any | None = None
        self._redis_module: Any | None = None
        self._handlers: dict[str, list[EventHandler]] = {}
        self._pattern_handlers: dict[str, list[EventHandler]] = {}

    def _load_driver(self) -> Any:
        if self._redis_module is not None:
            return self._redis_module
        try:
            import redis
        except ImportError as exc:
            self._mark_error(exc)
            raise self._runtime_error(
                "connect",
                "Redis backbone requires 'redis' and it is not installed",
                details={"dependency": "redis", "url": self._url},
            ) from exc
        self._redis_module = redis
        return redis

    def _ensure_listener(self) -> None:
        if self._listener is not None:
            return
        self._listener = self._pubsub.run_in_thread(sleep_time=0.01, daemon=True)

    def _ensure_client(self) -> None:
        if self._closed:
            raise self._runtime_error("connect", "Redis backbone has been closed")
        if self._client is not None:
            try:
                self._client.ping()
                self._mark_ready()
                return
            except Exception:
                self._client = None
                self._pubsub = None
                self._listener = None

        with self._lock:
            if self._client is not None:
                try:
                    self._client.ping()
                    self._mark_ready()
                    return
                except Exception:
                    self._client = None
                    self._pubsub = None
                    self._listener = None

            redis = self._load_driver()
            try:
                self._client = redis.from_url(
                    self._url,
                    decode_responses=True,
                    socket_connect_timeout=3,
                    socket_timeout=3,
                )
                self._pubsub = self._client.pubsub(ignore_subscribe_messages=True)
                self._client.ping()
                self._mark_ready()
                log.info("Redis connected to %s", self._url)
            except EventBackboneError:
                raise
            except Exception as exc:
                self._client = None
                self._pubsub = None
                self._listener = None
                self._mark_error(exc)
                raise self._runtime_error(
                    "connect",
                    f"unable to connect to Redis at {self._url}: {exc}",
                    details={"url": self._url},
                ) from exc

    @staticmethod
    def _serialize_event(event: SylionEvent) -> str:
        return json.dumps(event.to_dict(), default=str)

    @staticmethod
    def _deserialize_event(raw_payload: Any, fallback_topic: str) -> SylionEvent:
        if isinstance(raw_payload, bytes):
            text = raw_payload.decode("utf-8")
        else:
            text = str(raw_payload)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"payload": text}
        if not isinstance(payload, dict):
            payload = {"payload": payload}

        return SylionEvent(
            event_id=str(payload.get("event_id") or ""),
            topic=str(payload.get("topic") or fallback_topic),
            payload=payload.get("payload", {}),
            source_module=str(payload.get("source_module") or ""),
            timestamp=float(payload.get("timestamp") or 0.0),
            idempotency_key=str(payload.get("idempotency_key") or ""),
        )

    def _dispatch_event(self, registration_key: str, event: SylionEvent) -> None:
        handlers = list(self._handlers.get(registration_key, []))
        handlers.extend(self._pattern_handlers.get(registration_key, []))
        for registered in handlers:
            try:
                registered(event)
            except Exception:
                log.exception("Redis subscriber error for key %s", registration_key)

    def _handle_message(self, message: dict[str, Any]) -> None:
        channel = str(message.get("channel") or "")
        event = self._deserialize_event(message.get("data"), channel)
        self._dispatch_event(channel, event)

    def _handle_pattern_message(self, message: dict[str, Any]) -> None:
        pattern = str(message.get("pattern") or "")
        channel = str(message.get("channel") or "")
        event = self._deserialize_event(message.get("data"), channel)
        self._dispatch_event(pattern, event)

    def publish(self, event: SylionEvent) -> str:
        self._ensure_client()
        try:
            self._client.publish(event.topic, self._serialize_event(event))
            self._published += 1
            self._mark_ready()
            return event.event_id
        except Exception as exc:
            self._mark_error(exc)
            raise self._runtime_error(
                "publish",
                f"Redis publish failed for topic {event.topic}: {exc}",
                details={"topic": event.topic, "url": self._url},
            ) from exc

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._ensure_client()
        is_pattern = topic == "*"
        target_map = self._pattern_handlers if is_pattern else self._handlers
        subscribe_fn = self._pubsub.psubscribe if is_pattern else self._pubsub.subscribe
        callback = self._handle_pattern_message if is_pattern else self._handle_message

        first_subscription = False
        with self._lock:
            if topic not in target_map:
                target_map[topic] = []
                first_subscription = True

        if first_subscription:
            try:
                subscribe_fn(**{topic: callback})
                self._ensure_listener()
            except Exception as exc:
                with self._lock:
                    target_map.pop(topic, None)
                self._mark_error(exc)
                raise self._runtime_error(
                    "subscribe",
                    f"Redis subscribe failed for topic {topic}: {exc}",
                    details={"topic": topic, "url": self._url},
                ) from exc

        with self._lock:
            target_map.setdefault(topic, []).append(handler)
            self._subscribed += 1
        self._mark_ready()

    def query(
        self,
        topic: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        raise self._unsupported_error(
            "query",
            "Redis Pub/Sub does not provide event history query in this runtime",
        )

    def get_catalog(self) -> dict[str, Any]:
        raise self._unsupported_error(
            "catalog",
            "Redis Pub/Sub does not provide a global topic catalog in this runtime",
        )

    def replay(self, topic: str, handler: EventHandler, since: float | None = None) -> None:
        raise self._unsupported_error(
            "replay",
            "Redis Pub/Sub cannot replay historical events in this runtime",
        )

    def _capabilities(self, ready: bool) -> dict[str, str]:
        runtime_state = "ok" if ready else "unavailable"
        return {
            "publish": runtime_state,
            "subscribe": runtime_state,
            "query": "unsupported",
            "catalog": "unsupported",
            "replay": "unsupported",
        }

    def health(self) -> dict[str, Any]:
        ready = False
        try:
            self._ensure_client()
            ready = True
        except EventBackboneError:
            ready = False

        status = "degraded" if ready else "error"
        return {
            "backend": "redis",
            "status": status,
            "ready": ready,
            "connected": ready,
            "url": self._url,
            "published": self._published,
            "subscribed": self._subscribed,
            "last_error": self._last_error,
            "last_checked_at": self._last_checked_at,
            "capabilities": self._capabilities(ready),
        }

    def close(self) -> None:
        self._closed = True
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                log.debug("Redis listener stop failed", exc_info=True)
        if self._pubsub is not None:
            try:
                self._pubsub.close()
            except Exception:
                log.debug("Redis pubsub close failed", exc_info=True)
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                log.debug("Redis client close failed", exc_info=True)
        self._listener = None
        self._pubsub = None
        self._client = None
        self._handlers.clear()
        self._pattern_handlers.clear()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


_backbone_instance: EventBackbone | None = None


class EventBackbone:
    """Factory + wrapper for the active backbone backend."""

    def __init__(self, mode: str | None = None, **kwargs: Any):
        self._mode = (mode or os.environ.get("SYLION_EVENT_MODE", "sqlite")).lower()
        self._backend = self._create_backend(**kwargs)
        log.info("EventBackbone initialized with mode=%s", self._mode)

    def _create_backend(self, **kwargs: Any) -> BackboneBackend:
        if self._mode in ("local", "sqlite"):
            return LocalBackbone(**kwargs)
        if self._mode == "nats":
            url = os.environ.get("NATS_URL", "nats://localhost:4222")
            stream = os.environ.get("NATS_STREAM", "SYLION")
            return NATSBackbone(url=url, stream=stream)
        if self._mode == "redis":
            url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            return RedisBackbone(url=url)
        raise ValueError(f"Unknown event backbone mode: {self._mode}")

    def publish(self, event: SylionEvent) -> str:
        return self._backend.publish(event)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._backend.subscribe(topic, handler)

    def query(
        self,
        topic: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._backend.query(topic=topic, since=since, limit=limit)

    def get_catalog(self) -> dict[str, Any]:
        return self._backend.get_catalog()

    def replay(self, topic: str, handler: EventHandler, since: float | None = None) -> None:
        self._backend.replay(topic, handler, since=since)

    def health(self) -> dict[str, Any]:
        payload = self._backend.health()
        payload["mode"] = self._mode
        return payload

    def close(self) -> None:
        self._backend.close()

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def backend(self) -> BackboneBackend:
        return self._backend


def get_event_backbone(mode: str | None = None, **kwargs: Any) -> EventBackbone:
    global _backbone_instance
    if _backbone_instance is None:
        _backbone_instance = EventBackbone(mode=mode, **kwargs)
    return _backbone_instance


def reset_event_backbone() -> None:
    global _backbone_instance
    if _backbone_instance is not None:
        _backbone_instance.close()
    _backbone_instance = None
