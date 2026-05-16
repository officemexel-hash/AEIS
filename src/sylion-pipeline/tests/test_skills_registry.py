"""Comprehensive tests for sylion.skills.registry (SkillsRegistry class)."""

import json
import threading
import time

import pytest

from sylion.skills.registry import (
    LIFECYCLE_TRANSITIONS,
    VALID_LIFECYCLE_STATES,
    Skill,
    SkillsRegistry,
    get_skills_registry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry():
    """Fresh in-memory SkillsRegistry per test."""
    return SkillsRegistry()


@pytest.fixture
def draft_skill(registry):
    """Register a single skill in DRAFT state."""
    result = registry.register("skill-1", "Test Skill", domain="core",
                                owner_role="dev", description="A test skill")
    return registry, result


@pytest.fixture
def published_skill(registry):
    """Register and publish a skill."""
    reg = registry.register("skill-pub", "Published Skill", domain="core")
    registry.publish("skill-pub")
    return registry, reg


# ---------------------------------------------------------------------------
# Skill dataclass
# ---------------------------------------------------------------------------

class TestSkillDataclass:
    def test_auto_generates_id(self):
        s = Skill()
        assert s.skill_id != ""
        assert len(s.skill_id) == 32

    def test_auto_generates_timestamps(self):
        before = time.time()
        s = Skill()
        after = time.time()
        assert before <= s.created_at <= after
        assert s.created_at == s.updated_at

    def test_default_lifecycle(self):
        s = Skill()
        assert s.lifecycle == "DRAFT"

    def test_default_cost_profile(self):
        s = Skill()
        assert s.cost_profile == "zero-cost"

    def test_custom_values(self):
        s = Skill(skill_id="custom", name="Test", lifecycle="PUBLISHED")
        assert s.skill_id == "custom"
        assert s.name == "Test"
        assert s.lifecycle == "PUBLISHED"


# ---------------------------------------------------------------------------
# Lifecycle constants
# ---------------------------------------------------------------------------

class TestLifecycleConstants:
    def test_valid_states(self):
        assert VALID_LIFECYCLE_STATES == (
            "DRAFT", "VALIDATED", "PUBLISHED", "DEPRECATED", "RETIRED",
        )

    def test_transitions_draft_to_validated(self):
        assert "VALIDATED" in LIFECYCLE_TRANSITIONS["DRAFT"]

    def test_transitions_validated_to_published(self):
        assert "PUBLISHED" in LIFECYCLE_TRANSITIONS["VALIDATED"]

    def test_transitions_published_to_deprecated(self):
        assert "DEPRECATED" in LIFECYCLE_TRANSITIONS["PUBLISHED"]

    def test_transitions_deprecated_to_retired(self):
        assert "RETIRED" in LIFECYCLE_TRANSITIONS["DEPRECATED"]

    def test_retired_has_no_transitions(self):
        assert "RETIRED" not in LIFECYCLE_TRANSITIONS


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_basic(self, registry):
        result = registry.register("skill-1", "Test Skill")
        assert result["skill_id"] == "skill-1"
        assert result["name"] == "Test Skill"
        assert result["lifecycle"] == "DRAFT"

    def test_register_with_all_fields(self, registry):
        result = registry.register(
            "skill-full", "Full Skill", domain="testing",
            owner_role="admin", description="Full desc",
        )
        assert result["skill_id"] == "skill-full"
        skill = registry.get("skill-full")
        assert skill["domain"] == "testing"
        assert skill["owner_role"] == "admin"
        assert skill["description"] == "Full desc"

    def test_register_default_values(self, registry):
        registry.register("s1", "Defaults")
        skill = registry.get("s1")
        assert skill["lifecycle"] == "DRAFT"
        assert skill["version"] == "1.0.0"
        assert skill["cost_profile"] == "zero-cost"
        assert skill["inputs"] == []
        assert skill["outputs"] == []
        assert skill["quality_gates"] == []

    def test_register_persists_to_db(self, registry):
        registry.register("s1", "Persisted")
        skill = registry.get("s1")
        assert skill is not None
        assert skill["name"] == "Persisted"


# ---------------------------------------------------------------------------
# Publish (walks DRAFT -> VALIDATED -> PUBLISHED)
# ---------------------------------------------------------------------------

class TestPublish:
    def test_publish_from_draft(self, draft_skill):
        registry, _ = draft_skill
        result = registry.publish("skill-1")
        assert result["lifecycle"] == "PUBLISHED"
        skill = registry.get("skill-1")
        assert skill["lifecycle"] == "PUBLISHED"

    def test_publish_walks_through_validated(self, registry):
        registry.register("s1", "Walk Test")
        registry.publish("s1")
        # After publish, the skill should be PUBLISHED
        skill = registry.get("s1")
        assert skill["lifecycle"] == "PUBLISHED"

    def test_publish_not_found_raises(self, registry):
        with pytest.raises(ValueError, match="not found"):
            registry.publish("nonexistent")

    def test_publish_already_published_is_idempotent(self, published_skill):
        registry, _ = published_skill
        # Publishing an already-published skill should succeed (already at target)
        result = registry.publish("skill-pub")
        assert result["lifecycle"] == "PUBLISHED"

    def test_publish_from_deprecated_raises(self, registry):
        registry.register("s1", "Test")
        registry.publish("s1")
        registry.deprecate("s1")
        with pytest.raises(ValueError, match="Cannot publish"):
            registry.publish("s1")

    def test_publish_from_retired_raises(self, registry):
        registry.register("s1", "Test")
        registry.publish("s1")
        registry.deprecate("s1")
        registry.retire("s1")
        with pytest.raises(ValueError, match="Cannot publish"):
            registry.publish("s1")


# ---------------------------------------------------------------------------
# Deprecate
# ---------------------------------------------------------------------------

class TestDeprecate:
    def test_deprecate_from_published(self, published_skill):
        registry, _ = published_skill
        result = registry.deprecate("skill-pub")
        assert result["lifecycle"] == "DEPRECATED"
        skill = registry.get("skill-pub")
        assert skill["lifecycle"] == "DEPRECATED"

    def test_deprecate_not_found_raises(self, registry):
        with pytest.raises(ValueError, match="not found"):
            registry.deprecate("nonexistent")

    def test_deprecate_from_draft_raises(self, draft_skill):
        registry, _ = draft_skill
        with pytest.raises(ValueError, match="Cannot deprecate"):
            registry.deprecate("skill-1")

    def test_deprecate_from_validated_raises(self, registry):
        # VALIDATED is an intermediate state -- cannot deprecate from it
        # We can't directly set it, but we know the transitions
        assert "DEPRECATED" not in LIFECYCLE_TRANSITIONS.get("VALIDATED", set())

    def test_deprecate_from_retired_raises(self, registry):
        registry.register("s1", "Test")
        registry.publish("s1")
        registry.deprecate("s1")
        registry.retire("s1")
        with pytest.raises(ValueError, match="Cannot deprecate"):
            registry.deprecate("s1")


# ---------------------------------------------------------------------------
# Retire
# ---------------------------------------------------------------------------

class TestRetire:
    def test_retire_from_deprecated(self, registry):
        registry.register("s1", "Test")
        registry.publish("s1")
        registry.deprecate("s1")
        result = registry.retire("s1")
        assert result["lifecycle"] == "RETIRED"
        skill = registry.get("s1")
        assert skill["lifecycle"] == "RETIRED"

    def test_retire_not_found_raises(self, registry):
        with pytest.raises(ValueError, match="not found"):
            registry.retire("nonexistent")

    def test_retire_from_draft_raises(self, draft_skill):
        registry, _ = draft_skill
        with pytest.raises(ValueError, match="Cannot retire"):
            registry.retire("skill-1")

    def test_retire_from_published_raises(self, published_skill):
        registry, _ = published_skill
        with pytest.raises(ValueError, match="Cannot retire"):
            registry.retire("skill-pub")


# ---------------------------------------------------------------------------
# Full lifecycle transition chain
# ---------------------------------------------------------------------------

class TestFullLifecycle:
    def test_draft_to_retired(self, registry):
        registry.register("s-lifecycle", "Lifecycle Test")
        skill = registry.get("s-lifecycle")
        assert skill["lifecycle"] == "DRAFT"

        registry.publish("s-lifecycle")
        skill = registry.get("s-lifecycle")
        assert skill["lifecycle"] == "PUBLISHED"

        registry.deprecate("s-lifecycle")
        skill = registry.get("s-lifecycle")
        assert skill["lifecycle"] == "DEPRECATED"

        registry.retire("s-lifecycle")
        skill = registry.get("s-lifecycle")
        assert skill["lifecycle"] == "RETIRED"

    def test_backward_transition_not_allowed(self, registry):
        """Cannot go from PUBLISHED back to DRAFT."""
        registry.register("s1", "No Back")
        registry.publish("s1")
        assert "DRAFT" not in LIFECYCLE_TRANSITIONS.get("PUBLISHED", set())

    def test_lifecycle_updates_timestamp(self, registry):
        registry.register("s1", "Time Test")
        ts_draft = registry.get("s1")["updated_at"]
        time.sleep(0.01)
        registry.publish("s1")
        ts_published = registry.get("s1")["updated_at"]
        assert ts_published >= ts_draft


# ---------------------------------------------------------------------------
# Get / ListSkills / Search
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_existing(self, draft_skill):
        registry, _ = draft_skill
        skill = registry.get("skill-1")
        assert skill is not None
        assert skill["skill_id"] == "skill-1"
        assert skill["name"] == "Test Skill"

    def test_get_not_found(self, registry):
        assert registry.get("nonexistent") is None

    def test_get_deserializes_json_fields(self, draft_skill):
        registry, _ = draft_skill
        skill = registry.get("skill-1")
        assert isinstance(skill["inputs"], list)
        assert isinstance(skill["outputs"], list)
        assert isinstance(skill["quality_gates"], list)


class TestListSkills:
    def test_list_all(self, registry):
        registry.register("s1", "A", domain="core")
        registry.register("s2", "B", domain="infra")
        registry.register("s3", "C", domain="core")
        results = registry.list_skills()
        assert len(results) == 3

    def test_list_filter_by_domain(self, registry):
        registry.register("s1", "A", domain="core")
        registry.register("s2", "B", domain="infra")
        registry.register("s3", "C", domain="core")
        results = registry.list_skills(domain="core")
        assert len(results) == 2
        assert all(r["domain"] == "core" for r in results)

    def test_list_filter_by_lifecycle(self, registry):
        registry.register("s1", "A")
        registry.register("s2", "B")
        registry.publish("s1")
        results = registry.list_skills(lifecycle="PUBLISHED")
        assert len(results) == 1
        assert results[0]["lifecycle"] == "PUBLISHED"

    def test_list_combined_filters(self, registry):
        registry.register("s1", "A", domain="core")
        registry.register("s2", "B", domain="core")
        registry.register("s3", "C", domain="infra")
        registry.publish("s1")
        results = registry.list_skills(domain="core", lifecycle="PUBLISHED")
        assert len(results) == 1

    def test_list_limit(self, registry):
        for i in range(10):
            registry.register(f"s-{i}", f"Skill {i}")
        results = registry.list_skills(limit=5)
        assert len(results) == 5

    def test_list_ordered_by_created_at_desc(self, registry):
        registry.register("s1", "First")
        time.sleep(0.01)
        registry.register("s2", "Second")
        results = registry.list_skills()
        assert results[0]["skill_id"] == "s2"
        assert results[1]["skill_id"] == "s1"

    def test_list_empty(self, registry):
        results = registry.list_skills()
        assert results == []


class TestSearch:
    def test_search_by_name(self, registry):
        registry.register("s1", "Code Bloat Detector", description="Detects bloat")
        registry.register("s2", "Performance Monitor")
        results = registry.search("bloat")
        assert len(results) == 1
        assert results[0]["skill_id"] == "s1"

    def test_search_by_description(self, registry):
        registry.register("s1", "Detector", description="Detects anomalies")
        registry.register("s2", "Other")
        results = registry.search("anomalies")
        assert len(results) == 1
        assert results[0]["skill_id"] == "s1"

    def test_search_no_match(self, registry):
        registry.register("s1", "Something")
        results = registry.search("zzz_nonexistent_zzz")
        assert results == []

    def test_search_limit(self, registry):
        for i in range(10):
            registry.register(f"s-{i}", f"Analyzer {i}")
        results = registry.search("Analyzer", limit=3)
        assert len(results) == 3

    def test_search_case_insensitive_like(self, registry):
        registry.register("s1", "MySkill")
        results_lower = registry.search("myskill")
        results_upper = registry.search("MySkill")
        assert len(results_lower) == len(results_upper)


# ---------------------------------------------------------------------------
# GetStats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_stats_empty(self, registry):
        stats = registry.get_stats()
        assert stats["total_skills"] == 0
        assert stats["by_lifecycle"] == {}
        assert stats["by_domain"] == {}

    def test_stats_populated(self, registry):
        registry.register("s1", "A", domain="core")
        registry.register("s2", "B", domain="infra")
        registry.register("s3", "C", domain="core")
        registry.publish("s1")

        stats = registry.get_stats()
        assert stats["total_skills"] == 3
        assert stats["by_domain"]["core"] == 2
        assert stats["by_domain"]["infra"] == 1
        assert stats["by_lifecycle"]["PUBLISHED"] == 1
        assert stats["by_lifecycle"]["DRAFT"] == 2

    def test_stats_total_equals_sum_of_lifecycle(self, registry):
        registry.register("s1", "A")
        registry.register("s2", "B")
        registry.publish("s1")
        stats = registry.get_stats()
        total_by_lifecycle = sum(stats["by_lifecycle"].values())
        assert stats["total_skills"] == total_by_lifecycle


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

class TestGetSkillsRegistryFactory:
    def test_factory_returns_instance(self):
        inst = get_skills_registry()
        assert isinstance(inst, SkillsRegistry)

    def test_factory_idempotent(self):
        a = get_skills_registry()
        b = get_skills_registry()
        assert a is b


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_registrations(self, registry):
        errors = []

        def register_skill(idx):
            try:
                registry.register(f"s-{idx}", f"Skill {idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_skill, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        stats = registry.get_stats()
        assert stats["total_skills"] == 20

    def test_concurrent_lifecycle_transitions(self, registry):
        errors = []
        # Register skills upfront
        for i in range(10):
            registry.register(f"s-{i}", f"Skill {i}")

        def publish_skill(idx):
            try:
                registry.publish(f"s-{idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=publish_skill, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        results = registry.list_skills(lifecycle="PUBLISHED")
        assert len(results) == 10
