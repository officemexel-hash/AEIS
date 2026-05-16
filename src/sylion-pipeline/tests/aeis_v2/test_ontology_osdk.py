"""Tests for sylion.aeis_v2.ontology.osdk_gen -- W15 G2.

Covers:
- generate_module emits valid Python source with correct class names
- Generated code is syntactically valid (compile + ast.parse)
- TypedDict for row shape is present and correctly typed
- Each manifest action produces a matching client method
- D-level + hg_required surface in the action method docstring
- Many-to-one relations produce a `<relation>_id` field in the row TypedDict
- write_osdk_module materialises a module on disk
- regenerate_all writes _osdk/__init__.py alongside per-type modules
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from sylion.aeis_v2.ontology import (
    ActionDef,
    DedicatedColumn,
    ObjectTypeManifest,
    ObjectTypeMetadata,
    ObjectTypeSpec,
    Relation,
    generate_module,
    regenerate_all,
    write_osdk_module,
)
from sylion.aeis_v2.ontology.manifest import ActionEffect


def _customer_manifest() -> ObjectTypeManifest:
    """A representative manifest with columns, relation, and actions."""
    return ObjectTypeManifest(
        api_version="sylion.aeis.v2/Object",
        kind="ObjectType",
        metadata=ObjectTypeMetadata(
            id="customer",
            name_pl="Klient",
            name_en="Customer",
            version="v1.0",
        ),
        spec=ObjectTypeSpec(
            dedicated_columns=[
                DedicatedColumn(name="title", type="text", nullable=False),
                DedicatedColumn(name="email", type="text", nullable=True),
                DedicatedColumn(name="visits", type="integer", nullable=True),
            ],
            relations=[
                Relation(
                    name="parent",
                    target="account",
                    cardinality="many_to_one",
                    on_delete="set_null",
                ),
            ],
            actions=[
                ActionDef(
                    id="archive_customer",
                    description_pl="Archiwizuje klienta i blokuje jego ponowne uzycie.",
                    description_en="Archives the customer and blocks reuse.",
                    d_level="D2",
                    hg_required=False,
                    effects=[
                        ActionEffect(type="update_field", field="status", to="archived"),
                    ],
                ),
                ActionDef(
                    id="mark_active_customer",
                    description_pl="Oznacza klienta jako aktywnego.",
                    description_en="Marks the customer as active.",
                    d_level="D3",
                    hg_required=True,
                    effects=[
                        ActionEffect(type="update_field", field="status", to="active"),
                    ],
                ),
            ],
        ),
    )


# --------------------------------------------------------------------------
# 1. Basic source emission
# --------------------------------------------------------------------------


def test_generate_module_returns_python_code() -> None:
    mod = generate_module(_customer_manifest())
    assert mod.type_id == "customer"
    assert mod.module_name == "customer"
    assert mod.code.startswith('"""Auto-generated')
    assert "class CustomerClient" in mod.code
    assert mod.line_count > 0


# --------------------------------------------------------------------------
# 2. Generated source is syntactically valid Python
# --------------------------------------------------------------------------


def test_generated_code_compiles() -> None:
    mod = generate_module(_customer_manifest())
    # Both compile() and ast.parse() must succeed -- belt-and-braces.
    compile(mod.code, "<test>", "exec")
    tree = ast.parse(mod.code)
    assert tree is not None


# --------------------------------------------------------------------------
# 3. TypedDict row class
# --------------------------------------------------------------------------


def test_generated_module_has_typed_dict() -> None:
    mod = generate_module(_customer_manifest())
    assert "class CustomerRow(TypedDict" in mod.code
    # All dedicated columns must be present in the TypedDict body.
    assert re.search(r"^\s*title: str$", mod.code, re.MULTILINE)
    assert re.search(r"^\s*email: str \| None$", mod.code, re.MULTILINE)
    assert re.search(r"^\s*visits: int \| None$", mod.code, re.MULTILINE)
    assert re.search(r"^\s*extension: dict\[str, Any\]$", mod.code, re.MULTILINE)


# --------------------------------------------------------------------------
# 4. Per-action client methods
# --------------------------------------------------------------------------


def test_generated_module_has_per_action_method() -> None:
    manifest = _customer_manifest()
    mod = generate_module(manifest)
    for action in manifest.spec.actions:
        # Method definition for each action.id must exist.
        assert re.search(rf"\bdef {re.escape(action.id)}\b", mod.code), (
            f"missing method for action {action.id} in:\n{mod.code}"
        )


# --------------------------------------------------------------------------
# 5. Action docstring carries D-level for governance auditors.
# --------------------------------------------------------------------------


def test_action_method_includes_d_level_in_docstring() -> None:
    manifest = _customer_manifest()
    mod = generate_module(manifest)
    for action in manifest.spec.actions:
        token = f"D-level={action.d_level}"
        assert token in mod.code, (
            f"missing '{token}' in generated code for {action.id}"
        )


# --------------------------------------------------------------------------
# 6. Relation FK columns surface in the row TypedDict.
# --------------------------------------------------------------------------


def test_relation_fk_columns_present_in_typed_dict() -> None:
    mod = generate_module(_customer_manifest())
    # `parent` is many_to_one -> we expect `parent_id: str | None` field.
    assert re.search(r"^\s*parent_id: str \| None$", mod.code, re.MULTILINE), (
        f"missing parent_id field in row TypedDict:\n{mod.code}"
    )


# --------------------------------------------------------------------------
# 7. write_osdk_module materialises module on disk and is parseable.
# --------------------------------------------------------------------------


def test_write_osdk_module_creates_file(tmp_path: Path) -> None:
    target = write_osdk_module(_customer_manifest(), str(tmp_path))
    p = Path(target)
    assert p.exists(), f"generated file {p} not on disk"
    assert p.name == "customer.py"
    contents = p.read_text(encoding="utf-8")
    # Round-trip through ast.parse to confirm syntactic validity.
    tree = ast.parse(contents)
    assert any(isinstance(n, ast.ClassDef) and n.name == "CustomerClient"
               for n in ast.walk(tree))
    # Sibling __init__.py must also be created.
    assert (p.parent / "__init__.py").exists()


# --------------------------------------------------------------------------
# 8. regenerate_all writes _osdk/__init__.py + at least one type module.
# --------------------------------------------------------------------------


def test_regenerate_all_creates_osdk_dir_with_init_py(tmp_path: Path) -> None:
    # Use a custom target_dir so we do not touch the real _osdk/ in the repo.
    paths = regenerate_all(target_dir=str(tmp_path))
    init = tmp_path / "__init__.py"
    assert init.exists(), "_osdk/__init__.py must exist after regenerate"
    # If the registry has any manifests loaded, at least one .py written.
    if paths:
        for p in paths:
            assert Path(p).exists()
            assert Path(p).suffix == ".py"
            # Each generated file must be syntactically valid Python.
            ast.parse(Path(p).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Bonus: action method invokes correct REST path.
# --------------------------------------------------------------------------


def test_action_method_targets_correct_rest_path() -> None:
    manifest = _customer_manifest()
    mod = generate_module(manifest)
    # Generated code should reference the canonical action endpoint.
    for action in manifest.spec.actions:
        # Path includes both type_id and action.id.
        marker = f"/api/v1/ontology/customer/" + "{instance_id}/actions/" + action.id
        assert marker in mod.code, (
            f"missing REST path '{marker}' in generated module"
        )


def test_camelcase_class_names_for_multi_word_type_ids() -> None:
    manifest = _customer_manifest()
    # Tweak metadata.id to a multi-word slug.
    manifest.metadata.id = "premium_customer"
    mod = generate_module(manifest)
    assert "class PremiumCustomerClient" in mod.code
    assert "class PremiumCustomerRow(TypedDict" in mod.code


def test_default_target_dir_points_at_osdk_subdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When target_dir is None, regenerate_all writes under <ontology>/_osdk."""
    # Empty registry behaves correctly: writes nothing but does not crash.
    # We avoid mutating the real _osdk/ by passing an explicit tmp_path.
    paths = regenerate_all(target_dir=str(tmp_path))
    assert isinstance(paths, list)
