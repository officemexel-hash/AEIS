"""SYLION AEIS v2 — tamper-evident audit chain.

Sprint 2 day 6 deliverable per Kimi review k4_gdpr_audit_chain_integrity:
plain JSONL append makes audit logs vulnerable to deletion / mutation
on disk. This package adds a hash-chain on top of the JSONL format so
the DPO (or any auditor) can verify the chain's integrity and pinpoint
the exact tampered row.

Format (one JSON object per line):

    {"prev_hash": "<16hex>", "content": {...}, "content_hash": "<16hex>"}

    content_hash = sha256(prev_hash + json.dumps(content, sort_keys=True))[:16]

    The first line uses ``prev_hash = "0000000000000000"`` (the genesis
    block). Each subsequent line's ``prev_hash`` is the previous line's
    ``content_hash``, so any single-line tamper invalidates every line
    after it.

Public API:

    * :func:`append_to_chain` — atomically append a content dict to a
      chain JSONL file, computing the new content_hash from the
      previous tail.
    * :func:`verify_chain` — walk a chain JSONL, return a list of
      :class:`Tampered` rows (empty list ↔ chain is intact).
    * :class:`AuditChainEntry` — the on-disk row dataclass.
    * :class:`Tampered` — a verification fault report.

Usage by other v2 modules: replace the existing
``open(path, "a") + write(json.dumps(...))`` patterns in
``gdpr_v2/dsr.py``, ``replay_v2/fork.py``, ``council_v2/wedge.py`` with
``append_to_chain(path, content)``. The migration is a separate commit
(sprint 2 day 6 step 2).
"""

from sylion.aeis_v2.audit_chain.chain import (
    GENESIS_HASH,
    AuditChainEntry,
    Tampered,
    append_to_chain,
    check_chain_replay_consistency,
    compute_content_hash,
    invalidate_last_hash_cache,
    reset_last_hash_cache,
    verify_chain,
)
from sylion.aeis_v2.audit_chain.rotator import (
    DEFAULT_RETAIN_DAYS,
    DEFAULT_SIZE_MB_THRESHOLD,
    AuditRotator,
    EvictionReport,
    RotationDecision,
)

__all__ = [
    "AuditChainEntry",
    "AuditRotator",
    "DEFAULT_RETAIN_DAYS",
    "DEFAULT_SIZE_MB_THRESHOLD",
    "EvictionReport",
    "GENESIS_HASH",
    "RotationDecision",
    "Tampered",
    "append_to_chain",
    "check_chain_replay_consistency",
    "compute_content_hash",
    "invalidate_last_hash_cache",
    "reset_last_hash_cache",
    "verify_chain",
]
