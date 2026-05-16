"""Manual table pricing adapter."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from sylion.aeis.advisor.pricing.adapters.base import FetchedPricing, ProviderPricingAdapter


class ManualTableAdapter(ProviderPricingAdapter):
    """Adapter backed by operator-supplied JSON tables."""

    provider_id = "manual"
    is_local = False

    def __init__(self, provider_id: str, table_path: str | Path):
        self.provider_id = provider_id
        self._table_path = Path(table_path)

    def is_available(self) -> bool:
        return self._table_path.is_file()

    def fetch_live_pricing(self, model_id: str) -> FetchedPricing | None:
        table = self._load_table()
        pricing = table.get(model_id)
        if not pricing:
            return None
        return FetchedPricing(
            model_id=model_id,
            input_tokens_usd_per_million=_to_decimal(pricing.get("input")),
            output_tokens_usd_per_million=_to_decimal(pricing.get("output")),
            cache_hit_tokens_usd_per_million=_to_decimal(pricing.get("cache")),
            source_url=str(self._table_path),
            raw_response={"manual_table": True},
        )

    def list_models(self) -> list[dict[str, Any]]:
        return list(self._load_table().values())

    def _load_table(self) -> dict[str, dict[str, Any]]:
        if not self._table_path.is_file():
            return {}
        return json.loads(self._table_path.read_text(encoding="utf-8"))


def _to_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))
