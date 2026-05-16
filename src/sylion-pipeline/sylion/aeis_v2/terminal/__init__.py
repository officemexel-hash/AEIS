"""W18 Operator Terminal Plane — public API.

PDF §7: "Pełen interaktywny terminal jako pierwszorzędne UI dla Roberta —
pokazuje na żywo co się dzieje w całej federacji agentów, z możliwością
interwencji w każdym momencie. Cockpit/Mission Control dla SYLION-a."

Phase 0 deliverables:

- ``sessions.py`` — model + store dla sesji terminala (każda sesja =
  kontekst pracy, multi-session równolegle).
- ``commands.py`` — parser command palette (``/status``, ``/cost``,
  ``/agents``, ...).
- ``stream.py`` — SSE event stream subscribing to ``sylion.core.event_bus``.
- ``replay.py`` — append-only log replay step-by-step (skeleton).

REST + SSE entry point: ``sylion/api/terminal_routes.py``.

Charter: ``docs/v2/charters/W18_operator_terminal.md``.
"""
from __future__ import annotations

from sylion.aeis_v2.terminal.sessions import (
    TerminalSession,
    SessionStore,
    get_session_store,
)
from sylion.aeis_v2.terminal.commands import (
    CommandResult,
    parse_command,
    list_commands,
    BUILTIN_COMMANDS,
)

__all__ = [
    "TerminalSession",
    "SessionStore",
    "get_session_store",
    "CommandResult",
    "parse_command",
    "list_commands",
    "BUILTIN_COMMANDS",
]
