"""Tests for sylion.core.auto_register -- module auto-registration from manifests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sylion.core.auto_register import auto_register_modules
from sylion.core.event_bus import EventBus
from sylion.core.module_registry import ModuleRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manifest(
    module_id: str = "core.test_mod",
    module_kind: str = "A",
    owner_plan: str = "P01",
    **overrides,
) -> dict:
    """Return a valid minimal manifest dict."""
    m = {
        "module_id": module_id,
        "module_kind": module_kind,
        "owner_plan": owner_plan,
        "description": "test module",
    }
    m.update(overrides)
    return m


def _write_manifests(tmp: Path, manifests: list[dict], names: list[str] | None = None):
    """Write manifest dicts as JSON files into *tmp*."""
    if names is None:
        names = [f"{m['module_id'].replace('.', '_')}.json" for m in manifests]
    for name, m in zip(names, manifests):
        (tmp / name).write_text(json.dumps(m), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def registry():
    return ModuleRegistry(db_path=":memory:")


@pytest.fixture()
def event_bus():
    return EventBus(db_path=":memory:")


@pytest.fixture()
def manifest_dir(tmp_path):
    return tmp_path / "manifests"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAutoRegisterFromManifests:
    """auto_register_modules loads JSON manifests and registers them."""

    def test_auto_register_from_manifests(self, registry, manifest_dir):
        manifest_dir.mkdir()
        _write_manifests(manifest_dir, [
            _make_manifest("core.alpha"),
            _make_manifest("cognitive.bravo", module_kind="B", owner_plan="P02"),
            _make_manifest("exec.charlie", module_kind="C", owner_plan="P03"),
        ])

        result = auto_register_modules(registry, manifest_dir)
        assert result["registered"] == 3
        assert result["skipped"] == 0
        assert result["errors"] == []

        assert registry.get("core.alpha") is not None
        assert registry.get("cognitive.bravo") is not None
        assert registry.get("exec.charlie") is not None

    def test_with_dependencies(self, registry, manifest_dir):
        """Modules with depends_on should register when deps are already present."""
        manifest_dir.mkdir()
        _write_manifests(manifest_dir, [
            _make_manifest("core.base"),
            _make_manifest("core.child", depends_on=["core.base"]),
        ],
        names=["01_base.json", "02_child.json"])

        result = auto_register_modules(registry, manifest_dir)
        # Both should register because base is processed first (sorted order).
        assert result["registered"] == 2
        assert result["errors"] == []

    def test_resolves_dependencies_across_passes(self, registry, manifest_dir):
        """Dependencies should not fail just because filenames sort child-first."""
        manifest_dir.mkdir()
        _write_manifests(
            manifest_dir,
            [
                _make_manifest("core.child", depends_on=["core.base"]),
                _make_manifest("core.base"),
            ],
            names=["01_child.json", "02_base.json"],
        )

        result = auto_register_modules(registry, manifest_dir)

        assert result["registered"] == 2
        assert result["skipped"] == 0
        assert result["errors"] == []
        assert registry.get("core.base") is not None
        assert registry.get("core.child") is not None


class TestSkipAlreadyRegistered:
    """Already-registered modules are silently skipped."""

    def test_skip_already_registered(self, registry, manifest_dir):
        manifest_dir.mkdir()
        _write_manifests(manifest_dir, [_make_manifest("core.dup")])

        # First pass registers.
        r1 = auto_register_modules(registry, manifest_dir)
        assert r1["registered"] == 1

        # Second pass skips.
        r2 = auto_register_modules(registry, manifest_dir)
        assert r2["registered"] == 0
        assert r2["skipped"] == 1

    def test_skip_pre_registered_in_registry(self, registry, manifest_dir):
        """Module registered outside auto_register should be skipped."""
        from sylion.core.module_registry import ModuleManifest, ModuleKind
        manifest_dir.mkdir()
        registry.register(ModuleManifest(
            module_id="core.pre",
            module_kind=ModuleKind.CORE_KERNEL,
            owner_plan="P01",
        ))
        _write_manifests(manifest_dir, [_make_manifest("core.pre")])

        result = auto_register_modules(registry, manifest_dir)
        assert result["registered"] == 0
        assert result["skipped"] == 1


class TestInvalidManifestSkipped:
    """Invalid manifests are logged as errors and do not halt registration."""

    def test_invalid_manifest_skipped(self, registry, manifest_dir):
        manifest_dir.mkdir()

        # Valid manifest
        _write_manifests(manifest_dir, [_make_manifest("core.ok")])

        # Invalid: missing module_id
        (manifest_dir / "bad1.json").write_text(
            json.dumps({"module_kind": "A", "owner_plan": "P01"}),
            encoding="utf-8",
        )

        # Invalid: not a dict (array)
        (manifest_dir / "bad2.json").write_text(
            json.dumps([1, 2, 3]), encoding="utf-8",
        )

        # Invalid: bad JSON
        (manifest_dir / "bad3.json").write_text("{broken", encoding="utf-8")

        # Invalid: bad enum value
        _write_manifests(manifest_dir, [
            _make_manifest("core.bad_enum", module_kind="Z"),
        ], names=["bad4.json"])

        result = auto_register_modules(registry, manifest_dir)
        assert result["registered"] == 1  # only core.ok
        assert len(result["errors"]) == 4  # bad1..bad4


class TestEmptyManifestDir:
    """Graceful handling of missing or empty manifest directories."""

    def test_empty_manifest_dir(self, registry, manifest_dir):
        manifest_dir.mkdir()
        result = auto_register_modules(registry, manifest_dir)
        assert result["registered"] == 0
        assert result["skipped"] == 0
        assert result["errors"] == []

    def test_missing_manifest_dir(self, registry, tmp_path):
        missing = tmp_path / "does_not_exist"
        result = auto_register_modules(registry, missing)
        assert result["registered"] == 0
        assert result["skipped"] == 0
        assert result["errors"] == []

    def test_manifest_dir_is_file(self, registry, tmp_path):
        file_path = tmp_path / "not_a_dir.json"
        file_path.write_text("{}", encoding="utf-8")
        result = auto_register_modules(registry, file_path)
        assert result["registered"] == 0
        assert result["errors"] == []


class TestAutoRegisterEmitsEvents:
    """module.auto_registered events are emitted for each newly registered module."""

    def test_auto_register_emits_events(self, registry, manifest_dir, event_bus):
        manifest_dir.mkdir()
        _write_manifests(manifest_dir, [
            _make_manifest("core.evt1"),
            _make_manifest("core.evt2"),
        ])

        captured: list = []
        event_bus.subscribe("module.auto_registered", captured.append)

        auto_register_modules(registry, manifest_dir, event_bus=event_bus)

        assert len(captured) == 2
        topics = [e.topic for e in captured]
        assert all(t == "module.auto_registered" for t in topics)

        ids = sorted(e.payload["module_id"] for e in captured)
        assert ids == ["core.evt1", "core.evt2"]

    def test_no_event_when_skipped(self, registry, manifest_dir, event_bus):
        manifest_dir.mkdir()
        _write_manifests(manifest_dir, [_make_manifest("core.skip_evt")])

        captured: list = []
        event_bus.subscribe("module.auto_registered", captured.append)

        # First call: registers + emits.
        auto_register_modules(registry, manifest_dir, event_bus=event_bus)
        assert len(captured) == 1

        # Second call: skips, no new event.
        auto_register_modules(registry, manifest_dir, event_bus=event_bus)
        assert len(captured) == 1  # still 1

    def test_no_event_bus(self, registry, manifest_dir):
        """Should work fine without an event_bus (None)."""
        manifest_dir.mkdir()
        _write_manifests(manifest_dir, [_make_manifest("core.no_bus")])
        result = auto_register_modules(registry, manifest_dir, event_bus=None)
        assert result["registered"] == 1
