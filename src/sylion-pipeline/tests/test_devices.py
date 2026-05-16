"""Tests for SYLION AEIS Device Integration modules (Class M)."""
import json
from unittest.mock import patch, MagicMock

import pytest


def _mock_adb(device_lines: str) -> MagicMock:
    r = MagicMock()
    r.stdout = f"List of devices attached\n{device_lines}"
    return r


# ===================================================================
# M1 — DeviceDiscoveryService
# ===================================================================

@patch("sylion.devices.device_discovery.subprocess")
def test_discovery_scan_returns_devices(mock_sub, bus):
    mock_sub.run.return_value = _mock_adb(
        "SERIAL1  device product:flame model:Pixel_8 device:oriole\n"
        "SERIAL2  device product:lynx model:Pixel_7 device:lynx\n"
    )
    from sylion.devices.device_discovery import DeviceDiscoveryService
    svc = DeviceDiscoveryService(event_bus=bus)
    devices = svc.scan(transport="usb")
    assert len(devices) == 2
    for d in devices:
        assert d["transport"] == "usb"
        assert d["status"] == "detected"
        assert d["device_id"].startswith("adb-")


@patch("sylion.devices.device_discovery.subprocess")
def test_discovery_get_and_list(mock_sub, bus):
    mock_sub.run.return_value = _mock_adb(
        "SERIAL1  device product:flame model:Pixel_8\n"
        "SERIAL2  device product:lynx model:Pixel_7\n"
    )
    from sylion.devices.device_discovery import DeviceDiscoveryService
    svc = DeviceDiscoveryService(event_bus=bus)
    devices = svc.scan(transport="usb")
    device_id = devices[0]["device_id"]

    got = svc.get_device(device_id)
    assert got is not None
    assert got["device_id"] == device_id

    all_devs = svc.list_devices()
    assert len(all_devs) >= 2

    filtered = svc.list_devices(transport="usb")
    assert len(filtered) == 2

    none_dev = svc.list_devices(transport="wifi")
    assert len(none_dev) == 0


@patch("sylion.devices.device_discovery.subprocess")
def test_discovery_release(mock_sub, bus):
    mock_sub.run.return_value = _mock_adb(
        "SERIAL1  device product:flame model:Pixel_8\n"
    )
    from sylion.devices.device_discovery import DeviceDiscoveryService
    svc = DeviceDiscoveryService(event_bus=bus)
    devices = svc.scan(transport="usb")
    device_id = devices[0]["device_id"]

    released = svc.release(device_id)
    assert released is not None
    assert released["status"] == "released"

    assert svc.release("nonexistent") is None


@patch("sylion.devices.device_discovery.subprocess")
def test_discovery_event_bus(mock_sub, bus):
    mock_sub.run.return_value = _mock_adb(
        "SERIAL1  device product:flame model:Pixel_8\n"
        "SERIAL2  device product:lynx model:Pixel_7\n"
    )
    from sylion.devices.device_discovery import DeviceDiscoveryService
    svc = DeviceDiscoveryService(event_bus=bus)
    svc.scan(transport="usb")
    events = bus.query(topic="device.attached")
    assert len(events) >= 2

    payload = json.loads(events[0]["payload"])
    svc.release(payload["device_id"])
    released_events = bus.query(topic="device.released")
    assert len(released_events) >= 1


# ===================================================================
# M2 — DeviceRegistry
# ===================================================================

def test_registry_register_and_get(bus):
    from sylion.devices.device_registry import DeviceRegistry
    reg = DeviceRegistry(event_bus=bus)
    result = reg.register("dev-001", "usb", "Pixel-8", firmware="1.0",
                          capabilities={"nfc": True})
    assert result["device_id"] == "dev-001"
    assert result["lifecycle"] == "attached"
    assert result["capabilities"]["nfc"] is True

    got = reg.get("dev-001")
    assert got is not None
    assert got["model"] == "Pixel-8"

    assert reg.get("nonexistent") is None


def test_registry_lifecycle_transitions(bus):
    from sylion.devices.device_registry import DeviceRegistry
    reg = DeviceRegistry(event_bus=bus)
    reg.register("dev-002", "bluetooth", "Watch-Pro")

    # attached -> identified -> quarantined -> authorized -> provisioned -> active -> released
    d = reg.transition("dev-002", "identified")
    assert d["lifecycle"] == "identified"

    d = reg.transition("dev-002", "quarantined")
    assert d["lifecycle"] == "quarantined"

    d = reg.transition("dev-002", "authorized")
    assert d["lifecycle"] == "authorized"

    d = reg.transition("dev-002", "provisioned")
    assert d["lifecycle"] == "provisioned"

    d = reg.transition("dev-002", "active")
    assert d["lifecycle"] == "active"

    d = reg.transition("dev-002", "released")
    assert d["lifecycle"] == "released"


def test_registry_invalid_transition(bus):
    from sylion.devices.device_registry import DeviceRegistry
    reg = DeviceRegistry(event_bus=bus)
    reg.register("dev-003", "wifi", "Tablet-X")

    # Cannot go attached -> active directly
    with pytest.raises(ValueError, match="Invalid transition"):
        reg.transition("dev-003", "active")

    # Unknown device
    with pytest.raises(ValueError, match="Device not found"):
        reg.transition("dev-999", "identified")

    # Unknown lifecycle state
    with pytest.raises(ValueError, match="Unknown lifecycle state"):
        reg.transition("dev-003", "nonexistent")


def test_registry_authorize(bus):
    from sylion.devices.device_registry import DeviceRegistry
    reg = DeviceRegistry(event_bus=bus)
    reg.register("dev-004", "usb", "AuthDevice")
    reg.transition("dev-004", "identified")
    reg.transition("dev-004", "quarantined")

    d = reg.authorize("dev-004", "admin@example.com")
    assert d["lifecycle"] == "authorized"
    assert d["authorized_by"] == "admin@example.com"

    # Cannot authorize a non-quarantined device
    with pytest.raises(ValueError, match="must be quarantined"):
        reg.authorize("dev-004", "other@example.com")


def test_registry_list_and_stats(bus):
    from sylion.devices.device_registry import DeviceRegistry
    reg = DeviceRegistry(event_bus=bus)
    reg.register("dev-s1", "usb", "M1")
    reg.register("dev-s2", "usb", "M2")
    reg.transition("dev-s2", "identified")

    all_devs = reg.list_devices()
    assert len(all_devs) == 2

    attached = reg.list_devices(lifecycle="attached")
    assert len(attached) == 1
    assert attached[0]["device_id"] == "dev-s1"

    stats = reg.get_stats()
    assert stats["total"] == 2
    assert stats["by_lifecycle"]["attached"] == 1
    assert stats["by_lifecycle"]["identified"] == 1


# ===================================================================
# M3 — ArtifactDeployer
# ===================================================================

def test_deployer_deploy_and_get(bus):
    from sylion.devices.artifact_deployer import ArtifactDeployer
    ad = ArtifactDeployer(event_bus=bus)
    result = ad.deploy("dev-d1", "deadbeef12345678", artifact_type="apk")
    assert result["deploy_id"].startswith("dep-")
    assert result["status"] == "deployed"
    assert result["device_id"] == "dev-d1"

    got = ad.get(result["deploy_id"])
    assert got is not None
    assert got["artifact_hash"] == "deadbeef12345678"
    assert got["artifact_type"] == "apk"


def test_deployer_rollback(bus):
    from sylion.devices.artifact_deployer import ArtifactDeployer
    ad = ArtifactDeployer(event_bus=bus)
    result = ad.deploy("dev-d2", "abcdef0123456789", artifact_type="firmware")
    deploy_id = result["deploy_id"]

    rolled = ad.rollback(deploy_id)
    assert rolled is not None
    assert rolled["status"] == "rolled_back"
    assert rolled["rollback_hash"] == "abcdef0123456789"

    # Rollback nonexistent returns None
    assert ad.rollback("nonexistent") is None


def test_deployer_list_deployments(bus):
    from sylion.devices.artifact_deployer import ArtifactDeployer
    ad = ArtifactDeployer(event_bus=bus)
    ad.deploy("dev-d3", "hash000000000001")
    ad.deploy("dev-d3", "hash000000000002")
    ad.deploy("dev-d4", "hash000000000003")

    all_deps = ad.list_deployments()
    assert len(all_deps) == 3

    dev_d3 = ad.list_deployments(device_id="dev-d3")
    assert len(dev_d3) == 2

    limited = ad.list_deployments(limit=1)
    assert len(limited) == 1


def test_deployer_dry_run(bus):
    from sylion.devices.artifact_deployer import ArtifactDeployer
    ad = ArtifactDeployer(event_bus=bus)

    # Valid hash
    result = ad.dry_run("dev-d5", "1234567890abcdef")
    assert result["valid"] is True
    assert result["dry_run"] is True
    assert len(result["warnings"]) == 0

    # Invalid hash (too short)
    result = ad.dry_run("dev-d5", "abc")
    assert result["valid"] is False
    assert len(result["warnings"]) >= 1


def test_deployer_event_bus(bus):
    from sylion.devices.artifact_deployer import ArtifactDeployer
    ad = ArtifactDeployer(event_bus=bus)
    result = ad.deploy("dev-ev", "hash_event_12345")
    deploy_id = result["deploy_id"]

    events = bus.query(topic="device.artifact.deployed")
    assert len(events) >= 1
    payload = json.loads(events[0]["payload"])
    assert payload["deploy_id"] == deploy_id

    ad.rollback(deploy_id)
    rb_events = bus.query(topic="device.artifact.rolled_back")
    assert len(rb_events) >= 1


# ===================================================================
# M4 — OnDeviceTestHarness
# ===================================================================

def test_harness_run_and_get(bus):
    from sylion.devices.test_harness import OnDeviceTestHarness
    th = OnDeviceTestHarness(event_bus=bus)
    result = th.run_test("dev-t1", suite="contract")
    assert result["test_id"].startswith("tst-")
    assert result["device_id"] == "dev-t1"
    assert result["suite"] == "contract"
    assert result["status"] == "passed"
    assert result["pass_rate"] == 1.0
    assert result["duration_ms"] > 0

    got = th.get_results(result["test_id"])
    assert got is not None
    assert got["status"] == "passed"


def test_harness_list_tests(bus):
    from sylion.devices.test_harness import OnDeviceTestHarness
    th = OnDeviceTestHarness(event_bus=bus)
    th.run_test("dev-t2", suite="contract")
    th.run_test("dev-t2", suite="integration")
    th.run_test("dev-t3", suite="e2e")

    all_tests = th.list_tests()
    assert len(all_tests) == 3

    dev_t2_tests = th.list_tests(device_id="dev-t2")
    assert len(dev_t2_tests) == 2

    limited = th.list_tests(limit=1)
    assert len(limited) == 1


def test_harness_stats(bus):
    from sylion.devices.test_harness import OnDeviceTestHarness
    th = OnDeviceTestHarness(event_bus=bus)
    th.run_test("dev-t4", suite="contract")
    th.run_test("dev-t4", suite="integration")

    stats = th.get_stats("dev-t4")
    assert stats["total"] == 2
    assert stats["passed"] == 2
    assert stats["failed"] == 0
    assert stats["pass_rate"] == 1.0

    # No tests for unknown device
    empty_stats = th.get_stats("dev-unknown")
    assert empty_stats["total"] == 0
    assert empty_stats["pass_rate"] == 0.0


def test_harness_event_bus(bus):
    from sylion.devices.test_harness import OnDeviceTestHarness
    th = OnDeviceTestHarness(event_bus=bus)
    result = th.run_test("dev-t5", suite="e2e")

    events = bus.query(topic="device.test.completed")
    assert len(events) >= 1
    payload = json.loads(events[0]["payload"])
    assert payload["test_id"] == result["test_id"]
    assert payload["status"] == "passed"


# ===================================================================
# Singleton getters
# ===================================================================

def test_singletons():
    from sylion.devices.device_discovery import get_device_discovery
    from sylion.devices.device_registry import get_device_registry
    from sylion.devices.artifact_deployer import get_artifact_deployer
    from sylion.devices.test_harness import get_on_device_test_harness

    disc = get_device_discovery()
    assert disc is not None
    assert get_device_discovery() is disc  # same instance

    reg = get_device_registry()
    assert reg is not None
    assert get_device_registry() is reg

    dep = get_artifact_deployer()
    assert dep is not None
    assert get_artifact_deployer() is dep

    th = get_on_device_test_harness()
    assert th is not None
    assert get_on_device_test_harness() is th
