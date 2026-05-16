"""W15 Ontology Manifest format — pydantic schema + loader.

Manifest jest deklaratywnym kontraktem dla object type w W15. Reprezentuje
typ obiektu który operator (Robert) chce przechowywać. Z manifestu schema
compiler generuje:

- DDL PostgreSQL (CREATE TABLE + indexes + triggers)
- REST endpoints (`/api/v1/ontology/{type_id}/...`)
- Python OSDK (klient klasyfikowany)
- Audit hooks (lineage hash chain)
- Search index (pg_trgm + opcjonalny pgvector)

Format jest celowo przedłużony żeby zmniejszyć ad-hoc decyzje przy każdym
nowym typie. Zobacz `manifests/customer.yaml` jako przykład.

Skeleton zgodny z PDF §3.2 Scope IN. Phase 0: validation + load only.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

# --------------------------------------------------------------------------
# Allowed types and enums
# --------------------------------------------------------------------------

# PostgreSQL types we support. Restrictive on purpose — PDF §3.6 R1 risk:
# "manifest schema zbyt restrykcyjny — niektóre W14 obiekty się nie wpasują".
# Mitigation: extend gradually based on real W14 migration findings.
SUPPORTED_PG_TYPES: frozenset[str] = frozenset({
    "text", "integer", "bigint", "boolean", "timestamptz", "numeric",
    "uuid", "date", "jsonb", "bytea",
})

# Cardinality between two ontology types.
CARDINALITY_TYPES: frozenset[str] = frozenset({
    "one_to_one", "one_to_many", "many_to_one", "many_to_many",
})

# What to do when target row of a relation is deleted.
ON_DELETE_TYPES: frozenset[str] = frozenset({
    "cascade", "set_null", "restrict", "no_action",
})

# Allowed D-levels (decision classification — D0 trivial → D5 critical).
D_LEVEL_PATTERN = re.compile(r"^D[0-5]$")

# Slug pattern: snake_case, alphanumeric + underscore, must start with letter.
SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

# api_version we expect in the manifest header.
API_VERSION_V2 = "sylion.aeis.v2/Object"

# --------------------------------------------------------------------------
# P1-3: YAML billion-laughs / anchor-bomb DoS guards
# --------------------------------------------------------------------------
# Typical manifests are <10 KB. 1 MB is 100x headroom for absurd legitimate
# cases (very long descriptions, large enum lists, etc.) while still capping
# the worst-case parse cost. A YAML file with anchor bombs that expands to
# billions of nodes can blow up the loader regardless of file size on disk;
# `_BoundedSafeLoader` adds a node-count cap as defence-in-depth.
MAX_MANIFEST_BYTES = 1_048_576           # 1 MB per file — typical is <10 KB
MAX_YAML_NODES = 100_000                 # billion-laughs guard

# P1-4: cap on number of manifests per directory to bound startup memory.
# 100k YAML files × ~5 KB pydantic model each ≈ 500 MB RSS at boot. The
# realistic ontology size for v2 is dozens; 1000 leaves three orders of
# magnitude of headroom while still refusing accidental import dumps or
# malicious flooding of the manifests directory.
MAX_MANIFESTS_PER_DIR = 1000


class _BoundedSafeLoader(yaml.SafeLoader):
    """SafeLoader that aborts on too many composed nodes (anchor-bomb DoS).

    P1-3 from `docs/v2/reviews/ADVERSARIAL_REVIEW_W15_compiler.md`: a
    manifest with chained YAML anchors can expand into billions of nodes
    even when the on-disk file is small. We override ``compose_node`` to
    count every composed node and raise once we exceed
    ``MAX_YAML_NODES``.

    State is class-level so it survives across the multiple
    ``compose_node`` calls of a single parse. Callers MUST invoke
    :meth:`reset` before each ``yaml.load(...)`` call. Concurrent loads
    in the same process would need thread-local state — we don't do
    concurrent manifest loads in v2, so class-level is fine.
    """

    _node_count: int = 0
    _node_limit: int = MAX_YAML_NODES

    def compose_node(self, parent, index):  # type: ignore[override]
        node = super().compose_node(parent, index)
        type(self)._node_count += 1
        if type(self)._node_count > type(self)._node_limit:
            raise yaml.YAMLError(
                f"manifest expanded to >{type(self)._node_limit} YAML nodes — "
                "refusing as anchor-bomb DoS protection (P1-3)"
            )
        return node

    @classmethod
    def reset(cls) -> None:
        """Reset the class-level node counter before a fresh load."""
        cls._node_count = 0


class ManifestValidationError(ValueError):
    """Raised when manifest fails to load or validate.

    Wraps pydantic ValidationError but uses ValueError ancestry so callers
    can catch with broad `except ValueError`. Includes manifest path in
    `path` attribute for richer error reporting in the registry loader.
    """

    def __init__(self, message: str, path: Path | None = None) -> None:
        super().__init__(message)
        self.path = path


# --------------------------------------------------------------------------
# Sub-models (compose into ObjectTypeManifest)
# --------------------------------------------------------------------------


class DedicatedColumn(BaseModel):
    """A dedicated PostgreSQL column.

    Use for fields that are queried often, indexed, or used in WHERE
    clauses. Other fields go into ``jsonb_extension`` for flexibility.
    """

    name: str
    type: str  # one of SUPPORTED_PG_TYPES
    nullable: bool = True
    indexed: bool = False           # creates btree index
    searchable: bool = False        # creates pg_trgm GIN index
    unique: bool = False            # adds UNIQUE constraint
    enum: list[str] | None = None   # adds CHECK constraint
    default: Any = None             # SQL-rendered (str → quoted, bool → true/false)
    description: str = ""

    @field_validator("name")
    @classmethod
    def _name_is_slug(cls, v: str) -> str:
        if not SLUG_PATTERN.match(v):
            raise ValueError(f"column name '{v}' must be snake_case slug")
        # Reserved names that we generate ourselves.
        if v in {"id", "created_at", "updated_at", "extension"}:
            raise ValueError(
                f"column name '{v}' is reserved (auto-generated by compiler)"
            )
        return v

    @field_validator("type")
    @classmethod
    def _type_supported(cls, v: str) -> str:
        if v not in SUPPORTED_PG_TYPES:
            raise ValueError(
                f"unsupported PG type '{v}' (allowed: {sorted(SUPPORTED_PG_TYPES)})"
            )
        return v


EXTENSION_FIELD_TYPES: frozenset[str] = frozenset({
    "string", "integer", "boolean", "float", "datetime", "array", "object",
})

EXTENSION_POLICIES: frozenset[str] = frozenset({"strict", "declared", "free"})


class ExtensionFieldDef(BaseModel):
    """Declarative schema for a single key inside the JSONB ``extension`` column.

    ADR-001 Decision #1 (hybrid strict/declared/free): each object type's
    extension JSONB gains a structured schema so write-time validation can
    catch typos, type drift, and accidentally-leaked-into-prod free-form
    payloads. The pure JSON Schema in ``JsonbExtension.schema_`` is kept for
    DDL CHECK rendering and JSON Schema-aware tooling, but for fast Pythonic
    runtime validation we want a flat list of typed declarations the
    validator can scan once.

    Attributes:
        name: snake_case key inside the ``extension`` JSONB column.
        type: one of EXTENSION_FIELD_TYPES — maps to a Python runtime check
            in :func:`extension_validator._check_field_type`.
        indexed: hint for the schema compiler to consider an expression
            index on ``(extension->>'<name>')``. Phase 0 ignored by the
            compiler; reserved for G1.
        default: Pythonic default value injected by the validator in
            ``strict`` mode when the key is absent. ``None`` means "leave
            unset" (no injection).
        description_pl: human-readable Polish description for ops/help UIs.
    """

    name: str
    type: Literal["string", "integer", "boolean", "float", "datetime", "array", "object"]
    indexed: bool = False
    default: Any = None
    description_pl: str = ""

    @field_validator("name")
    @classmethod
    def _name_is_slug(cls, v: str) -> str:
        if not SLUG_PATTERN.match(v):
            raise ValueError(f"extension_field name '{v}' must be snake_case slug")
        return v


class JsonbExtension(BaseModel):
    """JSONB extension column for free-form fields.

    Always a single column named per ``field`` (default: ``extension``).
    Restricted by an optional JSON Schema in ``schema``. Extension fields
    can be queried via JSON path ops but get no dedicated index unless
    the user adds one in `search.columns_to_index` referencing extension.<key>.

    ADR-001 #1 fields:
        policy:           ``strict`` (default) | ``declared`` | ``free``.
                          See ``extension_validator.validate_extension_payload``.
        extension_fields: declarative type schema. Required for ``strict`` if
                          callers send any payload through the validator;
                          optional but useful for ``declared``; ignored in
                          ``free``.

    The legacy ``schema_`` JSON Schema field stays — DDL/JSONSchema-aware
    code can still consume it. The new flat list is what
    ``extension_validator`` walks at write-time.
    """

    field: str = "extension"
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    policy: Literal["strict", "declared", "free"] = "strict"
    extension_fields: list[ExtensionFieldDef] = Field(default_factory=list)

    @field_validator("field")
    @classmethod
    def _field_is_slug(cls, v: str) -> str:
        if not SLUG_PATTERN.match(v):
            raise ValueError(f"jsonb field name '{v}' must be snake_case slug")
        return v

    @model_validator(mode="after")
    def _check_extension_fields_unique(self) -> "JsonbExtension":
        """Names inside ``extension_fields`` must be unique."""
        seen: set[str] = set()
        for ef in self.extension_fields:
            if ef.name in seen:
                raise ValueError(
                    f"duplicate extension_field name: '{ef.name}'"
                )
            seen.add(ef.name)
        return self


class Relation(BaseModel):
    """Relation between two ontology types.

    Compiled to:
    - ``one_to_many`` / ``many_to_one`` — FK column on the *many* side.
    - ``one_to_one`` — FK + UNIQUE.
    - ``many_to_many`` — separate join table.
    """

    name: str
    target: str  # references metadata.id of another manifest
    cardinality: str = "many_to_one"
    on_delete: str = "set_null"
    nullable: bool = True
    description: str = ""

    @field_validator("name", "target")
    @classmethod
    def _names_are_slugs(cls, v: str) -> str:
        if not SLUG_PATTERN.match(v):
            raise ValueError(f"relation name '{v}' must be snake_case slug")
        return v

    @field_validator("cardinality")
    @classmethod
    def _card_supported(cls, v: str) -> str:
        if v not in CARDINALITY_TYPES:
            raise ValueError(
                f"cardinality '{v}' invalid (allowed: {sorted(CARDINALITY_TYPES)})"
            )
        return v

    @field_validator("on_delete")
    @classmethod
    def _on_delete_supported(cls, v: str) -> str:
        if v not in ON_DELETE_TYPES:
            raise ValueError(
                f"on_delete '{v}' invalid (allowed: {sorted(ON_DELETE_TYPES)})"
            )
        return v


class AuditConfig(BaseModel):
    """Lineage / audit configuration for an object type.

    PDF §3.2: "Lineage & Events — hash-chained DAG operacji per obiekt".
    When ``hash_chain=True``, every mutation is appended to a per-object
    hash chain stored in a satellite table (``<type>_lineage``). The hash
    is `sha256(prev_hash || jsonb_canonical(diff))`.
    """

    enabled: bool = True
    track_fields: list[str] = Field(default_factory=list)
    hash_chain: bool = True


class SearchEmbeddings(BaseModel):
    """Optional pgvector embeddings configuration."""

    enabled: bool = False
    source_columns: list[str] = Field(default_factory=list)
    dim: int = 1024


class SearchConfig(BaseModel):
    """Full-text + optional vector search configuration.

    Compiled to:
    - GIN trigram index per column in ``columns_to_index``.
    - Optional ``<type>_embeddings`` table when embeddings enabled.
    """

    enabled: bool = True
    columns_to_index: list[str] = Field(default_factory=list)
    embeddings: SearchEmbeddings = Field(default_factory=SearchEmbeddings)


class ActionEffect(BaseModel):
    """Single declarative effect inside an action.

    Compiler turns this into a sequence of SQL UPDATE / INSERT or event
    bus emissions. Phase 0 supports only the simplest types.
    """

    type: Literal["update_field", "emit_event", "insert_row", "soft_delete"]
    # Flexible payload — schema depends on `type`. Validation in compiler.
    field: str | None = None
    to: Any = None
    topic: str | None = None
    payload: dict[str, Any] | None = None


class ActionDef(BaseModel):
    """Action that can be performed on an instance of this type.

    Each action is auto-generated as a POST endpoint:
    ``POST /api/v1/ontology/{type_id}/{instance_id}/actions/{action_id}``.

    PDF §3.2: "Action Types — funkcje transformujące obiekty z D-level
    mapping i HG integration".
    """

    id: str
    description_pl: str = ""
    description_en: str = ""
    d_level: str = "D2"
    hg_required: bool = False
    input_schema: dict[str, Any] | None = None
    effects: list[ActionEffect] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id_is_slug(cls, v: str) -> str:
        if not SLUG_PATTERN.match(v):
            raise ValueError(f"action id '{v}' must be snake_case slug")
        return v

    @field_validator("d_level")
    @classmethod
    def _d_level_format(cls, v: str) -> str:
        if not D_LEVEL_PATTERN.match(v):
            raise ValueError(f"d_level '{v}' must match D0-D5")
        return v


# --------------------------------------------------------------------------
# Top-level manifest models
# --------------------------------------------------------------------------


class ObjectTypeMetadata(BaseModel):
    """Metadata block of a manifest."""

    id: str
    name_pl: str
    name_en: str
    version: str = "v1.0"
    description_pl: str = ""
    description_en: str = ""
    tags: list[str] = Field(default_factory=list)
    d_level: str = "D2"

    @field_validator("id")
    @classmethod
    def _id_is_slug(cls, v: str) -> str:
        if not SLUG_PATTERN.match(v):
            raise ValueError(f"metadata.id '{v}' must be snake_case slug")
        # Avoid clashing with PostgreSQL reserved words.
        if v in {"user", "table", "select", "from", "where", "order", "group"}:
            raise ValueError(f"metadata.id '{v}' is a SQL reserved word")
        return v

    @field_validator("d_level")
    @classmethod
    def _d_level_format(cls, v: str) -> str:
        if not D_LEVEL_PATTERN.match(v):
            raise ValueError(f"d_level '{v}' must match D0-D5")
        return v


class ObjectTypeSpec(BaseModel):
    """Spec block of a manifest."""

    primary_key: str = "id"
    dedicated_columns: list[DedicatedColumn] = Field(default_factory=list)
    jsonb_extension: JsonbExtension = Field(default_factory=JsonbExtension)
    relations: list[Relation] = Field(default_factory=list)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    actions: list[ActionDef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_unique_column_names(self) -> "ObjectTypeSpec":
        """Dedicated columns + relations + jsonb field must not clash."""
        seen: set[str] = set()
        for col in self.dedicated_columns:
            if col.name in seen:
                raise ValueError(f"duplicate column name: {col.name}")
            seen.add(col.name)
        for rel in self.relations:
            # FK column will be `<rel.name>_id`. Check it doesn't clash.
            fk = f"{rel.name}_id"
            if fk in seen:
                raise ValueError(
                    f"relation '{rel.name}' generates FK '{fk}' which "
                    "clashes with a dedicated column"
                )
            seen.add(fk)
        if self.jsonb_extension.field in seen:
            raise ValueError(
                f"jsonb_extension.field '{self.jsonb_extension.field}' "
                "clashes with a dedicated column or relation FK"
            )
        return self


class ObjectTypeManifest(BaseModel):
    """Full object type manifest as loaded from a YAML file.

    Structure (also valid YAML)::

        api_version: sylion.aeis.v2/Object
        kind: ObjectType
        metadata:
          id: customer
          name_pl: Klient
          ...
        spec:
          dedicated_columns: [...]
          jsonb_extension: {...}
          ...
    """

    api_version: str
    kind: str
    metadata: ObjectTypeMetadata
    spec: ObjectTypeSpec

    @field_validator("api_version")
    @classmethod
    def _api_version_supported(cls, v: str) -> str:
        if v != API_VERSION_V2:
            raise ValueError(
                f"unsupported api_version '{v}' (expected '{API_VERSION_V2}')"
            )
        return v

    @field_validator("kind")
    @classmethod
    def _kind_supported(cls, v: str) -> str:
        if v != "ObjectType":
            raise ValueError(f"unsupported kind '{v}' (expected 'ObjectType')")
        return v


# --------------------------------------------------------------------------
# Loaders
# --------------------------------------------------------------------------


def load_manifest(path: Path | str) -> ObjectTypeManifest:
    """Load and validate a single manifest YAML file.

    P1-3 (DoS hardening): enforces ``MAX_MANIFEST_BYTES`` file-size cap
    before opening, and uses :class:`_BoundedSafeLoader` so anchor-bomb
    YAML cannot expand into millions of nodes. Any unexpected exception
    from the parser is normalised to :class:`ManifestValidationError`
    so a malicious file can't crash the loader silently.
    """
    p = Path(path)
    if not p.exists():
        raise ManifestValidationError(f"manifest not found: {p}", path=p)
    # P1-3: cap file size BEFORE opening — cheap, prevents unbounded reads.
    size = p.stat().st_size
    if size > MAX_MANIFEST_BYTES:
        raise ManifestValidationError(
            f"manifest {p} is {size} bytes; max {MAX_MANIFEST_BYTES} "
            "(P1-3 DoS guard)",
            path=p,
        )
    try:
        # P1-3: reset class-level node counter before each load.
        _BoundedSafeLoader.reset()
        with open(p, encoding="utf-8") as f:
            raw = yaml.load(f, Loader=_BoundedSafeLoader)
    except yaml.YAMLError as exc:
        raise ManifestValidationError(
            f"YAML parse error in {p}: {exc}", path=p
        ) from exc
    except Exception as exc:  # defence-in-depth: any other parse-time failure
        raise ManifestValidationError(
            f"YAML parse error in {p}: {exc}", path=p
        ) from exc
    if not isinstance(raw, dict):
        raise ManifestValidationError(
            f"manifest {p} is not a YAML object", path=p
        )
    try:
        return ObjectTypeManifest.model_validate(raw)
    except ValidationError as exc:
        raise ManifestValidationError(
            f"manifest validation failed for {p}: {exc}", path=p
        ) from exc


def load_manifest_dir(directory: Path | str) -> dict[str, ObjectTypeManifest]:
    """Load every ``*.yaml`` in a directory.

    Returns dict keyed by ``metadata.id``. Files starting with ``_`` are
    skipped (treated as index/sidecar files).

    P1-4 (DoS hardening): the candidate file count is capped at
    ``MAX_MANIFESTS_PER_DIR`` *before* any file is opened. An operator
    drop of 100k YAML files into ``manifests/`` would otherwise instantiate
    ~500 MB of pydantic models at startup (cold-start failure / DoS).
    Refusing on the directory listing keeps the costly file I/O off the
    hot path.
    """
    d = Path(directory)
    if not d.is_dir():
        raise ManifestValidationError(f"not a directory: {d}", path=d)
    candidates = sorted(
        f for f in d.glob("*.yaml") if not f.name.startswith("_")
    )
    if len(candidates) > MAX_MANIFESTS_PER_DIR:
        raise ManifestValidationError(
            f"directory {d} contains {len(candidates)} manifests; "
            f"max is {MAX_MANIFESTS_PER_DIR} (P1-4 startup-memory guard)",
            path=d,
        )
    out: dict[str, ObjectTypeManifest] = {}
    for f in candidates:
        m = load_manifest(f)
        if m.metadata.id in out:
            raise ManifestValidationError(
                f"duplicate metadata.id '{m.metadata.id}' (also in "
                f"{out[m.metadata.id]})",
                path=f,
            )
        out[m.metadata.id] = m
    return out


# --------------------------------------------------------------------------
# W15 cross-manifest validation: orphan-relation detector
# --------------------------------------------------------------------------

# Env-var escape hatch — when set to "1", :func:`validate_relations` returns
# an empty list regardless of orphan relations. Use ONLY for dev-mode work
# where you intentionally have a partially-loaded ontology (e.g. iterating
# on one manifest at a time without all dependencies present). Production
# deployments must NEVER set this — orphan FKs surface at runtime with an
# unhelpful KeyError or as a delayed PG constraint violation.
SKIP_RELATION_VALIDATION_ENV = "SYLION_SKIP_RELATION_VALIDATION"


def validate_relations(manifests: list[ObjectTypeManifest]) -> list[str]:
    """Cross-manifest validation: every ``Relation.target`` must reference a known type.

    The single-manifest validators in :class:`Relation` and :class:`ObjectTypeSpec`
    only check shape — they cannot know whether ``target='customr'`` (typo)
    actually corresponds to a loaded type because at parse time only ONE
    manifest is in scope. After the registry has loaded every manifest, we
    have full knowledge of valid type ids and can flag orphans up-front
    instead of letting them explode at DDL compile or FK enforcement time.

    Args:
        manifests: every loaded :class:`ObjectTypeManifest`. Typically passed as
            ``list(registry._by_id.values())`` from :meth:`ObjectTypeRegistry.reload`.

    Returns:
        List of human-readable error strings. Empty list when every relation
        target resolves to a known type. Each string carries enough context
        (source type, relation name, bad target, available alternatives) for
        an operator to fix the typo without reading the registry source.

    Escape hatch:
        Setting environment variable ``SYLION_SKIP_RELATION_VALIDATION=1``
        forces the function to return ``[]`` unconditionally. This is a
        "we know what we're doing" override for dev-mode partial loading
        (e.g. iterating on a single new manifest without its targets yet
        present). Production must never set this — orphan targets surface
        as confusing KeyErrors at compile time or as runtime FK violations.

    Example error string::

        `customer.relations.owner.target='supplier'` — type 'supplier' not
        found in registry. Available: [customer, project, vehicle].
    """
    if os.environ.get(SKIP_RELATION_VALIDATION_ENV) == "1":
        return []

    known_ids: set[str] = {m.metadata.id for m in manifests}
    errors: list[str] = []
    available_str = ", ".join(sorted(known_ids)) or "<none>"

    for manifest in manifests:
        type_id = manifest.metadata.id
        for rel in manifest.spec.relations:
            if rel.target not in known_ids:
                errors.append(
                    f"`{type_id}.relations.{rel.name}.target='{rel.target}'` — "
                    f"type '{rel.target}' not found in registry. "
                    f"Available: [{available_str}]."
                )
                continue
            # Orphan back-reference detection: future-proofing for
            # ``inverse_name`` / ``back_ref`` style fields. Phase 0 Relation
            # does not yet declare such a field, so this branch is a no-op
            # in practice — but if either the explicit attribute or a hint
            # in ``description`` ever appears, we validate it here.
            inverse_name = getattr(rel, "inverse_name", None) or getattr(
                rel, "back_ref", None
            )
            if inverse_name:
                target_manifest = next(
                    (m for m in manifests if m.metadata.id == rel.target), None
                )
                if target_manifest is None:
                    continue  # already reported as orphan target above
                target_rel_names = {r.name for r in target_manifest.spec.relations}
                if inverse_name not in target_rel_names:
                    errors.append(
                        f"`{type_id}.relations.{rel.name}.inverse_name="
                        f"'{inverse_name}'` — target type '{rel.target}' has "
                        f"no inbound relation named '{inverse_name}'. "
                        f"Defined relations on '{rel.target}': "
                        f"[{', '.join(sorted(target_rel_names)) or '<none>'}]."
                    )

    return errors
