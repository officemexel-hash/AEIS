"""Public Project Showcase — service + adversarial tests."""
from __future__ import annotations

import pytest

from sylion.demo.public_project_showcase import (
    PortalService, PortalStore, ProjectComment, PublicProject,
    Submission, ViewerRole,
)
from sylion.demo.public_project_showcase.service import (
    MAX_SUBMISSIONS_PER_MINUTE,
)


@pytest.fixture
def store():
    return PortalStore()


@pytest.fixture
def svc(store):
    return PortalService(store=store)


# -------- Models --------

def test_project_requires_owner():
    with pytest.raises(ValueError, match="owner_id"):
        PublicProject(slug="x", title="X")


def test_project_requires_alphanumeric_slug():
    with pytest.raises(ValueError, match="slug"):
        PublicProject(owner_id="op", slug="bad slug!", title="X")


def test_project_visibility_validated():
    with pytest.raises(ValueError, match="visibility"):
        PublicProject(owner_id="op", slug="ok", title="X",
                      visibility="invalid")


def test_comment_requires_body():
    with pytest.raises(ValueError, match="body"):
        ProjectComment(project_id="p", author_id="a", body="")


def test_submission_requires_email():
    with pytest.raises(ValueError, match="email"):
        Submission(submitter_email="not-an-email", body="hi")


# -------- Service: create + view --------

def test_create_and_view_public_project(svc):
    p = svc.create_project(owner_id="op_1", slug="my-proj",
                            title="My Project")
    fetched = svc.view_project(p.project_id, viewer_role="public")
    assert fetched is not None
    assert fetched.slug == "my-proj"


def test_view_private_blocks_public(svc):
    p = svc.create_project(owner_id="op_1", slug="secret",
                            title="Secret", visibility="private")
    with pytest.raises(PermissionError, match="private"):
        svc.view_project(p.project_id, viewer_role="public")


def test_view_unlisted_blocks_public(svc):
    p = svc.create_project(owner_id="op_1", slug="hidden",
                            title="Hidden", visibility="unlisted")
    with pytest.raises(PermissionError, match="unlisted"):
        svc.view_project(p.project_id, viewer_role="public")


def test_view_increments_view_count(svc, store):
    p = svc.create_project(owner_id="op_1", slug="counted", title="X")
    svc.view_project(p.project_id, viewer_role="public")
    svc.view_project(p.project_id, viewer_role="public")
    assert store.get_project(p.project_id).view_count == 2


def test_create_duplicate_slug_rejected(svc):
    svc.create_project(owner_id="op_1", slug="taken", title="A")
    with pytest.raises(ValueError, match="slug already taken"):
        svc.create_project(owner_id="op_2", slug="taken", title="B")


# -------- RBAC: edit --------

def test_public_cannot_edit(svc):
    p = svc.create_project(owner_id="op_1", slug="x", title="X")
    with pytest.raises(PermissionError, match="public"):
        svc.edit_project(p.project_id, "anon", editor_role="public",
                         title="hacked")


def test_authenticated_cannot_edit(svc):
    p = svc.create_project(owner_id="op_1", slug="y", title="Y")
    with pytest.raises(PermissionError, match="authenticated"):
        svc.edit_project(p.project_id, "viewer_x",
                         editor_role="authenticated",
                         title="hacked")


def test_owner_can_edit_own_project(svc):
    p = svc.create_project(owner_id="op_1", slug="mine", title="Mine")
    updated = svc.edit_project(p.project_id, "op_1",
                                editor_role="owner",
                                title="Mine Updated")
    assert updated.title == "Mine Updated"


def test_admin_can_edit_anyone_project(svc):
    p = svc.create_project(owner_id="op_1", slug="adminable", title="A")
    updated = svc.edit_project(p.project_id, "admin_user",
                                editor_role="admin",
                                description="moderated")
    assert updated.description == "moderated"


# -------- IDOR adversarial --------

def test_adv_idor_attempt_other_user_blocked(svc):
    p = svc.create_project(owner_id="op_1", slug="targeted", title="T")
    # op_2 tries to edit op_1's project as owner
    with pytest.raises(PermissionError, match="IDOR"):
        svc.edit_project(p.project_id, "op_2",
                         editor_role="owner",
                         title="hacked")


# -------- Comments --------

def test_public_cannot_comment(svc):
    p = svc.create_project(owner_id="op_1", slug="commentable", title="X")
    with pytest.raises(PermissionError, match="public"):
        svc.add_comment(p.project_id, "anon", "hi",
                        author_role="public")


def test_authenticated_can_comment(svc):
    p = svc.create_project(owner_id="op_1", slug="open", title="X")
    c = svc.add_comment(p.project_id, "user_1", "great work",
                        author_role="authenticated")
    assert c.comment_id.startswith("cmnt_")


def test_comment_unknown_project_rejected(svc):
    with pytest.raises(ValueError, match="not found"):
        svc.add_comment("pubproj_doesnotexist", "user_1", "hi",
                        author_role="authenticated")


# -------- Submissions: rate limit (anti-spam) --------

def test_submission_within_rate_limit_accepted(svc):
    for i in range(MAX_SUBMISSIONS_PER_MINUTE):
        svc.submit_contact_form(
            project_id=None,
            submitter_email=f"user{i}@example.com",
            body=f"msg {i}", submitter_ip="1.2.3.4",
        )


def test_adv_submission_spam_blocked_at_limit(svc):
    for i in range(MAX_SUBMISSIONS_PER_MINUTE):
        svc.submit_contact_form(
            project_id=None,
            submitter_email=f"u{i}@x.com",
            body="x", submitter_ip="9.9.9.9",
        )
    # Next submission from same IP — blocked
    with pytest.raises(PermissionError, match="rate limit"):
        svc.submit_contact_form(
            project_id=None,
            submitter_email="spammer@x.com",
            body="spam", submitter_ip="9.9.9.9",
        )


def test_submission_different_ip_allowed(svc):
    for i in range(MAX_SUBMISSIONS_PER_MINUTE):
        svc.submit_contact_form(
            project_id=None, submitter_email=f"a{i}@x.com",
            body="x", submitter_ip="1.1.1.1",
        )
    # Different IP — allowed even after limit on first IP
    svc.submit_contact_form(
        project_id=None, submitter_email="b@x.com",
        body="hi", submitter_ip="2.2.2.2",
    )


# -------- Health --------

def test_store_health(store):
    h = store.health()
    assert h["ok"] is True
    assert "portal_projects" in h["counts"]
