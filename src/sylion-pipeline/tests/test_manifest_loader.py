"""Tests for sylion.core.manifest_loader module."""

import pytest

from sylion.core.manifest_loader import ManifestLoader
from sylion.core.module_registry import get_registry


class TestManifestLoader:
    @pytest.fixture
    def loader(self):
        return ManifestLoader(registry=get_registry())

    def test_load_dict_valid(self, loader):
        data = {"module_id": "test-mod", "module_kind": "A", "owner_plan": "P00"}
        result = loader.load_dict(data)
        assert result["module_id"] == "test-mod"

    def test_load_dict_missing_module_id(self, loader):
        with pytest.raises(ValueError, match="missing required field"):
            loader.load_dict({"module_kind": "A", "owner_plan": "P00"})

    def test_load_dict_missing_module_kind(self, loader):
        with pytest.raises(ValueError, match="missing required field"):
            loader.load_dict({"module_id": "m1", "owner_plan": "P00"})

    def test_load_dict_missing_owner_plan(self, loader):
        with pytest.raises(ValueError, match="missing required field"):
            loader.load_dict({"module_id": "m1", "module_kind": "A"})

    def test_load_dict_invalid_module_kind(self, loader):
        with pytest.raises(ValueError, match="invalid module_kind"):
            loader.load_dict({"module_id": "m1", "module_kind": "Z", "owner_plan": "P00"})

    def test_load_dict_not_dict(self, loader):
        with pytest.raises(ValueError, match="must be a dict"):
            loader.load_dict("not a dict")

    def test_load_dict_all_valid_kinds(self, loader):
        from sylion.core.module_registry import ModuleKind
        for kind in ModuleKind:
            data = {"module_id": f"mod-{kind.value}", "module_kind": kind.value, "owner_plan": "P00"}
            result = loader.load_dict(data)
            assert result["module_kind"] == kind.value

    def test_load_dict_extra_fields_ok(self, loader):
        data = {"module_id": "m1", "module_kind": "A", "owner_plan": "P00", "extra": "val"}
        result = loader.load_dict(data)
        assert result["extra"] == "val"

    def test_loader_with_default_registry(self):
        loader = ManifestLoader()
        assert loader._registry is not None
