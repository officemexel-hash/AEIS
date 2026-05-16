#!/usr/bin/env python3
"""
SYLION v5.9.1 — HallucinationGuard test suite
==============================================

Tests for FileVerificationLayer + HallucinationGuard path-traversal safety
and phantom-file detection, including the NameError fix (log → logger) on
lines 336/344 of file_verification.py.

Run:
    cd sylion-pipeline
    /tmp/sylion_venv/bin/python -m pytest tests/test_hallucination_guard_v591.py -v
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Make root importable from tests/ subdir
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from file_verification import (
    AgentClaim,
    ClaimAction,
    FileVerificationLayer,
    HallucinationType,
    HallucinationGuard,
    Verdict,
)


class _Base(unittest.TestCase):
    """Base: temp workspace + FileVerificationLayer."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="sylion_hguard_")
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

    def _run_claim(self, rel: str, action: ClaimAction, *, setup=None):
        """Run before_iteration → optional mutation → after_iteration."""
        ctx = self.guard.before_iteration("test_agent", [rel])
        if setup:
            setup()
        return self.guard.after_iteration(
            "test_agent",
            [AgentClaim(file_path=rel, action=action)],
            ctx,
        )


# ---------------------------------------------------------------------------
# Test 1: PHANTOM_FILE on CREATED claim for non-existent file
# ---------------------------------------------------------------------------

class TestPhantomFileClaimCreated(_Base):
    """Agent claims CREATED on a file that never appeared."""

    def test_phantom_file_claim_created(self):
        # File does NOT exist at all — no setup call
        ctx = self.guard.before_iteration("agent_x", ["ghost.go"])
        result = self.guard.after_iteration(
            "agent_x",
            [AgentClaim(file_path="ghost.go", action=ClaimAction.CREATED)],
            ctx,
        )
        self.assertEqual(result.verdict, Verdict.HALLUCINATION)
        self.assertTrue(result.blocked)
        self.assertEqual(len(result.hallucinations), 1)
        h = result.hallucinations[0]
        self.assertEqual(h.hallucination_type, HallucinationType.PHANTOM_FILE)
        self.assertEqual(h.file_path, "ghost.go")


# ---------------------------------------------------------------------------
# Test 2: PHANTOM_FILE on MODIFIED claim for non-existent file
# ---------------------------------------------------------------------------

class TestPhantomFileClaimModified(_Base):
    """Agent claims MODIFIED on a file that doesn't exist before or after."""

    def test_phantom_file_claim_modified(self):
        ctx = self.guard.before_iteration("agent_y", ["nonexistent.go"])
        result = self.guard.after_iteration(
            "agent_y",
            [AgentClaim(file_path="nonexistent.go", action=ClaimAction.MODIFIED)],
            ctx,
        )
        self.assertEqual(result.verdict, Verdict.HALLUCINATION)
        self.assertTrue(result.blocked)
        self.assertEqual(len(result.hallucinations), 1)
        h = result.hallucinations[0]
        self.assertEqual(h.hallucination_type, HallucinationType.PHANTOM_FILE)


# ---------------------------------------------------------------------------
# Test 3: DELETED claim on file that existed before → NOT a phantom
# ---------------------------------------------------------------------------

class TestPhantomFileClaimDeletedButExistedBefore(_Base):
    """Agent claims DELETED; file existed before and is gone after → legitimate."""

    def test_phantom_file_claim_deleted_but_existed_before(self):
        self._write("legacy.go", "package legacy\n")
        ctx = self.guard.before_iteration("agent_z", ["legacy.go"])

        # Actually delete the file between iterations
        self._delete("legacy.go")

        result = self.guard.after_iteration(
            "agent_z",
            [AgentClaim(file_path="legacy.go", action=ClaimAction.DELETED)],
            ctx,
        )
        # File existed in baseline and is now gone → verified deletion
        self.assertEqual(result.verdict, Verdict.VERIFIED)
        self.assertFalse(result.blocked)
        self.assertEqual(len(result.hallucinations), 0)


# ---------------------------------------------------------------------------
# Test 4: Path traversal via "../../../etc/passwd" → rejected, NO NameError
# ---------------------------------------------------------------------------

class TestPathTraversalRejected(_Base):
    """snapshot_file() must reject path traversal without raising NameError."""

    def test_path_traversal_rejected(self):
        traversal_path = "../../../etc/passwd"
        # Before the fix this raised NameError: name 'log' is not defined.
        # After fix it logs a warning and returns an empty (non-existent) snapshot.
        snap = self.layer.snapshot_file(traversal_path)
        self.assertFalse(snap.exists, "Traversal path must be reported as non-existent")
        self.assertEqual(snap.sha256, "", "SHA must be empty for rejected path")

    def test_path_traversal_rejected_no_name_error(self):
        """Confirm the fix: calling snapshot_file with '..' does not raise NameError."""
        try:
            self.layer.snapshot_file("../../secret.txt")
        except NameError as e:
            self.fail(f"NameError should be fixed but got: {e}")


# ---------------------------------------------------------------------------
# Test 5: Symlink pointing outside workspace → rejected
# ---------------------------------------------------------------------------

class TestPathTraversalSymlink(_Base):
    """Symlink that resolves outside repo_root must be rejected."""

    def test_path_traversal_symlink(self):
        # Create a symlink inside repo that points outside
        outside_target = Path(self.tmp).parent  # one level up = outside repo
        link_path = self.repo / "evil_link"
        try:
            link_path.symlink_to(outside_target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not supported on this platform")

        snap = self.layer.snapshot_file("evil_link")
        # The resolved path escapes repo_root → rejected
        self.assertFalse(snap.exists,
                         "Symlink escaping repo must be reported as non-existent")


# ---------------------------------------------------------------------------
# Test 6: SIZE_MISMATCH — file exists but size differs from expected
# ---------------------------------------------------------------------------

class TestSizeMismatchDetection(_Base):
    """
    HallucinationType.SIZE_MISMATCH is reserved (not auto-generated by the
    engine). We test that we can construct a Hallucination with that type and
    that the enum value is accessible — ensuring the enum member exists and
    has not been removed.

    Additionally we verify that a file whose SHA changed (different content
    implies different size) is correctly detected as a hallucination when
    the agent makes a NOOP claim (no-change assertion violated).
    """

    def test_size_mismatch_detection(self):
        # Confirm SIZE_MISMATCH enum member exists
        self.assertEqual(HallucinationType.SIZE_MISMATCH.value, "size_mismatch")

        # Indirect size-mismatch scenario: write small file, snapshot, then
        # write a bigger file → agent claims NOOP → FILE_NOT_IN_SNAPSHOT detected.
        self._write("data.bin", "small")
        ctx = self.guard.before_iteration("agent_s", ["data.bin"])

        # Replace with larger content
        self._write("data.bin", "X" * 4096)

        result = self.guard.after_iteration(
            "agent_s",
            [AgentClaim(file_path="data.bin", action=ClaimAction.NOOP)],
            ctx,
        )
        self.assertEqual(result.verdict, Verdict.HALLUCINATION)
        self.assertTrue(result.blocked)
        # NOOP + SHA changed → FILE_NOT_IN_SNAPSHOT
        h = result.hallucinations[0]
        self.assertEqual(h.hallucination_type, HallucinationType.FILE_NOT_IN_SNAPSHOT)


# ---------------------------------------------------------------------------
# Test 7: SHA-256 mismatch — content changed, agent claims NOOP
# ---------------------------------------------------------------------------

class TestSha256MismatchDetection(_Base):
    """File SHA changed but agent claims NOOP → hallucination detected."""

    def test_sha256_mismatch_detection(self):
        self._write("handler.go", "package main\nfunc A() {}\n")
        ctx = self.guard.before_iteration("agent_sha", ["handler.go"])

        # Mutate the file (different SHA)
        self._write("handler.go", "package main\nfunc A() { /* changed */ }\n")

        result = self.guard.after_iteration(
            "agent_sha",
            [AgentClaim(file_path="handler.go", action=ClaimAction.NOOP)],
            ctx,
        )
        self.assertEqual(result.verdict, Verdict.HALLUCINATION)
        self.assertTrue(result.blocked)
        h = result.hallucinations[0]
        # NOOP with SHA change → FILE_NOT_IN_SNAPSHOT
        self.assertEqual(h.hallucination_type, HallucinationType.FILE_NOT_IN_SNAPSHOT)
        self.assertIsNotNone(h.sha_before)
        self.assertIsNotNone(h.sha_after)
        self.assertNotEqual(h.sha_before, h.sha_after)


if __name__ == "__main__":
    unittest.main()
