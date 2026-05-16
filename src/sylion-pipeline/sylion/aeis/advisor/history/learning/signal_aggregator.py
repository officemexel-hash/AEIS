"""Signal aggregator.

Per master_spec §9.3 soft-learning rules:
- accept rate >= 0.7 over last 5 cards of same recommendation_type ->
  emit soft signal (auto-apply attempt downstream)
- reject rate >= 0.7 -> same direction, opposite signal
- explicit `save_as_preference` action -> immediate hard_change_requested

Returns a `LearningSignal` (already persisted) or None when no threshold met.
"""

from __future__ import annotations

import logging
from typing import Any

from sylion.aeis.advisor.history._db import (
    fetch_recent_actions_for_operator_and_type,
    insert_learning_signal,
)
from sylion.aeis.advisor.history._models import CardAction, LearningSignal

log = logging.getLogger("sylion.aeis.advisor.history.learning.signal_aggregator")

SOFT_LEARNING_WINDOW = 5
SOFT_LEARNING_THRESHOLD = 0.7


def aggregate_signal_for_action(
    action: CardAction,
    *,
    recommendation_type: str,
    project_type: str = "",
    project_domain: str = "",
    preference_key: str = "",
) -> LearningSignal | None:
    """Inspect the rolling window and persist a learning signal if thresholds met.

    The `save_as_preference` action shortcuts the rolling-window check: any save
    is immediately a `preference_save` signal flagged for hard learning.
    """
    if action.action == "save_as_preference":
        signal = LearningSignal(
            operator_id=action.operator_id,
            signal_type="preference_save",
            preference_key=preference_key or recommendation_type,
            context_project_type=project_type,
            context_project_domain=project_domain,
            signal_strength=1.0,
            source_card_id=action.card_id,
            source_action_event_id=action.action_event_id,
            hard_change_status="pending",
        )
        insert_learning_signal(signal)
        return signal

    if action.action not in ("accept", "reject"):
        return None

    recent = fetch_recent_actions_for_operator_and_type(
        action.operator_id,
        recommendation_type,
        limit=SOFT_LEARNING_WINDOW,
    )
    accept_rate, reject_rate = _rates(recent)

    if accept_rate >= SOFT_LEARNING_THRESHOLD:
        signal_type = "card_acceptance"
        strength = accept_rate
    elif reject_rate >= SOFT_LEARNING_THRESHOLD:
        signal_type = "card_rejection"
        strength = reject_rate
    else:
        return None

    signal = LearningSignal(
        operator_id=action.operator_id,
        signal_type=signal_type,
        preference_key=preference_key or recommendation_type,
        context_project_type=project_type,
        context_project_domain=project_domain,
        signal_strength=float(strength),
        source_card_id=action.card_id,
        source_action_event_id=action.action_event_id,
    )
    insert_learning_signal(signal)
    return signal


def _rates(recent: list[CardAction]) -> tuple[float, float]:
    if not recent:
        return 0.0, 0.0
    n = len(recent)
    accepts = sum(1 for a in recent if a.action == "accept")
    rejects = sum(1 for a in recent if a.action == "reject")
    return accepts / n, rejects / n


def context_from_action(action: CardAction) -> dict[str, Any]:
    """Extract the context fields the aggregator depends on."""
    ctx = action.context or {}
    return {
        "recommendation_type": ctx.get("recommendation_type", ""),
        "project_type": ctx.get("project_type", ""),
        "project_domain": ctx.get("project_domain", ""),
        "preference_key": ctx.get("preference_key", ""),
        "dont_learn": bool(ctx.get("dont_learn", False)),
    }
