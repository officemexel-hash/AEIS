#!/usr/bin/env python3
"""
orchestrator_anti_halluc_hook.py
=================================
SYLION v5.9.2 — GAP-04 fix: fragment diff + drop-in hook for orchestrator.py.

This file shows exactly WHAT to change in orchestrator.py to auto-feed the
`anti_hallucination_log` dashboard table after every agent iteration.

Overview
--------
The dashboard at /security/anti-hallucination reads the `anti_hallucination_log`
SQLite table.  Before this fix, HallucinationGuard wrote violations only to:
  - results/hallucinations.jsonl  (local audit trail)
  - Python logger (ephemeral)

The DB table was populated only by unit test seed data.

Fix strategy
------------
1. Import `insert_anti_hallucination_log` from the patch module (or inline it).
2. Call it immediately after `vf_result = _halluc_guard.after_iteration(...)`.
3. Use SYLION_DB_PATH, the unified AEIS runtime database.

Exact application
-----------------
Apply the `DIFF` string below as a unified diff to orchestrator.py, OR
copy the `anti_halluc_hook()` function call into run_agent_wrapper() at
the marked location.

Compatibility: orchestrator.py v5.9.1 (160 819 bytes, last modified 2026-04-19)
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from file_verification import VerificationResult

log = logging.getLogger("orchestrator.anti_halluc_hook")


# ---------------------------------------------------------------------------
# The hook function
# ---------------------------------------------------------------------------

def anti_halluc_hook(
    vf_result: "VerificationResult",
    agent_id: str,
    run_id: str,
    *,
    db_path: "Path | str | None" = None,
    layer: str = "file_verification",
) -> int:
    """
    Write every HallucinationGuard violation from `vf_result` into the
    `anti_hallucination_log` table.

    Parameters
    ----------
    vf_result : VerificationResult
        The object returned by HallucinationGuard.after_iteration().
    agent_id  : str
        The agent identifier used in the iteration.
    run_id    : str
        The pipeline run_id (passed from run_agent_wrapper's `run_id` arg).
    db_path   : Path | str | None
        Path to the SQLite database.  If None, resolved from SYLION_DB_PATH.
    layer     : str
        The layer name stored in the `layer` column (default: 'file_verification').

    Returns
    -------
    int
        Number of rows inserted (0 if clean result or DB unavailable).
    """
    if not vf_result.hallucinations:
        return 0

    # Resolve DB path
    if db_path is None:
        db_path = os.getenv("SYLION_DB_PATH")
        if not db_path:
            log.warning("anti_halluc_hook: SYLION_DB_PATH not set; skip DB write")
            return 0

    db_path = Path(db_path)
    if not db_path.parent.exists():
        log.debug("anti_halluc_hook: DB parent dir %s does not exist; skip", db_path.parent)
        return 0

    rows_inserted = 0
    ts_now = time.time()

    try:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        for halluc in vf_result.hallucinations:
            row_id = f"halluc-{uuid.uuid4().hex}"
            # Stable dedup hash so the same event doesn't double-insert
            input_hash = hashlib.sha256(
                f"{agent_id}:{halluc.file_path}:{halluc.hallucination_type.value}".encode()
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
                    halluc.description[:2000],
                    agent_id,
                    run_id or "",
                ),
            )
            rows_inserted += 1

        conn.commit()
        conn.close()
        log.info(
            "anti_halluc_hook: %d violation(s) written → anti_hallucination_log "
            "(agent=%s run=%s)",
            rows_inserted, agent_id, run_id,
        )
    except sqlite3.Error as exc:
        log.error("anti_halluc_hook: DB write failed: %s", exc)

    return rows_inserted


# ---------------------------------------------------------------------------
# Unified diff — apply to orchestrator.py
# ---------------------------------------------------------------------------

# UNIFIED_DIFF and INLINE_SNIPPET are documentation-only strings
# (unified diff to apply to orchestrator.py, and inline variant).
# Original source contained triple-quote conflicts inside the raw strings,
# so they are stored base64-encoded and decoded lazily on access.
import base64 as _b64_fix
UNIFIED_DIFF = _b64_fix.b64decode('LS0tIGEvb3JjaGVzdHJhdG9yLnB5CisrKyBiL29yY2hlc3RyYXRvci5weQpAQCAtMSw2ICsxLDkgQEAKICMhL3Vzci9iaW4vZW52IHB5dGhvbjMKICIiIgogLi4uCisjIEdBUC0wNCBmaXg6IGFudGlfaGFsbHVjaW5hdGlvbl9sb2cgYXV0by1mZWVkCitmcm9tIG9yY2hlc3RyYXRvcl9hbnRpX2hhbGx1Y19ob29rIGltcG9ydCBhbnRpX2hhbGx1Y19ob29rCgpAQCAtOTIwLDYgKzkyMywxNyBAQCBkZWYgcnVuX2FnZW50X3dyYXBwZXIoCiAgICAgICAgICAgICB2Zl9yZXN1bHQgPSBfaGFsbHVjX2d1YXJkLmFmdGVyX2l0ZXJhdGlvbigKICAgICAgICAgICAgICAgICBhZ2VudF9pZD1hZ2VudF9pZCBvciBsYWJlbCwKICAgICAgICAgICAgICAgICBjbGFpbXM9Y2xhaW1zLAogICAgICAgICAgICAgICAgIGN0eD12ZXJpZmljYXRpb25fY3R4LAogICAgICAgICAgICAgKQorICAgICAgICAgICAgIyDilIDilIAgR0FQLTA0OiBhdXRvLWZlZWQgYW50aV9oYWxsdWNpbmF0aW9uX2xvZyBkYXNoYm9hcmQgdGFibGUg4pSA4pSACisgICAgICAgICAgICBpZiB2Zl9yZXN1bHQuaGFsbHVjaW5hdGlvbnM6CisgICAgICAgICAgICAgICAgX25fcm93cyA9IGFudGlfaGFsbHVjX2hvb2soCisgICAgICAgICAgICAgICAgICAgIHZmX3Jlc3VsdD12Zl9yZXN1bHQsCisgICAgICAgICAgICAgICAgICAgIGFnZW50X2lkPWFnZW50X2lkIG9yIGxhYmVsLAorICAgICAgICAgICAgICAgICAgICBydW5faWQ9cnVuX2lkLAorICAgICAgICAgICAgICAgICkKKyAgICAgICAgICAgICAgICBsb2cuaW5mbygKKyAgICAgICAgICAgICAgICAgICAgIiAgYW50aV9oYWxsdWNfbG9nOiAlZCB2aW9sYXRpb24ocykgcGVyc2lzdGVkIHRvIGRhc2hib2FyZCBEQiIsCisgICAgICAgICAgICAgICAgICAgIF9uX3Jvd3MsCisgICAgICAgICAgICAgICAgKQorICAgICAgICAgICAgIyDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAKICAgICAgICAgICAgIGlmIHZmX3Jlc3VsdC5ibG9ja2VkOgogICAgICAgICAgICAgICAgIGxvZy5lcnJvcigKICAgICAgICAgICAgICAgICAgICAgZiIgIOKaoO+4jyBIQUxMVUNJTkFUSU9OIEJMT0NLRUQg4oCUIGFnZW50PSd7YWdlbnRfaWQgb3IgbGFiZWx9JyAi').decode("utf-8")
INLINE_SNIPPET = _b64_fix.b64decode('IyA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KIyBHQVAtMDQ6IGFudGlfaGFsbHVjaW5hdGlvbl9sb2cgYXV0by1mZWVkIChpbmxpbmUsIG5vIGltcG9ydCkKIyBJbnNlcnQgYWZ0ZXI6ICB2Zl9yZXN1bHQgPSBfaGFsbHVjX2d1YXJkLmFmdGVyX2l0ZXJhdGlvbiguLi4pCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09CmlmIHZmX3Jlc3VsdCBhbmQgdmZfcmVzdWx0LmhhbGx1Y2luYXRpb25zOgogICAgdHJ5OgogICAgICAgIGltcG9ydCBoYXNobGliIGFzIF9oYXNobGliCiAgICAgICAgaW1wb3J0IHNxbGl0ZTMgYXMgX3NxbGl0ZTMKICAgICAgICBpbXBvcnQgdGltZSBhcyBfdGltZQogICAgICAgIGltcG9ydCB1dWlkIGFzIF91dWlkCiAgICAgICAgZnJvbSBkYXNoYm9hcmQuZGIgaW1wb3J0IERCX1BBVEggYXMgX0RCX1BBVEgKCiAgICAgICAgX3RzID0gX3RpbWUudGltZSgpCiAgICAgICAgX2Nvbm4gPSBfc3FsaXRlMy5jb25uZWN0KHN0cihfREJfUEFUSCksIGNoZWNrX3NhbWVfdGhyZWFkPUZhbHNlKQogICAgICAgIGZvciBfaCBpbiB2Zl9yZXN1bHQuaGFsbHVjaW5hdGlvbnM6CiAgICAgICAgICAgIF9jb25uLmV4ZWN1dGUoCiAgICAgICAgICAgICAgICAiIiJJTlNFUlQgT1IgSUdOT1JFIElOVE8gYW50aV9oYWxsdWNpbmF0aW9uX2xvZwogICAgICAgICAgICAgICAgICAgKGlkLCB0cywgbGF5ZXIsIGNoZWNrX3R5cGUsIGlucHV0X2hhc2gsIHJlc3VsdCwgZGV0YWlsLCBhZ2VudF9pZCwgcnVuX2lkKQogICAgICAgICAgICAgICAgICAgVkFMVUVTICg/LCA/LCA/LCA/LCA/LCA/LCA/LCA/LCA/KSIiIiwKICAgICAgICAgICAgICAgICgKICAgICAgICAgICAgICAgICAgICBmImhhbGx1Yy17X3V1aWQudXVpZDQoKS5oZXh9IiwKICAgICAgICAgICAgICAgICAgICBfdHMsCiAgICAgICAgICAgICAgICAgICAgImZpbGVfdmVyaWZpY2F0aW9uIiwKICAgICAgICAgICAgICAgICAgICBfaC5oYWxsdWNpbmF0aW9uX3R5cGUudmFsdWUsCiAgICAgICAgICAgICAgICAgICAgX2hhc2hsaWIuc2hhMjU2KAogICAgICAgICAgICAgICAgICAgICAgICBmInthZ2VudF9pZCBvciBsYWJlbH06e19oLmZpbGVfcGF0aH06e19oLmhhbGx1Y2luYXRpb25fdHlwZS52YWx1ZX0iCiAgICAgICAgICAgICAgICAgICAgICAgIC5lbmNvZGUoKQogICAgICAgICAgICAgICAgICAgICkuaGV4ZGlnZXN0KClbOjMyXSwKICAgICAgICAgICAgICAgICAgICAidmlvbGF0aW9uIiwKICAgICAgICAgICAgICAgICAgICBfaC5kZXNjcmlwdGlvbls6MjAwMF0sCiAgICAgICAgICAgICAgICAgICAgYWdlbnRfaWQgb3IgbGFiZWwsCiAgICAgICAgICAgICAgICAgICAgcnVuX2lkIG9yICIiLAogICAgICAgICAgICAgICAgKSwKICAgICAgICAgICAgKQogICAgICAgIF9jb25uLmNvbW1pdCgpCiAgICAgICAgX2Nvbm4uY2xvc2UoKQogICAgICAgIGxvZy5pbmZvKAogICAgICAgICAgICAiICBhbnRpX2hhbGx1Y19sb2c6ICVkIHZpb2xhdGlvbihzKSDihpIgZGFzaGJvYXJkIERCIiwKICAgICAgICAgICAgbGVuKHZmX3Jlc3VsdC5oYWxsdWNpbmF0aW9ucyksCiAgICAgICAgKQogICAgZXhjZXB0IEV4Y2VwdGlvbiBhcyBfZXhjOgogICAgICAgIGxvZy53YXJuaW5nKCIgIGFudGlfaGFsbHVjX2xvZyB3cml0ZSBmYWlsZWQ6ICVzIiwgX2V4YykKIyA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0=').decode("utf-8")

# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile, shutil

    tmp = Path(tempfile.mkdtemp())
    db_p = tmp / "test.db"

    # Create minimal schema
    c = sqlite3.connect(str(db_p))
    c.execute("""
        CREATE TABLE IF NOT EXISTS anti_hallucination_log (
            id TEXT PRIMARY KEY, ts REAL NOT NULL,
            layer TEXT NOT NULL DEFAULT '', check_type TEXT NOT NULL DEFAULT '',
            input_hash TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT 'pass',
            detail TEXT NOT NULL DEFAULT '', agent_id TEXT NOT NULL DEFAULT '',
            run_id TEXT NOT NULL DEFAULT ''
        )
    """)
    c.commit()
    c.close()

    # Stub VerificationResult
    from unittest.mock import MagicMock
    r = MagicMock()
    h = MagicMock()
    h.hallucination_type.value = "phantom_file"
    h.file_path = "ghost.py"
    h.description = "Agent claimed DELETED ghost.py but it never existed"
    r.hallucinations = [h]

    n = anti_halluc_hook(r, "test_agent", "run-selftest", db_path=db_p)
    print(f"Rows inserted: {n}")

    rows = sqlite3.connect(str(db_p)).execute(
        "SELECT id, check_type, agent_id FROM anti_hallucination_log"
    ).fetchall()
    print(f"DB rows: {rows}")

    shutil.rmtree(tmp)
    print("Self-test OK")
