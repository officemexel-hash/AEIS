"""W14 Auto-Repair Controller — R0..R9 lifecycle for findings.

R0 Detect       — finding registered (OPEN)
R1 Reproduce    — REPRODUCED
R2 Classify     — CLASSIFIED (severity + d_level confirmed)
R3 Localize     — REPAIR_PROPOSED branch + finding region identified
R4 Patch        — REPAIRING (PatchProposal applied to repair branch)
R5 Regression   — READY_FOR_RETEST (regression suite started)
R6 Evidence     — WAITING_FOR_HUMAN_GATE (evidence pack handed off)
R7 Human Retest — WAITING_FOR_HUMAN_GATE if D3+
R8 Learning     — record lesson + transition VERIFIED
R9 Gate         — CLOSED after merge

Loop Governor consulted at every step that creates a new attempt.
Merge Guard consulted at R8/R9 (final transitions affecting branch merge).
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from sylion.aeis.testing.loop_governor import LoopGovernor
from sylion.aeis.testing.merge_guard import MergeGuard
from sylion.aeis.testing.ontology.enums import BranchType, RStatus
from sylion.aeis.testing.ontology.objects import Branch, Finding, RepairAttempt
from sylion.aeis.testing.ontology.store import OntologyStore

log = logging.getLogger("sylion.aeis.testing.auto_repair_controller")


# Phase order matters. Forward-only transitions (no skip beyond +1)
# unless the caller is moving to a terminal state (CLOSED/ESCALATED/WAIVED)
# which is a legitimate human-gate override.
PHASES_ORDER: tuple[str, ...] = (
    RStatus.OPEN.value,
    RStatus.TRIAGED.value,
    RStatus.REPRODUCED.value,
    RStatus.CLASSIFIED.value,
    RStatus.REPAIR_PROPOSED.value,
    RStatus.REPAIRING.value,
    RStatus.READY_FOR_RETEST.value,
    RStatus.WAITING_FOR_HUMAN_GATE.value,
    RStatus.VERIFIED.value,
    RStatus.CLOSED.value,
)

TERMINAL_STATUSES: frozenset[str] = frozenset({
    RStatus.CLOSED.value,
    RStatus.ESCALATED.value,
    RStatus.WAIVED_BY_HUMAN.value,
})

# Phases that legitimately re-enter a sequence (not strict forward-only):
LOOPBACK_STATUSES: frozenset[str] = frozenset({
    RStatus.REGRESSION_FAILED.value,
})


@dataclass
class RepairSession:
    session_id: str = field(default_factory=lambda: f"ars_{uuid.uuid4().hex[:12]}")
    finding_id: str = ""
    branch_id: str = ""  # repair branch
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    last_phase: str = RStatus.OPEN.value
    attempt_count: int = 0
    blocked: bool = False
    block_reason: str | None = None
    loop_report_id: str | None = None


class AutoRepairController:
    """Orchestrates R0..R9 transitions for a Finding via repair branches."""

    def __init__(
        self,
        ontology: OntologyStore,
        loop_governor: LoopGovernor | None = None,
        merge_guard: MergeGuard | None = None,
        event_bus: Any | None = None,
        repair_project_id: str = "proj_repair",
    ) -> None:
        self._ontology = ontology
        self._loop = loop_governor or LoopGovernor(ontology, event_bus=event_bus)
        self._guard = merge_guard or MergeGuard(ontology)
        self._event_bus = event_bus
        self._sessions: dict[str, RepairSession] = {}
        # Race-safe accounting so two callers cannot start parallel sessions
        # for the same finding simultaneously.
        self._lock = threading.RLock()
        self._repair_project_id = repair_project_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_repair(
        self,
        finding_id: str,
        branch_id: str = "",
        sot_version: str = "current",
        masterplan_version: str = "current",
        created_by: str = "auto_repair",
    ) -> str:
        """R0: register a repair session for finding. Returns session_id (str).

        Per W14 C4 contract: this method MUST create a Branch with
        ``branch_type='repair'`` (or attach to one supplied by the caller)
        so downstream MergeGuard / regression infrastructure has something
        to anchor against. Returns the session_id as a string so callers
        coded against the contract don't have to know about RepairSession.
        """
        finding = self._ontology.get(Finding, finding_id)
        if finding is None:
            raise ValueError(f"finding not found: {finding_id}")

        with self._lock:
            # Parallel-session guard: only one OPEN session per finding.
            existing = [
                s for s in self._sessions.values()
                if s.finding_id == finding_id and not s.completed_at
                and not s.blocked
            ]
            if existing:
                raise RuntimeError(
                    f"finding {finding_id} already has an active repair "
                    f"session ({existing[0].session_id})"
                )

            # Loop check before even starting
            check = self._loop.check(finding_id)
            if not check["allowed"]:
                session = RepairSession(
                    finding_id=finding_id,
                    branch_id=branch_id,
                    blocked=True,
                    block_reason=check["reason"],
                    loop_report_id=check["loop_report_id"],
                )
                self._sessions[session.session_id] = session
                log.warning("repair blocked at R0: %s (%s)",
                            finding_id, check["reason"])
                self._emit("aeis.testing.repair.session_blocked", {
                    "session_id": session.session_id,
                    "finding_id": finding_id,
                    "reason": check["reason"],
                })
                return session.session_id

            # Materialize a repair branch if the caller didn't supply one.
            if not branch_id:
                project_id = (
                    getattr(finding, "ticket_id", "")
                    or self._repair_project_id
                )
                branch = Branch(
                    branch_type=BranchType.REPAIR.value,
                    parent_branch_id="main",
                    project_id=project_id if project_id.startswith("proj_")
                    else self._repair_project_id,
                    sot_version=sot_version,
                    masterplan_version=masterplan_version,
                    created_by=created_by,
                )
                self._ontology.create(branch)
                branch_id = branch.branch_id

            session = RepairSession(
                finding_id=finding_id,
                branch_id=branch_id,
                last_phase=finding.r_status,
            )
            self._sessions[session.session_id] = session

        self._emit("aeis.testing.repair.session_started", {
            "session_id": session.session_id,
            "finding_id": finding_id,
            "branch_id": branch_id,
        })
        return session.session_id

    @staticmethod
    def _is_legal_transition(current: str, proposed: str) -> bool:
        """Forward-only along PHASES_ORDER, with terminal/loopback overrides."""
        if proposed in TERMINAL_STATUSES:
            return True
        if proposed in LOOPBACK_STATUSES:
            # Regression failures legitimately re-enter from REPAIRING /
            # READY_FOR_RETEST.
            return current in {
                RStatus.REPAIRING.value,
                RStatus.READY_FOR_RETEST.value,
            }
        if current in LOOPBACK_STATUSES:
            # From REGRESSION_FAILED we may go back into the repair loop.
            return proposed in {
                RStatus.REPAIRING.value,
                RStatus.REPAIR_PROPOSED.value,
            }
        if current not in PHASES_ORDER or proposed not in PHASES_ORDER:
            return False
        ci = PHASES_ORDER.index(current)
        pi = PHASES_ORDER.index(proposed)
        # Allow same-phase re-entry (idempotent step) and forward-only.
        return pi >= ci

    def step(
        self,
        session_id: str,
        target_phase: str,
        attempt_payload: dict | None = None,
        merge_context: dict | None = None,
    ) -> dict:
        """Transition to target_phase. Records RepairAttempt on R3..R5.

        Strict forward-only along PHASES_ORDER; terminal statuses
        (CLOSED/ESCALATED/WAIVED_BY_HUMAN) and the regression-failed
        loopback are the only exceptions. ``merge_context`` is forwarded
        to MergeGuard.check_branch when transitioning to VERIFIED/CLOSED
        so the controller owns the C4-required merge validation rather
        than offloading it to a side-channel API.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"session not found: {session_id}")
        if session.blocked:
            return {
                "next_status": session.last_phase,
                "attempts": session.attempt_count,
                "blocked": True,
                "reason": session.block_reason,
            }
        if target_phase not in RStatus.values():
            raise ValueError(f"invalid target_phase: {target_phase}")

        finding = self._ontology.get(Finding, session.finding_id)
        if finding is None:
            raise ValueError(f"finding gone: {session.finding_id}")

        if not self._is_legal_transition(session.last_phase, target_phase):
            raise ValueError(
                f"illegal transition {session.last_phase!r} -> "
                f"{target_phase!r}; PHASES_ORDER is forward-only with "
                f"terminal/loopback exceptions only"
            )

        # MergeGuard at merge-relevant transitions (C4 contract: controller
        # owns guard validation, no side-channel request_merge required).
        if target_phase in (RStatus.VERIFIED.value, RStatus.CLOSED.value) \
                and session.branch_id:
            guard_result = self._guard.check_branch(
                session.branch_id, merge_context,
            )
            if not guard_result.get("allowed", False):
                session.blocked = True
                session.block_reason = "merge_guard_violation"
                self._emit("aeis.testing.repair.merge_guard_blocked", {
                    "session_id": session_id,
                    "violations": guard_result.get("violations", []),
                })
                return {
                    "next_status": session.last_phase,
                    "attempts": session.attempt_count,
                    "blocked": True,
                    "reason": "merge_guard_violation",
                    "violations": guard_result.get("violations", []),
                }

        # Phases that require Loop Governor + create attempt records
        attempting_phases = {
            RStatus.REPAIR_PROPOSED.value,
            RStatus.REPAIRING.value,
        }
        if target_phase in attempting_phases:
            check = self._loop.check(session.finding_id, attempt_payload)
            if not check["allowed"]:
                session.blocked = True
                session.block_reason = check["reason"]
                session.loop_report_id = check["loop_report_id"]
                self._emit("aeis.testing.repair.session_blocked", {
                    "session_id": session_id,
                    "reason": check["reason"],
                    "loop_report_id": check["loop_report_id"],
                })
                return {
                    "next_status": finding.r_status,
                    "attempts": session.attempt_count,
                    "blocked": True,
                    "reason": check["reason"],
                    "loop_report_id": check["loop_report_id"],
                }

            # Record attempt
            session.attempt_count += 1
            ap = attempt_payload or {}
            attempt = RepairAttempt(
                finding_id=session.finding_id,
                n=session.attempt_count,
                patch_proposal_id=ap.get("patch_proposal_id"),
                r_phase=target_phase,
                result=ap.get("result", "success"),
                files_touched_count=int(ap.get("files_touched_count", 0)),
                diff_lines=int(ap.get("diff_lines", 0)),
                time_in_phase_s=float(ap.get("time_in_phase_s", 0.0)),
                cost_usd=float(ap.get("cost_usd", 0.0)),
                completed_at=time.time(),
            )
            self._ontology.create(attempt)

        # Phase transition on Finding
        finding.r_status = target_phase
        if target_phase == RStatus.CLOSED.value:
            finding.closed_at = time.time()
        self._ontology.update(finding)
        session.last_phase = target_phase
        if target_phase in (RStatus.CLOSED.value, RStatus.VERIFIED.value):
            session.completed_at = time.time()

        self._emit("aeis.testing.repair.phase_transitioned", {
            "session_id": session_id,
            "finding_id": session.finding_id,
            "to": target_phase,
        })

        return {
            "next_status": target_phase,
            "attempts": session.attempt_count,
            "blocked": False,
        }

    def get_session(self, session_id: str) -> dict | None:
        """C4 contract: returns a plain dict (or None when not found).

        Internal callers can still reach the dataclass via
        ``_get_session_obj`` if needed.
        """
        s = self._sessions.get(session_id)
        if s is None:
            return None
        return asdict(s)

    def _get_session_obj(self, session_id: str) -> RepairSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self, blocked_only: bool = False) -> list[dict]:
        items = list(self._sessions.values())
        if blocked_only:
            items = [s for s in items if s.blocked]
        return [asdict(s) for s in items]

    def request_merge(self, session_id: str, merge_context: dict | None = None) -> dict:
        """Final R9 gate: consult Merge Guard before signalling merge.

        Returns Guard's verdict. Caller (BranchManager.merge) makes the actual merge.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"session not found: {session_id}")
        if not session.branch_id:
            return {"allowed": False, "violations": ["no_branch_associated"]}
        return self._guard.check_branch(session.branch_id, merge_context)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        try:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=event_type, payload=payload,
                source_module="aeis.testing.auto_repair_controller",
            ))
        except Exception as e:  # pragma: no cover
            log.debug("event emit failed (%s): %s", event_type, e)


__all__ = ["AutoRepairController", "RepairSession", "PHASES_ORDER"]
