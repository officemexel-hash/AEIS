"""W14 Guardians — 13 event subscribers (8 core + 5 NEW)."""
from __future__ import annotations

from typing import Any

from sylion.aeis.testing.guardians.base import GuardianBase
from sylion.aeis.testing.guardians.implementations import (
    ALL_GUARDIAN_CLASSES, CostSentinel, CouncilGuardian, EvidenceGuardian,
    GateGuardian, LLMDriftGuardian, LoopGuardian, MasterplanGuardian,
    MockFallbackGuardian, PIIGuardian, ReleaseGuardian, SoTGuardian,
    TestIntegrityGuardian, TraceCompletenessGuardian,
)
from sylion.aeis.testing.ontology.store import OntologyStore


def register_all_guardians(
    ontology: OntologyStore | None = None,
    event_bus: Any | None = None,
) -> dict[str, GuardianBase]:
    """Instantiate all 13 guardians and wire each one to the bus.

    When ``event_bus`` is provided every guardian subscribes its
    ``subscribed_events`` topics so a publish on the bus reaches the
    guardian's ``handle_event`` (idempotent + crash-isolated wrapper
    around ``on_event``).
    """
    out: dict[str, GuardianBase] = {}
    for cls in ALL_GUARDIAN_CLASSES:
        g = cls(ontology=ontology, event_bus=event_bus)
        if event_bus is not None:
            g.subscribe(event_bus)
        out[g.name] = g
    return out


__all__ = [
    "GuardianBase",
    "ALL_GUARDIAN_CLASSES",
    "register_all_guardians",
    "SoTGuardian", "MasterplanGuardian", "TestIntegrityGuardian",
    "MockFallbackGuardian", "EvidenceGuardian", "GateGuardian",
    "CouncilGuardian", "ReleaseGuardian", "LoopGuardian",
    "LLMDriftGuardian", "CostSentinel", "PIIGuardian",
    "TraceCompletenessGuardian",
]
