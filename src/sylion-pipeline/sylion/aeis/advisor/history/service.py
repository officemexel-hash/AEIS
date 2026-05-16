"""History service singleton.

Public facade used by REST/gRPC adapters, the engine confidence calculator,
and tests. Subscribes to:
  - `aeis.advisor.actions.action_routed`        -> record_action
  - `aeis.advisor.engine.recommendation_emitted` -> light card emission snapshot

Emits (best-effort; never crashes on bus failure):
  - `aeis.advisor.history.action_recorded`
  - `aeis.advisor.history.learning_signal_emitted`
  - `aeis.advisor.history.soft_learning_applied`
  - `aeis.advisor.history.hard_change_requested`
  - `aeis.advisor.history.skip_learning_recorded`

Threading.Lock-guarded init mirrors the pattern in
`sylion/governance/council_workflow.py` and the engine's `service.py`.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any

from sylion.aeis.advisor.history._db import (
    fetch_actions_for_card,
    fetch_actions_for_operator,
    fetch_learning_signals,
    fetch_pending_hard_change_signals,
    fetch_signal_by_id,
    init_history_schema,
    insert_card_emission,
)
from sylion.aeis.advisor.history._models import CardAction, LearningSignal
from sylion.aeis.advisor.history.confidence_provider.historical_acceptance import (
    get_historical_acceptance_snapshot,
)
from sylion.aeis.advisor.history.confidence_provider.history_match import (
    get_history_match_snapshot,
)
from sylion.aeis.advisor.history.learning.hard_learning import (
    confirm_hard_change as _confirm_hard_change,
)
from sylion.aeis.advisor.history.learning.hard_learning import (
    reject_hard_change as _reject_hard_change,
)
from sylion.aeis.advisor.history.learning.soft_learning import apply_soft_signal
from sylion.aeis.advisor.history.recorder import RecordResult, record_action

log = logging.getLogger("sylion.aeis.advisor.history.service")


class AdvisorHistoryService:
    """High-level facade. Holds no per-request state; safe to share."""

    def __init__(self) -> None:
        init_history_schema()
        self._subscribed = 0
        self._lock = threading.Lock()
        self._event_bus: Any = None

    # -- subscriptions --------------------------------------------------

    def attach_to_event_bus(self, event_bus: Any) -> int:
        """Wire the two inbound subscriptions. Returns count subscribed."""
        with self._lock:
            self._event_bus = event_bus
            self._subscribed = _register_subscribers(event_bus, self)
        log.info("history attached to event_bus, %d subscriptions", self._subscribed)
        return self._subscribed

    # -- recording ------------------------------------------------------

    def record_action(
        self,
        *,
        card_id: str,
        operator_id: str,
        action: str,
        operator_note: str = "",
        modified_recommendation: str = "",
        context: dict[str, Any] | None = None,
    ) -> str:
        result = record_action(
            card_id=card_id,
            operator_id=operator_id,
            action=action,
            operator_note=operator_note,
            modified_recommendation=modified_recommendation,
            context=context,
        )
        self._dispatch_record_events(result)
        return result.action.action_event_id

    def record_card_emission(
        self,
        *,
        card_id: str,
        operator_id: str,
        recommendation_type: str = "",
        project_type: str = "",
        project_domain: str = "",
        risk_level: str = "",
        emitted_at: float | None = None,
    ) -> None:
        """Lightweight snapshot for trend analysis. Does not enter the action log."""
        insert_card_emission(
            card_id=card_id,
            operator_id=operator_id,
            recommendation_type=recommendation_type,
            project_type=project_type,
            project_domain=project_domain,
            risk_level=risk_level,
            emitted_at=emitted_at if emitted_at is not None else time.time(),
        )

    # -- queries --------------------------------------------------------

    def list_actions_for_card(self, card_id: str) -> list[CardAction]:
        return fetch_actions_for_card(card_id)

    def list_actions_for_operator(
        self, operator_id: str, limit: int = 100
    ) -> list[CardAction]:
        return fetch_actions_for_operator(operator_id, limit=limit)

    def list_learning_signals(
        self, operator_id: str, *, only_unapplied: bool = False
    ) -> list[LearningSignal]:
        return fetch_learning_signals(operator_id, only_unapplied=only_unapplied)

    # -- confidence components -----------------------------------------

    def get_history_match_snapshot(
        self,
        *,
        operator_id: str,
        recommendation_type: str,
        project_type: str | None = None,
        project_domain: str | None = None,
    ) -> dict[str, Any]:
        return get_history_match_snapshot(
            operator_id=operator_id,
            recommendation_type=recommendation_type,
            project_type=project_type,
            project_domain=project_domain,
        )

    def get_historical_acceptance_snapshot(
        self,
        *,
        operator_id: str,
        recommendation_type: str,
    ) -> dict[str, Any]:
        return get_historical_acceptance_snapshot(
            operator_id=operator_id, recommendation_type=recommendation_type
        )

    # -- soft / hard learning ------------------------------------------

    def apply_pending_learning(self, operator_id: str) -> int:
        applied = 0
        for signal in fetch_learning_signals(operator_id, only_unapplied=True):
            if signal.hard_change_status == "pending":
                continue
            if signal.signal_type == "preference_save":
                continue
            result = apply_soft_signal(signal)
            self._emit(
                "aeis.advisor.history.soft_learning_applied",
                {
                    "signal_id": signal.signal_id,
                    "operator_id": signal.operator_id,
                    "preference_key": signal.preference_key,
                    "applied": bool(result.get("applied")),
                    "reason": result.get("reason", ""),
                },
            )
            if result.get("applied"):
                applied += 1
        return applied

    def list_pending_hard_change_requests(
        self, operator_id: str
    ) -> list[dict[str, Any]]:
        return [
            _signal_to_dict(s) for s in fetch_pending_hard_change_signals(operator_id)
        ]

    def confirm_hard_change(self, *, signal_id: str, operator_id: str) -> bool:
        ok = _confirm_hard_change(signal_id=signal_id, operator_id=operator_id)
        if ok:
            signal = fetch_signal_by_id(signal_id)
            self._emit(
                "aeis.advisor.history.soft_learning_applied",
                {
                    "signal_id": signal_id,
                    "operator_id": operator_id,
                    "preference_key": signal.preference_key if signal else "",
                    "applied": bool(signal and signal.applied_to_preference),
                    "reason": "hard_change_confirmed",
                },
            )
        return ok

    def reject_hard_change(self, *, signal_id: str, operator_id: str) -> bool:
        return _reject_hard_change(signal_id=signal_id, operator_id=operator_id)

    # -- internals ------------------------------------------------------

    def _dispatch_record_events(self, result: RecordResult) -> None:
        action = result.action
        self._emit(
            "aeis.advisor.history.action_recorded",
            {
                "action_event_id": action.action_event_id,
                "card_id": action.card_id,
                "operator_id": action.operator_id,
                "action": action.action,
                "performed_at": action.performed_at,
                "triggered_soft_learning": action.triggered_soft_learning,
                "triggered_hard_learning_request": action.triggered_hard_learning_request,
            },
        )

        if result.skip_learning:
            self._emit(
                "aeis.advisor.history.skip_learning_recorded",
                {
                    "action_event_id": action.action_event_id,
                    "card_id": action.card_id,
                    "operator_id": action.operator_id,
                    "reason": result.skip_learning_reason,
                },
            )
            return

        signal = result.signal
        if signal is None:
            return

        self._emit(
            "aeis.advisor.history.learning_signal_emitted",
            {
                "signal_id": signal.signal_id,
                "operator_id": signal.operator_id,
                "signal_type": signal.signal_type,
                "preference_key": signal.preference_key,
                "context_project_type": signal.context_project_type,
                "context_project_domain": signal.context_project_domain,
                "signal_strength": signal.signal_strength,
                "source_card_id": signal.source_card_id,
                "source_action_event_id": signal.source_action_event_id,
            },
        )

        if result.hard_change_requested:
            self._emit(
                "aeis.advisor.history.hard_change_requested",
                {
                    "signal_id": signal.signal_id,
                    "operator_id": signal.operator_id,
                    "preference_key": signal.preference_key,
                    "context_project_type": signal.context_project_type,
                    "context_project_domain": signal.context_project_domain,
                    "source_card_id": signal.source_card_id,
                },
            )
            return

        if signal.signal_type in ("card_acceptance", "card_rejection"):
            apply_result = apply_soft_signal(signal)
            self._emit(
                "aeis.advisor.history.soft_learning_applied",
                {
                    "signal_id": signal.signal_id,
                    "operator_id": signal.operator_id,
                    "preference_key": signal.preference_key,
                    "applied": bool(apply_result.get("applied")),
                    "reason": apply_result.get("reason", ""),
                },
            )

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        bus = self._event_bus
        if bus is None:
            return
        try:
            from sylion.core.event_bus import SylionEvent

            event = SylionEvent(
                event_id=uuid.uuid4().hex,
                topic=topic,
                payload=payload,
                source_module="sylion.aeis.advisor.history",
                timestamp=time.time(),
                idempotency_key=payload.get("action_event_id")
                or payload.get("signal_id")
                or "",
            )
            publish = getattr(bus, "publish", None)
            if publish is not None:
                publish(event)
        except Exception:  # pragma: no cover - best effort
            log.exception("event emit failed for topic=%s", topic)


def _signal_to_dict(signal: LearningSignal) -> dict[str, Any]:
    return {
        "signal_id": signal.signal_id,
        "operator_id": signal.operator_id,
        "signal_type": signal.signal_type,
        "preference_key": signal.preference_key,
        "context_project_type": signal.context_project_type,
        "context_project_domain": signal.context_project_domain,
        "signal_strength": signal.signal_strength,
        "source_card_id": signal.source_card_id,
        "source_action_event_id": signal.source_action_event_id,
        "applied_to_preference": signal.applied_to_preference,
        "applied_at": signal.applied_at,
        "created_at": signal.created_at,
        "hard_change_status": signal.hard_change_status,
    }


# ---------------------------------------------------------------------------
# Subscriber wiring
# ---------------------------------------------------------------------------


HISTORY_SUBSCRIBED_TOPICS = (
    "aeis.advisor.actions.action_routed",
    "aeis.advisor.engine.recommendation_emitted",
)


def _register_subscribers(event_bus: Any, service: AdvisorHistoryService) -> int:
    from sylion.core.event_bus import SylionEvent

    def _handler(event: SylionEvent) -> None:
        try:
            _dispatch_inbound(event, service)
        except Exception:
            log.exception("history handler failed for topic=%s", event.topic)

    count = 0
    if not hasattr(event_bus, "subscribe"):
        return 0
    for topic in HISTORY_SUBSCRIBED_TOPICS:
        try:
            event_bus.subscribe(topic, _handler)
            count += 1
        except Exception:
            log.exception("subscribe failed topic=%s", topic)
    if hasattr(event_bus, "subscribe_pattern"):
        try:
            event_bus.subscribe_pattern("aeis.advisor.actions.*", _handler)
            count += 1
        except Exception:
            pass
    return count


def register_subscribers(event_bus: Any) -> int:
    """Module-level subscriber registration (matches engine pattern)."""
    return get_history_service().attach_to_event_bus(event_bus)


def _dispatch_inbound(event: Any, service: AdvisorHistoryService) -> None:
    topic = getattr(event, "topic", "")
    payload = getattr(event, "payload", {}) or {}
    if topic == "aeis.advisor.actions.action_routed":
        card_id = str(payload.get("card_id", ""))
        operator_id = str(payload.get("operator_id", ""))
        action = str(payload.get("action", ""))
        if not card_id or not operator_id or not action:
            return
        context = payload.get("context")
        if not isinstance(context, dict):
            context = {}
        # Carry through known fields the actions module attaches.
        for key in ("recommendation_type", "project_type", "project_domain", "preference_key"):
            if key in payload and key not in context:
                context[key] = payload[key]
        service.record_action(
            card_id=card_id,
            operator_id=operator_id,
            action=action,
            operator_note=str(payload.get("operator_note", "")),
            modified_recommendation=str(payload.get("modified_recommendation", "")),
            context=context,
        )
        return

    if topic == "aeis.advisor.engine.recommendation_emitted":
        card_id = str(payload.get("card_id", ""))
        operator_id = str(payload.get("operator_id", ""))
        if not card_id or not operator_id:
            return
        service.record_card_emission(
            card_id=card_id,
            operator_id=operator_id,
            recommendation_type=str(payload.get("recommendation_type", "")),
            project_type=str(payload.get("project_type", "")),
            project_domain=str(payload.get("project_domain", "")),
            risk_level=str(payload.get("risk_level", "")),
            emitted_at=float(payload.get("emitted_at") or time.time()),
        )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------


_service: AdvisorHistoryService | None = None
_service_lock = threading.Lock()


def get_history_service() -> AdvisorHistoryService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = AdvisorHistoryService()
    return _service


def reset_history_service() -> None:
    """For tests: drop the singleton."""
    global _service
    with _service_lock:
        _service = None
