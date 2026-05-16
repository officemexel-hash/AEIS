"""Tests for sylion.aeis_v2.ontology compiler + registry."""
from __future__ import annotations

import pytest
import yaml
from pathlib import Path

from sylion.aeis_v2.ontology import (
    ActionDef, AuditConfig, DedicatedColumn, JsonbExtension,
    ManifestValidationError, ObjectTypeManifest, ObjectTypeMetadata,
    ObjectTypeSpec, Relation, SearchConfig,
    compile_to_ddl, explain_actions, get_registry,
    load_manifest, load_manifest_dir,
)
from sylion.aeis_v2.ontology.compiler import SchemaCompiler


def _minimal_manifest(type_id="customer"):
    return ObjectTypeManifest(
        api_version="sylion.aeis.v2/Object",
        kind="ObjectType",
        metadata=ObjectTypeMetadata(
            id=type_id,
            name_pl="Klient",
            name_en="Customer",
        ),
        spec=ObjectTypeSpec(
            dedicated_columns=[
                DedicatedColumn(name="title", type="text", nullable=False),
nullable=False),
            ],
        ),
    )


def _write_manifest(tmp_path: Path, manifest: ObjectTypeManifest, filename:
filename: str = "m.yaml"):
    path = tmp_path / filename
    path.write_text(yaml.safe_dump(manifest.model_dump()))
    return path


@pytest.mark.parametrize("test_case", [
    ("minimal", _minimal_manifest()),
    ("reserved_id", ObjectTypeManifest(
        api_version="sylion.aeis.v2/Object",
        kind="ObjectType",
        metadata=ObjectTypeMetadata(
            id="foo",
            name_pl="Foo",
            name_en="Foo",
        ),
        spec=ObjectTypeSpec(
            dedicated_columns=[
                DedicatedColumn(name="id", type="text", nullable=False),
            ],
        ),
    )),
])
def test_minimal_manifest_loads(test_case):
    _, manifest = test_case
    assert isinstance(manifest, ObjectTypeManifest)


def test_manifest_rejects_wrong_api_version():
    with pytest.raises(ValueError):
        ObjectTypeManifest(
            api_version="wrong",
            kind="ObjectType",
            metadata=ObjectTypeMetadata(id="x", name_pl="x", name_en="x"),
            spec=ObjectTypeSpec(dedicated_columns=[]),
        )


def test_manifest_rejects_wrong_kind():
    with pytest.raises(ValueError):
        ObjectTypeManifest(
            api_version="sylion.aeis.v2/Object",
            kind="WrongKind",
            metadata=ObjectTypeMetadata(id="x", name_pl="x", name_en="x"),
            spec=ObjectTypeSpec(dedicated_columns=[]),
        )


def test_column_name_must_be_slug():
    with pytest.raises(ValueError):
        DedicatedColumn(name="Bad-Name", type="text", nullable=False)


def test_column_name_reserved_id():
    with pytest.raises(ValueError):
        DedicatedColumn(name="id", type="text", nullable=False)


def test_column_type_must_be_supported():
    with pytest.raises(ValueError):
        DedicatedColumn(name="c", type="varchar", nullable=False)


def test_relation_target_required():
    with pytest.raises(ValueError):
        Relation(name="foo")


def test_relation_cardinality_validated():
    with pytest.raises(ValueError):
        Relation(name="foo", target="bar", cardinality="invalid")


def test_relation_fk_clashes_with_dedicated_column(tmp_path: Path):
    manifest = ObjectTypeManifest(
        api_version="sylion.aeis.v2/Object",
        kind="ObjectType",
        metadata=ObjectTypeMetadata(id="x", name_pl="x", name_en="x"),
        spec=ObjectTypeSpec(
            dedicated_columns=[
                DedicatedColumn(name="foo_id", type="int", nullable=False),
nullable=False),
            ],
            relations=[
                Relation(name="foo", target="y", cardinality="many_to_one")
cardinality="many_to_one"),
            ],
        ),
    )
    with pytest.raises(ValueError):
        compile_to_ddl(manifest)


def test_compile_emits_create_table(tmp_path: Path):
    ddl = compile_to_ddl(_minimal_manifest())
    assert "CREATE TABLE IF NOT EXISTS sylion_v2.customer" in ddl


def test_compile_emits_btree_index_when_indexed(tmp_path: Path):
    manifest = _minimal_manifest()
    manifest.spec.dedicated_columns.append(
        DedicatedColumn(name="code", type="text", nullable=False, indexed=T
indexed=True)
    )
    ddl = compile_to_ddl(manifest)
    assert "customer_code_btree" in ddl


def test_compile_emits_gin_trgm_when_searchable(tmp_path: Path):
    manifest = _minimal_manifest()
    manifest.spec.search_config = SearchConfig(
        text_fields=["title"], exact_fields=[], fuzzy_fields=[]
    )
    ddl = compile_to_ddl(manifest)
    assert "gin_trgm_ops" in ddl


def test_compile_emits_check_constraint_for_enum(tmp_path: Path):
    manifest = _minimal_manifest()
    manifest.spec.dedicated_columns.append(
        DedicatedColumn(name="status", type="enum", nullable=False, values=
values=["a", "b"])
    )
    ddl = compile_to_ddl(manifest)
    assert "CHECK (status IN" in ddl


def test_compile_emits_unique_constraint(tmp_path: Path):
    manifest = _minimal_manifest()
    manifest.spec.dedicated_columns.append(
        DedicatedColumn(name="code", type="text", nullable=False, unique=Tr
unique=True)
    )
    ddl = compile_to_ddl(manifest)
    assert "UNIQUE" in ddl


def test_compile_emits_default_value(tmp_path: Path):
    manifest = _minimal_manifest()
    manifest.spec.dedicated_columns.append(
        DedicatedColumn(name="status", type="text", nullable=False, default
default="draft")
    )
    ddl = compile_to_ddl(manifest)
    assert "DEFAULT 'draft'" in ddl


def test_compile_emits_fk_constraint_for_many_to_one(tmp_path: Path):
    manifest = _minimal_manifest()
    manifest.spec.relations = [
        Relation(name="owner", target="user", cardinality="many_to_one")
    ]
    ddl = compile_to_ddl(manifest)
    assert "FOREIGN KEY" in ddl
    assert "REFERENCES sylion_v2.user(id)" in ddl


def test_compile_emits_join_table_for_many_to_many(tmp_path: Path):
    manifest = _minimal_manifest()
    manifest.spec.relations = [
        Relation(name="tags", target="tag", cardinality="many_to_many")
    ]
    ddl = compile_to_ddl(manifest)
    assert "CREATE TABLE IF NOT EXISTS sylion_v2.customer_tags" in ddl
    assert "REFERENCES sylion_v2.tag(id)" in ddl


def test_compile_emits_lineage_table_when_hash_chain(tmp_path: Path):
    manifest = _minimal_manifest()
    manifest.metadata.hash_chain = True
    ddl = compile_to_ddl(manifest)
    assert "CREATE TABLE IF NOT EXISTS sylion_v2.customer_lineage" in ddl


def test_compile_skips_lineage_when_disabled(tmp_path: Path):
    manifest = _minimal_manifest()
    manifest.metadata.hash_chain = False
    ddl = compile_to_ddl(manifest)
    assert "customer_lineage" not in ddl


def test_compile_emits_updated_at_trigger(tmp_path: Path):
    ddl = compile_to_ddl(_minimal_manifest())
    assert "sylion_v2.touch_updated_at" in ddl


def test_compile_shared_emitted_only_once_per_compiler(tmp_path: Path):
    compiler = SchemaCompiler()
    out1 = compiler.compile([_minimal_manifest()])
    out2 = compiler.compile([_minimal_manifest()])
    shared = "CREATE EXTENSION IF NOT EXISTS"
    assert shared in out1
    assert out1.count(shared) == out2.count(shared) == 1


def test_compile_to_ddl_helper_always_emits_shared(tmp_path: Path):
    ddl = compile_to_ddl(_minimal_manifest())
    assert "CREATE EXTENSION IF NOT EXISTS" in ddl


def test_load_manifest_dir_skips_underscore_prefixed(tmp_path: Path):
    _write_manifest(tmp_path, _minimal_manifest(), "m.yaml")
    _write_manifest(tmp_path, _minimal_manifest(), "_index.yaml")
    manifests = load_manifest_dir(tmp_path)
    assert len(manifests) == 1
    assert manifests[0].metadata.id == "customer"


def test_load_manifest_dir_raises_on_duplicate_id(tmp_path: Path):
    _write_manifest(tmp_path, _minimal_manifest("dup"), "a.yaml")
    _write_manifest(tmp_path, _minimal_manifest("dup"), "b.yaml")
    with pytest.raises(ManifestValidationError):
        load_manifest_dir(tmp_path)


def test_registry_singleton():
    r1 = get_registry()
    r2 = get_registry()
    assert r1 is r2


def test_registry_register_dir(tmp_path: Path):
    ids = []
    for i in range(3):
        m = _minimal_manifest(f"t{i}")
        ids.append(m.metadata.id)
        _write_manifest(tmp_path, m, f"{i}.yaml")
    registry = get_registry()
    registry.register_dir(tmp_path)
    for id_ in ids:
        assert registry.get(id_) is not None


def test_registry_reload_replaces_all(tmp_path: Path):
    registry = get_registry()
    ids1 = []
    for i in range(2):
        m = _minimal_manifest(f"a{i}")
        ids1.append(m.metadata.id)
        _write_manifest(tmp_path, m, f"{i}.yaml")
    registry.reload(tmp_path)
    for id_ in ids1:
        assert registry.get(id_) is not None
    ids2 = ["b0"]
    for id_ in ids2:
        m = _minimal_manifest(id_)
        _write_manifest(tmp_path, m, f"{id_}.yaml")
    registry.reload(tmp_path)
    assert all(registry.get(id_) is None for id_ in ids1)
    assert all(registry.get(id_) is not None for id_ in ids2)


def test_registry_get_returns_none_for_unknown():
    registry = get_registry()
    assert registry.get("missing") is None


def test_explain_actions_returns_endpoints_and_d_level():
    m = _minimal_manifest()
    m.spec.actions = [
        ActionDef(name="read", endpoint="/r", d_level="public", hg_required
hg_required=False)
    ]
    res = explain_actions([m])
    assert isinstance(res, list) and len(res) == 1
    d = res[0]
    assert set(d.keys()) == {"endpoint", "d_level", "hg_required"}


def test_render_sql_terminates_each_statement_with_semicolon(tmp_path: Path
Path):
    ddl = compile_to_ddl(_minimal_manifest())
    for line in ddl.splitlines():
        if line.strip():
            assert line.strip().endswith(";")


