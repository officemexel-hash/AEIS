"""Variants fixtures for deterministic local advisor tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest


_MODELS = {
    "claude-sonnet-4-6": ("anthropic", Decimal("3000"), Decimal("15000")),
    "claude-opus-4-7": ("anthropic", Decimal("15000"), Decimal("75000")),
    "gpt-5": ("openai", Decimal("10000"), Decimal("30000")),
    "gemini-2.5-pro": ("google", Decimal("5000"), Decimal("20000")),
    "qwen2.5:72b-instruct": ("local", Decimal("0"), Decimal("0")),
    "qwen2.5:7b-instruct": ("local", Decimal("0"), Decimal("0")),
}


@pytest.fixture(autouse=True)
def _variants_local_runtime(monkeypatch):
    from sylion.aeis.advisor.variants.service import reset_variants_service

    reset_variants_service()

    def _catalog_model(model_id: str):
        row = _MODELS.get(model_id)
        if row is None:
            return None
        provider_id, _, _ = row
        return SimpleNamespace(model_id=model_id, provider_id=provider_id)

    def _db_model(model_id: str):
        row = _MODELS.get(model_id)
        if row is None:
            return None
        provider_id, _, _ = row
        return {"model_id": model_id, "provider_id": provider_id}

    def _active_pricing(model_id: str):
        row = _MODELS.get(model_id)
        if row is None:
            return None
        _, input_price, output_price = row
        return {
            "pricing_id": f"price:{model_id}",
            "input_tokens_usd_per_million": input_price,
            "output_tokens_usd_per_million": output_price,
            "cache_hit_tokens_usd_per_million": Decimal("0"),
            "source": "profile",
            "is_assumption": False,
            "assumption_note": None,
            "effective_from": datetime.now(timezone.utc),
        }

    monkeypatch.setattr("sylion.aeis.advisor.pricing.catalog.get_model", _catalog_model)
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.catalog.list_models",
        lambda **_: [_catalog_model(model_id) for model_id in _MODELS],
    )
    monkeypatch.setattr("sylion.aeis.advisor.pricing.estimator._db.get_model", _db_model)
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.estimator._db.get_active_pricing",
        _active_pricing,
    )

    yield

    reset_variants_service()
