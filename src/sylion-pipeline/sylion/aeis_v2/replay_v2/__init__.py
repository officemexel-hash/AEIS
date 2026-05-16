"""SYLION AEIS v2 — replay-as-fork PoC.

Sprint 2 day 5/6 deliverable. Replay-as-fork lets the operator (or an
automated regression suite) take a snapshot of a session at decision
point ``N`` and replay it from ``N+1`` with a different model / context
to compare outcomes.

Use cases (per ADR-002 routing matrix research):

    1. A/B test routing decisions: did Claude vs Codex pick the same
       template?
    2. Debug a failed council vote: snapshot session at the dissent
       point, replay with a different sentinel set.
    3. Regression test after model swap: replay yesterday's session
       with today's model, measure divergence_score.

The PoC stays abstract about what a "session" is — anything that can
be JSON-serialised qualifies. The replay callable owns the semantics
of "running" the session with overrides; this module owns snapshot
capture, replay orchestration, divergence_score computation and audit
JSONL emission.

Composition:

    SessionSnapshot.capture(session_dict, decision_point=N)
        -> SessionSnapshot

    ReplayFork(snapshot, replay_callable).run(model_override=...)
        -> ReplayResult (carries divergence_score)
"""

from sylion.aeis_v2.replay_v2.divergence import (
    compute_divergence_score,
    compute_weighted_divergence,
    cosine_similarity_floats,
    jaccard_set_similarity,
    levenshtein_distance,
)
try:
    from sylion.aeis_v2.replay_v2.fork import (
        ReplayFork,
        ReplayResult,
        SessionSnapshot,
    )
except ModuleNotFoundError:  # pragma: no cover
    ReplayFork = ReplayResult = SessionSnapshot = None
from sylion.aeis_v2.replay_v2.replay_storage_lru import ReplayStorageLRU

__all__ = [
    "ReplayFork",
    "ReplayResult",
    "ReplayStorageLRU",
    "SessionSnapshot",
    "compute_divergence_score",
    "compute_weighted_divergence",
    "cosine_similarity_floats",
    "jaccard_set_similarity",
    "levenshtein_distance",
]
