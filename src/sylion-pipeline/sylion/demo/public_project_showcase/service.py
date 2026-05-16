"""PortalService — RBAC + rate-limit + IDOR guard."""
from __future__ import annotations

import logging
import time
from typing import Any

from sylion.demo.public_project_showcase.models import (
    ProjectComment, PublicProject, Submission, ViewerRole,
)
from sylion.demo.public_project_showcase.store import PortalStore

log = logging.getLogger("sylion.demo.public_project_showcase.service")


# Rate limit: max submissions per IP per minute (anti-spam)
MAX_SUBMISSIONS_PER_MINUTE = 3


class PortalService:
    def __init__(
        self, store: PortalStore, event_bus: Any | None = None,
    ) -> None:
        self._store = store
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Projects (RBAC + IDOR)
    # ------------------------------------------------------------------

    def create_project(
        self, owner_id: str, slug: str, title: str,
        description: str = "", visibility: str = "public",
    ) -> PublicProject:
        # Slug uniqueness check
        if self._store.get_by_slug(slug) is not None:
            raise ValueError(f"slug already taken: {slug}")
        p = PublicProject(
            owner_id=owner_id, slug=slug, title=title,
            description=description, visibility=visibility,
        )
        self._store.create_project(p)
        self._emit("demo.portal.project_created",
                   {"project_id": p.project_id, "owner_id": owner_id})
        return p

    def view_project(
        self, project_id: str, viewer_role: str = "public",
    ) -> PublicProject | None:
        """Read project — RBAC enforced for non-public visibility."""
        p = self._store.get_project(project_id)
        if p is None:
            return None
        if p.visibility == "private" and viewer_role not in (
            ViewerRole.OWNER.value, ViewerRole.ADMIN.value,
        ):
            raise PermissionError(
                f"private project accessible only to owner/admin "
                f"(role={viewer_role})"
            )
        if p.visibility == "unlisted" and viewer_role == ViewerRole.PUBLIC.value:
            raise PermissionError("unlisted project requires authentication")
        # Track view
        self._store.increment_view(project_id)
        return p

    def edit_project(
        self, project_id: str, editor_id: str,
        editor_role: str = "owner", **fields: Any,
    ) -> PublicProject:
        """Edit — viewer/public/authenticated cannot edit (RBAC).

        IDOR protection: must be project owner OR admin.
        """
        if editor_role == ViewerRole.PUBLIC.value:
            raise PermissionError("public viewers cannot edit projects")
        if editor_role == ViewerRole.AUTHENTICATED.value:
            raise PermissionError(
                "authenticated viewers cannot edit (need owner role)"
            )
        # Admin bypasses ownership check
        if editor_role == ViewerRole.ADMIN.value:
            p = self._store.get_project(project_id)
            if p is None:
                raise ValueError(f"project not found: {project_id}")
            return self._store.update_project(
                project_id, expected_owner=p.owner_id, **fields,
            )
        # Owner: store enforces ownership match -> PermissionError on IDOR
        return self._store.update_project(
            project_id, expected_owner=editor_id, **fields,
        )

    # ------------------------------------------------------------------
    # Comments (auth required)
    # ------------------------------------------------------------------

    def add_comment(
        self, project_id: str, author_id: str, body: str,
        author_role: str = "authenticated",
    ) -> ProjectComment:
        if author_role == ViewerRole.PUBLIC.value:
            raise PermissionError("public viewers cannot comment")
        # Verify project exists
        if self._store.get_project(project_id) is None:
            raise ValueError(f"project not found: {project_id}")
        c = ProjectComment(
            project_id=project_id, author_id=author_id, body=body,
        )
        self._store.add_comment(c)
        return c

    # ------------------------------------------------------------------
    # Submissions (rate-limited)
    # ------------------------------------------------------------------

    def submit_contact_form(
        self, project_id: str | None, submitter_email: str,
        body: str, submitter_ip: str,
    ) -> Submission:
        """Submit contact form. Rate-limit by IP (anti-spam)."""
        since = time.time() - 60.0
        recent = self._store.count_submissions_from_ip(submitter_ip, since)
        if recent >= MAX_SUBMISSIONS_PER_MINUTE:
            raise PermissionError(
                f"rate limit exceeded: {recent} submissions from {submitter_ip} "
                f"in last 60s (max {MAX_SUBMISSIONS_PER_MINUTE})"
            )
        s = Submission(
            project_id=project_id,
            submitter_email=submitter_email,
            body=body,
            submitter_ip=submitter_ip,
        )
        self._store.add_submission(s)
        self._emit("demo.portal.contact_submitted",
                   {"submission_id": s.submission_id, "ip": submitter_ip})
        return s

    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        try:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="demo.public_project_showcase",
            ))
        except Exception as e:  # pragma: no cover
            log.debug("event emit failed: %s", e)


__all__ = ["PortalService", "MAX_SUBMISSIONS_PER_MINUTE"]
