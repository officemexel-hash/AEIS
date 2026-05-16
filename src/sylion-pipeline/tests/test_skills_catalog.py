"""Comprehensive tests for sylion.skills.catalog (SkillsCatalog class)."""

import json
import threading
import time

import pytest

from sylion.skills.catalog import (
    VALID_CATEGORIES,
    SkillsCatalog,
    get_skills_catalog,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def catalog():
    """Fresh in-memory SkillsCatalog per test."""
    return SkillsCatalog()


@pytest.fixture
def populated_catalog(catalog):
    """Catalog with several entries across categories and domains."""
    e1 = catalog.add(
        "s1", "Kernel Analyzer", category="kernel", domain="core",
        description="Analyzes kernel modules", tags=["security", "audit"],
        author="alice", compatibility=">=3.0",
    )
    e2 = catalog.add(
        "s2", "Contract Tester", category="contract", domain="testing",
        description="Tests contracts", tags=["test", "validation"],
        author="bob",
    )
    e3 = catalog.add(
        "s3", "Scaffold Gen", category="scaffold", domain="core",
        description="Generates scaffolding", tags=["codegen"],
        author="alice",
    )
    e4 = catalog.add(
        "s4", "Governance Gate", category="governance", domain="governance",
        description="Enforces governance rules", tags=["audit"],
        author="carol",
    )
    # Set ratings and usage via update()
    catalog.update(e1["entry_id"], rating=4.9)
    catalog.update(e2["entry_id"], rating=3.5)
    catalog.update(e3["entry_id"], rating=4.0)
    catalog.update(e4["entry_id"], rating=2.5)
    # Track usage
    for _ in range(15):
        catalog.track_usage(e1["entry_id"])
    for _ in range(7):
        catalog.track_usage(e2["entry_id"])
    for _ in range(3):
        catalog.track_usage(e3["entry_id"])
    return catalog, (e1, e2, e3, e4)


# ---------------------------------------------------------------------------
# Add / Update / Remove
# ---------------------------------------------------------------------------

class TestAdd:
    def test_add_basic(self, catalog):
        result = catalog.add("skill-1", "Test Skill", category="kernel", domain="core")
        assert result["skill_id"] == "skill-1"
        assert result["name"] == "Test Skill"
        assert result["category"] == "kernel"
        assert "entry_id" in result

    def test_add_default_category(self, catalog):
        result = catalog.add("s1", "Default Cat")
        assert result["category"] == "custom"

    def test_add_with_all_fields(self, catalog):
        result = catalog.add(
            "s-full", "Full Skill", category="test", domain="testing",
            description="A full description", tags=["a", "b"],
            author="dev", compatibility=">=2.0",
        )
        assert result["skill_id"] == "s-full"
        entry = catalog.get(result["entry_id"])
        assert entry["description"] == "A full description"
        assert set(entry["tags"]) == {"a", "b"}
        assert entry["author"] == "dev"
        assert entry["compatibility"] == ">=2.0"

    def test_add_invalid_category_raises(self, catalog):
        with pytest.raises(ValueError, match="Invalid category"):
            catalog.add("s1", "Bad", category="nonexistent")

    def test_add_all_valid_categories(self, catalog):
        """Every category in VALID_CATEGORIES must be accepted."""
        for i, cat in enumerate(VALID_CATEGORIES):
            result = catalog.add(f"s-{i}", f"Skill {i}", category=cat)
            assert result["category"] == cat

    def test_add_default_rating_and_usage_are_zero(self, catalog):
        result = catalog.add("s1", "Zero Init")
        entry = catalog.get(result["entry_id"])
        assert entry["rating"] == 0.0
        assert entry["usage_count"] == 0

    def test_add_no_direct_rating_override(self, catalog):
        """add() does NOT accept rating -- it stays 0.0 regardless of kwargs."""
        # The method signature does not expose rating; verify it stays 0
        result = catalog.add("s1", "No Rating")
        entry = catalog.get(result["entry_id"])
        assert entry["rating"] == 0.0


class TestUpdate:
    def test_update_name_and_description(self, catalog):
        added = catalog.add("s1", "Original")
        result = catalog.update(added["entry_id"], name="Updated", description="New desc")
        assert result["updated"] is True
        entry = catalog.get(added["entry_id"])
        assert entry["name"] == "Updated"
        assert entry["description"] == "New desc"

    def test_update_rating_via_update_method(self, catalog):
        added = catalog.add("s1", "Rated")
        catalog.update(added["entry_id"], rating=4.7)
        entry = catalog.get(added["entry_id"])
        assert entry["rating"] == 4.7

    def test_update_tags(self, catalog):
        added = catalog.add("s1", "Tagged")
        catalog.update(added["entry_id"], tags=["x", "y"])
        entry = catalog.get(added["entry_id"])
        assert entry["tags"] == ["x", "y"]

    def test_update_category_valid(self, catalog):
        added = catalog.add("s1", "Test", category="kernel")
        catalog.update(added["entry_id"], category="test")
        entry = catalog.get(added["entry_id"])
        assert entry["category"] == "test"

    def test_update_category_invalid_raises(self, catalog):
        added = catalog.add("s1", "Test")
        with pytest.raises(ValueError, match="Invalid category"):
            catalog.update(added["entry_id"], category="invalid")

    def test_update_not_found_raises(self, catalog):
        with pytest.raises(ValueError, match="not found"):
            catalog.update("nonexistent", name="X")

    def test_update_no_allowed_fields_returns_not_updated(self, catalog):
        added = catalog.add("s1", "Test")
        result = catalog.update(added["entry_id"], bogus_field="ignored")
        assert result["updated"] is False

    def test_update_sets_updated_at(self, catalog):
        added = catalog.add("s1", "Time")
        entry_before = catalog.get(added["entry_id"])
        time.sleep(0.01)
        catalog.update(added["entry_id"], name="Time2")
        entry_after = catalog.get(added["entry_id"])
        assert entry_after["updated_at"] >= entry_before["updated_at"]


class TestRemove:
    def test_remove_entry(self, catalog):
        added = catalog.add("s1", "Test")
        result = catalog.remove(added["entry_id"])
        assert result["removed"] is True
        assert catalog.get(added["entry_id"]) is None

    def test_remove_not_found_raises(self, catalog):
        with pytest.raises(ValueError, match="not found"):
            catalog.remove("nonexistent")

    def test_remove_then_readd(self, catalog):
        added = catalog.add("s1", "First")
        catalog.remove(added["entry_id"])
        readded = catalog.add("s1", "Second")
        entry = catalog.get(readded["entry_id"])
        assert entry["name"] == "Second"
        assert entry["entry_id"] != added["entry_id"]


# ---------------------------------------------------------------------------
# Browsing and Search
# ---------------------------------------------------------------------------

class TestBrowse:
    def test_browse_by_category(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.browse(category="kernel")
        assert all(r["category"] == "kernel" for r in results)

    def test_browse_by_domain(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.browse(domain="core")
        assert all(r["domain"] == "core" for r in results)

    def test_browse_by_tag(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.browse(tag="audit")
        assert all("audit" in r["tags"] for r in results)

    def test_browse_combined_filters(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.browse(category="kernel", domain="core")
        assert all(r["category"] == "kernel" and r["domain"] == "core" for r in results)

    def test_browse_no_filters_returns_all(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.browse()
        assert len(results) == 4

    def test_browse_limit(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.browse(limit=2)
        assert len(results) == 2

    def test_browse_orders_by_usage_and_rating(self, populated_catalog):
        catalog, (e1, e2, _, _) = populated_catalog
        results = catalog.browse()
        # e1 has highest rating (4.9) and most usage (15)
        assert results[0]["entry_id"] == e1["entry_id"]

    def test_browse_empty_catalog(self, catalog):
        results = catalog.browse()
        assert results == []


class TestSearch:
    def test_search_by_name(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.search("Analyzer")
        assert len(results) == 1
        assert results[0]["name"] == "Kernel Analyzer"

    def test_search_by_description(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.search("scaffolding")
        assert len(results) == 1
        assert results[0]["skill_id"] == "s3"

    def test_search_by_tag(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.search("validation")
        assert len(results) >= 1

    def test_search_no_match(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.search("zzz_nonexistent_zzz")
        assert results == []

    def test_search_limit(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.search("a", limit=2)
        assert len(results) <= 2

    def test_search_case_insensitive_like(self, populated_catalog):
        catalog, _ = populated_catalog
        results_lower = catalog.search("analyzer")
        results_upper = catalog.search("Analyzer")
        assert len(results_lower) == len(results_upper)


# ---------------------------------------------------------------------------
# Get / GetBySkill
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_existing(self, catalog):
        added = catalog.add("s1", "Test Skill", category="kernel")
        entry = catalog.get(added["entry_id"])
        assert entry is not None
        assert entry["name"] == "Test Skill"
        assert entry["tags"] == []

    def test_get_not_found(self, catalog):
        assert catalog.get("nonexistent") is None

    def test_get_by_skill_existing(self, catalog):
        catalog.add("s1", "Test Skill")
        entry = catalog.get_by_skill("s1")
        assert entry is not None
        assert entry["skill_id"] == "s1"

    def test_get_by_skill_not_found(self, catalog):
        assert catalog.get_by_skill("nonexistent") is None


# ---------------------------------------------------------------------------
# Usage tracking and recommendations
# ---------------------------------------------------------------------------

class TestTrackUsage:
    def test_track_usage_increments(self, catalog):
        added = catalog.add("s1", "Test")
        catalog.track_usage(added["entry_id"])
        catalog.track_usage(added["entry_id"])
        entry = catalog.get(added["entry_id"])
        assert entry["usage_count"] == 2

    def test_track_usage_updates_timestamp(self, catalog):
        added = catalog.add("s1", "Test")
        before = catalog.get(added["entry_id"])["updated_at"]
        time.sleep(0.01)
        catalog.track_usage(added["entry_id"])
        after = catalog.get(added["entry_id"])["updated_at"]
        assert after >= before


class TestRecommend:
    def test_recommend_sorted_by_rating(self, populated_catalog):
        catalog, (e1, e2, e3, _) = populated_catalog
        results = catalog.recommend()
        assert results[0]["rating"] >= results[1]["rating"]

    def test_recommend_filter_by_domain(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.recommend(domain="core")
        assert all(r["domain"] == "core" for r in results)

    def test_recommend_filter_by_category(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.recommend(category="kernel")
        assert all(r["category"] == "kernel" for r in results)

    def test_recommend_limit(self, populated_catalog):
        catalog, _ = populated_catalog
        results = catalog.recommend(limit=2)
        assert len(results) == 2

    def test_recommend_empty_catalog(self, catalog):
        results = catalog.recommend()
        assert results == []


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_stats_empty(self, catalog):
        stats = catalog.get_stats()
        assert stats["total_entries"] == 0
        assert stats["by_category"] == {}
        assert stats["by_domain"] == {}
        assert stats["top_rated"] == []

    def test_stats_populated(self, populated_catalog):
        catalog, _ = populated_catalog
        stats = catalog.get_stats()
        assert stats["total_entries"] == 4
        assert stats["by_category"]["kernel"] == 1
        assert stats["by_category"]["contract"] == 1
        assert stats["by_domain"]["core"] == 2
        assert len(stats["top_rated"]) == 4

    def test_stats_top_rated_order(self, populated_catalog):
        catalog, _ = populated_catalog
        stats = catalog.get_stats()
        if len(stats["top_rated"]) >= 2:
            assert stats["top_rated"][0]["rating"] >= stats["top_rated"][1]["rating"]


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

class TestGetSkillsCatalogFactory:
    def test_factory_returns_instance(self):
        inst = get_skills_catalog()
        assert isinstance(inst, SkillsCatalog)

    def test_factory_idempotent(self):
        a = get_skills_catalog()
        b = get_skills_catalog()
        assert a is b


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_adds(self, catalog):
        errors = []

        def add_skill(idx):
            try:
                catalog.add(f"s-{idx}", f"Skill {idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_skill, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        stats = catalog.get_stats()
        assert stats["total_entries"] == 20

    def test_concurrent_track_usage(self, catalog):
        added = catalog.add("s1", "Contended")
        errors = []

        def track():
            try:
                catalog.track_usage(added["entry_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=track) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        entry = catalog.get(added["entry_id"])
        assert entry["usage_count"] == 50
