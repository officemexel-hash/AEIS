"""Tests for sylion.cellular.rf_isolation — RFIsolationValidator.

Covers every public method: validate, get, latest, is_valid, list_checks.
No mocking — real in-memory SQLite instances.
"""
import json
import sqlite3
import time

import pytest

from sylion.cellular.rf_isolation import RFIsolationValidator, get_rf_isolation_validator
from sylion.core.event_bus import EventBus


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def rf(bus):
    return RFIsolationValidator(event_bus=bus)


# =====================================================================
# _classify (static threshold logic)
# =====================================================================

class TestClassify:
    """Static method _classify — boundary logic for PASS / WARN / FAIL."""

    def test_pass_below_minus_90(self):
        assert RFIsolationValidator._classify(-100) == "PASS"
        assert RFIsolationValidator._classify(-91) == "PASS"
        assert RFIsolationValidator._classify(-120) == "PASS"

    def test_warn_minus_90_to_minus_81(self):
        assert RFIsolationValidator._classify(-90) == "WARN"
        assert RFIsolationValidator._classify(-85) == "WARN"
        assert RFIsolationValidator._classify(-81) == "WARN"

    def test_fail_minus_80_and_above(self):
        assert RFIsolationValidator._classify(-80) == "FAIL"
        assert RFIsolationValidator._classify(-70) == "FAIL"
        assert RFIsolationValidator._classify(0) == "FAIL"


# =====================================================================
# validate
# =====================================================================

class TestValidate:
    def test_returns_check_id(self, rf):
        result = rf.validate(1800e6, -100)
        assert "check_id" in result
        assert len(result["check_id"]) == 12

    def test_stores_frequency(self, rf):
        result = rf.validate(1800e6, -100)
        assert result["experiment_freq"] == 1800e6

    def test_stores_measurement(self, rf):
        result = rf.validate(900e6, -95)
        assert result["measurement_dbm"] == -95

    def test_result_pass(self, rf):
        result = rf.validate(1800e6, -100)
        assert result["result"] == "PASS"

    def test_result_warn(self, rf):
        result = rf.validate(1800e6, -85)
        assert result["result"] == "WARN"

    def test_result_fail(self, rf):
        result = rf.validate(1800e6, -70)
        assert result["result"] == "FAIL"

    def test_monitor_sdr_stored(self, rf):
        result = rf.validate(1800e6, -100, monitor_sdr="hackrf-001")
        assert result["monitor_sdr"] == "hackrf-001"

    def test_monitor_sdr_default_empty(self, rf):
        result = rf.validate(1800e6, -100)
        assert result["monitor_sdr"] == ""

    def test_harmonics_none_defaults_empty_list(self, rf):
        result = rf.validate(1800e6, -100, harmonics=None)
        assert result["harmonics"] == []

    def test_harmonics_stored(self, rf):
        h = [{"freq": 3600e6, "dbm": -110}, {"freq": 5400e6, "dbm": -115}]
        result = rf.validate(1800e6, -100, harmonics=h)
        assert len(result["harmonics"]) == 2
        assert result["harmonics"][0]["freq"] == 3600e6
        assert result["harmonics"][1]["freq"] == 5400e6

    def test_valid_until_is_future(self, rf):
        before = time.time() + 3599
        result = rf.validate(1800e6, -100)
        after = time.time() + 3601
        assert result["valid_until"] > before or result["valid_until"] >= time.time() + 3599
        assert result["valid_until"] < time.time() + 3605

    def test_emits_event(self, bus, rf):
        rf.validate(1800e6, -100)
        events = bus.query(topic="cellular.rf.isolation.checked")
        assert len(events) == 1

    def test_event_payload(self, bus, rf):
        rf.validate(2100e6, -88, monitor_sdr="usrp-1")
        events = bus.query(topic="cellular.rf.isolation.checked")
        payload = events[0]["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["frequency"] == 2100e6
        assert payload["measurement_dbm"] == -88
        assert payload["result"] == "WARN"

    def test_multiple_validates(self, rf):
        rf.validate(900e6, -100)
        rf.validate(1800e6, -95)
        rf.validate(2100e6, -70)
        checks = rf.list_checks()
        assert len(checks) == 3

    def test_without_event_bus(self):
        rf_no_bus = RFIsolationValidator()
        result = rf_no_bus.validate(1800e6, -100)
        assert result["result"] == "PASS"


# =====================================================================
# get
# =====================================================================

class TestGet:
    def test_get_existing(self, rf):
        result = rf.validate(900e6, -100)
        fetched = rf.get(result["check_id"])
        assert fetched is not None
        assert fetched["check_id"] == result["check_id"]
        assert fetched["experiment_freq"] == 900e6

    def test_get_nonexistent(self, rf):
        assert rf.get("nonexistent_id") is None

    def test_get_returns_parsed_harmonics(self, rf):
        rf.validate(1800e6, -100, harmonics=[{"freq": 3600e6, "dbm": -110}])
        checks = rf.list_checks()
        fetched = rf.get(checks[0]["check_id"])
        assert isinstance(fetched["harmonics"], list)
        assert len(fetched["harmonics"]) == 1

    def test_get_after_multiple_inserts(self, rf):
        r1 = rf.validate(900e6, -100)
        r2 = rf.validate(1800e6, -95)
        assert rf.get(r1["check_id"])["experiment_freq"] == 900e6
        assert rf.get(r2["check_id"])["experiment_freq"] == 1800e6


# =====================================================================
# latest
# =====================================================================

class TestLatest:
    def test_latest_none_when_empty(self, rf):
        assert rf.latest() is None

    def test_latest_returns_most_recent(self, rf):
        r1 = rf.validate(900e6, -100)
        r2 = rf.validate(1800e6, -95)
        latest = rf.latest()
        assert latest is not None
        assert latest["check_id"] == r2["check_id"]

    def test_latest_returns_parsed_harmonics(self, rf):
        rf.validate(1800e6, -100, harmonics=[{"freq": 3600e6, "dbm": -110}])
        latest = rf.latest()
        assert isinstance(latest["harmonics"], list)
        assert len(latest["harmonics"]) == 1


# =====================================================================
# is_valid
# =====================================================================

class TestIsValid:
    def test_valid_fresh_pass(self, rf):
        rf.validate(1800e6, -100)
        assert rf.is_valid(1800e6) is True

    def test_invalid_fresh_warn(self, rf):
        rf.validate(1800e6, -85)
        assert rf.is_valid(1800e6) is False

    def test_invalid_fresh_fail(self, rf):
        rf.validate(1800e6, -70)
        assert rf.is_valid(1800e6) is False

    def test_invalid_no_check(self, rf):
        assert rf.is_valid(9999) is False

    def test_invalid_after_expiry(self, rf):
        result = rf.validate(1800e6, -100)
        # Manually expire the check
        with rf._lock:
            rf._conn.execute(
                "UPDATE isolation_checks SET valid_until = ? WHERE check_id = ?",
                (time.time() - 1, result["check_id"])
            )
            rf._conn.commit()
        assert rf.is_valid(1800e6) is False

    def test_different_frequencies_independent(self, rf):
        rf.validate(900e6, -100)   # PASS
        rf.validate(1800e6, -70)   # FAIL
        assert rf.is_valid(900e6) is True
        assert rf.is_valid(1800e6) is False

    def test_latest_pass_overrides_earlier_fail(self, rf):
        rf.validate(1800e6, -70)   # FAIL
        rf.validate(1800e6, -100)  # PASS (newer)
        assert rf.is_valid(1800e6) is True


# =====================================================================
# list_checks
# =====================================================================

class TestListChecks:
    def test_empty(self, rf):
        assert rf.list_checks() == []

    def test_returns_all(self, rf):
        rf.validate(900e6, -100)
        rf.validate(1800e6, -95)
        checks = rf.list_checks()
        assert len(checks) == 2

    def test_respects_limit(self, rf):
        for i in range(5):
            rf.validate(900e6 + i * 1e6, -100)
        checks = rf.list_checks(limit=3)
        assert len(checks) == 3

    def test_ordered_by_valid_until_desc(self, rf):
        r1 = rf.validate(900e6, -100)
        r2 = rf.validate(1800e6, -95)
        checks = rf.list_checks()
        assert checks[0]["check_id"] == r2["check_id"]
        assert checks[1]["check_id"] == r1["check_id"]

    def test_harmonics_parsed_in_list(self, rf):
        rf.validate(1800e6, -100, harmonics=[{"freq": 3600e6, "dbm": -110}])
        checks = rf.list_checks()
        assert isinstance(checks[0]["harmonics"], list)


# =====================================================================
# get_rf_isolation_validator (module-level singleton)
# =====================================================================

class TestGetValidator:
    def test_returns_instance(self):
        # Reset global state for isolation
        import sylion.cellular.rf_isolation as mod
        mod._var = None
        validator = get_rf_isolation_validator()
        assert isinstance(validator, RFIsolationValidator)
        mod._var = None  # cleanup

    def test_singleton(self):
        import sylion.cellular.rf_isolation as mod
        mod._var = None
        v1 = get_rf_isolation_validator()
        v2 = get_rf_isolation_validator()
        assert v1 is v2
        mod._var = None  # cleanup


# =====================================================================
# Thread safety (basic smoke)
# =====================================================================

class TestThreadSafety:
    def test_sequential_concurrent_validates(self, rf):
        """Each thread creates then reads its own record. The module lock
        serialises writes; reads happen after all writes complete."""
        import threading
        errors = []
        results = {}

        def do_validate(idx):
            try:
                freq = 900e6 + idx * 1e6
                result = rf.validate(freq, -100)
                assert result["result"] == "PASS"
                results[idx] = result["check_id"]
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_validate, args=(i,))
                    for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify all records are readable after threads complete
        for idx, check_id in results.items():
            fetched = rf.get(check_id)
            assert fetched is not None
            assert fetched["result"] == "PASS"
        assert len(rf.list_checks(limit=20)) == 10
