#!/usr/bin/env python3
"""
book_guardian_rebase.py — SYLION BookGuardian Authorized Rebase Tool
======================================================================

CLI tool for performing an authorized baseline update of Księga SYLION 3.4 FIXED.
This is the ONLY approved mechanism for updating the BookGuardian baseline.

Usage:
    python book_guardian_rebase.py \\
        --authorize-by "admin@sylion.local" \\
        --reason "v5.9.2 corrections" \\
        [--ksiega-path path/to/Ksiega.docx] \\
        [--db-path path/to/sylion_aeis.db] \\
        [--log-dir path/to/log/dir] \\
        [--dry-run]

Authorization requirements:
    - File ~/sylion/REBASE_AUTHORIZED must exist
    - File must contain: TOKEN=<value> on first line, TS=<unix_epoch> on second line
    - Token must be a non-empty hex string (min 32 chars)
    - Timestamp must be within 10 minutes of NOW (UTC)

Flow:
    1. Validate REBASE_AUTHORIZED flag file
    2. Compute new SHA-256 of Księga
    3. Show diff (old SHA → new SHA) and require HumanGate y/n prompt
    4. If confirmed: write new baseline to disk + audit_log + DB
    5. Print final summary with new SHA

Security invariants:
    - NEVER auto-approves without explicit human input
    - Authorization flag expires after 10 minutes
    - Every rebase is appended to audit_log.jsonl (non-truncating)
    - DB record links rebase event to authorized_by + reason + timestamp

Fixes:
    - TODO-01 from TF03: book_guardian_rebase.py was missing from repository
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AUTH_FLAG_PATH = Path.home() / "sylion" / "REBASE_AUTHORIZED"
AUTH_MAX_AGE_SEC = 600  # 10 minutes

DEFAULT_KSIEGA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "latest" / "sylion-pipeline"
    / "workspace_uploads" / "ksiega"
)
DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "latest" / "sylion-pipeline" / "sylion_aeis.db"
)
DEFAULT_LOG_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "latest" / "sylion-pipeline" / "results" / "book_guardian"
)

_HASH_BUF_SIZE = 65536


# ---------------------------------------------------------------------------
# Auth-flag validation
# ---------------------------------------------------------------------------

class RebaseAuthError(Exception):
    """Raised when REBASE_AUTHORIZED flag is missing, expired, or malformed."""


def validate_auth_flag(flag_path: Path = AUTH_FLAG_PATH) -> tuple[str, float]:
    """
    Validate the REBASE_AUTHORIZED flag file.

    Expected file format:
        TOKEN=<hex_string_min_32_chars>
        TS=<unix_epoch_float>

    Returns:
        (token, issued_at_ts) on success.

    Raises:
        RebaseAuthError on any failure.
    """
    if not flag_path.exists():
        raise RebaseAuthError(
            f"Authorization flag not found: {flag_path}\n"
            f"Create it with:\n"
            f"  mkdir -p {flag_path.parent}\n"
            f"  echo 'TOKEN=$(openssl rand -hex 32)' >> {flag_path}\n"
            f"  echo 'TS=$(date +%s)' >> {flag_path}"
        )

    try:
        content = flag_path.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise RebaseAuthError(f"Cannot read authorization flag: {e}") from e

    lines = {
        k.strip(): v.strip()
        for line in content.splitlines()
        if "=" in line
        for k, v in [line.split("=", 1)]
    }

    if "TOKEN" not in lines:
        raise RebaseAuthError("Authorization flag malformed: missing TOKEN= field")
    if "TS" not in lines:
        raise RebaseAuthError("Authorization flag malformed: missing TS= field")

    token = lines["TOKEN"]
    if len(token) < 32 or not all(c in "0123456789abcdefABCDEF" for c in token):
        raise RebaseAuthError(
            f"Authorization token invalid: must be a hex string of ≥32 chars, got: {token[:16]}..."
        )

    try:
        issued_at = float(lines["TS"])
    except ValueError as e:
        raise RebaseAuthError(f"Authorization flag TS= is not a valid timestamp: {lines['TS']}") from e

    age_sec = time.time() - issued_at
    if age_sec < 0:
        raise RebaseAuthError(
            f"Authorization flag timestamp is in the future ({-age_sec:.0f}s ahead). "
            f"Check system clock."
        )
    if age_sec > AUTH_MAX_AGE_SEC:
        raise RebaseAuthError(
            f"Authorization flag expired: issued {age_sec:.0f}s ago "
            f"(max {AUTH_MAX_AGE_SEC}s = 10 minutes). "
            f"Re-issue a fresh flag."
        )

    return token, issued_at


# ---------------------------------------------------------------------------
# SHA-256 computation
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    """Compute SHA-256 of a file in 64KB chunks. Raises FileNotFoundError if missing."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_HASH_BUF_SIZE):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Disk persistence
# ---------------------------------------------------------------------------

def load_existing_baseline(log_dir: Path) -> dict | None:
    """Load existing baseline.json if it exists, else return None."""
    baseline_file = log_dir / "baseline.json"
    if not baseline_file.exists():
        return None
    try:
        with open(baseline_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def write_baseline_to_disk(
    log_dir: Path,
    ksiega_path: Path,
    new_sha: str,
    size_bytes: int,
    mtime: float,
) -> Path:
    """Write new baseline.json to log_dir. Returns path written."""
    log_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = log_dir / "baseline.json"
    payload = {
        "file_path": str(ksiega_path),
        "sha256": new_sha,
        "size_bytes": size_bytes,
        "mtime": mtime,
        "exists": True,
        "snapshot_time": datetime.now(timezone.utc).isoformat(),
    }
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return baseline_path


def append_audit_log(
    log_dir: Path,
    authorized_by: str,
    reason: str,
    old_sha: str | None,
    new_sha: str,
    token_prefix: str,
    issued_at: float,
) -> Path:
    """Append a rebase event to audit_log.jsonl. Returns path written."""
    log_dir.mkdir(parents=True, exist_ok=True)
    audit_path = log_dir / "audit_log.jsonl"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_id": "book_guardian_rebase",
        "action": "rebase_baseline",
        "details": {
            "authorized_by": authorized_by,
            "reason": reason,
            "old_sha": old_sha,
            "new_sha": new_sha,
            "auth_token_prefix": token_prefix[:8] + "...",
            "auth_issued_at": datetime.fromtimestamp(issued_at, tz=timezone.utc).isoformat(),
        },
    }
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return audit_path


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

def write_rebase_to_db(
    db_path: Path,
    authorized_by: str,
    reason: str,
    new_sha: str,
    ksiega_path: Path,
) -> bool:
    """
    Insert a promoted baseline record + audit event into the DB.

    Returns True on success, False if DB not available (non-fatal).
    """
    if not db_path.exists():
        print(f"  [WARN] DB not found at {db_path} — skipping DB write (non-fatal)")
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")

        # Demote previous promoted baselines
        conn.execute(
            "UPDATE baselines SET status='superseded' WHERE status='promoted'"
        )

        # Insert new promoted baseline
        ts_now = time.time()
        conn.execute(
            """
            INSERT INTO baselines (name, content, sha256, file_path, status, created_at, promoted_at)
            VALUES (?, ?, ?, ?, 'promoted', ?, ?)
            """,
            (
                f"rebase_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}",
                f"Rebase by {authorized_by}: {reason}",
                new_sha,
                str(ksiega_path),
                ts_now,
                ts_now,
            ),
        )

        # Append to audit_log table if it exists
        try:
            conn.execute(
                """
                INSERT INTO audit_log (action, actor, details, ts)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "rebase_baseline",
                    authorized_by,
                    json.dumps({"reason": reason, "new_sha": new_sha, "ksiega_path": str(ksiega_path)}),
                    ts_now,
                ),
            )
        except sqlite3.OperationalError:
            pass  # audit_log table may not exist — non-fatal

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"  [WARN] DB write failed: {e} — continuing without DB record")
        return False


# ---------------------------------------------------------------------------
# HumanGate prompt
# ---------------------------------------------------------------------------

def human_gate_prompt(old_sha: str | None, new_sha: str, ksiega_path: Path, authorized_by: str, reason: str) -> bool:
    """
    Display a clear summary and require explicit y/n confirmation.

    Returns True if operator confirmed, False if aborted.
    """
    print()
    print("=" * 70)
    print("  HUMAN GATE — SYLION BookGuardian Rebase Authorization")
    print("=" * 70)
    print(f"  Authorized by : {authorized_by}")
    print(f"  Reason        : {reason}")
    print(f"  Księga file   : {ksiega_path}")
    print(f"  Old SHA-256   : {old_sha or '(none — no existing baseline)'}")
    print(f"  New SHA-256   : {new_sha}")
    print()
    print("  This operation will:")
    print("    1. Update the BookGuardian baseline SHA on disk")
    print("    2. Mark new baseline as 'promoted' in DB")
    print("    3. Append audit entry to audit_log.jsonl")
    print()
    print("  WARNING: After rebase, BookGuardian will accept the new SHA as")
    print("  the normative baseline. Previous drift alerts will be resolved.")
    print("=" * 70)
    print()

    try:
        answer = input("  Confirm rebase? [y/N] ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\n  Aborted by user.")
        return False

    if answer != "y":
        print("  Rebase cancelled.")
        return False

    return True


# ---------------------------------------------------------------------------
# Main rebase flow
# ---------------------------------------------------------------------------

def run_rebase(
    authorized_by: str,
    reason: str,
    ksiega_path: Path,
    db_path: Path,
    log_dir: Path,
    dry_run: bool = False,
    flag_path: Path = AUTH_FLAG_PATH,
    skip_prompt: bool = False,  # for testing only
) -> int:
    """
    Execute the full rebase flow.

    Returns:
        0 — success
        1 — authorization failure
        2 — operator cancelled
        3 — Księga file not found
        4 — unexpected error
    """
    print(f"[BookGuardian Rebase] v5.9.2")
    print(f"[BookGuardian Rebase] Started: {datetime.now(timezone.utc).isoformat()}")
    print()

    # Step 1: Validate authorization flag
    print("[Step 1/4] Validating authorization flag...")
    try:
        token, issued_at = validate_auth_flag(flag_path)
        age_sec = time.time() - issued_at
        print(f"  OK — Token valid, issued {age_sec:.0f}s ago (max {AUTH_MAX_AGE_SEC}s)")
        print(f"  Token prefix: {token[:8]}...")
    except RebaseAuthError as e:
        print(f"\n  [AUTH ERROR] {e}")
        return 1

    # Step 2: Find Księga and compute new SHA
    print("\n[Step 2/4] Computing new SHA-256 of Księga...")

    # If ksiega_path is a directory, find the most recent file
    actual_ksiega = ksiega_path
    if ksiega_path.is_dir():
        candidates = sorted(
            [
                f for f in ksiega_path.iterdir()
                if f.is_file() and f.suffix.lower() in (".docx", ".pdf", ".md", ".txt")
                and f.name != "test_upload.txt"
            ],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            # Fallback: any file
            candidates = [f for f in ksiega_path.iterdir() if f.is_file()]
        if candidates:
            actual_ksiega = candidates[0]
        else:
            print(f"  [ERROR] No files found in Księga directory: {ksiega_path}")
            return 3

    if not actual_ksiega.exists() or not actual_ksiega.is_file():
        print(f"  [ERROR] Księga file not found: {actual_ksiega}")
        return 3

    try:
        stat = actual_ksiega.stat()
        new_sha = sha256_file(actual_ksiega)
        size_bytes = stat.st_size
        mtime = stat.st_mtime
        print(f"  File  : {actual_ksiega}")
        print(f"  Size  : {size_bytes:,} bytes")
        print(f"  SHA   : {new_sha}")
    except OSError as e:
        print(f"  [ERROR] Cannot read Księga: {e}")
        return 4

    # Load existing baseline for comparison
    existing = load_existing_baseline(log_dir)
    old_sha = existing.get("sha256") if existing else None

    if old_sha == new_sha:
        print("\n  [INFO] New SHA matches existing baseline — no change needed.")
        print("  If you intended to reset, verify that Księga was actually modified.")
        return 0

    # Step 3: HumanGate prompt
    print("\n[Step 3/4] Requiring operator confirmation (HumanGate)...")
    if not skip_prompt:
        confirmed = human_gate_prompt(old_sha, new_sha, actual_ksiega, authorized_by, reason)
        if not confirmed:
            return 2
    else:
        print("  [SKIP] HumanGate prompt bypassed (testing mode)")

    if dry_run:
        print("\n[DRY RUN] Would write:")
        print(f"  baseline.json → {log_dir / 'baseline.json'}")
        print(f"  audit_log.jsonl → {log_dir / 'audit_log.jsonl'}")
        print(f"  DB promoted baseline → {db_path}")
        print("\n[DRY RUN] No files written.")
        return 0

    # Step 4: Commit rebase
    print("\n[Step 4/4] Committing rebase...")

    baseline_path = write_baseline_to_disk(log_dir, actual_ksiega, new_sha, size_bytes, mtime)
    print(f"  OK — baseline.json written: {baseline_path}")

    audit_path = append_audit_log(
        log_dir, authorized_by, reason, old_sha, new_sha,
        token, issued_at,
    )
    print(f"  OK — audit_log.jsonl updated: {audit_path}")

    db_ok = write_rebase_to_db(db_path, authorized_by, reason, new_sha, actual_ksiega)
    if db_ok:
        print(f"  OK — DB baseline promoted: {db_path}")

    print()
    print("=" * 70)
    print("  REBASE COMPLETE")
    print(f"  New baseline SHA : {new_sha}")
    print(f"  Authorized by   : {authorized_by}")
    print(f"  Reason          : {reason}")
    print(f"  Timestamp       : {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)
    print()
    print("  BookGuardian will now accept the new SHA as the normative baseline.")
    print("  Restart the pipeline to pick up the updated baseline if it is")
    print("  currently running with an in-memory BookGuardian instance.")
    print()

    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="book_guardian_rebase.py",
        description="SYLION BookGuardian authorized rebase tool — updates Księga baseline SHA.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python book_guardian_rebase.py \\
      --authorize-by "admin@sylion.local" \\
      --reason "v5.9.2 corrections"

  python book_guardian_rebase.py \\
      --authorize-by "admin@sylion.local" \\
      --reason "emergency patch" \\
      --ksiega-path /custom/path/Ksiega.docx \\
      --dry-run

Authorization setup:
  mkdir -p ~/sylion
  echo "TOKEN=$(openssl rand -hex 32)" > ~/sylion/REBASE_AUTHORIZED
  echo "TS=$(date +%s)" >> ~/sylion/REBASE_AUTHORIZED
        """,
    )
    p.add_argument(
        "--authorize-by",
        required=True,
        metavar="EMAIL",
        help="Email or ID of the authorizing operator (e.g. admin@sylion.local)",
    )
    p.add_argument(
        "--reason",
        required=True,
        metavar="TEXT",
        help="Human-readable reason for the rebase (e.g. 'v5.9.2 corrections')",
    )
    p.add_argument(
        "--ksiega-path",
        default=str(DEFAULT_KSIEGA_PATH),
        metavar="PATH",
        help=f"Path to Księga file or directory (default: {DEFAULT_KSIEGA_PATH})",
    )
    p.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        metavar="PATH",
        help=f"Path to sylion_aeis.db (default: {DEFAULT_DB_PATH})",
    )
    p.add_argument(
        "--log-dir",
        default=str(DEFAULT_LOG_DIR),
        metavar="PATH",
        help=f"Path to BookGuardian log directory (default: {DEFAULT_LOG_DIR})",
    )
    p.add_argument(
        "--flag-path",
        default=str(AUTH_FLAG_PATH),
        metavar="PATH",
        help=f"Path to REBASE_AUTHORIZED flag file (default: {AUTH_FLAG_PATH})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be done without writing any files",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.authorize_by.strip():
        print("[ERROR] --authorize-by cannot be empty")
        return 1
    if not args.reason.strip():
        print("[ERROR] --reason cannot be empty")
        return 1

    return run_rebase(
        authorized_by=args.authorize_by.strip(),
        reason=args.reason.strip(),
        ksiega_path=Path(args.ksiega_path),
        db_path=Path(args.db_path),
        log_dir=Path(args.log_dir),
        dry_run=args.dry_run,
        flag_path=Path(args.flag_path),
    )


if __name__ == "__main__":
    sys.exit(main())
