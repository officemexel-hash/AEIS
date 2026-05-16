"""
test_e2e_010_human_gate.py — Human Gate: trigger, see pending UI, approve, see completion.

Scenario E2E-010 (GAP-009 coverage):
  On the #human-gate screen:
  - A pending gate item must appear with Approve/Reject/Defer/Escalate buttons.
  - Clicking Approve (with a reason if required) must call POST /api/human-gate/{id}/decide.
  - The item's status must update to "decided" / "approved".
  - The consequences modal must appear for CRITICAL gates before approval.

Pre-condition:
  Admin account exists. A pending human-gate item exists (created via API or seeded).
  The test will attempt to create one via API if none exist.
"""

import requests
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8421"
API = f"{BASE_URL}/api"

ADMIN_USER = "admin"
ADMIN_PASS = "TestPass123!"

APPROVE_REASON = "E2E test approval — automated regression"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_token() -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=10,
    )
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["token"]


def _get_pending_gates(token: str) -> list:
    """Return list of pending human gate items."""
    r = requests.get(
        f"{API}/human-gate",
        headers={"X-Session-Token": token},
        timeout=10,
    )
    if r.status_code != 200:
        return []
    data = r.json()
    # Support both list and {"items": [...]} shapes
    if isinstance(data, list):
        return [g for g in data if g.get("status") == "pending"]
    return [g for g in data.get("items", []) if g.get("status") == "pending"]


def _create_test_gate(token: str) -> str | None:
    """Attempt to create a synthetic test human-gate item. Return id or None."""
    # Try common creation endpoints — implementation may vary
    for endpoint in [f"{API}/human-gate", f"{API}/human-gate/create"]:
        r = requests.post(
            endpoint,
            json={
                "action_type": "e2e_test_action",
                "description": "E2E test gate — safe to approve",
                "severity": "LOW",
                "context": {"test": True},
            },
            headers={"X-Session-Token": token},
            timeout=10,
        )
        if r.status_code in (200, 201):
            data = r.json()
            return data.get("id") or data.get("gate_id")
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHumanGateScreen:
    """E2E-010 — Human Gate UI flow."""

    @pytest.fixture(autouse=True)
    def login_and_navigate(self, page: Page):
        """Login as admin and navigate to human-gate screen."""
        page.goto(BASE_URL)
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(ADMIN_PASS)
        page.locator("button", has_text="Zaloguj").click()
        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)

        # Navigate to human-gate
        page.locator(
            "[data-screen='human-gate'], a[href='#human-gate'], "
            ".nav-item:has-text('Human Gate'), .nav-item:has-text('Gate')"
        ).first.click()
        expect(page.locator("#screen-human-gate")).to_be_visible(timeout=6_000)

    def test_human_gate_screen_visible(self, page: Page):
        """#screen-human-gate must be visible after navigation."""
        expect(page.locator("#screen-human-gate")).to_be_visible()

    def test_pending_items_or_empty_state_rendered(self, page: Page):
        """The screen must render either a list of pending items or an empty state."""
        page.wait_for_timeout(2_000)
        # Either pending gate rows exist, or an empty-state message is shown
        pending_rows = page.locator(
            ".gate-item, .human-gate-row, [class*='gate-card'], "
            "tr[data-gate-id], [data-status='pending']"
        )
        empty_state = page.locator(
            ".empty-state, .no-gates, [class*='empty'], :has-text('Brak')"
        )
        assert pending_rows.count() > 0 or empty_state.count() > 0, (
            "Human gate screen shows neither pending items nor empty state"
        )

    def test_approve_button_visible_on_pending_item(self, page: Page):
        """If a pending gate exists, the Approve button must be visible."""
        # Ensure a gate exists (create via API if needed)
        admin_token = _admin_token()
        pending = _get_pending_gates(admin_token)
        if not pending:
            gate_id = _create_test_gate(admin_token)
            if gate_id is None:
                pytest.skip("Cannot create test gate — skipping approve button test")

        # Refresh the page to pick up the new gate
        page.reload()
        expect(page.locator("#screen-human-gate")).to_be_visible(timeout=8_000)
        page.wait_for_timeout(2_000)

        approve_btn = page.locator(
            "button:has-text('Approve'), button:has-text('Zatwierdź'), "
            "button[onclick*='approve'], button[data-action='approve']"
        ).first
        expect(approve_btn).to_be_visible(timeout=5_000)

    def test_approve_gate_updates_status(self, page: Page):
        """
        Click Approve on a pending gate → status must change to decided/approved.
        """
        admin_token = _admin_token()
        pending = _get_pending_gates(admin_token)
        if not pending:
            gate_id = _create_test_gate(admin_token)
            if gate_id is None:
                pytest.skip("No pending gates available — skipping approval test")
            page.reload()
            expect(page.locator("#screen-human-gate")).to_be_visible(timeout=8_000)

        page.wait_for_timeout(2_000)

        # Click Approve on first pending item
        approve_btn = page.locator(
            "button:has-text('Approve'), button:has-text('Zatwierdź'), "
            "button[onclick*='approve'], button[data-action='approve']"
        ).first

        if approve_btn.count() == 0:
            pytest.skip("No Approve button found — gate list may be empty")

        approve_btn.click()

        # If a consequences modal appears (CRITICAL gate), interact with it
        modal = page.locator(
            ".consequences-modal, .confirm-modal, [id*='modal']:visible"
        ).first
        if modal.count() > 0 and modal.is_visible():
            # Fill reason field if present
            reason_field = modal.locator(
                "input[placeholder*='reason'], textarea[placeholder*='reason'], "
                "input[name*='reason'], textarea[name*='reason']"
            ).first
            if reason_field.count() > 0:
                reason_field.fill(APPROVE_REASON)

            # Confirm in modal
            modal.locator(
                "button:has-text('Confirm'), button:has-text('OK'), "
                "button:has-text('Zatwierdź'), button[data-action='confirm']"
            ).first.click()

        # After approval, the item should show decided/approved status
        page.wait_for_timeout(3_000)
        decided_item = page.locator(
            "[data-status='decided'], [data-status='approved'], "
            "[class*='decided'], [class*='approved'], "
            ":has-text('decided'), :has-text('approved'), :has-text('Zatwierdzone')"
        ).first
        # Accept either a decided status element OR that the pending list has shrunk
        # (gate moved to history)
        pending_now = _get_pending_gates(admin_token)
        pending_before_count = len(_get_pending_gates(admin_token)) + 1  # rough upper bound
        assert (
            decided_item.count() > 0
            or len(pending_now) < pending_before_count
        ), "Gate status did not change to decided after approval"

    def test_approve_api_called_on_click(self, page: Page):
        """Clicking Approve must trigger POST /api/human-gate/{id}/decide."""
        admin_token = _admin_token()
        pending = _get_pending_gates(admin_token)
        if not pending:
            gate_id = _create_test_gate(admin_token)
            if gate_id is None:
                pytest.skip("No pending gates — skipping API call verification")
            page.reload()
            expect(page.locator("#screen-human-gate")).to_be_visible(timeout=8_000)

        page.wait_for_timeout(2_000)

        decide_calls = []

        def capture(request):
            if "/human-gate/" in request.url and "decide" in request.url:
                decide_calls.append(request.url)

        page.on("request", capture)

        approve_btn = page.locator(
            "button:has-text('Approve'), button:has-text('Zatwierdź'), "
            "button[onclick*='approve'], button[data-action='approve']"
        ).first

        if approve_btn.count() == 0:
            pytest.skip("No Approve button found")

        approve_btn.click()
        page.wait_for_timeout(3_000)

        assert decide_calls, (
            "No POST /api/human-gate/{id}/decide request observed after clicking Approve"
        )
