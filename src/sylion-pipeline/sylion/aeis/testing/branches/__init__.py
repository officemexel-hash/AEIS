"""W14 Testing Branches — isolation envelope for repair/test/release work.

BranchManager extends governance.change_proposal flow with branch_id as
first-class object. Snapshot semantics differ per branch_type:
  - simulation: in-memory only, auto-discard after run
  - repair:     git-style branch with diff log, merge requires MergeGuard
  - test:       long-lived, charter-scoped
  - release:    promotion target, MergeGuard required
"""
from __future__ import annotations

from sylion.aeis.testing.branches.manager import BranchManager
from sylion.aeis.testing.branches.snapshot import (
    BranchSnapshot,
    DEFAULT_BASE_DIR,
    SNAPSHOT_PREFIX,
)

__all__ = [
    "BranchManager",
    "BranchSnapshot",
    "DEFAULT_BASE_DIR",
    "SNAPSHOT_PREFIX",
]
