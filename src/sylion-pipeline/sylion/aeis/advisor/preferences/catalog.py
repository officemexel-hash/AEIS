"""Catalog helpers for advisor preferences."""

from __future__ import annotations

from sylion.aeis.advisor.preferences import _db
from sylion.aeis.advisor.preferences._models import CatalogEntry, PreferenceKeyMetadata


def list_catalog(catalog_type: str, include_custom: bool = True) -> list[CatalogEntry]:
    """Return one catalog as dataclasses."""
    return [
        CatalogEntry(
            entry_id=str(row["entry_id"]),
            display_name=str(row["display_name"]),
            description=row.get("description"),  # type: ignore[arg-type]
            is_system=bool(row["is_system"]),
            is_immutable=bool(row["is_immutable"]),
            metadata=row.get("metadata") or {},  # type: ignore[arg-type]
        )
        for row in _db.get_catalog_entries(catalog_type, include_custom=include_custom)
    ]


def add_custom_entry(
    *,
    catalog_type: str,
    entry_id: str,
    display_name: str,
    description: str,
    created_by: str,
) -> CatalogEntry | None:
    """Create one custom catalog row if valid."""
    success = _db.add_custom_catalog_entry(
        catalog_type=catalog_type,
        entry_id=entry_id,
        display_name=display_name,
        description=description,
        created_by=created_by,
    )
    if not success:
        return None
    for item in list_catalog(catalog_type, include_custom=True):
        if item.entry_id == entry_id:
            return item
    return None


def get_preference_key_metadata(preference_key: str) -> PreferenceKeyMetadata | None:
    """Return metadata for a preference key."""
    row = _db.get_preference_key_meta(preference_key)
    if row is None:
        return None
    return PreferenceKeyMetadata(
        key=str(row["preference_key"]),
        display_name=str(row["display_name"]),
        description=row.get("description"),  # type: ignore[arg-type]
        value_schema=row.get("value_schema") or {},  # type: ignore[arg-type]
        default_value=row.get("default_value"),
        is_hard_change=bool(row["is_hard_change"]),
    )
