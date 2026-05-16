"""
SYLION Core — Event Bus Factory

Dual-mode adapter:
  - "inprocess" (default): SQLite-backed EventBus (for tests and dev-light)
  - "nats": NATS JetStream NATSEventBus (for staging-strict and prod-strict)

Mode is controlled by the SYLION_EVENT_MODE environment variable.
Both modes return a singleton instance managed per mode.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from sylion.core.event_bus import EventBus

log = logging.getLogger("sylion.core.event_bus_factory")

# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------

_VALID_MODES = ("inprocess", "nats")


def get_event_bus_mode() -> str:
    """Read SYLION_EVENT_MODE env var. Defaults to 'inprocess'."""
    mode = os.environ.get("SYLION_EVENT_MODE", "inprocess").lower().strip()
    if mode not in _VALID_MODES:
        log.warning(
            "invalid SYLION_EVENT_MODE=%r, falling back to 'inprocess'", mode
        )
        mode = "inprocess"
    return mode


# ---------------------------------------------------------------------------
# Singleton registry
# ---------------------------------------------------------------------------

_instances: dict[str, Any] = {}
_lock = threading.Lock()


def create_event_bus(mode: str | None = None, **kwargs) -> EventBus:
    """Create or return the singleton EventBus for the given mode.

    Args:
        mode: "inprocess" or "nats". If None, reads SYLION_EVENT_MODE env var.
        **kwargs: Passed to the EventBus constructor.
            - inprocess: db_path
            - nats: nats_url (default "nats://localhost:4222")

    Returns:
        EventBus (inprocess) or NATSEventBus (nats). Both share the same API.
    """
    if mode is None:
        mode = get_event_bus_mode()

    if mode not in _VALID_MODES:
        raise ValueError(f"invalid event bus mode: {mode!r}. Must be one of {_VALID_MODES}")

    with _lock:
        if mode in _instances:
            return _instances[mode]

        if mode == "inprocess":
            db_path = kwargs.get("db_path", None)
            bus = EventBus(db_path=db_path)
            _instances[mode] = bus
            log.debug("created inprocess EventBus singleton")
            return bus

        if mode == "nats":
            from sylion.core.nats_adapter import NATSEventBus
            nats_url = kwargs.get("nats_url", "nats://localhost:4222")
            bus = NATSEventBus(nats_url=nats_url)
            _instances[mode] = bus
            log.debug("created NATSEventBus singleton (not yet connected — call connect())")
            return bus

        # Should not reach here
        raise ValueError(f"unhandled mode: {mode}")


def reset_event_bus():
    """Clear singleton instances. Useful for testing."""
    with _lock:
        _instances.clear()
