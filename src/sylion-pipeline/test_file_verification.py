#!/usr/bin/env python3
"""
Tests for SYLION File Verification Layer.

17 tests in 4 groups:
  - TestHappyPath          (5)  — claims match reality
  - TestHallucinationDetection (7) — all 6 hallucination types + CHANGELOG-v3.4.13 scenario
  - TestPartialVerification (1) — mixed results
  - TestEdgeCases          (4)  — empty claims, validation, SHA consistency, large files

Run:
  cd sylion-pipeline
  python -m pytest test_file_verification.py -v
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from file_verification import (
    AgentClaim,
    ClaimAction,
    FileSnapshot,
    FileVerificationLayer,
    Hallucination,
    HallucinationType,
    Verdict,
    VerificationResult,
)


class _TestBase(unittest.TestCase):
    """Base class: creates a temp repo with sample files."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp(prefix="sylion_test_")
        self.repo = Path(self.tmp_dir)

        # Create sample Go files mimicking SYLION repo
        (self.repo / "cmd").mkdir()
        (self.repo / "internal").mkdir()
        (self.repo / "internal" / "handler").mkdir()

        self._write("cmd/main.go", "package main\n\nfunc main() {}\n")
        self._write("internal/handler/handler.go",
                     'package handler\n\nimport "fmt"\n\n'
                     'func Handle(w http.ResponseWriter, r *http.Request) {\n'
                     '    fmt.Fprintf(w, "OK")\n'
                     '}\n')
        self._write("internal/handler/utils.go",
                     "package handler\n\nfunc sanitize(s string) string {\n"
                     "    return s\n}\n")
        self._write("go.mod", "module sylion\n\ngo 1.22\n")

        self.layer = FileVerificationLayer(
            repo_root=self.repo,
            fail_closed=True,
            log_dir=self.repo / ".verification_logs",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write(self, rel_path: str, content: str) -> Path:
        """Write a file relative to repo root."""
        p = self.repo / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def _read(self, rel_path: str) -> str:
        return (self.repo / rel_path).read_text(encoding="utf-8")

    def _delete(self, rel_path: str) -> None:
        (self.repo / rel_path).unlink()


# ═══════════════════════════════════════════════════════════════════════════
# GROUP 1: Happy Path — claims match reality (5 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestHappyPath(_TestBase):
    """All claims align with actual file changes → VERIFIED."""

    def test_01_modify_claim_verified(self):
        """Agent modifies handler.go and claims MODIFIED → VERIFIED."""
        fp = "internal/handler/handler.go"
        snapshots = self.layer.snapshot_files([fp])

        # Agent actually modifies the file
        original = self._read(fp)
        self._write(fp, original.replace('fmt.Fprintf(w, "OK")',
                                          'fmt.Fprintf(w, "OK\\n")'))

        claims = [AgentClaim(file_path=fp, action=ClaimAction.MODIFIED,
                             description="Added newline to response")]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        self.assertEqual(result.verdict, Verdict.VERIFIED)
        self.assertEqual(result.claims_verified, 1)
        self.assertEqual(result.hallucination_count, 0)
        self.assertFalse(result.blocked)

    def test_02_fix_claim_verified(self):
        """Agent fixes handler.go and claims FIXED → VERIFIED."""
        fp = "internal/handler/handler.go"
        snapshots = self.layer.snapshot_files([fp])

        original = self._read(fp)
        self._write(fp, original.replace("func Handle(",
                                          "func Handle(ctx context.Context, "))

        claims = [AgentClaim(file_path=fp, action=ClaimAction.FIXED,
                             description="Added context parameter")]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        self.assertEqual(result.verdict, Verdict.VERIFIED)
        self.assertFalse(result.blocked)

    def test_03_create_claim_verified(self):
        """Agent creates a new file and claims CREATED → VERIFIED."""
        fp = "internal/handler/middleware.go"
        snapshots = self.layer.snapshot_files([fp])

        # File doesn't exist yet — snapshot shows exists=False
        self.assertFalse(snapshots[fp].exists)

        # Agent creates it
        self._write(fp, "package handler\n\nfunc Auth() {}\n")

        claims = [AgentClaim(file_path=fp, action=ClaimAction.CREATED,
                             description="Created auth middleware")]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        self.assertEqual(result.verdict, Verdict.VERIFIED)
        self.assertFalse(result.blocked)

    def test_04_delete_claim_verified(self):
        """Agent deletes utils.go and claims DELETED → VERIFIED."""
        fp = "internal/handler/utils.go"
        snapshots = self.layer.snapshot_files([fp])

        self.assertTrue(snapshots[fp].exists)
        self._delete(fp)

        claims = [AgentClaim(file_path=fp, action=ClaimAction.DELETED,
                             description="Removed unused utils")]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        self.assertEqual(result.verdict, Verdict.VERIFIED)
        self.assertFalse(result.blocked)

    def test_05_noop_claim_verified(self):
        """Agent declares NOOP on a file it didn't touch → VERIFIED."""
        fp = "go.mod"
        snapshots = self.layer.snapshot_files([fp])

        # Agent doesn't touch go.mod
        claims = [AgentClaim(file_path=fp, action=ClaimAction.NOOP,
                             description="No changes needed in go.mod")]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        self.assertEqual(result.verdict, Verdict.VERIFIED)
        self.assertFalse(result.blocked)


# ═══════════════════════════════════════════════════════════════════════════
# GROUP 2: Hallucination Detection (7 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestHallucinationDetection(_TestBase):
    """Claims contradict reality → hallucination detected."""

    def test_06_no_actual_change_fixed(self):
        """Agent claims FIXED but SHA is unchanged → NO_ACTUAL_CHANGE."""
        fp = "internal/handler/handler.go"
        snapshots = self.layer.snapshot_files([fp])

        # Agent does NOTHING to the file
        claims = [AgentClaim(file_path=fp, action=ClaimAction.FIXED,
                             description="Fixed error handling",
                             finding_id="F-001")]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        self.assertEqual(result.verdict, Verdict.HALLUCINATION)
        self.assertEqual(result.hallucination_count, 1)
        self.assertTrue(result.blocked)

        h = result.hallucinations[0]
        self.assertEqual(h.hallucination_type, HallucinationType.NO_ACTUAL_CHANGE)
        self.assertEqual(h.sha_before, h.sha_after)

    def test_07_phantom_file(self):
        """Agent claims MODIFIED on non-existent file → PHANTOM_FILE."""
        fp = "internal/handler/nonexistent.go"
        snapshots = self.layer.snapshot_files([fp])

        claims = [AgentClaim(file_path=fp, action=ClaimAction.MODIFIED,
                             description="Fixed race condition")]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        self.assertEqual(result.verdict, Verdict.HALLUCINATION)
        h = result.hallucinations[0]
        self.assertEqual(h.hallucination_type, HallucinationType.PHANTOM_FILE)
        self.assertTrue(result.blocked)

    def test_08_file_not_in_snapshot_undeclared(self):
        """Agent modifies file without claiming it → FILE_NOT_IN_SNAPSHOT."""
        fp_claimed = "internal/handler/handler.go"
        fp_undeclared = "go.mod"
        snapshots = self.layer.snapshot_files([fp_claimed, fp_undeclared])

        # Agent modifies handler.go (claimed) AND go.mod (not claimed)
        self._write(fp_claimed,
                    self._read(fp_claimed) + "\n// patched\n")
        self._write(fp_undeclared, "module sylion\n\ngo 1.23\n")

        claims = [AgentClaim(file_path=fp_claimed, action=ClaimAction.MODIFIED,
                             description="Added comment")]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        # handler.go claim verified, but go.mod changed without claim
        self.assertIn(result.verdict, (Verdict.PARTIAL, Verdict.HALLUCINATION))
        types = {h.hallucination_type for h in result.hallucinations}
        self.assertIn(HallucinationType.FILE_NOT_IN_SNAPSHOT, types)

    def test_09_unexpected_deletion(self):
        """File disappears without a delete claim → UNEXPECTED_DELETION."""
        fp_keep = "internal/handler/handler.go"
        fp_vanish = "internal/handler/utils.go"
        snapshots = self.layer.snapshot_files([fp_keep, fp_vanish])

        # Agent only claims noop on handler.go but deletes utils.go
        self._delete(fp_vanish)

        claims = [AgentClaim(file_path=fp_keep, action=ClaimAction.NOOP)]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        types = {h.hallucination_type for h in result.hallucinations}
        self.assertIn(HallucinationType.UNEXPECTED_DELETION, types)

    def test_10_unexpected_creation(self):
        """File appears without a create claim → UNEXPECTED_CREATION."""
        fp_watch = "internal/handler/handler.go"
        fp_surprise = "internal/handler/backdoor.go"
        snapshots = self.layer.snapshot_files([fp_watch, fp_surprise])

        # Surprise file creation
        self._write(fp_surprise, "package handler\n// surprise!\n")

        claims = [AgentClaim(file_path=fp_watch, action=ClaimAction.NOOP)]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        types = {h.hallucination_type for h in result.hallucinations}
        self.assertIn(HallucinationType.UNEXPECTED_CREATION, types)

    def test_11_delete_nonexistent(self):
        """Agent claims DELETED on file that didn't exist → PHANTOM_FILE."""
        fp = "internal/handler/imaginary.go"
        snapshots = self.layer.snapshot_files([fp])

        claims = [AgentClaim(file_path=fp, action=ClaimAction.DELETED,
                             description="Deleted legacy code")]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        self.assertEqual(result.verdict, Verdict.HALLUCINATION)
        h = result.hallucinations[0]
        self.assertEqual(h.hallucination_type, HallucinationType.PHANTOM_FILE)

    def test_12_changelog_v3_4_13_scenario(self):
        """THE critical test: agent claims it fixed a file but SHA is unchanged.

        Simulates the CHANGELOG-v3.4.13 hallucination scenario:
        - Iteration 3, agent says "fixed err.Error() in handler.go"
        - File is NOT actually modified
        - LoopGuard loop_score < 0.45 (would pass without SHA check)
        - FileVerificationLayer catches it: SHA before == SHA after
        """
        fp = "internal/handler/handler.go"
        snapshots = self.layer.snapshot_files([fp])

        # Record SHA before
        sha_before = snapshots[fp].sha256

        # Agent does NOTHING (simulates the hallucination)
        # but claims it fixed err.Error()
        claims = [AgentClaim(
            file_path=fp,
            action=ClaimAction.FIXED,
            description="Fixed err.Error() handling — replaced with fmt.Errorf "
                        "for better error context (CHANGELOG-v3.4.13 fix)",
            finding_id="F-SEC-042",
            agent_id="programmer_go_1",
        )]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        # SHA after must equal SHA before (agent didn't touch it)
        snap_after = self.layer.snapshot_file(fp)
        self.assertEqual(sha_before, snap_after.sha256)

        # Must be caught as hallucination
        self.assertEqual(result.verdict, Verdict.HALLUCINATION)
        self.assertEqual(result.hallucination_count, 1)
        self.assertTrue(result.blocked)

        h = result.hallucinations[0]
        self.assertEqual(h.hallucination_type, HallucinationType.NO_ACTUAL_CHANGE)
        self.assertEqual(h.sha_before, h.sha_after)
        self.assertEqual(h.agent_id, "programmer_go_1")
        self.assertIn("SHA-256 is identical", h.description)


# ═══════════════════════════════════════════════════════════════════════════
# GROUP 3: Partial Verification (1 test)
# ═══════════════════════════════════════════════════════════════════════════

class TestPartialVerification(_TestBase):
    """Some claims pass, some fail → PARTIAL."""

    def test_13_mixed_claims(self):
        """2 claims: one real modification, one hallucinated fix → PARTIAL."""
        fp_real = "internal/handler/handler.go"
        fp_fake = "internal/handler/utils.go"
        snapshots = self.layer.snapshot_files([fp_real, fp_fake])

        # Really modify handler.go
        self._write(fp_real, self._read(fp_real) + "\n// real change\n")

        # Don't touch utils.go (hallucinated claim)
        claims = [
            AgentClaim(file_path=fp_real, action=ClaimAction.MODIFIED,
                       description="Added real comment"),
            AgentClaim(file_path=fp_fake, action=ClaimAction.FIXED,
                       description="Fixed sanitization — HALLUCINATED"),
        ]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        self.assertEqual(result.verdict, Verdict.PARTIAL)
        self.assertEqual(result.claims_verified, 1)
        self.assertEqual(result.claims_failed, 1)
        self.assertTrue(result.blocked)  # fail_closed=True


# ═══════════════════════════════════════════════════════════════════════════
# GROUP 4: Edge Cases (4 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases(_TestBase):
    """Boundary conditions and special scenarios."""

    def test_14_no_claims_no_changes(self):
        """Agent makes no claims at all → NO_CLAIMS verdict."""
        snapshots = self.layer.snapshot_files(["go.mod"])
        result = self.layer.verify_changes("programmer_go_1", [], snapshots)

        self.assertEqual(result.verdict, Verdict.NO_CLAIMS)
        self.assertEqual(result.claims_total, 0)
        self.assertFalse(result.blocked)

    def test_15_claim_validation_action_types(self):
        """All ClaimAction enum values are handled without error."""
        fp = "cmd/main.go"
        snapshots = self.layer.snapshot_files([fp])

        for action in ClaimAction:
            claim = AgentClaim(file_path=fp, action=action,
                               description=f"Test {action.value}")
            # Should not raise, regardless of action
            result = self.layer.verify_changes(
                "test_agent", [claim], snapshots
            )
            self.assertIsInstance(result, VerificationResult)

    def test_16_sha_consistency(self):
        """Same file content always produces the same SHA-256."""
        fp = "cmd/main.go"
        s1 = self.layer.snapshot_file(fp)
        s2 = self.layer.snapshot_file(fp)
        self.assertEqual(s1.sha256, s2.sha256)
        self.assertTrue(len(s1.sha256) == 64)  # Full SHA-256 hex

        # Write same content — SHA must not change
        content = self._read(fp)
        self._write(fp, content)
        s3 = self.layer.snapshot_file(fp)
        self.assertEqual(s1.sha256, s3.sha256)

    def test_17_large_file_handling(self):
        """SHA-256 works correctly on a large file (>1MB)."""
        fp = "large_test_file.bin"
        # Write 2MB of deterministic data
        data = b"SYLION_TEST_BLOCK" * (2 * 1024 * 1024 // 17 + 1)
        abs_path = self.repo / fp
        abs_path.write_bytes(data)

        s1 = self.layer.snapshot_file(fp)
        self.assertTrue(s1.exists)
        self.assertGreater(s1.size_bytes, 1_000_000)

        # SHA must be consistent
        s2 = self.layer.snapshot_file(fp)
        self.assertEqual(s1.sha256, s2.sha256)

        # Modify one byte — SHA must differ
        data_mod = bytearray(data)
        data_mod[1000] = (data_mod[1000] + 1) % 256
        abs_path.write_bytes(bytes(data_mod))

        s3 = self.layer.snapshot_file(fp)
        self.assertNotEqual(s1.sha256, s3.sha256)


if __name__ == "__main__":
    unittest.main()
