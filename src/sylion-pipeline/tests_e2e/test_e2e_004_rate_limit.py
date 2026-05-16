"""
test_e2e_004_rate_limit.py — 5+ failed attempts in 5 min → 429 lockout.

Scenario E2E-004:
  - 6 consecutive failed login API calls must yield at least one HTTP 429.
  - The 429 response must include a Retry-After header.
  - The UI must display a visible, non-empty error when IP is locked (GAP-003).

WARNING: This test uses a unique fake username to avoid locking the admin account.
         Running against a shared server may still affect the same IP for real users.

Pre-condition: App running, fresh IP state (or awaiting lockout expiry).
"""

import time
import requests
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8421"
API = f"{BASE_URL}/api"

# Use a user that definitely doesn't exist — avoids admin lockout
FAKE_USER = "rate_limit_nonexistent_abc123"
FAKE_PASS = "WrongPasswordForRateTest!"

# How many attempts to make (backend locks after _LOGIN_RATE_LIMIT_MAX=5)
ATTEMPT_COUNT = 7


class TestRateLimitAPI:
    """E2E-004 (API layer) — consecutive failures trigger HTTP 429."""

    def test_sixth_attempt_returns_429(self):
        """
        Make ATTEMPT_COUNT login attempts with wrong credentials.
        At least one response must be 429.
        """
        session = requests.Session()
        statuses = []
        for _ in range(ATTEMPT_COUNT):
            r = session.post(
                f"{API}/auth/login",
                json={"username": FAKE_USER, "password": FAKE_PASS},
                timeout=10,
            )
            statuses.append(r.status_code)

        assert 429 in statuses, (
            f"Expected HTTP 429 after {ATTEMPT_COUNT} bad attempts but got: {statuses}"
        )

    def test_429_includes_retry_after_header(self):
        """When rate-limited, the response must carry a Retry-After header."""
        session = requests.Session()
        last_429 = None
        for _ in range(ATTEMPT_COUNT):
            r = session.post(
                f"{API}/auth/login",
                json={"username": FAKE_USER, "password": FAKE_PASS},
                timeout=10,
            )
            if r.status_code == 429:
                last_429 = r

        assert last_429 is not None, (
            f"No 429 response observed after {ATTEMPT_COUNT} attempts"
        )
        assert "Retry-After" in last_429.headers, (
            "429 response is missing the Retry-After header"
        )
        retry_after = int(last_429.headers["Retry-After"])
        assert retry_after > 0, f"Retry-After must be positive, got {retry_after}"

    def test_429_body_contains_error_message(self):
        """The 429 response body must contain a descriptive error (not empty)."""
        session = requests.Session()
        last_429 = None
        for _ in range(ATTEMPT_COUNT):
            r = session.post(
                f"{API}/auth/login",
                json={"username": FAKE_USER, "password": FAKE_PASS},
                timeout=10,
            )
            if r.status_code == 429:
                last_429 = r

        if last_429 is None:
            pytest.skip("No 429 observed — rate limiter may not be triggered yet")

        # Body should be JSON with a detail/message field
        try:
            body = last_429.json()
            detail = body.get("detail", "") or body.get("message", "")
            assert detail, f"429 body has no detail/message: {body}"
        except ValueError:
            assert last_429.text.strip(), "429 response body is empty"


class TestRateLimitUI:
    """E2E-004 (UI layer) — after lockout, UI must show error, not silent failure."""

    def _trigger_lockout(self):
        """Call the API enough times to trigger rate limiting."""
        session = requests.Session()
        for _ in range(ATTEMPT_COUNT):
            session.post(
                f"{API}/auth/login",
                json={"username": FAKE_USER, "password": FAKE_PASS},
                timeout=10,
            )

    def test_ui_shows_error_when_ip_locked(self, page: Page):
        """
        After triggering lockout via API, a UI login attempt must show
        a visible error message in #login-error (GAP-003 coverage).
        """
        self._trigger_lockout()

        page.goto(BASE_URL)
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)

        page.locator("#login-username").fill(FAKE_USER)
        page.locator("#login-password").fill(FAKE_PASS)
        page.locator("button", has_text="Zaloguj").click()

        error_el = page.locator("#login-error")
        expect(error_el).to_be_visible(timeout=5_000)

        error_text = error_el.inner_text().strip()
        assert error_text, (
            "#login-error is visible but empty — UI may have silently swallowed the 429 (GAP-003)"
        )

    def test_ui_does_not_navigate_to_dashboard_when_locked(self, page: Page):
        """Rate-limited login must never land the user on the dashboard."""
        self._trigger_lockout()

        page.goto(BASE_URL)
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)

        page.locator("#login-username").fill(FAKE_USER)
        page.locator("#login-password").fill(FAKE_PASS)
        page.locator("button", has_text="Zaloguj").click()

        page.wait_for_timeout(2_000)
        expect(page.locator("#screen-dashboard")).to_be_hidden()
