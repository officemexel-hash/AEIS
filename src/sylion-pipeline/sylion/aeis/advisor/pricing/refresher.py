"""Pricing refresh orchestration."""

from __future__ import annotations

import logging
from typing import Any

from sylion.aeis.advisor.pricing import _db
from sylion.aeis.advisor.pricing.adapters import get_adapter, initialize_default_adapters
from sylion.aeis.advisor.pricing.catalog import initialize_catalog

log = logging.getLogger("sylion.aeis.advisor.pricing.refresher")


def refresh_provider_pricing(provider_id: str, force: bool = False) -> dict[str, Any]:
    """Refresh pricing for all models of a provider."""
    _ = force
    adapter = get_adapter(provider_id)
    if adapter is None:
        return {
            "provider_id": provider_id,
            "refreshed_count": 0,
            "failed_count": 0,
            "used_live": False,
            "assumption_fallback": True,
            "events": ["provider_unavailable"],
        }

    events: list[str] = []
    if not adapter.is_available():
        for model in adapter.list_models():
            _db.insert_pricing_history(
                model_id=str(model["model_id"]),
                source="assumption",
                raw_response=None,
                resolved_pricing_id=None,
                is_assumption=True,
                error="adapter_not_available",
            )
        return {
            "provider_id": provider_id,
            "refreshed_count": 0,
            "failed_count": 0,
            "used_live": False,
            "assumption_fallback": True,
            "events": ["provider_unavailable", "assumption_used"],
        }

    refreshed_count = 0
    failed_count = 0
    for model in adapter.list_models():
        model_id = str(model["model_id"])
        try:
            fetched = adapter.fetch_live_pricing(model_id)
            if fetched is None:
                _db.insert_pricing_history(
                    model_id=model_id,
                    source="assumption",
                    raw_response=None,
                    resolved_pricing_id=None,
                    is_assumption=True,
                    error="no_data_from_adapter",
                )
                failed_count += 1
                _append_event(events, "assumption_used")
                continue

            source = "measured" if adapter.is_local else "profile"
            assumption_note = None
            if fetched.input_tokens_usd_per_million is None and fetched.output_tokens_usd_per_million is None:
                source = "assumption"
                assumption_note = "Adapter returned no billable pricing details"
            pricing_id = _db.insert_pricing_table(
                model_id=model_id,
                input_per_million=fetched.input_tokens_usd_per_million,
                output_per_million=fetched.output_tokens_usd_per_million,
                cache_per_million=fetched.cache_hit_tokens_usd_per_million,
                source=source,
                source_url=fetched.source_url,
                is_assumption=source == "assumption",
                assumption_note=assumption_note,
            )
            _db.insert_pricing_history(
                model_id=model_id,
                source=source,
                raw_response=fetched.raw_response,
                resolved_pricing_id=pricing_id,
                is_assumption=source == "assumption",
                error=None,
            )
            refreshed_count += 1
            _append_event(events, "live_metadata_fetched" if source == "measured" else "profile_updated")
        except Exception as exc:
            log.exception("pricing refresh failed for %s/%s", provider_id, model_id)
            _db.insert_pricing_history(
                model_id=model_id,
                source="assumption",
                raw_response=None,
                resolved_pricing_id=None,
                is_assumption=True,
                error=str(exc),
            )
            failed_count += 1
            _append_event(events, "adapter_failed")
            _append_event(events, "assumption_used")

    _append_event(events, "refreshed")
    return {
        "provider_id": provider_id,
        "refreshed_count": refreshed_count,
        "failed_count": failed_count,
        "used_live": any(event == "live_metadata_fetched" for event in events),
        "assumption_fallback": failed_count > 0 and refreshed_count == 0,
        "events": events,
    }


def initialize_pricing_catalog(api_keys: dict[str, str | None] | None = None) -> None:
    """Seed providers and models."""
    initialize_default_adapters(api_keys=api_keys)
    initialize_catalog(api_keys=api_keys)


def _append_event(events: list[str], event_name: str) -> None:
    if event_name not in events:
        events.append(event_name)
