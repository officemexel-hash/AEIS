"""Tests for SYLION AEIS LPW Checkpoint (enhanced Last Known Good Position)."""
import json
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.module_registry import (
    ModuleKind,
    ModuleLifecycleStage,
    ModuleManifest,
    ModuleRegistry,
)
from sylion.rebuild.lpw_checkpoint import LPWCheckpoint, get_lpw_checkpoint


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def registry():
    return ModuleRegistry()


@pytest.fixture
def cp(bus):
    """LPWCheckpoint with event bus, no registry (unit-level)."""
    return LPWCheckpoint(event_bus=bus)


@pytest.fixture
def cp_full(bus, registry):
    """LPWCheckpoint with both registry and event bus."""
    return LPWCheckpoint(registry=registry, event_bus=bus)


def _register_module(registry, module_id="mod.alpha", kind=ModuleKind.CORE_KERNEL,
                     owner="P01", lifecycle="draft", contract_ver="1.0.0"):
    """Helper: register a single module and optionally transition lifecycle."""
    registry.register(ModuleManifest(
        module_id=module_id,
        module_kind=kind,
        owner_plan=owner,
        contract_version=contract_ver,
    ))
    if lifecycle != "draft":
        stages = {
            "build": ModuleLifecycleStage.BUILD,
            "validate": ModuleLifecycleStage.VALIDATE,
            "shadow": ModuleLifecycleStage.SHADOW,
            "dual": ModuleLifecycleStage.DUAL,
            "cutover": ModuleLifecycleStage.CUTOVER,
            "stable": ModuleLifecycleStage.STABLE,
        }
        # Walk through stages to reach the desired one
        stage_order = ["build", "validate", "shadow", "dual", "cutover", "stable"]
        for s in stage_order:
            if s == lifecycle:
                registry.transition(module_id, stages[s])
                break
            registry.transition(module_id, stages[s])


# ===========================================================================
# 1. Basic creation tests
# ===========================================================================

class TestCreateCheckpoint:
    """Tests for create_checkpoint."""

    def test_create_returns_required_keys(self, cp):
        result = cp.create_checkpoint(label="test", trigger="manual")
        for key in ("checkpoint_id", "snapshot_hash", "modules", "contracts",
                     "created_at", "event_position", "label", "trigger"):
            assert key in result

    def test_create_has_nonempty_id(self, cp):
        result = cp.create_checkpoint(label="test", trigger="manual")
        assert len(result["checkpoint_id"]) == 32  # uuid hex

    def test_create_snapshot_hash_is_sha256(self, cp):
        result = cp.create_checkpoint(label="test", trigger="manual")
        assert len(result["snapshot_hash"]) == 64  # SHA-256 hex

    def test_create_label_and_trigger_stored(self, cp):
        result = cp.create_checkpoint(label="pre-upgrade", trigger="D3_change")
        assert result["label"] == "pre-upgrade"
        assert result["trigger"] == "D3_change"

    def test_create_with_registry_captures_modules(self, cp_full):
        _register_module(cp_full._registry, "mod.a")
        result = cp_full.create_checkpoint(label="m1", trigger="auto")
        assert len(result["modules"]) == 1
        assert result["modules"][0]["module_id"] == "mod.a"

    def test_create_with_registry_captures_contracts(self, cp_full):
        _register_module(cp_full._registry, "mod.b", contract_ver="2.5.0")
        result = cp_full.create_checkpoint(label="m2", trigger="auto")
        assert len(result["contracts"]) == 1
        assert result["contracts"][0]["contract_ver"] == "2.5.0"

    def test_create_event_position_captured(self, cp):
        result = cp.create_checkpoint(label="ev", trigger="auto")
        assert result["event_position"] > 0


# ===========================================================================
# 2. Query tests
# ===========================================================================

class TestQueryCheckpoint:
    """Tests for get_latest, get_checkpoint, list_checkpoints."""

    def test_get_latest_returns_none_when_empty(self, cp):
        assert cp.get_latest() is None

    def test_get_latest_returns_most_recent(self, cp):
        r1 = cp.create_checkpoint(label="first", trigger="auto")
        r2 = cp.create_checkpoint(label="second", trigger="auto")
        latest = cp.get_latest()
        assert latest is not None
        assert latest["checkpoint_id"] == r2["checkpoint_id"]

    def test_get_checkpoint_by_id(self, cp):
        r = cp.create_checkpoint(label="by-id", trigger="auto")
        fetched = cp.get_checkpoint(r["checkpoint_id"])
        assert fetched is not None
        assert fetched["label"] == "by-id"

    def test_get_checkpoint_nonexistent_returns_none(self, cp):
        assert cp.get_checkpoint("deadbeef") is None

    def test_list_checkpoints_empty(self, cp):
        assert cp.list_checkpoints() == []

    def test_list_checkpoints_order(self, cp):
        cp.create_checkpoint(label="oldest", trigger="auto")
        cp.create_checkpoint(label="newest", trigger="auto")
        cps = cp.list_checkpoints()
        assert len(cps) == 2
        assert cps[0]["label"] == "newest"
        assert cps[1]["label"] == "oldest"

    def test_list_checkpoints_limit(self, cp):
        for i in range(5):
            cp.create_checkpoint(label=f"cp-{i}", trigger="auto")
        cps = cp.list_checkpoints(limit=3)
        assert len(cps) == 3


# ===========================================================================
# 3. Verification tests
# ===========================================================================

class TestVerifyCheckpoint:
    """Tests for verify_checkpoint."""

    def test_verify_valid_checkpoint(self, cp):
        r = cp.create_checkpoint(label="verify-me", trigger="auto")
        v = cp.verify_checkpoint(r["checkpoint_id"])
        assert v["valid"] is True
        assert v["hash_match"] is True

    def test_verify_detects_corruption(self, cp):
        r = cp.create_checkpoint(label="corrupt", trigger="auto")
        # Corrupt the hash in the database
        cp._conn.execute(
            "UPDATE lpw_checkpoints SET snapshot_hash = 'deadbeef' "
            "WHERE checkpoint_id = ?",
            (r["checkpoint_id"],),
        )
        cp._conn.commit()
        v = cp.verify_checkpoint(r["checkpoint_id"])
        assert v["valid"] is False
        assert v["hash_match"] is False

    def test_verify_nonexistent_checkpoint(self, cp):
        v = cp.verify_checkpoint("nonexistent")
        assert v["valid"] is False
        assert "error" in v

    def test_verify_invalidated_checkpoint(self, cp):
        r = cp.create_checkpoint(label="invalidate", trigger="auto")
        cp.invalidate_checkpoint(r["checkpoint_id"])
        v = cp.verify_checkpoint(r["checkpoint_id"])
        assert v["valid"] is False
        assert v["is_valid_flag"] is False


# ===========================================================================
# 4. Restore tests
# ===========================================================================

class TestRestoreCheckpoint:
    """Tests for restore_checkpoint."""

    def test_restore_nonexistent_returns_error(self, cp_full):
        result = cp_full.restore_checkpoint("nonexistent")
        assert "error" in result
        assert result["error"] == "checkpoint not found"

    def test_restore_restores_lifecycle(self, cp_full):
        reg = cp_full._registry
        _register_module(reg, "mod.x", lifecycle="stable")
        cp_full.create_checkpoint(label="before", trigger="manual")
        # Transition module away from stable
        reg.transition("mod.x", ModuleLifecycleStage.SHADOW)
        assert reg.get("mod.x")["lifecycle"] == "shadow"
        # Get checkpoint and restore
        cp_data = cp_full.get_latest()
        result = cp_full.restore_checkpoint(cp_data["checkpoint_id"])
        assert result["restored_count"] == 1
        assert reg.get("mod.x")["lifecycle"] == "stable"

    def test_restore_restores_contract_version(self, cp_full):
        reg = cp_full._registry
        _register_module(reg, "mod.cv", contract_ver="3.0.0")
        cp_data = cp_full.create_checkpoint(label="contract", trigger="auto")
        # Change contract version directly
        with reg._lock:
            reg._conn.execute(
                "UPDATE sylion_modules SET contract_ver='9.9.9' WHERE module_id='mod.cv'"
            )
            reg._conn.commit()
        assert reg.get("mod.cv")["contract_ver"] == "9.9.9"
        # Restore
        cp_full.restore_checkpoint(cp_data["checkpoint_id"])
        assert reg.get("mod.cv")["contract_ver"] == "3.0.0"

    def test_restore_marks_restored_at(self, cp):
        r = cp.create_checkpoint(label="restore-ts", trigger="auto")
        result = cp.restore_checkpoint(r["checkpoint_id"])
        assert result["restored_at"] > 0

    def test_restore_invalid_checkpoint_returns_error(self, cp):
        r = cp.create_checkpoint(label="inv", trigger="auto")
        cp.invalidate_checkpoint(r["checkpoint_id"])
        result = cp.restore_checkpoint(r["checkpoint_id"])
        assert "error" in result
        assert "invalid" in result["error"]

    def test_restore_with_multiple_modules(self, cp_full):
        reg = cp_full._registry
        _register_module(reg, "mod.a", lifecycle="stable")
        _register_module(reg, "mod.b", lifecycle="stable", contract_ver="2.0.0")
        cp_data = cp_full.create_checkpoint(label="multi", trigger="auto")
        # Transition both
        reg.transition("mod.a", ModuleLifecycleStage.SHADOW)
        reg.transition("mod.b", ModuleLifecycleStage.SHADOW)
        assert reg.get("mod.a")["lifecycle"] == "shadow"
        assert reg.get("mod.b")["lifecycle"] == "shadow"
        # Restore
        result = cp_full.restore_checkpoint(cp_data["checkpoint_id"])
        assert result["restored_count"] == 2
        assert reg.get("mod.a")["lifecycle"] == "stable"
        assert reg.get("mod.b")["lifecycle"] == "stable"


# ===========================================================================
# 5. Prune tests
# ===========================================================================

class TestPruneCheckpoints:
    """Tests for prune_old_checkpoints."""

    def test_prune_keeps_most_recent(self, cp):
        ids = []
        for i in range(5):
            r = cp.create_checkpoint(label=f"prune-{i}", trigger="auto")
            ids.append(r["checkpoint_id"])
        removed = cp.prune_old_checkpoints(keep=3)
        assert removed == 2
        remaining = cp.list_checkpoints(limit=100)
        assert len(remaining) == 3
        # The last 3 created should remain
        for r in remaining:
            assert r["checkpoint_id"] in ids[2:]

    def test_prune_nothing_if_under_limit(self, cp):
        cp.create_checkpoint(label="only", trigger="auto")
        removed = cp.prune_old_checkpoints(keep=10)
        assert removed == 0

    def test_prune_empty_table(self, cp):
        removed = cp.prune_old_checkpoints(keep=5)
        assert removed == 0


# ===========================================================================
# 6. Event emission tests
# ===========================================================================

class TestEventEmission:
    """Tests that checkpoints emit events on the bus."""

    def test_create_emits_event(self, bus):
        events = []
        bus.subscribe("rebuild.lpw_checkpoint.created",
                       lambda e: events.append(e))
        cp = LPWCheckpoint(event_bus=bus)
        cp.create_checkpoint(label="emit-test", trigger="manual")
        assert len(events) == 1
        assert events[0].payload["label"] == "emit-test"

    def test_restore_emits_event(self, bus):
        events = []
        bus.subscribe("rebuild.lpw_checkpoint.restored",
                       lambda e: events.append(e))
        cp = LPWCheckpoint(event_bus=bus)
        r = cp.create_checkpoint(label="ev-restore", trigger="auto")
        cp.restore_checkpoint(r["checkpoint_id"])
        assert len(events) == 1

    def test_verify_emits_event(self, bus):
        events = []
        bus.subscribe("rebuild.lpw_checkpoint.verified",
                       lambda e: events.append(e))
        cp = LPWCheckpoint(event_bus=bus)
        r = cp.create_checkpoint(label="ev-verify", trigger="auto")
        cp.verify_checkpoint(r["checkpoint_id"])
        assert len(events) == 1

    def test_prune_emits_event(self, bus):
        events = []
        bus.subscribe("rebuild.lpw_checkpoint.pruned",
                       lambda e: events.append(e))
        cp = LPWCheckpoint(event_bus=bus)
        for i in range(3):
            cp.create_checkpoint(label=f"prune-ev-{i}", trigger="auto")
        cp.prune_old_checkpoints(keep=1)
        assert len(events) == 1
        assert events[0].payload["removed_count"] == 2


# ===========================================================================
# 7. Hash determinism and integrity tests
# ===========================================================================

class TestHashIntegrity:
    """Tests for checkpoint hash computation."""

    def test_same_state_same_module_hash(self, cp_full):
        """Module snapshots are identical across checkpoints (event pos differs)."""
        _register_module(cp_full._registry, "mod.hash")
        r1 = cp_full.create_checkpoint(label="h1", trigger="auto")
        r2 = cp_full.create_checkpoint(label="h2", trigger="auto")
        # Module and contract data are identical
        assert r1["modules"] == r2["modules"]
        assert r1["contracts"] == r2["contracts"]
        # Hashes differ because event_position advances
        assert r1["snapshot_hash"] != r2["snapshot_hash"]

    def test_different_state_different_hash(self, cp_full):
        _register_module(cp_full._registry, "mod.diff")
        r1 = cp_full.create_checkpoint(label="h1", trigger="auto")
        # Change module state
        cp_full._registry.transition("mod.diff", ModuleLifecycleStage.BUILD)
        r2 = cp_full.create_checkpoint(label="h2", trigger="auto")
        assert r1["snapshot_hash"] != r2["snapshot_hash"]


# ===========================================================================
# 8. Singleton / get_lpw_checkpoint tests
# ===========================================================================

class TestSingleton:
    """Tests for get_lpw_checkpoint singleton."""

    def test_singleton_returns_same_instance(self):
        from sylion.rebuild import lpw_checkpoint
        # Reset singleton
        lpw_checkpoint._instance = None
        a = get_lpw_checkpoint()
        b = get_lpw_checkpoint()
        assert a is b
        # Cleanup
        lpw_checkpoint._instance = None
