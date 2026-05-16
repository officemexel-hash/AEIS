"""Tests for sylion.security.profiles — SecurityProfile, get_profile, list_profiles."""

import pytest

from sylion.security.profiles import (
    SecurityProfile,
    PROFILES,
    get_profile,
    list_profiles,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSecurityProfileDataclass:
    def test_default_values(self):
        p = SecurityProfile(name="test")
        assert p.auth_mode == "bootstrap"
        assert p.audit_level == "basic"
        assert p.exec_guard == "off"
        assert p.secret_rotation_days == 90
        assert p.rate_limit == 1000
        assert p.allowed_origins == ["*"]
        assert p.encryption_at_rest is False
        assert p.signing_enabled is False
        assert p.policy_enforcement == "advisory"
        assert p.session_timeout == 3600
        assert p.max_concurrent_sessions == 10

    def test_custom_values(self):
        p = SecurityProfile(
            name="custom",
            auth_mode="mTLS",
            audit_level="full",
            exec_guard="enforce",
            secret_rotation_days=30,
            rate_limit=500,
            allowed_origins=["https://example.com"],
            encryption_at_rest=True,
            signing_enabled=True,
            policy_enforcement="strict",
            session_timeout=1800,
            max_concurrent_sessions=3,
        )
        assert p.auth_mode == "mTLS"
        assert p.audit_level == "full"
        assert p.exec_guard == "enforce"
        assert p.secret_rotation_days == 30
        assert p.rate_limit == 500
        assert p.allowed_origins == ["https://example.com"]
        assert p.encryption_at_rest is True
        assert p.signing_enabled is True
        assert p.policy_enforcement == "strict"
        assert p.session_timeout == 1800
        assert p.max_concurrent_sessions == 3


class TestProfilesDict:
    def test_all_profiles_exist(self):
        expected = {"dev-light", "test-light", "staging-strict", "prod-strict"}
        assert set(PROFILES.keys()) == expected

    def test_profiles_are_security_profile_instances(self):
        for name, p in PROFILES.items():
            assert isinstance(p, SecurityProfile)
            assert p.name == name

    def test_dev_light_profile(self):
        p = PROFILES["dev-light"]
        assert p.auth_mode == "bootstrap"
        assert p.audit_level == "basic"
        assert p.exec_guard == "off"
        assert p.rate_limit == 10000
        assert p.session_timeout == 86400

    def test_test_light_profile(self):
        p = PROFILES["test-light"]
        assert p.auth_mode == "token"
        assert p.audit_level == "basic"
        assert p.exec_guard == "warn"
        assert p.rate_limit == 5000
        assert p.session_timeout == 7200

    def test_staging_strict_profile(self):
        p = PROFILES["staging-strict"]
        assert p.auth_mode == "token"
        assert p.audit_level == "full"
        assert p.exec_guard == "enforce"
        assert p.encryption_at_rest is True
        assert p.signing_enabled is True
        assert p.policy_enforcement == "strict"

    def test_prod_strict_profile(self):
        p = PROFILES["prod-strict"]
        assert p.auth_mode == "mTLS"
        assert p.audit_level == "full"
        assert p.exec_guard == "enforce"
        assert p.secret_rotation_days == 30
        assert p.rate_limit == 500
        assert p.allowed_origins == ["https://sylion.aeis"]
        assert p.encryption_at_rest is True
        assert p.signing_enabled is True
        assert p.policy_enforcement == "strict"
        assert p.session_timeout == 1800
        assert p.max_concurrent_sessions == 3


class TestGetProfile:
    def test_get_known_profile(self):
        p = get_profile("dev-light")
        assert p.name == "dev-light"
        assert isinstance(p, SecurityProfile)

    def test_get_prod_profile(self):
        p = get_profile("prod-strict")
        assert p.auth_mode == "mTLS"

    def test_get_unknown_returns_default(self):
        p = get_profile("nonexistent")
        assert p.name == "dev-light"  # fallback

    def test_get_empty_string_returns_default(self):
        p = get_profile("")
        assert p.name == "dev-light"


class TestListProfiles:
    def test_list_profiles_returns_dict(self):
        result = list_profiles()
        assert isinstance(result, dict)
        assert len(result) == 4

    def test_list_profiles_keys(self):
        result = list_profiles()
        assert "dev-light" in result
        assert "test-light" in result
        assert "staging-strict" in result
        assert "prod-strict" in result

    def test_list_profiles_structure(self):
        result = list_profiles()
        for name, info in result.items():
            assert "name" in info
            assert "auth_mode" in info
            assert "audit_level" in info
            assert "exec_guard" in info
            assert info["name"] == name

    def test_list_profiles_auth_modes(self):
        result = list_profiles()
        assert result["dev-light"]["auth_mode"] == "bootstrap"
        assert result["test-light"]["auth_mode"] == "token"
        assert result["staging-strict"]["auth_mode"] == "token"
        assert result["prod-strict"]["auth_mode"] == "mTLS"


class TestProfileSecurityGraduation:
    """Verify security levels increase from dev to prod."""

    def test_auth_mode_escalation(self):
        modes = [PROFILES[n].auth_mode for n in
                 ["dev-light", "test-light", "staging-strict", "prod-strict"]]
        assert "mTLS" in modes[-1]

    def test_rate_limit_decrease(self):
        limits = [PROFILES[n].rate_limit for n in
                  ["dev-light", "test-light", "staging-strict", "prod-strict"]]
        # prod-strict should have the lowest rate limit
        assert limits[-1] == min(limits)

    def test_session_timeout_decrease(self):
        timeouts = [PROFILES[n].session_timeout for n in
                    ["dev-light", "test-light", "staging-strict", "prod-strict"]]
        assert timeouts[-1] == min(timeouts)

    def test_prod_has_encryption(self):
        assert PROFILES["prod-strict"].encryption_at_rest is True
        assert PROFILES["dev-light"].encryption_at_rest is False
