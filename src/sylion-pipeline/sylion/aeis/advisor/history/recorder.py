"""Card-action recorder.

Inserts an append-only `card_actions` row, then dispatches to the learning
loop subject to the `dont_learn` flag.

`dont_learn` resolution order:
1. `context["dont_learn"]` (truthy) — explicit flag from caller
2. `dont_learn_from_this` action — operator-marked card
3. engine row lookup (`advisor_engine_recommendations.dont_learn`) for the
   underlying card_id — best effort, treats missing rows as `False`

Returns a `RecordResult` that the service facade uses to decide which events
to emit (`action_recorded`, `learning_signal_emitted`, `skip_learning_recorded`,
`hard_change_requested`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sylion.aeis.advisor.history._db import insert_card_action, update_card_action_flags
from sylion.aeis.advisor.history._models import CardAction, LearningSignal
from sylion.aeis.advisor.history.learning.hard_learning import request_hard_change
from sylion.aeis.advisor.history.learning.signal_aggregator import (
    aggregate_signal_for_action,
    context_from_action,
)

log = logging.getLogger("sylion.aeis.advisor.history.recorder")


@dataclass
class RecordResult:
    action: CardAction
    skip_learning: bool = False
    skip_learning_reason: str = ""
    signal: LearningSignal | None = None
    hard_change_requested: bool = False
    enriched_context: dict[str, Any] = field(default_factory=dict)


def record_action(
    *,
    card_id: str,
    operator_id: str,
    action: str,
    operator_note: str = "",
    modified_recommendation: str = "",
    context: dict[str, Any] | None = None,
) -> RecordResult:
    enriched = dict(context or {})
    enriched_dont_learn = bool(enriched.get("dont_learn", False))
    if action == "dont_learn_from_this":
        enriched_dont_learn = True

    if not enriched_dont_learn:
        engine_dont_learn = _engine_dont_learn(card_id)
        if engine_dont_learn:
            enriched_dont_learn = True
            enriched.setdefault("dont_learn_source", "engine_recommendation")

    enriched["dont_learn"] = enriched_dont_learn

    card_action = CardAction(
        card_id=card_id,
        operator_id=operator_id,
        action=action,
        operator_note=operator_note,
        modified_recommendation=modified_recommendation,
        context=enriched,
    )
    insert_card_action(card_action)

    if enriched_dont_learn:
        return RecordResult(
            action=card_action,
            skip_learning=True,
            skip_learning_reason="dont_learn_flag",
            enriched_context=enriched,
        )

    ctx = context_from_action(card_action)
    if not ctx["recommendation_type"]:
        # No recommendation_type means the aggregator has nothing to bucket on;
        # we still return the action but skip signal building.
        return RecordResult(
            action=card_action,
            skip_learning=False,
            enriched_context=enriched,
        )

    signal = aggregate_signal_for_action(
        card_action,
        recommendation_type=ctx["recommendation_type"],
        project_type=ctx["project_type"],
        project_domain=ctx["project_domain"],
        preference_key=ctx["preference_key"],
    )

    if signal is None:
        return RecordResult(action=card_action, enriched_context=enriched)

    triggered_soft = signal.signal_type in ("card_acceptance", "card_rejection")
    triggered_hard = False
    if signal.signal_type == "preference_save":
        request_hard_change(signal)
        triggered_hard = True

    update_card_action_flags(
        action_event_id=card_action.action_event_id,
        triggered_soft_learning=triggered_soft,
        triggered_hard_learning_request=triggered_hard,
    )
    card_action.triggered_soft_learning = triggered_soft
    card_action.triggered_hard_learning_request = triggered_hard

    return RecordResult(
        action=card_action,
        signal=signal,
        hard_change_requested=triggered_hard,
        enriched_context=enriched,
    )


def _engine_dont_learn(card_id: str) -> bool:
    """Best-effort lookup of `dont_learn` on the engine's stored card row.

    Treat any failure (engine module not loaded, row missing, etc.) as False.
    """
    if not card_id:
        return False
    try:
        from sylion.aeis.advisor.engine.service import get_engine_service
    except Exception:
        return False
    try:
        svc = get_engine_service()
        env = svc.get_recommendation(card_id=card_id)
    except Exception:
        return False
    if not env:
        return False
    header = env.get("header") if isinstance(env, dict) else None
    if not header:
        return False
    return bool(header.get("dont_learn", False))
