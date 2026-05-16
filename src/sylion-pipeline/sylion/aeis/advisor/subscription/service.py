"""AEIS Advisor — Subscription service.

HARD GATE: This module NEVER auto-purchases.
All purchase recommendations MUST be D3+ with Evidence Pack.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sylion.aeis.advisor.subscription._models import (
    RecommendationCard,
    ROICalculation,
    UsageRecord,
    UsageReport,
)
from sylion.aeis.advisor.subscription.plan_catalog import (
    list_plans,
    get_plan,
    register_custom_plan,
)
from sylion.aeis.advisor.subscription.roi_calculator import compute_roi
from sylion.aeis.advisor.subscription.usage_tracker import (
    record_usage as _record_usage,
    get_usage_report as _get_usage_report,
)
from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.aeis.advisor.subscription.service")


class SubscriptionService:
    """Subscription advisor with HARD GATE on purchase recommendations."""

    def __init__(self, event_bus: EventBus | None = None):
        self._event_bus = event_bus or get_event_bus()

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id=str(uuid.uuid4()),
                topic=topic,
                payload=payload,
                source_module="sylion.aeis.advisor.subscription",
                timestamp=time.time(),
            ))

    def record_usage(
        self,
        operator_id: str,
        provider_id: str,
        model_id: str,
        tokens_in: int,
        tokens_out: int,
        cost: float,
    ) -> UsageRecord:
        """Record usage and emit threshold event if crossed."""
        rec = _record_usage(operator_id, provider_id, model_id, tokens_in, tokens_out, cost)

        # Simple threshold check: emit if daily cost > $10
        self._emit("aeis.advisor.subscription.usage_recorded", {
            "record_id": rec.record_id,
            "operator_id": operator_id,
            "cost_usd": cost,
        })

        # Check cumulative cost in last 24h
        import time
        day_ago = time.time() - 86400
        report = _get_usage_report(operator_id, day_ago, time.time())
        if report.total_cost_usd > 10.0:
            self._emit("aeis.advisor.subscription.usage_threshold_crossed", {
                "operator_id": operator_id,
                "daily_cost_usd": report.total_cost_usd,
                "threshold": 10.0,
            })

        return rec

    def get_usage_report(
        self,
        operator_id: str,
        period_start: float,
        period_end: float,
    ) -> UsageReport:
        """Get usage report for a period."""
        return _get_usage_report(operator_id, period_start, period_end)

    def compute_roi(
        self,
        operator_id: str,
        plan_id: str,
        observation_window_days: int = 30,
    ) -> ROICalculation:
        """Compute ROI for a plan."""
        return compute_roi(operator_id, plan_id, observation_window_days)

    def list_available_plans(self, provider_id: str | None = None) -> list[dict[str, Any]]:
        """List available subscription plans."""
        return [p.to_dict() for p in list_plans(provider_id)]

    def register_custom_plan(self, plan_data: dict[str, Any]) -> None:
        """Register a custom plan."""
        register_custom_plan(plan_data)
        self._emit("aeis.advisor.subscription.custom_plan_registered", {
            "plan_id": plan_data.get("plan_id"),
            "operator_id": plan_data.get("operator_id"),
        })

    def emit_purchase_recommendation(
        self,
        operator_id: str,
        plan_id: str,
        roi_calc: ROICalculation,
        evidence_pack_id: str,
    ) -> RecommendationCard:
        """Emit a PURCHASE_PLAN recommendation card.

        HARD GATE: card MUST have d_level >= D3 AND evidence_pack_id set.
        """
        card = RecommendationCard(
            d_level="D3",
            recommendation_type="PURCHASE_PLAN",
            evidence_pack_id=evidence_pack_id,
            human_gate_required=True,
            operator_id=operator_id,
            plan_id=plan_id,
            payload={"roi": roi_calc.to_dict()},
        )

        # HARD GATE assertions
        assert card.d_level in ("D3", "D4", "D5"), "subscription cards must be D3+"
        assert card.evidence_pack_id is not None, "subscription cards must have Evidence Pack"
        assert card.evidence_pack_id != "", "subscription cards must have non-empty Evidence Pack"
        assert card.human_gate_required is True, "subscription cards must require Human Gate"

        self._emit("aeis.advisor.subscription.purchase_recommended", {
            "card_id": card.card_id,
            "operator_id": operator_id,
            "plan_id": plan_id,
            "d_level": card.d_level,
            "evidence_pack_id": card.evidence_pack_id,
        })

        log.info("purchase recommendation emitted for %s plan=%s d_level=%s",
                 operator_id, plan_id, card.d_level)
        return card

    def emit_downgrade_recommendation(
        self,
        operator_id: str,
        plan_id: str,
        roi_calc: ROICalculation,
    ) -> RecommendationCard:
        """Emit a downgrade recommendation card."""
        card = RecommendationCard(
            d_level="D2",
            recommendation_type="DOWNGRADE",
            evidence_pack_id=None,
            human_gate_required=False,
            operator_id=operator_id,
            plan_id=plan_id,
            payload={"roi": roi_calc.to_dict()},
        )
        self._emit("aeis.advisor.subscription.downgrade_recommended", {
            "card_id": card.card_id,
            "operator_id": operator_id,
            "plan_id": plan_id,
            "d_level": card.d_level,
        })
        return card


_service: SubscriptionService | None = None


def get_subscription_service(event_bus: EventBus | None = None) -> SubscriptionService:
    """Get or create the global SubscriptionService singleton."""
    global _service
    if _service is None:
        _service = SubscriptionService(event_bus=event_bus)
    return _service


def reset_subscription_service() -> None:
    """Reset singleton for tests."""
    global _service
    _service = None
