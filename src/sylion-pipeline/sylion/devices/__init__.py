"""SYLION Devices -- discovery, registry, deployment, and on-device testing."""

from sylion.devices.device_discovery import DeviceDiscoveryService, get_device_discovery
from sylion.devices.device_registry import DeviceRegistry, get_device_registry
from sylion.devices.artifact_deployer import ArtifactDeployer, get_artifact_deployer
from sylion.devices.test_harness import OnDeviceTestHarness, get_on_device_test_harness

__all__ = [
    "DeviceDiscoveryService",
    "get_device_discovery",
    "DeviceRegistry",
    "get_device_registry",
    "ArtifactDeployer",
    "get_artifact_deployer",
    "OnDeviceTestHarness",
    "get_on_device_test_harness",
]
