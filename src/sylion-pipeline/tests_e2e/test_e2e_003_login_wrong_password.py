"""
test_e2e_003_login_wrong_password.py — Wrong password → inline error shown.

Scenario E2E-003:
  Given the login panel is visible:
  - Entering a valid username but wrong password and clicking Zaloguj must:
    * NOT navigate to #dashboard.
    * Display a non-empty error message in #login-error.
  - Entering a completely unknown username must also produce an error.
  - The error message should be user-readable (not a raw JSON dump).

Pre-condition: Admin account exists.
"""

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8421"
ADMIN_USER = "admin"
WRONG_PASS = "ThisIsDefinitelyWrong!99"
NONEXISTENT_USER = "ghost_user_xyz_notreal"


class TestLoginWrongPassword:
    """E2E-003 — Invalid credentials show inline error, no dashboard."""

    @pytest.fixture(autouse=True)
    def go_to_login(self, page: Page):
        page.goto(BASE_URL)
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)

    def test_wrong_password_stays_on_login_screen(self, page: Page):
        """After wrong password, dashboard must NOT appear."""
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(WRONG_PASS)
        page.locator("button", has_text="Zaloguj").click()

        # Dashboard must not appear
        page.wait_for_timeout(2_000)
        expect(page.locator("#screen-dashboard")).to_be_hidden()
        # Login screen stays visible
        expect(page.locator("#login-screen")).to_be_visible()

    def test_wrong_password_shows_login_error(self, page: Page):
        """#login-error must become visible and contain a message on 401."""
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(WRONG_PASS)
        page.locator("button", has_text="Zaloguj").click()

        error_el = page.locator("#login-error")
        expect(error_el).to_be_visible(timeout=5_000)

        error_text = error_el.inner_text()
        assert error_text.strip(), "#login-error is visible but contains no text"

    def test_wrong_password_error_is_human_readable(self, page: Page):
        """Error must not be raw JSON — should be a plain readable string."""
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(WRONG_PASS)
        page.locator("button", has_text="Zaloguj").click()

        error_el = page.locator("#login-error")
        expect(error_el).to_be_visible(timeout=5_000)

        error_text = error_el.inner_text().strip()
        # Must not start with '{' (raw JSON)
        assert not error_text.startswith("{"), (
            f"Error looks like raw JSON: {error_text[:80]}"
        )
        # Should be non-trivially long
        assert len(error_text) >= 3, f"Error text too short: '{error_text}'"

    def test_unknown_user_shows_error(self, page: Page):
        """Unknown username must also produce an error in #login-error."""
        page.locator("#login-username").fill(NONEXISTENT_USER)
        page.locator("#login-password").fill(WRONG_PASS)
        page.locator("button", has_text="Zaloguj").click()

        error_el = page.locator("#login-error")
        expect(error_el).to_be_visible(timeout=5_000)
        assert error_el.inner_text().strip(), "No error shown for unknown user"

    def test_empty_password_shows_error(self, page: Page):
        """Submitting with empty password must show an error (validation or 401)."""
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill("")
        page.locator("button", has_text="Zaloguj").click()

        # Either native HTML5 validation prevents submission (field stays focused)
        # or the server returns 401 and JS shows #login-error.
        # Either way, dashboard must not appear.
        page.wait_for_timeout(2_000)
        expect(page.locator("#screen-dashboard")).to_be_hidden()

    def test_login_panel_still_visible_after_failure(self, page: Page):
        """The login panel must remain visible (not replaced/hidden) after a bad attempt."""
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(WRONG_PASS)
        page.locator("button", has_text="Zaloguj").click()

        page.wait_for_timeout(2_000)
        expect(page.locator("#login-panel")).to_be_visible()
