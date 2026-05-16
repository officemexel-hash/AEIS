"""SessionSnapshot + ReplayFork — replay-as-fork orchestrator."""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from sylion.aeis_v2.replay_v2.divergence import compute_divergence_score

log = logging.getLogger(__name__)


def _default_audit_path() -> Path:
    try:
        from sylion.aeis_v2.audit_profile import resolve_audit_chain_path

        return resolve_audit_chain_path(
            "replay_fork.jsonl",
            Path(__file__).resolve().parents[3] / "logs" / "v2",
        )
    except Exception:  # noqa: BLE001
        return (
            Path(__file__).resolve().parents[3]
            / "logs" / "v2" / "replay_fork.jsonl"
        )

#: Audit JSONL path — best-effort emission, mirrors the v2 convention.
AUDIT_LOG_PATH = (
    _default_audit_path()
)


def _stable_state_hash(state: dict[str, Any]) -> str:
    """Stable 16-char hash of an arbitrary dict — for snapshot integrity."""
    encoded = json.dumps(state, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    """Captured session state at a particular decision point.

    Snapshots are immutable; replay produces a new :class:`ReplayResult`
    rather than mutating the snapshot in place. The ``state`` dict is a
    deep copy of the input so caller mutations after capture don't
    leak into the snapshot.
    """

    snapshot_id: str
    original_session_id: str
    decision_point: int
    captured_at: float
    state: dict[str, Any]
    state_hash: str

    @classmethod
    def capture(
        cls,
        session: dict[str, Any],
        *,
        decision_point: int,
        original_session_id: str | None = None,
    ) -> "SessionSnapshot":
        """Capture a snapshot from a session dict.

        Args:
            session: arbitrary JSON-serialisable dict.
            decision_point: integer index of the rendezvous point.
            original_session_id: optional override — defaults to a fresh
                UUID if the session dict does not carry one.

        Raises:
            ValueError: if ``decision_point`` is negative.
        """
        if decision_point < 0:
            raise ValueError("decision_point must be >= 0")
        # Deep copy via json round-trip so caller mutations are isolated.
        state_copy = json.loads(json.dumps(session, default=str))
        sid = original_session_id or session.get("session_id") or str(uuid.uuid4())
        return cls(
            snapshot_id=str(uuid.uuid4()),
            original_session_id=sid,
            decision_point=decision_point,
            captured_at=time.time(),
            state=state_copy,
            state_hash=_stable_state_hash(state_copy),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "original_session_id": self.original_session_id,
            "decision_point": self.decision_point,
            "captured_at": self.captured_at,
            "state": dict(self.state),
            "state_hash": self.state_hash,
        }


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Outcome of a replay, including divergence_score vs original."""

    replay_id: str
    snapshot_id: str
    completed_at: float
    model_override: str | None
    context_override: dict[str, Any] | None
    original_decisions: list[str]
    replay_decisions: list[str]
    original_final: list[float]
    replay_final: list[float]
    divergence_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "replay_id": self.replay_id,
            "snapshot_id": self.snapshot_id,
            "completed_at": self.completed_at,
            "model_override": self.model_override,
            "context_override": (
                dict(self.context_override) if self.context_override else None
            ),
            "original_decisions": list(self.original_decisions),
            "replay_decisions": list(self.replay_decisions),
            "original_final": list(self.original_final),
            "replay_final": list(self.replay_final),
            "divergence_score": self.divergence_score,
        }


#: Replay callable contract.
#:
#:   ``replay_callable(state: dict, *, model_override: str | None,
#:                     context_override: dict | None) -> tuple[list[str], list[float]]``
#:
#: Returns ``(decisions, final_state_vector)``.
ReplayCallable = Callable[
    [dict[str, Any]],
    tuple[Sequence[str], Sequence[float]],
]


class ReplayFork:
    """Orchestrator: replay a snapshotted session and score divergence.

    Every replay is recorded in :data:`AUDIT_LOG_PATH` as a single JSONL
    line so the operator can rebuild the trail without walking session
    snapshots. Audit emission is best-effort and never raises.
    """

    def __init__(
        self,
        snapshot: SessionSnapshot,
        *,
        original_decisions: Sequence[str],
        original_final: Sequence[float],
        audit_log_path: Path | str | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._original_decisions = list(original_decisions)
        self._original_final = list(original_final)
        self._audit_path = (
            Path(audit_log_path) if audit_log_path is not None else AUDIT_LOG_PATH
        )

    @property
    def snapshot(self) -> SessionSnapshot:
        return self._snapshot

    def _emit_audit(self, payload: dict[str, Any]) -> None:
        # Sprint 2 day 6 — migrated to tamper-evident chain (commit ac97e957).
        try:
            from sylion.aeis_v2.audit_chain import append_to_chain

            append_to_chain(self._audit_path, payload)
        except Exception as exc:  # noqa: BLE001
            log.warning("replay_fork: audit emit failed (%s)", exc)

    def run(
        self,
        replay_callable: Callable[..., tuple[Sequence[str], Sequence[float]]],
        *,
        model_override: str | None = None,
        context_override: dict[str, Any] | None = None,
    ) -> ReplayResult:
        """Execute the replay and compute divergence_score.

        Args:
            replay_callable: caller-supplied function that takes the
                snapshot state plus override kwargs and returns
                ``(decisions, final_vector)``. Must be deterministic
                given identical inputs (else divergence_score is noise).
            model_override / context_override: forwarded to the callable
                AND recorded in the audit row for traceability.

        Returns:
            :class:`ReplayResult` with ``divergence_score`` in ``[0, 1]``
            (computed via :func:`compute_divergence_score` with the
            canonical 0.6 cosine + 0.4 decisions weighting).
        """
        decisions, final = replay_callable(
            self._snapshot.state,
            model_override=model_override,
            context_override=context_override,
        )
        replay_decisions = list(decisions)
        replay_final = list(final)

        score = compute_divergence_score(
            self._original_decisions,
            replay_decisions,
            self._original_final,
            replay_final,
        )

        result = ReplayResult(
            replay_id=str(uuid.uuid4()),
            snapshot_id=self._snapshot.snapshot_id,
            completed_at=time.time(),
            model_override=model_override,
            context_override=context_override,
            original_decisions=self._original_decisions,
            replay_decisions=replay_decisions,
            original_final=self._original_final,
            replay_final=replay_final,
            divergence_score=score,
        )

        self._emit_audit({
            "kind": "replay_fork.run",
            "snapshot_id": self._snapshot.snapshot_id,
            "original_session_id": self._snapshot.original_session_id,
            "decision_point": self._snapshot.decision_point,
            **result.to_dict(),
        })

        log.info(
            "replay_fork: snapshot=%s replay=%s divergence=%.3f",
            self._snapshot.snapshot_id, result.replay_id, score,
        )
        return result
