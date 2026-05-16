"""W14 Testing Actions — base handler class.

Each action is a TestingActionHandler subclass with:
  - target_action (str)
  - d_level (DLevel)
  - phase ("TWO_PHASE" | "IMMEDIATE")
  - mirror_to_ticket (bool)
  - gate_type (GateType | None)

Methods:
  - validate(payload: dict) -> None  (raises ValueError on bad input)
  - execute(payload: dict, intent_id: str) -> dict  (returns result)

The handler is registered via register_testing_actions() which wires it into
the existing CommandBus (target_module="testing").
"""
from __future__ import annotations

import logging
import time
from typing import Any, Literal

from sylion.aeis.testing.ontology.enums import DLevel, GateType
from sylion.aeis.testing.ontology.store import OntologyStore

log = logging.getLogger("sylion.aeis.testing.actions.base")


# ----------------------------------------------------------------------
# Priority -> SLA mapping (for governance ticket mirror)
# ----------------------------------------------------------------------

PRIORITY_BY_DLEVEL: dict[DLevel, str] = {
    DLevel.D0: "P4",
    DLevel.D1: "P3",
    DLevel.D2: "P2",
    DLevel.D3: "P1",
    DLevel.D4: "P0",
    DLevel.D5: "P0",
}

SLA_SECONDS: dict[str, int] = {
    "P0": 15 * 60,           # 15 min
    "P1": 60 * 60,           # 1h
    "P2": 4 * 60 * 60,       # 4h
    "P3": 24 * 60 * 60,      # 1d
    "P4": 7 * 24 * 60 * 60,  # 1w
}


# ----------------------------------------------------------------------
# Handler base class
# ----------------------------------------------------------------------

class TestingActionHandler:
    """Abstract base for W14 testing actions registered on CommandBus.

    Subclasses override class attributes (target_action, d_level, phase,
    mirror_to_ticket, gate_type). Stores are injected via __init__.
    """

    # Pytest: do NOT collect this class (name starts with "Test")
    __test__ = False

    # Class-level attributes (overridden by subclasses)
    target_action: str = ""
    d_level: DLevel = DLevel.D1
    phase: Literal["TWO_PHASE", "IMMEDIATE"] = "TWO_PHASE"
    mirror_to_ticket: bool = False
    gate_type: GateType | None = None

    def __init__(
        self,
        ontology: OntologyStore | None = None,
        tickets: Any | None = None,
        event_bus: Any | None = None,
    ) -> None:
        self.ontology = ontology
        self.tickets = tickets
        self.event_bus = event_bus

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(target_action={self.target_action!r}, "
            f"d_level={self.d_level.value}, phase={self.phase})"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, payload: dict) -> None:
        """Raise ValueError if payload is invalid."""
        raise NotImplementedError(f"{type(self).__name__}.validate")

    def execute(self, payload: dict, intent_id: str) -> dict:
        """Perform the action. Return result dict."""
        raise NotImplementedError(f"{type(self).__name__}.execute")

    # ------------------------------------------------------------------
    # Helpers (used by subclasses)
    # ------------------------------------------------------------------

    def _require_keys(self, payload: dict, *keys: str) -> None:
        missing = [k for k in keys if k not in payload]
        if missing:
            raise ValueError(
                f"{self.target_action}: missing required fields: {missing}"
            )

    def _require_prefix(self, payload: dict, key: str, prefix: str) -> None:
        value = payload.get(key, "")
        if not isinstance(value, str) or not value.startswith(prefix):
            raise ValueError(
                f"{self.target_action}: {key} must start with '{prefix}', got: {value!r}"
            )

    def _require_not_main(self, payload: dict, key: str = "branch_id") -> None:
        """Hard validation: branch_id MUST NOT be 'main'.

        Defensive normalization: strips whitespace and case-folds before the
        comparison so attempts like "MAIN", "main ", "Main\\n" all reject.
        """
        raw = payload.get(key)
        if raw is None:
            return
        if not isinstance(raw, str):
            raise ValueError(
                f"{self.target_action}: {key} must be a string, "
                f"got {type(raw).__name__}"
            )
        normalized = raw.strip().casefold()
        if normalized == "main":
            raise ValueError(
                f"{self.target_action}: {key} MUST NOT be 'main' "
                f"(W14 prohibits direct main mutation; got: {raw!r})"
            )

    def _require_in_range(self, payload: dict, key: str,
                           lo: float, hi: float) -> None:
        v = payload.get(key)
        if v is None or not (lo <= float(v) <= hi):
            raise ValueError(
                f"{self.target_action}: {key} must be in [{lo}, {hi}], got: {v!r}"
            )

    def _emit(self, event_type: str, payload: dict,
              *, trace_id: str | None = None) -> None:
        """Publish a SylionEvent.

        ``trace_id`` is auto-injected into the event payload so every action
        emit is correlatable across the W14 audit trail. Callers that already
        carry the ``intent_id`` MUST pass it as ``trace_id`` here; older call
        sites that put trace_id directly in the payload still work because
        we don't overwrite an explicit value.
        """
        if self.event_bus is None:
            return
        merged_payload = dict(payload)
        if trace_id and "trace_id" not in merged_payload:
            merged_payload["trace_id"] = trace_id
        try:
            # Two SylionEvent shapes coexist in the codebase: the canonical
            # core/event_bus.SylionEvent uses (event_id, topic, payload, ...);
            # the W14 contracts also reference (event_type=..., payload=...,
            # producer_module=...). We try the canonical shape first and fall
            # back so this module works against both.
            from sylion.core.event_bus import SylionEvent
            try:
                evt = SylionEvent(
                    event_id="",
                    topic=event_type,
                    payload=merged_payload,
                    source_module="aeis.testing.actions",
                )
            except TypeError:
                evt = SylionEvent(  # type: ignore[call-arg]
                    event_type=event_type,
                    payload=merged_payload,
                    producer_module="aeis.testing.actions",
                )
            self.event_bus.publish(evt)
        except Exception as e:  # pragma: no cover — best-effort emit
            log.debug("event emit failed (%s): %s", event_type, e)

    def _mirror_ticket(self, *, project_id: str, title: str,
                       summary: str, payload: dict,
                       requested_by: str = "system",
                       gate_type_override: GateType | None = None) -> str | None:
        """Create GovernanceTicket if mirror_to_ticket=True. Returns ticket_id."""
        if not self.mirror_to_ticket or self.tickets is None:
            return None
        try:
            from sylion.governance.ticket import GovernanceTicket
        except Exception:  # pragma: no cover
            return None

        gate = gate_type_override or self.gate_type or GateType.NON_BLOCKING
        priority = PRIORITY_BY_DLEVEL.get(self.d_level, "P3")
        sla = SLA_SECONDS.get(priority, 86400)

        ticket = GovernanceTicket(
            origin="testing",
            project_id=project_id,
            decision_class=self.d_level.value,
            gate_type=gate.value if hasattr(gate, "value") else str(gate),
            priority=priority,
            title=title,
            summary=summary,
            payload=payload,
            requested_by=requested_by,
            sla_deadline=time.time() + sla,
        )
        try:
            return self.tickets.submit(ticket)
        except Exception as e:  # pragma: no cover
            log.warning("ticket submit failed (%s): %s", self.target_action, e)
            return None


__all__ = [
    "TestingActionHandler",
    "PRIORITY_BY_DLEVEL",
    "SLA_SECONDS",
]
