"""
test_e2e_001_first_setup.py â€” First-time setup flow.

Scenario E2E-001:
  Given an empty database (needs_setup=true), the app must:
  - Show the setup panel (not the login panel).
  - Auto-load the setup token from /api/auth/setup-token-hint into #setup-token.
  - Accept username + password, create the admin account.
  - Redirect to the login panel after successful setup.
  - Allow the newly created admin to log in and see the dashboard.

Pre-condition:
  App started against a fresh DB (rm -f ~/sylion/sylion.db then python -m sylion.server --host 127.0.0.1 --http-port 8421).
  This test is ORDER-SENSITIVE and must run FIRST in the suite.

NOTE: If the DB already has an admin, setup-panel will not show and these tests
      will be skipped automatically.
"""

import requests
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8421"
API = f"{BASE_URL}/api"

SETUP_ADMIN_USER = "admin"
SETUP_ADMIN_PASS = "TestPass123!"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def needs_setup() -> bool:
    """Return True if the app is in first-time setup mode."""
    try:
        r = requests.get(f"{API}/auth/status", timeout=5)
        return r.json().get("needs_setup", False)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFirstTimeSetup:
    """E2E-001 â€” Full first-time setup through the browser."""

    @pytest.fixture(autouse=True)
    def skip_if_already_setup(self):
        if not needs_setup():
            pytest.skip("App already set up â€” E2E-001 requires a fresh DB.")

    def test_setup_panel_visible_on_first_load(self, page: Page):
        """Visiting / when needs_setup=true should show #setup-panel, not #login-panel."""
        page.goto(BASE_URL)
        # The login screen container should be visible
        expect(page.locator("#login-screen")).to_be_visible(timeout=8_000)
        # The setup panel (not login panel) should be shown
        expect(page.locator("#setup-panel")).to_be_visible(timeout=5_000)
        expect(page.locator("#login-panel")).to_be_hidden(timeout=3_000)

    def test_setup_token_auto_loaded(self, page: Page):
        """#setup-token field must be populated automatically via autoLoadToken()."""
        page.goto(BASE_URL)
        expect(page.locator("#setup-panel")).to_be_visible(timeout=8_000)
        # Wait for JS to call /api/auth/setup-token-hint and fill the input
        setup_token_input = page.locator("#setup-token")
        expect(setup_token_input).to_be_visible(timeout=5_000)
        # Token value should be non-empty after auto-load
        page.wait_for_function(
            "document.querySelector('#setup-token') && "
            "document.querySelector('#setup-token').value.trim().length > 0",
            timeout=5_000,
        )
        token_value = setup_token_input.input_value()
        assert token_value.strip(), "#setup-token was not auto-populated by autoLoadToken()"

    def test_setup_fields_present(self, page: Page):
        """Setup form must have username, password, confirm-password fields and submit."""
        page.goto(BASE_URL)
        expect(page.locator("#setup-panel")).to_be_visible(timeout=8_000)
        expect(page.locator("#setup-token")).to_be_visible()
        expect(page.locator("#setup-username")).to_be_visible()
        expect(page.locator("#setup-password")).to_be_visible()
        expect(page.locator("#setup-password2")).to_be_visible()
        # Submit button
        expect(
            page.locator("button", has_text="UtwĂłrz").or_(
                page.locator("button", has_text="Setup")
            ).or_(
                page.locator("button[onclick*='doSetup']")
            ).first
        ).to_be_visible()

    def test_full_setup_creates_admin_and_allows_login(self, page: Page):
        """
        Complete setup: fill form â†’ submit â†’ setup completes â†’ login with new creds â†’
        dashboard visible.
        """
        page.goto(BASE_URL)
        expect(page.locator("#setup-panel")).to_be_visible(timeout=8_000)

        # Wait for token auto-load
        page.wait_for_function(
            "document.querySelector('#setup-token') && "
            "document.querySelector('#setup-token').value.trim().length > 0",
            timeout=5_000,
        )

        # Fill username and passwords
        page.locator("#setup-username").fill(SETUP_ADMIN_USER)
        page.locator("#setup-password").fill(SETUP_ADMIN_PASS)
        page.locator("#setup-password2").fill(SETUP_ADMIN_PASS)

        # Click the setup/create button
        page.locator(
            "button:has-text('UtwĂłrz'), button:has-text('Setup'), button[onclick*='doSetup']"
        ).first.click()

        # After setup, login panel should appear (setup_token consumed)
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)
        expect(page.locator("#setup-panel")).to_be_hidden(timeout=5_000)

        # Log in with new credentials
        page.locator("#login-username").fill(SETUP_ADMIN_USER)
        page.locator("#login-password").fill(SETUP_ADMIN_PASS)
        page.locator("button", has_text="Zaloguj").click()

        # Dashboard must appear
        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)
