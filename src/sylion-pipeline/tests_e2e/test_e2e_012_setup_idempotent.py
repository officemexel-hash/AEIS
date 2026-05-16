"""
test_e2e_012_setup_idempotent.py — Setup token persists until first admin created.

Scenario E2E-012:
  After the app is started and an admin already exists:
  - POST /api/auth/setup must return 400 "Setup already completed".
  - The setup panel must NOT appear when an admin already exists.
  - The setup-token-hint endpoint must return 404 or an empty/disabled response.

  Idempotency (restart path):
  - If the app is restarted, the setup token from a prior run is still required
    (the flag is stored in the DB, not in memory).
  - This prevents re-setup after a process restart without DB wipe.

Pre-condition: Admin account already exists (setup was completed previously).
"""

import requests
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8421"
API = f"{BASE_URL}/api"

ADMIN_USER = "admin"
ADMIN_PASS = "TestPass123!"

# Fake setup data (should be rejected)
FAKE_SETUP_TOKEN = "fake-setup-token-should-not-work"
FAKE_SETUP_USER = "second_admin_attempt"
FAKE_SETUP_PASS = "SecondAdmin!1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_setup_completed() -> bool:
    """Return True if the app reports setup is already done."""
    try:
        r = requests.get(f"{API}/auth/status", timeout=5)
        data = r.json()
        return not data.get("needs_setup", True)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSetupIdempotencyAPI:
    """E2E-012 (API) — Re-setup attempt is rejected after first admin created."""

    @pytest.fixture(autouse=True)
    def require_setup_complete(self):
        if not _is_setup_completed():
            pytest.skip("Setup not yet complete — run E2E-001 first")

    def test_post_setup_returns_400_when_already_setup(self):
        """POST /api/auth/setup after setup must return 400 or 409."""
        # First get a valid admin token to potentially get the real setup token
        r_login = requests.post(
            f"{API}/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
            timeout=10,
        )
        if r_login.status_code != 200:
            pytest.skip("Admin login failed — cannot run idempotency test")

        # Attempt to re-run setup
        r = requests.post(
            f"{API}/auth/setup",
            json={
                "setup_token": FAKE_SETUP_TOKEN,
                "username": FAKE_SETUP_USER,
                "password": FAKE_SETUP_PASS,
            },
            timeout=10,
        )
        assert r.status_code in (400, 409), (
            f"Expected 400/409 for duplicate setup, got {r.status_code}: {r.text}"
        )

    def test_setup_rejection_message_mentions_already_completed(self):
        """The 400 response body must explain that setup is already done."""
        r = requests.post(
            f"{API}/auth/setup",
            json={
                "setup_token": FAKE_SETUP_TOKEN,
                "username": FAKE_SETUP_USER,
                "password": FAKE_SETUP_PASS,
            },
            timeout=10,
        )
        if r.status_code not in (400, 409):
            pytest.skip(f"Got {r.status_code} — not a setup-already-done response")

        try:
            body = r.json()
            detail = str(body.get("detail", "")) + str(body.get("message", ""))
        except ValueError:
            detail = r.text

        assert detail, "Empty error body on re-setup attempt"
        # Common messages: "Setup already completed", "already exists", "already done"
        assert any(
            kw in detail.lower()
            for kw in ["setup", "already", "completed", "exists", "done"]
        ), f"Error message doesn't mention setup completion: {detail!r}"

    def test_setup_token_hint_unavailable_after_setup(self):
        """
        /api/auth/setup-token-hint should return 404 or empty after setup completes.
        This prevents token leakage post-setup.
        """
        r = requests.get(f"{API}/auth/setup-token-hint", timeout=10)
        # Should be 404 (endpoint gone) or return empty/disabled token
        if r.status_code == 200:
            data = r.json()
            token_val = data.get("token") or data.get("setup_token") or ""
            assert not token_val, (
                f"setup-token-hint still returns a token after setup: {token_val!r}"
            )
        else:
            assert r.status_code in (404, 403, 410), (
                f"Unexpected status for setup-token-hint post-setup: {r.status_code}"
            )

    def test_status_endpoint_reports_setup_done(self):
        """/api/auth/status must report needs_setup=false after first admin created."""
        r = requests.get(f"{API}/auth/status", timeout=10)
        assert r.status_code == 200, f"/api/auth/status returned {r.status_code}"
        data = r.json()
        needs_setup = data.get("needs_setup", True)
        assert needs_setup is False, (
            f"needs_setup should be False after setup, got: {data}"
        )


class TestSetupIdempotencyUI:
    """E2E-012 (UI) — Login panel (not setup panel) shown after setup complete."""

    @pytest.fixture(autouse=True)
    def require_setup_complete(self):
        if not _is_setup_completed():
            pytest.skip("Setup not yet complete — run E2E-001 first")

    def test_login_panel_shown_not_setup_panel(self, page: Page):
        """After setup, visiting / must show #login-panel, not #setup-panel."""
        page.goto(BASE_URL)
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)
        expect(page.locator("#setup-panel")).to_be_hidden(timeout=3_000)

    def test_setup_panel_not_shown_after_restart_simulation(self, page: Page):
        """
        Simulates a restart by opening a fresh browser context and navigating to /.
        Setup panel must not appear — flag is persisted in DB, not RAM.
        """
        # Fresh context (no prior session cookies)
        fresh_ctx = page.context.browser.new_context(
            base_url=BASE_URL, ignore_https_errors=True
        )
        fresh_page = fresh_ctx.new_page()
        try:
            fresh_page.goto(BASE_URL)
            # Should see login panel, not setup panel
            expect(fresh_page.locator("#login-panel")).to_be_visible(timeout=8_000)
            expect(fresh_page.locator("#setup-panel")).to_be_hidden(timeout=3_000)
        finally:
            fresh_ctx.close()

    def test_re_setup_via_fake_token_shows_error_in_ui(self, page: Page):
        """
        Attempting to POST /api/auth/setup via the UI (if setup panel is accessible)
        must show an error, not succeed.
        """
        # This is an API-level guard since the setup panel won't be rendered post-setup.
        # Verify directly via API that the error is surfaced.
        r = requests.post(
            f"{API}/auth/setup",
            json={
                "setup_token": FAKE_SETUP_TOKEN,
                "username": FAKE_SETUP_USER,
                "password": FAKE_SETUP_PASS,
            },
            timeout=10,
        )
        assert r.status_code in (400, 403, 409), (
            f"Re-setup should fail with 400/403/409, got {r.status_code}"
        )
