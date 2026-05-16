"""W14 Loop Governor — hard limits on auto-repair iterations.

Prevents endless model loops by blocking new attempts once any limit
is exceeded. Limits per docs/CLAUDE_AEIS_W14_TESTING.md sec 12.1:

  max_auto_fix_attempts_per_finding: 2
  max_total_no_go_iterations: 3
  max_files_touched_no_hg: 5
  max_diff_size_no_hg: 300
  max_time_in_repair_loop_s: 1800
  max_same_test_retries: 3
  max_new_p0_p1_introduced: 0
  max_parallel_repair_agents_per_finding: 1
"""
from __future__ import annotations

import logging
import time
from typing import Any

from sylion.aeis.testing.ontology.objects import (
    Finding, LoopReport, RepairAttempt,
)
from sylion.aeis.testing.ontology.store import OntologyStore

log = logging.getLogger("sylion.aeis.testing.loop_governor")


# ----------------------------------------------------------------------
# Defaults
# ----------------------------------------------------------------------

# Module-level alias kept for backward compatibility with earlier importers;
# the contract surface is ``LoopGovernor.DEFAULTS`` (class attribute below).
DEFAULT_LIMITS: dict[str, Any] = {
    "max_auto_fix_attempts_per_finding": 2,
    "max_total_no_go_iterations": 3,
    "max_files_touched_no_hg": 5,
    "max_diff_size_no_hg": 300,
    "max_time_in_repair_loop_s": 1800,
    "max_same_test_retries": 3,
    "max_new_p0_p1_introduced": 0,
    "max_parallel_repair_agents_per_finding": 1,
}


# Map limit-name -> canonical LoopReport.loop_type (one of 6 enum values)
LIMIT_TO_LOOP_TYPE: dict[str, str] = {
    "max_auto_fix_attempts_per_finding": "no_progress",
    "max_total_no_go_iterations": "no_progress",
    "max_files_touched_no_hg": "scope_drift",
    "max_diff_size_no_hg": "scope_drift",
    "max_time_in_repair_loop_s": "no_progress",
    "max_same_test_retries": "same_failure",
    "max_new_p0_p1_introduced": "new_failures",
    "max_parallel_repair_agents_per_finding": "no_progress",
}


class LoopGovernor:
    """Enforces hard auto-repair limits and emits LoopReport on block."""

    # Contract surface (W14_INTEGRATION_CONTRACTS.md C4): introspectable
    # default limits exposed on the class itself.
    DEFAULTS: dict[str, Any] = dict(DEFAULT_LIMITS)

    def __init__(
        self,
        ontology: OntologyStore,
        limits: dict[str, Any] | None = None,
        event_bus: Any | None = None,
    ) -> None:
        self._ontology = ontology
        self._limits = {**self.DEFAULTS, **(limits or {})}
        self._event_bus = event_bus
        # Race-safe accounting: parallel check() callers must not both pass
        # when their cumulative payloads would exceed the budget.
        self._lock = __import__("threading").RLock()

    @property
    def limits(self) -> dict[str, Any]:
        return dict(self._limits)

    @staticmethod
    def _safe_int(value: Any, field_name: str, default: int = 0) -> int:
        """Coerce attempt_payload values to int. NaN/inf/strings -> default+log."""
        if value is None:
            return default
        try:
            iv = int(value)
        except (TypeError, ValueError):
            log.warning(
                "loop_governor: invalid %s=%r, using default %d",
                field_name, value, default,
            )
            return default
        return max(iv, 0)

    def check(self, finding_id: str, attempt_payload: dict | None = None) -> dict:
        """Return {'allowed': bool, 'reason': str|None, 'loop_report_id': str|None}.

        attempt_payload may include:
          files_touched_count, diff_lines, has_hg_ticket, new_p0_p1_introduced,
          parallel_agents_active

        The whole check is wrapped in ``self._lock`` so two parallel callers
        cannot both pass when their cumulative payload would breach a limit.
        """
        ap = attempt_payload or {}
        with self._lock:
            return self._check_locked(finding_id, ap)

    def _check_locked(self, finding_id: str, ap: dict) -> dict:
        finding = self._ontology.get(Finding, finding_id)
        if finding is None:
            return {"allowed": False, "reason": "finding_not_found",
                    "loop_report_id": None}

        # Existing attempts for this finding
        attempts = self._ontology.list(
            RepairAttempt, filters={"finding_id": finding_id}, limit=1000,
        )

        # 1. attempts_per_finding
        if len(attempts) >= self._limits["max_auto_fix_attempts_per_finding"]:
            return self._block(
                finding_id, "max_auto_fix_attempts_per_finding",
                attempts, similarity=self._estimate_similarity(attempts),
            )

        # 2. NO-GO iterations (failed_same / failed_new / regression_failed)
        no_go = sum(
            1 for a in attempts
            if a.result in ("failed_same", "failed_new", "regression_failed")
        )
        if no_go >= self._limits["max_total_no_go_iterations"]:
            return self._block(
                finding_id, "max_total_no_go_iterations",
                attempts, similarity=self._estimate_similarity(attempts),
            )

        # 3. files_touched (cumulative)
        files_total = sum(a.files_touched_count for a in attempts)
        if not ap.get("has_hg_ticket"):
            future_files = files_total + self._safe_int(
                ap.get("files_touched_count"), "files_touched_count",
            )
            if future_files > self._limits["max_files_touched_no_hg"]:
                return self._block(
                    finding_id, "max_files_touched_no_hg",
                    attempts, similarity=0.0,
                )
            future_loc = sum(a.diff_lines for a in attempts) + self._safe_int(
                ap.get("diff_lines"), "diff_lines",
            )
            if future_loc > self._limits["max_diff_size_no_hg"]:
                return self._block(
                    finding_id, "max_diff_size_no_hg",
                    attempts, similarity=0.0,
                )

        # 4. time in loop
        if attempts:
            oldest = min(a.started_at for a in attempts)
            if (time.time() - oldest) > self._limits["max_time_in_repair_loop_s"]:
                return self._block(
                    finding_id, "max_time_in_repair_loop_s",
                    attempts, similarity=0.0,
                )

        # 5. parallel agents — caller-supplied counter is the source of
        # truth (Kimi attack #1: RepairAttempt.completed_at is set when
        # the persisted record is created, not when the worker actually
        # finishes, so the persisted-state heuristic always reads zero
        # active attempts). Combine with the persisted active count for
        # safety: either signal exceeding max_par blocks the new attempt.
        active_attempts = [a for a in attempts if a.completed_at is None]
        max_par = self._limits["max_parallel_repair_agents_per_finding"]
        active_now = self._safe_int(
            ap.get("parallel_agents_active"), "parallel_agents_active",
        )
        if len(active_attempts) >= max_par or active_now >= max_par:
            return self._block(
                finding_id, "max_parallel_repair_agents_per_finding",
                attempts, similarity=0.0,
            )

        # 6. new P0/P1 introduced
        new_pf = self._safe_int(
            ap.get("new_p0_p1_introduced"), "new_p0_p1_introduced",
        )
        if new_pf > self._limits["max_new_p0_p1_introduced"]:
            return self._block(
                finding_id, "max_new_p0_p1_introduced",
                attempts, similarity=0.0,
            )

        return {"allowed": True, "reason": None, "loop_report_id": None}

    def generate_loop_report(
        self,
        finding_id: str,
        loop_type: str = "same_failure",
        attempts: list[RepairAttempt] | None = None,
        similarity: float = 0.0,
    ) -> LoopReport:
        """Create + persist a LoopReport for this finding (idempotent).

        If a report already exists for the same (finding_id, loop_type)
        pair we return the existing one rather than creating a duplicate.
        Kimi attack #4 (race-condition LoopReport storm) is defused by
        running the lookup-then-create under ``self._lock``.
        """
        with self._lock:
            existing = self._ontology.list(
                LoopReport,
                filters={"finding_id": finding_id, "loop_type": loop_type},
                limit=10,
            )
            if existing:
                return existing[0]

            if attempts is None:
                attempts = self._ontology.list(
                    RepairAttempt,
                    filters={"finding_id": finding_id},
                    limit=1000,
                )
            report = LoopReport(
                finding_id=finding_id,
                loop_type=loop_type,
                attempts_n=len(attempts),
                similarity_score=similarity,
                suspected_root_cause=self._suspect_root_cause(attempts, loop_type),
                blocked_actions=self._blocked_actions_for(loop_type),
                required_decision={
                    "type": "Human Gate",
                    "suggested_d_level": "D3",
                    "question": (
                        "Auto-repair blocked. Review attempts and decide: "
                        "patch differently, change masterplan/SoT, or accept as known issue."
                    ),
                },
            )
            self._ontology.create(report)
        self._emit("aeis.testing.loop.detected", {
            "finding_id": finding_id,
            "report_id": report.report_id,
            "loop_type": loop_type,
        })
        return report

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _block(
        self,
        finding_id: str,
        limit_name: str,
        attempts: list[RepairAttempt],
        similarity: float,
    ) -> dict:
        # Map limit name to canonical LoopReport.loop_type enum
        loop_type = LIMIT_TO_LOOP_TYPE.get(limit_name, "no_progress")
        report = self.generate_loop_report(
            finding_id, loop_type=loop_type,
            attempts=attempts, similarity=similarity,
        )
        self._emit("aeis.testing.loop.blocked", {
            "finding_id": finding_id,
            "report_id": report.report_id,
            "reason": limit_name,
        })
        return {
            "allowed": False,
            "reason": limit_name,
            "loop_report_id": report.report_id,
        }

    @staticmethod
    def _estimate_similarity(attempts: list[RepairAttempt]) -> float:
        """Cheap proxy: ratio of attempts with same result."""
        if len(attempts) < 2:
            return 0.0
        results = [a.result for a in attempts]
        most_common_count = max(results.count(r) for r in set(results))
        return most_common_count / len(results)

    @staticmethod
    def _suspect_root_cause(
        attempts: list[RepairAttempt], loop_type: str,
    ) -> list[str]:
        """Map canonical loop_type values (from LIMIT_TO_LOOP_TYPE) to causes.

        Earlier versions branched on raw limit names that ``_block`` had
        already translated to canonical loop types — so several arms were
        unreachable and reports collapsed to ``["unknown"]``. Now keyed by
        the actual loop_type values the LoopReport stores.
        """
        causes: list[str] = []
        if loop_type == "same_failure":
            causes.append("ambiguous_specification_or_test_expectation")
            causes.append("contract_mismatch_between_modules")
        elif loop_type == "no_progress":
            causes.append("repeated_failure_pattern_indicates_root_in_dependency")
            causes.append("complexity_exceeds_auto_repair_budget")
        elif loop_type == "scope_drift":
            causes.append("scope_too_large_for_auto_repair")
            causes.append("attempted_rewrite_instead_of_patch")
        elif loop_type == "new_failures":
            causes.append("patch_breaks_neighboring_modules")
        elif loop_type == "test_modification":
            causes.append("test_was_weakened_or_skipped_to_pass")
        elif loop_type == "semantic_repeat":
            causes.append("equivalent_patch_with_different_surface")
        return causes or ["unknown"]

    @staticmethod
    def _blocked_actions_for(loop_type: str) -> list[str]:
        return [
            "further_auto_patch",
            "test_deletion",
            "assertion_weakening",
            "mock_as_fix",
        ]

    def _emit(self, event_type: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        try:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=event_type, payload=payload,
                source_module="aeis.testing.loop_governor",
            ))
        except Exception as e:  # pragma: no cover
            log.debug("event emit failed (%s): %s", event_type, e)


__all__ = ["LoopGovernor", "DEFAULT_LIMITS"]
