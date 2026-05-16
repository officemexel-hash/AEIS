"""Tests for sylion.security.profile_manager module."""
import pytest
from sylion.security.profile_manager import SecurityProfileManager


class TestSecurityProfileManager:
    @pytest.fixture
    def mgr(self):
        return SecurityProfileManager()

    def test_define_profile(self, mgr):
        result = mgr.define_profile("dev-default", "dev-light", {"allow_debug": True})
        assert result["name"] == "dev-default"
        assert result["level"] == "dev-light"

    def test_define_profile_invalid_level(self, mgr):
        result = mgr.define_profile("bad", "invalid-level")
        assert "error" in result

    def test_get_profile(self, mgr):
        mgr.define_profile("prod-strict-v1", "prod-strict")
        found = mgr.get_profile("prod-strict-v1")
        assert found is not None
        assert found["name"] == "prod-strict-v1"

    def test_get_profile_not_found(self, mgr):
        assert mgr.get_profile("nonexistent") is None

    def test_list_profiles(self, mgr):
        mgr.define_profile("list-a", "dev-light")
        mgr.define_profile("list-b", "prod-strict")
        profiles = mgr.list_profiles()
        assert len(profiles) >= 2

    def test_list_profiles_filter_level(self, mgr):
        mgr.define_profile("filter-dev", "dev-light")
        mgr.define_profile("filter-prod", "prod-strict")
        profiles = mgr.list_profiles(level="dev-light")
        assert all(p["level"] == "dev-light" for p in profiles)

    def test_assign_profile(self, mgr):
        mgr.define_profile("assign-target", "staging-strict")
        result = mgr.assign_profile("mod-1", "assign-target")
        assert result["profile_name"] == "assign-target"

    def test_assign_profile_not_found(self, mgr):
        result = mgr.assign_profile("mod-x", "nonexistent")
        assert "error" in result

    def test_get_module_profile(self, mgr):
        mgr.define_profile("get-mod-pro", "prod-strict")
        mgr.assign_profile("mod-2", "get-mod-pro")
        result = mgr.get_module_profile("mod-2")
        assert result is not None
        assert result["name"] == "get-mod-pro"

    def test_get_module_profile_not_assigned(self, mgr):
        assert mgr.get_module_profile("unassigned") is None

    def test_hot_swap_profile(self, mgr):
        mgr.define_profile("swap-from", "dev-light")
        mgr.define_profile("swap-to", "prod-strict")
        mgr.assign_profile("mod-3", "swap-from")
        result = mgr.hot_swap_profile("mod-3", "swap-to")
        assert result["new_profile"] == "swap-to"

    def test_hot_swap_profile_not_found(self, mgr):
        result = mgr.hot_swap_profile("mod-4", "nonexistent")
        assert "error" in result

    def test_validate_profile_compliance(self, mgr):
        mgr.define_profile("comp-check", "staging-strict")
        mgr.assign_profile("mod-5", "comp-check")
        result = mgr.validate_profile_compliance("mod-5")
        assert result["compliant"] is True

    def test_validate_no_profile(self, mgr):
        result = mgr.validate_profile_compliance("unassigned")
        assert result["compliant"] is False

    def test_get_audit_trail(self, mgr):
        mgr.define_profile("audit-p", "dev-light")
        mgr.assign_profile("mod-6", "audit-p")
        trail = mgr.get_audit_trail()
        assert len(trail) >= 1

    def test_get_audit_trail_filter_module(self, mgr):
        mgr.define_profile("filter-audit", "dev-light")
        mgr.assign_profile("mod-7", "filter-audit")
        trail = mgr.get_audit_trail(module_id="mod-7")
        assert all(t["module_id"] == "mod-7" for t in trail)

    def test_get_stats(self, mgr):
        mgr.define_profile("stat-p", "dev-light")
        mgr.assign_profile("mod-8", "stat-p")
        stats = mgr.get_stats()
        assert stats["total_profiles"] >= 1
        assert stats["total_assignments"] >= 1
