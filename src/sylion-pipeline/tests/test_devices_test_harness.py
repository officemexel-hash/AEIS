"""Comprehensive tests for sylion.devices.test_harness (OnDeviceTestHarness)."""

import sqlite3
import threading
import time

import pytest

from sylion.devices.test_harness import (
    OnDeviceTestHarness,
    get_on_device_test_harness,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def harness():
    """Fresh in-memory OnDeviceTestHarness per test."""
    return OnDeviceTestHarness()


@pytest.fixture
def populated_harness(harness):
    """Harness with test runs across multiple devices and suites."""
    results = []
    for suite in ["contract", "integration", "e2e"]:
        for dev in ["dev-alpha", "dev-beta"]:
            r = harness.run_test(dev, suite)
            results.append(r)
    return harness, results


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

class TestInstantiation:
    def test_default_in_memory(self):
        h = OnDeviceTestHarness()
        assert h._db_path == ":memory:"

    def test_custom_db_path(self, tmp_path):
        db_file = str(tmp_path / "test_harness.db")
        h = OnDeviceTestHarness(db_path=db_file)
        assert h._db_path == db_file

    def test_tables_created(self, harness):
        """Verify the device_tests table was created."""
        row = harness._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='device_tests'"
        ).fetchone()
        assert row is not None


# ---------------------------------------------------------------------------
# Run test
# ---------------------------------------------------------------------------

class TestRunTest:
    def test_run_basic(self, harness):
        result = harness.run_test("dev-001")
        assert result["device_id"] == "dev-001"
        assert result["status"] == "passed"
        assert result["pass_rate"] == 1.0

    def test_run_with_suite(self, harness):
        result = harness.run_test("dev-001", suite="integration")
        assert result["suite"] == "integration"

    def test_run_default_suite(self, harness):
        result = harness.run_test("dev-001")
        assert result["suite"] == "contract"

    def test_run_generates_test_id(self, harness):
        result = harness.run_test("dev-001")
        assert result["test_id"].startswith("tst-")
        assert len(result["test_id"]) > 4

    def test_run_has_duration(self, harness):
        result = harness.run_test("dev-001")
        assert result["duration_ms"] > 0

    def test_run_has_logs_hash(self, harness):
        result = harness.run_test("dev-001")
        assert result["logs_hash"] != ""

    def test_run_has_timestamp(self, harness):
        before = time.time()
        result = harness.run_test("dev-001")
        after = time.time()
        assert before <= result["ran_at"] <= after

    def test_run_unique_test_ids(self, harness):
        r1 = harness.run_test("dev-001")
        r2 = harness.run_test("dev-001")
        assert r1["test_id"] != r2["test_id"]

    def test_run_persists_to_db(self, harness):
        result = harness.run_test("dev-001", suite="e2e")
        record = harness.get_results(result["test_id"])
        assert record is not None
        assert record["device_id"] == "dev-001"
        assert record["suite"] == "e2e"

    def test_run_multiple_suites(self, harness):
        for suite in ["contract", "integration", "e2e", "regression"]:
            result = harness.run_test("dev-001", suite=suite)
            assert result["suite"] == suite


# ---------------------------------------------------------------------------
# Get results
# ---------------------------------------------------------------------------

class TestGetResults:
    def test_get_existing(self, populated_harness):
        harness, results = populated_harness
        test_id = results[0]["test_id"]
        record = harness.get_results(test_id)
        assert record is not None
        assert record["test_id"] == test_id

    def test_get_not_found(self, harness):
        assert harness.get_results("nonexistent-id") is None

    def test_get_returns_all_fields(self, populated_harness):
        harness, results = populated_harness
        record = harness.get_results(results[0]["test_id"])
        expected_keys = {
            "test_id", "device_id", "suite", "status",
            "pass_rate", "logs_hash", "duration_ms", "ran_at",
        }
        assert expected_keys.issubset(record.keys())


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------

class TestListTests:
    def test_list_all(self, populated_harness):
        harness, _ = populated_harness
        results = harness.list_tests()
        assert len(results) == 6  # 3 suites * 2 devices

    def test_list_filter_by_device(self, populated_harness):
        harness, _ = populated_harness
        results = harness.list_tests(device_id="dev-alpha")
        assert len(results) == 3
        assert all(r["device_id"] == "dev-alpha" for r in results)

    def test_list_filter_no_match(self, populated_harness):
        harness, _ = populated_harness
        results = harness.list_tests(device_id="nonexistent")
        assert results == []

    def test_list_limit(self, populated_harness):
        harness, _ = populated_harness
        results = harness.list_tests(limit=2)
        assert len(results) == 2

    def test_list_ordered_by_ran_at_desc(self, populated_harness):
        harness, _ = populated_harness
        results = harness.list_tests()
        timestamps = [r["ran_at"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_list_empty(self, harness):
        results = harness.list_tests()
        assert results == []

    def test_list_default_limit(self, harness):
        # Add more than 100 entries
        for i in range(110):
            harness.run_test("dev-many", suite="contract")
        results = harness.list_tests()
        assert len(results) == 100


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_stats_empty_device(self, harness):
        stats = harness.get_stats("dev-none")
        assert stats["total"] == 0
        assert stats["passed"] == 0
        assert stats["failed"] == 0
        assert stats["pass_rate"] == 0.0

    def test_stats_with_results(self, populated_harness):
        harness, _ = populated_harness
        stats = harness.get_stats("dev-alpha")
        assert stats["total"] == 3
        assert stats["passed"] == 3
        assert stats["failed"] == 0
        assert stats["pass_rate"] == 1.0

    def test_stats_multiple_devices(self, populated_harness):
        harness, _ = populated_harness
        for dev in ["dev-alpha", "dev-beta"]:
            stats = harness.get_stats(dev)
            assert stats["total"] == 3

    def test_stats_per_device_isolation(self, populated_harness):
        harness, _ = populated_harness
        alpha = harness.get_stats("dev-alpha")
        beta = harness.get_stats("dev-beta")
        assert alpha["total"] == beta["total"]


# ---------------------------------------------------------------------------
# Event bus integration
# ---------------------------------------------------------------------------

class TestEventBusIntegration:
    def test_run_test_emits_event(self):
        published = []

        class MockBus:
            def publish(self, event):
                published.append(event)

        h = OnDeviceTestHarness(event_bus=MockBus())
        h.run_test("dev-001")

        assert len(published) == 1
        assert published[0].topic == "device.test.completed"
        assert published[0].payload["device_id"] == "dev-001"
        assert published[0].payload["status"] == "passed"

    def test_no_event_without_bus(self, harness):
        """Should not crash when no event_bus is provided."""
        result = harness.run_test("dev-001")
        assert result["status"] == "passed"


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_factory_returns_instance(self):
        inst = get_on_device_test_harness()
        assert isinstance(inst, OnDeviceTestHarness)

    def test_factory_idempotent(self):
        a = get_on_device_test_harness()
        b = get_on_device_test_harness()
        assert a is b


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_run_tests(self, harness):
        errors = []
        results = []
        retriable = (sqlite3.OperationalError, sqlite3.InterfaceError)

        def run_one(idx):
            for attempt in range(8):
                try:
                    r = harness.run_test(f"dev-thread-{idx % 3}", suite="contract")
                    results.append(r)
                    return
                except retriable:
                    if attempt == 7:
                        errors.append(RuntimeError(f"run_test gave up at {idx}"))
                    time.sleep(0.05 * (2 ** attempt))
                except Exception as e:
                    errors.append(e)
                    return

        threads = [threading.Thread(target=run_one, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors
        assert len(results) == 30

    def test_concurrent_reads_and_writes(self, harness):
        errors = []
        retriable = (sqlite3.OperationalError, sqlite3.InterfaceError, IndexError)
        write_count = [0]  # mutable counter for closure
        count_lock = threading.Lock()

        # Seed some data
        for i in range(5):
            harness.run_test("dev-seed", suite="contract")

        def writer():
            for i in range(10):
                for attempt in range(8):
                    try:
                        harness.run_test("dev-writer", suite="integration")
                        with count_lock:
                            write_count[0] += 1
                        break
                    except retriable:
                        if attempt == 7:
                            errors.append(RuntimeError(f"writer gave up at {i}"))
                        time.sleep(0.05 * (2 ** attempt))
                    except Exception as e:
                        errors.append(e)
                        break

        def reader():
            for _ in range(10):
                for attempt in range(8):
                    try:
                        harness.list_tests()
                        break
                    except retriable:
                        if attempt == 7:
                            errors.append(RuntimeError("reader gave up"))
                        time.sleep(0.05 * (2 ** attempt))
                    except Exception as e:
                        errors.append(e)
                        break

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Ensure all threads completed
        assert all(not t.is_alive() for t in threads)
        assert not errors
        assert write_count[0] >= 20
        # 5 seed + write_count writer entries
        all_tests = harness.list_tests(limit=1000)
        assert len(all_tests) >= 5 + 20


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_run_test_empty_device_id(self, harness):
        result = harness.run_test("")
        assert result["device_id"] == ""
        assert result["status"] == "passed"

    def test_run_test_unicode_device_id(self, harness):
        result = harness.run_test("\u4f60\u597d-world")
        assert result["device_id"] == "\u4f60\u597d-world"

    def test_stats_after_many_runs(self, harness):
        for i in range(50):
            harness.run_test("dev-heavy", suite="contract")
        stats = harness.get_stats("dev-heavy")
        assert stats["total"] == 50
        assert stats["pass_rate"] == 1.0
