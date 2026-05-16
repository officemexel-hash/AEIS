"""IdeaLifecycle implementation."""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sylion.aeis_v2.audit_chain import append_to_chain

log = logging.getLogger(__name__)

#: Canonical 11 states (frozenset for fast membership checks).
IDEA_LIFECYCLE_STATES: frozenset[str] = frozenset({
    "draft",
    "submitted",
    "under_review",
    "approved",
    "rejected",
    "in_progress",
    "blocked",
    "completed",
    "archived",
    "soft_deleted",
    "hard_deleted",
})

#: Sparse transition matrix. ``hard_deleted`` is terminal (no outgoing).
#: Backward edges are deliberate per the runbook in __init__.py.
IDEA_LIFECYCLE_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft":        frozenset({"submitted", "soft_deleted"}),
    "submitted":    frozenset({"under_review", "draft", "soft_deleted"}),
    "under_review": frozenset({"approved", "rejected", "submitted"}),
    "approved":     frozenset({"in_progress", "archived", "soft_deleted"}),
    "rejected":     frozenset({"under_review", "archived", "soft_deleted"}),
    "in_progress":  frozenset({"blocked", "completed", "rejected"}),
    "blocked":      frozenset({"in_progress", "rejected", "soft_deleted"}),
    "completed":    frozenset({"archived"}),
    "archived":     frozenset({"soft_deleted"}),
    "soft_deleted": frozenset({"archived", "hard_deleted"}),
    "hard_deleted": frozenset(),  # terminal
}

#: Audit JSONL — chained per ac97e957.
IDEA_LIFECYCLE_AUDIT_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "idea_lifecycle.jsonl"
)

LIFECYCLE_PG_VIEW_DDL: str = """
CREATE MATERIALIZED VIEW IF NOT EXISTS current_idea_state AS
SELECT idea_id, last_value(to_state)
FROM idea_transitions
WHERE success = true
GROUP BY idea_id;

CREATE INDEX IF NOT EXISTS current_idea_state_idea_id_idx
    ON current_idea_state (idea_id);
"""


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    """One state-transition row."""

    event_id: str
    ts: float
    idea_id: str
    from_state: str
    to_state: str
    actor: str
    success: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "ts": self.ts,
            "idea_id": self.idea_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "actor": self.actor,
            "success": self.success,
            "detail": self.detail,
        }


def is_valid_transition(from_state: str, to_state: str) -> bool:
    """Pure check — no side effects, no audit emission."""
    if from_state == to_state:
        return False  # self-loop is never valid
    allowed = IDEA_LIFECYCLE_TRANSITIONS.get(from_state)
    if allowed is None:
        return False
    return to_state in allowed


def is_terminal(state: str) -> bool:
    """``True`` if no transitions out of ``state`` are valid."""
    return not IDEA_LIFECYCLE_TRANSITIONS.get(state)


class IdeaLifecycle:
    """Stateless dispatcher around the transition matrix.

    Stateless because the durable state lives in the audit chain — a
    fresh call walks history(idea_id) to determine the current state.
    Production deployments will materialise into a Postgres view; this
    module focuses on the canonical contract.
    """

    def __init__(self, audit_log_path: Path | str | None = None) -> None:
        self._audit_log_path = (
            Path(audit_log_path) if audit_log_path is not None
            else IDEA_LIFECYCLE_AUDIT_PATH
        )
        self._lock = threading.RLock()

    @property
    def audit_log_path(self) -> Path:
        return self._audit_log_path

    def _emit_audit(self, event: LifecycleEvent) -> None:
        try:
            append_to_chain(
                self._audit_log_path,
                {"kind": "idea_lifecycle.transition", **event.to_dict()},
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("idea_lifecycle: audit emit failed (%s)", exc)

    def transition(
        self,
        idea_id: str,
        from_state: str,
        to_state: str,
        *,
        actor: str = "anonymous",
        detail: str = "",
    ) -> bool:
        """Validate + audit a state transition.

        Returns ``True`` on success, ``False`` on invalid transition
        (which is also recorded as a rejected event so the audit trail
        captures attempted bad transitions — useful forensic signal).
        """
        valid = is_valid_transition(from_state, to_state)
        with self._lock:
            event = LifecycleEvent(
                event_id=str(uuid.uuid4()),
                ts=time.time(),
                idea_id=idea_id,
                from_state=from_state,
                to_state=to_state,
                actor=actor,
                success=valid,
                detail=detail or (
                    "" if valid
                    else f"invalid transition {from_state}->{to_state}"
                ),
            )
            self._emit_audit(event)
        log.info(
            "idea_lifecycle: idea=%s %s->%s actor=%s success=%s",
            idea_id, from_state, to_state, actor, valid,
        )
        return valid

    def history(self, idea_id: str) -> list[dict[str, Any]]:
        """Walk the audit chain; return every successful event for ``idea_id``.

        Returns an empty list if the chain doesn't exist yet.
        """
        path = self._audit_log_path
        if not path.exists():
            return []
        out: list[dict[str, Any]] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        d = json.loads(stripped)
                    except json.JSONDecodeError:
                        continue
                    content = d.get("content")
                    if not isinstance(content, dict):
                        continue
                    if content.get("kind") != "idea_lifecycle.transition":
                        continue
                    if content.get("idea_id") != idea_id:
                        continue
                    if not content.get("success"):
                        continue
                    out.append(content)
        except OSError as exc:
            log.warning("idea_lifecycle: history read failed (%s)", exc)
        return out

    def current_state(self, idea_id: str, *, default: str = "draft") -> str:
        """Latest successful state for an idea, or ``default`` if none."""
        events = self.history(idea_id)
        if not events:
            return default
        # Successful events are ordered chronologically in the chain;
        # the last one's to_state is the current state.
        return str(events[-1]["to_state"])


__all__ = [
    "IDEA_LIFECYCLE_AUDIT_PATH",
    "IDEA_LIFECYCLE_STATES",
    "IDEA_LIFECYCLE_TRANSITIONS",
    "IdeaLifecycle",
    "LIFECYCLE_PG_VIEW_DDL",
    "LifecycleEvent",
    "is_terminal",
    "is_valid_transition",
]
