"""Tests for SYLION Rebuild — Rebuildability Framework.

Covers: snapshot, rebuild plan, fidelity verification, CFT run,
rebuild history, rebuildability check, edge cases, event emission,
thread safety, contracts integration.
"""
import json
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.module_registry import ModuleManifest, ModuleKind, ModuleRegistry
from sylion.rebuild.rebuildability_framework import (
    FIDELITY_THRESHOLD,
    RebuildabilityFramework,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def registry():
    reg = ModuleRegistry()
    reg.register(ModuleManifest(
        module_id="core.kernel", module_kind=ModuleKind.CORE_KERNEL,
        owner_plan="P01", description="Core kernel",
    ))
    reg.register(ModuleManifest(
        module_id="memory.store", module_kind=ModuleKind.MEMORY,
        owner_plan="P04", description="Memory store",
        depends_on=["core.kernel"],
    ))
    reg.register(ModuleManifest(
        module_id="cognitive.engine", module_kind=ModuleKind.COGNITIVE,
        owner_plan="P02", description="Cognitive engine",
        depends_on=["core.kernel", "memory.store"],
    ))
    return reg


@pytest.fixture
def fw(registry, bus):
    return RebuildabilityFramework(registry=registry, event_bus=bus)


@pytest.fixture
def fw_no_bus(registry):
    return RebuildabilityFramework(registry=registry, event_bus=None)


@pytest.fixture
def fw_no_registry(bus):
    return RebuildabilityFramework(registry=None, event_bus=bus)


@pytest.fixture
def fw_with_contracts(registry, bus):
    from sylion.core.contract_registry import Contract, ContractRegistry
    cr = ContractRegistry(event_bus=bus)
    cr.publish(Contract(
        name="kernel.api", version="1.0.0", producer_module="core.kernel",
        description="Kernel API contract",
    ))
    cr.publish(Contract(
        name="memory.api", version="2.1.0", producer_module="memory.store",
        description="Memory API contract",
    ))
    return RebuildabilityFramework(
        registry=registry, event_bus=bus, contract_registry=cr,
    )


# ---------------------------------------------------------------------------
# 1. Initialization
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_with_defaults(self, registry):
        fw = RebuildabilityFramework(registry=registry)
        assert fw._db_path == ":memory:"
        assert fw._event_bus is None
        assert fw._registry is registry

    def test_tables_created(self, fw):
        tables = fw._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "rebuild_snapshots" in names
        assert "rebuild_history" in names
        assert "rebuild_plans" in names


# ---------------------------------------------------------------------------
# 2. Snapshot
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_snapshot_returns_required_fields(self, fw):
        snap = fw.snapshot_system_state()
        for key in ("snapshot_id", "snapshot_hash", "modules", "contracts",
                     "events", "decisions", "timestamp"):
            assert key in snap

    def test_snapshot_counts_modules(self, fw):
        snap = fw.snapshot_system_state()
        assert snap["modules"] == 3

    def test_snapshot_hash_changes_on_state_change(self, fw, registry):
        snap1 = fw.snapshot_system_state()
        registry.register(ModuleManifest(
            module_id="security.auth", module_kind=ModuleKind.SECURITY,
            owner_plan="P09",
        ))
        snap2 = fw.snapshot_system_state()
        assert snap1["snapshot_hash"] != snap2["snapshot_hash"]

    def test_snapshot_persisted_and_retrievable(self, fw):
        snap = fw.snapshot_system_state()
        loaded = fw.get_snapshot(snap["snapshot_id"])
        assert loaded is not None
        assert loaded["snapshot_hash"] == snap["snapshot_hash"]
        assert len(loaded["modules"]) == 3

    def test_snapshot_nonexistent_returns_none(self, fw):
        assert fw.get_snapshot("nonexistent") is None

    def test_snapshot_empty_system(self, fw_no_registry):
        snap = fw_no_registry.snapshot_system_state()
        assert snap["modules"] == 0
        assert snap["contracts"] == 0
        assert snap["events"] == 0
        assert snap["decisions"] == 0


# ---------------------------------------------------------------------------
# 3. Rebuild plan
# ---------------------------------------------------------------------------

class TestRebuildPlan:
    def test_generates_plan_with_steps(self, fw):
        plan = fw.generate_rebuild_plan()
        assert "plan_id" in plan
        assert len(plan["steps"]) == 3

    def test_topological_order(self, fw):
        plan = fw.generate_rebuild_plan()
        ids = [s["module_id"] for s in plan["steps"]]
        assert ids.index("core.kernel") < ids.index("memory.store")
        assert ids.index("memory.store") < ids.index("cognitive.engine")

    def test_step_fields(self, fw):
        plan = fw.generate_rebuild_plan()
        step = plan["steps"][0]
        for key in ("order", "module_id", "dependencies", "contract_version", "action"):
            assert key in step

    def test_plan_persisted(self, fw):
        plan = fw.generate_rebuild_plan()
        row = fw._conn.execute(
            "SELECT * FROM rebuild_plans WHERE plan_id = ?", (plan["plan_id"],),
        ).fetchone()
        assert row is not None
        assert len(json.loads(row["steps_json"])) == 3

    def test_plan_empty_system(self, fw_no_registry):
        plan = fw_no_registry.generate_rebuild_plan()
        assert plan["steps"] == []


# ---------------------------------------------------------------------------
# 4. Fidelity verification
# ---------------------------------------------------------------------------

class TestFidelityVerification:
    def test_identical_snapshots_perfect_fidelity(self, fw):
        snap1 = fw.snapshot_system_state()
        snap2 = fw.snapshot_system_state()
        result = fw.verify_rebuild(snap1, snap2)
        assert result["fidelity"] == 1.0
        assert result["passed"] is True

    def test_different_state_reduces_fidelity(self, fw, registry):
        snap1 = fw.snapshot_system_state()
        registry.register(ModuleManifest(
            module_id="security.auth", module_kind=ModuleKind.SECURITY,
            owner_plan="P09",
        ))
        snap2 = fw.snapshot_system_state()
        result = fw.verify_rebuild(snap1, snap2)
        assert result["fidelity"] < 1.0

    def test_verification_records_history(self, fw):
        snap = fw.snapshot_system_state()
        fw.verify_rebuild(snap, snap)
        history = fw.get_rebuild_history()
        assert len(history) == 1
        assert history[0]["fidelity"] == 1.0

    def test_verification_result_fields(self, fw):
        snap = fw.snapshot_system_state()
        result = fw.verify_rebuild(snap, snap)
        for key in ("fidelity", "module_match", "contract_match",
                     "event_match", "passed"):
            assert key in result


# ---------------------------------------------------------------------------
# 5. CFT run
# ---------------------------------------------------------------------------

class TestCFTRun:
    def test_cft_perfect_system_passes(self, fw):
        result = fw.run_cft()
        assert result["fidelity"] >= FIDELITY_THRESHOLD
        assert result["passed"] is True

    def test_cft_creates_auto_and_rebuilt_snapshots(self, fw):
        fw.run_cft()
        rows = fw._conn.execute(
            "SELECT label, COUNT(*) as cnt FROM rebuild_snapshots GROUP BY label"
        ).fetchall()
        labels = {r["label"]: r["cnt"] for r in rows}
        assert "auto" in labels
        assert "rebuilt" in labels

    def test_cft_empty_system(self, fw_no_registry):
        result = fw_no_registry.run_cft()
        assert result["fidelity"] == 1.0
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# 6. Rebuild history
# ---------------------------------------------------------------------------

class TestRebuildHistory:
    def test_history_starts_empty(self, fw):
        assert fw.get_rebuild_history() == []

    def test_history_grows(self, fw):
        snap = fw.snapshot_system_state()
        fw.verify_rebuild(snap, snap)
        fw.verify_rebuild(snap, snap)
        assert len(fw.get_rebuild_history()) == 2

    def test_history_ordered_desc(self, fw):
        snap = fw.snapshot_system_state()
        fw.verify_rebuild(snap, snap)
        time.sleep(0.01)
        fw.verify_rebuild(snap, snap)
        history = fw.get_rebuild_history()
        assert history[0]["timestamp"] >= history[1]["timestamp"]


# ---------------------------------------------------------------------------
# 7. Full rebuildability check
# ---------------------------------------------------------------------------

class TestRebuildabilityCheck:
    def test_check_returns_all_fields(self, fw):
        result = fw.check_rebuildability()
        for key in ("rebuildable", "manifests_valid", "contracts_frozen",
                     "cft_passed", "cft_fidelity", "issues"):
            assert key in result

    def test_valid_system_is_rebuildable(self, fw):
        result = fw.check_rebuildability()
        assert result["manifests_valid"] is True
        assert result["rebuildable"] is True

    def test_empty_system_rebuildable(self, fw_no_registry):
        result = fw_no_registry.check_rebuildability()
        assert result["rebuildable"] is True

    def test_with_contracts_rebuildable(self, fw_with_contracts):
        result = fw_with_contracts.check_rebuildability()
        assert result["rebuildable"] is True


# ---------------------------------------------------------------------------
# 8. Event emission
# ---------------------------------------------------------------------------

class TestEvents:
    def test_snapshot_emits_event(self, fw, bus):
        received = []
        bus.subscribe("rebuild.snapshot_captured", lambda e: received.append(e))
        fw.snapshot_system_state()
        assert len(received) == 1

    def test_plan_emits_event(self, fw, bus):
        received = []
        bus.subscribe("rebuild.plan_generated", lambda e: received.append(e))
        fw.generate_rebuild_plan()
        assert len(received) == 1

    def test_cft_emits_event(self, fw, bus):
        received = []
        bus.subscribe("rebuild.cft_completed", lambda e: received.append(e))
        fw.run_cft()
        assert len(received) == 1

    def test_no_bus_no_error(self, fw_no_bus):
        snap = fw_no_bus.snapshot_system_state()
        assert snap is not None
        result = fw_no_bus.run_cft()
        assert result is not None


# ---------------------------------------------------------------------------
# 9. Fidelity edge cases
# ---------------------------------------------------------------------------

class TestFidelityEdgeCases:
    def test_empty_sets_fidelity_1(self):
        assert RebuildabilityFramework._compute_set_fidelity(set(), set()) == 1.0

    def test_one_empty_fidelity_0(self):
        assert RebuildabilityFramework._compute_set_fidelity({"a"}, set()) == 0.0

    def test_partial_overlap(self):
        result = RebuildabilityFramework._compute_set_fidelity(
            {"a", "b", "c"}, {"a", "b", "d"},
        )
        assert result == 0.5

    def test_hash_deterministic(self):
        h1 = RebuildabilityFramework._compute_snapshot_hash([{"module_id": "x"}], [], [], [])
        h2 = RebuildabilityFramework._compute_snapshot_hash([{"module_id": "x"}], [], [], [])
        assert h1 == h2

    def test_hash_different_for_different_data(self):
        h1 = RebuildabilityFramework._compute_snapshot_hash([{"module_id": "a"}], [], [], [])
        h2 = RebuildabilityFramework._compute_snapshot_hash([{"module_id": "b"}], [], [], [])
        assert h1 != h2


# ---------------------------------------------------------------------------
# 10. Contracts integration
# ---------------------------------------------------------------------------

class TestContractIntegration:
    def test_snapshot_includes_contracts(self, fw_with_contracts):
        snap = fw_with_contracts.snapshot_system_state()
        full = fw_with_contracts.get_snapshot(snap["snapshot_id"])
        assert len(full["contracts"]) == 2

    def test_cft_with_contracts_passes(self, fw_with_contracts):
        result = fw_with_contracts.run_cft()
        assert result["passed"] is True
        assert result["fidelity"] >= FIDELITY_THRESHOLD

    def test_plan_contract_versions(self, fw_with_contracts):
        plan = fw_with_contracts.generate_rebuild_plan()
        kernel_step = next(
            s for s in plan["steps"] if s["module_id"] == "core.kernel"
        )
        assert kernel_step["contract_version"] == "1.0.0"


# ---------------------------------------------------------------------------
# 11. Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_snapshots(self, fw, tmp_path):
        errors = []
        results = []

        def take_snapshot(idx):
            try:
                fw_local = RebuildabilityFramework(
                    registry=fw._registry, event_bus=None,
                    db_path=str(tmp_path / f"snap_{idx}.db"),
                )
                results.append(fw_local.snapshot_system_state())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=take_snapshot, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10

    def test_concurrent_cft_runs(self, fw, tmp_path):
        errors = []
        results = []

        def run_cft(idx):
            try:
                fw_local = RebuildabilityFramework(
                    registry=fw._registry, event_bus=None,
                    db_path=str(tmp_path / f"cft_{idx}.db"),
                )
                results.append(fw_local.run_cft())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run_cft, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5
        for r in results:
            assert r["passed"] is True
