"""CRM service + GDPR + merge + role escalation tests."""
from __future__ import annotations

import pytest

from sylion.demo.operator_crm import (
    Contact, ContactRole, CrmService, CrmStore, ProjectLink,
)


@pytest.fixture
def store():
    return CrmStore()


@pytest.fixture
def svc(store):
    return CrmService(store=store)


# -------- Models --------

def test_contact_email_validated():
    with pytest.raises(ValueError, match="email"):
        Contact(full_name="X", email="not-an-email")


def test_contact_role_validated():
    with pytest.raises(ValueError, match="role"):
        Contact(full_name="X", email="x@x.com", role="hacker")


def test_contact_merged_status_requires_pointer():
    with pytest.raises(ValueError, match="merged_into"):
        Contact(full_name="X", email="x@x.com", status="merged")


# -------- Create + duplicate guard --------

def test_create_contact_persists(svc, store):
    c = svc.create_contact("op_1", "Anna K.", "anna@x.com", phone="+48 123")
    assert store.get_contact(c.contact_id) is not None


def test_create_duplicate_email_rejected(svc):
    svc.create_contact("op_1", "Anna", "anna@x.com")
    with pytest.raises(ValueError, match="already exists"):
        svc.create_contact("op_2", "Other", "anna@x.com")


def test_create_writes_audit_with_pii_redacted(svc, store):
    c = svc.create_contact("op_1", "Anna", "anna@x.com", phone="+48 123")
    audit = store.list_audit_for_target(c.contact_id)
    assert len(audit) == 1
    assert audit[0].action == "create_contact"
    # PII redacted
    assert audit[0].payload_redacted["email"] == "[REDACTED]"
    assert audit[0].payload_redacted["phone"] == "[REDACTED]"
    assert audit[0].payload_redacted["full_name"] == "[REDACTED]"


# -------- GDPR delete (D4) --------

def test_gdpr_delete_redacts_pii(svc, store):
    c = svc.create_contact("op_1", "Bob", "bob@x.com", phone="+48 999")
    svc.gdpr_delete("op_admin", c.contact_id, hg_ticket_id="hg_gdpr_001")
    fetched = store.get_contact(c.contact_id)
    assert fetched.status == "deleted_gdpr"
    assert fetched.full_name == "[GDPR_REDACTED]"
    assert "@gdpr.local" in fetched.email
    assert fetched.phone == ""


def test_gdpr_delete_preserves_audit(svc, store):
    """GDPR delete must NOT erase audit log (retention rule)."""
    c = svc.create_contact("op_1", "Bob", "bob@x.com")
    svc.gdpr_delete("op_admin", c.contact_id, hg_ticket_id="hg_001")
    audit = store.list_audit_for_target(c.contact_id)
    # Audit still present (create + delete)
    assert len(audit) == 2


def test_adv_gdpr_delete_without_hg_blocked(svc):
    c = svc.create_contact("op_1", "X", "x@x.com")
    with pytest.raises(PermissionError, match="hg_ticket_id"):
        svc.gdpr_delete("op_1", c.contact_id, hg_ticket_id="")


def test_gdpr_delete_idempotent(svc, store):
    c = svc.create_contact("op_1", "X", "x@x.com")
    svc.gdpr_delete("op_admin", c.contact_id, hg_ticket_id="hg_1")
    svc.gdpr_delete("op_admin", c.contact_id, hg_ticket_id="hg_2")  # no-op
    assert store.get_contact(c.contact_id).status == "deleted_gdpr"


# -------- Merge with conflict detection --------

def test_merge_no_conflicts_succeeds(svc, store):
    c1 = svc.create_contact("op_1", "John D", "john@x.com", role="customer")
    c2 = svc.create_contact("op_2", "John D", "john@y.com", role="customer")
    # Both customer, only different email -> conflict
    with pytest.raises(ValueError, match="MERGE CONFLICT"):
        svc.merge_contacts("op_admin", c1.contact_id, c2.contact_id)


def test_merge_with_resolution_succeeds(svc, store):
    c1 = svc.create_contact("op_1", "John D", "john@x.com", role="customer")
    c2 = svc.create_contact("op_2", "John D", "john@y.com", role="lead")
    survivor = svc.merge_contacts(
        "op_admin", c1.contact_id, c2.contact_id,
        conflict_resolution={"prefer_email_from": c1.contact_id,
                             "prefer_role_from": c1.contact_id},
    )
    assert survivor.contact_id == c1.contact_id
    # c2 marked merged
    merged = store.get_contact(c2.contact_id)
    assert merged.status == "merged"
    assert merged.merged_into == c1.contact_id


def test_merge_migrates_project_links(svc, store):
    c1 = svc.create_contact("op_1", "X", "x1@x.com")
    c2 = svc.create_contact("op_1", "X", "x2@x.com")
    store.add_link(ProjectLink(
        contact_id=c2.contact_id, aeis_project_id="proj_z",
        relationship="owner",
    ))
    svc.merge_contacts(
        "op_admin", c1.contact_id, c2.contact_id,
        conflict_resolution={"prefer_email_from": c1.contact_id},
    )
    assert len(store.list_links(c1.contact_id)) == 1


def test_merge_self_rejected(svc):
    c = svc.create_contact("op_1", "X", "x@x.com")
    with pytest.raises(ValueError, match="itself"):
        svc.merge_contacts("op_admin", c.contact_id, c.contact_id)


def test_merge_unknown_contact_rejected(svc):
    c = svc.create_contact("op_1", "X", "x@x.com")
    with pytest.raises(ValueError, match="must exist"):
        svc.merge_contacts("op_admin", c.contact_id, "con_unknown")


# -------- Role escalation (D4) --------

def test_change_role_to_customer_no_special_auth(svc):
    c = svc.create_contact("op_1", "X", "x@x.com", role="lead")
    updated = svc.change_role(
        "op_1", c.contact_id, "customer",
        actor_role="operator",
    )
    assert updated.role == "customer"


def test_adv_promote_to_vip_requires_admin(svc):
    c = svc.create_contact("op_1", "X", "x@x.com", role="customer")
    with pytest.raises(PermissionError, match="admin"):
        svc.change_role(
            "op_1", c.contact_id, "vip",
            actor_role="operator", hg_ticket_id="hg_1",
        )


def test_adv_promote_to_vip_requires_hg(svc):
    c = svc.create_contact("op_1", "X", "x@x.com", role="customer")
    with pytest.raises(PermissionError, match="hg_ticket_id"):
        svc.change_role(
            "op_admin", c.contact_id, "vip",
            actor_role="admin", hg_ticket_id=None,
        )


def test_promote_to_vip_with_admin_and_hg_succeeds(svc):
    c = svc.create_contact("op_1", "X", "x@x.com", role="customer")
    updated = svc.change_role(
        "op_admin", c.contact_id, "vip",
        actor_role="admin", hg_ticket_id="hg_d4_promote_001",
    )
    assert updated.role == "vip"


# -------- Health --------

def test_store_health(store):
    h = store.health()
    assert h["ok"] is True
