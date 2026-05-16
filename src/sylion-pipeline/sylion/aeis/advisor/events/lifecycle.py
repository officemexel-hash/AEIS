"""Helpers for AEIS advisor lifecycle hook events."""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from sylion.core.event_backbone import get_event_backbone
from sylion.core.event_bus import SylionEvent

AdvisorDecision = Literal["proceed", "block", "defer_to_human_gate"]


def publish_lifecycle_event(
    topic: str,
    payload: dict[str, Any],
    *,
    source_module: str,
    primary_key: str,
) -> str:
    """Publish a lifecycle event on the shared event backbone."""
    event = SylionEvent(
        event_id=str(uuid.uuid4()),
        topic=topic,
        payload=payload,
        source_module=source_module,
        timestamp=time.time(),
        idempotency_key=f"{topic}:{primary_key}",
    )
    return get_event_backbone().publish(event)


def await_advisor_decision(
    event_id: str,
    timeout_s: float = 5.0,
) -> dict[str, Any]:
    """Placeholder synchronous gate until the engine subscriber exists."""
    _ = event_id, timeout_s
    return {"decision": "proceed"}
