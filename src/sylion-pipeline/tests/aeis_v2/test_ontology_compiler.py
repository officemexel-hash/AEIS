"""Tests for sylion.aeis_v2.ontology — manifest, compiler, registry.

Covers:
- Manifest validation (pydantic v2): api_version, kind, slug rules, type
  whitelist, relation cardinality, FK/dedicated column clashes.
- Compiler P0 fixes from adversarial review:
    - P0-1: SQL injection escape in enum values + defaults.
    - P0-2: Lineage hash-chain advisory lock + UNIQUE constraint.
    - P0-3: compile_alter detects added/removed/indexed columns.
- Registry singleton + manifest dir loader (skips _ prefixed files).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from sylion.aeis_v2.ontology import (
    AuditConfig,
    DedicatedColumn,
    ManifestValidationError,
    ObjectTypeManifest,
    ObjectTypeMetadata,
    ObjectTypeSpec,
    Relation,
    SchemaCompiler,
    compile_alter,
    compile_to_ddl,
    load_manifest,
    load_manifest_dir,
)
from sylion.aeis_v2.ontology.compiler import _escape_sql_literal


def _minimal_manifest(type_id: str = "customer") -> ObjectTypeManifest:
    return ObjectTypeManifest(
        api_version="sylion.aeis.v2/Object",
        kind="ObjectType",
        metadata=ObjectTypeMetadata(
            id=type_id, name_pl="Klient", name_en="Customer",
        ),
        spec=ObjectTypeSpec(
            dedicated_columns=[
                DedicatedColumn(name="title", type="text", nullable=False),
            ],
        ),
    )


# --------------------------------------------------------------------------
# Manifest validation
# --------------------------------------------------------------------------


def test_minimal_manifest_loads():
    m = _minimal_manifest()
    assert isinstance(m, ObjectTypeManifest)
    assert m.metadata.id == "customer"
    assert len(m.spec.dedicated_columns) == 1


def test_manifest_rejects_wrong_api_version():
    with pytest.raises(ValidationError):
        ObjectTypeManifest(
            api_version="bogus/v9",
            kind="ObjectType",
            metadata=ObjectTypeMetadata(id="x", name_pl="x", name_en="x"),
            spec=ObjectTypeSpec(),
        )


def test_manifest_rejects_wrong_kind():
    with pytest.raises(ValidationError):
        ObjectTypeManifest(
            api_version="sylion.aeis.v2/Object",
            kind="WrongKind",
            metadata=ObjectTypeMetadata(id="x", name_pl="x", name_en="x"),
            spec=ObjectTypeSpec(),
        )


def test_column_name_must_be_slug():
    with pytest.raises(ValidationError):
        DedicatedColumn(name="Bad-Name", type="text", nullable=False)


def test_column_name_reserved_id_rejected():
    with pytest.raises(ValidationError):
        DedicatedColumn(name="id", type="text", nullable=False)


def test_column_type_must_be_supported():
    with pytest.raises(ValidationError):
        DedicatedColumn(name="email", type="varchar", nullable=False)


def test_relation_target_required():
    with pytest.raises(ValidationError):
        Relation(name="parent")  # type: ignore[call-arg]


def test_relation_cardinality_validated():
    with pytest.raises(ValidationError):
        Relation(name="parent", target="other", cardinality="weird")


def test_relation_fk_clashes_with_dedicated_column():
    with pytest.raises(ValidationError):
        ObjectTypeSpec(
            dedicated_columns=[
                DedicatedColumn(name="title", type="text", nullable=False),
                DedicatedColumn(name="parent_id", type="uuid"),
            ],
            relations=[
                Relation(name="parent", target="other", cardinality="many_to_one"),
            ],
        )


# --------------------------------------------------------------------------
# P0-1: SQL injection escape (enum values + defaults)
# --------------------------------------------------------------------------


def test_enum_with_sql_injection_is_escaped():
    """P0-1: enum literal `'); DROP TABLE x;` must become `'''); DROP TABLE x;'`.

    The CHECK constraint must contain the doubled apostrophe; no lone
    apostrophe can appear inside the value (which would terminate the
    string and let the rest execute).
    """
    m = _minimal_manifest()
    m.spec.dedicated_columns.append(
        DedicatedColumn(
            name="status", type="text", nullable=False,
            enum=["'); DROP TABLE x;"],
        )
    )
    sql = compile_to_ddl(m).render_sql()
    # Doubled apostrophe present (escape).
    assert "'''); DROP TABLE x;'" in sql
    # The CHECK clause must have a balanced number of apostrophes — i.e.
    # even number on every line containing the constraint.
    for line in sql.splitlines():
        if 'CHECK ("status"' in line:
            assert line.count("'") % 2 == 0


def test_enum_with_nul_byte_rejected():
    """P0-1: NUL byte inside enum literal must raise — never reach DDL."""
    m = _minimal_manifest()
    m.spec.dedicated_columns.append(
        DedicatedColumn(name="status", type="text", enum=["foo\x00bar"])
    )
    with pytest.raises(ValueError):
        compile_to_ddl(m)


def test_default_string_with_quotes_escaped():
    """P0-1: default value `O'Brien` must render as `DEFAULT 'O''Brien'`."""
    m = _minimal_manifest()
    m.spec.dedicated_columns.append(
        DedicatedColumn(name="owner", type="text", default="O'Brien")
    )
    sql = compile_to_ddl(m).render_sql()
    assert "DEFAULT 'O''Brien'" in sql


def test_default_nan_rejected():
    """P2-5: NaN/Inf floats are rejected because PostgreSQL can't store them."""
    m = _minimal_manifest()
    m.spec.dedicated_columns.append(
        DedicatedColumn(name="ratio", type="numeric", default=float("nan"))
    )
    with pytest.raises(ValueError):
        compile_to_ddl(m)


# --------------------------------------------------------------------------
# DDL emission
# --------------------------------------------------------------------------


def test_compile_emits_create_table():
    sql = compile_to_ddl(_minimal_manifest()).render_sql()
    assert 'CREATE TABLE IF NOT EXISTS "sylion_v2"."customer"' in sql


def test_compile_emits_btree_index_when_indexed():
    m = _minimal_manifest()
    m.spec.dedicated_columns.append(
        DedicatedColumn(name="email", type="text", indexed=True)
    )
    sql = compile_to_ddl(m).render_sql()
    assert "customer_email_btree" in sql


def test_compile_emits_gin_trgm_when_searchable():
    m = _minimal_manifest()
    m.spec.dedicated_columns.append(
        DedicatedColumn(name="email", type="text", searchable=True)
    )
    sql = compile_to_ddl(m).render_sql()
    assert "gin_trgm_ops" in sql
    assert "customer_email_trgm" in sql


def test_compile_emits_check_constraint_for_enum():
    m = _minimal_manifest()
    m.spec.dedicated_columns.append(
        DedicatedColumn(
            name="status", type="text", nullable=False,
            enum=["draft", "active"],
        )
    )
    sql = compile_to_ddl(m).render_sql()
    assert 'CHECK ("status" IN' in sql
    assert "'draft'" in sql and "'active'" in sql


def test_compile_emits_unique_constraint():
    m = _minimal_manifest()
    m.spec.dedicated_columns.append(
        DedicatedColumn(name="email", type="text", unique=True)
    )
    sql = compile_to_ddl(m).render_sql()
    assert "UNIQUE" in sql


def test_compile_emits_fk_constraint_for_many_to_one():
    m = _minimal_manifest()
    m.spec.relations = [
        Relation(name="owner", target="user", cardinality="many_to_one")
    ]
    sql = compile_to_ddl(m).render_sql()
    assert "FOREIGN KEY" in sql
    assert 'REFERENCES "sylion_v2"."user"(id)' in sql


def test_compile_emits_join_table_for_many_to_many():
    m = _minimal_manifest()
    m.spec.relations = [
        Relation(name="tags", target="tag", cardinality="many_to_many")
    ]
    sql = compile_to_ddl(m).render_sql()
    assert 'CREATE TABLE IF NOT EXISTS "sylion_v2"."customer__tags__tag"' in sql
    assert 'REFERENCES "sylion_v2"."tag"(id)' in sql


def test_compile_emits_lineage_table_when_hash_chain():
    m = _minimal_manifest()
    m.spec.audit = AuditConfig(hash_chain=True)
    sql = compile_to_ddl(m).render_sql()
    assert 'CREATE TABLE IF NOT EXISTS "sylion_v2"."customer_lineage"' in sql


# --------------------------------------------------------------------------
# P0-2: lineage chain integrity
# --------------------------------------------------------------------------


def test_lineage_includes_unique_constraint():
    """P0-2: defense-in-depth UNIQUE INDEX on (object_id, prev_hash)."""
    m = _minimal_manifest()
    m.spec.audit = AuditConfig(hash_chain=True)
    sql = compile_to_ddl(m).render_sql()
    assert "_chain_uniq" in sql
    assert "CREATE UNIQUE INDEX" in sql


def test_append_lineage_uses_advisory_lock():
    """P0-2: shared DDL must call pg_advisory_xact_lock to serialize chains."""
    art = compile_to_ddl(_minimal_manifest())
    shared = art.shared[0]
    assert "pg_advisory_xact_lock" in shared


def test_compile_emits_updated_at_trigger():
    sql = compile_to_ddl(_minimal_manifest()).render_sql()
    assert "sylion_v2.touch_updated_at" in sql
    assert "customer_set_updated_at" in sql


def test_compile_shared_emitted_only_once_per_compiler():
    compiler = SchemaCompiler()
    art1 = compiler.compile(_minimal_manifest("customer"))
    art2 = compiler.compile(_minimal_manifest("project"))
    assert len(art1.shared) == 1
    assert art2.shared == []  # second manifest does not re-emit shared


def test_compile_to_ddl_helper_always_emits_shared():
    art = compile_to_ddl(_minimal_manifest())
    assert len(art.shared) == 1
    assert "CREATE SCHEMA IF NOT EXISTS sylion_v2" in art.shared[0]


# --------------------------------------------------------------------------
# P1-6: trigger DROP+CREATE atomicity (rendered SQL wrapped in transaction)
# --------------------------------------------------------------------------


def test_render_sql_wraps_in_transaction():
    """P1-6: rendered SQL starts with BEGIN; and ends with COMMIT;.

    Ensures DROP+CREATE TRIGGER pair (and other multi-statement sequences)
    run atomically when the rendered SQL is fed through ``psql -f``. Our
    in-process applier already uses a single transaction; this fixes the
    case where an operator runs the SQL via psql directly.
    """
    sql = compile_to_ddl(_minimal_manifest()).render_sql()
    stripped = sql.strip()
    assert stripped.startswith("BEGIN;"), (
        f"SQL must start with BEGIN; got: {stripped[:80]}"
    )
    assert stripped.rstrip(";").rstrip().endswith("COMMIT"), (
        f"SQL must end with COMMIT; got: ...{stripped[-80:]}"
    )


def test_trigger_section_has_p1_6_comment():
    """P1-6: compiler module documents the trigger atomicity invariant."""
    import inspect
    from sylion.aeis_v2.ontology import compiler as compiler_mod
    src = inspect.getsource(compiler_mod)
    assert "P1-6" in src
    assert "transaction" in src.lower()


# --------------------------------------------------------------------------
# P0-3: compile_alter — schema evolution
# --------------------------------------------------------------------------


def test_compile_alter_detects_added_column():
    """P0-3: adding a DedicatedColumn yields ALTER TABLE ADD COLUMN."""
    old = _minimal_manifest()
    new = _minimal_manifest()
    new.spec.dedicated_columns.append(
        DedicatedColumn(name="email", type="text", nullable=True)
    )
    art = compile_alter(old, new)
    assert any("ADD COLUMN" in s and '"email"' in s for s in art.main_table)


def test_compile_alter_warns_on_removed_column():
    """P0-3: removed columns produce a commented DROP + WARNING note."""
    old = _minimal_manifest()
    old.spec.dedicated_columns.append(
        DedicatedColumn(name="legacy", type="text", nullable=True)
    )
    new = _minimal_manifest()
    art = compile_alter(old, new)
    assert any("DESTRUCTIVE" in s for s in art.main_table)
    assert any("legacy" in n and "WARNING" in n for n in art.notes)


def test_compile_alter_emits_index_for_newly_indexed_column():
    """P0-3: newly-indexed column → CREATE INDEX btree."""
    old = _minimal_manifest()
    new = _minimal_manifest()
    new.spec.dedicated_columns.append(
        DedicatedColumn(name="email", type="text", indexed=True)
    )
    art = compile_alter(old, new)
    assert any("customer_email_btree" in s for s in art.indexes)


def test_compile_alter_type_change_emits_alter_column_type():
    """When a column type changes, compile_alter emits ALTER TABLE ... ALTER COLUMN ... TYPE.

    Type changes are commented out (DESTRUCTIVE — needs USING clause). The
    emitted SQL must include the column name AND the new type AND a USING
    cast hint.
    """
    old = _minimal_manifest()
    old.spec.dedicated_columns.append(
        DedicatedColumn(name="age", type="text", nullable=True)
    )
    new = _minimal_manifest()
    new.spec.dedicated_columns.append(
        DedicatedColumn(name="age", type="integer", nullable=True)
    )
    art = compile_alter(old, new)
    sql = "\n".join(art.main_table)
    assert "ALTER COLUMN \"age\"" in sql or 'ALTER COLUMN "age"' in sql
    assert "INTEGER" in sql.upper()
    assert "USING" in sql.upper()
    # destructive — must be commented out
    assert any("--" in line and "ALTER" in line for line in art.main_table)
    assert any("type change" in note.lower() or "WARNING" in note for note in art.notes)


def test_compile_alter_nullable_to_not_null_emits_set_not_null():
    """Tightening nullability emits ALTER COLUMN ... SET NOT NULL."""
    old = _minimal_manifest()
    old.spec.dedicated_columns.append(
        DedicatedColumn(name="email", type="text", nullable=True)
    )
    new = _minimal_manifest()
    new.spec.dedicated_columns.append(
        DedicatedColumn(name="email", type="text", nullable=False)
    )
    art = compile_alter(old, new)
    sql = "\n".join(art.main_table)
    assert "SET NOT NULL" in sql
    assert "email" in sql


def test_compile_alter_not_null_to_nullable_emits_drop_not_null():
    """Loosening nullability emits ALTER COLUMN ... DROP NOT NULL."""
    old = _minimal_manifest()
    old.spec.dedicated_columns.append(
        DedicatedColumn(name="phone", type="text", nullable=False)
    )
    new = _minimal_manifest()
    new.spec.dedicated_columns.append(
        DedicatedColumn(name="phone", type="text", nullable=True)
    )
    art = compile_alter(old, new)
    sql = "\n".join(art.main_table)
    assert "DROP NOT NULL" in sql
    assert "phone" in sql


def test_compile_alter_default_added_emits_set_default():
    """Adding a default emits ALTER COLUMN ... SET DEFAULT '<value>'."""
    old = _minimal_manifest()
    old.spec.dedicated_columns.append(
        DedicatedColumn(name="status", type="text", nullable=False)
    )
    new = _minimal_manifest()
    new.spec.dedicated_columns.append(
        DedicatedColumn(name="status", type="text", nullable=False, default="draft")
    )
    art = compile_alter(old, new)
    sql = "\n".join(art.main_table)
    assert "SET DEFAULT" in sql
    assert "'draft'" in sql


def test_compile_alter_default_removed_emits_drop_default():
    """Removing a default emits ALTER COLUMN ... DROP DEFAULT."""
    old = _minimal_manifest()
    old.spec.dedicated_columns.append(
        DedicatedColumn(name="status", type="text", nullable=False, default="active")
    )
    new = _minimal_manifest()
    new.spec.dedicated_columns.append(
        DedicatedColumn(name="status", type="text", nullable=False)
    )
    art = compile_alter(old, new)
    sql = "\n".join(art.main_table)
    assert "DROP DEFAULT" in sql


def test_compile_alter_new_relation_emits_fk_column_and_constraint():
    """Adding a relation emits ALTER TABLE ADD COLUMN <name>_id + ADD CONSTRAINT FK."""
    from sylion.aeis_v2.ontology.manifest import Relation
    old = _minimal_manifest()
    new = _minimal_manifest()
    new.spec.relations.append(
        Relation(name="parent_project", target="project", cardinality="many_to_one")
    )
    art = compile_alter(old, new)
    main_sql = "\n".join(art.main_table)
    fk_sql = "\n".join(art.foreign_keys)
    # FK column added on the many side
    assert "parent_project_id" in main_sql
    assert "UUID" in main_sql.upper()
    # FK constraint
    assert "REFERENCES" in fk_sql.upper()
    assert "project" in fk_sql
    # rationale note
    assert any("relation" in n.lower() for n in art.notes)


def test_compile_alter_searchable_added_emits_gin_trgm():
    """Toggling searchable=true emits the trigram GIN index."""
    old = _minimal_manifest()
    old.spec.dedicated_columns.append(
        DedicatedColumn(name="title", type="text", searchable=False)
    )
    new = _minimal_manifest()
    new.spec.dedicated_columns.append(
        DedicatedColumn(name="title", type="text", searchable=True)
    )
    art = compile_alter(old, new)
    idx_sql = "\n".join(art.indexes)
    assert "gin_trgm_ops" in idx_sql
    assert "trgm" in idx_sql


# --------------------------------------------------------------------------
# Loader / registry
# --------------------------------------------------------------------------


def test_load_manifest_dir_skips_underscore_prefixed(tmp_path: Path):
    good = tmp_path / "customer.yaml"
    skipped = tmp_path / "_index.yaml"
    good.write_text(yaml.safe_dump(_minimal_manifest("customer").model_dump()))
    # _index.yaml is invalid on purpose — proves it was skipped (no error raised).
    skipped.write_text("not: a: valid: manifest:")
    out = load_manifest_dir(tmp_path)
    assert "customer" in out
    assert len(out) == 1


# --------------------------------------------------------------------------
# P1-1: PostgreSQL identifier byte limit (63 bytes)
# --------------------------------------------------------------------------


def test_compile_rejects_identifier_over_63_bytes():
    """P1-1: long type_id produces table/index names PG would silently truncate.

    Adversarial review case: ``type_id`` 30 chars × ``rel.name`` 30 chars
    × ``target`` 30 chars yields a 94-byte join table identifier that
    PG truncates to 63, causing collisions across manifests. Compiler
    now refuses up-front rather than letting the operator hit a runtime
    surprise.
    """
    from sylion.aeis_v2.ontology.compiler import _validate_identifier_length

    # Exactly 64 chars → reject.
    too_long = "a" * 64
    with pytest.raises(ValueError, match="exceeds PostgreSQL"):
        _validate_identifier_length(too_long)
    # Exactly 63 chars → ok.
    just_fits = "a" * 63
    _validate_identifier_length(just_fits)  # no exception


def test_compile_rejects_pg_prefixed_identifier():
    """P1-2: PG reserves `pg_` prefix for system catalogs."""
    from sylion.aeis_v2.ontology.compiler import _validate_identifier_length

    with pytest.raises(ValueError, match="reserved PostgreSQL prefix"):
        _validate_identifier_length("pg_my_table")
    # Mixed case still caught.
    with pytest.raises(ValueError, match="reserved PostgreSQL prefix"):
        _validate_identifier_length("PG_my_table")


# --------------------------------------------------------------------------
# P1-3: YAML billion-laughs / anchor-bomb DoS guards
# --------------------------------------------------------------------------


def test_load_manifest_rejects_oversized_file(tmp_path):
    """P1-3: cap manifest file size to avoid memory exhaustion."""
    big = tmp_path / "big.yaml"
    big.write_text("api_version: sylion.aeis.v2/Object\n" + ("# pad\n" * 200_000))
    with pytest.raises(ManifestValidationError, match="bytes"):
        load_manifest(big)


def test_load_manifest_rejects_anchor_bomb(tmp_path):
    """P1-3: refuse YAML billion-laughs / anchor-bomb expansion."""
    bomb = tmp_path / "bomb.yaml"
    bomb.write_text(
        "a: &a [x, x, x, x, x, x, x, x, x]\n"
        "b: &b [*a, *a, *a, *a, *a, *a, *a, *a, *a]\n"
        "c: &c [*b, *b, *b, *b, *b, *b, *b, *b, *b]\n"
        "d: &d [*c, *c, *c, *c, *c, *c, *c, *c, *c]\n"
        "e: &e [*d, *d, *d, *d, *d, *d, *d, *d, *d]\n"
        "f: [*e, *e, *e, *e, *e, *e, *e, *e, *e]\n"
    )
    with pytest.raises(ManifestValidationError):
        load_manifest(bomb)


# --------------------------------------------------------------------------
# P1-4: per-directory manifest count cap (startup memory guard)
# --------------------------------------------------------------------------


def test_load_manifest_dir_rejects_too_many_files(tmp_path, monkeypatch):
    """P1-4: cap manifest directory at MAX_MANIFESTS_PER_DIR."""
    from sylion.aeis_v2.ontology import manifest as manifest_mod
    monkeypatch.setattr(manifest_mod, "MAX_MANIFESTS_PER_DIR", 3)
    for i in range(5):
        (tmp_path / f"obj_{i}.yaml").write_text(
            yaml.safe_dump(_minimal_manifest(f"obj_{i}").model_dump())
        )
    with pytest.raises(ManifestValidationError, match="manifests"):
        load_manifest_dir(tmp_path)


# --------------------------------------------------------------------------
# P1-5: registry.reload() must be atomic on partial failure
# --------------------------------------------------------------------------


def test_registry_reload_atomic_on_partial_failure(tmp_path):
    """P1-5: reload() must NOT mutate registry when a directory fails to load."""
    from sylion.aeis_v2.ontology.registry import ObjectTypeRegistry

    # Setup: registry with one good dir.
    good_dir = tmp_path / "good"
    good_dir.mkdir()
    (good_dir / "alpha.yaml").write_text(
        yaml.safe_dump(_minimal_manifest("alpha").model_dump())
    )
    reg = ObjectTypeRegistry()
    reg.register_dir(good_dir)
    assert "alpha" in reg

    # Add a bad dir to the registry's known dirs
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    (bad_dir / "beta.yaml").write_text(
        yaml.safe_dump(_minimal_manifest("beta").model_dump())
    )
    reg.register_dir(bad_dir)
    assert "beta" in reg

    # Now corrupt one file in bad_dir.
    (bad_dir / "gamma.yaml").write_text("!!!malformed-yaml: {[}")

    # reload() should raise BUT not damage existing state.
    with pytest.raises(ManifestValidationError):
        reg.reload()

    # State preserved — alpha and beta still there because reload was atomic.
    assert "alpha" in reg
    assert "beta" in reg


# --------------------------------------------------------------------------
# P1-7: lineage table monthly partitioning (unbounded growth fix)
# --------------------------------------------------------------------------


def test_lineage_table_is_partitioned_by_recorded_at():
    """P1-7: lineage tables use PARTITION BY RANGE (recorded_at) for monthly partitions."""
    from sylion.aeis_v2.ontology import compile_to_ddl
    from sylion.aeis_v2.ontology.manifest import AuditConfig

    m = _minimal_manifest()
    m.spec.audit = AuditConfig(hash_chain=True)
    sql = compile_to_ddl(m).render_sql()
    assert "PARTITION BY RANGE (recorded_at)" in sql or \
           "PARTITION BY RANGE(recorded_at)" in sql


def test_lineage_initial_partition_created():
    """P1-7: at apply time we create the current-month partition."""
    from sylion.aeis_v2.ontology import compile_to_ddl
    from sylion.aeis_v2.ontology.manifest import AuditConfig

    m = _minimal_manifest()
    m.spec.audit = AuditConfig(hash_chain=True)
    sql = compile_to_ddl(m).render_sql()
    assert "PARTITION OF" in sql
    assert "_initial" in sql or "FOR VALUES FROM (date_trunc('month', NOW()))" in sql


def test_create_next_lineage_partition_function_in_shared_ddl():
    """P1-7: shared DDL exposes a create_next_lineage_partition() helper."""
    from sylion.aeis_v2.ontology import compile_to_ddl
    sql = compile_to_ddl(_minimal_manifest()).render_sql()
    assert "create_next_lineage_partition" in sql
    assert "PARTITION OF" in sql or "PARTITION BY RANGE" in sql


def test_lineage_chain_uniq_includes_partition_key():
    """P1-7: UNIQUE INDEX for chain protection includes recorded_at to satisfy PG
    partitioning constraint that unique indexes must include the partition key."""
    from sylion.aeis_v2.ontology import compile_to_ddl
    from sylion.aeis_v2.ontology.manifest import AuditConfig

    m = _minimal_manifest()
    m.spec.audit = AuditConfig(hash_chain=True)
    sql = compile_to_ddl(m).render_sql()
    # The UNIQUE INDEX def should mention recorded_at (or be missing
    # if the test catches a regression).
    assert "_chain_uniq" in sql
    # Find the line containing _chain_uniq and assert recorded_at on same line
    for line in sql.splitlines():
        if "_chain_uniq" in line and "INDEX" in line.upper():
            # Index def may span multiple lines — check next 3
            idx = sql.splitlines().index(line)
            window = "\n".join(sql.splitlines()[idx:idx+3])
            assert "recorded_at" in window, \
                f"chain_uniq index must include recorded_at; got: {window}"
            break


# --------------------------------------------------------------------------
# P1-8: GIN jsonb_path_ops index on extension column
# --------------------------------------------------------------------------


def test_compile_emits_gin_jsonb_path_ops_on_extension():
    """P1-8: extension column gets a GIN jsonb_path_ops index for fast @> queries."""
    sql = compile_to_ddl(_minimal_manifest("customer")).render_sql()
    assert "customer_extension_gin" in sql
    assert "USING GIN" in sql
    assert "jsonb_path_ops" in sql


def test_compile_extension_gin_uses_field_name():
    """P1-8: GIN index uses the manifest's jsonb_extension.field name (custom case)."""
    from sylion.aeis_v2.ontology.manifest import JsonbExtension

    m = _minimal_manifest("customer")
    m.spec.jsonb_extension = JsonbExtension(field="metadata")
    sql = compile_to_ddl(m).render_sql()
    assert "customer_metadata_gin" in sql
    assert '"metadata" jsonb_path_ops' in sql


def test_compile_extension_gin_present_for_every_type():
    """P1-8: every loaded sample manifest emits an extension GIN index in DDL."""
    from sylion.aeis_v2.ontology import get_registry
    reg = get_registry()
    reg.reload()
    types_checked = 0
    for tid in reg.list_ids():
        if tid.startswith("w14_"):
            continue  # W14 lifted manifests handled separately
        sql = compile_to_ddl(reg.get(tid)).render_sql()
        assert f"{tid}_extension_gin" in sql, f"no extension GIN for {tid}"
        types_checked += 1
    assert types_checked >= 5  # 5 sample types: customer/idea/inspection/project/vehicle


# --------------------------------------------------------------------------
# P1-9: named CHECK constraints (deterministic name for ALTER stability)
# --------------------------------------------------------------------------


def test_compile_emits_named_check_constraint_for_enum():
    """P1-9: CHECK constraint must carry the deterministic ``<type>_<col>_chk`` name.

    Without a stable name, PG auto-generates one (e.g. ``customer_status_check``)
    that is version-dependent and silently changes if columns are renamed,
    breaking ``compile_alter()``'s ability to ``DROP CONSTRAINT IF EXISTS``.
    """
    m = _minimal_manifest("customer")
    m.spec.dedicated_columns.append(
        DedicatedColumn(
            name="status", type="text", nullable=False,
            enum=["active", "inactive"],
        )
    )
    sql = compile_to_ddl(m).render_sql()
    # Literal CONSTRAINT ... CHECK clause, with deterministic name.
    assert 'CONSTRAINT "customer_status_chk" CHECK' in sql, (
        f"expected named CHECK constraint, got SQL:\n{sql}"
    )
    # Sanity: still a valid IN-list with both enum members quoted.
    assert "'active'" in sql and "'inactive'" in sql


def test_compile_check_constraint_name_uses_type_id_prefix():
    """P1-9: two manifests sharing a column name get unique constraint names.

    ``customer.status`` -> ``customer_status_chk``; ``vehicle.status`` ->
    ``vehicle_status_chk``. Without the type_id prefix the two would
    collide on the same constraint name across manifests in the same DB.
    """
    customer = _minimal_manifest("customer")
    customer.spec.dedicated_columns.append(
        DedicatedColumn(name="status", type="text", enum=["a", "b"])
    )
    vehicle = _minimal_manifest("vehicle")
    vehicle.spec.dedicated_columns.append(
        DedicatedColumn(name="status", type="text", enum=["a", "b"])
    )
    customer_sql = compile_to_ddl(customer).render_sql()
    vehicle_sql = compile_to_ddl(vehicle).render_sql()
    assert '"customer_status_chk"' in customer_sql
    assert '"vehicle_status_chk"' in vehicle_sql
    # And neither leaks into the other.
    assert '"vehicle_status_chk"' not in customer_sql
    assert '"customer_status_chk"' not in vehicle_sql


def test_compile_alter_emits_drop_then_add_constraint_on_enum_change():
    """P1-9: enum change emits DROP CONSTRAINT IF EXISTS then ADD CONSTRAINT.

    The DROP+ADD pair uses the same ``<type>_<col>_chk`` name so the
    DROP IF EXISTS reliably finds the prior constraint regardless of
    which compiler version originally created it.
    """
    old = _minimal_manifest("customer")
    old.spec.dedicated_columns.append(
        DedicatedColumn(name="status", type="text", enum=["a", "b"])
    )
    new = _minimal_manifest("customer")
    new.spec.dedicated_columns.append(
        DedicatedColumn(name="status", type="text", enum=["a", "b", "c"])
    )
    art = compile_alter(old, new)
    sql = "\n".join(art.main_table)
    assert (
        'DROP CONSTRAINT IF EXISTS "customer_status_chk"' in sql
    ), f"expected DROP CONSTRAINT IF EXISTS, got:\n{sql}"
    assert (
        'ADD CONSTRAINT "customer_status_chk" CHECK' in sql
    ), f"expected ADD CONSTRAINT with same name, got:\n{sql}"
    # New enum value must appear in the ADD clause.
    assert "'c'" in sql
    # Order matters — DROP must come before ADD.
    drop_idx = sql.index("DROP CONSTRAINT IF EXISTS")
    add_idx = sql.index("ADD CONSTRAINT")
    assert drop_idx < add_idx, "DROP must come before ADD"


def test_compile_check_constraint_name_falls_back_on_overlong_identifier():
    """P1-9: when ``<type>_<col>_chk`` would exceed 63 bytes, fall back to ``chk_<sha8>``.

    A 60-char type_id with a 10-char column would produce a 75-char
    natural name (60+1+10+4=75 bytes). The compiler must mint a stable
    short hash-based fallback rather than crash. We deliberately do not
    use ``pg_`` as the fallback prefix because that prefix is reserved
    by PG for system catalogs (and rejected by ``_validate_identifier_length``).
    """
    from sylion.aeis_v2.ontology.compiler import _check_constraint_name

    # Natural form: 60 + 1 + 10 + 4 = 75 bytes -> overflow.
    long_type = "a" * 60
    long_col = "b" * 10
    natural = f"{long_type}_{long_col}_chk"
    assert len(natural.encode("utf-8")) > 63, (
        "test precondition: natural name must overflow 63-byte limit"
    )

    fallback = _check_constraint_name(long_type, long_col)
    # Fits within PG identifier limit.
    assert len(fallback.encode("utf-8")) <= 63
    # Deterministic prefix so operators can recognize the pattern.
    assert fallback.startswith("chk_"), (
        f"expected chk_<hash> fallback, got: {fallback}"
    )
    # Same input -> same output (determinism).
    assert _check_constraint_name(long_type, long_col) == fallback
    # Different inputs -> different outputs.
    other = _check_constraint_name(long_type, "c" * 10)
    assert other != fallback
    # Short inputs use the natural form, not the fallback.
    short = _check_constraint_name("customer", "status")
    assert short == "customer_status_chk"


# ----- W15 P1-10: _quote_ident hardening (empty / NUL / control chars) -----


def test_quote_ident_rejects_empty_string():
    """W15 P1-10: empty identifier is refused with a clear ValueError.

    PG would otherwise parse ``""`` as an unnamed identifier and emit a
    confusing message. We catch it at the compiler boundary so any
    upstream bug (e.g. compiler synthesizing ``f"{type_id}_{col}"`` where
    one is blank) surfaces immediately.
    """
    from sylion.aeis_v2.ontology.compiler import _quote_ident

    with pytest.raises(ValueError, match="empty"):
        _quote_ident("")


def test_quote_ident_rejects_nul_byte():
    """W15 P1-10: NUL byte in an identifier is refused.

    PG (and libpq) silently truncate strings at NUL when using
    server-side prepared statements; the resulting DDL would be
    unpredictable. Refuse before it ever reaches the wire.
    """
    from sylion.aeis_v2.ontology.compiler import _quote_ident

    with pytest.raises(ValueError, match="NUL"):
        _quote_ident("foo\x00bar")


@pytest.mark.parametrize(
    "ch",
    ["\n", "\t", "\r", "\x01", "\x1f", "\x7f"],
    ids=["LF", "TAB", "CR", "SOH", "US", "DEL"],
)
def test_quote_ident_rejects_control_chars(ch):
    """W15 P1-10: ASCII + Unicode control characters are refused.

    These can break log inspection and PG's own internal parsing edge
    cases. ``unicodedata.category() == "Cc"`` captures the entire
    control class — covers ``\\n \\t \\r \\x01-\\x1f \\x7f`` (and any
    Unicode Cc beyond ASCII).
    """
    from sylion.aeis_v2.ontology.compiler import _quote_ident

    with pytest.raises(ValueError, match="control"):
        _quote_ident(f"foo{ch}bar")


def test_quote_ident_accepts_normal_identifiers():
    """W15 P1-10 regression: normal snake_case identifiers pass through.

    The new guards must not regress the happy path. A plain
    ``customer_status`` identifier should still come back wrapped in
    double quotes exactly as before.
    """
    from sylion.aeis_v2.ontology.compiler import _quote_ident

    assert _quote_ident("customer_status") == '"customer_status"'
    # A few more conventional shapes for good measure.
    assert _quote_ident("a") == '"a"'
    assert _quote_ident("orders_2026_q2") == '"orders_2026_q2"'


# --------------------------------------------------------------------------
# W15 cross-manifest orphan-relation detector (validate_relations)
# --------------------------------------------------------------------------


def _manifest_with_relation(
    type_id: str, rel_name: str, target: str
) -> ObjectTypeManifest:
    """Helper: minimal manifest carrying a single relation pointing at *target*."""
    return ObjectTypeManifest(
        api_version="sylion.aeis.v2/Object",
        kind="ObjectType",
        metadata=ObjectTypeMetadata(
            id=type_id, name_pl=type_id, name_en=type_id,
        ),
        spec=ObjectTypeSpec(
            dedicated_columns=[
                DedicatedColumn(name="title", type="text", nullable=False),
            ],
            relations=[
                Relation(name=rel_name, target=target, cardinality="many_to_one"),
            ],
        ),
    )


def test_validate_relations_empty_when_all_targets_exist():
    """validate_relations returns [] when every relation resolves to a known type."""
    from sylion.aeis_v2.ontology import validate_relations

    customer = _minimal_manifest("customer")
    project = _manifest_with_relation("project", "customer", "customer")
    vehicle = _manifest_with_relation("vehicle", "owner", "customer")
    errors = validate_relations([customer, project, vehicle])
    assert errors == []


def test_validate_relations_flags_typo_in_target():
    """validate_relations emits an error pointing at the typo'd target."""
    from sylion.aeis_v2.ontology import validate_relations

    typo_owner = _manifest_with_relation("vehicle", "owner", "customr")
    customer = _minimal_manifest("customer")
    errors = validate_relations([typo_owner, customer])
    assert len(errors) == 1
    msg = errors[0]
    assert "vehicle.relations.owner.target='customr'" in msg
    assert "type 'customr' not found" in msg


def test_validate_relations_includes_available_targets_in_message():
    """Error string must list valid alternatives so operator can find the right name."""
    from sylion.aeis_v2.ontology import validate_relations

    typo = _manifest_with_relation("vehicle", "owner", "supplier")
    customer = _minimal_manifest("customer")
    project = _minimal_manifest("project")
    errors = validate_relations([typo, customer, project])
    assert len(errors) == 1
    msg = errors[0]
    # Available alternatives appear in the error, sorted alphabetically.
    assert "Available:" in msg
    assert "customer" in msg
    assert "project" in msg
    assert "vehicle" in msg


def test_registry_reload_raises_on_orphan_relation(tmp_path, monkeypatch):
    """ObjectTypeRegistry.reload() must raise ManifestValidationError for orphan targets."""
    from sylion.aeis_v2.ontology.manifest import SKIP_RELATION_VALIDATION_ENV
    from sylion.aeis_v2.ontology.registry import ObjectTypeRegistry

    # Make sure no leaked dev-mode bypass affects this test.
    monkeypatch.delenv(SKIP_RELATION_VALIDATION_ENV, raising=False)

    bad_dir = tmp_path / "manifests"
    bad_dir.mkdir()
    # vehicle.owner -> 'customr' (typo: missing 'e')
    typo_manifest = _manifest_with_relation("vehicle", "owner", "customr")
    (bad_dir / "vehicle.yaml").write_text(
        yaml.safe_dump(typo_manifest.model_dump(by_alias=True))
    )
    # customer.yaml exists (the legit target — but typo means we still orphan)
    (bad_dir / "customer.yaml").write_text(
        yaml.safe_dump(_minimal_manifest("customer").model_dump(by_alias=True))
    )

    reg = ObjectTypeRegistry()
    reg.register_dir(bad_dir)
    # register_dir does not run cross-manifest validation; reload does.
    with pytest.raises(ManifestValidationError) as ei:
        reg.reload()
    assert "Cross-manifest validation failed" in str(ei.value)
    assert "customr" in str(ei.value)


def test_registry_reload_passes_with_skip_env_var(tmp_path, monkeypatch):
    """SYLION_SKIP_RELATION_VALIDATION=1 bypasses orphan detection (dev escape hatch)."""
    from sylion.aeis_v2.ontology.manifest import SKIP_RELATION_VALIDATION_ENV
    from sylion.aeis_v2.ontology.registry import ObjectTypeRegistry

    monkeypatch.setenv(SKIP_RELATION_VALIDATION_ENV, "1")

    bad_dir = tmp_path / "manifests"
    bad_dir.mkdir()
    typo_manifest = _manifest_with_relation("vehicle", "owner", "custmer")
    (bad_dir / "vehicle.yaml").write_text(
        yaml.safe_dump(typo_manifest.model_dump(by_alias=True))
    )

    reg = ObjectTypeRegistry()
    reg.register_dir(bad_dir)
    # Should NOT raise — env var bypass is in effect.
    n = reg.reload()
    assert n == 1
    assert "vehicle" in reg
