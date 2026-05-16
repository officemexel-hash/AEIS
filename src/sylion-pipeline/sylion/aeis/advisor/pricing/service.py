"""Pricing service for AEIS advisor."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock
from typing import Any

from sylion.aeis.advisor.pricing import _db
from sylion.aeis.advisor.pricing._models import CostEstimate, Model, PricingSnapshot, Provider, Source
from sylion.aeis.advisor.pricing.catalog import (
    get_model,
    get_provider,
    initialize_catalog,
    list_models,
    list_providers,
    register_dynamic_adapter,
)
from sylion.aeis.advisor.pricing.estimator import estimate_cost
from sylion.aeis.advisor.pricing.refresher import initialize_pricing_catalog, refresh_provider_pricing
from sylion.core.event_backbone import get_event_backbone
from sylion.core.event_bus import SylionEvent

log = logging.getLogger("sylion.aeis.advisor.pricing.service")


class PricingService:
    """Service facade for pricing operations."""

    def __init__(self, event_bus: Any | None = None):
        self._event_bus = event_bus or get_event_backbone()
        self._lock = Lock()

    def initialize(self) -> None:
        """Seed default providers and models."""
        with self._lock:
            initialize_pricing_catalog()

    def get_cost(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        cache_hit_tokens: int = 0,
    ) -> CostEstimate:
        """Return the current cost estimate for one call."""
        blocked_providers = self._get_blocked_providers()
        model = get_model(model_id)
        if model is not None and model.provider_id in blocked_providers:
            now = datetime.now(timezone.utc)
            self._emit(
                "aeis.advisor.pricing.assumption_used",
                {"model_id": model_id, "provider_id": model.provider_id, "reason": "provider_blocked"},
            )
            return CostEstimate(
                model_id=model_id,
                provider_id=model.provider_id,
                total_cost_usd=Decimal("0"),
                input_cost_usd=Decimal("0"),
                output_cost_usd=Decimal("0"),
                cache_cost_usd=Decimal("0"),
                source=Source.ASSUMPTION,
                is_assumption=True,
                assumption_note="Provider blocked by operator preferences",
                pricing_effective_from=now,
                pricing_id="",
            )

        estimate = estimate_cost(model_id, input_tokens, output_tokens, cache_hit_tokens)
        if estimate.is_assumption:
            self._emit(
                "aeis.advisor.pricing.assumption_used",
                {"model_id": model_id, "provider_id": estimate.provider_id, "note": estimate.assumption_note or ""},
            )
        return estimate

    def refresh_pricing(self, provider_id: str, force: bool = False) -> dict[str, Any]:
        """Refresh pricing for one provider."""
        self.initialize()
        result = refresh_provider_pricing(provider_id, force=force)
        for event_name in result.get("events", []):
            self._emit(f"aeis.advisor.pricing.{event_name}", {"provider_id": provider_id})
        return {
            "refreshed_count": int(result["refreshed_count"]),
            "failed_count": int(result["failed_count"]),
            "used_live": bool(result["used_live"]),
            "assumption_fallback": bool(result["assumption_fallback"]),
        }

    def list_providers(self, active_only: bool = True) -> list[Provider]:
        """List visible providers."""
        self.initialize()
        return list_providers(active_only=active_only, blocked_providers=self._get_blocked_providers())

    def list_models(
        self,
        provider_id: str | None = None,
        include_deprecated: bool = False,
    ) -> list[Model]:
        """List visible models."""
        self.initialize()
        return list_models(
            provider_id=provider_id,
            include_deprecated=include_deprecated,
            blocked_providers=self._get_blocked_providers(),
        )

    def register_adapter(
        self,
        provider_id: str,
        display_name: str,
        is_local: bool,
        metadata_url: str,
        adapter_class_path: str,
    ) -> tuple[bool, str]:
        """Register a dynamic adapter."""
        success, error = register_dynamic_adapter(
            provider_id=provider_id,
            display_name=display_name,
            is_local=is_local,
            metadata_url=metadata_url,
            adapter_class_path=adapter_class_path,
        )
        return success, error

    def get_pricing_history(
        self,
        model_id: str,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[PricingSnapshot]:
        """Return pricing history snapshots."""
        rows = _db.get_pricing_history(model_id=model_id, since=since, limit=limit)
        return [
            PricingSnapshot(
                history_id=str(row["history_id"]),
                model_id=str(row["model_id"]),
                fetched_at=row["fetched_at"],
                source=Source(str(row["source"])),
                is_assumption=bool(row["is_assumption"]),
                error_message=row.get("error_message"),
            )
            for row in rows
        ]

    def get_provider(self, provider_id: str) -> Provider | None:
        """Return provider metadata."""
        return get_provider(provider_id)

    def get_model(self, model_id: str) -> Model | None:
        """Return model metadata."""
        model = get_model(model_id)
        if model is None:
            return None
        if model.provider_id in self._get_blocked_providers():
            return None
        return model

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(
            SylionEvent(
                event_id=str(uuid.uuid4()),
                topic=topic,
                payload=payload,
                source_module="sylion.aeis.advisor.pricing",
                timestamp=time.time(),
                idempotency_key=f"{topic}:{payload.get('provider_id', payload.get('model_id', 'global'))}",
            )
        )

    def _get_blocked_providers(self) -> set[str]:
        """Best-effort preferences integration."""
        try:
            from sylion.aeis.advisor.preferences.service import get_preferences
        except Exception:
            return set()
        try:
            resolver = get_preferences()
            blocked = resolver.get_blocked_providers()  # type: ignore[attr-defined]
        except Exception:
            return set()
        return {str(item) for item in blocked}
