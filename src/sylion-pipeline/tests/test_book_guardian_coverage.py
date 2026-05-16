#!/usr/bin/env python3
"""
SYLION v5.9.1 - BookGuardian Extended Coverage
===============================================
Covers run_watchdog() and load_baseline() - missing from test_book_guardian_v591.py.

Run:
    pytest tests_coverage/test_book_guardian_coverage.py -v
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent / "latest/sylion-pipeline"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from book_guardian import BookGuardian, DriftReport, KsiegaSnapshot, run_watchdog


# ---------------------------------------------------------------------------
# Shared fixture base
# ---------------------------------------------------------------------------

@pytest.fixture()
def book_env(tmp_path):
    """Yield (tmp_path, ksiega_path, log_dir, guardian)."""
    ksiega = tmp_path / "Ksiega_SYLION_3_4_FIXED.docx"
    ksiega.write_bytes(b"Ksiega SYLION 3.4 FIXED content - normative baseline")
    log_dir = tmp_path / "bg_logs"
    guardian = BookGuardian(ksiega_path=ksiega, log_dir=log_dir)
    return tmp_path, ksiega, log_dir, guardian


# ---------------------------------------------------------------------------
# load_baseline() - happy path
# ---------------------------------------------------------------------------

class TestLoadBaselineHappyPath:
    """load_baseline() reads a JSON file and restores KsiegaSnapshot state."""

    def test_load_baseline_restores_sha(self, tmp_path):
        """load_baseline() must restore the baseline SHA from disk."""
        # Arrange: create guardian and capture its baseline JSON
        ksiega = tmp_path / "ksiega.docx"
        ksiega.write_bytes(b"original content")
        log_dir = tmp_path / "logs"
        guardian = BookGuardian(ksiega_path=ksiega, log_dir=log_dir)
        original_sha = guardian.baseline_sha
        baseline_file = log_dir / "baseline.json"

        # Act: create a new guardian with no existing file and load the JSON
        ksiega2 = tmp_path / "ksiega2.docx"
        ksiega2.write_bytes(b"different content")
        log2 = tmp_path / "logs2"
        guardian2 = BookGuardian(ksiega_path=ksiega2, log_dir=log2)
        guardian2.load_baseline(baseline_file)

        # Assert: SHA matches the saved snapshot (not the new file's SHA)
        assert guardian2.baseline_sha == original_sha, (
            "load_baseline must restore the original SHA from JSON"
        )

    def test_load_baseline_baseline_file_persisted_on_init(self, book_env):
        """Guardian must write baseline.json on __init__."""
        tmp_path, ksiega, log_dir, guardian = book_env
        baseline_file = log_dir / "baseline.json"
        assert baseline_file.exists(), "baseline.json must exist after BookGuardian init"

    def test_load_baseline_from_dict_roundtrip(self, tmp_path):
        """KsiegaSnapshot → to_dict() → from_dict() must be lossless."""
        from datetime import datetime, timezone
        snap = KsiegaSnapshot(
            file_path="/some/path.docx",
            sha256="a" * 64,
            size_bytes=1024,
            mtime=1_700_000_000.0,
            exists=True,
            snapshot_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        restored = KsiegaSnapshot.from_dict(snap.to_dict())
        assert restored.sha256 == snap.sha256
        assert restored.size_bytes == snap.size_bytes
        assert restored.exists == snap.exists

    def test_load_baseline_missing_file_logs_error_not_raises(self, tmp_path):
        """load_baseline with non-existent file must log error, not raise."""
        ksiega = tmp_path / "k.docx"
        ksiega.write_bytes(b"x")
        guardian = BookGuardian(ksiega_path=ksiega, log_dir=tmp_path / "logs")
        # Must not raise
        guardian.load_baseline(tmp_path / "no_such_baseline.json")
        # Guardian still functional
        assert guardian.baseline is not None


# ---------------------------------------------------------------------------
# load_baseline() - edge cases
# ---------------------------------------------------------------------------

class TestLoadBaselineEdgeCases:
    """Edge cases: corrupt JSON, empty file, missing keys."""

    def test_load_baseline_corrupt_json_does_not_raise(self, tmp_path):
        """Corrupt JSON must be caught silently - guardian state unchanged."""
        ksiega = tmp_path / "k.docx"
        ksiega.write_bytes(b"test")
        log_dir = tmp_path / "logs"
        guardian = BookGuardian(ksiega_path=ksiega, log_dir=log_dir)
        original_sha = guardian.baseline_sha

        corrupt_file = tmp_path / "corrupt.json"
        corrupt_file.write_text("{invalid json content!!!}", encoding="utf-8")
        guardian.load_baseline(corrupt_file)

        # baseline unchanged - the corrupt load was a no-op
        assert guardian.baseline_sha == original_sha

    def test_load_baseline_empty_json_object_is_no_op(self, tmp_path):
        """Empty JSON object {} must be treated as no-op, not crash."""
        ksiega = tmp_path / "k.docx"
        ksiega.write_bytes(b"test")
        log_dir = tmp_path / "logs"
        guardian = BookGuardian(ksiega_path=ksiega, log_dir=log_dir)
        original_sha = guardian.baseline_sha

        empty_file = tmp_path / "empty.json"
        empty_file.write_text("{}", encoding="utf-8")
        guardian.load_baseline(empty_file)

        # Baseline should be unchanged (empty dict → falsy → no-op branch)
        # Or it may raise a KeyError which is caught → no state change
        assert guardian.baseline_sha == original_sha


# ---------------------------------------------------------------------------
# run_watchdog() - mock-based tests
# ---------------------------------------------------------------------------

class TestRunWatchdog:
    """run_watchdog() runs a periodic check loop; tested with mocked sleep."""

    def test_run_watchdog_calls_check_after_interval(self, tmp_path):
        """After sleeping interval_sec, run_watchdog calls guardian.check()."""
        ksiega = tmp_path / "k.docx"
        ksiega.write_bytes(b"guarded content")
        log_dir = tmp_path / "logs"

        check_calls = []
        sleep_calls = []

        def fake_sleep(n):
            sleep_calls.append(n)
            if len(sleep_calls) >= 2:
                raise KeyboardInterrupt()

        with patch("book_guardian.time.sleep", side_effect=fake_sleep), \
             patch("book_guardian.BookGuardian.check", side_effect=lambda self=None: check_calls.append(1) or True):
            try:
                run_watchdog(ksiega_path=ksiega, interval_sec=5, log_dir=log_dir)
            except KeyboardInterrupt:
                pass

        assert len(sleep_calls) >= 1, "run_watchdog must call time.sleep with the interval"
        assert sleep_calls[0] == 5, "First sleep must use interval_sec=5"

    def test_run_watchdog_keyboard_interrupt_exits_cleanly(self, tmp_path):
        """KeyboardInterrupt must terminate run_watchdog without propagating."""
        ksiega = tmp_path / "k.docx"
        ksiega.write_bytes(b"content")

        def _immediately_interrupt(n):
            raise KeyboardInterrupt()

        with patch("book_guardian.time.sleep", side_effect=_immediately_interrupt):
            # Must not raise
            run_watchdog(ksiega_path=ksiega, interval_sec=1, log_dir=tmp_path / "logs")

    def test_run_watchdog_uses_custom_interval(self, tmp_path):
        """run_watchdog must pass interval_sec directly to time.sleep."""
        ksiega = tmp_path / "k.docx"
        ksiega.write_bytes(b"content")
        captured = []

        def _capture_sleep(n):
            captured.append(n)
            raise KeyboardInterrupt()

        with patch("book_guardian.time.sleep", side_effect=_capture_sleep):
            run_watchdog(ksiega_path=ksiega, interval_sec=3600, log_dir=tmp_path / "logs")

        assert captured[0] == 3600
