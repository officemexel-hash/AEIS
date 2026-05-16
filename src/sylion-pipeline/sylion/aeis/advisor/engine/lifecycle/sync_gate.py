"""Synchronous gate for H13 production deploy and H16 final approval.

The endpoint that emits the lifecycle event also calls `evaluate_gate(...)`
synchronously and waits up to `timeout_s` for the engine's verdict. The engine
may produce a BLOCK card (e.g. `REC_TYPE_BLOCK_PRODUCTION_DEPLOY` when SoT is
not approved), in which case the endpoint returns 423 with the card_id.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from sylion.aeis.advisor.engine.orchestrator import process_event

log = logging.getLogger("sylion.aeis.advisor.engine.lifecycle.sync_gate")


@dataclass
class GateDecision:
    decision: str  # 'proceed' | 'block' | 'defer_to_human_gate'
    blocking_card_id: str = ""
    created_human_gate_ticket_id: str = ""
    reason: str = ""


def evaluate_gate(
    *,
    topic: str,
    payload: dict[str, Any],
    operator_id: str,
    triggering_event_id: str = "",
    timeout_s: float = 5.0,
) -> GateDecision:
    """Run the engine for `topic`+`payload`; if a BLOCK card emits, return BLOCK."""
    start = time.time()
    try:
        cards = process_event(
            topic=topic,
            payload=payload,
            operator_id=operator_id,
            triggering_event_id=triggering_event_id,
            sync_gate=True,
        )
    except Exception as exc:
        log.exception("sync_gate evaluation failed; defaulting to PROCEED")
        return GateDecision(decision="proceed", reason=f"engine_error:{exc}")

    elapsed = time.time() - start
    if elapsed > timeout_s:
        log.warning("sync_gate exceeded timeout=%.2fs (took %.2fs); proceeding", timeout_s, elapsed)

    block_types = {"REC_TYPE_BLOCK_PRODUCTION_DEPLOY"}
    defer_types = {"REC_TYPE_HUMAN_GATE_BATCH"}

    for card in cards:
        body = card.body()
        if body is None:
            continue
        rec_type = getattr(body, "recommendation_type", "")
        if rec_type in block_types or card.header.d_level == "D5":
            return GateDecision(
                decision="block",
                blocking_card_id=card.header.card_id,
                reason=f"blocked_by_card:{rec_type or card.header.title}",
            )
        if rec_type in defer_types:
            return GateDecision(
                decision="defer_to_human_gate",
                blocking_card_id=card.header.card_id,
                reason=f"defer_by_card:{rec_type}",
            )

    return GateDecision(decision="proceed")
