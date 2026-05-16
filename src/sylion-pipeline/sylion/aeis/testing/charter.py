"""W14 CharterStore — domain wrapper around OntologyStore for TestCharter.

Adds lifecycle enforcement and convenience methods on top of the generic
OntologyStore CRUD.

Lifecycle: draft -> proposed -> {approved, rejected} -> archived

Thread-safe: ``threading.RLock`` serializes lifecycle transitions so two
parallel ``approve`` calls cannot both win the race.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

from sylion.aeis.testing.ontology.objects import TestCharter
from sylion.aeis.testing.ontology.store import OntologyStore

log = logging.getLogger("sylion.aeis.testing.charter")


VALID_STATUSES = ("draft", "proposed", "approved", "rejected", "archived")
TRANSITIONS: dict[str, set[str]] = {
    "draft": {"proposed", "rejected"},
    "proposed": {"approved", "rejected"},
    "approved": {"archived"},
    "rejected": {"archived"},
    "archived": set(),
}


class CharterStore:
    """Lifecycle-aware wrapper around OntologyStore for TestCharter."""

    def __init__(self, ontology: OntologyStore, event_bus: Any | None = None) -> None:
        self._ontology = ontology
        self._event_bus = event_bus
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, charter: TestCharter) -> TestCharter:
        """Persist a new charter (status restricted to 'draft' on creation).

        Kimi E7 attack #5: callers can no longer create a charter that
        is already 'approved' or 'archived' — they must walk the
        draft→proposed→approved gates explicitly.
        """
        if not charter.status:
            charter.status = "draft"
        if charter.status != "draft":
            raise ValueError(
                f"CharterStore.create only accepts status='draft', got "
                f"{charter.status!r}; advance via propose()/approve()/reject()"
            )
        self._ontology.create(charter)
        self._emit("aeis.testing.charter.created", {
            "charter_id": charter.charter_id,
            "project_id": charter.project_id,
            "status": charter.status,
        })
        return charter

    def propose(self, charter_id: str) -> TestCharter:
        """Move draft -> proposed."""
        return self._transition(charter_id, "proposed")

    def approve(
        self, charter_id: str, approver: str,
        hg_ticket_id: str | None = None,
        council_session_id: str | None = None,
    ) -> TestCharter:
        """proposed -> approved (atomic). Records approver + gate refs.

        Approver is mandatory; whitespace-only values are rejected so
        the audit trail can't be poisoned with blanks.
        """
        if not isinstance(approver, str) or not approver.strip():
            raise ValueError("approver is required (non-empty string)")
        with self._lock:
            # Kimi E7 attack #2: explicit "already approved" guard inside
            # the lock so two parallel callers cannot both think they're
            # the first one to win the race.
            existing = self._ontology.get(TestCharter, charter_id)
            if existing is None:
                raise ValueError(f"charter not found: {charter_id}")
            if existing.status == "approved":
                raise ValueError(
                    f"charter {charter_id} is already approved "
                    f"(at {existing.approved_at})"
                )
            charter = self._transition(charter_id, "approved")
            charter.approved_at = time.time()
            if hg_ticket_id:
                charter.hg_ticket_id = hg_ticket_id
            if council_session_id:
                charter.council_session_id = council_session_id
            self._ontology.update(charter, actor=approver)
            return charter

    def reject(self, charter_id: str, reason: str = "") -> TestCharter:
        """proposed/draft -> rejected."""
        return self._transition(charter_id, "rejected", extra={"reason": reason})

    def archive(self, charter_id: str) -> TestCharter:
        """approved/rejected -> archived (terminal)."""
        return self._transition(charter_id, "archived")

    def list_for_project(self, project_id: str) -> list[TestCharter]:
        if not isinstance(project_id, str) or not project_id.startswith("proj_"):
            raise ValueError(
                "project_id must be a non-empty string with 'proj_' prefix"
            )
        # Defensive: refuse path-traversal / control chars / SQL LIKE
        # wildcard '%' before the value reaches the store layer (Kimi E7 #6).
        # '_' is intentionally allowed because every canonical project_id
        # starts with the "proj_" prefix; the strict-format regex below
        # closes the door on any wildcard pattern beyond that.
        if any(t in project_id for t in ("/", "\\", "..", "\x00", "\n", "\r", "%")):
            raise ValueError(f"project_id contains illegal chars: {project_id!r}")
        # Strict format: proj_<alnum>+ with optional alnum/-/_ tail.
        import re as _re
        if not _re.fullmatch(r"proj_[A-Za-z0-9][A-Za-z0-9_\-]*", project_id):
            raise ValueError(
                f"project_id format invalid: {project_id!r}; "
                "expected proj_<alnum>[A-Za-z0-9_-]*"
            )
        return self._ontology.list(
            TestCharter, filters={"project_id": project_id}, limit=1000,
        )

    def get_active(self, project_id: str) -> TestCharter | None:
        """Return the most recent APPROVED charter for the project, if any."""
        candidates = [
            c for c in self.list_for_project(project_id)
            if c.status == "approved"
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.approved_at or 0)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _transition(
        self, charter_id: str, target: str,
        extra: dict | None = None,
    ) -> TestCharter:
        charter = self._ontology.get(TestCharter, charter_id)
        if charter is None:
            raise ValueError(f"charter not found: {charter_id}")
        if target not in VALID_STATUSES:
            raise ValueError(f"invalid target status: {target}")
        allowed = TRANSITIONS.get(charter.status, set())
        if target not in allowed:
            raise ValueError(
                f"invalid transition {charter.status} -> {target} "
                f"(allowed: {sorted(allowed)})"
            )
        charter.status = target
        self._ontology.update(charter)
        self._emit(f"aeis.testing.charter.{target}", {
            "charter_id": charter_id,
            **(extra or {}),
        })
        return charter

    def _emit(self, topic: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        try:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.testing.charter",
            ))
        except Exception as e:  # pragma: no cover
            log.debug("event emit failed: %s", e)


__all__ = ["CharterStore", "VALID_STATUSES", "TRANSITIONS"]
