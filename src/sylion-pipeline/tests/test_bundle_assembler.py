"""
Tests for sylion.core.bundle_assembler -- BundleAssembler

Covers:
  - create_bundle: validation, initial components, return values
  - add_component: validation, bundle existence, config as dict/str
  - remove_component: found / not-found
  - get_bundle: with components, not found
  - list_bundles: status filter, limit
  - create_version: snapshot creation, bundle not found
  - get_version: retrieval, snapshot parsing, not found
  - list_versions: ordering, empty
  - deploy_bundle: status change, event emission, validation
  - EventBus events: bundle_created, component_added, version_created, bundle_deployed
  - Thread safety: concurrent create_bundle calls
  - Singleton: get_bundle_assembler / reset_bundle_assembler
"""
from __future__ import annotations

import json
import threading
import time

import pytest

from sylion.core.bundle_assembler import (
    BundleAssembler,
    get_bundle_assembler,
    reset_bundle_assembler,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    eb = EventBus()
    eb._captured: list[SylionEvent] = []

    _orig = eb.publish

    def _capture(event: SylionEvent):
        eb._captured.append(event)
        return _orig(event)

    eb.publish = _capture
    return eb


@pytest.fixture
def assembler():
    """Fresh BundleAssembler (in-memory, no event bus)."""
    return BundleAssembler()


@pytest.fixture
def assembler_with_bus(bus):
    """BundleAssembler wired to the captured EventBus."""
    return BundleAssembler(event_bus=bus)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create(assembler: BundleAssembler, name: str = "test-bundle",
            description: str = "") -> dict:
    return assembler.create_bundle(name, description)


# ============================================================================
# TestCreateBundle
# ============================================================================

class TestCreateBundle:
    def test_basic_creation(self, assembler):
        result = _create(assembler)
        assert result["bundle_id"]
        assert result["name"] == "test-bundle"
        assert result["status"] == "draft"
        assert result["created_at"] > 0

    def test_with_description(self, assembler):
        result = assembler.create_bundle("my-bundle", "A test description")
        assert result["description"] == "A test description"

    def test_empty_name_raises(self, assembler):
        with pytest.raises(ValueError, match="non-empty"):
            assembler.create_bundle("")

    def test_with_initial_components(self, assembler):
        components = [
            {"component_type": "module", "component_ref": "core.api", "config_json": {"port": 8080}},
            {"component_type": "module", "component_ref": "core.auth"},
        ]
        result = assembler.create_bundle("with-comps", components_list=components)
        assert len(result["components"]) == 2
        assert result["components"][0]["component_ref"] == "core.api"

    def test_initial_components_config_serialized(self, assembler):
        components = [
            {"component_type": "module", "component_ref": "mod.a", "config_json": {"k": "v"}},
        ]
        result = assembler.create_bundle("config-c", components_list=components)
        parsed = json.loads(result["components"][0]["config_json"])
        assert parsed["k"] == "v"

    def test_stored_in_db(self, assembler):
        _create(assembler)
        bundles = assembler.list_bundles()
        assert len(bundles) == 1

    def test_emits_bundle_created(self, assembler_with_bus, bus):
        assembler_with_bus.create_bundle("evt-bundle")
        topics = [e.topic for e in bus._captured]
        assert "bundle_created" in topics
        event = [e for e in bus._captured if e.topic == "bundle_created"][0]
        assert event.payload["name"] == "evt-bundle"

    def test_unique_bundle_ids(self, assembler):
        b1 = assembler.create_bundle("b1")
        b2 = assembler.create_bundle("b2")
        assert b1["bundle_id"] != b2["bundle_id"]

    def test_empty_components_list(self, assembler):
        result = assembler.create_bundle("empty-comps", components_list=[])
        assert result["components"] == []

    def test_none_components_list(self, assembler):
        result = assembler.create_bundle("no-comps")
        assert result["components"] == []


# ============================================================================
# TestAddComponent
# ============================================================================

class TestAddComponent:
    def test_add_basic_component(self, assembler):
        b = _create(assembler, name="add-c")
        result = assembler.add_component(b["bundle_id"], "module", "core.auth")
        assert result["component_id"]
        assert result["component_type"] == "module"
        assert result["component_ref"] == "core.auth"

    def test_add_with_config_dict(self, assembler):
        b = _create(assembler, name="add-cfg")
        result = assembler.add_component(b["bundle_id"], "service", "svc.a", {"timeout": 30})
        parsed = json.loads(result["config_json"])
        assert parsed["timeout"] == 30

    def test_add_with_config_string(self, assembler):
        b = _create(assembler, name="add-cfg-s")
        result = assembler.add_component(b["bundle_id"], "service", "svc.a", '{"timeout": 30}')
        assert result["config_json"] == '{"timeout": 30}'

    def test_add_to_nonexistent_bundle_raises(self, assembler):
        with pytest.raises(ValueError, match="not found"):
            assembler.add_component("nonexistent", "module", "mod.a")

    def test_empty_bundle_id_raises(self, assembler):
        with pytest.raises(ValueError, match="non-empty"):
            assembler.add_component("", "module", "ref")

    def test_empty_component_type_raises(self, assembler):
        b = _create(assembler)
        with pytest.raises(ValueError, match="non-empty"):
            assembler.add_component(b["bundle_id"], "", "ref")

    def test_empty_component_ref_raises(self, assembler):
        b = _create(assembler)
        with pytest.raises(ValueError, match="non-empty"):
            assembler.add_component(b["bundle_id"], "module", "")

    def test_emits_component_added(self, assembler_with_bus, bus):
        b = assembler_with_bus.create_bundle("add-evt")
        assembler_with_bus.add_component(b["bundle_id"], "module", "mod.x")
        topics = [e.topic for e in bus._captured]
        assert "component_added" in topics

    def test_component_visible_in_get_bundle(self, assembler):
        b = _create(assembler, name="vis-c")
        assembler.add_component(b["bundle_id"], "module", "mod.y")
        bundle = assembler.get_bundle(b["bundle_id"])
        assert len(bundle["components"]) == 1
        assert bundle["components"][0]["component_ref"] == "mod.y"

    def test_add_updates_bundle_timestamp(self, assembler):
        b = _create(assembler, name="ts-b")
        original = assembler.get_bundle(b["bundle_id"])
        time.sleep(0.01)
        assembler.add_component(b["bundle_id"], "module", "mod.z")
        updated = assembler.get_bundle(b["bundle_id"])
        assert updated["updated_at"] >= original["created_at"]


# ============================================================================
# TestRemoveComponent
# ============================================================================

class TestRemoveComponent:
    def test_remove_existing(self, assembler):
        b = _create(assembler, name="rem-c")
        comp = assembler.add_component(b["bundle_id"], "module", "mod.a")
        assert assembler.remove_component(b["bundle_id"], comp["component_id"]) is True
        bundle = assembler.get_bundle(b["bundle_id"])
        assert len(bundle["components"]) == 0

    def test_remove_nonexistent(self, assembler):
        b = _create(assembler, name="rem-ne")
        assert assembler.remove_component(b["bundle_id"], "nonexistent") is False

    def test_remove_wrong_bundle_returns_false(self, assembler):
        b1 = _create(assembler, name="rem-b1")
        b2 = _create(assembler, name="rem-b2")
        comp = assembler.add_component(b1["bundle_id"], "module", "mod.a")
        assert assembler.remove_component(b2["bundle_id"], comp["component_id"]) is False

    def test_remove_twice_returns_false(self, assembler):
        b = _create(assembler, name="rem-2x")
        comp = assembler.add_component(b["bundle_id"], "module", "mod.a")
        assert assembler.remove_component(b["bundle_id"], comp["component_id"]) is True
        assert assembler.remove_component(b["bundle_id"], comp["component_id"]) is False

    def test_remove_empty_args_raises(self, assembler):
        with pytest.raises(ValueError, match="non-empty"):
            assembler.remove_component("", "some-id")
        with pytest.raises(ValueError, match="non-empty"):
            assembler.remove_component("some-id", "")


# ============================================================================
# TestGetBundle
# ============================================================================

class TestGetBundle:
    def test_get_existing(self, assembler):
        b = _create(assembler, name="get-b")
        result = assembler.get_bundle(b["bundle_id"])
        assert result is not None
        assert result["name"] == "get-b"

    def test_get_nonexistent(self, assembler):
        assert assembler.get_bundle("nonexistent") is None

    def test_get_includes_components(self, assembler):
        b = _create(assembler, name="get-inc")
        assembler.add_component(b["bundle_id"], "module", "m1")
        assembler.add_component(b["bundle_id"], "service", "s1")
        result = assembler.get_bundle(b["bundle_id"])
        assert len(result["components"]) == 2

    def test_get_returns_all_fields(self, assembler):
        b = assembler.create_bundle("full-b", "full description")
        result = assembler.get_bundle(b["bundle_id"])
        assert "bundle_id" in result
        assert "name" in result
        assert "description" in result
        assert "status" in result
        assert "created_at" in result
        assert "updated_at" in result
        assert "components" in result


# ============================================================================
# TestListBundles
# ============================================================================

class TestListBundles:
    def test_list_all(self, assembler):
        _create(assembler, name="b1")
        _create(assembler, name="b2")
        assert len(assembler.list_bundles()) == 2

    def test_list_by_status(self, assembler):
        b1 = _create(assembler, name="draft-b")
        b2 = _create(assembler, name="deploy-b")
        # Manually set status for testing filter
        with assembler._lock:
            assembler._conn.execute(
                "UPDATE bundles SET status = 'deployed' WHERE bundle_id = ?",
                (b2["bundle_id"],),
            )
            assembler._conn.commit()
        deployed = assembler.list_bundles(status="deployed")
        assert len(deployed) == 1
        assert deployed[0]["name"] == "deploy-b"

    def test_list_limit(self, assembler):
        for i in range(10):
            _create(assembler, name=f"lim-{i}")
        assert len(assembler.list_bundles(limit=5)) == 5

    def test_list_empty(self, assembler):
        assert assembler.list_bundles() == []


# ============================================================================
# TestCreateVersion
# ============================================================================

class TestCreateVersion:
    def test_basic_version(self, assembler):
        b = _create(assembler, name="ver-c")
        assembler.add_component(b["bundle_id"], "module", "m1")
        result = assembler.create_version(b["bundle_id"], "v1.0.0")
        assert result["version_id"]
        assert result["version_tag"] == "v1.0.0"
        assert result["bundle_id"] == b["bundle_id"]

    def test_version_snapshot_includes_components(self, assembler):
        b = _create(assembler, name="snap-c")
        assembler.add_component(b["bundle_id"], "module", "m1")
        assembler.create_version(b["bundle_id"], "v1.0")
        version = assembler.get_version(b["bundle_id"], "v1.0")
        assert "components" in version["snapshot"]
        assert len(version["snapshot"]["components"]) == 1

    def test_nonexistent_bundle_returns_none(self, assembler):
        result = assembler.create_version("nonexistent", "v1.0")
        assert result is None

    def test_empty_bundle_id_raises(self, assembler):
        with pytest.raises(ValueError, match="non-empty"):
            assembler.create_version("", "v1.0")

    def test_empty_version_tag_raises(self, assembler):
        b = _create(assembler)
        with pytest.raises(ValueError, match="non-empty"):
            assembler.create_version(b["bundle_id"], "")

    def test_emits_version_created(self, assembler_with_bus, bus):
        b = assembler_with_bus.create_bundle("ver-evt")
        assembler_with_bus.create_version(b["bundle_id"], "v1.0")
        topics = [e.topic for e in bus._captured]
        assert "version_created" in topics

    def test_multiple_versions(self, assembler):
        b = _create(assembler, name="multi-ver")
        assembler.create_version(b["bundle_id"], "v1.0")
        assembler.create_version(b["bundle_id"], "v2.0")
        versions = assembler.list_versions(b["bundle_id"])
        assert len(versions) == 2


# ============================================================================
# TestGetVersion
# ============================================================================

class TestGetVersion:
    def test_get_existing_version(self, assembler):
        b = _create(assembler, name="getv-c")
        assembler.create_version(b["bundle_id"], "v1.0")
        result = assembler.get_version(b["bundle_id"], "v1.0")
        assert result is not None
        assert result["version_tag"] == "v1.0"

    def test_get_nonexistent_version(self, assembler):
        b = _create(assembler, name="getv-ne")
        assert assembler.get_version(b["bundle_id"], "v99.0") is None

    def test_snapshot_is_parsed(self, assembler):
        b = _create(assembler, name="getv-parse")
        assembler.add_component(b["bundle_id"], "module", "m1")
        assembler.create_version(b["bundle_id"], "v1.0")
        version = assembler.get_version(b["bundle_id"], "v1.0")
        assert isinstance(version["snapshot"], dict)
        assert "bundle" in version["snapshot"]
        assert "components" in version["snapshot"]


# ============================================================================
# TestListVersions
# ============================================================================

class TestListVersions:
    def test_list_all_versions(self, assembler):
        b = _create(assembler, name="lv-c")
        assembler.create_version(b["bundle_id"], "v1.0")
        assembler.create_version(b["bundle_id"], "v2.0")
        versions = assembler.list_versions(b["bundle_id"])
        assert len(versions) == 2

    def test_list_empty(self, assembler):
        b = _create(assembler, name="lv-empty")
        assert assembler.list_versions(b["bundle_id"]) == []

    def test_list_ordered_desc(self, assembler):
        b = _create(assembler, name="lv-order")
        assembler.create_version(b["bundle_id"], "v1.0")
        time.sleep(0.01)
        assembler.create_version(b["bundle_id"], "v2.0")
        versions = assembler.list_versions(b["bundle_id"])
        assert versions[0]["version_tag"] == "v2.0"
        assert versions[1]["version_tag"] == "v1.0"


# ============================================================================
# TestDeployBundle
# ============================================================================

class TestDeployBundle:
    def test_deploy_existing(self, assembler):
        b = _create(assembler, name="dep-c")
        result = assembler.deploy_bundle(b["bundle_id"], "production")
        assert result is not None
        assert result["status"] == "deploying"
        assert result["target_env"] == "production"

    def test_deploy_updates_status(self, assembler):
        b = _create(assembler, name="dep-status")
        assembler.deploy_bundle(b["bundle_id"], "staging")
        bundle = assembler.get_bundle(b["bundle_id"])
        assert bundle["status"] == "deploying"

    def test_deploy_nonexistent_returns_none(self, assembler):
        result = assembler.deploy_bundle("nonexistent", "prod")
        assert result is None

    def test_deploy_empty_bundle_id_raises(self, assembler):
        with pytest.raises(ValueError, match="non-empty"):
            assembler.deploy_bundle("", "prod")

    def test_deploy_empty_target_env_raises(self, assembler):
        b = _create(assembler)
        with pytest.raises(ValueError, match="non-empty"):
            assembler.deploy_bundle(b["bundle_id"], "")

    def test_emits_bundle_deployed(self, assembler_with_bus, bus):
        b = assembler_with_bus.create_bundle("dep-evt")
        assembler_with_bus.deploy_bundle(b["bundle_id"], "prod")
        topics = [e.topic for e in bus._captured]
        assert "bundle_deployed" in topics
        event = [e for e in bus._captured if e.topic == "bundle_deployed"][0]
        assert event.payload["target_env"] == "prod"

    def test_deploying_bundle_in_status_filter(self, assembler):
        b = _create(assembler, name="dep-filter")
        assembler.deploy_bundle(b["bundle_id"], "prod")
        deploying = assembler.list_bundles(status="deploying")
        assert len(deploying) == 1


# ============================================================================
# TestThreadSafety
# ============================================================================

class TestThreadSafety:
    def test_concurrent_create_bundles(self, assembler):
        errors: list[Exception] = []

        def worker(n: int):
            try:
                for i in range(10):
                    assembler.create_bundle(f"concurrent_{n}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(assembler.list_bundles()) == 50

    def test_concurrent_read_write(self, assembler):
        errors: list[Exception] = []
        b = assembler.create_bundle("rw-bundle")

        def writer():
            try:
                for i in range(20):
                    assembler.add_component(b["bundle_id"], "module", f"mod_{i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(20):
                    assembler.list_bundles()
                    assembler.get_bundle(b["bundle_id"])
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ============================================================================
# TestSingleton
# ============================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        reset_bundle_assembler()
        ba = get_bundle_assembler()
        assert isinstance(ba, BundleAssembler)
        reset_bundle_assembler()

    def test_get_returns_same_instance(self):
        reset_bundle_assembler()
        ba1 = get_bundle_assembler()
        ba2 = get_bundle_assembler()
        assert ba1 is ba2
        reset_bundle_assembler()

    def test_reset_clears_singleton(self):
        reset_bundle_assembler()
        ba1 = get_bundle_assembler()
        reset_bundle_assembler()
        ba2 = get_bundle_assembler()
        assert ba1 is not ba2
        reset_bundle_assembler()
