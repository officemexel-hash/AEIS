"""Subscribe the engine to all 16 lifecycle hooks + companion + internal events."""

from __future__ import annotations

import logging
from typing import Any, Callable

from sylion.aeis.advisor.engine.lifecycle.handlers import dispatch_event
from sylion.core.event_bus import SylionEvent

log = logging.getLogger("sylion.aeis.advisor.engine.lifecycle.subscribers")


# 16 lifecycle hooks per docs/.../04_lifecycle_hooks.md
LIFECYCLE_HOOK_TOPICS = (
    "aeis.system.model_setup_requested",          # H01
    "aeis.system.api_provider_setup_requested",   # H02
    "aeis.system.budget_config_requested",        # H03
    "aeis.idea.intake.completed",                  # H04
    "aeis.idea.sot_model_selection_requested",    # H05
    "aeis.council.formation_requested",           # H06
    "aeis.system.autonomy_policy_change_requested",  # H07
    "aeis.idea.sot_drafted",                      # H08
    "aeis.masterplan.created",                    # H09
    "aeis.system.runtime_topology_change_requested",  # H10
    "aeis.system.vps_scaling_requested",          # H11
    "aeis.system.skill_selection_requested",      # H12
    "aeis.production.deploy_requested",           # H13 (synchronous gate)
    "aeis.testing.started",                       # H14
    "aeis.human_gate.ticket_pending",             # H15
    "aeis.final_approval.requested",              # H16 (synchronous gate)
)

COMPANION_TOPICS = (
    "aeis.system.budget_threshold_crossed",
    "aeis.council.formed",
    "aeis.idea.sot_approved",
    "aeis.idea.sot_rejected",
    "aeis.bundle.created",
    "aeis.production.deployed",
    "aeis.production.deploy_blocked",
    "aeis.testing.completed",
    "aeis.human_gate.ticket_decided",
    "aeis.security.audit_completed",
    "aeis.governance.policy_changed",
)

INTERNAL_ADVISOR_TOPICS = (
    "aeis.advisor.preferences.updated",
    "aeis.advisor.preferences.reset",
    "aeis.advisor.pricing.refreshed",
    "aeis.advisor.subscription.roi_computed",
)


ENGINE_SUBSCRIBED_TOPICS = LIFECYCLE_HOOK_TOPICS + COMPANION_TOPICS + INTERNAL_ADVISOR_TOPICS


def register_lifecycle_subscribers(event_bus: Any) -> int:
    """Wire dispatch_event() to all subscribed topics.

    `event_bus` must expose `subscribe(topic_or_pattern, handler)` taking a
    SylionEvent. The existing `sylion.core.event_bus.EventBus` qualifies.
    Returns count of subscriptions registered.
    """

    def _handler(event: SylionEvent) -> None:
        try:
            dispatch_event(event)
        except Exception:
            log.exception("engine handler failed for topic=%s", event.topic)

    count = 0
    if hasattr(event_bus, "subscribe"):
        for topic in ENGINE_SUBSCRIBED_TOPICS:
            try:
                event_bus.subscribe(topic, _handler)
                count += 1
            except Exception:
                log.exception("subscribe failed topic=%s", topic)
        # If the bus supports wildcard subscribe for advisor.* internal events,
        # add a broad listener too. We skip this if not available.
        if hasattr(event_bus, "subscribe_pattern"):
            try:
                event_bus.subscribe_pattern("aeis.advisor.*", _handler)
                count += 1
            except Exception:
                pass
    return count
