"""W18 SessionLifecycle — 4-state machine for Operator Terminal sessions.

Sprint 3 deliverable per W18 charter §4 ("session state model"). Sits
alongside :class:`IdeaLifecycle` (commit ``aa08334c``); shares the
chained-audit + history-walking pattern but uses a smaller state set
tailored to terminal sessions.

States::

    active          — operator is interacting with the session live
    suspended       — paused (intervention UI, operator hand-off)
    replay_source   — frozen at a decision point so a ReplayFork can
                       snapshot it deterministically
    archived        — session closed; available for read-only audit

Per Kimi k3 (round 53:30): the 4 names are deliberately distinct from
the 11-state IdeaLifecycle to avoid namespace collisions; only
``archived`` overlaps, which is a category-level concept and stays
fine.

Public API mirrors IdeaLifecycle:

    SessionLifecycle.transition(session_id, from_s, to_s, actor)
        -> bool

    SessionLifecycle.is_valid_transition / is_terminal
    SessionLifecycle.history(session_id) -> list[dict]
    SessionLifecycle.current_state(session_id, default='active') -> str
"""
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

#: Canonical 4 states.
SESSION_LIFECYCLE_STATES: frozenset[str] = frozenset({
    "active", "suspended", "replay_source", "archived",
})

#: Sparse transition matrix.
SESSION_LIFECYCLE_TRANSITIONS: dict[str, frozenset[str]] = {
    "active":        frozenset({"suspended", "replay_source", "archived"}),
    "suspended":     frozenset({"active", "archived"}),
    "replay_source": frozenset({"active", "archived"}),
    "archived":      frozenset(),  # terminal
}

#: Audit JSONL path — chained per ac97e957.
SESSION_LIFECYCLE_AUDIT_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "session_lifecycle.jsonl"
)


@dataclass(frozen=True, slots=True)
class SessionLifecycleEvent:
    """One state-transition row for a terminal session."""

    event_id: str
    ts: float
    session_id: str
    from_state: str
    to_state: str
    actor: str
    success: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "ts": self.ts,
            "session_id": self.session_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "actor": self.actor,
            "success": self.success,
            "detail": self.detail,
        }


def session_is_valid_transition(from_state: str, to_state: str) -> bool:
    """Pure check, no side effects."""
    if from_state == to_state:
        return False
    allowed = SESSION_LIFECYCLE_TRANSITIONS.get(from_state)
    if allowed is None:
        return False
    return to_state in allowed


def session_is_terminal(state: str) -> bool:
    """Only ``archived`` is terminal."""
    return not SESSION_LIFECYCLE_TRANSITIONS.get(state)


class SessionLifecycle:
    """Stateless dispatcher around the 4-state matrix.

    Mirrors :class:`IdeaLifecycle`: durable state lives in the audit
    chain; ``current_state`` walks history off disk. Production
    deployments materialise into a Postgres view as needed.
    """

    def __init__(self, audit_log_path: Path | str | None = None) -> None:
        self._audit_log_path = (
            Path(audit_log_path) if audit_log_path is not None
            else SESSION_LIFECYCLE_AUDIT_PATH
        )
        self._lock = threading.RLock()

    @property
    def audit_log_path(self) -> Path:
        return self._audit_log_path

    def _emit_audit(self, event: SessionLifecycleEvent) -> None:
        try:
            append_to_chain(
                self._audit_log_path,
                {"kind": "session_lifecycle.transition", **event.to_dict()},
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("session_lifecycle: audit emit failed (%s)", exc)

    def transition(
        self,
        session_id: str,
        from_state: str,
        to_state: str,
        *,
        actor: str = "anonymous",
        detail: str = "",
    ) -> bool:
        """Validate + audit a state transition. Records invalid attempts too."""
        valid = session_is_valid_transition(from_state, to_state)
        with self._lock:
            event = SessionLifecycleEvent(
                event_id=str(uuid.uuid4()),
                ts=time.time(),
                session_id=session_id,
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
            "session_lifecycle: session=%s %s->%s actor=%s success=%s",
            session_id, from_state, to_state, actor, valid,
        )
        return valid

    def history(self, session_id: str) -> list[dict[str, Any]]:
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
                    if content.get("kind") != "session_lifecycle.transition":
                        continue
                    if content.get("session_id") != session_id:
                        continue
                    if not content.get("success"):
                        continue
                    out.append(content)
        except OSError as exc:
            log.warning("session_lifecycle: history read failed (%s)", exc)
        return out

    def current_state(
        self, session_id: str, *, default: str = "active",
    ) -> str:
        events = self.history(session_id)
        if not events:
            return default
        return str(events[-1]["to_state"])


__all__ = [
    "SESSION_LIFECYCLE_AUDIT_PATH",
    "SESSION_LIFECYCLE_STATES",
    "SESSION_LIFECYCLE_TRANSITIONS",
    "SessionLifecycle",
    "SessionLifecycleEvent",
    "session_is_terminal",
    "session_is_valid_transition",
]
