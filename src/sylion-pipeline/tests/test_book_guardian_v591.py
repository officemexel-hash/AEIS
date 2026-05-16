#!/usr/bin/env python3
"""
SYLION v5.9.1 — BookGuardian test suite
=======================================

Tests for BookGuardian — the SHA-256 watchdog protecting Księga SYLION 3.4 FIXED.

Run:
    cd sylion-pipeline
    /tmp/sylion_venv/bin/python -m pytest tests/test_book_guardian_v591.py -v
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from book_guardian import BookGuardian, DriftReport, KsiegaSnapshot


class _Base(unittest.TestCase):
    """Base: temp directory with a fake Księga file."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="sylion_bg_")
        self.tmpdir = Path(self.tmp)
        self.log_dir = self.tmpdir / "bg_logs"
        self.ksiega = self.tmpdir / "Ksiega_SYLION_3_4_FIXED.docx"
        # Write a valid Księga file
        self.ksiega.write_bytes(b"Ksiega SYLION 3.4 FIXED content here")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_guardian(self, **kwargs) -> BookGuardian:
        return BookGuardian(
            ksiega_path=self.ksiega,
            log_dir=self.log_dir,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Test 1: Baseline SHA-256 computed on start
# ---------------------------------------------------------------------------

class TestBaselineSha256ComputedOnStart(_Base):
    """BookGuardian must compute and store a baseline SHA on init."""

    def test_baseline_sha256_computed_on_start(self):
        guardian = self._make_guardian()

        # Baseline is computed
        self.assertIsNotNone(guardian.baseline)
        self.assertTrue(guardian.baseline.exists)
        self.assertEqual(len(guardian.baseline.sha256), 64,
                         "SHA-256 hex digest must be 64 characters")
        self.assertGreater(guardian.baseline.size_bytes, 0)

        # baseline.json persisted to disk
        baseline_file = self.log_dir / "baseline.json"
        self.assertTrue(baseline_file.exists(),
                        "baseline.json must be written to log_dir on init")

    def test_baseline_sha_property_accessible(self):
        guardian = self._make_guardian()
        sha = guardian.baseline_sha
        self.assertEqual(len(sha), 64)


# ---------------------------------------------------------------------------
# Test 2: Deleted file → drift detected (DELETED type)
# ---------------------------------------------------------------------------

class TestFileRemovedDriftDetected(_Base):
    """After init, deleting the Księga file must trigger drift on check()."""

    def test_file_removed_drift_detected(self):
        guardian = self._make_guardian()

        # Delete the Księga file
        self.ksiega.unlink()

        # check() must detect drift and return False
        result = guardian.check()
        self.assertFalse(result, "check() must return False when Księga is deleted")
        self.assertGreater(guardian.drift_count, 0, "drift_count must be > 0")
        self.assertFalse(guardian.is_healthy)

        # The drift report description mentions DELETED
        drift_report = guardian._drift_reports[-1]
        self.assertIn("DELETED", drift_report.description)


# ---------------------------------------------------------------------------
# Test 3: SHA changed → drift with SHA_CHANGED description
# ---------------------------------------------------------------------------

class TestShaChangedDrift(_Base):
    """Modifying the Księga content must trigger drift on check()."""

    def test_sha_changed_drift(self):
        guardian = self._make_guardian()
        original_sha = guardian.baseline_sha

        # Mutate the Księga
        self.ksiega.write_bytes(b"MODIFIED - unauthorized change!")

        result = guardian.check()
        self.assertFalse(result, "check() must return False when SHA changes")
        self.assertGreater(guardian.drift_count, 0)

        drift_report = guardian._drift_reports[-1]
        self.assertIn("CHANGED", drift_report.description)
        self.assertIn(original_sha[:16], drift_report.description)


# ---------------------------------------------------------------------------
# Test 4: File appeared when baseline was empty → drift APPEARED
# ---------------------------------------------------------------------------

class TestAppearedWhenBaselineEmpty(_Base):
    """
    Init on non-existent file → empty baseline.
    Then create the file → check() detects APPEARED and recalculates baseline.
    """

    def test_appeared_when_baseline_empty(self):
        # Start without a Księga
        missing_path = self.tmpdir / "not_yet_created.docx"
        guardian = BookGuardian(
            ksiega_path=missing_path,
            log_dir=self.log_dir,
        )

        # Baseline shows file doesn't exist
        self.assertFalse(guardian.baseline.exists)

        # Now create the file
        missing_path.write_bytes(b"newly appeared Ksiega content")

        # check() detects appearance → returns True (not a hard error) and updates baseline
        result = guardian.check()
        self.assertTrue(result, "Appeared file from empty baseline returns True (non-blocking)")
        # After appearance, baseline is recalculated
        self.assertTrue(guardian.baseline.exists)
        self.assertEqual(len(guardian.baseline.sha256), 64)


# ---------------------------------------------------------------------------
# Test 5: auto_halt parameter wiring
# ---------------------------------------------------------------------------

class TestAutoHaltParameterWiring(_Base):
    """
    auto_halt=True is stored on the guardian; check() returns False on drift.
    The caller is responsible for acting on the return value.
    Verify that when drift is found + auto_halt=True, check() returns False
    (signalling halt) and drift_count increments — the guardian does its part.
    """

    def test_auto_halt_parameter_wiring(self):
        guardian = self._make_guardian(auto_halt=True)
        self.assertTrue(guardian.auto_halt, "auto_halt must be stored as True")

        # Trigger drift
        self.ksiega.unlink()
        result = guardian.check()

        # Return value is False → caller must honour halt
        self.assertFalse(result,
                         "check() returns False on drift — caller must halt when auto_halt=True")
        self.assertGreater(guardian.drift_count, 0)

    def test_auto_halt_false_still_returns_false_on_drift(self):
        """auto_halt=False: check() still returns False on drift."""
        guardian = self._make_guardian(auto_halt=False)
        self.ksiega.unlink()
        result = guardian.check()
        self.assertFalse(result)

    def test_check_returns_true_when_no_drift(self):
        """No mutation → check() returns True."""
        guardian = self._make_guardian(auto_halt=True)
        self.assertTrue(guardian.check())
        self.assertEqual(guardian.drift_count, 0)
        self.assertTrue(guardian.is_healthy)


# ---------------------------------------------------------------------------
# Test 6: GateLevel.CRITICAL integration via mocked supervisor
# ---------------------------------------------------------------------------

class TestGateCriticalIntegration(_Base):
    """
    BookGuardian escalates to HumanGate via GateLevel.CRITICAL on drift.
    Verify that when a mock supervisor is injected, request_approval is called
    with a GateRequest at CRITICAL level.
    """

    def test_gate_critical_integration(self):
        # Mock supervisor module available to book_guardian
        mock_gate_request_cls = MagicMock()
        mock_gate_level = MagicMock()
        mock_gate_level.CRITICAL = "CRITICAL"

        captured_requests = []

        def fake_request_approval(req):
            captured_requests.append(req)

        mock_human_gate = MagicMock()
        mock_human_gate.request_approval.side_effect = fake_request_approval

        # Patch supervisor import inside book_guardian
        with patch.dict("sys.modules", {
            "supervisor": MagicMock(
                GateRequest=mock_gate_request_cls,
                GateLevel=mock_gate_level,
            )
        }):
            guardian = BookGuardian(
                ksiega_path=self.ksiega,
                log_dir=self.log_dir,
                human_gate=mock_human_gate,
            )
            # Trigger drift (delete Księga)
            self.ksiega.unlink()
            result = guardian.check()

        self.assertFalse(result)
        # human_gate.request_approval was called with a GateRequest
        mock_human_gate.request_approval.assert_called_once()
        # The GateRequest was constructed
        mock_gate_request_cls.assert_called_once()
        call_kwargs = mock_gate_request_cls.call_args
        # level should reference GateLevel.CRITICAL
        self.assertEqual(call_kwargs.kwargs.get("level"), mock_gate_level.CRITICAL)

    def test_gate_critical_not_called_without_drift(self):
        """When no drift, human_gate.request_approval must NOT be called."""
        mock_human_gate = MagicMock()
        with patch.dict("sys.modules", {
            "supervisor": MagicMock(
                GateRequest=MagicMock(),
                GateLevel=MagicMock(CRITICAL="CRITICAL"),
            )
        }):
            guardian = BookGuardian(
                ksiega_path=self.ksiega,
                log_dir=self.log_dir,
                human_gate=mock_human_gate,
            )
            result = guardian.check()

        self.assertTrue(result)
        mock_human_gate.request_approval.assert_not_called()


if __name__ == "__main__":
    unittest.main()
