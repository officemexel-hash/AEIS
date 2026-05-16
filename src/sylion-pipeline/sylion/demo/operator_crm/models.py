"""CRM domain models — PII-aware."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class ContactRole(str, Enum):
    LEAD = "lead"
    CUSTOMER = "customer"
    PARTNER = "partner"
    VIP = "vip"


CONTACT_STATUS = ("active", "deleted_gdpr", "merged", "archived")


@dataclass
class Contact:
    contact_id: str = field(default_factory=lambda: f"con_{uuid.uuid4().hex[:12]}")
    full_name: str = ""
    email: str = ""
    phone: str = ""           # PII — must be redacted in audit logs
    role: str = "lead"
    status: str = "active"
    notes: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    deleted_at: float | None = None
    merged_into: str | None = None  # contact_id of survivor

    def __post_init__(self) -> None:
        if not self.full_name:
            raise ValueError("full_name required")
        if "@" not in self.email or len(self.email) > 200:
            raise ValueError("valid email required")
        if self.role not in ContactRole._value2member_map_:
            raise ValueError(f"invalid role: {self.role}")
        if self.status not in CONTACT_STATUS:
            raise ValueError(f"invalid status: {self.status}")
        if self.status == "merged" and not self.merged_into:
            raise ValueError("merged status requires merged_into pointer")


@dataclass
class ProjectLink:
    """Link contact to AEIS project."""
    link_id: str = field(default_factory=lambda: f"plink_{uuid.uuid4().hex[:12]}")
    contact_id: str = ""
    aeis_project_id: str = ""
    relationship: str = "owner"  # owner, decision_maker, technical, billing
    created_at: float = field(default_factory=time.time)


@dataclass
class AuditEntry:
    """Append-only audit log. PII redacted at write."""
    entry_id: str = field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:12]}")
    actor_id: str = ""
    action: str = ""
    target_id: str = ""        # contact_id, link_id, etc
    target_type: str = "contact"
    payload_redacted: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.actor_id:
            raise ValueError("actor_id required (no anonymous audit)")
        if not self.action:
            raise ValueError("action required")


__all__ = [
    "Contact", "ContactRole", "ProjectLink", "AuditEntry",
    "CONTACT_STATUS",
]
