"""Internal models for the advisor preferences module."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ResolutionLevel(str, Enum):
    """Effective preference match strength."""

    SPECIFIC = "specific"
    TYPE_ONLY = "type_only"
    DOMAIN_ONLY = "domain_only"
    USER_DEFAULT = "user_default"
    SYSTEM_DEFAULT = "system_default"


@dataclass(frozen=True)
class PreferenceRow:
    """Explicit preference row stored in PG."""

    user_id: str
    project_type: str | None
    project_domain: str | None
    preference_key: str
    preference_value: Any
    set_by: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ResolvedPreference:
    """Effective preference result with source metadata."""

    value: Any
    resolution_level: ResolutionLevel
    source_row: PreferenceRow | None


@dataclass(frozen=True)
class CatalogEntry:
    """Catalog row for domain, type, or preference key."""

    entry_id: str
    display_name: str
    description: str | None
    is_system: bool
    is_immutable: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreferenceKeyMetadata:
    """Extra metadata stored for preference keys."""

    key: str
    display_name: str
    description: str | None
    value_schema: dict[str, Any]
    default_value: Any
    is_hard_change: bool


@dataclass(frozen=True)
class AuditRow:
    """Append-only preference audit entry."""

    audit_id: str
    user_id: str
    project_type: str | None
    project_domain: str | None
    preference_key: str
    old_value: Any
    new_value: Any
    change_type: str
    changed_by: str
    changed_at: datetime
    reason: str | None


@dataclass
class HardChangeRequest:
    """Pending hard-change request stored in memory until confirmed."""

    request_id: str
    user_id: str
    project_type: str | None
    project_domain: str | None
    preference_key: str
    proposed_value: Any
    source_card_id: str | None
    rationale: str | None
    requested_at: datetime
    expires_at: datetime
    confirmed: bool | None = None
    confirmed_at: datetime | None = None
    operator_signature: str | None = None
