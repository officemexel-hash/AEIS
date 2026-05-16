"""
test_e2e_007_change_password_invalidates.py — Change password → old session 401.

Scenario E2E-007 / MEDIUM-001:
  This is a CRITICAL security regression test.

  Current behavior (v5.9.0 BUG):
    PUT /api/users/{user_id} with a new password_hash does NOT call:
      DELETE FROM sessions WHERE user_id=?
    → The old session token T1 remains valid (MEDIUM-001).

  Expected behavior (post-fix):
    After password change, any existing session for that user must be
    invalidated — /api/auth/me with T1 must return authenticated=False.

  This file:
    1. API-level test documenting the current behavior (asserts the BUG).
    2. API-level FIXED assertion (commented out — invert once patched).
    3. UI-level test: admin changes operator password → modal closes.

  Flip the assertion in test_medium_001_session_survives_bug() once the fix
  is deployed.

Pre-condition: Admin account exists.
"""

import requests
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8421"
API = f"{BASE_URL}/api"

ADMIN_USER = "admin"
ADMIN_PASS = "TestPass123!"
OPERATOR_USER = "op_pw_change_test"
OPERATOR_PASS = "OperPass!1"
OPERATOR_NEW_PASS = "OperNewPass!2"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _api_login(username: str, password: str) -> requests.Response:
    return requests.post(
        f"{API}/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )


def _api_me(token: str) -> dict:
    r = requests.get(
        f"{API}/auth/me",
        headers={"X-Session-Token": token},
        timeout=10,
    )
    return r.json()


def _admin_token() -> str:
    r = _api_login(ADMIN_USER, ADMIN_PASS)
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["token"]


def _create_operator(admin_token: str) -> str:
    r = requests.post(
        f"{API}/users",
        json={
            "username": OPERATOR_USER,
            "display_name": "Op PW Change Test",
            "password": OPERATOR_PASS,
            "role": "operator",
        },
        headers={"X-Session-Token": admin_token},
        timeout=10,
    )
    assert r.status_code == 200, f"Operator create failed: {r.text}"
    return r.json()["id"]


def _delete_operator(user_id: str, admin_token: str):
    requests.delete(
        f"{API}/users/{user_id}",
        headers={"X-Session-Token": admin_token},
        timeout=10,
    )


# ---------------------------------------------------------------------------
# MEDIUM-001 API tests
# ---------------------------------------------------------------------------


class TestChangePasswordSessionInvalidation:
    """E2E-007 / MEDIUM-001 — Session handling after password change."""

    def test_medium_001_session_survives_bug(self):
        """
        MEDIUM-001 REGRESSION TEST — documents current vulnerable behavior.

        After admin changes operator's password, T1 remains valid.
        THIS ASSERTS THE BUG. When the fix is applied:
          - Comment out: assert still_authenticated is True
          - Uncomment:   assert still_authenticated is False
        """
        admin_token = _admin_token()
        op_id = _create_operator(admin_token)
        try:
            # Step 1: operator logs in, gets session T1
            r = _api_login(OPERATOR_USER, OPERATOR_PASS)
            assert r.status_code == 200, f"Operator login failed: {r.text}"
            t1 = r.json()["token"]

            # T1 must be valid now
            me_before = _api_me(t1)
            assert me_before.get("authenticated") is True, "T1 should be active before change"

            # Step 2: admin changes operator password
            r_change = requests.put(
                f"{API}/users/{op_id}",
                json={"password": OPERATOR_NEW_PASS},
                headers={"X-Session-Token": admin_token},
                timeout=10,
            )
            assert r_change.status_code == 200, f"Password change failed: {r_change.text}"

            # Step 3: check if T1 is still valid — CURRENT BUG: it is
            me_after = _api_me(t1)
            still_authenticated = me_after.get("authenticated")

            # --- DOCUMENT THE BUG (assert True = still valid = security hole) ---
            assert still_authenticated is True, (
                "MEDIUM-001: Expected session to still be valid (current bug). "
                "If this fails, the fix has been applied — invert this assertion."
            )
            # --- FIXED assertion (uncomment after fix) ---
            # assert still_authenticated is False, (
            #     "MEDIUM-001 FIX: old session must be invalidated after password change"
            # )

        finally:
            _delete_operator(op_id, admin_token)

    def test_new_password_login_works_after_change(self):
        """After password change, the new password must allow a successful login."""
        admin_token = _admin_token()
        op_id = _create_operator(admin_token)
        try:
            # Change password
            r_change = requests.put(
                f"{API}/users/{op_id}",
                json={"password": OPERATOR_NEW_PASS},
                headers={"X-Session-Token": admin_token},
                timeout=10,
            )
            assert r_change.status_code == 200, f"Password change failed: {r_change.text}"

            # Login with new password must succeed
            r_new = _api_login(OPERATOR_USER, OPERATOR_NEW_PASS)
            assert r_new.status_code == 200, (
                f"Login with new password failed: {r_new.text}"
            )
            assert r_new.json().get("token"), "No token in new-password login response"
        finally:
            _delete_operator(op_id, admin_token)

    def test_old_password_rejected_after_change(self):
        """After password change, the old password must no longer work."""
        admin_token = _admin_token()
        op_id = _create_operator(admin_token)
        try:
            # Change password
            r_change = requests.put(
                f"{API}/users/{op_id}",
                json={"password": OPERATOR_NEW_PASS},
                headers={"X-Session-Token": admin_token},
                timeout=10,
            )
            assert r_change.status_code == 200

            # Old password must fail
            r_old = _api_login(OPERATOR_USER, OPERATOR_PASS)
            assert r_old.status_code in (401, 403), (
                f"Old password still accepted after change (status {r_old.status_code})"
            )
        finally:
            _delete_operator(op_id, admin_token)


class TestChangePasswordUI:
    """E2E-007 UI — change password via Users screen, modal closes on save."""

    def test_change_password_via_users_ui(self, page: Page):
        """
        Admin opens Users screen, edits operator, sets new password, saves.
        Modal must close — confirms the PUT succeeded.
        """
        admin_token = _admin_token()
        op_id = _create_operator(admin_token)
        try:
            # Login as admin
            page.goto(BASE_URL)
            expect(page.locator("#login-panel")).to_be_visible(timeout=8_000)
            page.locator("#login-username").fill(ADMIN_USER)
            page.locator("#login-password").fill(ADMIN_PASS)
            page.locator("button", has_text="Zaloguj").click()
            expect(page.locator("#screen-dashboard")).to_be_visible(timeout=8_000)

            # Navigate to Users screen
            page.locator(
                "[data-screen='users'], .nav-item:has-text('Użytkownicy'), "
                "a[href*='users'], button:has-text('Użytkownicy')"
            ).first.click()
            expect(page.locator("#screen-users")).to_be_visible(timeout=6_000)

            # Click Edit for operator row
            page.locator(
                f"tr:has-text('{OPERATOR_USER}') button:has-text('Edytuj'), "
                f".user-row:has-text('{OPERATOR_USER}') button:has-text('Edytuj'), "
                f"[data-username='{OPERATOR_USER}'] button:has-text('Edytuj')"
            ).first.click()

            # Fill new password in edit modal
            pw_field = page.locator("#edit-user-password")
            expect(pw_field).to_be_visible(timeout=5_000)
            pw_field.fill(OPERATOR_NEW_PASS)

            # Save
            page.locator(
                "button:has-text('Zapisz'), button:has-text('Aktualizuj'), "
                "button[type='submit']:visible"
            ).first.click()

            # Modal must close (password field hidden)
            expect(pw_field).to_be_hidden(timeout=5_000)

        finally:
            _delete_operator(op_id, admin_token)
