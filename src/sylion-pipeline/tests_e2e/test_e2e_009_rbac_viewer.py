"""
test_e2e_009_rbac_viewer.py — Viewer/operator role: attempt POST endpoint → 403.

Scenario E2E-009 (GAP-010 coverage):
  An operator (non-owner) must:
  - NOT see the Users screen admin controls (add-user button).
  - Get HTTP 403 when attempting POST/PUT to owner-only endpoints.
  - Not be able to navigate to owner-only UI sections (or see them empty/locked).

  Tests cover:
  1. API-level: operator token → POST /api/users → 401/403.
  2. UI-level: operator cannot see "+ Nowy użytkownik" button.
  3. Navigating to #users as operator shows no user data or access denied.

Pre-condition: Admin account exists.
"""

import requests
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8421"
API = f"{BASE_URL}/api"

ADMIN_USER = "admin"
ADMIN_PASS = "TestPass123!"
VIEWER_USER = "viewer_rbac_test"
VIEWER_PASS = "ViewerPass!1"


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


def _create_viewer(admin_token: str) -> tuple:
    """Create a viewer/auditor user and return (user_id, token)."""
    r = requests.post(
        f"{API}/users",
        json={
            "username": VIEWER_USER,
            "display_name": "Viewer RBAC Test",
            "password": VIEWER_PASS,
            "role": "auditor",  # auditor = read-only role
        },
        headers={"X-Session-Token": admin_token},
        timeout=10,
    )
    assert r.status_code == 200, f"Viewer create failed: {r.text}"
    user_id = r.json()["id"]

    # Log in as viewer
    r2 = requests.post(
        f"{API}/auth/login",
        json={"username": VIEWER_USER, "password": VIEWER_PASS},
        timeout=10,
    )
    assert r2.status_code == 200, f"Viewer login failed: {r2.text}"
    viewer_token = r2.json()["token"]
    return user_id, viewer_token


def _delete_user(user_id: str, admin_token: str):
    requests.delete(
        f"{API}/users/{user_id}",
        headers={"X-Session-Token": admin_token},
        timeout=10,
    )


# ---------------------------------------------------------------------------
# API-level RBAC tests
# ---------------------------------------------------------------------------


class TestRBACAPI:
    """E2E-009 (API) — Operator/viewer cannot call owner-only endpoints."""

    def test_viewer_post_users_returns_403(self):
        """POST /api/users with viewer token must return 401 or 403."""
        admin_token = _admin_token()
        viewer_id, viewer_token = _create_viewer(admin_token)
        try:
            r = requests.post(
                f"{API}/users",
                json={
                    "username": "should_not_be_created",
                    "password": "Pass123!",
                    "role": "auditor",
                },
                headers={"X-Session-Token": viewer_token},
                timeout=10,
            )
            assert r.status_code in (401, 403), (
                f"Expected 401/403 for viewer POST /api/users, got {r.status_code}: {r.text}"
            )
        finally:
            _delete_user(viewer_id, admin_token)

    def test_viewer_delete_user_returns_403(self):
        """DELETE /api/users/{id} with viewer token must return 401 or 403."""
        admin_token = _admin_token()
        viewer_id, viewer_token = _create_viewer(admin_token)
        try:
            # Attempt to delete themselves (or the admin)
            r = requests.delete(
                f"{API}/users/{viewer_id}",
                headers={"X-Session-Token": viewer_token},
                timeout=10,
            )
            assert r.status_code in (401, 403), (
                f"Viewer could DELETE own user account: {r.status_code}"
            )
        finally:
            _delete_user(viewer_id, admin_token)

    def test_viewer_put_api_key_returns_403(self):
        """PUT /api/keys/openai with viewer token must return 401 or 403."""
        admin_token = _admin_token()
        viewer_id, viewer_token = _create_viewer(admin_token)
        try:
            r = requests.put(
                f"{API}/keys/openai",
                json={"value": "sk-" + "b" * 48},
                headers={"X-Session-Token": viewer_token},
                timeout=10,
            )
            assert r.status_code in (401, 403), (
                f"Viewer could PUT /api/keys/openai: {r.status_code}"
            )
        finally:
            _delete_user(viewer_id, admin_token)

    def test_viewer_get_users_returns_403(self):
        """GET /api/users with viewer/auditor token should be restricted."""
        admin_token = _admin_token()
        viewer_id, viewer_token = _create_viewer(admin_token)
        try:
            r = requests.get(
                f"{API}/users",
                headers={"X-Session-Token": viewer_token},
                timeout=10,
            )
            # owner-only endpoint should return 401/403
            assert r.status_code in (401, 403), (
                f"GET /api/users returned {r.status_code} for viewer — expected 401/403"
            )
        finally:
            _delete_user(viewer_id, admin_token)


# ---------------------------------------------------------------------------
# UI-level RBAC tests
# ---------------------------------------------------------------------------


class TestRBACUI:
    """E2E-009 (UI) — Viewer cannot see owner-only controls."""

    @pytest.fixture(autouse=True)
    def setup_viewer_and_login(self, page: Page):
        """Create viewer account and log in as viewer in the browser."""
        self._admin_token = _admin_token()
        self._viewer_id, self._viewer_token = _create_viewer(self._admin_token)

        page.goto(BASE_URL)
        expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)
        page.locator("#login-username").fill(VIEWER_USER)
        page.locator("#login-password").fill(VIEWER_PASS)
        page.locator("button", has_text="Zaloguj").click()
        expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)
        yield
        _delete_user(self._viewer_id, self._admin_token)

    def test_viewer_cannot_see_add_user_button(self, page: Page):
        """The '+ Nowy użytkownik' button must be absent for viewer role (GAP-010)."""
        # Try to navigate to users screen
        users_nav = page.locator(
            "[data-screen='users'], a[href='#users'], a[href*='users'], "
            ".nav-item:has-text('Użytkownicy')"
        ).first
        if users_nav.count() > 0:
            users_nav.click()
            page.wait_for_timeout(2_000)

        # The add-user button must not be visible
        add_user_btn = page.locator(
            "button:has-text('Nowy'), button:has-text('Dodaj'), "
            "button:has-text('+ Nowy'), button[onclick*='addUser']"
        )
        assert add_user_btn.count() == 0 or add_user_btn.is_hidden(), (
            "Viewer can see the add-user button — RBAC UI gating missing (GAP-010)"
        )

    def test_viewer_users_screen_empty_or_inaccessible(self, page: Page):
        """Viewer navigating to #users must see empty/denied screen, not user list."""
        page.goto(f"{BASE_URL}/#users")
        page.wait_for_timeout(2_000)

        # Should not show other users' data (admin, etc.)
        # Either the screen is hidden or shows an "access denied" or empty state
        users_screen = page.locator("#screen-users")
        if users_screen.is_visible():
            # If visible, no user rows should be populated
            user_rows = page.locator(
                "#screen-users tr[data-user-id], "
                "#screen-users .user-row"
            )
            assert user_rows.count() == 0, (
                f"Viewer can see {user_rows.count()} user rows — RBAC leak"
            )
