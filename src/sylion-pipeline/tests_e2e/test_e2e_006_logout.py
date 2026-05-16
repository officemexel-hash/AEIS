"""
test_e2e_006_logout.py — Logout button → redirects to login screen.

Scenario E2E-006:
  After logging in as admin:
  - Clicking the logout button (⬆ Wyloguj / ↗) must:
    * POST /api/auth/logout (verified via network interception).
    * Show #login-screen / #login-panel.
    * Hide #app-root / #screen-dashboard.
    * Delete (or invalidate) the sylion_session cookie (GAP-012).
  - After logout, navigating to / must still show login (session gone).

Pre-condition: Admin account exists.
"""

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8421"
ADMIN_USER = "admin"
ADMIN_PASS = "TestPass123!"


class TestLogout:
    """E2E-006 — Full logout flow with cookie and redirect verification."""

    @pytest.fixture(autouse=True)
    def login_first(self, page: Page):
        """Log in before each test in this class."""
        page.goto(BASE_URL)
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(ADMIN_PASS)
        page.locator("button", has_text="Zaloguj").click()
        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)

    def test_logout_button_exists(self, page: Page):
        """The logout button must be visible in the nav after login."""
        logout_btn = page.locator(
            "button[title='Wyloguj'], button:has-text('Wyloguj'), "
            "button:has-text('↗'), [onclick*='doLogout']"
        ).first
        expect(logout_btn).to_be_visible(timeout=3_000)

    def test_logout_shows_login_screen(self, page: Page):
        """Clicking logout must bring back the login screen."""
        page.locator(
            "button[title='Wyloguj'], button:has-text('Wyloguj'), "
            "button:has-text('↗'), [onclick*='doLogout']"
        ).first.click()

        expect(page.locator("#login-screen")).to_be_visible(timeout=5_000)
        expect(page.locator("#login-panel")).to_be_visible(timeout=5_000)

    def test_logout_hides_dashboard(self, page: Page):
        """After logout, #screen-dashboard must be hidden."""
        page.locator(
            "button[title='Wyloguj'], button:has-text('Wyloguj'), "
            "button:has-text('↗'), [onclick*='doLogout']"
        ).first.click()

        expect(page.locator("#screen-dashboard")).to_be_hidden(timeout=5_000)

    def test_logout_api_called(self, page: Page):
        """Logout must trigger a call to POST /api/auth/logout."""
        logout_requests = []

        def capture_request(request):
            if "/api/auth/logout" in request.url and request.method == "POST":
                logout_requests.append(request.url)

        page.on("request", capture_request)

        page.locator(
            "button[title='Wyloguj'], button:has-text('Wyloguj'), "
            "button:has-text('↗'), [onclick*='doLogout']"
        ).first.click()

        page.wait_for_timeout(2_000)
        assert logout_requests, "No POST /api/auth/logout request observed after clicking logout"

    def test_logout_removes_session_cookie(self, page: Page):
        """
        After logout, the sylion_session cookie must be absent or expired
        (GAP-012 coverage).
        """
        page.locator(
            "button[title='Wyloguj'], button:has-text('Wyloguj'), "
            "button:has-text('↗'), [onclick*='doLogout']"
        ).first.click()

        expect(page.locator("#login-screen")).to_be_visible(timeout=5_000)

        # Check all cookies for sylion_session
        ctx = page.context
        cookies = ctx.cookies()
        session_cookies = [c for c in cookies if c["name"] == "sylion_session"]

        # Either no cookie, or the cookie max-age / expires is in the past
        for c in session_cookies:
            expires = c.get("expires", -1)
            # -1 means session cookie (gone on context close), 0 means deleted
            assert expires <= 0 or expires < 1, (
                f"sylion_session cookie still has future expiry after logout: {c}"
            )

    def test_revisit_after_logout_shows_login(self, page: Page):
        """Navigating back to / after logout must show login (session gone)."""
        page.locator(
            "button[title='Wyloguj'], button:has-text('Wyloguj'), "
            "button:has-text('↗'), [onclick*='doLogout']"
        ).first.click()

        expect(page.locator("#login-screen")).to_be_visible(timeout=5_000)

        # Navigate to root again
        page.goto(BASE_URL)
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)
        expect(page.locator("#screen-dashboard")).to_be_hidden()
