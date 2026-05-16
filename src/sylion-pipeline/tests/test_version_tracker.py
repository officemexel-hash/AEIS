"""Tests for sylion.contracts.version_tracker module."""

import pytest

from sylion.contracts.version_tracker import VersionTracker, parse_semver


class TestParseSemver:
    def test_valid(self):
        assert parse_semver("1.2.3") == (1, 2, 3)

    def test_valid_with_prerelease(self):
        assert parse_semver("1.0.0-alpha") == (1, 0, 0)

    def test_invalid(self):
        assert parse_semver("not-semver") is None

    def test_invalid_partial(self):
        assert parse_semver("1.2") is None

    def test_zero_version(self):
        assert parse_semver("0.0.0") == (0, 0, 0)


class TestVersionTracker:
    @pytest.fixture
    def tracker(self):
        return VersionTracker()

    def test_register_version(self, tracker):
        result = tracker.register_version("mod-a", "1.0.0")
        assert result["module_id"] == "mod-a"
        assert result["version"] == "1.0.0"

    def test_register_multiple_versions(self, tracker):
        tracker.register_version("mod-b", "1.0.0")
        result = tracker.register_version("mod-b", "1.1.0")
        assert result["version"] == "1.1.0"

    def test_register_breaking_version(self, tracker):
        tracker.register_version("mod-c", "1.0.0")
        result = tracker.register_version("mod-c", "2.0.0", breaking=True)
        assert result["breaking"] is True

    def test_get_current_version(self, tracker):
        tracker.register_version("mod-d", "1.5.0")
        result = tracker.get_current_version("mod-d")
        assert result is not None
        assert result["version"] == "1.5.0"

    def test_get_current_not_found(self, tracker):
        assert tracker.get_current_version("nonexistent") is None

    def test_get_version_history(self, tracker):
        tracker.register_version("mod-e", "1.0.0")
        tracker.register_version("mod-e", "1.1.0")
        tracker.register_version("mod-e", "1.2.0")
        history = tracker.get_version_history("mod-e")
        assert len(history) >= 3

    def test_get_version_history_empty(self, tracker):
        assert tracker.get_version_history("nonexistent") == []

    def test_is_compatible(self, tracker):
        tracker.register_version("mod-f", "1.0.0")
        result = tracker.is_compatible("mod-f", "1.0.0", "1.1.0")
        assert result is True

    def test_is_compatible_breaking(self, tracker):
        tracker.register_version("mod-g", "1.0.0")
        result = tracker.is_compatible("mod-g", "1.0.0", "2.0.0")
        assert result is False

    def test_list_breaking_changes(self, tracker):
        tracker.register_version("mod-h", "1.0.0")
        tracker.register_version("mod-h", "2.0.0")
        changes = tracker.list_breaking_changes("mod-h")
        assert isinstance(changes, list)

    def test_get_stats(self, tracker):
        tracker.register_version("s1", "1.0.0")
        tracker.register_version("s2", "2.0.0", breaking=True)
        stats = tracker.get_stats()
        assert stats["total_versions"] >= 2
        assert stats["breaking_change_count"] >= 1
