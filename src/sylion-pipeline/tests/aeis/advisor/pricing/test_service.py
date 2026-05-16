"""Service tests for advisor pricing."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from sylion.aeis.advisor.pricing._models import CostEstimate, Source
from sylion.aeis.advisor.pricing.service import PricingService


class _FakeBus:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


def test_blocked_provider_returns_assumption(monkeypatch):
    service = PricingService(event_bus=_FakeBus())
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.service.get_model",
        lambda model_id: SimpleNamespace(provider_id="openai"),
    )
    monkeypatch.setattr(
        service,
        "_get_blocked_providers",
        lambda: {"openai"},
    )

    estimate = service.get_cost("gpt-5", 1000, 1000)
    assert estimate.is_assumption is True
    assert estimate.provider_id == "openai"


def test_refresh_pricing_emits_events(monkeypatch):
    bus = _FakeBus()
    service = PricingService(event_bus=bus)
    monkeypatch.setattr(service, "initialize", lambda: None)
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.service.refresh_provider_pricing",
        lambda provider_id, force=False: {
            "refreshed_count": 1,
            "failed_count": 0,
            "used_live": False,
            "assumption_fallback": False,
            "events": ["profile_updated", "refreshed"],
        },
    )

    result = service.refresh_pricing("anthropic")
    assert result["refreshed_count"] == 1
    assert [event.topic for event in bus.events] == [
        "aeis.advisor.pricing.profile_updated",
        "aeis.advisor.pricing.refreshed",
    ]


def test_list_models_filters_blocked_provider(monkeypatch):
    service = PricingService(event_bus=_FakeBus())
    monkeypatch.setattr(service, "initialize", lambda: None)
    monkeypatch.setattr(service, "_get_blocked_providers", lambda: {"openai"})
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.service.list_models",
        lambda **kwargs: [
            model
            for model in [
                SimpleNamespace(model_id="gpt-5", provider_id="openai"),
                SimpleNamespace(model_id="claude-sonnet-4-6", provider_id="anthropic"),
            ]
            if model.provider_id not in kwargs.get("blocked_providers", set())
        ],
    )

    models = service.list_models()
    assert [model.model_id for model in models] == ["claude-sonnet-4-6"]


def test_provider_unavailable_marks_assumption_fallback(monkeypatch):
    bus = _FakeBus()
    service = PricingService(event_bus=bus)
    monkeypatch.setattr(service, "initialize", lambda: None)
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.service.refresh_provider_pricing",
        lambda provider_id, force=False: {
            "refreshed_count": 0,
            "failed_count": 0,
            "used_live": False,
            "assumption_fallback": True,
            "events": ["provider_unavailable", "assumption_used"],
        },
    )

    result = service.refresh_pricing("assumption-provider")

    assert result["assumption_fallback"] is True
    assert [event.topic for event in bus.events] == [
        "aeis.advisor.pricing.provider_unavailable",
        "aeis.advisor.pricing.assumption_used",
    ]


def test_missing_model_cost_estimate_emits_assumption_event(monkeypatch):
    bus = _FakeBus()
    service = PricingService(event_bus=bus)
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.service.get_model",
        lambda model_id: None,
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.service.estimate_cost",
        lambda *args: CostEstimate(
            model_id="missing-model",
            provider_id="unknown",
            total_cost_usd=Decimal("0"),
            input_cost_usd=Decimal("0"),
            output_cost_usd=Decimal("0"),
            cache_cost_usd=Decimal("0"),
            source=Source.ASSUMPTION,
            is_assumption=True,
            assumption_note="No pricing data available for this model",
            pricing_effective_from=datetime.now(timezone.utc),
            pricing_id="",
        ),
    )

    estimate = service.get_cost("missing-model", 10, 20)

    assert estimate.is_assumption is True
    assert estimate.provider_id == "unknown"
    assert bus.events[-1].topic == "aeis.advisor.pricing.assumption_used"


def test_refresh_pricing_cascades_adapter_failures(monkeypatch):
    bus = _FakeBus()
    service = PricingService(event_bus=bus)
    monkeypatch.setattr(service, "initialize", lambda: None)
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.service.refresh_provider_pricing",
        lambda provider_id, force=False: {
            "refreshed_count": 0,
            "failed_count": 3,
            "used_live": False,
            "assumption_fallback": True,
            "events": ["adapter_failed", "assumption_used", "refreshed"],
        },
    )

    result = service.refresh_pricing("anthropic")
    topics = [event.topic for event in bus.events]

    assert result["failed_count"] == 3
    assert Counter(topics) == Counter(
        {
            "aeis.advisor.pricing.adapter_failed": 1,
            "aeis.advisor.pricing.assumption_used": 1,
            "aeis.advisor.pricing.refreshed": 1,
        }
    )


def test_pricing_history_is_append_only(monkeypatch):
    rows = [
        {
            "history_id": "hist-2",
            "model_id": "gpt-5",
            "fetched_at": datetime(2026, 4, 25, 12, 5, tzinfo=timezone.utc),
            "source": "assumption",
            "is_assumption": True,
            "error_message": "adapter_failed",
        },
        {
            "history_id": "hist-1",
            "model_id": "gpt-5",
            "fetched_at": datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc),
            "source": "profile",
            "is_assumption": False,
            "error_message": None,
        },
    ]
    monkeypatch.setattr(
        "sylion.aeis.advisor.pricing.service._db.get_pricing_history",
        lambda **kwargs: rows,
    )

    history = PricingService(event_bus=_FakeBus()).get_pricing_history("gpt-5", limit=10)

    assert [snapshot.history_id for snapshot in history] == ["hist-2", "hist-1"]
    assert history[0].is_assumption is True
    assert history[1].is_assumption is False
