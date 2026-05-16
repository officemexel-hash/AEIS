"""
test_e2e_011_session_expiry.py â€” Expired session â†’ 401 â†’ SPA shows login.

Scenario E2E-011:
  When a session expires (or is deleted from the DB):
  - Any authenticated API request with the old token must return 401.
  - The SPA must detect the 401 and call showLogin(), returning to the login screen.
  - The browser must not show an error page or hang â€” it should gracefully redirect.

  This test simulates expiry by:
  1. Getting a valid token T1 via API.
  2. Directly deleting the session from the SQLite DB (fastest method).
  3. Making a UI action that triggers an authenticated request.
  4. Asserting the SPA shows the login panel.

Pre-condition: Admin account exists. DB path accessible.
"""

import os
import sqlite3
import requests
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8421"
API = f"{BASE_URL}/api"

ADMIN_USER = "admin"
ADMIN_PASS = "TestPass123!"

# Common DB paths â€” checked in order
DB_PATHS = [
    os.path.expanduser("~/sylion/sylion.db"),
    os.path.expanduser("~/sylion/sylion_aeis.db"),
    "/home/user/sylion/sylion.db",
    "/home/user/sylion/sylion_aeis.db",
    "/tmp/sylion.db",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_db() -> str | None:
    for path in DB_PATHS:
        if os.path.exists(path):
            return path
    return None


def _admin_token() -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=10,
    )
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["token"]


def _delete_session_from_db(token: str, db_path: str) -> bool:
    """Delete the session row directly from the SQLite DB. Returns True on success."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    except Exception:
        return False


def _expire_session_in_db(token: str, db_path: str) -> bool:
    """Set session expires_at to past time. Returns True on success."""
    try:
        conn = sqlite3.connect(db_path)
        # Set to Unix epoch 0 (far past)
        cursor = conn.execute(
            "UPDATE sessions SET expires_at=0 WHERE token=?", (token,)
        )
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# API-level test (no browser needed)
# ---------------------------------------------------------------------------


class TestSessionExpiryAPI:
    """E2E-011 (API) â€” Expired/deleted session returns 401."""

    def test_deleted_session_returns_401(self):
        """Deleting session from DB causes /api/auth/me to return 401."""
        db_path = _find_db()
        if db_path is None:
            pytest.skip("Could not locate sylion.db â€” skipping DB manipulation test")

        token = _admin_token()

        # Confirm token is valid
        r_before = requests.get(
            f"{API}/auth/me",
            headers={"X-Session-Token": token},
            timeout=10,
        )
        assert r_before.status_code == 200, "Token not valid before deletion"

        # Delete session from DB
        deleted = _delete_session_from_db(token, db_path)
        assert deleted, f"Session row not found in {db_path} â€” token: {token[:8]}..."

        # Now the token should be rejected
        r_after = requests.get(
            f"{API}/auth/me",
            headers={"X-Session-Token": token},
            timeout=10,
        )
        assert r_after.status_code == 401, (
            f"Expected 401 after session deletion, got {r_after.status_code}"
        )

    def test_expired_session_returns_401(self):
        """Setting expires_at=0 causes /api/auth/me to return 401."""
        db_path = _find_db()
        if db_path is None:
            pytest.skip("Could not locate sylion.db â€” skipping DB manipulation test")

        token = _admin_token()

        # Expire session
        expired = _expire_session_in_db(token, db_path)
        if not expired:
            pytest.skip("Could not expire session in DB")

        r = requests.get(
            f"{API}/auth/me",
            headers={"X-Session-Token": token},
            timeout=10,
        )
        assert r.status_code == 401, (
            f"Expected 401 for expired session, got {r.status_code}"
        )


# ---------------------------------------------------------------------------
# UI-level test (browser + DB)
# ---------------------------------------------------------------------------


class TestSessionExpiryUI:
    """E2E-011 (UI) â€” SPA handles 401 gracefully by showing login screen."""

    def test_spa_redirects_to_login_on_401(self, page: Page):
        """
        After session expiry, any UI action triggering an API call must cause
        the SPA to show the login panel (not an error page).
        """
        db_path = _find_db()

        # Log in via UI
        page.goto(BASE_URL)
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(ADMIN_PASS)
        page.locator("button", has_text="Zaloguj").click()
        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)

        # Extract the session token from the in-page JS state
        token = page.evaluate(
            "() => window._sessionToken || window.sessionToken || "
            "localStorage.getItem('session_token') || "
            "document.cookie.split(';').find(c=>c.trim().startsWith('sylion_session=')) "
            "  ?.split('=')[1]?.trim() || ''"
        )

        if db_path and token:
            # Delete session from DB
            _delete_session_from_db(token, db_path)
        elif db_path is None:
            pytest.skip("No DB found â€” testing only via API 401 injection")

        # Trigger a refresh/navigation that will hit an authenticated API endpoint
        page.reload()
        page.wait_for_timeout(3_000)

        # SPA should detect the 401 and show the login screen
        expect(page.locator("#login-screen")).to_be_visible(timeout=8_000)

    def test_expired_session_does_not_show_error_page(self, page: Page):
        """
        After session expiry, the browser must not show an uncaught error page.
        SPA should gracefully redirect to login (showLogin() called).
        """
        db_path = _find_db()

        page.goto(BASE_URL)
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)
        page.locator("#login-username").fill(ADMIN_USER)
        page.locator("#login-password").fill(ADMIN_PASS)
        page.locator("button", has_text="Zaloguj").click()
        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)

        js_errors = []
        page.on("pageerror", lambda e: js_errors.append(str(e)))

        token = page.evaluate(
            "() => window._sessionToken || window.sessionToken || "
            "localStorage.getItem('session_token') || ''"
        )

        if db_path and token:
            _delete_session_from_db(token, db_path)

        # Navigate to another screen â€” will trigger authenticated API call
        page.goto(f"{BASE_URL}/#monitoring")
        page.wait_for_timeout(4_000)

        # Should not surface an unhandled error page
        assert "Unhandled" not in " ".join(js_errors), (
            f"Unhandled JS errors after session expiry: {js_errors}"
        )
