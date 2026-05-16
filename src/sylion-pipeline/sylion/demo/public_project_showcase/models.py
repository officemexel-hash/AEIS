"""Domain models for Public Project Showcase Portal."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class ViewerRole(str, Enum):
    PUBLIC = "public"           # anonymous visitor (read-only)
    AUTHENTICATED = "authenticated"  # logged-in (can comment)
    OWNER = "owner"             # project owner (can edit own)
    ADMIN = "admin"             # full access


PROJECT_VISIBILITY = ("public", "unlisted", "private")
SUBMISSION_STATUS = ("pending", "approved", "rejected", "spam")


@dataclass
class PublicProject:
    project_id: str = field(
        default_factory=lambda: f"pubproj_{uuid.uuid4().hex[:12]}"
    )
    owner_id: str = ""
    slug: str = ""               # URL-friendly identifier
    title: str = ""
    description: str = ""
    visibility: str = "public"
    metrics: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    view_count: int = 0

    def __post_init__(self) -> None:
        if not self.owner_id:
            raise ValueError("owner_id required")
        if not self.slug or not self.slug.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "slug must be non-empty alphanumeric with - or _"
            )
        if self.visibility not in PROJECT_VISIBILITY:
            raise ValueError(f"invalid visibility: {self.visibility}")
        if not self.title or len(self.title) > 200:
            raise ValueError("title required, max 200 chars")


@dataclass
class ProjectComment:
    comment_id: str = field(
        default_factory=lambda: f"cmnt_{uuid.uuid4().hex[:12]}"
    )
    project_id: str = ""
    author_id: str = ""
    body: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError("project_id required")
        if not self.author_id:
            raise ValueError("author_id required")
        if not self.body or len(self.body) > 2000:
            raise ValueError("body required, max 2000 chars")


@dataclass
class Submission:
    """Contact form submission (rate-limited)."""
    submission_id: str = field(
        default_factory=lambda: f"sub_{uuid.uuid4().hex[:12]}"
    )
    project_id: str | None = None
    submitter_email: str = ""
    body: str = ""
    status: str = "pending"
    submitter_ip: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if "@" not in self.submitter_email or len(self.submitter_email) > 200:
            raise ValueError("valid submitter_email required")
        if not self.body or len(self.body) > 5000:
            raise ValueError("body required, max 5000 chars")
        if self.status not in SUBMISSION_STATUS:
            raise ValueError(f"invalid status: {self.status}")


__all__ = [
    "PublicProject", "ProjectComment", "Submission", "ViewerRole",
    "PROJECT_VISIBILITY", "SUBMISSION_STATUS",
]
