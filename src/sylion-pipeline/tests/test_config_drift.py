"""Tests for SYLION Efficiency -- Config Drift Detector."""
import threading
import time

import pytest

from sylion.core.event_bus import EventBus
from sylion.efficiency.config_drift import (
    ComplianceError,
    ConfigBaseline,
    ConfigDriftDetector,
    DriftEvent,
    get_config_drift_detector,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    """Fresh EventBus for each test."""
    return EventBus()


@pytest.fixture
def detector(bus):
    """Fresh ConfigDriftDetector for each test."""
    return ConfigDriftDetector(event_bus=bus)


# ===========================================================================
# 1. Data model tests
# ===========================================================================

class TestConfigBaselineDataclass:
    def test_default_values(self):
        b = ConfigBaseline(module_id="mod_a", config_key="timeout")
        assert b.module_id == "mod_a"
        assert b.config_key == "timeout"
        assert b.config_value == ""
        assert b.set_at > 0

    def test_custom_values(self):
        b = ConfigBaseline(
            module_id="mod_b", config_key="retries",
            config_value="3", set_at=1000.0,
        )
        assert b.config_value == "3"
        assert b.set_at == 1000.0


class TestDriftEventDataclass:
    def test_auto_generated_id(self):
        d = DriftEvent(module_id="m", config_key="k")
        assert d.drift_id
        assert len(d.drift_id) == 32  # uuid hex

    def test_auto_detected_at(self):
        d = DriftEvent(module_id="m", config_key="k")
        assert d.detected_at > 0

    def test_custom_drift_id(self):
        d = DriftEvent(drift_id="custom_id", module_id="m", config_key="k")
        assert d.drift_id == "custom_id"


# ===========================================================================
# 2. set_baseline / get_baseline
# ===========================================================================

class TestSetGetBaseline:
    def test_set_baseline_string(self, detector):
        result = detector.set_baseline("mod_a", "timeout", "30")
        assert result["module_id"] == "mod_a"
        assert result["config_key"] == "timeout"
        assert result["config_value"] == "30"

    def test_set_baseline_int(self, detector):
        result = detector.set_baseline("mod_a", "retries", 3)
        assert result["config_value"] == "3"

    def test_set_baseline_dict(self, detector):
        val = {"host": "localhost", "port": 8080}
        result = detector.set_baseline("mod_a", "connection", val)
        assert '"host"' in result["config_value"]
        assert "8080" in result["config_value"]

    def test_set_baseline_none(self, detector):
        result = detector.set_baseline("mod_a", "flag", None)
        assert result["config_value"] == "__NULL__"

    def test_set_baseline_list(self, detector):
        result = detector.set_baseline("mod_a", "tags", ["a", "b", "c"])
        assert "a" in result["config_value"]

    def test_get_baseline_returns_value(self, detector):
        detector.set_baseline("mod_b", "timeout", "60")
        val = detector.get_baseline("mod_b", "timeout")
        assert val == "60"

    def test_get_baseline_nonexistent(self, detector):
        assert detector.get_baseline("no.mod", "no.key") is None

    def test_set_baseline_upsert(self, detector):
        detector.set_baseline("mod_c", "pool_size", "10")
        detector.set_baseline("mod_c", "pool_size", "20")
        assert detector.get_baseline("mod_c", "pool_size") == "20"

    def test_get_baselines_for_module(self, detector):
        detector.set_baseline("mod_d", "k1", "v1")
        detector.set_baseline("mod_d", "k2", "v2")
        detector.set_baseline("mod_d", "k3", "v3")
        baselines = detector.get_baselines_for_module("mod_d")
        assert len(baselines) == 3
        assert baselines["k1"] == "v1"
        assert baselines["k2"] == "v2"
        assert baselines["k3"] == "v3"

    def test_get_baselines_empty_module(self, detector):
        assert detector.get_baselines_for_module("no.such.mod") == {}

    def test_remove_baseline(self, detector):
        detector.set_baseline("mod_e", "temp", "42")
        assert detector.remove_baseline("mod_e", "temp") is True
        assert detector.get_baseline("mod_e", "temp") is None

    def test_remove_baseline_nonexistent(self, detector):
        assert detector.remove_baseline("no.mod", "no.key") is False

    def test_remove_baselines_for_module(self, detector):
        detector.set_baseline("mod_f", "a", "1")
        detector.set_baseline("mod_f", "b", "2")
        detector.set_baseline("mod_f", "c", "3")
        count = detector.remove_baselines_for_module("mod_f")
        assert count == 3
        assert detector.get_baselines_for_module("mod_f") == {}


# ===========================================================================
# 3. check_drift
# ===========================================================================

class TestCheckDrift:
    def test_no_drift_compliant(self, detector):
        detector.set_baseline("mod_g", "timeout", "30")
        result = detector.check_drift("mod_g", {"timeout": "30"})
        assert result["compliant"] is True
        assert result["drifts"] == []

    def test_drift_detected_value_change(self, detector):
        detector.set_baseline("mod_h", "timeout", "30")
        result = detector.check_drift("mod_h", {"timeout": "60"})
        assert result["compliant"] is False
        assert len(result["drifts"]) == 1
        assert result["drifts"][0]["expected"] == "30"
        assert result["drifts"][0]["actual"] == "60"

    def test_drift_missing_key(self, detector):
        detector.set_baseline("mod_i", "timeout", "30")
        result = detector.check_drift("mod_i", {})
        assert result["compliant"] is False
        assert len(result["drifts"]) == 1
        assert result["drifts"][0]["actual"] == "__NULL__"

    def test_no_drift_with_extra_keys(self, detector):
        detector.set_baseline("mod_j", "timeout", "30")
        result = detector.check_drift("mod_j", {"timeout": "30", "extra": "ignored"})
        assert result["compliant"] is True

    def test_multiple_keys_partial_drift(self, detector):
        detector.set_baseline("mod_k", "timeout", "30")
        detector.set_baseline("mod_k", "retries", "3")
        result = detector.check_drift("mod_k", {"timeout": "30", "retries": "5"})
        assert result["compliant"] is False
        assert len(result["drifts"]) == 1
        assert result["drifts"][0]["config_key"] == "retries"

    def test_multiple_drifts(self, detector):
        detector.set_baseline("mod_l", "timeout", "30")
        detector.set_baseline("mod_l", "retries", "3")
        result = detector.check_drift("mod_l", {"timeout": "99", "retries": "0"})
        assert result["compliant"] is False
        assert len(result["drifts"]) == 2

    def test_check_drift_no_baselines_is_compliant(self, detector):
        result = detector.check_drift("no_baselines", {"k": "v"})
        assert result["compliant"] is True

    def test_check_drift_int_vs_string(self, detector):
        detector.set_baseline("mod_m", "port", "8080")
        result = detector.check_drift("mod_m", {"port": 8080})
        # int 8080 serialised as "8080" should match string "8080"
        assert result["compliant"] is True

    def test_check_drift_records_events(self, detector):
        detector.set_baseline("mod_n", "timeout", "30")
        detector.check_drift("mod_n", {"timeout": "60"})
        history = detector.get_drift_history("mod_n")
        assert len(history) == 1

    def test_check_drift_compliant_no_history(self, detector):
        detector.set_baseline("mod_o", "timeout", "30")
        detector.check_drift("mod_o", {"timeout": "30"})
        history = detector.get_drift_history("mod_o")
        assert len(history) == 0


# ===========================================================================
# 4. record_drift (manual)
# ===========================================================================

class TestRecordDrift:
    def test_record_drift_manual(self, detector):
        result = detector.record_drift("mod_p", "timeout", "30", "60")
        assert result["drift_id"]
        assert result["module_id"] == "mod_p"
        assert result["expected"] == "30"
        assert result["actual"] == "60"

    def test_record_drift_with_types(self, detector):
        result = detector.record_drift("mod_q", "retries", 3, 5)
        assert result["expected"] == "3"
        assert result["actual"] == "5"

    def test_recorded_drift_appears_in_history(self, detector):
        detector.record_drift("mod_r", "k", "v1", "v2")
        history = detector.get_drift_history("mod_r")
        assert len(history) == 1
        assert history[0]["expected_value"] == "v1"
        assert history[0]["actual_value"] == "v2"


# ===========================================================================
# 5. get_drift_history
# ===========================================================================

class TestGetDriftHistory:
    def test_empty_history(self, detector):
        assert detector.get_drift_history("no_drifts") == []

    def test_history_respects_limit(self, detector):
        for i in range(30):
            detector.record_drift("mod_s", f"key_{i}", "old", "new")
        history = detector.get_drift_history("mod_s", limit=10)
        assert len(history) == 10

    def test_history_ordered_by_time_desc(self, detector):
        detector.record_drift("mod_t", "k1", "1", "2")
        time.sleep(0.01)
        detector.record_drift("mod_t", "k2", "3", "4")
        history = detector.get_drift_history("mod_t")
        assert len(history) == 2
        assert history[0]["detected_at"] >= history[1]["detected_at"]


# ===========================================================================
# 6. get_all_drifts
# ===========================================================================

class TestGetAllDrifts:
    def test_no_drifts(self, detector):
        assert detector.get_all_drifts() == []

    def test_returns_unremediated_drifts(self, detector):
        detector.set_baseline("m1", "k", "v1")
        detector.check_drift("m1", {"k": "v2"})
        detector.set_baseline("m2", "k", "v1")
        detector.check_drift("m2", {"k": "v3"})
        all_drifts = detector.get_all_drifts()
        assert len(all_drifts) == 2

    def test_excludes_remediated_drifts(self, detector):
        detector.set_baseline("m3", "k", "v1")
        result = detector.check_drift("m3", {"k": "v2"})
        drift_id = detector.get_drift_history("m3")[0]["drift_id"]
        detector.remediate_drift(drift_id, "v2")
        all_drifts = detector.get_all_drifts()
        assert len(all_drifts) == 0


# ===========================================================================
# 7. remediate_drift
# ===========================================================================

class TestRemediateDrift:
    def test_remediate_updates_baseline(self, detector):
        detector.set_baseline("mod_u", "timeout", "30")
        detector.check_drift("mod_u", {"timeout": "60"})
        drift = detector.get_drift_history("mod_u")[0]
        result = detector.remediate_drift(drift["drift_id"], "60")
        assert result["remediated"] is True
        assert result["new_baseline"] == "60"
        assert detector.get_baseline("mod_u", "timeout") == "60"

    def test_remediate_marks_event(self, detector):
        detector.set_baseline("mod_v", "k", "1")
        detector.check_drift("mod_v", {"k": "2"})
        drift = detector.get_drift_history("mod_v")[0]
        detector.remediate_drift(drift["drift_id"], "2")
        history = detector.get_drift_history("mod_v")
        assert history[0]["remediated"] == 1

    def test_remediate_nonexistent_drift_raises(self, detector):
        with pytest.raises(ValueError, match="not found"):
            detector.remediate_drift("nonexistent_id", "value")

    def test_remediate_with_complex_value(self, detector):
        detector.set_baseline("mod_w", "config", {"a": 1})
        detector.check_drift("mod_w", {"config": {"a": 2}})
        drift = detector.get_drift_history("mod_w")[0]
        result = detector.remediate_drift(drift["drift_id"], {"a": 2})
        assert '"a"' in result["new_baseline"]

    def test_after_remediate_check_passes(self, detector):
        detector.set_baseline("mod_x", "timeout", "30")
        detector.check_drift("mod_x", {"timeout": "60"})
        drift = detector.get_drift_history("mod_x")[0]
        detector.remediate_drift(drift["drift_id"], "60")
        # Now check again -- should be compliant
        result = detector.check_drift("mod_x", {"timeout": "60"})
        assert result["compliant"] is True


# ===========================================================================
# 8. enforce_compliance
# ===========================================================================

class TestEnforceCompliance:
    def test_compliant_passes(self, detector):
        detector.set_baseline("mod_y", "k", "v")
        result = detector.enforce_compliance("mod_y", {"k": "v"})
        assert result["compliant"] is True

    def test_non_compliant_raises(self, detector):
        detector.set_baseline("mod_z", "k", "v")
        with pytest.raises(ComplianceError, match="non-compliant"):
            detector.enforce_compliance("mod_z", {"k": "different"})

    def test_error_message_contains_keys(self, detector):
        detector.set_baseline("mod_aa", "k1", "v1")
        detector.set_baseline("mod_aa", "k2", "v2")
        with pytest.raises(ComplianceError, match="k1.*k2|k2.*k1"):
            detector.enforce_compliance("mod_aa", {"k1": "x", "k2": "y"})

    def test_no_baseline_is_compliant(self, detector):
        result = detector.enforce_compliance("empty_mod", {"k": "v"})
        assert result["compliant"] is True


# ===========================================================================
# 9. get_stats
# ===========================================================================

class TestGetStats:
    def test_empty_stats(self, detector):
        stats = detector.get_stats()
        assert stats["total_baselines"] == 0
        assert stats["total_drifts"] == 0
        assert stats["compliance_rate"] == 100.0
        assert stats["by_module"] == {}

    def test_stats_after_baselines(self, detector):
        detector.set_baseline("m1", "k1", "v1")
        detector.set_baseline("m1", "k2", "v2")
        detector.set_baseline("m2", "k1", "v1")
        stats = detector.get_stats()
        assert stats["total_baselines"] == 3
        assert stats["by_module"]["m1"]["baselines"] == 2
        assert stats["by_module"]["m2"]["baselines"] == 1

    def test_stats_with_drifts(self, detector):
        detector.set_baseline("m1", "k1", "v1")
        detector.check_drift("m1", {"k1": "v2"})
        stats = detector.get_stats()
        assert stats["total_drifts"] == 1
        assert stats["by_module"]["m1"]["active_drifts"] == 1
        assert stats["by_module"]["m1"]["compliance_rate"] == 0.0

    def test_stats_compliance_rate_mixed(self, detector):
        detector.set_baseline("m1", "k1", "v1")
        detector.set_baseline("m1", "k2", "v2")
        detector.set_baseline("m1", "k3", "v3")
        # Drift on k1 only
        detector.check_drift("m1", {"k1": "changed", "k2": "v2", "k3": "v3"})
        stats = detector.get_stats()
        assert stats["by_module"]["m1"]["active_drifts"] == 1
        # 2 out of 3 compliant = 66.67%
        assert stats["by_module"]["m1"]["compliance_rate"] == pytest.approx(66.67, rel=0.01)

    def test_stats_after_remediation(self, detector):
        detector.set_baseline("m1", "k1", "v1")
        detector.check_drift("m1", {"k1": "v2"})
        drift = detector.get_drift_history("m1")[0]
        detector.remediate_drift(drift["drift_id"], "v2")
        stats = detector.get_stats()
        assert stats["total_drifts"] == 0
        assert stats["compliance_rate"] == 100.0


# ===========================================================================
# 10. Serialisation
# ===========================================================================

class TestSerialisation:
    def test_string_passthrough(self, detector):
        assert detector._serialise("hello") == "hello"

    def test_int_to_string(self, detector):
        assert detector._serialise(42) == "42"

    def test_float_to_string(self, detector):
        assert detector._serialise(3.14) == "3.14"

    def test_dict_to_json(self, detector):
        result = detector._serialise({"b": 2, "a": 1})
        assert '"a"' in result
        assert '"b"' in result

    def test_list_to_json(self, detector):
        assert detector._serialise([1, 2, 3]) == "[1, 2, 3]"

    def test_none_to_null_marker(self, detector):
        assert detector._serialise(None) == "__NULL__"

    def test_bool_to_string(self, detector):
        assert detector._serialise(True) == "True"

    def test_set_to_json(self, detector):
        result = detector._serialise({1, 2, 3})
        # Sets serialise via json.dumps which converts to list
        assert "1" in result and "2" in result and "3" in result


# ===========================================================================
# 11. Thread safety
# ===========================================================================

class TestThreadSafety:
    def test_concurrent_set_baseline(self, detector):
        errors: list[Exception] = []

        def set_bl(i):
            try:
                detector.set_baseline(f"mod_conc_{i}", "timeout", str(i * 10))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=set_bl, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        for i in range(30):
            val = detector.get_baseline(f"mod_conc_{i}", "timeout")
            assert val == str(i * 10)

    def test_concurrent_check_drift(self, detector):
        detector.set_baseline("race_mod", "k", "v")
        errors: list[Exception] = []

        def check():
            try:
                detector.check_drift("race_mod", {"k": "v"})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=check) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_concurrent_record_drift(self, detector):
        errors: list[Exception] = []

        def record(i):
            try:
                detector.record_drift("conc_drift", f"key_{i}", "old", "new")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        history = detector.get_drift_history("conc_drift", limit=50)
        assert len(history) == 30

    def test_concurrent_mixed_operations(self, detector):
        detector.set_baseline("mixed_mod", "k1", "v1")
        detector.set_baseline("mixed_mod", "k2", "v2")
        errors: list[Exception] = []

        def op(i):
            try:
                if i % 3 == 0:
                    detector.check_drift("mixed_mod", {"k1": "v1", "k2": "v2"})
                elif i % 3 == 1:
                    detector.get_drift_history("mixed_mod")
                else:
                    detector.get_stats()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=op, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ===========================================================================
# 12. Singleton
# ===========================================================================

class TestSingleton:
    def test_get_config_drift_detector_returns_instance(self):
        import sylion.efficiency.config_drift as mod
        mod._detector = None
        d = get_config_drift_detector()
        assert isinstance(d, ConfigDriftDetector)
        assert d is get_config_drift_detector()
        mod._detector = None


# ===========================================================================
# 13. Event emission
# ===========================================================================

class TestEventEmission:
    def test_set_baseline_emits(self, bus, detector):
        events = []
        bus.subscribe("efficiency.config_drift.baseline_set", events.append)
        detector.set_baseline("ev_mod", "k", "v")
        assert len(events) == 1
        assert events[0].payload["module_id"] == "ev_mod"

    def test_drift_detected_emits(self, bus, detector):
        events = []
        bus.subscribe("efficiency.config_drift.drift_detected", events.append)
        detector.set_baseline("ev_mod2", "k", "v1")
        detector.check_drift("ev_mod2", {"k": "v2"})
        assert len(events) == 1
        assert events[0].payload["drift_count"] == 1

    def test_compliance_ok_emits(self, bus, detector):
        events = []
        bus.subscribe("efficiency.config_drift.compliance_ok", events.append)
        detector.set_baseline("ev_mod3", "k", "v")
        detector.check_drift("ev_mod3", {"k": "v"})
        assert len(events) == 1

    def test_drift_recorded_emits(self, bus, detector):
        events = []
        bus.subscribe("efficiency.config_drift.drift_recorded", events.append)
        detector.record_drift("ev_mod4", "k", "old", "new")
        assert len(events) == 1
        assert events[0].payload["expected"] == "old"

    def test_drift_remediated_emits(self, bus, detector):
        events = []
        bus.subscribe("efficiency.config_drift.drift_remediated", events.append)
        detector.set_baseline("ev_mod5", "k", "v1")
        detector.check_drift("ev_mod5", {"k": "v2"})
        drift = detector.get_drift_history("ev_mod5")[0]
        detector.remediate_drift(drift["drift_id"], "v2")
        assert len(events) == 1
        assert events[0].payload["new_baseline"] == "v2"


# ===========================================================================
# 14. Edge cases & integration
# ===========================================================================

class TestEdgeCases:
    def test_empty_config_dict(self, detector):
        detector.set_baseline("edge1", "k", "v")
        result = detector.check_drift("edge1", {})
        assert result["compliant"] is False

    def test_baseline_with_special_characters(self, detector):
        detector.set_baseline("edge2", "conn_str",
                              "host=localhost;port=5432;ssl=true")
        val = detector.get_baseline("edge2", "conn_str")
        assert val == "host=localhost;port=5432;ssl=true"

    def test_drift_same_value_different_types(self, detector):
        """String "123" vs int 123 should be equivalent after serialisation."""
        detector.set_baseline("edge3", "count", "123")
        result = detector.check_drift("edge3", {"count": 123})
        assert result["compliant"] is True

    def test_multiple_check_drifts_accumulate_history(self, detector):
        detector.set_baseline("edge4", "k", "v1")
        detector.check_drift("edge4", {"k": "v2"})
        detector.check_drift("edge4", {"k": "v3"})
        detector.check_drift("edge4", {"k": "v4"})
        history = detector.get_drift_history("edge4")
        assert len(history) == 3

    def test_large_config_dict(self, detector):
        configs = {f"key_{i}": f"val_{i}" for i in range(100)}
        for k, v in configs.items():
            detector.set_baseline("edge5", k, v)
        result = detector.check_drift("edge5", configs)
        assert result["compliant"] is True

    def test_db_path_memory(self):
        d = ConfigDriftDetector(db_path=":memory:")
        d.set_baseline("test", "k", "v")
        assert d.get_baseline("test", "k") == "v"

    def test_no_event_bus_no_crash(self):
        d = ConfigDriftDetector(event_bus=None)
        d.set_baseline("test", "k", "v")
        result = d.check_drift("test", {"k": "v"})
        assert result["compliant"] is True

    def test_full_lifecycle_workflow(self, detector):
        """End-to-end: set baseline, check drift, remediate, verify."""
        # 1. Set baseline
        detector.set_baseline("lifecycle", "timeout", "30")
        detector.set_baseline("lifecycle", "retries", "3")

        # 2. Check -- compliant
        r = detector.check_drift("lifecycle", {"timeout": "30", "retries": "3"})
        assert r["compliant"] is True

        # 3. Config changes -- check drift
        r = detector.check_drift("lifecycle", {"timeout": "60", "retries": "3"})
        assert r["compliant"] is False
        assert len(r["drifts"]) == 1

        # 4. Remediate
        drift = detector.get_drift_history("lifecycle")[0]
        detector.remediate_drift(drift["drift_id"], "60")

        # 5. Verify compliance restored
        r = detector.check_drift("lifecycle", {"timeout": "60", "retries": "3"})
        assert r["compliant"] is True

        # 6. Stats show 100%
        stats = detector.get_stats()
        assert stats["by_module"]["lifecycle"]["compliance_rate"] == 100.0

    def test_enforce_compliance_after_remediation(self, detector):
        detector.set_baseline("enforce_mod", "k", "v1")
        with pytest.raises(ComplianceError):
            detector.enforce_compliance("enforce_mod", {"k": "v2"})
        drift = detector.get_drift_history("enforce_mod")[0]
        detector.remediate_drift(drift["drift_id"], "v2")
        # Now should pass
        result = detector.enforce_compliance("enforce_mod", {"k": "v2"})
        assert result["compliant"] is True
