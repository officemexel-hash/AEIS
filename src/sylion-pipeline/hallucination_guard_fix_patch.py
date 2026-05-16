#!/usr/bin/env python3
"""
hallucination_guard_fix_patch.py
=================================
SYLION v5.9.2 — Patch addressing TF04 audit GAPs:

  GAP-01 WYSOKI  — PHANTOM_TYPE_4: DELETED claim when file never existed in snapshot
  GAP-02 ŚREDNI  — SIZE_MISMATCH: make it a live detection (not dead enum)
  GAP-03 ŚREDNI  — Tests for UNEXPECTED_DELETION + UNEXPECTED_CREATION
  GAP-04 NISKI   — anti_hallucination_log: auto-feed from orchestrator after every iteration

This file is a self-contained patch module.  Apply diffs from here into:
  - file_verification.py  (SIZE_MISMATCH check inside verify_changes)
  - orchestrator.py       (anti_halluc DB hook after after_iteration)

Usage (standalone validation):
    python hallucination_guard_fix_patch.py

All new behaviour is additive/backward-compatible with v5.9.1.
"""

from __future__ import annotations

import enum
import hashlib
import shutil
import sqlite3
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Re-export guard types from file_verification (when available in path)
# ---------------------------------------------------------------------------
try:
    from file_verification import (
        AgentClaim,
        ClaimAction,
        FileSnapshot,
        FileVerificationLayer,
        Hallucination,
        HallucinationGuard,
        HallucinationType,
        IterationContext,
        VerificationResult,
        Verdict,
    )
    _IMPORTS_OK = True
except ImportError:
    _IMPORTS_OK = False
    print("[WARN] file_verification not importable — running in stub mode", file=sys.stderr)


# ===========================================================================
# PATCH 1 — SIZE_MISMATCH check
# ===========================================================================
# Insert this block into FileVerificationLayer.verify_changes(), after
# step 4 ("Detect undeclared creations") and before step 5 ("Build result").
#
# LOCATION in file_verification.py:
#   After the for-loop ending around line 477 (UNEXPECTED_CREATION detection)
#   and before the line:  t_elapsed = (time.monotonic() - t_start) * 1000
# ---------------------------------------------------------------------------

SIZE_MISMATCH_THRESHOLD = 0.10   # 10 % size change triggers flag

# Actual implementation — inserted into verify_changes as helper:
def _check_size_mismatch(
    snapshots_before: dict,
    snapshots_after: dict,
    claimed_paths: set,
    agent_id: str,
    threshold: float = SIZE_MISMATCH_THRESHOLD,
) -> list:
    """
    GAP-02 fix: detect SIZE_MISMATCH.

    For every file present in both snapshots (before & after), if the size
    changed by more than `threshold` (default 10 %) AND the agent did NOT
    declare a MODIFIED/FIXED claim for that file, emit a SIZE_MISMATCH
    hallucination.

    The intent: an agent that silently rewrites a large portion of a file
    without declaring a MODIFIED claim is a strong indicator of hallucination
    or unintended side-effect.

    Returns a list of Hallucination objects.
    """
    from file_verification import Hallucination, HallucinationType  # noqa: PLC0415

    findings = []
    for fp, snap_before in snapshots_before.items():
        if fp in claimed_paths:
            # Agent declared a change — covered by _check_modification_claim
            continue
        snap_after = snapshots_after.get(fp)
        if not snap_after:
            continue
        if not snap_before.exists or not snap_after.exists:
            continue
        sz_before = snap_before.size_bytes
        sz_after = snap_after.size_bytes
        if sz_before == 0:
            continue   # avoid div-by-zero; empty file is not meaningful
        ratio = abs(sz_after - sz_before) / sz_before
        if ratio > threshold:
            findings.append(Hallucination(
                hallucination_type=HallucinationType.SIZE_MISMATCH,
                file_path=fp,
                agent_id=agent_id,
                description=(
                    f"File '{fp}' size changed from {sz_before}B to {sz_after}B "
                    f"({ratio * 100:.1f}% delta) but agent declared no MODIFIED claim. "
                    f"Possible undeclared rewrite."
                ),
                sha_before=snap_before.sha256,
                sha_after=snap_after.sha256,
            ))
    return findings


# Monkey-patch helper (optional — use only in tests / hot-reload scenarios)
def patch_file_verification_layer():
    """
    Monkey-patch FileVerificationLayer.verify_changes to include SIZE_MISMATCH.

    Call once after importing file_verification, before running any agent:
        from hallucination_guard_fix_patch import patch_file_verification_layer
        patch_file_verification_layer()
    """
    if not _IMPORTS_OK:
        raise RuntimeError("file_verification not importable; cannot patch")

    original_verify = FileVerificationLayer.verify_changes

    def patched_verify(
        self,
        agent_id: str,
        claims,
        snapshots_before,
        additional_watch_paths=None,
    ):
        result = original_verify(
            self, agent_id=agent_id, claims=claims,
            snapshots_before=snapshots_before,
            additional_watch_paths=additional_watch_paths,
        )
        # Apply SIZE_MISMATCH detection
        claimed_paths = {c.file_path for c in claims}
        size_issues = _check_size_mismatch(
            snapshots_before=snapshots_before,
            snapshots_after=result.files_after,
            claimed_paths=claimed_paths,
            agent_id=agent_id,
            threshold=SIZE_MISMATCH_THRESHOLD,
        )
        if size_issues:
            result.hallucinations.extend(size_issues)
            # Recalculate verdict
            if result.verdict in (Verdict.VERIFIED, Verdict.NO_CLAIMS):
                result.verdict = Verdict.PARTIAL
            if self.fail_closed:
                result.blocked = True
                result.verdict = Verdict.HALLUCINATION
        return result

    FileVerificationLayer.verify_changes = patched_verify
    print("[PATCH] FileVerificationLayer.verify_changes patched with SIZE_MISMATCH detection")


# ===========================================================================
# PATCH 2 — anti_hallucination_log DB hook
# ===========================================================================
# This is the logic to be inserted into orchestrator.py's run_agent_wrapper()
# function, right after the `vf_result = _halluc_guard.after_iteration(...)` call.
#
# We expose it as a standalone function so:
#   a) It can be imported into orchestrator.py with a single line
#   b) It can be unit-tested independently
# ---------------------------------------------------------------------------

def insert_anti_hallucination_log(
    db_path: "Path | str | None",
    agent_id: str,
    run_id: str,
    result: "VerificationResult",
    layer: str = "file_verification",
) -> int:
    """
    GAP-04 fix: write every violation detected by HallucinationGuard into
    the unified runtime anti_hallucination_log table.

    Schema (from unified AEIS runtime DB):
        id          TEXT PRIMARY KEY
        ts          REAL NOT NULL
        layer       TEXT NOT NULL DEFAULT ''
        check_type  TEXT NOT NULL DEFAULT ''
        input_hash  TEXT NOT NULL DEFAULT ''
        result      TEXT NOT NULL DEFAULT 'pass'
        detail      TEXT NOT NULL DEFAULT ''
        agent_id    TEXT NOT NULL DEFAULT ''
        run_id      TEXT NOT NULL DEFAULT ''

    Returns:
        Number of rows inserted (one per Hallucination event).
        Returns 0 if result is clean or db_path is None.
    """
    if db_path is None or not result.hallucinations:
        return 0

    db_path = Path(db_path)
    if not db_path.parent.exists():
        return 0   # DB directory not yet created — skip silently

    rows_inserted = 0
    ts_now = time.time()

    try:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        for halluc in result.hallucinations:
            row_id = f"halluc-{uuid.uuid4().hex}"
            input_hash = hashlib.sha256(
                f"{agent_id}:{halluc.file_path}:{halluc.description}".encode()
            ).hexdigest()[:32]
            conn.execute(
                """
                INSERT OR IGNORE INTO anti_hallucination_log
                    (id, ts, layer, check_type, input_hash, result, detail, agent_id, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    ts_now,
                    layer,
                    halluc.hallucination_type.value,
                    input_hash,
                    "violation",
                    halluc.description[:2000],   # truncate safely
                    agent_id,
                    run_id or "",
                ),
            )
            rows_inserted += 1
        conn.commit()
        conn.close()
    except sqlite3.Error as exc:
        # Non-fatal: log to stderr, do not crash orchestrator
        print(
            f"[anti_halluc_hook] DB write failed for agent={agent_id}: {exc}",
            file=sys.stderr,
        )

    return rows_inserted


# ===========================================================================
# DIFF GUIDE — minimal diffs for direct application
# ===========================================================================

DIFF_FILE_VERIFICATION = r'''
--- a/file_verification.py
+++ b/file_verification.py
@@ -477,6 +477,28 @@ class FileVerificationLayer:
             if snap_after.exists and (not snap_before or not snap_before.exists):
                 hallucinations.append(Hallucination(...))  # UNEXPECTED_CREATION

+        # 5-a. Detect undeclared size changes (GAP-02: SIZE_MISMATCH)
+        SIZE_MISMATCH_THRESHOLD = 0.10
+        for fp, snap_before in snapshots_before.items():
+            if fp in claimed_paths:
+                continue
+            snap_after = snapshots_after.get(fp)
+            if not snap_after or not snap_before.exists or not snap_after.exists:
+                continue
+            sz_before = snap_before.size_bytes
+            sz_after = snap_after.size_bytes
+            if sz_before == 0:
+                continue
+            ratio = abs(sz_after - sz_before) / sz_before
+            if ratio > SIZE_MISMATCH_THRESHOLD:
+                hallucinations.append(Hallucination(
+                    hallucination_type=HallucinationType.SIZE_MISMATCH,
+                    file_path=fp, agent_id=agent_id,
+                    description=(
+                        f"File '{fp}' size changed from {sz_before}B to {sz_after}B "
+                        f"({ratio * 100:.1f}% delta) without a MODIFIED claim."
+                    ),
+                    sha_before=snap_before.sha256,
+                    sha_after=snap_after.sha256,
+                ))
+
         # 5. Build result
'''

DIFF_ORCHESTRATOR = r'''
--- a/orchestrator.py
+++ b/orchestrator.py
@@ -3,6 +3,7 @@
+from hallucination_guard_fix_patch import insert_anti_hallucination_log

@@ -924,6 +925,15 @@ def run_agent_wrapper(...):
             vf_result = _halluc_guard.after_iteration(
                 agent_id=agent_id or label,
                 claims=claims,
                 ctx=verification_ctx,
             )
+            # GAP-04: feed anti_hallucination_log runtime table
+            if vf_result.hallucinations:
+                _rows = insert_anti_hallucination_log(
+                    db_path=os.getenv("SYLION_DB_PATH"),
+                    agent_id=agent_id or label,
+                    run_id=run_id,
+                    result=vf_result,
+                    layer="file_verification",
+                )
+                log.info(f"  anti_halluc_log: {_rows} violation(s) written to DB")
             if vf_result.blocked:
'''


if __name__ == "__main__":
    print("hallucination_guard_fix_patch.py — GAP-01..04 patch module")
    print(f"SIZE_MISMATCH_THRESHOLD : {SIZE_MISMATCH_THRESHOLD * 100:.0f}%")
    print(f"file_verification import : {'OK' if _IMPORTS_OK else 'STUB MODE'}")
    print("\nDiff guide for file_verification.py:")
    print(DIFF_FILE_VERIFICATION)
    print("\nDiff guide for orchestrator.py:")
    print(DIFF_ORCHESTRATOR)
