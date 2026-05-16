"""Tests for sylion.sdr.capture_orchestrator -- CaptureOrchestrator."""

import pytest

from sylion.sdr.capture_orchestrator import CaptureOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def orch():
    return CaptureOrchestrator(db_path=":memory:")


def _create_capture(orch, sdr_id="sdr-1", frequency=100e6, **kwargs):
    return orch.create_capture(sdr_id, frequency, **kwargs)


# ---------------------------------------------------------------------------
# create_capture()
# ---------------------------------------------------------------------------

class TestCreateCapture:
    def test_create_returns_record(self, orch):
        r = _create_capture(orch)
        assert "capture_id" in r
        assert r["sdr_id"] == "sdr-1"
        assert r["frequency"] == 100e6

    def test_default_mode_is_rx(self, orch):
        r = _create_capture(orch)
        assert r["mode"] == "RX"

    def test_custom_mode(self, orch):
        r = _create_capture(orch, mode="TX")
        assert r["mode"] == "TX"

    def test_default_status_is_created(self, orch):
        r = _create_capture(orch)
        assert r["status"] == "created"

    def test_default_sample_rate(self, orch):
        r = _create_capture(orch)
        assert r["sample_rate"] == 2e6

    def test_custom_sample_rate(self, orch):
        r = _create_capture(orch, sample_rate=10e6)
        assert r["sample_rate"] == 10e6

    def test_custom_duration(self, orch):
        r = _create_capture(orch, duration_s=120)
        assert r["duration_s"] == 120

    def test_sigmf_meta_default(self, orch):
        r = _create_capture(orch)
        assert r["sigmf_meta"] == "{}"


# ---------------------------------------------------------------------------
# start()
# ---------------------------------------------------------------------------

class TestStart:
    def test_start_created_capture(self, orch):
        r = _create_capture(orch)
        result = orch.start(r["capture_id"])
        assert result["status"] == "running"

    def test_start_nonexistent_returns_error(self, orch):
        result = orch.start("no-such-id")
        assert "error" in result
        assert result["capture_id"] == "no-such-id"

    def test_start_already_running_returns_error(self, orch):
        r = _create_capture(orch)
        orch.start(r["capture_id"])
        result = orch.start(r["capture_id"])
        assert "error" in result

    def test_start_stopped_capture(self, orch):
        r = _create_capture(orch)
        orch.start(r["capture_id"])
        orch.stop(r["capture_id"])
        result = orch.start(r["capture_id"])
        assert result["status"] == "running"

    def test_start_tx_blocked_when_no_governor(self, orch):
        """TX mode capture should be blocked when RF governor is unavailable."""
        r = _create_capture(orch, mode="TX")
        result = orch.start(r["capture_id"])
        assert "error" in result
        assert "TX" in result["error"]


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------

class TestStop:
    def test_stop_running_capture(self, orch):
        r = _create_capture(orch)
        orch.start(r["capture_id"])
        result = orch.stop(r["capture_id"])
        assert result["status"] == "stopped"

    def test_stop_nonexistent_returns_error(self, orch):
        result = orch.stop("nope")
        assert "error" in result

    def test_stop_created_capture_returns_error(self, orch):
        r = _create_capture(orch)
        result = orch.stop(r["capture_id"])
        assert "error" in result

    def test_stop_already_stopped_returns_error(self, orch):
        r = _create_capture(orch)
        orch.start(r["capture_id"])
        orch.stop(r["capture_id"])
        result = orch.stop(r["capture_id"])
        assert "error" in result


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_existing(self, orch):
        r = _create_capture(orch)
        fetched = orch.get(r["capture_id"])
        assert fetched is not None
        assert fetched["sdr_id"] == "sdr-1"

    def test_get_nonexistent_returns_none(self, orch):
        assert orch.get("ghost") is None


# ---------------------------------------------------------------------------
# list_captures()
# ---------------------------------------------------------------------------

class TestListCaptures:
    def test_list_all(self, orch):
        _create_capture(orch)
        _create_capture(orch)
        assert len(orch.list_captures()) == 2

    def test_filter_by_sdr(self, orch):
        _create_capture(orch, sdr_id="sdr-1")
        _create_capture(orch, sdr_id="sdr-2")
        filtered = orch.list_captures(sdr_id="sdr-1")
        assert len(filtered) == 1

    def test_limit(self, orch):
        for i in range(5):
            _create_capture(orch)
        assert len(orch.list_captures(limit=3)) == 3

    def test_empty_list(self, orch):
        assert orch.list_captures() == []


# ---------------------------------------------------------------------------
# Full lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_created_to_running_to_stopped(self, orch):
        r = _create_capture(orch)
        assert r["status"] == "created"
        r = orch.start(r["capture_id"])
        assert r["status"] == "running"
        r = orch.stop(r["capture_id"])
        assert r["status"] == "stopped"

    def test_restarted_capture(self, orch):
        r = _create_capture(orch)
        cid = r["capture_id"]
        orch.start(cid)
        orch.stop(cid)
        r2 = orch.start(cid)
        assert r2["status"] == "running"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_create_emits_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        orch = CaptureOrchestrator(db_path=":memory:", event_bus=MockBus())
        orch.create_capture("sdr-1", 100e6)
        assert any(e.topic == "sdr.capture.created" for e in events)

    def test_start_emits_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        orch = CaptureOrchestrator(db_path=":memory:", event_bus=MockBus())
        r = orch.create_capture("sdr-1", 100e6)
        orch.start(r["capture_id"])
        assert any(e.topic == "sdr.capture.started" for e in events)

    def test_stop_emits_completed_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        orch = CaptureOrchestrator(db_path=":memory:", event_bus=MockBus())
        r = orch.create_capture("sdr-1", 100e6)
        orch.start(r["capture_id"])
        orch.stop(r["capture_id"])
        assert any(e.topic == "sdr.capture.completed" for e in events)
