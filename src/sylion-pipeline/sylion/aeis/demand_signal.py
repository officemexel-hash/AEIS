"""F-009 path alias: Masterplan v3.5 R3.10 declares this module at
``sylion.aeis.demand_signal`` but the actual implementation lives under
``sylion.skills.demand_signal`` (Plan 20 - skill demand analyser).

This file is a thin re-export so both canonical paths resolve to the same
implementation until the Masterplan is updated to v3.6+ to reflect the
move into ``sylion.skills``. Audit finding F-009 documents the path drift.
"""
from __future__ import annotations

from sylion.skills import demand_signal as _impl

# Re-export every public name (no leading underscore) from the implementation.
for _name in dir(_impl):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_impl, _name)

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
