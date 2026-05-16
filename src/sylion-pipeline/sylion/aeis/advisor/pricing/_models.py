"""SYLION AEIS Advisor pricing models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class Source(str, Enum):
    """Origin of pricing data."""

    ASSUMPTION = "assumption"
    PROFILE = "profile"
    MEASURED = "measured"
    SUBSCRIPTION = "subscription"


@dataclass(frozen=True)
class Provider:
    """Provider metadata."""

    provider_id: str
    display_name: str
    is_local: bool
    is_active: bool
    metadata_url: str | None = None


@dataclass(frozen=True)
class Model:
    """Model metadata."""

    model_id: str
    provider_id: str
    display_name: str
    context_window: int | None
    is_local: bool
    capabilities: list[str] = field(default_factory=list)
    is_default_judge: bool = False
    is_default_local: bool = False
    is_deprecated: bool = False


@dataclass(frozen=True)
class PricingTable:
    """Pricing data for one model at a point in time."""

    pricing_id: str
    model_id: str
    input_tokens_usd_per_million: Decimal | None
    output_tokens_usd_per_million: Decimal | None
    cache_hit_tokens_usd_per_million: Decimal | None
    source: Source
    source_url: str | None
    is_assumption: bool
    assumption_note: str | None
    effective_from: datetime
    effective_until: datetime | None


@dataclass(frozen=True)
class CostEstimate:
    """Computed cost estimate."""

    model_id: str
    provider_id: str
    total_cost_usd: Decimal
    input_cost_usd: Decimal
    output_cost_usd: Decimal
    cache_cost_usd: Decimal
    source: Source
    is_assumption: bool
    assumption_note: str | None
    pricing_effective_from: datetime
    pricing_id: str


@dataclass(frozen=True)
class PricingSnapshot:
    """Historical pricing fetch result."""

    history_id: str
    model_id: str
    fetched_at: datetime
    source: Source
    is_assumption: bool
    error_message: str | None
