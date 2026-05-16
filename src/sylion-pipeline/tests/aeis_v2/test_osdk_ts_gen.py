"""Tests for sylion.aeis_v2.ontology.osdk_ts_gen — W15 G2 frontend OSDK.

Mirrors ``test_ontology_osdk.py`` but for the TypeScript generator.
We assert structural markers in the emitted ``.ts`` text rather than
parsing through a full TS AST — keeping tests self-contained and not
dependent on a Node toolchain.

Coverage:
- Header + interface + constants markers present.
- ``UUID`` -> ``string`` mapping.
- ``enum=[...]`` -> union of string literals.
- ``nullable=True`` -> ``?:`` modifier on the property.
- ``jsonb`` extension -> ``Record<string, unknown>``.
- ``regenerate_ts_all`` writes per-type files plus ``index.ts`` barrel.
- Many-to-one relations -> ``<rel>_id?: string`` plus doc note.
- TS smoke: every generated header has the expected provenance comments.
"""
from __future__ import annotations

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
    generate_ts_module,
    regenerate_ts_all,
    write_ts_barrel,
    write_ts_module,
)
from sylion.aeis_v2.ontology.manifest import ActionEffect


def _customer_manifest() -> ObjectTypeManifest:
    """Representative manifest covering UUID + enum + nullable + relation."""
    return ObjectTypeManifest(
        api_version="sylion.aeis.v2/Object",
        kind="ObjectType",
        metadata=ObjectTypeMetadata(
            id="customer",
            name_pl="Klient",
            name_en="Customer",
            version="0.1.0",
        ),
        spec=ObjectTypeSpec(
            dedicated_columns=[
                # UUID column to verify uuid -> string mapping.
                DedicatedColumn(name="external_uuid", type="uuid", nullable=False),
                # Required text column (no `?:`).
                DedicatedColumn(name="title", type="text", nullable=False),
                # Optional text column (`?:`).
                DedicatedColumn(name="email", type="text", nullable=True),
                # Enum column to verify union literal generation.
                DedicatedColumn(
                    name="status",
                    type="text",
                    nullable=True,
                    enum=["active", "inactive"],
                ),
                # Numeric column to verify integer -> number mapping.
                DedicatedColumn(name="visits", type="integer", nullable=True),
            ],
            relations=[
                Relation(
                    name="owner",
                    target="customer",
                    cardinality="many_to_one",
                    on_delete="set_null",
                    nullable=True,
                ),
            ],
            actions=[
                ActionDef(
                    id="archive_customer",
                    description_pl="Archiwizuje klienta.",
                    description_en="Archives the customer.",
                    d_level="D2",
                    hg_required=False,
                    effects=[
                        ActionEffect(type="update_field", field="status", to="archived"),
                    ],
                ),
            ],
        ),
    )


# --------------------------------------------------------------------------
# 1. Header + interface + constants markers.
# --------------------------------------------------------------------------


def test_generate_ts_module_emits_valid_typescript_interface_header() -> None:
    mod = generate_ts_module(_customer_manifest())
    assert mod.type_id == "customer"
    assert mod.module_name == "customer"
    # Provenance markers — used by frontend code review.
    assert "AUTO-GENERATED" in mod.code
    assert "sylion.aeis_v2.ontology.osdk_ts_gen" in mod.code
    # Interface declaration (PascalCase) and constants must both be present.
    assert "export interface Customer" in mod.code, mod.code
    assert "export const CUSTOMER_TYPE_ID = 'customer';" in mod.code
    assert "export const CUSTOMER_VERSION = '0.1.0';" in mod.code
    assert mod.line_count > 0


# --------------------------------------------------------------------------
# 2. UUID -> string mapping.
# --------------------------------------------------------------------------


def test_generate_ts_module_maps_uuid_to_string() -> None:
    mod = generate_ts_module(_customer_manifest())
    # `external_uuid` is required -> no `?` modifier; type `string`.
    pat = re.compile(r"^\s*external_uuid: string;.*$", re.MULTILINE)
    assert pat.search(mod.code), (
        f"missing `external_uuid: string` field in:\n{mod.code}"
    )


# --------------------------------------------------------------------------
# 3. enum -> TypeScript union literal.
# --------------------------------------------------------------------------


def test_generate_ts_module_maps_enum_to_union_type() -> None:
    mod = generate_ts_module(_customer_manifest())
    # `status?: 'active' | 'inactive'` — must be optional (nullable=True)
    # and emit a string-literal union, NOT plain `string`.
    pat = re.compile(
        r"^\s*status\?: 'active' \| 'inactive';.*$",
        re.MULTILINE,
    )
    assert pat.search(mod.code), (
        f"missing union-type `status` field in:\n{mod.code}"
    )
    # Should NOT collapse to plain `string` somewhere else.
    assert "status: string;" not in mod.code
    assert "status?: string;" not in mod.code


# --------------------------------------------------------------------------
# 4. nullable -> `?:` modifier.
# --------------------------------------------------------------------------


def test_generate_ts_module_marks_nullable_with_question_mark() -> None:
    mod = generate_ts_module(_customer_manifest())
    # Required column has no `?`.
    assert re.search(r"^\s*title: string;", mod.code, re.MULTILINE), mod.code
    # Optional column has `?`.
    assert re.search(r"^\s*email\?: string;", mod.code, re.MULTILINE), mod.code
    # Optional integer column also gets `?:` and `number`.
    assert re.search(r"^\s*visits\?: number;", mod.code, re.MULTILINE), mod.code


# --------------------------------------------------------------------------
# 5. JSONB extension -> Record<string, unknown>.
# --------------------------------------------------------------------------


def test_generate_ts_module_maps_jsonb_extension_to_record_unknown() -> None:
    mod = generate_ts_module(_customer_manifest())
    # The default `extension` JSONB column is always present in the row
    # interface and must be typed as Record<string, unknown>.
    assert re.search(
        r"^\s*extension\?: Record<string, unknown>;", mod.code, re.MULTILINE
    ), f"missing `extension?: Record<string, unknown>` in:\n{mod.code}"


# --------------------------------------------------------------------------
# 6. regenerate_ts_all writes per-type files + index.ts barrel.
# --------------------------------------------------------------------------


def test_regenerate_ts_all_writes_files_and_barrel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the registry is empty, only `index.ts` is written. When it has
    manifests, one ``.ts`` per type plus the barrel.

    We don't depend on the real registry's contents — we patch
    ``get_registry`` to return a small fake so the test is hermetic.
    """
    customer = _customer_manifest()

    class _FakeRegistry:
        def list_ids(self) -> list[str]:
            return ["customer"]

        def get(self, tid: str) -> ObjectTypeManifest | None:
            return customer if tid == "customer" else None

    fake_reg = _FakeRegistry()
    monkeypatch.setattr(
        "sylion.aeis_v2.ontology.registry.get_registry",
        lambda: fake_reg,
    )

    written = regenerate_ts_all(target_dir=str(tmp_path))
    # Expect: customer.ts + index.ts.
    assert len(written) == 2, written
    names = {p.name for p in written}
    assert "customer.ts" in names
    assert "index.ts" in names

    barrel = tmp_path / "index.ts"
    barrel_text = barrel.read_text(encoding="utf-8")
    assert "export * from './customer';" in barrel_text
    assert "AUTO-GENERATED barrel" in barrel_text

    customer_ts = tmp_path / "customer.ts"
    customer_text = customer_ts.read_text(encoding="utf-8")
    assert "export interface Customer" in customer_text
    assert "export const CUSTOMER_TYPE_ID = 'customer';" in customer_text


# --------------------------------------------------------------------------
# Bonus: relation FK columns.
# --------------------------------------------------------------------------


def test_relation_fk_emitted_with_doc_comment() -> None:
    mod = generate_ts_module(_customer_manifest())
    # `owner` is many_to_one and nullable=True -> owner_id?: string with FK note.
    assert re.search(
        r"^\s*owner_id\?: string;\s*//\s*FK relation: customer\.owner -> customer",
        mod.code,
        re.MULTILINE,
    ), f"missing owner_id FK field in:\n{mod.code}"


# --------------------------------------------------------------------------
# Bonus: write_ts_module + write_ts_barrel idempotence + filenames.
# --------------------------------------------------------------------------


def test_write_ts_module_creates_dotts_file(tmp_path: Path) -> None:
    target = write_ts_module(_customer_manifest(), str(tmp_path))
    p = Path(target)
    assert p.exists(), f"generated file {p} not on disk"
    assert p.suffix == ".ts"
    assert p.name == "customer.ts"
    text = p.read_text(encoding="utf-8")
    assert "export interface Customer" in text
    # Idempotency — second write overwrites cleanly with identical content.
    target2 = write_ts_module(_customer_manifest(), str(tmp_path))
    assert target == target2
    assert Path(target2).read_text(encoding="utf-8") == text


def test_write_ts_barrel_emits_sorted_exports(tmp_path: Path) -> None:
    # Pass a deliberate order to confirm the barrel preserves it.
    barrel_path = write_ts_barrel(str(tmp_path), ["alpha", "beta", "gamma"])
    text = Path(barrel_path).read_text(encoding="utf-8")
    # The export order must match the input list order verbatim.
    idx_alpha = text.find("export * from './alpha';")
    idx_beta = text.find("export * from './beta';")
    idx_gamma = text.find("export * from './gamma';")
    assert 0 <= idx_alpha < idx_beta < idx_gamma, text


def test_pascal_case_interface_name_for_multi_word_slug() -> None:
    """`premium_customer` -> `PremiumCustomer` interface and PREMIUM_CUSTOMER_TYPE_ID."""
    manifest = _customer_manifest()
    manifest.metadata.id = "premium_customer"
    mod = generate_ts_module(manifest)
    assert "export interface PremiumCustomer" in mod.code
    assert "PREMIUM_CUSTOMER_TYPE_ID = 'premium_customer';" in mod.code
    assert "PREMIUM_CUSTOMER_VERSION" in mod.code
