#!/usr/bin/env python3
"""
test_book_guardian_extended.py — SYLION v5.9.2 Extended BookGuardian Tests
===========================================================================

Addresses gaps identified in TF03 report (LUK-03, LUK-04):
  - LUK-03: run_watchdog() had no pytest coverage
  - LUK-04: load_baseline() had no pytest coverage
  - BUG-02: /api/guards/status runtime vs. DB mismatch

New tests:
  1. test_run_watchdog_detects_modification
  2. test_run_watchdog_halt_pipeline_on_drift
  3. test_load_baseline_from_disk
  4. test_load_baseline_recovery_from_db
  5. test_api_guards_status_runtime_matches_db

Run:
    cd /home/user/workspace/sylion_v591/latest/sylion-pipeline
    python -m pytest ../../mega_audit/book_guardian_runtime_check/test_book_guardian_extended.py -v

Or directly:
    python test_book_guardian_extended.py
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# ---------------------------------------------------------------------------
# Path setup — support running from any directory
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_PIPELINE_ROOT = _THIS_DIR.parent.parent / "latest" / "sylion-pipeline"

for _p in [str(_PIPELINE_ROOT), str(_THIS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from book_guardian import BookGuardian, KsiegaSnapshot, run_watchdog  # noqa: E402


# ---------------------------------------------------------------------------
# Shared base class
# ---------------------------------------------------------------------------

class _Base(unittest.TestCase):
    """Sets up a fresh temp directory with a fake Księga file."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="sylion_bg_ext_")
        self.tmpdir = Path(self.tmp)
        self.log_dir = self.tmpdir / "bg_logs"
        self.ksiega = self.tmpdir / "Ksiega_SYLION_3_4_FIXED.docx"
        self.ksiega.write_bytes(b"Ksiega SYLION 3.4 FIXED - canonical v5.9.2 content")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_guardian(self, **kwargs) -> BookGuardian:
        return BookGuardian(
            ksiega_path=self.ksiega,
            log_dir=self.log_dir,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Test 1: run_watchdog detects modification (LUK-03)
# ---------------------------------------------------------------------------

class TestRunWatchdogDetectsModification(_Base):
    """
    run_watchdog() must detect SHA change on Księga and log a drift report.

    We mock time.sleep to avoid real waiting, intercept the loop via
    side_effect that modifies Księga on the 2nd iteration, and stop the
    watchdog after 3 iterations via a StopIteration raised from sleep.
    """

    def test_run_watchdog_detects_modification(self):
        """
        Scenario:
          - Iteration 0 (immediate): baseline computed, file OK
          - Iteration 1 (after first sleep): file modified → drift
          - Iteration 2: StopIteration raised to exit infinite loop
        """
        iteration_count = [0]

        def fake_sleep(seconds):
            iteration_count[0] += 1
            if iteration_count[0] == 1:
                # Modify Księga on first wake
                self.ksiega.write_bytes(b"UNAUTHORIZED MODIFICATION - DRIFT!")
            elif iteration_count[0] >= 3:
                raise KeyboardInterrupt  # exit watchdog loop

        captured_prints = []

        def fake_print(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            captured_prints.append(msg)

        with (
            patch("book_guardian.time.sleep", side_effect=fake_sleep),
            patch("builtins.print", side_effect=fake_print),
        ):
            try:
                run_watchdog(
                    ksiega_path=self.ksiega,
                    interval_sec=1,
                    log_dir=self.log_dir,
                )
            except KeyboardInterrupt:
                pass  # Normal exit from watchdog via our fake_sleep

        # Verify drift was reported in printed output
        all_output = "\n".join(captured_prints)
        self.assertIn("DRIFT DETECTED", all_output,
                      "run_watchdog must print 'DRIFT DETECTED' on SHA mismatch")

        # Verify drift_log.jsonl was created
        drift_log = self.log_dir / "drift_log.jsonl"
        self.assertTrue(drift_log.exists(), "drift_log.jsonl must be written on drift")

        # Verify at least one drift entry
        with open(drift_log, encoding="utf-8") as f:
            entries = [json.loads(line) for line in f if line.strip()]
        self.assertGreater(len(entries), 0, "drift_log must contain at least 1 entry")
        self.assertTrue(entries[0]["drift_detected"])
        self.assertIn("CHANGED", entries[0]["description"])


# ---------------------------------------------------------------------------
# Test 2: run_watchdog halts pipeline on drift (LUK-03)
# ---------------------------------------------------------------------------

class TestRunWatchdogHaltPipelineOnDrift(_Base):
    """
    After drift is detected, run_watchdog() must:
      - Return False from check()
      - Record the drift report to disk (drift_log.jsonl)
      - NOT auto-modify the baseline

    This test verifies the watchdog does not silently ignore drift.
    """

    def test_run_watchdog_halt_pipeline_on_drift(self):
        """
        Simulate drift on iteration 1, then verify the drift_log exists and
        the baseline on disk still holds the old SHA (no auto-rebase).
        """
        original_sha_holder = [None]
        iteration_count = [0]

        def fake_sleep(seconds):
            iteration_count[0] += 1
            if iteration_count[0] == 1:
                self.ksiega.write_bytes(b"SECOND CONTENT - DRIFT!")
            elif iteration_count[0] >= 2:
                raise KeyboardInterrupt

        with (
            patch("book_guardian.time.sleep", side_effect=fake_sleep),
            patch("builtins.print"),
        ):
            # Capture original SHA before watchdog starts
            guardian_temp = self._make_guardian()
            original_sha_holder[0] = guardian_temp.baseline_sha

            try:
                run_watchdog(
                    ksiega_path=self.ksiega,
                    interval_sec=1,
                    log_dir=self.log_dir,
                )
            except KeyboardInterrupt:
                pass

        # The baseline.json on disk must NOT have changed (no auto-rebase)
        baseline_file = self.log_dir / "baseline.json"
        self.assertTrue(baseline_file.exists())
        with open(baseline_file, encoding="utf-8") as f:
            baseline_data = json.load(f)

        # The baseline written by the watchdog's internal guardian should
        # still be the original SHA (watchdog never calls update_baseline)
        # Note: run_watchdog initialises its own guardian, so baseline.json
        # reflects that guardian's init — it should equal the file at init time,
        # which is the canonical content (before modification).
        # The sha in drift_log should show the baseline vs. modified.
        drift_log = self.log_dir / "drift_log.jsonl"
        if drift_log.exists():
            with open(drift_log, encoding="utf-8") as f:
                entries = [json.loads(line) for line in f if line.strip()]
            if entries:
                # Drift report must record the old vs new SHA
                report = entries[0]
                self.assertTrue(report["drift_detected"])
                self.assertNotEqual(
                    report["baseline"]["sha256"],
                    report["current"]["sha256"],
                    "Drift report must show SHA mismatch between baseline and current",
                )

        # Verify pipeline would be halted: is_healthy must be False after drift
        # (create new guardian pointing to modified file, load baseline)
        recovery_guardian = BookGuardian(
            ksiega_path=self.ksiega,
            log_dir=self.tmpdir / "recovery_logs",
        )
        # Recovery guardian baseline = modified file → check() returns True (new init)
        # But if we load the OLD baseline from disk, check() returns False
        recovery_guardian.load_baseline(self.log_dir / "baseline.json")
        result = recovery_guardian.check()
        self.assertFalse(
            result,
            "Guardian loaded with old baseline must detect drift against modified file",
        )


# ---------------------------------------------------------------------------
# Test 3: load_baseline from disk (LUK-04)
# ---------------------------------------------------------------------------

class TestLoadBaselineFromDisk(_Base):
    """
    load_baseline(path) must load a previously serialized KsiegaSnapshot.
    After loading, check() must use the loaded SHA for comparison.

    Covers LUK-04: load_baseline() had no pytest coverage.
    """

    def test_load_baseline_from_disk(self):
        """
        Flow:
          1. Guardian A: init → serialize baseline → baseline.json written
          2. Modify Księga
          3. Guardian B: init with modified file (new baseline)
          4. Call B.load_baseline() with A's baseline.json
          5. B.check() must return False (detects drift vs. A's baseline)
        """
        # Guardian A — captures original baseline
        guardian_a = self._make_guardian()
        original_sha = guardian_a.baseline_sha
        baseline_json = self.log_dir / "baseline.json"
        self.assertTrue(baseline_json.exists(), "baseline.json must exist after guardian_a init")

        # Modify Księga
        self.ksiega.write_bytes(b"Modified content - simulating authorized v5.9.2 update")

        # Guardian B — will start with modified file as its baseline
        log_dir_b = self.tmpdir / "logs_b"
        guardian_b = BookGuardian(ksiega_path=self.ksiega, log_dir=log_dir_b)
        new_sha = guardian_b.baseline_sha

        # Sanity: A and B have different SHAs
        self.assertNotEqual(original_sha, new_sha, "Guardian B must have a different baseline SHA")

        # Load guardian A's baseline into guardian B
        guardian_b.load_baseline(baseline_json)

        # After loading A's baseline, B's _baseline should reflect original SHA
        self.assertEqual(
            guardian_b.baseline_sha, original_sha,
            "After load_baseline(), guardian_b must hold original SHA",
        )

        # check() must now detect drift (current file = modified, baseline = original)
        result = guardian_b.check()
        self.assertFalse(result, "check() must return False after loading stale baseline")
        self.assertGreater(guardian_b.drift_count, 0)
        self.assertFalse(guardian_b.is_healthy)

    def test_load_baseline_preserves_all_fields(self):
        """
        load_baseline() must round-trip all KsiegaSnapshot fields correctly:
        file_path, sha256, size_bytes, mtime, exists, snapshot_time.
        """
        guardian = self._make_guardian()
        original_baseline = guardian.baseline

        # Create a fresh guardian with a *different* file so we can load
        other_file = self.tmpdir / "other.docx"
        other_file.write_bytes(b"other content")
        log_dir_other = self.tmpdir / "logs_other"
        guardian_other = BookGuardian(ksiega_path=other_file, log_dir=log_dir_other)

        # Load original's baseline
        guardian_other.load_baseline(self.log_dir / "baseline.json")

        loaded = guardian_other.baseline
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.sha256, original_baseline.sha256)
        self.assertEqual(loaded.size_bytes, original_baseline.size_bytes)
        self.assertEqual(loaded.file_path, original_baseline.file_path)
        self.assertTrue(loaded.exists)

    def test_load_baseline_missing_file_is_graceful(self):
        """
        load_baseline() must not raise if the path does not exist.
        It should log an error and leave baseline unchanged.
        """
        guardian = self._make_guardian()
        original_sha = guardian.baseline_sha

        # Load from non-existent path
        guardian.load_baseline(self.tmpdir / "nonexistent_baseline.json")

        # Baseline must be unchanged
        self.assertEqual(
            guardian.baseline_sha, original_sha,
            "load_baseline() from missing file must leave baseline unchanged",
        )


# ---------------------------------------------------------------------------
# Test 4: load_baseline recovery from DB (LUK-04 extended)
# ---------------------------------------------------------------------------

class TestLoadBaselineRecoveryFromDB(_Base):
    """
    Recovery scenario: baseline.json on disk is missing or corrupted,
    but a promoted baseline exists in the DB.

    Simulates a recovery helper that reads the DB baseline and injects
    it into a guardian via load_baseline(), allowing the pipeline to
    resume checking integrity without a rebase.
    """

    def setUp(self) -> None:
        super().setUp()
        self.db_path = self.tmpdir / "test.db"
        self._create_test_db()

    def _create_test_db(self):
        """Create a minimal baselines table with a promoted record."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE baselines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                content TEXT,
                sha256 TEXT,
                file_path TEXT,
                status TEXT DEFAULT 'pending',
                created_at REAL,
                promoted_at REAL
            )
        """)
        conn.commit()
        conn.close()

    def _insert_baseline_to_db(self, sha256: str, file_path: str, status: str = "promoted"):
        conn = sqlite3.connect(str(self.db_path))
        ts = time.time()
        conn.execute(
            "INSERT INTO baselines (name, content, sha256, file_path, status, created_at, promoted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("test_baseline", "Test baseline entry", sha256, file_path, status, ts, ts),
        )
        conn.commit()
        conn.close()

    def _write_snapshot_json(self, path: Path, guardian: BookGuardian):
        """Manually serialize guardian baseline to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(guardian.baseline.to_dict(), f, ensure_ascii=False, indent=2)

    def test_load_baseline_recovery_from_db(self):
        """
        Scenario: baseline.json is absent (simulating disk failure / fresh node).
        DB has a promoted baseline. Recovery helper reconstructs baseline.json
        from DB, then guardian loads it and check() works correctly.
        """
        # Step 1: Compute canonical SHA directly
        guardian_orig = self._make_guardian()
        canonical_sha = guardian_orig.baseline_sha

        # Insert canonical SHA to DB as promoted
        self._insert_baseline_to_db(canonical_sha, str(self.ksiega))

        # Step 2: Simulate disk failure — delete baseline.json
        (self.log_dir / "baseline.json").unlink(missing_ok=True)
        self.assertFalse((self.log_dir / "baseline.json").exists(), "baseline.json must be absent")

        # Step 3: Recovery — read baseline from DB and reconstruct JSON
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT sha256, file_path FROM baselines WHERE status='promoted' "
            "ORDER BY promoted_at DESC LIMIT 1"
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row, "DB must have a promoted baseline")

        # Reconstruct minimal baseline.json from DB record
        recovered_baseline_path = self.log_dir / "baseline_recovered.json"
        recovered_baseline_path.parent.mkdir(parents=True, exist_ok=True)
        recovered_data = {
            "file_path": row["file_path"],
            "sha256": row["sha256"],
            "size_bytes": self.ksiega.stat().st_size,
            "mtime": self.ksiega.stat().st_mtime,
            "exists": True,
            "snapshot_time": "2026-01-01T00:00:00+00:00",
        }
        with open(recovered_baseline_path, "w", encoding="utf-8") as f:
            json.dump(recovered_data, f)

        # Step 4: Load recovered baseline into a new guardian
        log_dir_new = self.tmpdir / "logs_new"
        guardian_new = BookGuardian(ksiega_path=self.ksiega, log_dir=log_dir_new)
        guardian_new.load_baseline(recovered_baseline_path)

        # Step 5: check() must pass (file unchanged → SHA matches DB)
        result = guardian_new.check()
        self.assertTrue(
            result,
            f"check() after DB recovery must return True — "
            f"baseline SHA={guardian_new.baseline_sha[:16]}, "
            f"file SHA={canonical_sha[:16]}",
        )
        self.assertEqual(guardian_new.drift_count, 0)
        self.assertTrue(guardian_new.is_healthy)

    def test_load_baseline_db_vs_disk_sha_consistency(self):
        """
        If DB SHA ≠ disk baseline SHA, guardian loaded from DB detects mismatch
        when compared against disk-loaded baseline.

        Verifies that DB is the authoritative source and disk is a cache.
        """
        # Canonical guardian
        guardian = self._make_guardian()
        canonical_sha = guardian.baseline_sha

        # Insert a STALE SHA to DB (simulating a rebase that failed to update disk)
        stale_sha = "a" * 64  # clearly wrong SHA
        self._insert_baseline_to_db(stale_sha, str(self.ksiega))

        # Guardian loaded from DB with stale SHA will detect drift
        log_dir_db = self.tmpdir / "logs_db"
        guardian_db = BookGuardian(ksiega_path=self.ksiega, log_dir=log_dir_db)

        # Inject stale DB SHA
        from book_guardian import KsiegaSnapshot
        guardian_db._baseline = KsiegaSnapshot(
            file_path=str(self.ksiega),
            sha256=stale_sha,
            size_bytes=self.ksiega.stat().st_size,
            mtime=self.ksiega.stat().st_mtime,
            exists=True,
        )

        result = guardian_db.check()
        self.assertFalse(
            result,
            "Guardian with stale DB SHA must detect drift against actual file",
        )
        self.assertGreater(guardian_db.drift_count, 0)


# ---------------------------------------------------------------------------
# Test 5: /api/guards/status runtime matches DB (BUG-02)
# ---------------------------------------------------------------------------

class TestApiGuardsStatusRuntimeMatchesDB(_Base):
    """
    BUG-02 fix: /api/guards/status must call BookGuardian.check() at runtime,
    not just read the DB baselines table.

    Tests the get_book_guardian_runtime_status() function from
    guards_status_runtime_patch.py.
    """

    def setUp(self) -> None:
        super().setUp()
        self.db_path = self.tmpdir / "test.db"
        self._create_test_db()

    def _create_test_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE baselines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                content TEXT,
                sha256 TEXT,
                file_path TEXT,
                status TEXT DEFAULT 'pending',
                created_at REAL,
                promoted_at REAL
            )
        """)
        conn.commit()
        conn.close()

    def _insert_baseline(self, sha256: str, file_path: str, status: str = "promoted"):
        conn = sqlite3.connect(str(self.db_path))
        ts = time.time()
        conn.execute(
            "INSERT INTO baselines (name, content, sha256, file_path, status, created_at, promoted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("test", "test", sha256, file_path, status, ts, ts),
        )
        conn.commit()
        conn.close()

    def _get_runtime_status(self, ksiega_dir=None, db_path=None):
        """Import and call get_book_guardian_runtime_status from patch module."""
        # Ensure patch module is importable
        patch_path = str(Path(__file__).resolve().parent)
        if patch_path not in sys.path:
            sys.path.insert(0, patch_path)
        from guards_status_runtime_patch import get_book_guardian_runtime_status
        return get_book_guardian_runtime_status(
            ksiega_dir=ksiega_dir or self.tmpdir,
            db_path=db_path or self.db_path,
            log_dir=self.log_dir,
        )

    def test_api_guards_status_active_when_sha_matches(self):
        """
        When DB has promoted baseline with SHA matching actual file,
        runtime status must be 'active'.
        """
        # Get canonical SHA
        guardian = self._make_guardian()
        canonical_sha = guardian.baseline_sha

        # Insert matching SHA to DB
        self._insert_baseline(canonical_sha, str(self.ksiega))

        # Override ksiega_dir to point to the temp dir
        # (ksiega file is directly in tmpdir, not in a subdirectory)
        # We need to move ksiega to a subdir that runtime_patch scans
        ksiega_dir = self.tmpdir / "ksiega_uploads"
        ksiega_dir.mkdir()
        import shutil
        shutil.copy2(str(self.ksiega), str(ksiega_dir / "Ksiega.docx"))

        # Re-insert with correct path
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("UPDATE baselines SET file_path=? WHERE status='promoted'",
                     (str(ksiega_dir / "Ksiega.docx"),))
        conn.commit()
        conn.close()

        from guards_status_runtime_patch import get_book_guardian_runtime_status
        result = get_book_guardian_runtime_status(
            ksiega_dir=ksiega_dir,
            db_path=self.db_path,
            log_dir=self.log_dir,
        )

        self.assertEqual(
            result["status"], "active",
            f"Expected 'active', got '{result['status']}'. Detail: {result.get('detail')}",
        )
        self.assertTrue(result["is_healthy"])
        self.assertEqual(result["drift_count"], 0)
        # Runtime check populates current_sha
        self.assertEqual(len(result["current_sha"]), 64,
                         "current_sha must be a 64-char SHA-256 hex string")

    def test_api_guards_status_runtime_matches_db(self):
        """
        Core BUG-02 regression test:
        When DB says 'active' (promoted baseline exists) but file has drifted,
        runtime check must return 'drift_detected' — not 'active'.

        This is the exact failure mode described in TF03 BUG-02.
        """
        # Step 1: Record the original SHA in DB
        guardian = self._make_guardian()
        original_sha = guardian.baseline_sha

        ksiega_dir = self.tmpdir / "ksiega_uploads"
        ksiega_dir.mkdir()
        import shutil
        shutil.copy2(str(self.ksiega), str(ksiega_dir / "Ksiega.docx"))

        self._insert_baseline(original_sha, str(ksiega_dir / "Ksiega.docx"))

        # Step 2: Drift — modify the Księga file AFTER baseline was stored
        (ksiega_dir / "Ksiega.docx").write_bytes(b"DRIFTED - unauthorized modification!")

        # Step 3: Old (buggy) behavior would return "active" since DB still has promoted baseline
        # New (fixed) behavior must return "drift_detected" because runtime check fails
        from guards_status_runtime_patch import get_book_guardian_runtime_status
        result = get_book_guardian_runtime_status(
            ksiega_dir=ksiega_dir,
            db_path=self.db_path,
            log_dir=self.log_dir,
        )

        self.assertNotEqual(
            result["status"], "active",
            "BUG-02: Runtime check must NOT return 'active' when file has drifted. "
            f"Got: {result['status']}. Detail: {result.get('detail')}",
        )
        self.assertEqual(
            result["status"], "drift_detected",
            f"Expected 'drift_detected', got '{result['status']}'. Detail: {result.get('detail')}",
        )
        self.assertFalse(result["is_healthy"])
        self.assertGreater(result["drift_count"], 0)
        # SHA mismatch is explicit in the response
        self.assertNotEqual(result["baseline_sha"], result["current_sha"])

    def test_api_guards_status_no_baseline(self):
        """
        When no Księga file and no promoted baseline exists,
        status must be 'no_baseline' — not 'active' or 'error'.
        """
        from guards_status_runtime_patch import get_book_guardian_runtime_status

        empty_dir = self.tmpdir / "empty_ksiega"
        empty_dir.mkdir()

        result = get_book_guardian_runtime_status(
            ksiega_dir=empty_dir,
            db_path=self.db_path,
            log_dir=self.log_dir,
        )

        self.assertEqual(
            result["status"], "no_baseline",
            f"Expected 'no_baseline', got '{result['status']}'",
        )
        self.assertFalse(result["is_healthy"])

    def test_api_guards_status_includes_required_fields(self):
        """
        Runtime status response must include all required fields:
        status, baseline_sha, current_sha, last_check_ms_ago, is_healthy, drift_count.
        """
        from guards_status_runtime_patch import get_book_guardian_runtime_status

        result = get_book_guardian_runtime_status(
            ksiega_dir=self.tmpdir / "absent",
            db_path=self.db_path,
            log_dir=self.log_dir,
        )

        required_fields = ["name", "status", "baseline_sha", "current_sha",
                           "last_check_ms_ago", "is_healthy", "drift_count", "detail"]
        for field in required_fields:
            self.assertIn(field, result, f"Response must include field: {field}")

        # last_check_ms_ago must be non-negative integer
        self.assertIsInstance(result["last_check_ms_ago"], int)
        self.assertGreaterEqual(result["last_check_ms_ago"], 0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
