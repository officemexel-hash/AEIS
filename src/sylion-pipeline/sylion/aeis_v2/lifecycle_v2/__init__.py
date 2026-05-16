"""SYLION AEIS v2 — IdeaLifecycle 11-state machine.

Sprint 3 deliverable per ADR-001 idea-lifecycle reference (canonical
11 states from MEMORY.md ``project_idea_lifecycle.md``).

States::

    draft            — operator drafted, not yet submitted
    submitted        — submitted to Council Hybrid review
    under_review     — Council Hybrid evaluating
    approved         — Council voted approve, ready for execution
    rejected         — Council voted reject; reversible to under_review
    in_progress      — execution started (W16 apps builder, etc.)
    blocked          — execution paused on dependency / resource
    completed        — execution finished
    archived         — operator-marked closed; soft-deletable
    soft_deleted     — flagged for deletion; reversible within grace window
    hard_deleted     — physically gone (terminal state)

Per Kimi review k3_idea_lifecycle_review (round 53:30):

* The 121-cell transition matrix is sparse — only ~26 valid transitions.
* Backward edges are deliberate (rejected → under_review for reopened
  ideas; soft_deleted → archived for accidental-erasure reversal) but
  hard_deleted is terminal.
* State names are deliberately distinct from
  :class:`W18.SessionLifecycle` ({active, suspended, replay_source,
  archived}) to avoid namespace collisions; only ``archived`` overlaps,
  which is fine — it's a category-level concept.
* Audit emission is mandatory on every transition via
  ``append_to_chain`` so the DPO has a tamper-evident trail of every
  state change for every idea (essential for GDPR Article 30 records
  of processing).

Public API:

    IdeaLifecycle.transition(idea_id, from_s, to_s, actor)
        -> bool  # True on valid+audited; False on invalid

    IdeaLifecycle.is_valid_transition(from_s, to_s) -> bool
    IdeaLifecycle.is_terminal(state) -> bool
    IdeaLifecycle.history(idea_id) -> list[dict]  # walks the chain
"""

from sylion.aeis_v2.lifecycle_v2.idea_lifecycle import (
    IDEA_LIFECYCLE_AUDIT_PATH,
    IDEA_LIFECYCLE_STATES,
    IDEA_LIFECYCLE_TRANSITIONS,
    IdeaLifecycle,
    LIFECYCLE_PG_VIEW_DDL,
    LifecycleEvent,
    is_terminal,
    is_valid_transition,
)
from sylion.aeis_v2.lifecycle_v2.session_lifecycle import (
    SESSION_LIFECYCLE_AUDIT_PATH,
    SESSION_LIFECYCLE_STATES,
    SESSION_LIFECYCLE_TRANSITIONS,
    SessionLifecycle,
    SessionLifecycleEvent,
    session_is_terminal,
    session_is_valid_transition,
)

__all__ = [
    "IDEA_LIFECYCLE_AUDIT_PATH",
    "IDEA_LIFECYCLE_STATES",
    "IDEA_LIFECYCLE_TRANSITIONS",
    "IdeaLifecycle",
    "LIFECYCLE_PG_VIEW_DDL",
    "LifecycleEvent",
    "SESSION_LIFECYCLE_AUDIT_PATH",
    "SESSION_LIFECYCLE_STATES",
    "SESSION_LIFECYCLE_TRANSITIONS",
    "SessionLifecycle",
    "SessionLifecycleEvent",
    "is_terminal",
    "is_valid_transition",
    "session_is_terminal",
    "session_is_valid_transition",
]
