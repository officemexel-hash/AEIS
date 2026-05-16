from __future__ import annotations

import enum
import importlib
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))
sys.path.insert(0, str(ROOT))


def _module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


@pytest.fixture()
def bridge_module():
    bridge = importlib.import_module("bridge")
    return importlib.reload(bridge)


def test_stream_monitor_bridge_not_configured_without_live_accessor(monkeypatch, bridge_module):
    monkeypatch.setitem(sys.modules, "stream_monitor", _module("stream_monitor"))

    payload = bridge_module.get_stream_monitor_health()

    assert payload["status"] == "not_configured"
    assert payload["module"] == "stream_monitor"
    assert payload["reason"] == "no live monitor accessor exported"
    assert "metrics" not in payload


def test_stream_monitor_bridge_uses_runtime_singleton(monkeypatch, bridge_module):
    class Snapshot:
        def to_dict(self):
            return {"fps": 30, "latency_p95_ms": 42.5}

    class Monitor:
        def get_snapshot(self):
            return Snapshot()

    monkeypatch.setitem(
        sys.modules,
        "stream_monitor",
        _module("stream_monitor", monitor=Monitor()),
    )

    payload = bridge_module.get_stream_monitor_health()

    assert payload["status"] == "ok"
    assert payload["module"] == "stream_monitor"
    assert payload["fps"] == 30
    assert payload["latency_p95_ms"] == 42.5


def test_stream_monitor_bridge_timeout_is_degraded(monkeypatch, bridge_module):
    def always_timeout(*args, **kwargs):
        raise TimeoutError

    monkeypatch.setattr(bridge_module, "_run_with_timeout", always_timeout)

    payload = bridge_module.get_stream_monitor_health()

    assert payload["status"] == "degraded"
    assert payload["module"] == "stream_monitor"
    assert "timed out" in payload["message"]


def test_device_bridge_not_configured_without_live_accessor(monkeypatch, bridge_module):
    class DeviceHarness:
        pass

    monkeypatch.setitem(
        sys.modules,
        "device_harness",
        _module("device_harness", DeviceHarness=DeviceHarness),
    )

    payload = bridge_module.get_device_status("pixel")

    assert payload["status"] == "not_configured"
    assert payload["module"] == "device_harness"
    assert payload["device_id"] == "pixel"
    assert "metrics" not in payload


def test_device_bridge_uses_runtime_harness_health_check(monkeypatch, bridge_module):
    class Status:
        def to_dict(self):
            return {"device": "pixel", "state": "ONLINE", "battery_pct": 87}

    class Harness:
        def health_check_pixel(self):
            return Status()

    monkeypatch.setitem(
        sys.modules,
        "device_harness",
        _module("device_harness", runtime_harness=Harness()),
    )

    payload = bridge_module.get_device_status("pixel")

    assert payload["status"] == "ok"
    assert payload["module"] == "device_harness"
    assert payload["device_id"] == "pixel"
    assert payload["state"] == "ONLINE"
    assert payload["battery_pct"] == 87


def test_abr_bridge_not_configured_without_live_accessor(monkeypatch, bridge_module):
    class ABRState(enum.Enum):
        IDLE = "IDLE"

    class ABRController:
        pass

    monkeypatch.setitem(
        sys.modules,
        "abr_controller",
        _module("abr_controller", ABRState=ABRState, ABRController=ABRController),
    )

    payload = bridge_module.get_abr_state()

    assert payload["status"] == "not_configured"
    assert payload["module"] == "abr_controller"
    assert payload["reason"] == "no live ABR accessor or runtime controller exported"
    assert "available_states" not in payload


def test_abr_bridge_uses_runtime_controller(monkeypatch, bridge_module):
    class Settings:
        def to_dict(self):
            return {"resolution": "1280x720", "bitrate_kbps": 2500}

    class RuntimeState(enum.Enum):
        STABLE = "STABLE"

    class Controller:
        state = RuntimeState.STABLE

        def get_stats(self):
            return {"current_rung": 2, "state": "STABLE"}

        def get_current_settings(self):
            return Settings()

    monkeypatch.setitem(
        sys.modules,
        "abr_controller",
        _module("abr_controller", controller=Controller()),
    )

    payload = bridge_module.get_abr_state()

    assert payload["status"] == "ok"
    assert payload["module"] == "abr_controller"
    assert payload["current_rung"] == 2
    assert payload["state"] == "STABLE"
    assert payload["current_settings"]["resolution"] == "1280x720"
