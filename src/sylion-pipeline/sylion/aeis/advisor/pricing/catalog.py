"""Catalog helpers for advisor pricing."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

from sylion.aeis.advisor.pricing import _db
from sylion.aeis.advisor.pricing.adapters import (
    ManualTableAdapter,
    ProviderPricingAdapter,
    get_adapter,
    initialize_default_adapters,
    register_adapter,
)
from sylion.aeis.advisor.pricing._models import Model, Provider

_SEED_PATH = Path(__file__).resolve().parent / "seed_data" / "default_providers.json"


def initialize_catalog(api_keys: dict[str, str | None] | None = None) -> None:
    """Seed default providers and models into PG."""
    initialize_default_adapters(api_keys=api_keys)
    if _SEED_PATH.is_file():
        providers = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    else:
        providers = []
    for provider in providers:
        _db.upsert_provider(
            provider_id=provider["provider_id"],
            display_name=provider["display_name"],
            is_local=bool(provider["is_local"]),
            metadata_url=provider.get("metadata_url"),
        )
        adapter = get_adapter(provider["provider_id"])
        if adapter is None:
            continue
        for model_data in adapter.list_models():
            _db.upsert_model(
                model_id=str(model_data["model_id"]),
                provider_id=provider["provider_id"],
                display_name=str(model_data["display_name"]),
                context_window=_to_optional_int(model_data.get("context_window")),
                is_local=bool(provider["is_local"]),
                capabilities=[str(item) for item in model_data.get("capabilities", [])],
                is_default_judge=bool(model_data.get("is_default_judge", False)),
                is_default_local=bool(model_data.get("is_default_local", False)),
                is_deprecated=bool(model_data.get("is_deprecated", False)),
            )


def get_provider(provider_id: str) -> Provider | None:
    """Return provider metadata."""
    row = _db.get_provider(provider_id)
    if row is None:
        return None
    return Provider(**row)


def list_providers(active_only: bool = True, blocked_providers: set[str] | None = None) -> list[Provider]:
    """List providers, excluding blocked ones."""
    blocked_providers = blocked_providers or set()
    rows = _db.list_providers(active_only=active_only)
    return [Provider(**row) for row in rows if row["provider_id"] not in blocked_providers]


def get_model(model_id: str) -> Model | None:
    """Return model metadata."""
    row = _db.get_model(model_id)
    if row is None:
        return None
    return Model(**row)


def list_models(
    provider_id: str | None = None,
    include_deprecated: bool = False,
    blocked_providers: set[str] | None = None,
) -> list[Model]:
    """List models, excluding blocked providers."""
    blocked_providers = blocked_providers or set()
    rows = _db.list_models(provider_id=provider_id, include_deprecated=include_deprecated)
    models = [Model(**row) for row in rows]
    return [model for model in models if model.provider_id not in blocked_providers]


def register_dynamic_adapter(
    provider_id: str,
    display_name: str,
    is_local: bool,
    metadata_url: str,
    adapter_class_path: str,
) -> tuple[bool, str]:
    """Register an adapter from an import path."""
    try:
        module_name, _, class_name = adapter_class_path.rpartition(".")
        if not module_name:
            return False, "adapter_class_path must include module and class"
        module = import_module(module_name)
        adapter_cls = getattr(module, class_name)
        adapter = adapter_cls()  # type: ignore[misc]
        if not isinstance(adapter, ProviderPricingAdapter):
            return False, "adapter_class_path did not resolve to ProviderPricingAdapter"
        register_adapter(provider_id, adapter)
        _db.upsert_provider(provider_id, display_name, is_local, metadata_url or None)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def register_manual_table(
    provider_id: str,
    display_name: str,
    metadata_url: str,
    table_path: str,
) -> tuple[bool, str]:
    """Register a manual-table adapter."""
    adapter = ManualTableAdapter(provider_id=provider_id, table_path=table_path)
    register_adapter(provider_id, adapter)
    _db.upsert_provider(provider_id, display_name, False, metadata_url or None)
    return True, ""


def _to_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)
