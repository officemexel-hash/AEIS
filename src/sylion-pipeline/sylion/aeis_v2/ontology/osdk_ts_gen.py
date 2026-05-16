"""W15 G2 OSDK-TS auto-generator -- manifest -> TypeScript interface modules.

Mirror of :mod:`sylion.aeis_v2.ontology.osdk_gen`, but emits TypeScript
``.ts`` files that frontend code can consume directly. The shape mirrors
the Python OSDK module: row-shape interface, type id / version constants,
plus a doc comment per relation FK.

For each manifest, emits a TS module under
``src/sylion-frontend/src/lib/osdk-ts/<type_id>.ts`` containing:

- ``export interface <PascalCaseTypeId>`` — row shape (dedicated columns +
  relation FKs + ``extension`` + ``created_at`` / ``updated_at``)
- ``export const <SCREAMING_SNAKE>_TYPE_ID`` — string literal of metadata.id
- ``export const <SCREAMING_SNAKE>_VERSION`` — string literal of metadata.version

Mapping rules (subset of W15 PDF §3.2):

================== ===========================================
PG type             TypeScript type
================== ===========================================
``uuid``           ``string``
``text``,          ``string``
``timestamptz``,
``date``
``integer``,       ``number``
``bigint``,
``numeric``
``boolean``        ``boolean``
``jsonb``          ``Record<string, unknown>``
``bytea``          ``string``  (base64-encoded blob in REST API)
================== ===========================================

Plus:

- ``enum=[...]`` on a column => union literal ``'a' | 'b' | 'c'``.
- ``nullable=True`` => optional modifier (``?:``) on the property.
- Relations (``many_to_one`` / ``one_to_one``) => ``<rel.name>_id?: string``
  with a doc comment describing the target type.

The generator is text-templated rather than AST-built because TypeScript
output is small and the regex assertions in tests are easier to keep
readable than AST queries. If a future field requires nested object
shapes (rare), revisit using a TS AST printer.

Phase 0 limitations:
- Frontend has no runtime client class yet — only typings emitted.
  W15 G3 will add a ``fetch``-based client mirroring :class:`CustomerClient`.
- ``bytea`` mapped to ``string`` (REST returns base64); revisit when a
  binary streaming endpoint lands.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sylion.aeis_v2.ontology.manifest import (
    DedicatedColumn,
    ObjectTypeManifest,
    Relation,
)


# --------------------------------------------------------------------------
# PostgreSQL -> TypeScript type mapping.
# --------------------------------------------------------------------------
#
# Keys here must stay aligned with `manifest.SUPPORTED_PG_TYPES`. When that
# set grows, add the new key here too — otherwise the generator emits
# ``unknown`` and tests on the new column type will surface a typo.
_PG_TO_TS: dict[str, str] = {
    "text": "string",
    "varchar": "string",       # not in current SUPPORTED_PG_TYPES but harmless
    "uuid": "string",
    "date": "string",
    "timestamptz": "string",   # ISO datetime in REST payloads
    "timestamp": "string",
    "integer": "number",
    "bigint": "number",
    "numeric": "number",
    "decimal": "number",
    "boolean": "boolean",
    "jsonb": "Record<string, unknown>",
    "bytea": "string",         # base64 in REST API
}


def _pascal_case(slug: str) -> str:
    """Convert ``snake_case`` slug to ``PascalCase`` for interface name."""
    return "".join(part.capitalize() for part in slug.split("_"))


def _screaming_snake(slug: str) -> str:
    """Convert ``snake_case`` slug to ``SCREAMING_SNAKE_CASE`` for constants."""
    return slug.upper()


def _ts_type_for_column(col: DedicatedColumn) -> str:
    """Return the TypeScript type expression for a single dedicated column.

    Resolution order:
    1. ``enum=[...]`` => union of string literals (each value single-quoted).
    2. PG type lookup in ``_PG_TO_TS``.
    3. Fallback ``unknown`` (defensive — surfaces unmapped types in review).
    """
    if col.enum:
        # Union of single-quoted string literals. Order preserved from manifest
        # so generated diffs are stable when the manifest reorders enum values.
        return " | ".join(f"'{v}'" for v in col.enum)
    return _PG_TO_TS.get(col.type, "unknown")


def _doc_comment(text: str, indent: str = "  ") -> list[str]:
    """Return JSDoc-style ``/** ... */`` comment lines, indented."""
    text = text.strip()
    if not text:
        return []
    # Single-line is more compact and tsc-friendly.
    if "\n" not in text:
        return [f"{indent}/** {text} */"]
    out = [f"{indent}/**"]
    for line in text.splitlines():
        out.append(f"{indent} * {line}")
    out.append(f"{indent} */")
    return out


@dataclass
class GeneratedTsModule:
    """Result of generating a single TypeScript OSDK module.

    Mirrors :class:`sylion.aeis_v2.ontology.osdk_gen.GeneratedModule` so
    consumers (tests, REST preview endpoint) can use the same shape.
    """

    type_id: str
    module_name: str   # filename stem without ``.ts`` (e.g. ``"customer"``)
    line_count: int
    code: str          # full TypeScript source


def generate_ts_module(manifest: ObjectTypeManifest) -> GeneratedTsModule:
    """Return TypeScript source for a manifest's frontend OSDK module.

    Output is plain ``.ts`` text — no JSX, no decorators. Should pass
    ``tsc --noEmit --strict`` once a frontend has wired up the directory
    in its tsconfig, but that gate is enforced separately at the frontend
    CI level. Here we only assert structural markers in the code string.
    """
    meta = manifest.metadata
    spec = manifest.spec
    type_id = meta.id
    iface = _pascal_case(type_id)
    const_prefix = _screaming_snake(type_id)

    cols = spec.dedicated_columns
    relations = spec.relations

    lines: list[str] = []

    # ------------------------------------------------------------------
    # Header — auto-gen marker + provenance comment.
    # ------------------------------------------------------------------
    lines.append("// AUTO-GENERATED -- do not edit manually")
    lines.append(
        f"// Generated from W15 manifest: {type_id} ({meta.version})"
    )
    lines.append("// by sylion.aeis_v2.ontology.osdk_ts_gen")
    lines.append("")

    # ------------------------------------------------------------------
    # Interface body.
    # ------------------------------------------------------------------
    # Top-of-interface doc comment uses name_en when available; fall back
    # to the slug. We avoid description_pl/en here because they can run
    # very long — keep the type declaration scannable.
    iface_doc = meta.name_en or meta.name_pl or type_id
    lines.append(f"/** {iface_doc} object type */")
    lines.append(f"export interface {iface} {{")

    # `id` is always present, never optional. UUID v4 emitted by the API.
    lines.append("  id: string;  // UUID v4")

    for col in cols:
        ts_type = _ts_type_for_column(col)
        opt = "?" if col.nullable else ""
        # Trailing comment summarises provenance: enum / PG type / dedicated.
        if col.enum:
            note = "enum from CHECK constraint"
        else:
            note = f"dedicated column ({col.type})"
        # JSDoc above the field surfaces the manifest description in IDE
        # tooltips (frontend devs see it on hover). Keep description short.
        if col.description:
            for d in _doc_comment(col.description):
                lines.append(d)
        lines.append(f"  {col.name}{opt}: {ts_type};  // {note}")

    for rel in relations:
        if rel.cardinality in {"many_to_one", "one_to_one"}:
            opt = "?" if rel.nullable else ""
            note = (
                f"FK relation: {type_id}.{rel.name} -> {rel.target} "
                f"({rel.cardinality})"
            )
            if rel.description:
                for d in _doc_comment(rel.description):
                    lines.append(d)
            lines.append(f"  {rel.name}_id{opt}: string;  // {note}")

    # JSONB extension column — always present per manifest invariant.
    ext_field = spec.jsonb_extension.field
    lines.append(
        f"  {ext_field}?: Record<string, unknown>;  // JSONB extension"
    )

    # Audit timestamps emitted by the runtime (compiler.py adds them).
    lines.append("  created_at?: string;  // ISO datetime")
    lines.append("  updated_at?: string;  // ISO datetime")

    lines.append("}")
    lines.append("")

    # ------------------------------------------------------------------
    # Module-level constants — type id + version. Useful for routing
    # tables, log tagging, and OpenAPI lookups in the frontend.
    # ------------------------------------------------------------------
    lines.append(
        f"export const {const_prefix}_TYPE_ID = '{type_id}';"
    )
    lines.append(
        f"export const {const_prefix}_VERSION = '{meta.version}';"
    )
    lines.append("")

    code = "\n".join(lines)
    return GeneratedTsModule(
        type_id=type_id,
        module_name=type_id,
        line_count=len(lines),
        code=code,
    )


def write_ts_module(manifest: ObjectTypeManifest, target_dir: str) -> str:
    """Write generated TS module to disk. Returns absolute path written.

    Idempotent — overwrites any existing ``<type_id>.ts``. The caller is
    responsible for invoking :func:`write_ts_barrel` afterwards if a
    fresh barrel is desired (``regenerate_ts_all`` does this for you).
    """
    out = Path(target_dir)
    out.mkdir(parents=True, exist_ok=True)
    mod = generate_ts_module(manifest)
    target = out / f"{mod.type_id}.ts"
    target.write_text(mod.code, encoding="utf-8")
    return str(target)


def write_ts_barrel(target_dir: str, type_ids: list[str]) -> str:
    """Write/refresh ``index.ts`` re-exporting every generated module.

    Args:
        target_dir: directory containing the per-type ``.ts`` files.
        type_ids: ordered list of type ids to re-export. The order is
            preserved verbatim — pass a sorted list for stable diffs.

    Returns:
        Absolute path to the written ``index.ts``.
    """
    out = Path(target_dir)
    out.mkdir(parents=True, exist_ok=True)
    barrel = out / "index.ts"
    lines: list[str] = [
        "// AUTO-GENERATED barrel for W15 OSDK-TS modules",
        "// Regenerate via POST /api/v1/ontology/regenerate-osdk-ts",
        "",
    ]
    for tid in type_ids:
        lines.append(f"export * from './{tid}';")
    lines.append("")
    barrel.write_text("\n".join(lines), encoding="utf-8")
    return str(barrel)


def _default_ts_target_dir() -> Path:
    """Resolve the default frontend output directory.

    Walks up from this file's location to ``src/sylion-pipeline``, then
    sideways into ``src/sylion-frontend/src/lib/osdk-ts``. We avoid
    hard-coding repo paths so the function works regardless of where the
    repo is cloned (CI, dev laptop, etc.).
    """
    # __file__ lives in src/sylion-pipeline/sylion/aeis_v2/ontology/.
    # `.parents[3]` is sylion-pipeline; `.parent` of that is `src`.
    pipeline_root = Path(__file__).resolve().parents[3]
    src_root = pipeline_root.parent
    return src_root / "sylion-frontend" / "src" / "lib" / "osdk-ts"


def regenerate_ts_all(target_dir: str | None = None) -> list[Path]:
    """Regenerate every loaded manifest's TS OSDK module + barrel.

    Args:
        target_dir: override the output directory. When ``None``, writes
            into ``src/sylion-frontend/src/lib/osdk-ts`` resolved
            relative to this file's location.

    Returns:
        List of absolute :class:`Path`s written. The barrel ``index.ts``
        is the LAST entry so callers wanting just the per-type modules
        can ``[:-1]``-slice it off. When the registry is empty, the
        barrel is still written (with no exports) and is the only entry.
    """
    from sylion.aeis_v2.ontology.registry import get_registry
    if target_dir is None:
        target_path = _default_ts_target_dir()
    else:
        target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    reg = get_registry()
    written: list[Path] = []
    type_ids: list[str] = []
    for tid in reg.list_ids():
        manifest = reg.get(tid)
        if manifest is None:
            continue
        path_str = write_ts_module(manifest, str(target_path))
        written.append(Path(path_str))
        type_ids.append(tid)

    # Barrel is regenerated from scratch each time so removed manifests
    # disappear cleanly — no stale re-exports.
    barrel_path = write_ts_barrel(str(target_path), type_ids)
    written.append(Path(barrel_path))
    return written
