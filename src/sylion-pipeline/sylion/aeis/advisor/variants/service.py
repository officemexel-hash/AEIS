"""AEIS Advisor — Variants service."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sylion.aeis.advisor.variants._models import VariantSet
from sylion.aeis.advisor.variants.generator import generate_variants, compare_variants
from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.aeis.advisor.variants.service")


class VariantsService:
    """Service for generating and comparing strategic variants."""

    def __init__(self, event_bus: EventBus | None = None):
        self._event_bus = event_bus or get_event_bus()
        self._history: dict[str, VariantSet] = {}

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id=str(uuid.uuid4()),
                topic=topic,
                payload=payload,
                source_module="sylion.aeis.advisor.variants",
                timestamp=time.time(),
            ))

    def generate_variants(self, context: dict[str, Any] | None = None) -> VariantSet:
        """Generate 3 strategic variants for a project context."""
        variant_set = generate_variants(context)
        self._history[variant_set.context_id] = variant_set

        self._emit("aeis.advisor.variants.generated", {
            "context_id": variant_set.context_id,
            "variant_count": len(variant_set.variants),
            "variant_names": [v.name for v in variant_set.variants],
        })

        log.info("generated %d variants for context %s",
                 len(variant_set.variants), variant_set.context_id)
        return variant_set

    def compare_variants(self, variant_ids: list[str],
                         context_id: str | None = None) -> dict[str, Any]:
        """Compare selected variants by dimensions."""
        variant_set = self._history.get(context_id) if context_id else None
        if variant_set is None:
            # Try latest
            if self._history:
                variant_set = list(self._history.values())[-1]
            else:
                return {"variant_ids": variant_ids, "dimensions": [], "error": "no variants"}

        result = compare_variants(variant_ids, variant_set)

        self._emit("aeis.advisor.variants.compared", {
            "context_id": context_id or "latest",
            "variant_ids": variant_ids,
            "dimensions": [d["dimension"] for d in result.get("dimensions", [])],
        })

        return result


_service: VariantsService | None = None


def get_variants_service(event_bus: EventBus | None = None) -> VariantsService:
    """Get or create the global VariantsService singleton."""
    global _service
    if _service is None:
        _service = VariantsService(event_bus=event_bus)
    return _service


def reset_variants_service() -> None:
    """Reset singleton for tests."""
    global _service
    _service = None
