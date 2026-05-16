"""Tests for sylion.devices.device_discovery -- DeviceDiscoveryService."""

import json
import time
from unittest.mock import patch, MagicMock

import pytest

from sylion.devices.device_discovery import DeviceDiscoveryService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def svc():
    """Fresh in-memory DeviceDiscoveryService per test."""
    return DeviceDiscoveryService(db_path=":memory:")


def _mock_adb_output(device_lines: str) -> MagicMock:
    """Create a mock subprocess result with ADB-style output."""
    result = MagicMock()
    result.stdout = f"List of devices attached\n{device_lines}"
    return result


def _mock_arp_output(lines: str) -> MagicMock:
    """Create a mock subprocess result with ARP-style output."""
    result = MagicMock()
    result.stdout = lines
    return result


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_in_memory_db(self, svc):
        assert svc._db_path == ":memory:"

    def test_empty_devices_initially(self, svc):
        devices = svc.list_devices()
        assert devices == []

    def test_event_bus_default_none(self, svc):
        assert svc._event_bus is None


# ---------------------------------------------------------------------------
# scan() -- ADB
# ---------------------------------------------------------------------------

class TestScanADB:
    @patch("sylion.devices.device_discovery.subprocess")
    def test_scan_adb_finds_device(self, mock_subprocess, svc):
        adb_output = "R5CR30ABCDE  device product:flame model:Pixel_6 device:oriole\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        result = svc.scan("usb")
        assert len(result) == 1
        assert result[0]["device_id"] == "adb-R5CR30ABCDE"
        assert result[0]["transport"] == "usb"
        assert result[0]["model"] == "Pixel_6"

    @patch("sylion.devices.device_discovery.subprocess")
    def test_scan_adb_empty(self, mock_subprocess, svc):
        mock_subprocess.run.return_value = _mock_adb_output("")
        result = svc.scan("usb")
        assert result == []

    @patch("sylion.devices.device_discovery.subprocess")
    def test_scan_adb_unauthorized_skipped(self, mock_subprocess, svc):
        adb_output = "R5CR30ABCDE  unauthorized\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)
        result = svc.scan("usb")
        assert result == []

    def test_scan_adb_not_installed(self, svc):
        """ADB not found should return empty list, not crash."""
        with patch("sylion.devices.device_discovery.subprocess") as mock_sub:
            mock_sub.run.side_effect = FileNotFoundError
            result = svc._scan_adb()
            assert result == []

    @patch("sylion.devices.device_discovery.subprocess")
    def test_scan_adb_multiple_devices(self, mock_subprocess, svc):
        adb_output = (
            "SERIAL1  device product:flame model:Pixel_8 device:shiba\n"
            "SERIAL2  device product:lynx model:Pixel_7 device:lynx\n"
        )
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)
        result = svc.scan("usb")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# scan() -- Network / SSH
# ---------------------------------------------------------------------------

class TestScanNetwork:
    def _make_sock_factory(self, open_ports: dict[int, int]):
        """Return a socket factory where connect_ex returns 0 for specified ports."""
        call_count = {"n": 0}
        port_order = [22, 23, 80, 443, 8080, 8443, 161]

        def factory(*a, **kw):
            sock = MagicMock()
            # Determine which port is being probed based on call order
            idx = call_count["n"]
            call_count["n"] += 1
            # Map call index to port
            if idx < len(port_order):
                port = port_order[idx]
            else:
                port = 0
            if port in open_ports:
                sock.connect_ex.return_value = 0
                if port == 22:
                    sock.recv.return_value = open_ports[port]
                elif port in (80, 8080):
                    sock.recv.return_value = open_ports[port]
            else:
                sock.connect_ex.return_value = 1
            return sock
        return factory

    @patch("sylion.devices.device_discovery.socket")
    @patch("sylion.devices.device_discovery.subprocess")
    def test_scan_network_finds_ssh_host(self, mock_subprocess, mock_socket, svc):
        arp_output = "? (192.168.1.1) at aa:bb:cc:dd:ee:ff on eth0\n"
        mock_subprocess.run.return_value = _mock_arp_output(arp_output)
        mock_socket.socket.side_effect = self._make_sock_factory({
            22: b"SSH-2.0-dropbear 2020\n",
        })

        result = svc._scan_network()
        assert len(result) >= 1
        assert result[0]["transport"] == "wifi"
        assert "net-" in result[0]["device_id"]

    @patch("sylion.devices.device_discovery.socket")
    @patch("sylion.devices.device_discovery.subprocess")
    def test_scan_network_identifies_openwrt(self, mock_subprocess, mock_socket, svc):
        arp_output = "? (10.0.0.1) at 11:22:33:44:55:66 on eth0\n"
        mock_subprocess.run.return_value = _mock_arp_output(arp_output)
        mock_socket.socket.side_effect = self._make_sock_factory({
            22: b"SSH-2.0-OpenWrt dropbear\n",
        })

        result = svc._scan_network()
        assert len(result) >= 1
        assert result[0]["model"] == "OpenWrt Router"

    @patch("sylion.devices.device_discovery.subprocess")
    def test_scan_network_empty_arp(self, mock_subprocess, svc):
        mock_subprocess.run.return_value = _mock_arp_output("")
        result = svc._scan_network()
        assert result == []

    def test_scan_network_arp_not_found(self, svc):
        with patch("sylion.devices.device_discovery.subprocess") as mock_sub:
            mock_sub.run.side_effect = FileNotFoundError
            result = svc._scan_network()
            assert result == []

    @patch("sylion.devices.device_discovery.socket")
    @patch("sylion.devices.device_discovery.subprocess")
    def test_scan_network_http_device(self, mock_subprocess, mock_socket, svc):
        arp_output = "? (192.168.1.50) at aa:bb:cc:dd:ee:ff on eth0\n"
        mock_subprocess.run.return_value = _mock_arp_output(arp_output)
        mock_socket.socket.side_effect = self._make_sock_factory({
            80: b"HTTP/1.1 200 OK\r\nServer: OpenWrt\r\n\r\n",
        })

        result = svc._scan_network()
        assert len(result) >= 1
        assert result[0]["model"] == "OpenWrt Router"


# ---------------------------------------------------------------------------
# scan() -- Persistence and events
# ---------------------------------------------------------------------------

class TestScanPersistence:
    @patch("sylion.devices.device_discovery.subprocess")
    def test_scan_persists_to_db(self, mock_subprocess, svc):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        svc.scan("usb")
        all_devices = svc.list_devices()
        assert len(all_devices) >= 1

    @patch("sylion.devices.device_discovery.subprocess")
    def test_scan_status_is_detected(self, mock_subprocess, svc):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        result = svc.scan("usb")
        for d in result:
            assert d["status"] == "detected"

    @patch("sylion.devices.device_discovery.subprocess")
    def test_scan_entries_have_required_fields(self, mock_subprocess, svc):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        result = svc.scan("usb")
        for d in result:
            assert "device_id" in d
            assert "transport" in d
            assert "model" in d
            assert "firmware" in d
            assert "capabilities" in d
            assert "status" in d
            assert "discovered_at" in d

    @patch("sylion.devices.device_discovery.subprocess")
    def test_scan_capabilities_is_dict(self, mock_subprocess, svc):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        result = svc.scan("usb")
        for d in result:
            assert isinstance(d["capabilities"], dict)


# ---------------------------------------------------------------------------
# get_device()
# ---------------------------------------------------------------------------

class TestGetDevice:
    @patch("sylion.devices.device_discovery.subprocess")
    def test_get_existing_device(self, mock_subprocess, svc):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        devices = svc.scan("usb")
        device_id = devices[0]["device_id"]
        device = svc.get_device(device_id)
        assert device is not None
        assert device["device_id"] == device_id
        assert isinstance(device["capabilities"], dict)

    def test_get_nonexistent_returns_none(self, svc):
        assert svc.get_device("nonexistent-id") is None


# ---------------------------------------------------------------------------
# list_devices()
# ---------------------------------------------------------------------------

class TestListDevices:
    @patch("sylion.devices.device_discovery.subprocess")
    def test_list_all(self, mock_subprocess, svc):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        svc.scan("usb")
        devices = svc.list_devices()
        assert len(devices) >= 1

    def test_empty_list_without_scan(self, svc):
        assert svc.list_devices() == []

    @patch("sylion.devices.device_discovery.subprocess")
    def test_filter_by_transport(self, mock_subprocess, svc):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        svc.scan("usb")
        usb = svc.list_devices(transport="usb")
        assert len(usb) >= 1
        for d in usb:
            assert d["transport"] == "usb"

    @patch("sylion.devices.device_discovery.subprocess")
    def test_filter_by_status(self, mock_subprocess, svc):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        svc.scan("usb")
        detected = svc.list_devices(status="detected")
        assert len(detected) >= 1

    @patch("sylion.devices.device_discovery.subprocess")
    def test_filter_by_nonexistent_status(self, mock_subprocess, svc):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        svc.scan("usb")
        assert svc.list_devices(status="nonexistent") == []


# ---------------------------------------------------------------------------
# release()
# ---------------------------------------------------------------------------

class TestRelease:
    @patch("sylion.devices.device_discovery.subprocess")
    def test_release_existing_device(self, mock_subprocess, svc):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        devices = svc.scan("usb")
        device_id = devices[0]["device_id"]
        result = svc.release(device_id)
        assert result is not None
        assert result["status"] == "released"

    def test_release_nonexistent_returns_none(self, svc):
        assert svc.release("no-such-device") is None

    @patch("sylion.devices.device_discovery.subprocess")
    def test_release_updates_in_db(self, mock_subprocess, svc):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        devices = svc.scan("usb")
        device_id = devices[0]["device_id"]
        svc.release(device_id)
        device = svc.get_device(device_id)
        assert device["status"] == "released"

    @patch("sylion.devices.device_discovery.subprocess")
    def test_released_device_not_in_detected_filter(self, mock_subprocess, svc):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        devices = svc.scan("usb")
        device_id = devices[0]["device_id"]
        svc.release(device_id)
        detected = svc.list_devices(status="detected")
        ids = [d["device_id"] for d in detected]
        assert device_id not in ids


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

class TestEvents:
    @patch("sylion.devices.device_discovery.subprocess")
    def test_emit_with_mock_bus(self, mock_subprocess):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        events = []

        class MockBus:
            def publish(self, event):
                events.append(event)

        svc = DeviceDiscoveryService(db_path=":memory:", event_bus=MockBus())
        svc.scan("usb")
        attached = [e for e in events if e.topic == "device.attached"]
        assert len(attached) >= 1

    @patch("sylion.devices.device_discovery.subprocess")
    def test_release_emits_event(self, mock_subprocess):
        adb_output = "SERIAL1  device product:flame model:Pixel_8\n"
        mock_subprocess.run.return_value = _mock_adb_output(adb_output)

        events = []

        class MockBus:
            def publish(self, event):
                events.append(event)

        svc = DeviceDiscoveryService(db_path=":memory:", event_bus=MockBus())
        devices = svc.scan("usb")
        svc.release(devices[0]["device_id"])
        released = [e for e in events if e.topic == "device.released"]
        assert len(released) == 1
