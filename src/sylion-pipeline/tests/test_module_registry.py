"""
Comprehensive tests for sylion.core.module_registry — ModuleRegistry class.
Tests: register, get, list_modules, transition, deregister, heartbeat, edge cases.
"""
from __future__ import annotations

import time
import threading

import pytest

from sylion.core.module_registry import (
    ModuleRegistry,
    ModuleManifest,
    ModuleKind,
    ModuleLifecycleStage,
    SecurityProfile,
    _VALID_TRANSITIONS,
    get_registry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _registry() -> ModuleRegistry:
    return ModuleRegistry()


def _manifest(module_id: str = "mod.test", kind: ModuleKind = ModuleKind.CORE_KERNEL,
              owner_plan: str = "P01", **kwargs) -> ModuleManifest:
    return ModuleManifest(
        module_id=module_id,
        module_kind=kind,
        owner_plan=owner_plan,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# ModuleKind enum
# ---------------------------------------------------------------------------

class TestModuleKind:

    def test_kind_values_are_single_letters(self):
        for kind in ModuleKind:
            assert len(kind.value) == 1
            assert kind.value.isupper() or kind.value.isalpha()

    def test_all_kinds_a_through_o(self):
        values = {k.value for k in ModuleKind}
        assert values == set("ABCDEFGHIJKLMNO")


# ---------------------------------------------------------------------------
# ModuleLifecycleStage enum
# ---------------------------------------------------------------------------

class TestModuleLifecycleStage:

    def test_stages_exist(self):
        expected = {"draft", "build", "validate", "shadow", "dual", "cutover", "stable", "deprecated"}
        actual = {s.value for s in ModuleLifecycleStage}
        assert actual == expected


# ---------------------------------------------------------------------------
# ModuleManifest dataclass
# ---------------------------------------------------------------------------

class TestModuleManifest:

    def test_required_fields(self):
        m = ModuleManifest(module_id="x", module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01")
        assert m.module_id == "x"
        assert m.module_kind == ModuleKind.CORE_KERNEL
        assert m.owner_plan == "P01"

    def test_defaults(self):
        m = _manifest()
        assert m.lifecycle_stage == ModuleLifecycleStage.DRAFT
        assert m.version == "1.0.0"
        assert m.milestone == "M0"
        assert m.security_profile == SecurityProfile.DEV_LIGHT
        assert m.depends_on == []
        assert m.description == ""

    def test_to_dict(self):
        m = _manifest(module_id="dict.test", description="hello", milestone="M3")
        d = m.to_dict()
        assert d["module_id"] == "dict.test"
        assert d["module_kind"] == "A"
        assert d["description"] == "hello"
        assert d["milestone"] == "M3"
        assert d["lifecycle_stage"] == "draft"


# ---------------------------------------------------------------------------
# Valid transitions table
# ---------------------------------------------------------------------------

class TestValidTransitions:

    def test_draft_can_go_to_build(self):
        assert ModuleLifecycleStage.BUILD in _VALID_TRANSITIONS[ModuleLifecycleStage.DRAFT]

    def test_deprecated_has_no_transitions(self):
        assert len(_VALID_TRANSITIONS[ModuleLifecycleStage.DEPRECATED]) == 0

    def test_stable_can_go_to_deprecated(self):
        assert ModuleLifecycleStage.DEPRECATED in _VALID_TRANSITIONS[ModuleLifecycleStage.STABLE]


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

class TestRegister:

    def test_register_returns_dict(self):
        reg = _registry()
        result = reg.register(_manifest(module_id="reg.test"))
        assert result["module_id"] == "reg.test"
        assert result["lifecycle_stage"] == "draft"

    def test_register_duplicate_raises(self):
        reg = _registry()
        reg.register(_manifest(module_id="dup.mod"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_manifest(module_id="dup.mod"))

    def test_register_with_missing_dependency_raises(self):
        reg = _registry()
        m = _manifest(module_id="dep.child", depends_on=["nonexistent"])
        with pytest.raises(ValueError, match="Dependency nonexistent not registered"):
            reg.register(m)

    def test_register_with_satisfied_dependency(self):
        reg = _registry()
        reg.register(_manifest(module_id="dep.parent"))
        m = _manifest(module_id="dep.child", depends_on=["dep.parent"])
        result = reg.register(m)
        assert result["module_id"] == "dep.child"

    def test_register_emits_callback(self):
        reg = _registry()
        events = []
        reg.on_event(lambda et, p: events.append((et, p)))
        reg.register(_manifest(module_id="cb.mod"))
        assert len(events) == 1
        assert events[0][0] == "module.registered"
        assert events[0][1]["module_id"] == "cb.mod"

    def test_register_sets_timestamps(self):
        reg = _registry()
        before = time.time()
        reg.register(_manifest(module_id="ts.mod"))
        row = reg.get("ts.mod")
        assert row["registered_at"] >= before
        assert row["last_heartbeat"] >= before


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------

class TestGet:

    def test_get_existing(self):
        reg = _registry()
        reg.register(_manifest(module_id="get.mod"))
        result = reg.get("get.mod")
        assert result is not None
        assert result["module_id"] == "get.mod"

    def test_get_nonexistent_returns_none(self):
        reg = _registry()
        assert reg.get("no.such.module") is None

    def test_get_returns_all_fields(self):
        reg = _registry()
        reg.register(_manifest(module_id="fields.mod", description="desc", version="2.0.0"))
        row = reg.get("fields.mod")
        assert "module_id" in row
        assert "module_kind" in row
        assert "description" in row
        assert row["description"] == "desc"
        assert row["version"] == "2.0.0"


# ---------------------------------------------------------------------------
# list_modules
# ---------------------------------------------------------------------------

class TestListModules:

    def test_list_all(self):
        reg = _registry()
        reg.register(_manifest(module_id="list.a"))
        reg.register(_manifest(module_id="list.b"))
        assert len(reg.list_modules()) == 2

    def test_list_empty(self):
        reg = _registry()
        assert reg.list_modules() == []

    def test_list_filter_by_kind(self):
        reg = _registry()
        reg.register(_manifest(module_id="k.a", kind=ModuleKind.CORE_KERNEL))
        reg.register(_manifest(module_id="k.b", kind=ModuleKind.SECURITY))
        results = reg.list_modules(kind="A")
        assert len(results) == 1
        assert results[0]["module_id"] == "k.a"

    def test_list_filter_by_milestone(self):
        reg = _registry()
        reg.register(_manifest(module_id="ms.a", milestone="M3"))
        reg.register(_manifest(module_id="ms.b", milestone="M1"))
        results = reg.list_modules(milestone="M3")
        assert len(results) == 1

    def test_list_filter_by_lifecycle(self):
        reg = _registry()
        reg.register(_manifest(module_id="lc.a"))
        results = reg.list_modules(lifecycle="draft")
        assert len(results) == 1

    def test_list_combined_filters(self):
        reg = _registry()
        reg.register(_manifest(module_id="cf.a", kind=ModuleKind.CORE_KERNEL))
        reg.register(_manifest(module_id="cf.b", kind=ModuleKind.SECURITY))
        results = reg.list_modules(kind="A", lifecycle="draft")
        assert len(results) == 1
        assert results[0]["module_id"] == "cf.a"

    def test_list_ordered_by_module_id(self):
        reg = _registry()
        reg.register(_manifest(module_id="z.mod"))
        reg.register(_manifest(module_id="a.mod"))
        results = reg.list_modules()
        assert results[0]["module_id"] == "a.mod"
        assert results[1]["module_id"] == "z.mod"


# ---------------------------------------------------------------------------
# Transition
# ---------------------------------------------------------------------------

class TestTransition:

    def test_valid_transition(self):
        reg = _registry()
        reg.register(_manifest(module_id="tr.mod"))
        result = reg.transition("tr.mod", ModuleLifecycleStage.BUILD)
        assert result["lifecycle"] == "build"

    def test_invalid_transition_raises(self):
        reg = _registry()
        reg.register(_manifest(module_id="inv.mod"))
        with pytest.raises(ValueError, match="Invalid"):
            reg.transition("inv.mod", ModuleLifecycleStage.STABLE)

    def test_transition_nonexistent_raises(self):
        reg = _registry()
        with pytest.raises(ValueError, match="not found"):
            reg.transition("ghost", ModuleLifecycleStage.BUILD)

    def test_full_lifecycle_path(self):
        reg = _registry()
        reg.register(_manifest(module_id="full.lc"))
        stages = [
            ModuleLifecycleStage.BUILD,
            ModuleLifecycleStage.VALIDATE,
            ModuleLifecycleStage.SHADOW,
            ModuleLifecycleStage.DUAL,
            ModuleLifecycleStage.CUTOVER,
            ModuleLifecycleStage.STABLE,
        ]
        for stage in stages:
            reg.transition("full.lc", stage)
        assert reg.get("full.lc")["lifecycle"] == "stable"

    def test_transition_emits_callback(self):
        reg = _registry()
        events = []
        reg.on_event(lambda et, p: events.append((et, p)))
        reg.register(_manifest(module_id="cb.tr"))
        reg.transition("cb.tr", ModuleLifecycleStage.BUILD)
        assert any(e[0] == "module.lifecycle.transition" for e in events)
        trans_events = [e for e in events if e[0] == "module.lifecycle.transition"]
        assert trans_events[0][1]["from"] == "draft"
        assert trans_events[0][1]["to"] == "build"

    def test_deprecated_no_transitions(self):
        reg = _registry()
        reg.register(_manifest(module_id="dep.mod"))
        stages = [
            ModuleLifecycleStage.BUILD,
            ModuleLifecycleStage.VALIDATE,
            ModuleLifecycleStage.SHADOW,
            ModuleLifecycleStage.DUAL,
            ModuleLifecycleStage.CUTOVER,
            ModuleLifecycleStage.STABLE,
            ModuleLifecycleStage.DEPRECATED,
        ]
        for s in stages:
            reg.transition("dep.mod", s)
        with pytest.raises(ValueError, match="Invalid"):
            reg.transition("dep.mod", ModuleLifecycleStage.BUILD)

    def test_rollback_transition(self):
        reg = _registry()
        reg.register(_manifest(module_id="rb.mod"))
        reg.transition("rb.mod", ModuleLifecycleStage.BUILD)
        reg.transition("rb.mod", ModuleLifecycleStage.VALIDATE)
        # rollback to BUILD
        reg.transition("rb.mod", ModuleLifecycleStage.BUILD)
        assert reg.get("rb.mod")["lifecycle"] == "build"


# ---------------------------------------------------------------------------
# Deregister
# ---------------------------------------------------------------------------

class TestDeregister:

    def test_deregister_existing(self):
        reg = _registry()
        reg.register(_manifest(module_id="del.mod"))
        result = reg.deregister("del.mod")
        assert result is True
        assert reg.get("del.mod") is None

    def test_deregister_nonexistent(self):
        reg = _registry()
        result = reg.deregister("ghost")
        assert result is False

    def test_deregister_with_dependents_raises(self):
        reg = _registry()
        reg.register(_manifest(module_id="parent.mod"))
        reg.register(_manifest(module_id="child.mod", depends_on=["parent.mod"]))
        with pytest.raises(ValueError, match="Cannot deregister"):
            reg.deregister("parent.mod")

    def test_deregister_emits_callback(self):
        reg = _registry()
        events = []
        reg.on_event(lambda et, p: events.append((et, p)))
        reg.register(_manifest(module_id="cb.del"))
        reg.deregister("cb.del")
        assert any(e[0] == "module.deregistered" for e in events)


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

class TestHeartbeat:

    def test_heartbeat_updates_timestamp(self):
        reg = _registry()
        reg.register(_manifest(module_id="hb.mod"))
        before = reg.get("hb.mod")["last_heartbeat"]
        time.sleep(0.01)
        reg.heartbeat("hb.mod")
        after = reg.get("hb.mod")["last_heartbeat"]
        assert after > before

    def test_heartbeat_nonexistent_no_crash(self):
        reg = _registry()
        reg.heartbeat("ghost")  # should not raise


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_registry_returns_instance(self):
        import sylion.core.module_registry as mod
        mod._registry = None
        reg = get_registry()
        assert isinstance(reg, ModuleRegistry)
        mod._registry = None


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_register(self):
        reg = _registry()
        errors = []

        def register_n(n):
            try:
                reg.register(_manifest(module_id=f"concurrent.{n}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_n, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(reg.list_modules()) == 20
