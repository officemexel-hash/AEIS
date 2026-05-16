"""W14 FindingStore — domain wrapper for Finding R-status lifecycle.

Enforces R0-R9 transition rules. Each Finding can also auto-mirror to
governance.tickets (if attached) for audit-chain integration.

Lifecycle (13 states, sec 11.1):
  OPEN -> TRIAGED -> REPRODUCED -> CLASSIFIED -> REPAIR_PROPOSED ->
    {WAITING_FOR_HUMAN_GATE, REPAIRING} -> READY_FOR_RETEST ->
    {VERIFIED, REGRESSION_FAILED} -> CLOSED
  Side branches:
    ESCALATED (any -> here when blocked by Loop Governor or human review)
    WAIVED_BY_HUMAN (any -> here with HG approval)

Thread-safe: ``threading.RLock`` serializes transitions so two parallel
calls cannot both pass the state-machine check on a stale read.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

from sylion.aeis.testing.ontology.enums import RStatus, Severity
from sylion.aeis.testing.ontology.objects import Finding
from sylion.aeis.testing.ontology.store import OntologyStore

log = logging.getLogger("sylion.aeis.testing.findings")


def _truthy_evidence(value: Any) -> bool:
    """Whitespace-only strings + empty containers count as missing evidence."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return bool(value)


# Allowed transitions per R-status
_ALLOWED: dict[str, set[str]] = {
    "OPEN": {"TRIAGED", "REPRODUCED", "CLOSED", "ESCALATED", "WAIVED_BY_HUMAN"},
    "TRIAGED": {"REPRODUCED", "CLASSIFIED", "ESCALATED", "WAIVED_BY_HUMAN", "CLOSED"},
    "REPRODUCED": {"CLASSIFIED", "REPAIR_PROPOSED", "ESCALATED", "WAIVED_BY_HUMAN"},
    "CLASSIFIED": {"REPAIR_PROPOSED", "WAITING_FOR_HUMAN_GATE", "ESCALATED",
                   "WAIVED_BY_HUMAN"},
    "REPAIR_PROPOSED": {"REPAIRING", "WAITING_FOR_HUMAN_GATE", "ESCALATED",
                        "WAIVED_BY_HUMAN"},
    "WAITING_FOR_HUMAN_GATE": {"REPAIRING", "ESCALATED", "WAIVED_BY_HUMAN", "CLOSED"},
    "REPAIRING": {"READY_FOR_RETEST", "REGRESSION_FAILED", "ESCALATED"},
    "READY_FOR_RETEST": {"VERIFIED", "REGRESSION_FAILED", "ESCALATED"},
    "REGRESSION_FAILED": {"REPAIRING", "ESCALATED", "WAIVED_BY_HUMAN"},
    "VERIFIED": {"CLOSED"},
    "ESCALATED": {"WAIVED_BY_HUMAN", "CLOSED"},
    "WAIVED_BY_HUMAN": {"CLOSED"},
    "CLOSED": set(),
}

TERMINAL_STATUSES = ("CLOSED",)

# Kimi E7 attack #7: evidence keys required for *high-stakes* terminal
# transitions only. Mid-lifecycle steps (REPRODUCED / CLASSIFIED /
# REPAIR_PROPOSED) accept an empty evidence dict so the auto-repair
# loop isn't burdened with synthetic audit metadata at every step —
# the loop already emits `aeis.testing.finding.transitioned` with
# actor + trace_id for those.
_REQUIRED_EVIDENCE_BY_TARGET: dict[str, tuple[str, ...]] = {
    "VERIFIED": ("regression_run_id",),
    "WAIVED_BY_HUMAN": ("hg_ticket_id", "rationale"),
    "ESCALATED": ("reason",),
}


class FindingStore:
    """Lifecycle-aware wrapper for Finding."""

    def __init__(
        self,
        ontology: OntologyStore,
        tickets: Any | None = None,
        event_bus: Any | None = None,
    ) -> None:
        self._ontology = ontology
        self._tickets = tickets
        self._event_bus = event_bus
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, finding: Finding, mirror_to_ticket: bool = True) -> Finding:
        """Persist + optionally auto-mirror to governance.tickets for D2+."""
        if not finding.r_status:
            finding.r_status = RStatus.OPEN.value
        if finding.r_status not in RStatus.values():
            raise ValueError(f"invalid r_status: {finding.r_status}")
        self._ontology.create(finding)
        self._emit("aeis.testing.finding.detected", {
            "finding_id": finding.finding_id,
            "severity": finding.severity,
            "d_level": finding.d_level,
        })
        if mirror_to_ticket and finding.d_level in ("D2", "D3", "D4", "D5"):
            ticket_id = self._mirror_to_ticket(finding)
            if ticket_id:
                finding.ticket_id = ticket_id
                self._ontology.update(finding)
        return finding

    def transition(
        self,
        finding_id: str,
        new_status: str,
        evidence: dict | None = None,
        actor: str = "system",
    ) -> Finding:
        """Transition with R-status flow validation (atomic).

        evidence dict is recorded in event payload (audit only).
        Wrapped in ``self._lock`` so two parallel transition() calls
        cannot both pass the state-machine check on a stale read.
        """
        with self._lock:
            finding = self._ontology.get(Finding, finding_id)
            if finding is None:
                raise ValueError(f"finding not found: {finding_id}")
            if new_status not in RStatus.values():
                raise ValueError(f"invalid r_status: {new_status}")
            allowed = _ALLOWED.get(finding.r_status, set())
            if new_status not in allowed:
                raise ValueError(
                    f"invalid transition {finding.r_status} -> {new_status} "
                    f"(allowed: {sorted(allowed)})"
                )
            # Kimi E7 attack #7: evidence schema validation per target.
            required = _REQUIRED_EVIDENCE_BY_TARGET.get(new_status)
            if required:
                ev = evidence or {}
                if not isinstance(ev, dict):
                    raise ValueError("evidence must be a dict")
                missing = [
                    k for k in required
                    if not _truthy_evidence(ev.get(k))
                ]
                if missing:
                    raise ValueError(
                        f"transition to {new_status} requires evidence "
                        f"keys {sorted(required)}; missing/empty: {missing}"
                    )
            finding.r_status = new_status
            if new_status in TERMINAL_STATUSES:
                finding.closed_at = time.time()
            self._ontology.update(finding, actor=actor)
            self._emit("aeis.testing.finding.transitioned", {
                "finding_id": finding_id,
                "to": new_status,
                "actor": actor,
                "evidence": evidence or {},
            })
            if new_status == RStatus.CLOSED.value:
                self._emit("aeis.testing.finding.closed", {
                    "finding_id": finding_id,
                    "actor": actor,
                })
            return finding

    def list_open(self, severity: str | None = None) -> list[Finding]:
        """All findings not in terminal status. Severity filter is validated."""
        if severity is not None:
            if severity not in Severity.values():
                raise ValueError(
                    f"invalid severity filter: {severity!r}. "
                    f"Must be one of {Severity.values()} or None"
                )
        findings = self._ontology.list(Finding, limit=10000)
        out = [f for f in findings if f.r_status not in TERMINAL_STATUSES]
        if severity:
            out = [f for f in out if f.severity == severity]
        return out

    def list_by_d_level(self, d_level: str) -> list[Finding]:
        return self._ontology.list(
            Finding, filters={"d_level": d_level}, limit=10000,
        )

    def list_critical(self) -> list[Finding]:
        """Open P0/P1 findings (operator dashboard)."""
        out: list[Finding] = []
        for sev in (Severity.P0.value, Severity.P1.value):
            out.extend(self.list_open(severity=sev))
        return out

    def get(self, finding_id: str) -> Finding | None:
        return self._ontology.get(Finding, finding_id)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _mirror_to_ticket(self, finding: Finding) -> str | None:
        if self._tickets is None:
            return None
        try:
            from sylion.governance.ticket import GovernanceTicket
        except Exception:  # pragma: no cover
            return None
        # Lift project_id from finding context: prefer ticket_id (when the
        # caller already attached one) or scan description for the
        # ``proj_*`` token. Empty project_id breaks audit linkage so we
        # use a conservative fallback rather than silently mirroring with
        # an empty field.
        project_id = self._project_id_for(finding) or "proj_unknown"
        try:
            ticket = GovernanceTicket(
                origin="testing",
                project_id=project_id,
                decision_class=finding.d_level,
                gate_type="non_blocking",
                priority=finding.severity if finding.severity in Severity.values() else "P3",
                title=finding.title[:200],
                summary=finding.description[:500],
                payload={"finding_id": finding.finding_id},
                requested_by=finding.discovered_by,
                sla_deadline=time.time() + 86400,
            )
            return self._tickets.submit(ticket)
        except Exception as e:  # pragma: no cover
            log.warning("ticket mirror failed: %s", e)
            return None

    @staticmethod
    def _project_id_for(finding: Finding) -> str:
        """Best-effort extraction of proj_* id from finding context."""
        for attr in ("ticket_id", "description"):
            value = getattr(finding, attr, "") or ""
            if not isinstance(value, str):
                continue
            for token in value.split():
                if token.startswith("proj_"):
                    return token.strip(",.;:")
        return ""

    def _emit(self, topic: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        try:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.testing.findings",
            ))
        except Exception as e:  # pragma: no cover
            log.debug("event emit failed: %s", e)


__all__ = ["FindingStore", "TERMINAL_STATUSES"]
