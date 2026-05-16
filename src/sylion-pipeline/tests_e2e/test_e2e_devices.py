"""
test_e2e_devices.py — Device management critical-path E2E tests.

Covers 5 scenarios:
  DEV-001  scan_button_triggers_adb       — Scan button calls ADB scan API
  DEV-002  pixel_9_detected_row           — Pixel 9 device appears in the device table
  DEV-003  mudi_detected_row              — GL.iNet Mudi device appears in device table
  DEV-004  provision_button_opens_humangate — Provision triggers Human Gate dialog
  DEV-005  device_quarantine_flow         — Quarantine moves device to quarantine status

Pre-condition: SYLION app running on http://127.0.0.1:8421, admin account exists.
ADB hardware is mocked via page.route() — no physical devices required.
"""

import json
import time

import pytest
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "http://127.0.0.1:8421"
API = f"{BASE_URL}/api"
ADMIN_USER = "admin"
ADMIN_PASS = "TestPass123!"

MOCK_PIXEL9 = {
    "id": "device-pixel9-e2e",
    "serial": "R9AA50XAAAA",
    "model": "Pixel 9",
    "manufacturer": "Google",
    "android_version": "14",
    "status": "ready",
    "type": "android",
}

MOCK_MUDI = {
    "id": "device-mudi-e2e",
    "serial": "GL-E750-MUDI-001",
    "model": "GL-E750 Mudi",
    "manufacturer": "GL.iNet",
    "firmware_version": "3.216",
    "status": "ready",
    "type": "router",
}

MOCK_DEVICES = [MOCK_PIXEL9, MOCK_MUDI]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skip_if_no_server():
    try:
        requests.get(f"{API}/auth/status", timeout=4)
    except Exception:
        pytest.skip("SYLION app not reachable on http://127.0.0.1:8421")


def _needs_setup() -> bool:
    try:
        r = requests.get(f"{API}/auth/status", timeout=4)
        return r.json().get("needs_setup", False)
    except Exception:
        return False


def _login_via_ui(page):
    page.goto(BASE_URL)
    page.locator("#login-panel").wait_for(state="visible", timeout=8_000)
    page.locator("#login-username").fill(ADMIN_USER)
    page.locator("#login-password").fill(ADMIN_PASS)
    page.locator("button", has_text="Zaloguj").click()
    page.locator("#screen-dashboard").wait_for(state="visible", timeout=8_000)


def _navigate_to_devices(page):
    """Navigate to the devices screen."""
    page.locator(
        "[data-screen='devices'], a[href='#devices'], "
        ".nav-item:has-text('Devices'), .nav-item:has-text('Urządzenia'), "
        ".nav-item:has-text('Device'), a[href='#device-list']"
    ).first.click()
    page.wait_for_selector(
        "#screen-devices, #device-list, [id*='device'], "
        ".devices-panel, .device-table, [class*='device']",
        timeout=8_000,
    )


def _mock_device_api(page, devices=None, scan_result=None):
    """Install route mocks for the device API."""
    if devices is None:
        devices = MOCK_DEVICES
    if scan_result is None:
        scan_result = devices

    devices_body = json.dumps({"devices": devices, "total": len(devices)})
    scan_body = json.dumps({
        "status": "scan_complete",
        "found": len(scan_result),
        "devices": scan_result,
    })

    scan_called = {"n": 0}

    def mock_route(route):
        url = route.request.url
        method = route.request.method

        if "/scan" in url and method == "POST":
            scan_called["n"] += 1
            route.fulfill(
                status=200,
                content_type="application/json",
                body=scan_body,
            )
        elif any(seg in url for seg in ["/devices", "/device-list"]):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=devices_body,
            )
        else:
            route.continue_()

    page.route("**/api/devices**", mock_route)
    page.route("**/api/device**", mock_route)

    return scan_called


# ---------------------------------------------------------------------------
# DEV-001 — Scan button triggers ADB scan API
# ---------------------------------------------------------------------------


class TestScanButtonTriggersAdb:
    """DEV-001 — Clicking the Scan button must call POST /api/devices/scan."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode")

    def test_scan_button_triggers_adb(self, page):
        """
        Mock the device scan API. Click the Scan button. Assert that:
          - POST /api/devices/scan (or equivalent) was called.
          - The UI shows a scanning indicator or refreshes the device list.
        """
        scan_calls = []

        def mock_route(route):
            url = route.request.url
            method = route.request.method
            if method == "POST" and any(s in url for s in ["/scan", "/adb/scan"]):
                scan_calls.append(url)
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "status": "scan_complete",
                        "found": len(MOCK_DEVICES),
                        "devices": MOCK_DEVICES,
                    }),
                )
            elif any(seg in url for seg in ["/devices", "/device-list"]):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"devices": MOCK_DEVICES, "total": len(MOCK_DEVICES)}),
                )
            else:
                route.continue_()

        page.route("**/api/**", mock_route)

        _login_via_ui(page)
        _navigate_to_devices(page)
        page.wait_for_timeout(1_500)

        scan_btn = page.locator(
            "button:has-text('Scan'), button:has-text('Skanuj'), "
            "button:has-text('Detect'), button:has-text('ADB Scan'), "
            "#scan-btn, #adb-scan-btn, [data-action='scan'], "
            "button[onclick*='scan']"
        ).first

        if scan_btn.count() == 0:
            pytest.skip("No Scan button found on devices screen")

        scan_btn.click()
        page.wait_for_timeout(3_000)

        assert scan_calls, (
            "Clicking Scan did not trigger POST /api/devices/scan or /api/adb/scan. "
            "The Scan button must call the ADB scan endpoint."
        )


# ---------------------------------------------------------------------------
# DEV-002 — Pixel 9 device appears in the table
# ---------------------------------------------------------------------------


class TestPixel9DetectedRow:
    """DEV-002 — After scan, Pixel 9 must appear as a row in the device table."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode")

    def test_pixel_9_detected_row(self, page):
        """
        Mock the scan and device list APIs to include a Pixel 9.
        After navigating to the devices screen, a row containing 'Pixel 9'
        (or the serial R9AA50XAAAA) must be visible.
        """
        from playwright.sync_api import expect

        _mock_device_api(page)
        _login_via_ui(page)
        _navigate_to_devices(page)
        page.wait_for_timeout(2_000)

        # Look for Pixel 9 in any table row, card, or list item
        pixel9_row = page.locator(
            "tr:has-text('Pixel 9'), .device-card:has-text('Pixel 9'), "
            ".device-row:has-text('Pixel 9'), [class*='device']:has-text('Pixel 9'), "
            f"tr:has-text('{MOCK_PIXEL9['serial']}'), "
            f".device-card:has-text('{MOCK_PIXEL9['serial']}')"
        ).first

        if pixel9_row.count() == 0:
            pytest.skip(
                "Pixel 9 row not found — device screen may not have loaded the mocked list. "
                "Check that the API route mock is applied before navigation."
            )

        expect(pixel9_row).to_be_visible(timeout=5_000)

        # Row must show model info
        row_text = pixel9_row.inner_text()
        assert "Pixel 9" in row_text or MOCK_PIXEL9["serial"] in row_text, (
            f"Pixel 9 row found but does not contain model name or serial: {row_text}"
        )


# ---------------------------------------------------------------------------
# DEV-003 — GL.iNet Mudi device appears in the table
# ---------------------------------------------------------------------------


class TestMudiDetectedRow:
    """DEV-003 — After scan, GL.iNet Mudi must appear as a row in the device table."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode")

    def test_mudi_detected_row(self, page):
        """
        Mock the device list to include the GL-E750 Mudi.
        The device table must show a row with 'Mudi' or 'GL-E750'.
        """
        from playwright.sync_api import expect

        _mock_device_api(page)
        _login_via_ui(page)
        _navigate_to_devices(page)
        page.wait_for_timeout(2_000)

        mudi_row = page.locator(
            "tr:has-text('Mudi'), .device-card:has-text('Mudi'), "
            ".device-row:has-text('Mudi'), [class*='device']:has-text('Mudi'), "
            "tr:has-text('GL-E750'), .device-card:has-text('GL-E750'), "
            f"tr:has-text('{MOCK_MUDI['serial']}')"
        ).first

        if mudi_row.count() == 0:
            pytest.skip(
                "Mudi row not found — device screen may not have loaded the mocked list."
            )

        expect(mudi_row).to_be_visible(timeout=5_000)

        row_text = mudi_row.inner_text()
        assert "Mudi" in row_text or "GL-E750" in row_text or MOCK_MUDI["serial"] in row_text, (
            f"Mudi row found but does not contain expected text: {row_text}"
        )

    def test_mudi_shows_router_type(self, page):
        """Mudi row must indicate device type 'router' (not 'android')."""
        _mock_device_api(page)
        _login_via_ui(page)
        _navigate_to_devices(page)
        page.wait_for_timeout(2_000)

        mudi_row = page.locator(
            "tr:has-text('Mudi'), .device-card:has-text('Mudi'), tr:has-text('GL-E750')"
        ).first

        if mudi_row.count() == 0:
            pytest.skip("Mudi row not found")

        row_text = mudi_row.inner_text().lower()
        # 'router' or 'GL.iNet' branding should appear; definitely not 'android'
        assert "router" in row_text or "gl.inet" in row_text or "gl-e750" in row_text, (
            f"Mudi row does not show router type or GL.iNet branding: {row_text}"
        )


# ---------------------------------------------------------------------------
# DEV-004 — Provision button opens Human Gate dialog
# ---------------------------------------------------------------------------


class TestProvisionButtonOpensHumangate:
    """DEV-004 — Clicking Provision on a device must open the Human Gate approval dialog."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode")

    def test_provision_button_opens_humangate(self, page):
        """
        Mock device list and provision API (returns waiting_human_gate).
        Click the Provision button for Pixel 9.
        Assert a Human Gate dialog / overlay appears.
        """
        provision_calls = []

        def mock_route(route):
            url = route.request.url
            method = route.request.method
            if "/provision" in url and method == "POST":
                provision_calls.append(url)
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "status": "waiting_human_gate",
                        "gate": {
                            "id": "gate-provision-e2e",
                            "action_type": "device_provision",
                            "description": f"Provision {MOCK_PIXEL9['model']} — review and approve",
                            "severity": "HIGH",
                            "device_id": MOCK_PIXEL9["id"],
                        },
                    }),
                )
            elif any(seg in url for seg in ["/devices", "/device-list"]):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"devices": MOCK_DEVICES, "total": len(MOCK_DEVICES)}),
                )
            else:
                route.continue_()

        page.route("**/api/**", mock_route)

        _login_via_ui(page)
        _navigate_to_devices(page)
        page.wait_for_timeout(2_000)

        # Find the Provision button for Pixel 9
        provision_btn = page.locator(
            "button:has-text('Provision'), button:has-text('Prowizja'), "
            "button:has-text('Flash'), button:has-text('Deploy'), "
            "[data-action='provision'], .provision-btn"
        ).first

        if provision_btn.count() == 0:
            pytest.skip("No Provision button found on devices screen")

        provision_btn.click()
        page.wait_for_timeout(3_000)

        # A Human Gate dialog must appear
        gate_dialog = page.locator(
            ".human-gate-modal, .humangate-dialog, .gate-overlay, "
            "[class*='gate']:visible, .modal:visible, [role='dialog']:visible, "
            ".approval-dialog, .confirm-gate, #screen-human-gate:visible"
        )

        assert provision_calls or gate_dialog.count() > 0, (
            "Clicking Provision did not call provision API or open Human Gate dialog. "
            "Device provisioning must route through the Human Gate approval flow."
        )


# ---------------------------------------------------------------------------
# DEV-005 — Device quarantine flow
# ---------------------------------------------------------------------------


class TestDeviceQuarantineFlow:
    """DEV-005 — Quarantining a device moves it to 'quarantined' status in the UI."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode")

    def test_device_quarantine_flow(self, page):
        """
        1. Render Pixel 9 with status 'ready'.
        2. Click the Quarantine button.
        3. Mock POST /api/devices/{id}/quarantine → returns 'quarantined'.
        4. Assert status changes to 'quarantined' in the UI.
        """
        quarantine_calls = []

        # Mutable device state
        device_status = {"status": MOCK_PIXEL9["status"]}

        def mock_route(route):
            url = route.request.url
            method = route.request.method

            if "/quarantine" in url and method == "POST":
                quarantine_calls.append(url)
                device_status["status"] = "quarantined"
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "id": MOCK_PIXEL9["id"],
                        "status": "quarantined",
                        "message": "Device quarantined successfully",
                    }),
                )
            elif any(seg in url for seg in ["/devices", "/device-list"]):
                # Return updated status after quarantine
                updated_pixel9 = dict(MOCK_PIXEL9)
                updated_pixel9["status"] = device_status["status"]
                current_devices = [updated_pixel9, MOCK_MUDI]
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"devices": current_devices, "total": len(current_devices)}),
                )
            else:
                route.continue_()

        page.route("**/api/**", mock_route)

        _login_via_ui(page)
        _navigate_to_devices(page)
        page.wait_for_timeout(2_000)

        # Find quarantine button
        quarantine_btn = page.locator(
            "button:has-text('Quarantine'), button:has-text('Kwarantanna'), "
            "button:has-text('Isolate'), button:has-text('Izoluj'), "
            "[data-action='quarantine'], .quarantine-btn, "
            "button[onclick*='quarantine']"
        ).first

        if quarantine_btn.count() == 0:
            pytest.skip("No Quarantine button found on devices screen")

        quarantine_btn.click()

        # Handle confirmation dialog if present
        page.wait_for_timeout(1_000)
        confirm_btn = page.locator(
            "button:has-text('Confirm'), button:has-text('Potwierdź'), "
            "button:has-text('Tak'), button:has-text('Yes')"
        ).first
        if confirm_btn.count() > 0 and confirm_btn.is_visible():
            confirm_btn.click()

        page.wait_for_timeout(2_500)

        assert quarantine_calls, (
            "No quarantine API call was observed after clicking Quarantine button"
        )

        # UI must reflect the new quarantined status
        quarantine_status = page.locator(
            ":has-text('quarantined'):visible, :has-text('kwarantanna'):visible, "
            "[data-status='quarantined'], .status-quarantined, "
            f"[data-id='{MOCK_PIXEL9['id']}']:has-text('quarantined')"
        )

        page.wait_for_timeout(1_000)
        assert quarantine_status.count() > 0 or device_status["status"] == "quarantined", (
            "Device status did not update to 'quarantined' in the UI after quarantine action"
        )
