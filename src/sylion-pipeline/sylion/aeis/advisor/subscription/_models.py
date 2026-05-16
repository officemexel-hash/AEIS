"""AEIS Advisor — Subscription models."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class UsageRecord:
    """A single usage record."""

    record_id: str = ""
    operator_id: str = ""
    provider_id: str = ""
    model_id: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.record_id:
            self.record_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "operator_id": self.operator_id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": self.cost_usd,
            "timestamp": self.timestamp,
        }


@dataclass
class UsageReport:
    """Aggregated usage report."""

    operator_id: str = ""
    period_start: float = 0.0
    period_end: float = 0.0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_usd: float = 0.0
    record_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total_tokens_in": self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "total_cost_usd": self.total_cost_usd,
            "record_count": self.record_count,
        }


@dataclass
class Plan:
    """A subscription plan."""

    plan_id: str = ""
    provider_id: str = ""
    monthly_price_usd: float = 0.0
    included_tokens: int = 0
    rate_limits: dict[str, Any] = field(default_factory=dict)
    is_assumption: bool = False
    source_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "provider_id": self.provider_id,
            "monthly_price_usd": self.monthly_price_usd,
            "included_tokens": self.included_tokens,
            "rate_limits": self.rate_limits,
            "is_assumption": self.is_assumption,
            "source_url": self.source_url,
        }


@dataclass
class SubscriptionQuota:
    """Active operator subscription with quota metadata."""

    subscription_id: str = ""
    operator_id: str = ""
    provider_id: str = ""
    plan_id: str = ""
    monthly_quota_tokens: int | None = None
    monthly_quota_usd: Decimal | None = None
    reset_day_of_month: int = 1
    models_covered: list[str] = field(default_factory=list)
    active_from: datetime | None = None
    active_until: datetime | None = None
    monthly_fee_usd: Decimal | None = None
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "subscription_id": self.subscription_id,
            "operator_id": self.operator_id,
            "provider_id": self.provider_id,
            "plan_id": self.plan_id,
            "monthly_quota_tokens": self.monthly_quota_tokens,
            "monthly_quota_usd": self.monthly_quota_usd,
            "reset_day_of_month": self.reset_day_of_month,
            "models_covered": list(self.models_covered),
            "active_from": self.active_from,
            "active_until": self.active_until,
            "monthly_fee_usd": self.monthly_fee_usd,
            "is_active": self.is_active,
        }


@dataclass
class ROICalculation:
    """ROI calculation for a subscription plan."""

    operator_id: str = ""
    plan_id: str = ""
    observation_window_days: int = 30
    usage_cost_without_plan: float = 0.0
    plan_cost: float = 0.0
    break_even_days: float | None = None
    recommendation: str = ""  # keep | upgrade | downgrade | purchase

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "plan_id": self.plan_id,
            "observation_window_days": self.observation_window_days,
            "usage_cost_without_plan": self.usage_cost_without_plan,
            "plan_cost": self.plan_cost,
            "break_even_days": self.break_even_days,
            "recommendation": self.recommendation,
        }


@dataclass
class RecommendationCard:
    """A recommendation card emitted by subscription advisor."""

    card_id: str = ""
    d_level: str = ""  # D3, D4, D5
    recommendation_type: str = ""  # PURCHASE_PLAN, DOWNGRADE, etc.
    evidence_pack_id: str | None = None
    human_gate_required: bool = False
    operator_id: str = ""
    plan_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.card_id:
            self.card_id = uuid.uuid4().hex
