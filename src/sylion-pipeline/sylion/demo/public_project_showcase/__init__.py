"""Public Project Showcase — D3 web-portal demo.

Public-facing portal showing AEIS-generated case studies.
W14 protections:
  - viewer attempts edit -> RBAC block (403)
  - SEO scrape rate-limited (token bucket)
  - IDOR attack on project_id -> verify ownership
"""
from sylion.demo.public_project_showcase.models import (
    PublicProject, ProjectComment, Submission, ViewerRole,
)
from sylion.demo.public_project_showcase.service import PortalService
from sylion.demo.public_project_showcase.store import PortalStore

__all__ = [
    "PublicProject", "ProjectComment", "Submission", "ViewerRole",
    "PortalService", "PortalStore",
]
