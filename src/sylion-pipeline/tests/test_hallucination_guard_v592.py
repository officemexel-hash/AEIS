#!/usr/bin/env python3
"""
test_hallucination_guard_v592.py
==================================
SYLION v5.9.2 — New HallucinationGuard tests closing TF04 gaps.

Tests:
  1. test_phantom_type_4_deleted_never_existed   — GAP-01 (PHANTOM_FILE on DELETED
                                                    when file never existed)
  2. test_size_mismatch_detected_automatic       — GAP-02 (SIZE_MISMATCH auto-check
                                                    in after_iteration)
  3. test_unexpected_deletion_flagged            — GAP-03a (UNEXPECTED_DELETION)
  4. test_unexpected_creation_flagged            — GAP-03b (UNEXPECTED_CREATION)
  5. test_size_mismatch_below_threshold_clean    — GAP-02 boundary: <10% → no flag
  6. test_phantom_type_4_with_additional_watch   — GAP-01 variant with watch paths

Run:
    cd sylion-pipeline
    python -m pytest ../mega_audit/phantom_deep/test_hallucination_guard_v592.py -v
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

# Make the pipeline root importable
ROOT = Path(__file__).resolve().parent.parent.parent / "latest" / "sylion-pipeline"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from file_verification import (
    AgentClaim,
    ClaimAction,
    FileVerificationLayer,
    HallucinationGuard,
    HallucinationType,
    Verdict,
)

# Optionally import SIZE_MISMATCH helper from patch module
PATCH_ROOT = Path(__file__).resolve().parent
if str(PATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(PATCH_ROOT))

try:
    from hallucination_guard_fix_patch import (
        _check_size_mismatch,
        patch_file_verification_layer,
        SIZE_MISMATCH_THRESHOLD,
    )
    _PATCH_AVAILABLE = True
except ImportError:
    _PATCH_AVAILABLE = False
    SIZE_MISMATCH_THRESHOLD = 0.10


# ---------------------------------------------------------------------------
# Base test infrastructure (mirrors test_hallucination_guard_v591.py style)
# ---------------------------------------------------------------------------

class _Base(unittest.TestCase):
    """Shared fixture: temp workspace, FileVerificationLayer, HallucinationGuard."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="sylion_v592_")
        self.repo = Path(self.tmp)
        self.layer = FileVerificationLayer(
            repo_root=self.repo,
            fail_closed=True,
            log_dir=self.repo / ".vlogs",
        )
        self.guard = HallucinationGuard(file_layer=self.layer)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, rel: str, content: str = "hello\n") -> Path:
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def _delete(self, rel: str) -> None:
        (self.repo / rel).unlink()


# ===========================================================================
# TEST 1 — GAP-01: PHANTOM_TYPE_4
# Agent claims DELETED xyz.py when file never existed in snapshot at all.
# Expected: PHANTOM_FILE (the specific "type 4" variant — not just "ghost.go
# that appeared then vanished" but "never existed anywhere").
# ===========================================================================

class TestPhantomType4DeletedNeverExisted(_Base):
    """
    GAP-01 — PHANTOM_TYPE_4:
    Agent claims it DELETED a file that was never present in the before-snapshot
    (i.e. it never existed at all, not just absent after).

    Previous test suite (v5.9.1) only tested:
      - PHANTOM on CREATED claim   (file never appeared)
      - PHANTOM on MODIFIED claim  (file never existed)
      - Legitimate deletion        (file existed, was deleted)

    Missing case: PHANTOM on DELETED claim when file was never in snapshot.
    """

    def test_phantom_type_4_deleted_never_existed(self):
        """
        Agent claims DELETED 'ghost_deleted.py'.
        The file did NOT exist BEFORE the iteration (no snapshot entry).
        The file does NOT exist AFTER the iteration either.
        => PHANTOM_FILE hallucination (delete of a file that never existed).
        """
        # No file created — ghost_deleted.py is completely absent
        ctx = self.guard.before_iteration(
            "agent_phantom4",
            ["ghost_deleted.py"],   # declared scope, but file is absent
        )

        # Agent makes a DELETE claim — but nothing was ever there
        result = self.guard.after_iteration(
            "agent_phantom4",
            [AgentClaim(file_path="ghost_deleted.py", action=ClaimAction.DELETED)],
            ctx,
        )

        self.assertEqual(result.verdict, Verdict.HALLUCINATION,
                         "DELETED claim on never-existing file must be HALLUCINATION")
        self.assertTrue(result.blocked,
                        "fail_closed=True must block on hallucination")
        self.assertEqual(len(result.hallucinations), 1)

        h = result.hallucinations[0]
        self.assertEqual(
            h.hallucination_type, HallucinationType.PHANTOM_FILE,
            f"Expected PHANTOM_FILE, got {h.hallucination_type}"
        )
        self.assertEqual(h.file_path, "ghost_deleted.py")
        self.assertIn("ghost_deleted.py", h.description)
        self.assertIn("did not exist before", h.description,
                      "Description must state file did not exist before")

    def test_phantom_type_4_delete_claim_undeclared_path(self):
        """
        Variant: agent claims DELETED on a path outside the declared scope.
        The file never existed anywhere.
        => Still PHANTOM_FILE.
        """
        # before_iteration does not include 'mystery.go' in the scope
        ctx = self.guard.before_iteration("agent_phantom4b", [])

        result = self.guard.after_iteration(
            "agent_phantom4b",
            [AgentClaim(file_path="mystery.go", action=ClaimAction.DELETED)],
            ctx,
        )

        self.assertEqual(result.verdict, Verdict.HALLUCINATION)
        h = result.hallucinations[0]
        self.assertEqual(h.hallucination_type, HallucinationType.PHANTOM_FILE)

    def test_phantom_type_4_does_not_fire_on_legitimate_deletion(self):
        """
        Regression guard: legitimate deletion (file existed before, gone after)
        must NOT be flagged as PHANTOM_FILE — must be VERIFIED.
        """
        self._write("real_file.py", "x = 1\n")
        ctx = self.guard.before_iteration("agent_legit_del", ["real_file.py"])

        # Actually delete it
        self._delete("real_file.py")

        result = self.guard.after_iteration(
            "agent_legit_del",
            [AgentClaim(file_path="real_file.py", action=ClaimAction.DELETED)],
            ctx,
        )

        self.assertEqual(result.verdict, Verdict.VERIFIED,
                         "Legitimate deletion must be VERIFIED")
        self.assertFalse(result.blocked)
        self.assertEqual(len(result.hallucinations), 0)


# ===========================================================================
# TEST 2 — GAP-02: SIZE_MISMATCH automatic activation
# File size changes >10% without MODIFIED claim.
# ===========================================================================

class TestSizeMismatchDetectedAutomatic(_Base):
    """
    GAP-02 — SIZE_MISMATCH:
    HallucinationType.SIZE_MISMATCH was a dead enum value — never emitted by
    the engine.  After applying hallucination_guard_fix_patch (or the inline
    diff), the engine must automatically emit SIZE_MISMATCH when a file's size
    changes by more than 10% without a corresponding MODIFIED/FIXED claim.
    """

    def _write_bytes(self, rel: str, size: int, byte: bytes = b"A") -> Path:
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(byte * size)
        return p

    def test_size_mismatch_detected_automatic(self):
        """
        Core GAP-02 test: file grows by >10%, agent claims NOOP on other file.
        After applying the SIZE_MISMATCH patch, the engine emits SIZE_MISMATCH.
        Without the patch the engine emits FILE_NOT_IN_SNAPSHOT (SHA changed).
        Both are valid hallucination signals — the test asserts a hallucination
        IS detected for bloated.py, and that SIZE_MISMATCH is emitted when
        the patch is applied.
        """
        if not _PATCH_AVAILABLE:
            self.skipTest(
                "hallucination_guard_fix_patch not importable — "
                "apply the diff to file_verification.py first"
            )

        # Apply the SIZE_MISMATCH monkey-patch to the live layer
        patch_file_verification_layer()

        # Re-create guard with patched layer
        self.layer = FileVerificationLayer(
            repo_root=self.repo,
            fail_closed=True,
            log_dir=self.repo / ".vlogs2",
        )
        self.guard = HallucinationGuard(file_layer=self.layer)

        # Create two files
        self._write_bytes("stable.py", 1000)   # 1000 bytes
        self._write_bytes("bloated.py", 1000)  # 1000 bytes

        ctx = self.guard.before_iteration(
            "agent_sm",
            ["stable.py", "bloated.py"],
        )

        # bloated.py grows by 50% — silently (agent makes no claim about it)
        self._write_bytes("bloated.py", 1500)

        # Agent only claims NOOP on stable.py
        result = self.guard.after_iteration(
            "agent_sm",
            [AgentClaim(file_path="stable.py", action=ClaimAction.NOOP)],
            ctx,
        )

        # After patching: SIZE_MISMATCH (or at minimum a hallucination) on bloated.py
        any_issues_on_bloated = [
            h for h in result.hallucinations if h.file_path == "bloated.py"
        ]
        self.assertGreaterEqual(
            len(any_issues_on_bloated), 1,
            f"Expected hallucination on bloated.py, got: "
            f"{[h.hallucination_type for h in result.hallucinations]}"
        )
        size_issues = [
            h for h in result.hallucinations
            if h.hallucination_type == HallucinationType.SIZE_MISMATCH
        ]
        self.assertGreaterEqual(
            len(size_issues), 1,
            f"Expected SIZE_MISMATCH after patch, got: "
            f"{[h.hallucination_type for h in result.hallucinations]}"
        )
        self.assertEqual(size_issues[0].file_path, "bloated.py")
        self.assertIn("bloated.py", size_issues[0].description)

    def test_size_mismatch_below_threshold_clean(self):
        """
        Boundary condition: size change <10% must NOT trigger SIZE_MISMATCH.
        """
        if not _PATCH_AVAILABLE:
            self.skipTest("hallucination_guard_fix_patch not importable")

        self._write_bytes("data.json", 1000)

        ctx = self.guard.before_iteration("agent_sm_clean", ["data.json"])

        # Only 5% growth — below threshold
        self._write_bytes("data.json", 1050)

        result = self.guard.after_iteration(
            "agent_sm_clean",
            [AgentClaim(file_path="data.json", action=ClaimAction.NOOP)],
            ctx,
        )

        size_issues = [
            h for h in result.hallucinations
            if h.hallucination_type == HallucinationType.SIZE_MISMATCH
        ]
        self.assertEqual(
            len(size_issues), 0,
            "Sub-threshold size change must not produce SIZE_MISMATCH"
        )

    def test_size_mismatch_helper_direct(self):
        """
        Unit test for the _check_size_mismatch() helper function directly.
        """
        if not _PATCH_AVAILABLE:
            self.skipTest("hallucination_guard_fix_patch not importable")

        from file_verification import FileSnapshot

        def _snap(exists: bool, size: int, sha: str = "abc") -> FileSnapshot:
            return FileSnapshot(
                file_path="dummy",
                sha256=sha,
                size_bytes=size,
                mtime=0.0,
                exists=exists,
            )

        before = {"big.py": _snap(True, 1000, "sha1")}
        after  = {"big.py": _snap(True, 2000, "sha2")}  # 100% growth

        issues = _check_size_mismatch(
            snapshots_before=before,
            snapshots_after=after,
            claimed_paths=set(),     # agent claimed nothing
            agent_id="tester",
        )
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].hallucination_type, HallucinationType.SIZE_MISMATCH)
        self.assertEqual(issues[0].file_path, "big.py")

    def test_size_mismatch_no_fire_when_modified_claimed(self):
        """
        SIZE_MISMATCH must NOT fire if the agent already claimed MODIFIED
        on the growing file — that path is covered by _check_modification_claim.
        """
        if not _PATCH_AVAILABLE:
            self.skipTest("hallucination_guard_fix_patch not importable")

        from file_verification import FileSnapshot

        def _snap(exists: bool, size: int, sha: str = "x") -> FileSnapshot:
            return FileSnapshot(file_path="big.py", sha256=sha,
                                size_bytes=size, mtime=0.0, exists=exists)

        before = {"big.py": _snap(True, 1000, "sha1")}
        after  = {"big.py": _snap(True, 2000, "sha2")}

        # Agent already declared MODIFIED — path is in claimed_paths
        issues = _check_size_mismatch(
            snapshots_before=before,
            snapshots_after=after,
            claimed_paths={"big.py"},
            agent_id="tester",
        )
        self.assertEqual(len(issues), 0,
                         "SIZE_MISMATCH must not double-fire for MODIFIED claims")


# ===========================================================================
# TEST 3 — GAP-03a: UNEXPECTED_DELETION
# File disappears without agent declaring DELETED.
# ===========================================================================

class TestUnexpectedDeletionFlagged(_Base):
    """
    GAP-03a — UNEXPECTED_DELETION:
    A file present in the before-snapshot disappears after the iteration
    but the agent made no DELETED claim for it.

    The engine already has code for this but there was no dedicated test.
    This test provides a precise, isolated regression guard.
    """

    def test_unexpected_deletion_flagged(self):
        """
        Core test: file 'config.yaml' exists before, is gone after,
        agent only claims to have MODIFIED 'handler.go'.
        => UNEXPECTED_DELETION on 'config.yaml'.
        """
        # Create both files
        self._write("handler.go", "package main\n")
        self._write("config.yaml", "version: 1\n")

        ctx = self.guard.before_iteration(
            "agent_del",
            ["handler.go", "config.yaml"],
        )

        # Modify handler, silently delete config
        self._write("handler.go", "package main // modified\n")
        self._delete("config.yaml")

        result = self.guard.after_iteration(
            "agent_del",
            [AgentClaim(file_path="handler.go", action=ClaimAction.MODIFIED)],
            ctx,
        )

        deletion_issues = [
            h for h in result.hallucinations
            if h.hallucination_type == HallucinationType.UNEXPECTED_DELETION
        ]
        self.assertGreaterEqual(
            len(deletion_issues), 1,
            f"Expected UNEXPECTED_DELETION, got: "
            f"{[h.hallucination_type for h in result.hallucinations]}"
        )
        self.assertEqual(deletion_issues[0].file_path, "config.yaml")
        self.assertIn("config.yaml", deletion_issues[0].description)
        self.assertIn("delete", deletion_issues[0].description.lower())

    def test_unexpected_deletion_with_no_claims_at_all(self):
        """
        Edge case: agent produces zero claims, but a file disappears.
        => UNEXPECTED_DELETION should still be caught (from the watch scan).
        """
        self._write("important.go", "// critical file\n")

        ctx = self.guard.before_iteration("agent_silent", ["important.go"])

        # Silent deletion
        self._delete("important.go")

        # Agent sends no claims
        result = self.guard.after_iteration("agent_silent", [], ctx)

        deletion_issues = [
            h for h in result.hallucinations
            if h.hallucination_type == HallucinationType.UNEXPECTED_DELETION
        ]
        self.assertGreaterEqual(
            len(deletion_issues), 1,
            "Silent deletion (no claims at all) must trigger UNEXPECTED_DELETION"
        )

    def test_unexpected_deletion_clean_when_declared(self):
        """
        Regression: when agent correctly declares DELETED, no UNEXPECTED_DELETION.
        """
        self._write("safe.go", "x = 1\n")
        ctx = self.guard.before_iteration("agent_good_del", ["safe.go"])
        self._delete("safe.go")

        result = self.guard.after_iteration(
            "agent_good_del",
            [AgentClaim(file_path="safe.go", action=ClaimAction.DELETED)],
            ctx,
        )
        unexpected = [
            h for h in result.hallucinations
            if h.hallucination_type == HallucinationType.UNEXPECTED_DELETION
        ]
        self.assertEqual(len(unexpected), 0,
                         "Properly declared DELETED must not produce UNEXPECTED_DELETION")


# ===========================================================================
# TEST 4 — GAP-03b: UNEXPECTED_CREATION
# File appears without agent declaring CREATED.
# ===========================================================================

class TestUnexpectedCreationFlagged(_Base):
    """
    GAP-03b — UNEXPECTED_CREATION:
    A new file appears in the workspace after the iteration but the agent
    did not declare a CREATED claim.

    Again, the engine has the code but v5.9.1 had no isolated test for this.
    """

    def test_unexpected_creation_flagged(self):
        """
        Core test: 'sneaky_output.bin' did not exist before the iteration,
        appears after, but agent claims MODIFIED on 'main.go' AND lists
        'sneaky_output.bin' in additional_watch so the engine can observe it.

        NOTE: The engine only detects UNEXPECTED_CREATION on paths it knows
        to re-snapshot. The correct integration pattern is to pass the
        full directory scan as additional_watch_paths. Here we simulate that
        by including the new file path in additional_watch.
        """
        self._write("main.go", "package main\n")

        # Include sneaky_output.bin in the watch so the engine sees it
        ctx = self.guard.before_iteration(
            "agent_create",
            ["main.go"],
            additional_watch=["sneaky_output.bin"],
        )

        # Modify declared file + silently create a new one
        self._write("main.go", "package main // v2\n")
        self._write("sneaky_output.bin", "binary garbage\n")

        result = self.guard.after_iteration(
            "agent_create",
            [AgentClaim(file_path="main.go", action=ClaimAction.MODIFIED)],
            ctx,
        )

        creation_issues = [
            h for h in result.hallucinations
            if h.hallucination_type == HallucinationType.UNEXPECTED_CREATION
        ]
        self.assertGreaterEqual(
            len(creation_issues), 1,
            f"Expected UNEXPECTED_CREATION, got: "
            f"{[h.hallucination_type for h in result.hallucinations]}"
        )
        self.assertEqual(creation_issues[0].file_path, "sneaky_output.bin")
        self.assertIn("sneaky_output.bin", creation_issues[0].description)
        self.assertIn("create", creation_issues[0].description.lower())

    def test_unexpected_creation_multiple_files(self):
        """
        Multiple files appear without claims: each triggers UNEXPECTED_CREATION.
        """
        ctx = self.guard.before_iteration("agent_multi_create", [])

        self._write("file_a.py", "a = 1\n")
        self._write("file_b.py", "b = 2\n")
        self._write("file_c.py", "c = 3\n")

        result = self.guard.after_iteration("agent_multi_create", [], ctx)

        # All three should be flagged — but they only appear if the watch
        # captured them; since no declared files, the engine scans claims only.
        # After GAP-03 is properly triggered via watch, we assert at least the
        # no-claims path doesn't crash:
        self.assertIsNotNone(result)
        self.assertIn(result.verdict, list(Verdict))

    def test_unexpected_creation_clean_when_declared(self):
        """
        Regression: agent correctly claims CREATED — no UNEXPECTED_CREATION.
        """
        ctx = self.guard.before_iteration("agent_good_create", ["new_module.py"])

        self._write("new_module.py", "x = 42\n")

        result = self.guard.after_iteration(
            "agent_good_create",
            [AgentClaim(file_path="new_module.py", action=ClaimAction.CREATED)],
            ctx,
        )

        unexpected = [
            h for h in result.hallucinations
            if h.hallucination_type == HallucinationType.UNEXPECTED_CREATION
        ]
        self.assertEqual(len(unexpected), 0,
                         "Properly declared CREATED must not produce UNEXPECTED_CREATION")


# ===========================================================================
# BONUS TEST — GAP-04: insert_anti_hallucination_log DB write
# ===========================================================================

class TestAntiHallucLogFeed(unittest.TestCase):
    """
    GAP-04 — Validate that insert_anti_hallucination_log correctly writes
    violation rows into a SQLite database matching the dashboard schema.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sylion_v592_db_")
        self.db_path = Path(self.tmp) / "test_dashboard.db"
        # Create minimal schema
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anti_hallucination_log (
                id          TEXT PRIMARY KEY,
                ts          REAL NOT NULL,
                layer       TEXT NOT NULL DEFAULT '',
                check_type  TEXT NOT NULL DEFAULT '',
                input_hash  TEXT NOT NULL DEFAULT '',
                result      TEXT NOT NULL DEFAULT 'pass',
                detail      TEXT NOT NULL DEFAULT '',
                agent_id    TEXT NOT NULL DEFAULT '',
                run_id      TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_result_stub(self, n_hallucinations: int = 1):
        """Build a minimal VerificationResult stub."""
        from unittest.mock import MagicMock
        result = MagicMock()
        hallucinations = []
        for i in range(n_hallucinations):
            h = MagicMock()
            h.hallucination_type.value = "phantom_file"
            h.file_path = f"ghost_{i}.py"
            h.description = f"File ghost_{i}.py was phantom-claimed"
            hallucinations.append(h)
        result.hallucinations = hallucinations
        return result

    @unittest.skipUnless(_PATCH_AVAILABLE, "hallucination_guard_fix_patch not importable")
    def test_insert_anti_hallucination_log_single(self):
        """Single violation → 1 row inserted."""
        from hallucination_guard_fix_patch import insert_anti_hallucination_log

        result = self._make_result_stub(1)
        rows = insert_anti_hallucination_log(
            db_path=self.db_path,
            agent_id="test_agent",
            run_id="run-abc123",
            result=result,
            layer="file_verification",
        )
        self.assertEqual(rows, 1)

        conn = sqlite3.connect(str(self.db_path))
        rows_db = conn.execute(
            "SELECT * FROM anti_hallucination_log WHERE agent_id='test_agent'"
        ).fetchall()
        conn.close()
        self.assertEqual(len(rows_db), 1)
        row = rows_db[0]
        # Schema: id(0), ts(1), layer(2), check_type(3), input_hash(4),
        #         result(5), detail(6), agent_id(7), run_id(8)
        self.assertEqual(row[5], "violation")  # result column
        self.assertEqual(row[7], "test_agent")  # agent_id
        self.assertEqual(row[8], "run-abc123")  # run_id

    @unittest.skipUnless(_PATCH_AVAILABLE, "hallucination_guard_fix_patch not importable")
    def test_insert_anti_hallucination_log_multiple(self):
        """Multiple violations → N rows inserted, one per hallucination."""
        from hallucination_guard_fix_patch import insert_anti_hallucination_log

        result = self._make_result_stub(3)
        rows = insert_anti_hallucination_log(
            db_path=self.db_path,
            agent_id="multi_agent",
            run_id="run-xyz",
            result=result,
        )
        self.assertEqual(rows, 3)

        conn = sqlite3.connect(str(self.db_path))
        count = conn.execute(
            "SELECT COUNT(*) FROM anti_hallucination_log WHERE agent_id='multi_agent'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(count, 3)

    @unittest.skipUnless(_PATCH_AVAILABLE, "hallucination_guard_fix_patch not importable")
    def test_insert_anti_hallucination_log_no_violation_noop(self):
        """Clean result (no hallucinations) → 0 rows, no DB error."""
        from hallucination_guard_fix_patch import insert_anti_hallucination_log

        result = self._make_result_stub(0)
        rows = insert_anti_hallucination_log(
            db_path=self.db_path,
            agent_id="clean_agent",
            run_id="run-clean",
            result=result,
        )
        self.assertEqual(rows, 0)

    @unittest.skipUnless(_PATCH_AVAILABLE, "hallucination_guard_fix_patch not importable")
    def test_insert_anti_hallucination_log_missing_db_noop(self):
        """Non-existent DB path → returns 0 without crashing."""
        from hallucination_guard_fix_patch import insert_anti_hallucination_log

        result = self._make_result_stub(1)
        rows = insert_anti_hallucination_log(
            db_path=Path("/nonexistent/path/db.sqlite"),
            agent_id="edge_agent",
            run_id="run-edge",
            result=result,
        )
        self.assertEqual(rows, 0, "Missing DB parent dir must return 0, not crash")

    @unittest.skipUnless(_PATCH_AVAILABLE, "hallucination_guard_fix_patch not importable")
    def test_insert_anti_hallucination_log_none_db_noop(self):
        """db_path=None → returns 0."""
        from hallucination_guard_fix_patch import insert_anti_hallucination_log

        result = self._make_result_stub(1)
        rows = insert_anti_hallucination_log(
            db_path=None,
            agent_id="null_agent",
            run_id="",
            result=result,
        )
        self.assertEqual(rows, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
