"""Operator CRM — D4 demo (PII + GDPR).

W14 protections:
  - GDPR delete vs audit retention conflict (D4)
  - Contact merge with conflict detection (D3)
  - Role escalation requires approval workflow (D4)
"""
from sylion.demo.operator_crm.models import (
    AuditEntry, Contact, ContactRole, ProjectLink,
)
from sylion.demo.operator_crm.service import CrmService
from sylion.demo.operator_crm.store import CrmStore

__all__ = [
    "AuditEntry", "Contact", "ContactRole", "ProjectLink",
    "CrmService", "CrmStore",
]
