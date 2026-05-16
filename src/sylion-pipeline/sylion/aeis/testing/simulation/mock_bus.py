"""Isolated mock event bus for W14 simulation sandboxes.

The mock bus implements the same ``publish(event)`` interface as
``sylion.core.event_bus.EventBus`` but never broadcasts to the real
subscribers and never persists events to the production SQLite. Each
sandbox owns its own ``MockEventBus`` instance, so there is no shared
state between simulations.

Use cases:
    - L1 program execution that emits events without disturbing the host
    - L2-L4 persona simulation where the test wants to inspect what
      events would have fired in production
    - Replay capture: ``mock_bus.replay()`` returns the captured trace
      with original ordering preserved
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any

log = logging.getLogger("sylion.aeis.testing.simulation.mock_bus")


class MockEventBus:
    """In-memory event bus that captures events instead of broadcasting.

    Thread-safe: a single RLock guards both publish and replay, so a
    sandbox can be driven from a worker thread without losing events.
    """

    def __init__(self, simulation_id: str = "") -> None:
        self.simulation_id = simulation_id
        self._lock = threading.RLock()
        self._events: list[dict[str, Any]] = []
        self._subscribers: dict[str, list] = {}

    # ------------------------------------------------------------------
    # Publisher API (mirrors core.event_bus.EventBus)
    # ------------------------------------------------------------------

    def publish(self, event: Any) -> str:
        """Capture an event. Returns a deterministic event id."""
        topic = (
            getattr(event, "topic", None)
            or getattr(event, "event_type", None)
            or type(event).__name__
        )
        payload = getattr(event, "payload", {}) or {}
        event_id = (
            getattr(event, "event_id", "") or uuid.uuid4().hex
        )
        captured = {
            "event_id": event_id,
            "topic": topic,
            "payload": dict(payload),
            "source_module": getattr(event, "source_module", "")
            or getattr(event, "producer_module", ""),
            "ts": time.time(),
            "simulation_id": self.simulation_id,
        }
        with self._lock:
            self._events.append(captured)
            local_subs = list(self._subscribers.get(topic, []))
        for handler in local_subs:
            try:
                handler(event)
            except Exception:  # pragma: no cover
                log.exception("mock subscriber failed for topic %s", topic)
        return event_id

    def subscribe(self, topic: str, handler) -> None:
        """Register an in-process subscriber. Calls only on later publishes."""
        with self._lock:
            self._subscribers.setdefault(topic, []).append(handler)

    # ------------------------------------------------------------------
    # Inspection API (sandbox-only — never on production bus)
    # ------------------------------------------------------------------

    def replay(self, topic: str | None = None) -> list[dict[str, Any]]:
        """Return captured events, optionally filtered by topic."""
        with self._lock:
            if topic is None:
                return list(self._events)
            return [e for e in self._events if e["topic"] == topic]

    def count(self, topic: str | None = None) -> int:
        return len(self.replay(topic))

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._subscribers.clear()


__all__ = ["MockEventBus"]
