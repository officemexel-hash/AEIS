"""
SYLION Memory Self-Model Store -- Comprehensive Unit Tests

Tests for sylion.memory.self_model_store.SelfModelStore:
  - initialize / get / update CRUD cycle
  - snapshot creation, history, latest
  - EventBus integration
  - error cases: nonexistent models, empty dicts
  - stats via helper methods
"""

from __future__ import annotations

import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.memory.self_model_store import SelfModel, ModelSnapshot, SelfModelStore


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def store():
    """Fresh in-memory SelfModelStore."""
    return SelfModelStore()


@pytest.fixture
def store_with_bus():
    """SelfModelStore with EventBus + captured events."""
    bus = EventBus()
    captured: list[SylionEvent] = []
    bus.subscribe("*", captured.append)
    sms = SelfModelStore(event_bus=bus)
    return sms, captured


@pytest.fixture
def populated_store(store):
    """Store with 3 models in various states."""
    store.initialize("model-a", capabilities={"reasoning": True})
    store.initialize(
        "model-b",
        capabilities={"code_gen": True},
        constraints={"max_tokens": 4096},
    )
    store.initialize(
        "model-c",
        capabilities={"vision": True},
        constraints={"max_resolution": 1080},
    )
    # Advance model-b to version 3
    store.update("model-b", health="degraded", autonomy_level=2)
    store.update("model-b", health="healthy", autonomy_level=3)
    return store


# =====================================================================
# CRUD Tests
# =====================================================================

class TestSelfModelInitialize:

    def test_initialize_returns_model_dict(self, store):
        result = store.initialize(
            "m1",
            capabilities={"reasoning": True},
            constraints={"max_tokens": 8192},
        )
        assert result["model_id"] == "m1"
        assert result["version"] == 1
        assert result["capabilities"] == {"reasoning": True}
        assert result["constraints"] == {"max_tokens": 8192}
        assert result["health"] == "healthy"
        assert result["autonomy_level"] == 0
        assert result["created_at"] > 0
        assert result["updated_at"] > 0

    def test_initialize_defaults(self, store):
        result = store.initialize("m-defaults")
        assert result["capabilities"] == {}
        assert result["constraints"] == {}
        assert result["health"] == "healthy"
        assert result["autonomy_level"] == 0

    def test_initialize_upserts(self, store):
        store.initialize("m-upsert", capabilities={"v1": True})
        result = store.initialize("m-upsert", capabilities={"v2": True})
        assert result["capabilities"] == {"v2": True}
        assert result["version"] == 1  # INSERT OR REPLACE resets version

    def test_initialize_multiple_models(self, store):
        store.initialize("m1")
        store.initialize("m2")
        store.initialize("m3")
        assert store.get("m1") is not None
        assert store.get("m2") is not None
        assert store.get("m3") is not None


class TestSelfModelGet:

    def test_get_existing_model(self, populated_store):
        model = populated_store.get("model-a")
        assert model is not None
        assert model["model_id"] == "model-a"
        assert model["capabilities"]["reasoning"] is True

    def test_get_nonexistent_model(self, store):
        assert store.get("ghost") is None

    def test_get_returns_parsed_json(self, store):
        store.initialize("m-json", capabilities={"nested": {"key": [1, 2]}})
        model = store.get("m-json")
        assert model["capabilities"]["nested"]["key"] == [1, 2]


class TestSelfModelUpdate:

    def test_update_increments_version(self, populated_store):
        updated = populated_store.update("model-a", health="degraded")
        assert updated is not None
        assert updated["version"] == 2

    def test_update_changes_fields(self, populated_store):
        updated = populated_store.update(
            "model-a",
            capabilities={"reasoning": False, "planning": True},
            health="degraded",
            autonomy_level=5,
        )
        assert updated["health"] == "degraded"
        assert updated["autonomy_level"] == 5
        assert updated["capabilities"]["planning"] is True

    def test_update_preserves_created_at(self, populated_store):
        original = populated_store.get("model-a")
        updated = populated_store.update("model-a", health="healthy")
        assert updated["created_at"] == original["created_at"]
        assert updated["updated_at"] >= original["updated_at"]

    def test_update_nonexistent_returns_none(self, store):
        result = store.update("phantom", health="healthy")
        assert result is None

    def test_multiple_updates_version_progression(self, populated_store):
        populated_store.update("model-a")
        populated_store.update("model-a")
        populated_store.update("model-a")
        model = populated_store.get("model-a")
        # Started at v1, 4 total updates from fixture + 1 in fixture = v5
        # fixture: initialize v1, then model-b gets 2 updates (not model-a)
        # So model-a was v1, now 3 more updates = v4
        assert model["version"] == 4


# =====================================================================
# Snapshot Tests
# =====================================================================

class TestSelfModelSnapshot:

    def test_snapshot_returns_summary(self, populated_store):
        snap = populated_store.snapshot("model-b", reason="checkpoint")
        assert snap is not None
        assert "snapshot_id" in snap
        assert snap["model_id"] == "model-b"
        assert snap["version"] == 3  # model-b was updated twice (v1 -> v2 -> v3)

    def test_snapshot_nonexistent_model(self, populated_store):
        result = populated_store.snapshot("nope")
        assert result is None

    def test_snapshot_reason_recorded(self, populated_store):
        populated_store.snapshot("model-a", reason="pre-upgrade")
        history = populated_store.get_history("model-a")
        assert len(history) == 1
        assert history[0]["reason"] == "pre-upgrade"

    def test_multiple_snapshots_history(self, populated_store):
        populated_store.snapshot("model-a", reason="first")
        populated_store.update("model-a")
        populated_store.snapshot("model-a", reason="second")
        history = populated_store.get_history("model-a")
        assert len(history) == 2

    def test_get_history_limit(self, populated_store):
        for i in range(10):
            populated_store.snapshot("model-a", reason=f"snap-{i}")
        history = populated_store.get_history("model-a", limit=5)
        assert len(history) == 5

    def test_get_history_ordered_desc(self, populated_store):
        populated_store.snapshot("model-a", reason="early")
        populated_store.snapshot("model-a", reason="late")
        history = populated_store.get_history("model-a")
        assert len(history) == 2
        assert history[0]["reason"] == "late"
        assert history[1]["reason"] == "early"

    def test_get_history_empty(self, populated_store):
        history = populated_store.get_history("model-a")
        assert history == []

    def test_get_latest_snapshot(self, populated_store):
        populated_store.snapshot("model-a", reason="first")
        populated_store.update("model-a")
        populated_store.snapshot("model-a", reason="second")
        latest = populated_store.get_latest("model-a")
        assert latest is not None
        assert latest["reason"] == "second"

    def test_get_latest_nonexistent(self, populated_store):
        assert populated_store.get_latest("model-a") is None


# =====================================================================
# EventBus Integration
# =====================================================================

class TestSelfModelEventBus:

    def test_initialize_emits_event(self, store_with_bus):
        store, captured = store_with_bus
        store.initialize("ev-1")
        events = [e for e in captured if e.topic == "self_model.initialized"]
        assert len(events) == 1
        assert events[0].payload["model_id"] == "ev-1"

    def test_update_emits_event(self, store_with_bus):
        store, captured = store_with_bus
        store.initialize("ev-2")
        captured.clear()
        store.update("ev-2", health="degraded")
        events = [e for e in captured if e.topic == "self_model.updated"]
        assert len(events) == 1
        assert events[0].payload["version"] == 2
        assert events[0].payload["health"] == "degraded"

    def test_snapshot_emits_event(self, store_with_bus):
        store, captured = store_with_bus
        store.initialize("ev-3")
        captured.clear()
        store.snapshot("ev-3", reason="test")
        events = [e for e in captured if e.topic == "self_model.snapshotted"]
        assert len(events) == 1
        assert "snapshot_id" in events[0].payload

    def test_no_events_without_bus(self, store):
        # Should not raise when no EventBus
        store.initialize("no-bus")
        store.update("no-bus")
        store.snapshot("no-bus")


# =====================================================================
# Dataclass Tests
# =====================================================================

class TestSelfModelDataclass:

    def test_self_model_auto_fields(self):
        m = SelfModel()
        assert len(m.model_id) == 32  # uuid hex
        assert m.created_at > 0
        assert m.updated_at > 0

    def test_self_model_custom_id(self):
        m = SelfModel(model_id="custom-id")
        assert m.model_id == "custom-id"

    def test_model_snapshot_auto_fields(self):
        s = ModelSnapshot()
        assert len(s.snapshot_id) == 32
        assert s.timestamp > 0

    def test_model_snapshot_custom_id(self):
        s = ModelSnapshot(snapshot_id="snap-1")
        assert s.snapshot_id == "snap-1"
