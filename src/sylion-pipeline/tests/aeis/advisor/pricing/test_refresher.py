"""Refresher tests for advisor pricing."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from sylion.aeis.advisor.pricing.refresher import refresh_provider_pricing


def test_profile_pricing_marks_profile(monkeypatch):
    adapter = SimpleNamespace(
        is_local=False,
        is_available=lambda: True,
        list_models=lambda: [{"model_id": "claude-sonnet-4-6"}],
        fetch_live_pricing=lambda model_id: SimpleNamespace(
            input_tokens_usd_per_million=Decimal("3.00"),
            output_tokens_usd_per_million=Decimal("15.00"),
            cache_hit_tokens_usd_per_million=Decimal("0.30"),
            source_url="https://example.test",
            raw_response={"profile_used": True},
        ),
    )
    captured = {"history": []}
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.refresher.get_adapter",
        lambda provider_id: adapter,
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.refresher._db.insert_pricing_table",
        lambda **kwargs: captured.setdefault("table", kwargs) or "price-1",
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.refresher._db.insert_pricing_history",
        lambda **kwargs: captured["history"].append(kwargs) or "hist-1",
    )

    result = refresh_provider_pricing("anthropic")
    assert result["refreshed_count"] == 1
    assert result["events"] == ["profile_updated", "refreshed"]
    assert captured["history"][0]["source"] == "profile"


def test_adapter_failure_falls_back_to_assumption(monkeypatch):
    adapter = SimpleNamespace(
        is_local=False,
        is_available=lambda: True,
        list_models=lambda: [{"model_id": "broken-model"}],
        fetch_live_pricing=lambda model_id: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    history = []
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.refresher.get_adapter",
        lambda provider_id: adapter,
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.refresher._db.insert_pricing_history",
        lambda **kwargs: history.append(kwargs) or "hist-1",
    )

    result = refresh_provider_pricing("anthropic")
    assert result["failed_count"] == 1
    assert "adapter_failed" in result["events"]
    assert history[0]["is_assumption"] is True
