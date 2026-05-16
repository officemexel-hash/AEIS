"""Consortium pool CRUD."""

from __future__ import annotations

from typing import Any

from sylion.aeis.advisor.funding import _db
from sylion.aeis.advisor.funding._models import ConsortiumPartner


def add_partner(
    *,
    display_name: str,
    entity_type: str,
    country: str = "",
    region: str = "",
    qualifications: list[str] | None = None,
    contact_info: dict[str, Any] | None = None,
    added_by: str = "",
    notes: str = "",
) -> ConsortiumPartner:
    partner = ConsortiumPartner(
        display_name=display_name,
        entity_type=entity_type,
        country=country,
        region=region,
        qualifications=list(qualifications or []),
        contact_info=dict(contact_info or {}),
        added_by=added_by,
        notes=notes,
    )
    _db.insert_consortium_partner(partner)
    return partner


def list_partners(
    *,
    entity_type: str | None = None,
    country: str | None = None,
    region: str | None = None,
) -> list[ConsortiumPartner]:
    return _db.fetch_consortium_partners(
        entity_type=entity_type,
        country=country,
        region=region,
    )
