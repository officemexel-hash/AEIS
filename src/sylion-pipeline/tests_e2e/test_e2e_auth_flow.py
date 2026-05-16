"""
test_e2e_auth_flow.py — Authentication critical-path E2E tests.

Covers 5 scenarios:
  AUTH-001  setup_token_one_shot        — setup token consumed after first use
  AUTH-002  login_success               — valid credentials → dashboard visible
  AUTH-003  login_wrong_password        — invalid credentials → inline error shown
  AUTH-004  logout_flush_csrf           — logout clears cookie + CSRF token
  AUTH-005  password_change_session_revoke — password change must invalidate old session

Pre-condition: SYLION app running on http://127.0.0.1:8421 with admin account seeded.
               Playwright installed: pip install pytest-playwright && playwright install chromium
"""

import re
import time

import requests
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "http://127.0.0.1:8421"
API = f"{BASE_URL}/api"
ADMIN_USER = "admin"
ADMIN_PASS = "TestPass123!"
NEW_PASS = "NewSecurePass99!"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skip_if_no_server():
    """Skip test if the app is not reachable."""
    try:
        requests.get(f"{API}/auth/status", timeout=4)
    except Exception:
        pytest.skip("SYLION app not reachable on http://127.0.0.1:8421")


def _admin_token(user: str = ADMIN_USER, password: str = ADMIN_PASS) -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"username": user, "password": password},
        timeout=10,
    )
    assert r.status_code == 200, f"Admin login failed ({r.status_code}): {r.text}"
    return r.json()["token"]


def _needs_setup() -> bool:
    try:
        r = requests.get(f"{API}/auth/status", timeout=5)
        return r.json().get("needs_setup", False)
    except Exception:
        return False


def _login_via_ui(page, user: str = ADMIN_USER, password: str = ADMIN_PASS):
    """Helper: navigate to app and perform UI login."""
    page.goto(BASE_URL)
    page.locator("#login-panel").wait_for(state="visible", timeout=8_000)
    page.locator("#login-username").fill(user)
    page.locator("#login-password").fill(password)
    page.locator("button", has_text="Zaloguj").click()


# ---------------------------------------------------------------------------
# AUTH-001 — Setup token is one-shot (consumed after first use)
# ---------------------------------------------------------------------------


class TestSetupTokenOneShot:
    """AUTH-001 — /api/auth/setup-token-hint must return 404/400 after setup is done."""

    def test_setup_token_one_shot(self, page):
        """
        Once first-time setup is complete, /api/auth/setup-token-hint must refuse
        to vend a new token (HTTP 4xx).  If setup has not been run yet, the
        endpoint must still serve the hint exactly once and the setup panel must
        vanish from the UI afterwards.
        """
        _skip_if_no_server()

        if not _needs_setup():
            # App is already configured — verify the hint endpoint is locked
            r = requests.get(f"{API}/auth/setup-token-hint", timeout=5)
            assert r.status_code in (400, 403, 404, 410), (
                f"setup-token-hint should be disabled after setup; got {r.status_code}"
            )
        else:
            # Fresh DB: perform setup via UI, then verify the token is gone
            page.goto(BASE_URL)
            page.locator("#setup-panel").wait_for(state="visible", timeout=8_000)

            # Wait for auto-load of token
            page.wait_for_function(
                "document.querySelector('#setup-token') && "
                "document.querySelector('#setup-token').value.trim().length > 0",
                timeout=6_000,
            )

            # Grab the token value before consuming it
            token_before = page.locator("#setup-token").input_value()
            assert token_before.strip(), "Setup token was not auto-loaded into #setup-token"

            # Complete setup
            page.locator("#setup-username").fill(ADMIN_USER)
            page.locator("#setup-password").fill(ADMIN_PASS)
            page.locator("#setup-password2").fill(ADMIN_PASS)
            page.locator(
                "button:has-text('Utwórz'), button:has-text('Setup'), button[onclick*='doSetup']"
            ).first.click()

            page.locator("#login-panel").wait_for(state="visible", timeout=8_000)

            # After setup, the hint endpoint must be locked
            r = requests.get(f"{API}/auth/setup-token-hint", timeout=5)
            assert r.status_code in (400, 403, 404, 410), (
                f"Token hint still available after setup consumed it; got {r.status_code}. "
                "This is a security issue — token must be one-shot."
            )


# ---------------------------------------------------------------------------
# AUTH-002 — Login success redirects to dashboard
# ---------------------------------------------------------------------------


class TestLoginSuccess:
    """AUTH-002 — Valid credentials produce a visible dashboard."""

    @pytest.fixture(autouse=True)
    def skip_if_needs_setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode — run AUTH-001 first")

    def test_login_success_dashboard_visible(self, page):
        """
        Entering ADMIN_USER / ADMIN_PASS via the UI must:
          - Navigate the SPA to #dashboard,
          - Make #screen-dashboard visible,
          - Show at least one .kpi-card.
        """
        from playwright.sync_api import expect

        _login_via_ui(page)
        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)

        # URL must contain the dashboard hash
        expect(page).to_have_url(re.compile(r"#dashboard"), timeout=5_000)

        # At least one KPI card
        page.wait_for_timeout(1_500)
        kpi = page.locator(".kpi-card").first
        expect(kpi).to_be_visible(timeout=6_000)

        # Route call to /api/auth/status should show authenticated=true
        r = requests.get(
            f"{API}/auth/status",
            cookies={c["name"]: c["value"] for c in page.context.cookies()},
            timeout=5,
        )
        data = r.json()
        assert data.get("authenticated") or data.get("user") or data.get("username"), (
            f"API reports not authenticated after UI login: {data}"
        )


# ---------------------------------------------------------------------------
# AUTH-003 — Login wrong password shows inline error
# ---------------------------------------------------------------------------


class TestLoginWrongPassword:
    """AUTH-003 — Invalid credentials must show inline error, not crash."""

    @pytest.fixture(autouse=True)
    def skip_if_needs_setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode — run AUTH-001 first")

    def test_wrong_password_shows_error(self, page):
        """
        Submitting a wrong password must:
          - Keep the login panel visible (no redirect),
          - Display an error element (#login-error or .login-error),
          - Not expose any stack trace in the visible DOM.
        """
        from playwright.sync_api import expect

        page.goto(BASE_URL)
        page.locator("#login-panel").wait_for(state="visible", timeout=8_000)

        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill("totally-wrong-password-XYZ")
        page.locator("button", has_text="Zaloguj").click()

        # Login panel must remain visible (no redirect to dashboard)
        page.wait_for_timeout(2_000)
        expect(page.locator("#login-panel")).to_be_visible(timeout=5_000)
        expect(page.locator("#screen-dashboard")).to_be_hidden(timeout=3_000)

        # An error element must appear
        error_el = page.locator(
            "#login-error, .login-error, [class*='error']:visible, "
            ".alert-danger, [role='alert']:visible"
        ).first
        expect(error_el).to_be_visible(timeout=5_000)

        error_text = error_el.inner_text()
        assert error_text.strip(), "Error element is visible but contains no text"

        # Must NOT expose stack trace or internal detail
        assert "Traceback" not in error_text and "Exception" not in error_text, (
            f"Error message exposes internal stack trace: {error_text}"
        )

    def test_wrong_password_api_returns_401(self):
        """API must return 401 for wrong password (not 500)."""
        _skip_if_no_server()
        r = requests.post(
            f"{API}/auth/login",
            json={"username": ADMIN_USER, "password": "wrong_password_E2E"},
            timeout=8,
        )
        assert r.status_code == 401, (
            f"Expected 401 for wrong password, got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# AUTH-004 — Logout flushes CSRF token and redirects to login
# ---------------------------------------------------------------------------


class TestLogoutFlushCsrf:
    """AUTH-004 — Logout must clear session cookie and any CSRF token."""

    @pytest.fixture(autouse=True)
    def skip_if_needs_setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode — run AUTH-001 first")

    def test_logout_returns_to_login_panel(self, page):
        """
        After clicking the logout button:
          - #login-panel must reappear.
          - #screen-dashboard must become hidden.
          - A follow-up request with the old session cookie must be rejected (401).
        """
        from playwright.sync_api import expect

        _login_via_ui(page)
        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)

        # Capture session cookie before logout
        cookies_before = {c["name"]: c["value"] for c in page.context.cookies()}

        # Click logout — accept any common selector
        page.locator(
            "button:has-text('Wyloguj'), button:has-text('Logout'), "
            "#logout-btn, [onclick*='logout'], [data-action='logout'], "
            ".logout-btn, a:has-text('Wyloguj'), a:has-text('Logout')"
        ).first.click()

        # Login panel must reappear
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)
        expect(page.locator("#screen-dashboard")).to_be_hidden(timeout=5_000)

        # Old session cookie must no longer grant access
        if cookies_before:
            r = requests.get(
                f"{API}/auth/status",
                cookies=cookies_before,
                timeout=5,
            )
            data = r.json()
            assert not data.get("authenticated", True) or r.status_code in (401, 403), (
                "Old session cookie still grants access after logout — session not invalidated"
            )

    def test_logout_clears_browser_cookies(self, page):
        """
        After logout, the browser context must not carry a live session cookie.
        """
        from playwright.sync_api import expect

        _login_via_ui(page)
        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)

        # Logout
        page.locator(
            "button:has-text('Wyloguj'), button:has-text('Logout'), "
            "#logout-btn, [onclick*='logout'], [data-action='logout']"
        ).first.click()

        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)

        # Check that no session-like cookies remain
        remaining_cookies = page.context.cookies()
        session_cookies = [
            c for c in remaining_cookies
            if any(kw in c["name"].lower() for kw in ("session", "token", "auth", "csrf"))
            and c.get("value", "")
        ]
        # Acceptable: no session cookies, or session cookie exists but is cleared (empty value)
        live_session = [c for c in session_cookies if c["value"] not in ("", "deleted")]
        assert not live_session, (
            f"Live session/auth cookies remain after logout: "
            f"{[c['name'] for c in live_session]}"
        )


# ---------------------------------------------------------------------------
# AUTH-005 — Password change must revoke existing sessions
# ---------------------------------------------------------------------------


class TestPasswordChangeSessionRevoke:
    """
    AUTH-005 — Changing a user's password via PUT /api/users/{id} must
    invalidate all existing sessions for that user (MEDIUM-001 regression guard).

    NOTE: Per README MEDIUM-001, the current implementation may NOT revoke
    sessions (the bug is known). This test asserts the CORRECT behaviour.
    Mark xfail if the fix has not yet landed.
    """

    @pytest.fixture(autouse=True)
    def skip_if_needs_setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode — run AUTH-001 first")

    @pytest.mark.xfail(
        reason="MEDIUM-001: PUT /api/users/{id} does not yet invalidate sessions after password change",
        strict=False,
    )
    def test_password_change_revokes_old_session(self, page):
        """
        Workflow:
          1. Login as admin → obtain session cookie.
          2. Change password via API (with old token).
          3. Use the OLD session cookie → must get 401 (session revoked).
          4. Login with new password → must succeed.
          5. Restore original password (cleanup).
        """
        from playwright.sync_api import expect

        # Step 1: login and capture session
        _login_via_ui(page)
        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)
        old_cookies = {c["name"]: c["value"] for c in page.context.cookies()}
        old_token = _admin_token()

        # Step 2: change password via API
        # Discover user ID
        me_r = requests.get(
            f"{API}/auth/me",
            headers={"X-Session-Token": old_token},
            timeout=8,
        )
        user_id = (
            me_r.json().get("id") or me_r.json().get("user_id") or "1"
            if me_r.status_code == 200
            else "1"
        )

        change_r = requests.put(
            f"{API}/users/{user_id}",
            json={"password": NEW_PASS},
            headers={"X-Session-Token": old_token},
            timeout=10,
        )
        assert change_r.status_code in (200, 204), (
            f"Password change failed: {change_r.status_code} {change_r.text}"
        )

        # Step 3: old session must now be rejected
        status_r = requests.get(
            f"{API}/auth/status",
            cookies=old_cookies,
            timeout=5,
        )
        assert status_r.status_code in (401, 403) or not status_r.json().get("authenticated", True), (
            "MEDIUM-001: Old session is still valid after password change — "
            "sessions must be revoked on password change"
        )

        # Step 4: new password must work
        new_token = _admin_token(password=NEW_PASS)
        assert new_token, "Could not log in with new password"

        # Step 5: restore original password (cleanup)
        requests.put(
            f"{API}/users/{user_id}",
            json={"password": ADMIN_PASS},
            headers={"X-Session-Token": new_token},
            timeout=10,
        )
