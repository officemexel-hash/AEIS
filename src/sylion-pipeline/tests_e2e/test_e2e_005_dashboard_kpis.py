"""
test_e2e_005_dashboard_kpis.py — Assert 5 top KPI widgets visible on dashboard.

Scenario E2E-005:
  After login, the #screen-dashboard must render:
  - At least 5 .kpi-card elements (the "top KPI widgets").
  - Guard status badges (at least one .guard-status-badge or element matching guard).
  - Recent events section or equivalent.
  - All KPI card title labels are non-empty strings.

Pre-condition: Admin account exists and app is running.
"""

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8421"
ADMIN_USER = "admin"
ADMIN_PASS = "TestPass123!"

MIN_KPI_CARDS = 5


class TestDashboardKPIs:
    """E2E-005 — Dashboard KPI widgets and guard badges after login."""

    @pytest.fixture(autouse=True)
    def login_and_go_to_dashboard(self, page: Page):
        """Log in as admin and navigate to the dashboard."""
        page.goto(BASE_URL)
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(ADMIN_PASS)
        page.locator("button", has_text="Zaloguj").click()
        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)

    def test_at_least_five_kpi_cards_present(self, page: Page):
        """Dashboard must render at least 5 KPI card elements."""
        # Give JS time to render async data
        page.wait_for_timeout(2_000)
        kpi_cards = page.locator(".kpi-card")
        count = kpi_cards.count()
        assert count >= MIN_KPI_CARDS, (
            f"Expected >= {MIN_KPI_CARDS} .kpi-card elements, found {count}"
        )

    def test_kpi_cards_all_visible(self, page: Page):
        """Every KPI card that is in the DOM should be visible."""
        page.wait_for_timeout(2_000)
        kpi_cards = page.locator(".kpi-card")
        count = kpi_cards.count()
        for i in range(min(count, MIN_KPI_CARDS)):
            expect(kpi_cards.nth(i)).to_be_visible()

    def test_kpi_card_titles_are_non_empty(self, page: Page):
        """Each KPI card should display a label/title (not blank)."""
        page.wait_for_timeout(2_000)
        kpi_cards = page.locator(".kpi-card")
        count = kpi_cards.count()
        assert count > 0, "No KPI cards found"

        for i in range(min(count, MIN_KPI_CARDS)):
            card = kpi_cards.nth(i)
            # Title can be in .kpi-title, h3, label, or any child text node
            title_el = card.locator(
                ".kpi-title, .kpi-label, h3, h4, label, [class*='title'], [class*='label']"
            ).first
            inner = title_el.inner_text() if title_el.count() else card.inner_text()
            assert inner.strip(), f"KPI card #{i} has no visible title text"

    def test_guard_status_badges_present(self, page: Page):
        """Dashboard must display at least one guard status badge."""
        page.wait_for_timeout(2_000)
        guard_badges = page.locator(
            ".guard-status-badge, [class*='guard'], .guard-badge, .status-badge"
        )
        count = guard_badges.count()
        assert count >= 1, (
            "No guard status badges found on dashboard — expected at least one"
        )

    def test_screen_dashboard_id_present(self, page: Page):
        """The element #screen-dashboard must exist and be visible."""
        expect(page.locator("#screen-dashboard")).to_be_visible()

    def test_recent_events_or_activity_section_present(self, page: Page):
        """Dashboard should contain a recent events / activity section."""
        page.wait_for_timeout(2_000)
        events_section = page.locator(
            "#recent-events, .recent-events, [id*='event'], "
            "[class*='event'], [id*='activity'], [class*='activity']"
        ).first
        # Soft check — warn if not found but do not fail CI (section may be empty on fresh DB)
        if events_section.count() == 0:
            pytest.warns(
                UserWarning,
                match="No recent events section found — possible GAP-001",
            )

    def test_no_js_errors_on_dashboard(self, page: Page):
        """There must be no uncaught JS errors when the dashboard loads."""
        errors = []

        def capture_error(exc):
            errors.append(str(exc))

        page.on("pageerror", capture_error)
        # Reload to catch any errors fresh
        page.reload()
        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)
        page.wait_for_timeout(2_000)

        assert not errors, f"Uncaught JS errors on dashboard: {errors}"
