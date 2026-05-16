"""Tests for sylion.sdr.rf_safety_governor -- RFSafetyGovernor."""

import pytest

from sylion.sdr.rf_safety_governor import RFSafetyGovernor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gov():
    return RFSafetyGovernor(db_path=":memory:")


# ---------------------------------------------------------------------------
# Safety invariant: TX disabled by default
# ---------------------------------------------------------------------------

class TestSafetyInvariant:
    def test_tx_disabled_by_default(self, gov):
        assert gov.is_tx_enabled() is False

    def test_check_tx_blocked_when_disabled(self, gov):
        result = gov.check_tx_allowed(100e6, 0)
        assert result["allowed"] is False
        assert "globally disabled" in result["reason"]


# ---------------------------------------------------------------------------
# enable_tx_global()
# ---------------------------------------------------------------------------

class TestEnableTxGlobal:
    def test_enable_with_valid_approval(self, gov):
        result = gov.enable_tx_global("council-approval-001")
        assert result["enabled"] is True
        assert gov.is_tx_enabled() is True

    def test_enable_with_empty_string_fails(self, gov):
        result = gov.enable_tx_global("")
        assert result["enabled"] is False
        assert "error" in result
        assert gov.is_tx_enabled() is False

    def test_enable_with_whitespace_fails(self, gov):
        result = gov.enable_tx_global("   ")
        assert result["enabled"] is False
        assert gov.is_tx_enabled() is False


# ---------------------------------------------------------------------------
# add_band_policy()
# ---------------------------------------------------------------------------

class TestBandPolicy:
    def test_add_policy_returns_record(self, gov):
        r = gov.add_band_policy("pol-1", "PL", 88e6, 108e6,
                                 max_power_dbm=10, tx_allowed=True)
        assert r["policy_id"] == "pol-1"
        assert r["jurisdiction"] == "PL"
        assert r["band_start"] == 88e6
        assert r["band_end"] == 108e6

    def test_tx_allowed_default_false(self, gov):
        r = gov.add_band_policy("pol-2", "PL", 2400e6, 2500e6)
        assert r["tx_allowed"] == 0

    def test_requires_council_default_true(self, gov):
        r = gov.add_band_policy("pol-3", "PL", 2400e6, 2500e6)
        assert r["requires_council"] == 1

    def test_replace_existing_policy(self, gov):
        gov.add_band_policy("pol-1", "PL", 88e6, 108e6, max_power_dbm=10)
        r = gov.add_band_policy("pol-1", "PL", 88e6, 108e6, max_power_dbm=20)
        assert r["max_power_dbm"] == 20


# ---------------------------------------------------------------------------
# check_tx_allowed()
# ---------------------------------------------------------------------------

class TestCheckTxAllowed:
    def _setup_enabled_gov(self, gov):
        gov.enable_tx_global("council-ok")
        gov.add_band_policy("ism", "PL", 2400e6, 2500e6,
                            max_power_dbm=10, tx_allowed=True,
                            requires_council=False)

    def test_allowed_in_permitting_band(self, gov):
        self._setup_enabled_gov(gov)
        r = gov.check_tx_allowed(2450e6, 5, "PL")
        assert r["allowed"] is True

    def test_blocked_power_too_high(self, gov):
        self._setup_enabled_gov(gov)
        r = gov.check_tx_allowed(2450e6, 15, "PL")
        assert r["allowed"] is False
        assert "exceeds" in r["reason"]

    def test_blocked_no_policy(self, gov):
        gov.enable_tx_global("council-ok")
        r = gov.check_tx_allowed(500e6, 0, "PL")
        assert r["allowed"] is False
        assert "no policy" in r["reason"]

    def test_blocked_tx_not_allowed_in_band(self, gov):
        gov.enable_tx_global("council-ok")
        gov.add_band_policy("no-tx", "PL", 88e6, 108e6, tx_allowed=False)
        r = gov.check_tx_allowed(100e6, 0, "PL")
        assert r["allowed"] is False

    def test_different_jurisdictions(self, gov):
        gov.enable_tx_global("council-ok")
        gov.add_band_policy("ism-pl", "PL", 2400e6, 2500e6,
                            tx_allowed=True)
        r = gov.check_tx_allowed(2450e6, 0, "DE")
        assert r["allowed"] is False  # No DE policy


# ---------------------------------------------------------------------------
# record_tx()
# ---------------------------------------------------------------------------

class TestRecordTx:
    def test_record_returns_event(self, gov):
        r = gov.record_tx("sdr-1", 2450e6, 5.0, approved_by="admin")
        assert "event_id" in r
        assert r["sdr_id"] == "sdr-1"
        assert r["frequency"] == 2450e6
        assert r["power_dbm"] == 5.0
        assert r["mode"] == "TX"

    def test_record_without_approval(self, gov):
        r = gov.record_tx("sdr-1", 100e6, 0)
        assert r["approved_by"] == ""


# ---------------------------------------------------------------------------
# get_policies()
# ---------------------------------------------------------------------------

class TestGetPolicies:
    def test_get_all_policies(self, gov):
        gov.add_band_policy("p1", "PL", 88e6, 108e6)
        gov.add_band_policy("p2", "DE", 2400e6, 2500e6)
        assert len(gov.get_policies()) == 2

    def test_filter_by_jurisdiction(self, gov):
        gov.add_band_policy("p1", "PL", 88e6, 108e6)
        gov.add_band_policy("p2", "DE", 2400e6, 2500e6)
        pl = gov.get_policies(jurisdiction="PL")
        assert len(pl) == 1
        assert pl[0]["jurisdiction"] == "PL"

    def test_empty_policies(self, gov):
        assert gov.get_policies() == []


# ---------------------------------------------------------------------------
# get_events()
# ---------------------------------------------------------------------------

class TestGetEvents:
    def test_get_all_events(self, gov):
        gov.record_tx("s1", 100e6, 0)
        gov.record_tx("s2", 200e6, 0)
        assert len(gov.get_events()) == 2

    def test_filter_by_sdr(self, gov):
        gov.record_tx("s1", 100e6, 0)
        gov.record_tx("s2", 200e6, 0)
        events = gov.get_events(sdr_id="s1")
        assert len(events) == 1
        assert events[0]["sdr_id"] == "s1"

    def test_limit(self, gov):
        for i in range(5):
            gov.record_tx("s1", 100e6 + i * 1e6, 0)
        assert len(gov.get_events(limit=3)) == 3


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_policy_added_emits(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        gov = RFSafetyGovernor(db_path=":memory:", event_bus=MockBus())
        gov.add_band_policy("p1", "PL", 88e6, 108e6)
        assert any(e.topic == "sdr.rf.policy_added" for e in events)

    def test_tx_enabled_emits(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        gov = RFSafetyGovernor(db_path=":memory:", event_bus=MockBus())
        gov.enable_tx_global("council-ok")
        assert any(e.topic == "sdr.rf.tx_enabled" for e in events)

    def test_record_tx_emits(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        gov = RFSafetyGovernor(db_path=":memory:", event_bus=MockBus())
        gov.record_tx("s1", 100e6, 0)
        assert any(e.topic == "sdr.rf.tx" for e in events)
