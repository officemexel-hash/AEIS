"""SYLION AEIS v2 — W14 Simulation L0-L4 plane (Phase 0).

This package provides graduated simulation environments used by W14
testing/simulation/repair/release governance. The W14 charter §Sim L0-L4
calls for five levels of fidelity vs. cost:

- ``L0``: pure-Python in-memory, no I/O — fastest, for unit-level
  fan-out tests and shape sanity checks.
- ``L1``: SQLite as PG substitute — fast, for query-shape tests where a
  real PG round-trip is overkill.
- ``L2``: real PG transient (transaction rolled back at end) — medium,
  for DDL tests and constraint validation. Phase 0 stub raises
  ``NotImplementedError`` (deferred to G2 once the v2 PG pool is wired
  to a disposable test database).
- ``L3``: real PG persistent, dedicated test schema — slow; placeholder.
- ``L4``: full multi-host federation — out of scope for Phase 0.

Phase 0 (this commit) ships L0 + L1 only. L2-L4 raise
``NotImplementedError`` with a clear deferral message so callers
opting into them get a typed failure rather than a silent skip.

Public API:

    from sylion.aeis_v2.simulation import (
        SimLevel,
        SimSession,
        create_l0_session,
        create_l1_session,
        create_l2_session,
        create_session,
        with_session,
        populate_l0_with_demo_customers,
        populate_l1_with_demo_customers,
    )

See ``levels.py`` for full docstrings.
"""
from __future__ import annotations

from sylion.aeis_v2.simulation.levels import (
    SimLevel,
    SimSession,
    create_l0_session,
    create_l1_session,
    create_l2_session,
    create_l3_session,
    create_l4_session,
    create_session,
    populate_l0_with_demo_customers,
    populate_l1_with_demo_customers,
    with_session,
)

__all__ = [
    "SimLevel",
    "SimSession",
    "create_l0_session",
    "create_l1_session",
    "create_l2_session",
    "create_l3_session",
    "create_l4_session",
    "create_session",
    "with_session",
    "populate_l0_with_demo_customers",
    "populate_l1_with_demo_customers",
]
