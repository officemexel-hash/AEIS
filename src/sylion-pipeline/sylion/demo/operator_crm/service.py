"""CrmService — GDPR + merge conflict + role escalation guards."""
from __future__ import annotations

import logging
import time
from typing import Any

from sylion.demo.operator_crm.models import (
    AuditEntry, Contact, ContactRole, ProjectLink,
)
from sylion.demo.operator_crm.store import CrmStore

log = logging.getLogger("sylion.demo.operator_crm.service")


# Role escalation requires HG approval (D4) — admin role specifically guarded
PRIVILEGED_ROLES = (ContactRole.VIP.value,)


class CrmService:
    def __init__(self, store: CrmStore, event_bus: Any = None) -> None:
        self._store = store
        self._event_bus = event_bus

    def _audit(
        self, actor_id: str, action: str, target_id: str,
        target_type: str = "contact", payload: dict | None = None,
    ) -> None:
        # PII redaction in audit (no full email, no phone)
        redacted = {}
        if payload:
            for k, v in payload.items():
                if k in ("email", "phone", "full_name"):
                    redacted[k] = "[REDACTED]"
                else:
                    redacted[k] = v
        entry = AuditEntry(
            actor_id=actor_id, action=action,
            target_id=target_id, target_type=target_type,
            payload_redacted=redacted,
        )
        self._store.append_audit(entry)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_contact(
        self, actor_id: str, full_name: str, email: str,
        phone: str = "", role: str = "lead",
    ) -> Contact:
        # Duplicate email check
        existing = self._store.find_by_email(email)
        if existing is not None:
            raise ValueError(
                f"contact with email already exists: {existing.contact_id}"
            )
        c = Contact(full_name=full_name, email=email, phone=phone, role=role)
        self._store.create_contact(c)
        self._audit(actor_id, "create_contact", c.contact_id,
                    payload={"email": email, "phone": phone,
                             "full_name": full_name, "role": role})
        return c

    # ------------------------------------------------------------------
    # GDPR (D4)
    # ------------------------------------------------------------------

    def gdpr_delete(
        self, actor_id: str, contact_id: str,
        hg_ticket_id: str,
    ) -> None:
        """GDPR delete: PII redacted, record kept for audit retention.

        Requires HG ticket (D4 governance gate).
        """
        if not hg_ticket_id:
            raise PermissionError(
                "GDPR delete REQUIRES hg_ticket_id (D4 governance)"
            )
        c = self._store.get_contact(contact_id)
        if c is None:
            raise ValueError(f"contact not found: {contact_id}")
        if c.status == "deleted_gdpr":
            return  # idempotent
        self._store.soft_delete_gdpr(contact_id)
        self._audit(
            actor_id, "gdpr_delete", contact_id,
            payload={"hg_ticket_id": hg_ticket_id,
                     "previous_email": "[REDACTED]"},
        )

    # ------------------------------------------------------------------
    # Merge with conflict detection (D3)
    # ------------------------------------------------------------------

    def merge_contacts(
        self, actor_id: str, survivor_id: str,
        merged_id: str, conflict_resolution: dict | None = None,
    ) -> Contact:
        """Merge two contacts. Detects conflicts (different emails, etc.)."""
        if survivor_id == merged_id:
            raise ValueError("cannot merge contact with itself")
        survivor = self._store.get_contact(survivor_id)
        merged = self._store.get_contact(merged_id)
        if survivor is None or merged is None:
            raise ValueError("both contacts must exist")
        if survivor.status != "active" or merged.status != "active":
            raise ValueError("can only merge active contacts")

        # Detect conflicts
        conflicts: list[str] = []
        if survivor.email != merged.email:
            conflicts.append(f"email: '{survivor.email}' vs '{merged.email}'")
        if survivor.phone != merged.phone and survivor.phone and merged.phone:
            conflicts.append("phone: differ")
        if survivor.role != merged.role:
            conflicts.append(f"role: '{survivor.role}' vs '{merged.role}'")

        if conflicts and not conflict_resolution:
            raise ValueError(
                f"MERGE CONFLICT requires conflict_resolution dict: {conflicts}"
            )

        # Migrate project links from merged -> survivor
        for link in self._store.list_links(merged_id):
            new_link = ProjectLink(
                contact_id=survivor_id,
                aeis_project_id=link.aeis_project_id,
                relationship=link.relationship,
            )
            self._store.add_link(new_link)

        # Mark merged
        self._store.mark_merged(merged_id, survivor_id)
        self._audit(
            actor_id, "merge_contacts", survivor_id,
            payload={"merged_id": merged_id,
                     "conflicts": conflicts,
                     "resolution": conflict_resolution or {}},
        )
        return self._store.get_contact(survivor_id)

    # ------------------------------------------------------------------
    # Role escalation (D4)
    # ------------------------------------------------------------------

    def change_role(
        self, actor_id: str, contact_id: str, new_role: str,
        actor_role: str = "operator",
        hg_ticket_id: str | None = None,
    ) -> Contact:
        """Change contact role.

        Promotion to VIP requires admin actor + HG ticket (D4).
        """
        if new_role not in ContactRole._value2member_map_:
            raise ValueError(f"invalid role: {new_role}")
        c = self._store.get_contact(contact_id)
        if c is None:
            raise ValueError(f"contact not found: {contact_id}")

        # Privileged role escalation requires admin + HG
        if new_role in PRIVILEGED_ROLES:
            if actor_role != "admin":
                raise PermissionError(
                    f"escalation to {new_role} requires admin actor "
                    f"(actor_role={actor_role})"
                )
            if not hg_ticket_id:
                raise PermissionError(
                    f"escalation to {new_role} requires hg_ticket_id (D4)"
                )

        # Update role (using direct SQL — no full update API needed for demo)
        with self._store._lock:
            self._store._conn.execute(
                "UPDATE crm_contacts SET role = ?, updated_at = ? "
                "WHERE contact_id = ?",
                (new_role, time.time(), contact_id),
            )
            self._store._conn.commit()
        self._audit(
            actor_id, "change_role", contact_id,
            payload={"from": c.role, "to": new_role,
                     "hg_ticket_id": hg_ticket_id},
        )
        return self._store.get_contact(contact_id)


__all__ = ["CrmService", "PRIVILEGED_ROLES"]
