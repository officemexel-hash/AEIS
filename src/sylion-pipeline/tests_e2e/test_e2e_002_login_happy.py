"""
test_e2e_002_login_happy.py — Login happy path + KPI visible.

Scenario E2E-002:
  Given a set-up app with an existing admin account:
  - The login panel (#login-panel) is shown.
  - Entering correct credentials and clicking Zaloguj navigates to #dashboard.
  - The dashboard screen (#screen-dashboard) becomes visible.
  - At least one KPI widget (.kpi-card) is rendered.
  - The navigation bar is present.

Pre-condition: Admin account exists (E2E-001 completed or DB pre-seeded).
"""

import re
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8421"
ADMIN_USER = "admin"
ADMIN_PASS = "TestPass123!"


class TestLoginHappyPath:
    """E2E-002 — Valid credentials → dashboard visible."""

    @pytest.fixture(autouse=True)
    def go_to_app(self, page: Page):
        page.goto(BASE_URL)
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)

    def test_login_panel_contains_expected_fields(self, page: Page):
        """Login form should have username, password fields and a submit button."""
        expect(page.locator("#login-username")).to_be_visible()
        expect(page.locator("#login-password")).to_be_visible()
        expect(page.locator("button", has_text="Zaloguj")).to_be_visible()

    def test_login_success_redirects_to_dashboard(self, page: Page):
        """Valid credentials must navigate the SPA to the #dashboard hash."""
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(ADMIN_PASS)
        page.locator("button", has_text="Zaloguj").click()

        # URL should contain #dashboard
        expect(page).to_have_url(re.compile(r"#dashboard"), timeout=8_000)

    def test_dashboard_screen_visible_after_login(self, page: Page):
        """#screen-dashboard must become visible after successful login."""
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(ADMIN_PASS)
        page.locator("button", has_text="Zaloguj").click()

        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)

    def test_kpi_card_rendered_after_login(self, page: Page):
        """At least one .kpi-card element should render on the dashboard."""
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(ADMIN_PASS)
        page.locator("button", has_text="Zaloguj").click()

        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)

        kpi_cards = page.locator(".kpi-card")
        expect(kpi_cards.first).to_be_visible(timeout=6_000)

    def test_navbar_visible_after_login(self, page: Page):
        """Navigation bar / sidebar should appear after login."""
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(ADMIN_PASS)
        page.locator("button", has_text="Zaloguj").click()

        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)

        # Nav can be a sidebar, top nav, or nav-bar — look for any nav element
        nav = page.locator("nav, #sidebar, .nav-bar, #main-nav, .sidebar").first
        expect(nav).to_be_visible(timeout=5_000)

    def test_login_error_hidden_on_success(self, page: Page):
        """#login-error must not be visible after a successful login."""
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(ADMIN_PASS)
        page.locator("button", has_text="Zaloguj").click()

        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)
        # Error element should remain hidden
        expect(page.locator("#login-error")).to_be_hidden()
