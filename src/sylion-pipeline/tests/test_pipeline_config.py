"""Tests for SYLION Core Pipeline Config Manager (40+ tests)."""

import json
import time

import pytest

from sylion.core.pipeline_config import (
    PipelineConfigManager,
    get_pipeline_config_manager,
    reset_pipeline_config_manager,
)
from sylion.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def manager(event_bus):
    return PipelineConfigManager(event_bus=event_bus)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_pipeline_config_manager()
    yield
    reset_pipeline_config_manager()


# ===========================================================================
# 1. Create Config
# ===========================================================================

def test_create_config_returns_dict(manager):
    result = manager.create_config("test-pipeline", "etl", '{"steps": []}')
    assert result["config_id"]
    assert result["name"] == "test-pipeline"
    assert result["pipeline_type"] == "etl"
    assert result["status"] == "active"
    assert result["created_at"] > 0


def test_create_config_default_json(manager):
    result = manager.create_config("empty", "batch")
    assert result["config_json"] == "{}"


def test_create_multiple_configs(manager):
    a = manager.create_config("a", "etl")
    b = manager.create_config("b", "ml")
    assert a["config_id"] != b["config_id"]


# ===========================================================================
# 2. Update Config
# ===========================================================================

def test_update_config_name(manager):
    cfg = manager.create_config("old-name", "etl")
    updated = manager.update_config(cfg["config_id"], name="new-name")
    assert updated["name"] == "new-name"


def test_update_config_status(manager):
    cfg = manager.create_config("x", "etl")
    updated = manager.update_config(cfg["config_id"], status="archived")
    assert updated["status"] == "archived"


def test_update_config_updates_timestamp(manager):
    cfg = manager.create_config("ts", "etl")
    time.sleep(0.01)
    updated = manager.update_config(cfg["config_id"], name="ts2")
    assert updated["updated_at"] >= cfg["created_at"]


def test_update_config_nonexistent(manager):
    assert manager.update_config("nope", name="x") is None


def test_update_config_unknown_field_raises(manager):
    cfg = manager.create_config("x", "etl")
    with pytest.raises(ValueError, match="unknown field"):
        manager.update_config(cfg["config_id"], bad_field="x")


def test_update_config_no_fields_returns_existing(manager):
    cfg = manager.create_config("x", "etl")
    result = manager.update_config(cfg["config_id"])
    assert result["config_id"] == cfg["config_id"]


# ===========================================================================
# 3. Get / List Config
# ===========================================================================

def test_get_config(manager):
    cfg = manager.create_config("find-me", "etl")
    fetched = manager.get_config(cfg["config_id"])
    assert fetched["name"] == "find-me"


def test_get_config_nonexistent(manager):
    assert manager.get_config("nope") is None


def test_list_configs_all(manager):
    manager.create_config("a", "etl")
    manager.create_config("b", "ml")
    configs = manager.list_configs()
    assert len(configs) == 2


def test_list_configs_by_type(manager):
    manager.create_config("a", "etl")
    manager.create_config("b", "ml")
    manager.create_config("c", "etl")
    etl = manager.list_configs(pipeline_type="etl")
    assert len(etl) == 2


def test_list_configs_empty(manager):
    assert manager.list_configs() == []


# ===========================================================================
# 4. Versioning
# ===========================================================================

def test_create_version(manager):
    cfg = manager.create_config("v-test", "etl")
    ver = manager.create_version(cfg["config_id"], "1.0.0", '{"change": "initial"}')
    assert ver["version_id"]
    assert ver["version"] == "1.0.0"
    assert ver["config_id"] == cfg["config_id"]


def test_create_version_nonexistent_config(manager):
    assert manager.create_version("nope", "1.0") is None


def test_get_version(manager):
    cfg = manager.create_config("v-get", "etl")
    ver = manager.create_version(cfg["config_id"], "1.0.0")
    fetched = manager.get_version(ver["version_id"])
    assert fetched["version"] == "1.0.0"


def test_get_version_nonexistent(manager):
    assert manager.get_version("nope") is None


def test_list_versions_by_config(manager):
    cfg = manager.create_config("v-list", "etl")
    manager.create_version(cfg["config_id"], "1.0.0")
    manager.create_version(cfg["config_id"], "1.1.0")
    versions = manager.list_versions(config_id=cfg["config_id"])
    assert len(versions) == 2


def test_list_versions_all(manager):
    c1 = manager.create_config("a", "etl")
    c2 = manager.create_config("b", "ml")
    manager.create_version(c1["config_id"], "1.0")
    manager.create_version(c2["config_id"], "2.0")
    versions = manager.list_versions()
    assert len(versions) == 2


def test_list_versions_empty(manager):
    assert manager.list_versions() == []


# ===========================================================================
# 5. Validation
# ===========================================================================

def test_validate_config_valid(manager):
    cfg = manager.create_config("val-ok", "etl", '{"name": "test", "steps": []}')
    rules = json.dumps({"required_keys": ["name", "steps"]})
    result = manager.validate_config(cfg["config_id"], rules)
    assert result["result"] == "valid"
    assert result["errors"] == []


def test_validate_config_invalid(manager):
    cfg = manager.create_config("val-fail", "etl", '{"name": "test"}')
    rules = json.dumps({"required_keys": ["name", "steps"]})
    result = manager.validate_config(cfg["config_id"], rules)
    assert result["result"] == "invalid"
    assert len(result["errors"]) == 1
    assert "steps" in result["errors"][0]


def test_validate_config_nonexistent(manager):
    assert manager.validate_config("nope") is None


def test_validate_config_no_rules(manager):
    cfg = manager.create_config("val-norules", "etl", '{"x": 1}')
    result = manager.validate_config(cfg["config_id"])
    assert result["result"] == "valid"


# ===========================================================================
# 6. Stats
# ===========================================================================

def test_get_config_stats_empty(manager):
    stats = manager.get_config_stats()
    assert stats["total_configs"] == 0
    assert stats["total_versions"] == 0
    assert stats["valid_rate"] == 0.0


def test_get_config_stats_populated(manager):
    cfg = manager.create_config("s1", "etl")
    manager.create_config("s2", "ml")
    manager.create_version(cfg["config_id"], "1.0")
    manager.validate_config(cfg["config_id"], json.dumps({"required_keys": []}))
    stats = manager.get_config_stats()
    assert stats["total_configs"] == 2
    assert stats["total_versions"] == 1
    assert stats["total_validations"] == 1
    assert stats["valid_rate"] == 100.0


def test_get_config_stats_by_type(manager):
    manager.create_config("a", "etl")
    manager.create_config("b", "etl")
    manager.create_config("c", "ml")
    stats = manager.get_config_stats()
    assert stats["by_pipeline_type"]["etl"] == 2
    assert stats["by_pipeline_type"]["ml"] == 1


# ===========================================================================
# 7. Events
# ===========================================================================

def test_create_config_emits_event(manager, event_bus):
    manager.create_config("ev-cfg", "etl")
    events = event_bus.query(topic="config.created")
    assert len(events) == 1
    payload = events[0]["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload["name"] == "ev-cfg"


def test_update_config_emits_event(manager, event_bus):
    cfg = manager.create_config("ev-upd", "etl")
    manager.update_config(cfg["config_id"], name="updated")
    events = event_bus.query(topic="config.updated")
    assert len(events) == 1


def test_create_version_emits_event(manager, event_bus):
    cfg = manager.create_config("ev-ver", "etl")
    manager.create_version(cfg["config_id"], "1.0")
    events = event_bus.query(topic="config.version_created")
    assert len(events) == 1


def test_validate_config_emits_event(manager, event_bus):
    cfg = manager.create_config("ev-val", "etl")
    manager.validate_config(cfg["config_id"])
    events = event_bus.query(topic="config.validated")
    assert len(events) == 1


def test_no_event_without_bus():
    mgr = PipelineConfigManager(event_bus=None)
    cfg = mgr.create_config("no-ev", "etl")
    assert cfg["status"] == "active"
    mgr.close()


# ===========================================================================
# 8. Singleton
# ===========================================================================

def test_get_pipeline_config_manager_singleton():
    a = get_pipeline_config_manager()
    b = get_pipeline_config_manager()
    assert a is b


def test_reset_pipeline_config_manager():
    a = get_pipeline_config_manager()
    reset_pipeline_config_manager()
    b = get_pipeline_config_manager()
    assert a is not b


# ===========================================================================
# 9. Close / Persistent DB
# ===========================================================================

def test_close(manager):
    manager.create_config("x", "etl")
    manager.close()


def test_persistent_db(tmp_path):
    db_file = tmp_path / "pc_test.db"
    mgr = PipelineConfigManager(db_path=str(db_file))
    cfg = mgr.create_config("persist", "etl")
    mgr.close()
    mgr2 = PipelineConfigManager(db_path=str(db_file))
    fetched = mgr2.get_config(cfg["config_id"])
    assert fetched is not None
    assert fetched["name"] == "persist"
    mgr2.close()


# ===========================================================================
# 10. Integration
# ===========================================================================

def test_full_config_lifecycle(manager, event_bus):
    cfg = manager.create_config("lifecycle", "etl", '{"steps": ["extract", "load"]}')
    manager.create_version(cfg["config_id"], "1.0.0")
    manager.create_version(cfg["config_id"], "1.1.0", '{"change": "added transform"}')
    result = manager.validate_config(
        cfg["config_id"],
        json.dumps({"required_keys": ["steps"]}),
    )
    assert result["result"] == "valid"
    assert len(manager.list_versions(config_id=cfg["config_id"])) == 2
    manager.update_config(cfg["config_id"], status="archived")
    assert manager.get_config(cfg["config_id"])["status"] == "archived"


def test_multiple_types_filter(manager):
    for i in range(3):
        manager.create_config(f"etl-{i}", "etl")
    for i in range(2):
        manager.create_config(f"ml-{i}", "ml")
    assert len(manager.list_configs(pipeline_type="etl")) == 3
    assert len(manager.list_configs(pipeline_type="ml")) == 2
