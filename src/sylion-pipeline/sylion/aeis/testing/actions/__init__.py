"""W14 Testing Actions — 20 handlers (19 MVP + 1 utility) on top of CommandBus.

Spec: docs/w14_workplan/actions_spec.yaml (FROZEN, E0 HG approved 2026-04-26).

Usage::

    from sylion.aeis.testing.actions import register_testing_actions
    handlers = register_testing_actions(
        bus=command_bus,
        ontology=ontology_store,
        tickets=ticket_store,
        event_bus=event_bus,
    )
"""
from __future__ import annotations

import logging
from typing import Any

from sylion.aeis.testing.actions.base import TestingActionHandler
from sylion.aeis.testing.actions.charter_actions import CHARTER_HANDLERS
from sylion.aeis.testing.actions.finding_actions import FINDING_HANDLERS
from sylion.aeis.testing.actions.persona_actions import PERSONA_HANDLERS
from sylion.aeis.testing.actions.release_actions import RELEASE_HANDLERS
from sylion.aeis.testing.actions.repair_actions import REPAIR_HANDLERS
from sylion.aeis.testing.ontology.store import OntologyStore

log = logging.getLogger("sylion.aeis.testing.actions")

ALL_HANDLER_CLASSES: tuple[type[TestingActionHandler], ...] = (
    *CHARTER_HANDLERS,
    *FINDING_HANDLERS,
    *REPAIR_HANDLERS,
    *PERSONA_HANDLERS,
    *RELEASE_HANDLERS,
)


def register_testing_actions(
    bus: Any | None = None,
    ontology: OntologyStore | None = None,
    tickets: Any | None = None,
    event_bus: Any | None = None,
) -> dict[str, TestingActionHandler]:
    """Instantiate all 20 handlers, optionally wire into CommandBus.

    Returns dict mapping target_action -> handler instance.

    The handlers are usable standalone (handler.validate() / handler.execute())
    so tests can drive them without a CommandBus. If `bus` is provided, the
    handlers register themselves on the bus for ``target_module="testing"``.
    """
    handlers: dict[str, TestingActionHandler] = {}
    for cls in ALL_HANDLER_CLASSES:
        h = cls(
            ontology=ontology,
            tickets=tickets,
            event_bus=event_bus,
        )
        if h.target_action in handlers:
            raise RuntimeError(f"duplicate target_action: {h.target_action}")
        handlers[h.target_action] = h

    if bus is not None:
        register_handler = getattr(bus, "register_handler", None)
        if callable(register_handler):
            for handler in handlers.values():
                try:
                    register_handler(handler, target_module="testing")
                except RuntimeError as exc:
                    # Duplicate registration: harmless if app.py boots twice
                    # in tests; log and move on.
                    log.debug("handler %s already registered: %s",
                              handler.target_action, exc)
        else:
            # Older CommandBus shim: fall back to the legacy attr (still
            # readable by handler-aware code paths) so we don't crash.
            existing = getattr(bus, "_testing_handlers", None)
            if existing is None:
                try:
                    bus._testing_handlers = handlers  # type: ignore[attr-defined]
                except Exception as e:
                    log.warning(
                        "could not attach _testing_handlers to bus: %s", e
                    )
            else:
                existing.update(handlers)

    log.info("registered %d W14 testing action handlers", len(handlers))
    return handlers


__all__ = [
    "TestingActionHandler",
    "ALL_HANDLER_CLASSES",
    "register_testing_actions",
    "CHARTER_HANDLERS",
    "FINDING_HANDLERS",
    "REPAIR_HANDLERS",
    "PERSONA_HANDLERS",
    "RELEASE_HANDLERS",
]
