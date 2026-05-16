"""Tests for sylion.contracts.event_validator.EventTaxonomyValidator."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from sylion.contracts.event_validator import EventTaxonomyValidator

TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "sylion" / "contracts" / "events.yaml"
assert TAXONOMY_PATH.exists(), f"events.yaml not found at {TAXONOMY_PATH}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def validator() -> EventTaxonomyValidator:
    """Return a validator loaded from the real events.yaml."""
    return EventTaxonomyValidator(TAXONOMY_PATH)


# ---------------------------------------------------------------------------
# test_load_taxonomy
# ---------------------------------------------------------------------------

class TestLoadTaxonomy:
    def test_loads_without_error(self, validator: EventTaxonomyValidator):
        """Validator should load the taxonomy file without raising."""
        assert validator.event_count > 0

    def test_declared_total_matches_actual(self, validator: EventTaxonomyValidator):
        """The total_events declared in YAML should match the loaded count."""
        # events.yaml declares total_events: 172
        assert validator.event_count == 172

    def test_version_present(self, validator: EventTaxonomyValidator):
        assert validator.version == "1.0.0"

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            EventTaxonomyValidator(tmp_path / "nonexistent.yaml")

    def test_bad_yaml_structure_raises(self, tmp_path: Path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("foo: bar\n", encoding="utf-8")
        with pytest.raises(ValueError, match="event_taxonomy"):
            EventTaxonomyValidator(bad)


# ---------------------------------------------------------------------------
# test_validate_known_event
# ---------------------------------------------------------------------------

class TestValidateKnownEvent:
    def test_known_event_is_valid(self, validator: EventTaxonomyValidator):
        result = validator.validate_event("bundle.assembled", "core.bundle_assembler")
        assert result["valid"] is True
        assert result["error"] is None
        assert result["topic"] == "bundle.assembled"

    def test_multi_owner_event(self, validator: EventTaxonomyValidator):
        """security.session.created has two owners."""
        result = validator.validate_event(
            "security.session.created", "security.auth_provider"
        )
        assert result["valid"] is True

        result2 = validator.validate_event(
            "security.session.created", "security.session_broker"
        )
        assert result2["valid"] is True


# ---------------------------------------------------------------------------
# test_validate_unknown_event
# ---------------------------------------------------------------------------

class TestValidateUnknownEvent:
    def test_unknown_event_is_invalid(self, validator: EventTaxonomyValidator):
        result = validator.validate_event("totally.fake.event", "some.module")
        assert result["valid"] is False
        assert "not found" in result["error"]

    def test_empty_topic(self, validator: EventTaxonomyValidator):
        result = validator.validate_event("", "core.bundle_assembler")
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# test_validate_wrong_owner
# ---------------------------------------------------------------------------

class TestValidateWrongOwner:
    def test_wrong_owner_is_invalid(self, validator: EventTaxonomyValidator):
        result = validator.validate_event("bundle.assembled", "wrong.module")
        assert result["valid"] is False
        assert "not an owner" in result["error"]
        assert result["owner"] == "core.bundle_assembler"


# ---------------------------------------------------------------------------
# test_get_events_for_module
# ---------------------------------------------------------------------------

class TestGetEventsForModule:
    def test_returns_events(self, validator: EventTaxonomyValidator):
        events = validator.get_events_for_module("core.module_registry")
        assert "module.registered" in events
        assert "module.deregistered" in events
        assert "module.lifecycle.transition" in events

    def test_unknown_module_returns_empty(self, validator: EventTaxonomyValidator):
        events = validator.get_events_for_module("nonexistent.module")
        assert events == []

    def test_all_owners_covered(self, validator: EventTaxonomyValidator):
        """Sum of per-module events should account for every topic."""
        seen: set[str] = set()
        for mod in validator.owner_modules:
            for t in validator.get_events_for_module(mod):
                seen.add(t)
        # Multi-owner topics appear under multiple modules, so seen >= topics
        assert seen >= validator.topics


# ---------------------------------------------------------------------------
# test_find_orphans
# ---------------------------------------------------------------------------

class TestFindOrphans:
    def test_no_orphans_when_all_registered(self, validator: EventTaxonomyValidator):
        orphans = validator.get_orphan_events(list(validator.owner_modules))
        assert orphans == []

    def test_orphans_when_module_missing(self, validator: EventTaxonomyValidator):
        # Register only one module -- everything else should be orphaned
        orphans = validator.get_orphan_events(["core.bundle_assembler"])
        orphan_topics = {o["topic"] for o in orphans}
        assert "bundle.assembled" not in orphan_topics
        assert len(orphans) > 0

    def test_empty_registry_means_all_orphaned(self, validator: EventTaxonomyValidator):
        orphans = validator.get_orphan_events([])
        assert len(orphans) == validator.event_count


# ---------------------------------------------------------------------------
# test_find_unregistered
# ---------------------------------------------------------------------------

class TestFindUnregistered:
    def test_all_known_returns_empty(self, validator: EventTaxonomyValidator):
        unknowns = validator.get_unregistered_events(list(validator.topics))
        assert unknowns == []

    def test_unknown_topics_found(self, validator: EventTaxonomyValidator):
        unknowns = validator.get_unregistered_events([
            "bundle.assembled",
            "phantom.event.happened",
            "another.fake.one",
        ])
        assert set(unknowns) == {"phantom.event.happened", "another.fake.one"}

    def test_empty_input(self, validator: EventTaxonomyValidator):
        assert validator.get_unregistered_events([]) == []


# ---------------------------------------------------------------------------
# validate_all structural checks
# ---------------------------------------------------------------------------

class TestValidateAll:
    def test_real_taxonomy_has_no_issues(self, validator: EventTaxonomyValidator):
        issues = validator.validate_all()
        assert issues == []

    def test_bad_topic_format_detected(self, tmp_path: Path):
        bad_yaml = tmp_path / "events.yaml"
        data = {
            "event_taxonomy": {
                "version": "0.0.1",
                "total_events": 1,
                "events": [
                    {
                        "topic": "INVALID TOPIC FORMAT",
                        "owner": "some.module",
                        "description": "bad topic",
                        "payload_keys": [],
                        "idempotency": True,
                    }
                ],
            }
        }
        bad_yaml.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
        v = EventTaxonomyValidator(bad_yaml)
        issues = v.validate_all()
        assert any(i["check"] == "topic_format" for i in issues)

    def test_total_mismatch_detected(self, tmp_path: Path):
        bad_yaml = tmp_path / "events.yaml"
        data = {
            "event_taxonomy": {
                "version": "0.0.1",
                "total_events": 999,
                "events": [
                    {
                        "topic": "a.b.c",
                        "owner": "mod",
                        "description": "ok",
                        "payload_keys": [],
                    }
                ],
            }
        }
        bad_yaml.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
        v = EventTaxonomyValidator(bad_yaml)
        issues = v.validate_all()
        assert any(i["check"] == "total_events" for i in issues)
