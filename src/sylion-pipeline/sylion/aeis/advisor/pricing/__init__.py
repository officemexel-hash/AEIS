"""AEIS Advisor pricing module."""

from __future__ import annotations

from threading import Lock

from sylion.aeis.advisor.pricing.service import PricingService

_service: PricingService | None = None
_lock = Lock()


def get_pricing() -> PricingService:
    """Return the singleton pricing service."""
    global _service
    if _service is None:
        with _lock:
            if _service is None:
                _service = PricingService()
    return _service


def reset_pricing() -> None:
    """Reset the pricing singleton for tests."""
    global _service
    with _lock:
        _service = None


__all__ = ["PricingService", "get_pricing", "reset_pricing"]
