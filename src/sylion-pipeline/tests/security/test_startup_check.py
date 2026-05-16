"""Tests for sylion.security.startup_check (Phase 3 W2.2).

Covers the prod-mode default-secret fail-fast assertion. The public surface
is small — `is_production`, `check_secrets`, `assert_safe_to_serve`, and the
``StartupSecretsViolation`` exception — so these tests stay flat and unit-y.
We pass ``env`` in as a dict per call so tests don't poison os.environ.
"""
from __future__ import annotations

import pytest

from sylion.security.startup_check import (
    StartupSecretsViolation,
    assert_safe_to_serve,
    check_secrets,
    is_production,
)


# ---------------------------------------------------------------------------
# is_production()
# ---------------------------------------------------------------------------


class TestIsProduction:
    def test_unset_returns_false(self, monkeypatch):
        monkeypatch.delenv("SYLION_AEIS_ENV", raising=False)
        assert is_production() is False

    def test_dev_returns_false(self, monkeypatch):
        monkeypatch.setenv("SYLION_AEIS_ENV", "dev")
        assert is_production() is False

    def test_production_returns_true(self, monkeypatch):
        monkeypatch.setenv("SYLION_AEIS_ENV", "production")
        assert is_production() is True

    def test_production_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("SYLION_AEIS_ENV", "PRODUCTION")
        assert is_production() is True

    def test_production_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("SYLION_AEIS_ENV", "  production  ")
        assert is_production() is True

    def test_partial_match_is_false(self, monkeypatch):
        # Defensive: "prod" is a common shorthand we deliberately do NOT accept,
        # so the operator can't accidentally enable prod-mode with a typo.
        monkeypatch.setenv("SYLION_AEIS_ENV", "prod")
        assert is_production() is False


# ---------------------------------------------------------------------------
# check_secrets() — pure function, env passed explicitly
# ---------------------------------------------------------------------------


_GOOD_VAULT = "ab" * 32           # any non-default, non-empty value
_GOOD_MOBILE = "real-mobile-secret-1234"
_BAD_VAULT_DEFAULTS = (
    "sylion-vault-default-secret-key-change-me",
    "sylion-default-secret",
)
_BAD_MOBILE_DEFAULT = "operator-mobile-dev-secret"


class TestCheckSecretsDevMode:
    def test_no_env_var_set_is_dev_mode_pass(self):
        result = check_secrets({})
        assert result.ok is True
        assert result.env == "dev"

    def test_explicit_dev_skips_all_checks(self):
        # Even leaving forbidden defaults in the env is fine outside production.
        result = check_secrets({
            "SYLION_AEIS_ENV": "dev",
            "SYLION_VAULT_SECRET": _BAD_VAULT_DEFAULTS[0],
            "SYLION_MOBILE_SIGNING_SECRET": _BAD_MOBILE_DEFAULT,
        })
        assert result.ok is True
        assert result.failures == []

    def test_test_env_skips_all_checks(self):
        # CI runs typically set SYLION_AEIS_ENV=test or leave it unset.
        result = check_secrets({"SYLION_AEIS_ENV": "test"})
        assert result.ok is True


class TestCheckSecretsProductionMode:
    def test_clean_production_env_passes(self):
        result = check_secrets({
            "SYLION_AEIS_ENV": "production",
            "SYLION_VAULT_SECRET": _GOOD_VAULT,
            "SYLION_MOBILE_SIGNING_SECRET": _GOOD_MOBILE,
        })
        assert result.ok is True
        assert result.env == "production"
        assert result.failures == []

    def test_missing_vault_secret_fails(self):
        result = check_secrets({
            "SYLION_AEIS_ENV": "production",
            "SYLION_MOBILE_SIGNING_SECRET": _GOOD_MOBILE,
        })
        assert result.ok is False
        assert any("SYLION_VAULT_SECRET" in f for f in result.failures)

    def test_missing_mobile_secret_fails(self):
        result = check_secrets({
            "SYLION_AEIS_ENV": "production",
            "SYLION_VAULT_SECRET": _GOOD_VAULT,
        })
        assert result.ok is False
        assert any("SYLION_MOBILE_SIGNING_SECRET" in f for f in result.failures)

    def test_empty_string_is_treated_as_unset(self):
        result = check_secrets({
            "SYLION_AEIS_ENV": "production",
            "SYLION_VAULT_SECRET": "",
            "SYLION_MOBILE_SIGNING_SECRET": "   ",   # whitespace-only also empty
        })
        assert result.ok is False
        assert len(result.failures) == 2

    @pytest.mark.parametrize("bad_value", _BAD_VAULT_DEFAULTS)
    def test_forbidden_vault_default_fails(self, bad_value):
        result = check_secrets({
            "SYLION_AEIS_ENV": "production",
            "SYLION_VAULT_SECRET": bad_value,
            "SYLION_MOBILE_SIGNING_SECRET": _GOOD_MOBILE,
        })
        assert result.ok is False
        assert any("forbidden dev default" in f for f in result.failures)
        assert any("SYLION_VAULT_SECRET" in f for f in result.failures)

    def test_forbidden_mobile_default_fails(self):
        result = check_secrets({
            "SYLION_AEIS_ENV": "production",
            "SYLION_VAULT_SECRET": _GOOD_VAULT,
            "SYLION_MOBILE_SIGNING_SECRET": _BAD_MOBILE_DEFAULT,
        })
        assert result.ok is False
        assert any("SYLION_MOBILE_SIGNING_SECRET" in f for f in result.failures)
        assert any("forbidden dev default" in f for f in result.failures)

    def test_all_bad_yields_all_failures(self):
        result = check_secrets({
            "SYLION_AEIS_ENV": "production",
            "SYLION_VAULT_SECRET": _BAD_VAULT_DEFAULTS[0],
            "SYLION_MOBILE_SIGNING_SECRET": _BAD_MOBILE_DEFAULT,
        })
        assert result.ok is False
        assert len(result.failures) == 2

    def test_production_rejects_rbac_disabled(self):
        # Threat model: SYLION_RBAC_DISABLED=1 carries over from a dev
        # terminal or test env into a prod deploy and silently disables
        # the entire RBAC layer at request time. Boot must fail.
        result = check_secrets({
            "SYLION_AEIS_ENV": "production",
            "SYLION_VAULT_SECRET": _GOOD_VAULT,
            "SYLION_MOBILE_SIGNING_SECRET": _GOOD_MOBILE,
            "SYLION_RBAC_DISABLED": "1",
        })
        assert result.ok is False
        assert any("SYLION_RBAC_DISABLED" in f for f in result.failures)
        assert any("disables a security guard" in f for f in result.failures)

    def test_production_rejects_rbac_disabled_with_whitespace(self):
        # The runtime bypass strips whitespace before comparing, so the
        # guard must too — otherwise " 1 " sneaks past.
        result = check_secrets({
            "SYLION_AEIS_ENV": "production",
            "SYLION_VAULT_SECRET": _GOOD_VAULT,
            "SYLION_MOBILE_SIGNING_SECRET": _GOOD_MOBILE,
            "SYLION_RBAC_DISABLED": " 1 ",
        })
        assert result.ok is False
        assert any("SYLION_RBAC_DISABLED" in f for f in result.failures)

    def test_production_accepts_rbac_disabled_zero(self):
        # "0" is the explicit "RBAC enabled" value — must not trigger.
        result = check_secrets({
            "SYLION_AEIS_ENV": "production",
            "SYLION_VAULT_SECRET": _GOOD_VAULT,
            "SYLION_MOBILE_SIGNING_SECRET": _GOOD_MOBILE,
            "SYLION_RBAC_DISABLED": "0",
        })
        assert result.ok is True

    def test_production_accepts_rbac_disabled_unset(self):
        # The default state — flag unset entirely. RBAC is on. PASS.
        result = check_secrets({
            "SYLION_AEIS_ENV": "production",
            "SYLION_VAULT_SECRET": _GOOD_VAULT,
            "SYLION_MOBILE_SIGNING_SECRET": _GOOD_MOBILE,
        })
        assert result.ok is True

    def test_dev_allows_rbac_disabled(self):
        # The whole point of the flag is dev/test bypass — must not
        # complain outside production mode.
        result = check_secrets({
            "SYLION_AEIS_ENV": "dev",
            "SYLION_RBAC_DISABLED": "1",
        })
        assert result.ok is True


# ---------------------------------------------------------------------------
# assert_safe_to_serve() — the wrapper called from app.py lifespan
# ---------------------------------------------------------------------------


class TestAssertSafeToServe:
    def test_dev_no_op(self, monkeypatch):
        # No env vars set — pure dev mode, must not raise.
        monkeypatch.delenv("SYLION_AEIS_ENV", raising=False)
        assert_safe_to_serve()

    def test_clean_production_passes(self, monkeypatch):
        monkeypatch.setenv("SYLION_AEIS_ENV", "production")
        monkeypatch.setenv("SYLION_VAULT_SECRET", _GOOD_VAULT)
        monkeypatch.setenv("SYLION_MOBILE_SIGNING_SECRET", _GOOD_MOBILE)
        # tests/conftest.py sets SYLION_RBAC_DISABLED=1 globally so legacy
        # anonymous-client tests don't 401. The new prod-rbac guard would
        # then fire here — clear it for this test.
        monkeypatch.delenv("SYLION_RBAC_DISABLED", raising=False)
        assert_safe_to_serve()

    def test_production_with_default_raises(self):
        env = {
            "SYLION_AEIS_ENV": "production",
            "SYLION_VAULT_SECRET": _BAD_VAULT_DEFAULTS[0],
            "SYLION_MOBILE_SIGNING_SECRET": _GOOD_MOBILE,
        }
        with pytest.raises(StartupSecretsViolation) as exc_info:
            assert_safe_to_serve(env)
        # Operator-friendly message: must name the offending var.
        assert "SYLION_VAULT_SECRET" in str(exc_info.value)

    def test_production_missing_var_raises(self):
        env = {"SYLION_AEIS_ENV": "production"}
        with pytest.raises(StartupSecretsViolation) as exc_info:
            assert_safe_to_serve(env)
        msg = str(exc_info.value)
        assert "SYLION_VAULT_SECRET" in msg
        assert "SYLION_MOBILE_SIGNING_SECRET" in msg
