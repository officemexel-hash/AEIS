"""Per-topic event dispatcher.

Most lifecycle events are async-style: emit a card without blocking.
H13 (production deploy) and H16 (final approval) are synchronous gates and are
handled by `sync_gate.evaluate_gate` instead of via this dispatcher.
"""

from __future__ import annotations

import logging
from typing import Any

from sylion.core.event_bus import SylionEvent
from sylion.aeis.advisor.engine.orchestrator import process_event

log = logging.getLogger("sylion.aeis.advisor.engine.lifecycle.handlers")


def dispatch_event(event: SylionEvent) -> None:
    """Async-style dispatch: routes through orchestrator and emits any cards."""
    topic = event.topic
    payload = event.payload or {}
    operator_id = (
        payload.get("operator_id")
        or payload.get("user_id")
        or "00000000-0000-0000-0000-000000000000"
    )

    cards = process_event(
        topic=topic,
        payload=payload,
        operator_id=operator_id,
        triggering_event_id=event.event_id,
    )
    if cards:
        log.info(
            "engine produced %d card(s) for topic=%s operator=%s",
            len(cards),
            topic,
            operator_id,
        )
