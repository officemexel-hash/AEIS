"""Tests for SYLION Prompt Template Manager.

Target: 35+ tests covering CRUD, versioning, resolve, search, stats,
import/export, events, edge cases, and singleton management.
"""
import json
import time

import pytest

from sylion.cognitive.prompt_templates import (
    PromptTemplateManager,
    get_prompt_template_manager,
    reset_prompt_template_manager,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the global singleton before and after each test."""
    reset_prompt_template_manager()
    yield
    reset_prompt_template_manager()


@pytest.fixture
def mgr():
    """Fresh in-memory PromptTemplateManager for each test."""
    return PromptTemplateManager(db_path=":memory:")


@pytest.fixture
def bus():
    """Fresh in-memory EventBus for capturing events."""
    return EventBus(db_path=":memory:")


@pytest.fixture
def mgr_bus(bus):
    """PromptTemplateManager wired to the EventBus fixture."""
    return PromptTemplateManager(db_path=":memory:", event_bus=bus)


def _make_template(mgr, **overrides):
    """Helper to create a template with sensible defaults."""
    defaults = dict(
        name="test-template",
        content="Hello {name}, welcome to {place}!",
        description="A test template",
        category="greeting",
        team_id="team-a",
        project_id="proj-1",
        created_by="alice",
    )
    defaults.update(overrides)
    return mgr.create_template(**defaults)


# ===================================================================
# create_template
# ===================================================================

class TestCreateTemplate:

    def test_basic_create(self, mgr):
        tpl = mgr.create_template(
            name="greet",
            content="Hello {name}!",
        )
        assert tpl["template_id"]
        assert tpl["name"] == "greet"
        assert tpl["variables"] == ["name"]
        assert tpl["version"] == 1
        assert tpl["is_active"] == 1

    def test_create_with_all_fields(self, mgr):
        tpl = mgr.create_template(
            name="full",
            content="{a} and {b}",
            description="desc",
            category="cat",
            team_id="t1",
            project_id="p1",
            created_by="bob",
        )
        assert tpl["description"] == "desc"
        assert tpl["category"] == "cat"
        assert tpl["team_id"] == "t1"
        assert tpl["project_id"] == "p1"
        assert tpl["created_by"] == "bob"
        assert tpl["variables"] == ["a", "b"]

    def test_create_no_variables(self, mgr):
        tpl = mgr.create_template(
            name="static",
            content="No placeholders here.",
        )
        assert tpl["variables"] == []

    def test_create_duplicate_variables(self, mgr):
        tpl = mgr.create_template(
            name="dupe",
            content="{x} and {x} and {y}",
        )
        # Should deduplicate
        assert tpl["variables"] == ["x", "y"]

    def test_create_stores_timestamps(self, mgr):
        before = time.time()
        tpl = mgr.create_template(name="ts", content="hi")
        after = time.time()
        assert before <= tpl["created_at"] <= after
        assert tpl["created_at"] == tpl["updated_at"]


# ===================================================================
# get_template
# ===================================================================

class TestGetTemplate:

    def test_get_existing(self, mgr):
        created = _make_template(mgr)
        fetched = mgr.get_template(created["template_id"])
        assert fetched is not None
        assert fetched["name"] == "test-template"
        assert fetched["content"] == "Hello {name}, welcome to {place}!"

    def test_get_nonexistent(self, mgr):
        assert mgr.get_template("does-not-exist") is None

    def test_get_returns_parsed_variables(self, mgr):
        created = _make_template(mgr)
        fetched = mgr.get_template(created["template_id"])
        assert isinstance(fetched["variables"], list)
        assert "name" in fetched["variables"]


# ===================================================================
# update_template
# ===================================================================

class TestUpdateTemplate:

    def test_update_name(self, mgr):
        created = _make_template(mgr)
        result = mgr.update_template(created["template_id"], name="new-name")
        assert result["name"] == "new-name"
        assert result["version"] == 2

    def test_update_content_reextracts_variables(self, mgr):
        created = _make_template(mgr)
        result = mgr.update_template(
            created["template_id"], content="Hello {user}!"
        )
        assert result["variables"] == ["user"]
        assert result["version"] == 2

    def test_update_nonexistent_returns_none(self, mgr):
        assert mgr.update_template("nope", name="x") is None

    def test_update_no_kwargs_returns_current(self, mgr):
        created = _make_template(mgr)
        result = mgr.update_template(created["template_id"])
        assert result["version"] == 1  # no bump, no changes

    def test_update_multiple_fields(self, mgr):
        created = _make_template(mgr)
        result = mgr.update_template(
            created["template_id"],
            name="updated",
            description="new desc",
            category="new-cat",
        )
        assert result["name"] == "updated"
        assert result["description"] == "new desc"
        assert result["category"] == "new-cat"
        assert result["version"] == 2

    def test_update_bumps_version_sequentially(self, mgr):
        created = _make_template(mgr)
        tid = created["template_id"]
        v2 = mgr.update_template(tid, name="v2")
        v3 = mgr.update_template(tid, name="v3")
        assert v2["version"] == 2
        assert v3["version"] == 3

    def test_update_stores_version_history(self, mgr):
        created = _make_template(mgr)
        tid = created["template_id"]
        mgr.update_template(tid, name="v2")
        mgr.update_template(tid, name="v3")
        versions = mgr.get_template_versions(tid)
        assert len(versions) == 2
        assert versions[0]["version"] == 1
        assert versions[0]["name"] == "test-template"
        assert versions[1]["version"] == 2
        assert versions[1]["name"] == "v2"


# ===================================================================
# list_templates
# ===================================================================

class TestListTemplates:

    def test_list_all(self, mgr):
        _make_template(mgr, name="a")
        _make_template(mgr, name="b")
        results = mgr.list_templates()
        assert len(results) == 2

    def test_list_filter_category(self, mgr):
        _make_template(mgr, name="a", category="cat1")
        _make_template(mgr, name="b", category="cat2")
        results = mgr.list_templates(category="cat1")
        assert len(results) == 1
        assert results[0]["name"] == "a"

    def test_list_filter_team_id(self, mgr):
        _make_template(mgr, name="a", team_id="team-a")
        _make_template(mgr, name="b", team_id="team-b")
        results = mgr.list_templates(team_id="team-b")
        assert len(results) == 1
        assert results[0]["name"] == "b"

    def test_list_filter_project_id(self, mgr):
        _make_template(mgr, name="a", project_id="p1")
        _make_template(mgr, name="b", project_id="p2")
        results = mgr.list_templates(project_id="p1")
        assert len(results) == 1

    def test_list_filter_is_active(self, mgr):
        created = _make_template(mgr, name="active")
        mgr.delete_template(created["template_id"])
        results = mgr.list_templates(is_active=1)
        assert len(results) == 0
        results = mgr.list_templates(is_active=0)
        assert len(results) == 1

    def test_list_pagination(self, mgr):
        for i in range(5):
            _make_template(mgr, name=f"tpl-{i}")
        page1 = mgr.list_templates(limit=2, offset=0)
        page2 = mgr.list_templates(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        ids1 = {t["template_id"] for t in page1}
        ids2 = {t["template_id"] for t in page2}
        assert ids1.isdisjoint(ids2)


# ===================================================================
# resolve_template
# ===================================================================

class TestResolveTemplate:

    def test_resolve_basic(self, mgr):
        created = _make_template(mgr)
        result = mgr.resolve_template(
            created["template_id"],
            {"name": "Alice", "place": "Wonderland"},
        )
        assert result == "Hello Alice, welcome to Wonderland!"

    def test_resolve_missing_variable_raises(self, mgr):
        created = _make_template(mgr)
        with pytest.raises(ValueError, match="Missing required variable"):
            mgr.resolve_template(created["template_id"], {"name": "Alice"})

    def test_resolve_nonexistent_raises(self, mgr):
        with pytest.raises(ValueError, match="not found"):
            mgr.resolve_template("nope", {"a": "b"})

    def test_resolve_inactive_raises(self, mgr):
        created = _make_template(mgr)
        mgr.delete_template(created["template_id"])
        with pytest.raises(ValueError, match="inactive"):
            mgr.resolve_template(created["template_id"], {"name": "A", "place": "B"})

    def test_resolve_extra_variables_ok(self, mgr):
        created = _make_template(mgr)
        result = mgr.resolve_template(
            created["template_id"],
            {"name": "Alice", "place": "Wonderland", "extra": "ignored"},
        )
        assert result == "Hello Alice, welcome to Wonderland!"

    def test_resolve_no_variables(self, mgr):
        created = mgr.create_template(name="static", content="Hello world!")
        result = mgr.resolve_template(created["template_id"], {})
        assert result == "Hello world!"


# ===================================================================
# delete_template (soft delete)
# ===================================================================

class TestDeleteTemplate:

    def test_soft_delete(self, mgr):
        created = _make_template(mgr)
        assert mgr.delete_template(created["template_id"]) is True
        fetched = mgr.get_template(created["template_id"])
        assert fetched["is_active"] == 0

    def test_delete_nonexistent_returns_false(self, mgr):
        assert mgr.delete_template("nope") is False

    def test_double_delete(self, mgr):
        created = _make_template(mgr)
        assert mgr.delete_template(created["template_id"]) is True
        assert mgr.delete_template(created["template_id"]) is False


# ===================================================================
# duplicate_template
# ===================================================================

class TestDuplicateTemplate:

    def test_duplicate_basic(self, mgr):
        created = _make_template(mgr)
        dup = mgr.duplicate_template(created["template_id"])
        assert dup is not None
        assert dup["template_id"] != created["template_id"]
        assert dup["name"] == "test-template (copy)"
        assert dup["content"] == created["content"]
        assert dup["version"] == 1

    def test_duplicate_custom_name(self, mgr):
        created = _make_template(mgr)
        dup = mgr.duplicate_template(created["template_id"], new_name="my-copy")
        assert dup["name"] == "my-copy"

    def test_duplicate_nonexistent_returns_none(self, mgr):
        assert mgr.duplicate_template("nope") is None

    def test_duplicate_preserves_category_and_team(self, mgr):
        created = _make_template(mgr, category="cat", team_id="t1")
        dup = mgr.duplicate_template(created["template_id"])
        assert dup["category"] == "cat"
        assert dup["team_id"] == "t1"


# ===================================================================
# get_template_versions
# ===================================================================

class TestGetTemplateVersions:

    def test_no_history_on_create(self, mgr):
        created = _make_template(mgr)
        versions = mgr.get_template_versions(created["template_id"])
        assert versions == []

    def test_history_after_update(self, mgr):
        created = _make_template(mgr)
        mgr.update_template(created["template_id"], name="v2")
        versions = mgr.get_template_versions(created["template_id"])
        assert len(versions) == 1
        assert versions[0]["name"] == "test-template"
        assert versions[0]["version"] == 1

    def test_multiple_versions(self, mgr):
        created = _make_template(mgr)
        tid = created["template_id"]
        for i in range(4):
            mgr.update_template(tid, name=f"v{i+2}")
        versions = mgr.get_template_versions(tid)
        assert len(versions) == 4
        # Oldest first
        assert versions[0]["version"] == 1
        assert versions[-1]["version"] == 4

    def test_versions_for_nonexistent_template(self, mgr):
        versions = mgr.get_template_versions("nope")
        assert versions == []


# ===================================================================
# search_templates
# ===================================================================

class TestSearchTemplates:

    def test_search_by_name(self, mgr):
        _make_template(mgr, name="alpha template")
        _make_template(mgr, name="beta template")
        results = mgr.search_templates("alpha")
        assert len(results) == 1
        assert results[0]["name"] == "alpha template"

    def test_search_by_description(self, mgr):
        _make_template(mgr, name="t1", description="security audit prompt")
        _make_template(mgr, name="t2", description="code review prompt")
        results = mgr.search_templates("security")
        assert len(results) == 1

    def test_search_by_content(self, mgr):
        _make_template(mgr, name="t1", content="Analyze {target} for vulnerabilities")
        _make_template(mgr, name="t2", content="Review {code} for style")
        results = mgr.search_templates("vulnerabilities")
        assert len(results) == 1

    def test_search_case_insensitive(self, mgr):
        _make_template(mgr, name="My Template")
        results = mgr.search_templates("my template")
        assert len(results) == 1

    def test_search_excludes_inactive(self, mgr):
        created = _make_template(mgr, name="findme")
        mgr.delete_template(created["template_id"])
        results = mgr.search_templates("findme")
        assert len(results) == 0

    def test_search_no_results(self, mgr):
        _make_template(mgr, name="t1")
        results = mgr.search_templates("nonexistent query")
        assert results == []


# ===================================================================
# get_categories
# ===================================================================

class TestGetCategories:

    def test_distinct_categories(self, mgr):
        _make_template(mgr, category="cat-a")
        _make_template(mgr, category="cat-b")
        _make_template(mgr, category="cat-a")
        cats = mgr.get_categories()
        assert cats == ["cat-a", "cat-b"]

    def test_excludes_empty(self, mgr):
        _make_template(mgr, category="")
        _make_template(mgr, category="real")
        cats = mgr.get_categories()
        assert cats == ["real"]

    def test_excludes_inactive(self, mgr):
        created = _make_template(mgr, category="deleteme")
        mgr.delete_template(created["template_id"])
        cats = mgr.get_categories()
        assert "deleteme" not in cats


# ===================================================================
# get_template_stats
# ===================================================================

class TestGetTemplateStats:

    def test_empty_stats(self, mgr):
        stats = mgr.get_template_stats()
        assert stats["total"] == 0
        assert stats["active"] == 0
        assert stats["inactive"] == 0

    def test_stats_counts(self, mgr):
        a = _make_template(mgr, name="a", category="cat1", team_id="t1")
        _make_template(mgr, name="b", category="cat1", team_id="t2")
        _make_template(mgr, name="c", category="cat2", team_id="t1")
        mgr.delete_template(a["template_id"])
        stats = mgr.get_template_stats()
        assert stats["total"] == 3
        assert stats["active"] == 2
        assert stats["inactive"] == 1
        assert stats["by_category"]["cat1"] == 1
        assert stats["by_category"]["cat2"] == 1
        assert stats["by_team"]["t1"] == 1
        assert stats["by_team"]["t2"] == 1


# ===================================================================
# export_template / import_template
# ===================================================================

class TestExportImport:

    def test_export(self, mgr):
        created = _make_template(mgr)
        exported = mgr.export_template(created["template_id"])
        data = json.loads(exported)
        assert data["name"] == "test-template"
        assert data["content"] == "Hello {name}, welcome to {place}!"

    def test_export_nonexistent_raises(self, mgr):
        with pytest.raises(ValueError, match="not found"):
            mgr.export_template("nope")

    def test_import_creates_new(self, mgr):
        payload = json.dumps({
            "name": "imported",
            "content": "Hi {user}",
            "description": "imported desc",
            "category": "import",
        })
        result = mgr.import_template(payload)
        assert result["name"] == "imported"
        assert result["variables"] == ["user"]
        assert result["version"] == 1

    def test_import_missing_fields_raises(self, mgr):
        with pytest.raises(ValueError, match="name.*content"):
            mgr.import_template(json.dumps({"name": "x"}))

    def test_import_overwrite_existing(self, mgr):
        created = _make_template(mgr)
        payload = json.dumps({
            "template_id": created["template_id"],
            "name": "overwritten",
            "content": "New content {x}",
        })
        result = mgr.import_template(payload, overwrite=True)
        assert result["name"] == "overwritten"
        assert result["variables"] == ["x"]
        assert result["version"] == 2

    def test_import_overwrite_nonexisting_creates_new(self, mgr):
        payload = json.dumps({
            "template_id": "ghost-id",
            "name": "new-one",
            "content": "Hello",
        })
        result = mgr.import_template(payload, overwrite=True)
        assert result["version"] == 1
        assert result["name"] == "new-one"

    def test_roundtrip_export_import(self, mgr):
        created = _make_template(mgr)
        exported = mgr.export_template(created["template_id"])
        # Import into a fresh manager
        mgr2 = PromptTemplateManager(db_path=":memory:")
        imported = mgr2.import_template(exported)
        assert imported["name"] == created["name"]
        assert imported["content"] == created["content"]
        assert imported["variables"] == created["variables"]


# ===================================================================
# Events
# ===================================================================

class TestEvents:

    def test_created_event(self, mgr_bus, bus):
        _make_template(mgr_bus)
        events = bus.query(topic="template.created")
        assert len(events) >= 1
        assert "template_id" in json.loads(events[0]["payload"])

    def test_updated_event(self, mgr_bus, bus):
        created = _make_template(mgr_bus)
        mgr_bus.update_template(created["template_id"], name="upd")
        events = bus.query(topic="template.updated")
        assert len(events) >= 1
        payload = json.loads(events[0]["payload"])
        assert payload["version"] == 2

    def test_resolved_event(self, mgr_bus, bus):
        created = _make_template(mgr_bus)
        mgr_bus.resolve_template(
            created["template_id"],
            {"name": "A", "place": "B"},
        )
        events = bus.query(topic="template.resolved")
        assert len(events) >= 1

    def test_deleted_event(self, mgr_bus, bus):
        created = _make_template(mgr_bus)
        mgr_bus.delete_template(created["template_id"])
        events = bus.query(topic="template.deleted")
        assert len(events) >= 1
        payload = json.loads(events[0]["payload"])
        assert payload["template_id"] == created["template_id"]


# ===================================================================
# Singleton management
# ===================================================================

class TestSingleton:

    def test_get_returns_same(self):
        m1 = get_prompt_template_manager(db_path=":memory:")
        m2 = get_prompt_template_manager()
        assert m1 is m2

    def test_reset_creates_new(self):
        m1 = get_prompt_template_manager(db_path=":memory:")
        m2 = reset_prompt_template_manager(db_path=":memory:")
        assert m1 is not m2

    def test_reset_then_get_returns_new(self):
        m1 = get_prompt_template_manager(db_path=":memory:")
        reset_prompt_template_manager(db_path=":memory:")
        m2 = get_prompt_template_manager()
        assert m1 is not m2


# ===================================================================
# Thread safety (smoke test)
# ===================================================================

class TestThreadSafety:

    def test_concurrent_creates(self, mgr):
        import threading
        errors = []

        def create_one(idx):
            try:
                mgr.create_template(name=f"concurrent-{idx}", content="hi")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_one, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        results = mgr.list_templates()
        assert len(results) == 10
