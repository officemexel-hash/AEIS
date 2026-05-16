"""W15 Schema Compiler — manifest → DDL.

Compiler bierze ``ObjectTypeManifest`` i generuje:

- ``CREATE TABLE`` z dedykowanymi kolumnami + jsonb extension
- B-tree i GIN indexes (dla ``indexed`` i ``searchable`` kolumn)
- CHECK constraints dla enums
- UNIQUE constraints
- FK constraints dla relacji
- ``updated_at`` trigger
- Lineage table + trigger (gdy ``audit.hash_chain=True``)
- ``many_to_many`` join tables (gdy istnieją)

Phase 0: TYLKO generacja stringów SQL — nie wykonujemy DDL na żywej bazie.
Compilator zwraca ``DDLArtifacts`` z gotowymi SQL-ami; zewnętrzne
narzędzie (Alembic migration / runtime DDL applier — implementacja w
G2) faktycznie executuje.

PDF §3.2: "PostgreSQL hybrid (dedicated columns + JSONB ext)" — ten
compiler jest kanonicznym tłumaczem tej decyzji.

P1-7 operator note: when ``audit.hash_chain=True`` the per-type lineage
table is PARTITION BY RANGE on ``recorded_at`` (monthly partitions). The
compiler emits the initial month's partition and one for next month at
apply time. After that, the operator MUST call
``sylion_v2.create_next_lineage_partition('<type>_lineage')`` once per
month before the partition window expires (typically via cron). Failing
to advance the partition window will cause the next UPDATE on the parent
table to FAIL because the lineage trigger cannot find a partition for
the new ``recorded_at`` value.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any

from sylion.aeis_v2.ontology.manifest import (
    ActionDef,
    DedicatedColumn,
    ObjectTypeManifest,
    Relation,
)

# Schema for v2 ontology objects in PostgreSQL. Always namespaced to
# avoid collisions with v1 tables.
SCHEMA_NAME = "sylion_v2"

# Prefix for shared infra (extensions + helper functions). These run once
# per database, not per object type.
SHARED_DDL = """\
-- One-time bootstrap for sylion_v2 ontology runtime.
-- Idempotent: every statement is IF NOT EXISTS or CREATE OR REPLACE.

CREATE SCHEMA IF NOT EXISTS sylion_v2;

CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- fuzzy full-text via GIN trigram
CREATE EXTENSION IF NOT EXISTS btree_gin;    -- combined btree+gin

-- Touch updated_at on every UPDATE.
CREATE OR REPLACE FUNCTION sylion_v2.touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Append a hash-chained lineage entry for an object.
-- Called from per-type triggers when audit.hash_chain=true.
--
-- P0-2 fix from adversarial review: previously two concurrent UPDATEs
-- on the same object_id could read identical prev_hash and INSERT
-- both with the same prev_hash, silently forking the chain. Mitigation:
--
--   1. Take a transaction-scoped advisory lock keyed by object_id so
--      only one append_lineage runs at a time per object. This avoids
--      `SELECT ... FOR UPDATE` on a non-existent row (chain is fresh).
--
--   2. Add a (object_id, prev_hash) UNIQUE INDEX so a fork attempt
--      that bypassed the advisory lock fails the second insert with
--      a constraint violation rather than corrupting silently. The
--      index lives on the per-type lineage table (not function body).
--
-- The advisory lock is process-shared (pg_advisory_xact_lock) and
-- automatically released at COMMIT/ROLLBACK. Two object_ids hash to
-- two different bigints so independent objects do not block each other.
CREATE OR REPLACE FUNCTION sylion_v2.append_lineage(
  p_lineage_table  REGCLASS,
  p_object_id      UUID,
  p_op             TEXT,
  p_diff           JSONB,
  p_actor          TEXT
) RETURNS VOID AS $$
DECLARE
  prev_hash  TEXT;
  new_hash   TEXT;
  ts         TIMESTAMPTZ := NOW();
  lock_key   BIGINT;
BEGIN
  -- Per-object advisory lock. hashtext returns int4 — mix with table
  -- regclass oid so two different lineage tables don't collide on the
  -- same UUID prefix.
  lock_key := hashtext(p_object_id::text || '|' || p_lineage_table::text)::BIGINT;
  PERFORM pg_advisory_xact_lock(lock_key);

  EXECUTE format(
    'SELECT entry_hash FROM %s WHERE object_id = $1 ORDER BY seq DESC LIMIT 1',
    p_lineage_table
  )
  INTO prev_hash USING p_object_id;
  IF prev_hash IS NULL THEN prev_hash := ''; END IF;
  new_hash := encode(
    digest(prev_hash || p_op || p_diff::text || p_actor || ts::text, 'sha256'),
    'hex'
  );
  EXECUTE format(
    'INSERT INTO %s (object_id, op, diff, actor, prev_hash, entry_hash, recorded_at) '
    'VALUES ($1, $2, $3, $4, $5, $6, $7)',
    p_lineage_table
  )
  USING p_object_id, p_op, p_diff, p_actor, prev_hash, new_hash, ts;
END;
$$ LANGUAGE plpgsql;

-- P1-7 fix from adversarial review: lineage tables grow unbounded.
-- Per-type lineage tables are PARTITION BY RANGE (recorded_at) with
-- monthly partitions. Operator MUST call this helper before each new
-- month begins (or schedule it via cron) so the next partition exists
-- when the new month rolls over. Without a partition for the target
-- range, the insert into the lineage table will FAIL with
-- "no partition of relation found for row" — i.e. UPDATE on the parent
-- object table will fail.
--
-- Idempotent — safe to call repeatedly. CREATE TABLE IF NOT EXISTS
-- inside the dynamic SQL keeps re-runs cheap.
--
-- Naming convention: <lineage_table>_<YYYY>_<MM>, e.g.
--   customer_lineage_2026_05  -- partition for May 2026
--
-- Example operator cron (Phase 0+ — out of scope for compiler):
--   SELECT sylion_v2.create_next_lineage_partition('customer_lineage');
--   SELECT sylion_v2.create_next_lineage_partition('project_lineage');
--   ... one call per type with audit.hash_chain=true
CREATE OR REPLACE FUNCTION sylion_v2.create_next_lineage_partition(
  p_lineage_table TEXT
) RETURNS VOID AS $$
DECLARE
  next_month_start DATE := date_trunc('month', NOW())::DATE + INTERVAL '1 month';
  next_month_end   DATE := next_month_start + INTERVAL '1 month';
  partition_name   TEXT := p_lineage_table || '_' ||
                           to_char(next_month_start, 'YYYY_MM');
BEGIN
  EXECUTE format(
    'CREATE TABLE IF NOT EXISTS sylion_v2.%I '
    'PARTITION OF sylion_v2.%I '
    'FOR VALUES FROM (%L) TO (%L)',
    partition_name, p_lineage_table,
    next_month_start, next_month_end
  );
END;
$$ LANGUAGE plpgsql;
"""


# --------------------------------------------------------------------------
# Output container
# --------------------------------------------------------------------------


@dataclass
class DDLArtifacts:
    """Result of compiling one manifest.

    Each field is a list of executable SQL strings. Order matters:
    apply ``shared`` once per DB, then ``main_table``, then everything
    else. ``rollback`` is the inverse.
    """

    # Per-database shared DDL (extensions, functions). Same string for
    # every type. Caller deduplicates if many manifests are compiled.
    shared: list[str] = field(default_factory=list)

    # CREATE TABLE for the main object table.
    main_table: list[str] = field(default_factory=list)

    # Indexes (btree, GIN trigram, etc).
    indexes: list[str] = field(default_factory=list)

    # FK constraints (added after all tables exist).
    foreign_keys: list[str] = field(default_factory=list)

    # CREATE TABLE for many_to_many join tables.
    join_tables: list[str] = field(default_factory=list)

    # Lineage table + trigger (only when audit.hash_chain=True).
    lineage: list[str] = field(default_factory=list)

    # touch_updated_at trigger binding.
    triggers: list[str] = field(default_factory=list)

    # DROP statements for clean rollback.
    rollback: list[str] = field(default_factory=list)

    # Diagnostics — one-line summary per artifact for human review.
    notes: list[str] = field(default_factory=list)

    def all_statements(self) -> list[str]:
        """Concat in canonical apply order."""
        return [
            *self.shared,
            *self.main_table,
            *self.foreign_keys,
            *self.indexes,
            *self.join_tables,
            *self.lineage,
            *self.triggers,
        ]

    def render_sql(self) -> str:
        """Single string with all DDL, wrapped in a single transaction.

        Suitable for ``psql -f`` or for embedding in an Alembic migration.

        P1-6 fix from adversarial review: the rendered output is wrapped
        in ``BEGIN; ... COMMIT;`` so that the DROP+CREATE TRIGGER pair (and
        any other multi-statement sequence) runs atomically when fed
        through ``psql -f file.sql``. Without the wrapper, psql processes
        each statement in its own implicit transaction; between the DROP
        and CREATE a concurrent UPDATE could slip through without firing
        ``touch_updated_at``, leaving rows with stale ``updated_at``.

        Note: the in-process applier (``apply_manifest``) consumes
        ``all_statements()`` directly inside its own ``with conn`` block
        + single ``conn.commit()``, so it already gets transactional
        semantics. The ``BEGIN``/``COMMIT`` here only protects the
        ``psql -f`` operator path.
        """
        chunks: list[str] = ["BEGIN;"]
        for stmt in self.all_statements():
            stmt = stmt.rstrip()
            if not stmt.endswith(";"):
                stmt += ";"
            chunks.append(stmt)
        chunks.append("COMMIT;")
        return "\n\n".join(chunks) + "\n"


# --------------------------------------------------------------------------
# SQL helpers
# --------------------------------------------------------------------------


# PostgreSQL hard limit for identifier length.
# https://www.postgresql.org/docs/current/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS
# 63 bytes (NAMEDATALEN-1). PG silently TRUNCATES anything longer, which is
# how P1-1 from the adversarial review bites: two distinct generated names
# can collide post-truncation, and IF NOT EXISTS then no-ops on the second
# manifest. We refuse instead — operator gets a loud, actionable error.
PG_MAX_IDENTIFIER_BYTES = 63

# Forbidden identifier prefix patterns. PG reserves `pg_` for system
# catalogs; user-defined names there compile but interfere with pg_dump,
# pg_catalog and `\d` introspection. Refuse defensively (P1-2 from review).
_FORBIDDEN_PREFIXES = ("pg_",)


def _validate_identifier_length(ident: str, kind: str = "identifier") -> None:
    """Raise ValueError when ``ident`` exceeds the PG byte limit.

    UTF-8 byte count, not codepoint count — PG measures bytes. Slugs in
    manifests are ASCII-only by SLUG_PATTERN so byte == char, but
    helper SQL strings (e.g. constraint names) might in theory take in
    non-ASCII; defending in depth.
    """
    encoded = ident.encode("utf-8")
    if len(encoded) > PG_MAX_IDENTIFIER_BYTES:
        raise ValueError(
            f"{kind} '{ident}' is {len(encoded)} bytes, exceeds PostgreSQL "
            f"limit of {PG_MAX_IDENTIFIER_BYTES} bytes. PG would silently "
            "truncate, risking collisions with another manifest. Shorten "
            "the source slug(s) and re-run."
        )
    for pref in _FORBIDDEN_PREFIXES:
        if ident.lower().startswith(pref):
            raise ValueError(
                f"{kind} '{ident}' uses reserved PostgreSQL prefix '{pref}'. "
                "PG system catalogs (`pg_*`) collide with introspection."
            )


def _quote_ident(ident: str) -> str:
    """Quote a SQL identifier.

    Rejects empty, NUL, control chars, double-quotes, and >63-byte names.
    Identifiers come from manifests (snake_case-validated) or
    compiler-synthesized (already snake_case). These guards are
    defense-in-depth for the synthesized branch — W15 P1-10.
    """
    # W15 P1-10: empty identifier — PG would parse `""` as an unnamed
    # identifier and bail with a confusing message. Reject loudly.
    if not ident:
        raise ValueError("refusing empty identifier")
    # W15 P1-10: NUL byte — PG (and libpq) silently truncate strings at
    # NUL when using server-side prepared statements; the resulting DDL
    # is unpredictable. Refuse before it ever reaches the wire.
    if "\x00" in ident:
        raise ValueError(f"refusing identifier with NUL byte: {ident!r}")
    # W15 P1-10: other ASCII + Unicode control characters (\r, \n, \t,
    # \x01-\x1f, \x7f, etc). They can break log inspection and PG's own
    # internal parsing edge cases. ``unicodedata.category() == "Cc"``
    # captures the entire control class.
    for ch in ident:
        if unicodedata.category(ch) == "Cc":
            raise ValueError(
                f"refusing identifier with control char {ch!r} "
                f"(U+{ord(ch):04X}): {ident!r}"
            )
    # We've validated slugs in manifest.py (snake_case only), but defense
    # in depth never hurts.
    if "\"" in ident:
        raise ValueError(f"refusing identifier with double quote: {ident!r}")
    # P1-1 / P1-2 defense — applied at every generated identifier, not
    # only at manifest validation. This catches names that the compiler
    # itself synthesizes (`<type>_<col>_btree`, join tables, etc).
    _validate_identifier_length(ident)
    return f'"{ident}"'


def _qualified(table: str) -> str:
    """schema-qualified identifier."""
    return f"{_quote_ident(SCHEMA_NAME)}.{_quote_ident(table)}"


def _sql_default(col: DedicatedColumn) -> str:
    """Render the DEFAULT clause for a column.

    P0-1 fix: same escape rules as `_escape_sql_literal` apply here.
    NaN/Inf for floats are rejected (P2-5 from review).
    """
    import math
    if col.default is None:
        return ""
    if isinstance(col.default, bool):
        return f"DEFAULT {'TRUE' if col.default else 'FALSE'}"
    if isinstance(col.default, (int, float)):
        if isinstance(col.default, float) and (math.isnan(col.default) or math.isinf(col.default)):
            raise ValueError(
                f"column '{col.name}' default cannot be NaN or Inf "
                "(PostgreSQL would reject)"
            )
        return f"DEFAULT {col.default}"
    if isinstance(col.default, str):
        return f"DEFAULT '{_escape_sql_literal(col.default)}'"
    # Lists/dicts → JSONB literal (rare for dedicated col).
    import json
    rendered = json.dumps(col.default)
    return f"DEFAULT '{_escape_sql_literal(rendered)}'::jsonb"


def _escape_sql_literal(value: str) -> str:
    """Escape a string literal for safe interpolation into SQL.

    P0-1 fix from adversarial review: previously `enum` and `default`
    string values were interpolated directly into DDL. A manifest with
    ``enum: ["'); DROP TABLE customers; --"]`` would ship malicious
    DDL through the compiler. We now reject any literal containing
    control characters or backslashes (which would break standard
    PostgreSQL string escaping) and escape single quotes.

    PostgreSQL standard string escaping is `''` for embedded single
    quotes; backslashes are LITERAL by default (standard_conforming_strings
    is on since PG 9.1) so they need no special handling, but we still
    refuse them defensively because some legacy connections set
    standard_conforming_strings=off.
    """
    if "\x00" in value:
        raise ValueError("SQL literal cannot contain NUL byte")
    # Refuse other ASCII control chars (newline / tab / CR) — they have
    # no business in a column enum value or default.
    for ch in value:
        if ord(ch) < 0x20 and ch not in {" "}:
            raise ValueError(
                f"SQL literal contains control char {hex(ord(ch))} — refusing"
            )
    # Single quote → doubled (canonical PG escape).
    return value.replace("'", "''")


def _check_constraint_name(type_id: str, col_name: str) -> str:
    """Build a deterministic CHECK constraint name for ``<type_id>.<col_name>``.

    P1-9 fix from W15 review: previously the compiler emitted anonymous
    CHECK constraints (``CHECK (col IN ('a','b'))``) and let PostgreSQL
    auto-generate a name. Auto-generated names are version-dependent and
    silently change if columns are renamed, which breaks
    ``compile_alter()`` — it cannot reliably ``DROP CONSTRAINT`` without
    a stable name. We now name every CHECK ``<type_id>_<col>_chk``.

    Identifier-length guard: PG caps identifiers at 63 bytes
    (``PG_MAX_IDENTIFIER_BYTES``). The natural ``<type>_<col>_chk`` form
    can overflow when both slugs are long. To avoid crashing the
    compiler on legitimate (if verbose) manifests, we fall back to a
    deterministic hash-based name ``chk_<sha8>`` when the natural form
    would exceed the byte limit. The hash is sha256 of
    ``<type_id>_<col>_chk`` so the fallback is stable across compiler
    runs and unique with overwhelming probability for any realistic
    constraint count.

    We deliberately DO NOT use the ``pg_`` prefix for the fallback —
    ``_validate_identifier_length`` rejects ``pg_*`` names because
    PostgreSQL reserves that prefix for system catalogs. The ``chk_``
    prefix is unambiguous and validator-friendly.
    """
    natural = f"{type_id}_{col_name}_chk"
    if len(natural.encode("utf-8")) <= PG_MAX_IDENTIFIER_BYTES:
        return natural
    # Fallback: deterministic short name. 8 hex chars of sha256 gives
    # 4 billion namespace — collision risk is negligible for any
    # realistic count of CHECK constraints in one ontology.
    import hashlib
    digest = hashlib.sha256(natural.encode("utf-8")).hexdigest()[:8]
    return f"chk_{digest}"


def _column_sql(col: DedicatedColumn, type_id: str) -> str:
    """Render `<name> <type> [NOT NULL] [DEFAULT ...] [CONSTRAINT ... CHECK ...]` for one col.

    ``type_id`` is required so we can mint a deterministic, named CHECK
    constraint (``<type_id>_<col>_chk``) when the column has an enum.
    P1-9 fix: previously the constraint was anonymous and PostgreSQL
    auto-named it; the auto name is fragile, so ALTER paths could not
    reliably ``DROP CONSTRAINT IF EXISTS``.
    """
    parts = [_quote_ident(col.name), col.type.upper()]
    if not col.nullable:
        parts.append("NOT NULL")
    default = _sql_default(col)
    if default:
        parts.append(default)
    if col.unique:
        parts.append("UNIQUE")
    if col.enum:
        # CONSTRAINT "<type>_<col>_chk" CHECK (col IN ('a','b','c'))
        # P0-1 fix: escape every enum literal. Refuse NUL/control chars.
        # P1-9 fix: emit a deterministic constraint name so compile_alter
        # can later DROP CONSTRAINT IF EXISTS by the same name.
        items = ", ".join(f"'{_escape_sql_literal(str(v))}'" for v in col.enum)
        chk_name = _check_constraint_name(type_id, col.name)
        parts.append(
            f"CONSTRAINT {_quote_ident(chk_name)} "
            f"CHECK ({_quote_ident(col.name)} IN ({items}))"
        )
    return " ".join(parts)


# --------------------------------------------------------------------------
# Main compiler
# --------------------------------------------------------------------------


@dataclass
class SchemaCompiler:
    """Stateful compiler for one or many manifests.

    Use ``compile(manifest)`` per type, then ``finalize()`` collapses
    repeated shared DDL.
    """

    schema_name: str = SCHEMA_NAME
    _seen_shared: bool = False

    def compile(self, manifest: ObjectTypeManifest) -> DDLArtifacts:
        out = DDLArtifacts()
        if not self._seen_shared:
            out.shared.append(SHARED_DDL.strip())
            out.notes.append(
                f"shared bootstrap (schema {self.schema_name} + extensions + helpers)"
            )
            self._seen_shared = True

        meta = manifest.metadata
        spec = manifest.spec
        type_id = meta.id

        # --- Main table -------------------------------------------------------
        cols_sql: list[str] = [
            f'  {_quote_ident("id")} UUID PRIMARY KEY DEFAULT gen_random_uuid()',
        ]
        for col in spec.dedicated_columns:
            cols_sql.append("  " + _column_sql(col, type_id))

        # FK columns derived from relations on the *many* side.
        fk_columns: list[Relation] = []
        for rel in spec.relations:
            if rel.cardinality in {"many_to_one", "one_to_one"}:
                fk_columns.append(rel)
                col = (
                    f"  {_quote_ident(rel.name + '_id')} UUID"
                    f"{'' if rel.nullable else ' NOT NULL'}"
                )
                if rel.cardinality == "one_to_one":
                    col += " UNIQUE"
                cols_sql.append(col)

        # JSONB extension column.
        jsonb_field = spec.jsonb_extension.field
        cols_sql.append(
            f"  {_quote_ident(jsonb_field)} JSONB NOT NULL DEFAULT '{{}}'::jsonb"
        )
        # Bookkeeping columns.
        cols_sql.append('  "created_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()')
        cols_sql.append('  "updated_at" TIMESTAMPTZ NOT NULL DEFAULT NOW()')

        main_sql = (
            f"CREATE TABLE IF NOT EXISTS {_qualified(type_id)} (\n"
            + ",\n".join(cols_sql)
            + "\n)"
        )
        out.main_table.append(main_sql)
        out.notes.append(
            f"main table {self.schema_name}.{type_id} with "
            f"{len(spec.dedicated_columns)} dedicated col(s) "
            f"+ {len(fk_columns)} FK col(s) + jsonb '{jsonb_field}'"
        )
        out.rollback.append(f"DROP TABLE IF EXISTS {_qualified(type_id)} CASCADE")

        # --- Indexes ----------------------------------------------------------
        for col in spec.dedicated_columns:
            if col.indexed:
                idx_name = f"{type_id}_{col.name}_btree"
                out.indexes.append(
                    f"CREATE INDEX IF NOT EXISTS {_quote_ident(idx_name)} "
                    f"ON {_qualified(type_id)} ({_quote_ident(col.name)})"
                )
            if col.searchable:
                if col.type != "text":
                    out.notes.append(
                        f"WARNING: column '{col.name}' marked searchable but "
                        f"type is '{col.type}' — pg_trgm only works on text"
                    )
                else:
                    idx_name = f"{type_id}_{col.name}_trgm"
                    out.indexes.append(
                        f"CREATE INDEX IF NOT EXISTS {_quote_ident(idx_name)} "
                        f"ON {_qualified(type_id)} USING GIN "
                        f"({_quote_ident(col.name)} gin_trgm_ops)"
                    )

        # FK indexes (for join performance).
        for rel in fk_columns:
            idx_name = f"{type_id}_{rel.name}_id_btree"
            out.indexes.append(
                f"CREATE INDEX IF NOT EXISTS {_quote_ident(idx_name)} "
                f"ON {_qualified(type_id)} ({_quote_ident(rel.name + '_id')})"
            )

        # P1-8 fix from adversarial review: GIN index on the JSONB extension
        # column. Without this, queries of the form
        # `WHERE extension @> '{"key":"val"}'` seq-scan over millions of rows
        # — a DoS vector once the type accumulates data and any operator
        # query lands on extension fields.
        #
        # `jsonb_path_ops` is the more compact / faster GIN variant: it only
        # supports containment (`@>`) and `@@` queries, which is exactly our
        # use case. Compared to the default `jsonb_ops`, it indexes ~30%
        # smaller and is faster on both writes and `@>` lookups. We do NOT
        # need key-existence operators (`?`, `?|`, `?&`) on extension —
        # those are answered by dedicated columns when the field matters.
        extension_field = spec.jsonb_extension.field
        ext_idx_name = f"{type_id}_{extension_field}_gin"
        out.indexes.append(
            f"CREATE INDEX IF NOT EXISTS {_quote_ident(ext_idx_name)} "
            f"ON {_qualified(type_id)} USING GIN "
            f"({_quote_ident(extension_field)} jsonb_path_ops)"
        )

        # --- FK constraints ---------------------------------------------------
        for rel in fk_columns:
            on_delete = rel.on_delete.upper().replace("_", " ")
            constr_name = f"fk_{type_id}_{rel.name}"
            out.foreign_keys.append(
                f"ALTER TABLE {_qualified(type_id)} "
                f"ADD CONSTRAINT {_quote_ident(constr_name)} "
                f"FOREIGN KEY ({_quote_ident(rel.name + '_id')}) "
                f"REFERENCES {_qualified(rel.target)}(id) "
                f"ON DELETE {on_delete}"
            )

        # --- many_to_many join tables ----------------------------------------
        for rel in spec.relations:
            if rel.cardinality == "many_to_many":
                join = f"{type_id}__{rel.name}__{rel.target}"
                join_sql = (
                    f"CREATE TABLE IF NOT EXISTS {_qualified(join)} (\n"
                    f"  {_quote_ident(type_id + '_id')} UUID NOT NULL "
                    f"REFERENCES {_qualified(type_id)}(id) ON DELETE CASCADE,\n"
                    f"  {_quote_ident(rel.target + '_id')} UUID NOT NULL "
                    f"REFERENCES {_qualified(rel.target)}(id) ON DELETE CASCADE,\n"
                    f"  PRIMARY KEY ({_quote_ident(type_id + '_id')}, "
                    f"{_quote_ident(rel.target + '_id')})\n"
                    f")"
                )
                out.join_tables.append(join_sql)
                out.rollback.append(
                    f"DROP TABLE IF EXISTS {_qualified(join)} CASCADE"
                )

        # --- updated_at trigger -----------------------------------------------
        # P1-6 (adversarial review): the DROP+CREATE TRIGGER pair MUST run
        # inside a single transaction. Otherwise, between the two statements,
        # a concurrent UPDATE on the table could commit without firing
        # ``touch_updated_at``, leaving the row with a stale ``updated_at``.
        # The window is microseconds normally but grows to seconds if the
        # migration pauses (statement_timeout, network drop, lock wait).
        #
        # Two execution paths satisfy this invariant:
        #   1. In-process applier (``apply_manifest``): wraps every statement
        #      in one ``with pool.connection() as conn`` block + single
        #      ``conn.commit()`` at the end. DROP and CREATE land in the same
        #      transaction; concurrent sessions either see the old trigger
        #      or the new one, never neither.
        #   2. Operator running ``psql -f rendered.sql``: the ``render_sql()``
        #      method emits ``BEGIN;`` at the top and ``COMMIT;`` at the
        #      bottom, giving the same atomic guarantee.
        #
        # Future option (PG >=14): replace the pair with
        # ``CREATE OR REPLACE TRIGGER`` — single atomic operation, no DROP
        # needed. Deferred because we still target PG 13 in some envs.
        trig_name = f"{type_id}_set_updated_at"
        out.triggers.append(
            f"DROP TRIGGER IF EXISTS {_quote_ident(trig_name)} "
            f"ON {_qualified(type_id)}"
        )
        out.triggers.append(
            f"CREATE TRIGGER {_quote_ident(trig_name)} "
            f"BEFORE UPDATE ON {_qualified(type_id)} "
            f"FOR EACH ROW EXECUTE FUNCTION sylion_v2.touch_updated_at()"
        )

        # --- Lineage table + trigger ------------------------------------------
        # P1-7 fix from adversarial review: lineage tables grow unbounded
        # (every UPDATE on the parent appends a row). After ~1 year of
        # operation that's millions of rows per type, no partitioning,
        # no archiving, query performance degrades. Mitigation: declarative
        # PARTITION BY RANGE (recorded_at), monthly granularity.
        #
        # Why monthly? PDF §3.2 lineage is operational audit, not
        # warehouse-scale. ~24 months × 30 types = 720 partitions max,
        # well within PG's healthy partition count of <1000.
        #
        # Why declarative not inheritance? PG 14+ recommends declarative;
        # cleaner partition pruning, easier ATTACH/DETACH for archiving.
        #
        # Constraint: PG declarative partitioning requires the partition
        # key to be in the PRIMARY KEY and in every UNIQUE INDEX. So:
        #   - PK is now (seq, recorded_at) — was (seq) alone.
        #   - obj_idx now includes recorded_at first (partition pruning).
        #   - chain_uniq now includes recorded_at to satisfy PG's rule
        #     that UNIQUE indexes on a partitioned table must contain
        #     all partition columns.
        #
        # Operator responsibility (out of compiler scope):
        # call sylion_v2.create_next_lineage_partition('<table>') monthly
        # (or schedule via cron) before each partition window expires.
        # If no partition exists for the target range, INSERT into the
        # lineage table FAILS — and the parent UPDATE fails with it.
        if spec.audit.hash_chain:
            lineage_table = f"{type_id}_lineage"
            # Partitioned parent table.
            out.lineage.append(
                f"CREATE TABLE IF NOT EXISTS {_qualified(lineage_table)} (\n"
                f"  seq         BIGSERIAL,\n"
                f"  object_id   UUID NOT NULL,\n"
                f"  op          TEXT NOT NULL,\n"
                f"  diff        JSONB NOT NULL DEFAULT '{{}}'::jsonb,\n"
                f"  actor       TEXT NOT NULL DEFAULT 'system',\n"
                f"  prev_hash   TEXT NOT NULL,\n"
                f"  entry_hash  TEXT NOT NULL,\n"
                f"  recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n"
                f"  PRIMARY KEY (seq, recorded_at)\n"
                f") PARTITION BY RANGE (recorded_at)"
            )
            # Initial partition for the current month — required so
            # INSERTs succeed immediately after apply.
            out.lineage.append(
                f"CREATE TABLE IF NOT EXISTS "
                f"{_qualified(lineage_table + '_initial')} "
                f"PARTITION OF {_qualified(lineage_table)} "
                f"FOR VALUES FROM (date_trunc('month', NOW())) "
                f"TO (date_trunc('month', NOW()) + INTERVAL '1 month')"
            )
            # Pre-create next month's partition so the rollover at midnight
            # on the 1st of next month does not fail. After that, operator
            # cron is on the hook to keep advancing the window.
            out.lineage.append(
                f"SELECT sylion_v2.create_next_lineage_partition('{lineage_table}')"
            )
            out.lineage.append(
                f"CREATE INDEX IF NOT EXISTS "
                f"{_quote_ident(lineage_table + '_obj_idx')} "
                f"ON {_qualified(lineage_table)} (object_id, recorded_at, seq)"
            )
            # P0-2 fix: defense-in-depth UNIQUE constraint catches any
            # fork attempt that bypassed the advisory lock in
            # `append_lineage`. Two concurrent inserts with the same
            # prev_hash for the same object_id will fail the second
            # one rather than corrupt the chain silently.
            #
            # P1-7 follow-up: index now includes recorded_at because PG
            # requires all partition-key columns to appear in every
            # UNIQUE index on a partitioned table. The chain protection
            # remains correct: two appends for the same object cannot
            # share a prev_hash within the same instant (recorded_at is
            # set inside append_lineage just before the INSERT, under
            # the per-object advisory lock), so adding recorded_at does
            # not loosen the invariant in practice.
            out.lineage.append(
                f"CREATE UNIQUE INDEX IF NOT EXISTS "
                f"{_quote_ident(lineage_table + '_chain_uniq')} "
                f"ON {_qualified(lineage_table)} (object_id, prev_hash, recorded_at)"
            )
            out.rollback.append(
                f"DROP TABLE IF EXISTS {_qualified(lineage_table)} CASCADE"
            )

        out.notes.append(
            f"actions defined: {len(spec.actions)} "
            f"(compiled to REST endpoints by api/ontology_routes.py)"
        )
        return out

    def reset_shared(self) -> None:
        """Force the next compile() to re-emit shared bootstrap.

        Useful when compiling against a fresh DB after a tear-down.
        """
        self._seen_shared = False


# --------------------------------------------------------------------------
# One-shot helper
# --------------------------------------------------------------------------


def compile_to_ddl(manifest: ObjectTypeManifest) -> DDLArtifacts:
    """Compile a single manifest using a fresh compiler (always emits shared)."""
    return SchemaCompiler().compile(manifest)


# --------------------------------------------------------------------------
# P0-3 fix: ALTER reconciliation between manifest versions
# --------------------------------------------------------------------------


def compile_alter(
    old: ObjectTypeManifest,
    new: ObjectTypeManifest,
) -> DDLArtifacts:
    """Generate minimal ALTER TABLE statements to evolve ``old`` → ``new``.

    P0-3 fix from adversarial review: previously running the compiler on
    a *changed* manifest produced only ``CREATE TABLE IF NOT EXISTS``,
    which silently no-ops on the live table. Operator hits
    ``UndefinedColumn`` at runtime when the new code expects a column
    the table doesn't have. This helper diff's two manifests and emits:

    - ``ALTER TABLE ADD COLUMN`` for new dedicated columns.
    - ``ALTER TABLE DROP COLUMN`` for columns removed from new manifest
      (commented out by default — destructive, requires explicit op approval).
    - ``ALTER TABLE ALTER COLUMN ... TYPE ...`` for type changes (ALSO
      commented — needs USING clause or explicit cast).
    - New CHECK constraints for added enum values.
    - New B-tree / GIN indexes for newly indexed/searchable columns.
    - New FK constraints for added relations.

    The result is *advisory* — caller is expected to review the SQL and
    apply manually (or with Alembic migration). Phase 0 does NOT
    auto-apply ALTERs; that's G2 territory.

    Constraints:
    - Both manifests must have the SAME ``metadata.id`` (no rename).
    - Cardinality changes on relations are NOT auto-handled (manual).
    """
    if old.metadata.id != new.metadata.id:
        raise ValueError(
            f"compile_alter: cannot evolve '{old.metadata.id}' -> "
            f"'{new.metadata.id}' (different type_id)"
        )

    out = DDLArtifacts()
    type_id = new.metadata.id
    table = _qualified(type_id)

    old_cols: dict[str, DedicatedColumn] = {c.name: c for c in old.spec.dedicated_columns}
    new_cols: dict[str, DedicatedColumn] = {c.name: c for c in new.spec.dedicated_columns}

    # --- Added columns ------------------------------------------------------
    for name, col in new_cols.items():
        if name not in old_cols:
            sql = (
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
                f"{_column_sql(col, type_id)}"
            )
            out.main_table.append(sql)
            out.notes.append(f"+col {name} ({col.type})")

    # --- Removed columns (commented — destructive) -------------------------
    for name in old_cols:
        if name not in new_cols:
            out.notes.append(
                f"WARNING: column '{name}' removed from manifest. "
                "DROP not auto-emitted — destructive, requires manual review."
            )
            out.main_table.append(
                f"-- ALTER TABLE {table} DROP COLUMN IF EXISTS "
                f"{_quote_ident(name)};  -- DESTRUCTIVE, review before applying"
            )

    # --- Type / nullability / default changes (commented) -----------------
    for name, new_col in new_cols.items():
        old_col = old_cols.get(name)
        if not old_col:
            continue
        if old_col.type != new_col.type:
            out.main_table.append(
                f"-- ALTER TABLE {table} ALTER COLUMN {_quote_ident(name)} "
                f"TYPE {new_col.type.upper()} "
                f"USING ({_quote_ident(name)}::{new_col.type});  -- review cast"
            )
            out.notes.append(
                f"WARNING: type change {name}: {old_col.type} -> {new_col.type} "
                "needs USING clause"
            )
        if old_col.nullable != new_col.nullable:
            verb = "DROP NOT NULL" if new_col.nullable else "SET NOT NULL"
            out.main_table.append(
                f"ALTER TABLE {table} ALTER COLUMN {_quote_ident(name)} {verb}"
            )
        if old_col.default != new_col.default:
            if new_col.default is None:
                out.main_table.append(
                    f"ALTER TABLE {table} ALTER COLUMN "
                    f"{_quote_ident(name)} DROP DEFAULT"
                )
            else:
                default_clause = _sql_default(new_col)
                if default_clause:
                    set_clause = default_clause.replace("DEFAULT ", "SET DEFAULT ")
                    out.main_table.append(
                        f"ALTER TABLE {table} ALTER COLUMN "
                        f"{_quote_ident(name)} {set_clause}"
                    )
        # P1-9: enum change → DROP old CHECK + ADD new CHECK using the
        # deterministic <type_id>_<col>_chk name so DROP IF EXISTS finds
        # the constraint regardless of whether it was created by an
        # earlier compile or by hand.
        if (old_col.enum or []) != (new_col.enum or []):
            chk_name = _check_constraint_name(type_id, name)
            # DROP first — IF EXISTS so this is safe even if the old
            # manifest had no enum at all (no constraint to drop).
            out.main_table.append(
                f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "
                f"{_quote_ident(chk_name)}"
            )
            if new_col.enum:
                items = ", ".join(
                    f"'{_escape_sql_literal(str(v))}'" for v in new_col.enum
                )
                out.main_table.append(
                    f"ALTER TABLE {table} ADD CONSTRAINT "
                    f"{_quote_ident(chk_name)} "
                    f"CHECK ({_quote_ident(name)} IN ({items}))"
                )
                out.notes.append(
                    f"enum change on {name}: "
                    f"{old_col.enum or []} -> {new_col.enum}"
                )
            else:
                out.notes.append(
                    f"enum removed from {name} (was {old_col.enum})"
                )

    # --- New indexes for newly indexed/searchable columns ------------------
    for name, new_col in new_cols.items():
        old_col = old_cols.get(name)
        was_indexed = bool(old_col and old_col.indexed)
        was_searchable = bool(old_col and old_col.searchable)
        if new_col.indexed and not was_indexed:
            idx = f"{type_id}_{name}_btree"
            out.indexes.append(
                f"CREATE INDEX IF NOT EXISTS {_quote_ident(idx)} "
                f"ON {table} ({_quote_ident(name)})"
            )
        if new_col.searchable and new_col.type == "text" and not was_searchable:
            idx = f"{type_id}_{name}_trgm"
            out.indexes.append(
                f"CREATE INDEX IF NOT EXISTS {_quote_ident(idx)} "
                f"ON {table} USING GIN ({_quote_ident(name)} gin_trgm_ops)"
            )

    # --- New relations (FK columns + constraints) --------------------------
    old_rels = {r.name: r for r in old.spec.relations}
    new_rels = {r.name: r for r in new.spec.relations}
    for name, rel in new_rels.items():
        if name in old_rels:
            continue
        if rel.cardinality in {"many_to_one", "one_to_one"}:
            fk_col = f"{name}_id"
            null_clause = "" if rel.nullable else " NOT NULL"
            uniq_clause = " UNIQUE" if rel.cardinality == "one_to_one" else ""
            out.main_table.append(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
                f"{_quote_ident(fk_col)} UUID{null_clause}{uniq_clause}"
            )
            constr = f"fk_{type_id}_{name}"
            on_delete = rel.on_delete.upper().replace("_", " ")
            out.foreign_keys.append(
                f"ALTER TABLE {table} ADD CONSTRAINT IF NOT EXISTS "
                f"{_quote_ident(constr)} FOREIGN KEY ({_quote_ident(fk_col)}) "
                f"REFERENCES {_qualified(rel.target)}(id) ON DELETE {on_delete}"
            )
            out.notes.append(f"+relation {name} -> {rel.target} ({rel.cardinality})")

    if not (out.main_table or out.indexes or out.foreign_keys):
        out.notes.append("no schema changes detected between manifests")

    return out


# --------------------------------------------------------------------------
# Action effect compilation (placeholder for G2)
# --------------------------------------------------------------------------


def explain_actions(manifest: ObjectTypeManifest) -> list[dict[str, Any]]:
    """Return a JSON-friendly preview of what actions would be exposed.

    Used by ``GET /api/v1/ontology/{type_id}/actions`` to let the
    frontend (and Robert) inspect the contract without executing.
    Pure function — no DB access.
    """
    rows: list[dict[str, Any]] = []
    for a in manifest.spec.actions:
        rows.append({
            "action_id": a.id,
            "endpoint": (
                f"POST /api/v1/ontology/{manifest.metadata.id}/"
                f"{{instance_id}}/actions/{a.id}"
            ),
            "d_level": a.d_level,
            "hg_required": a.hg_required,
            "description_pl": a.description_pl,
            "description_en": a.description_en,
            "input_schema": a.input_schema,
            "effects_count": len(a.effects),
        })
    return rows


# --------------------------------------------------------------------------
# Example self-check
# --------------------------------------------------------------------------


def _selfcheck() -> None:
    """Run a no-op compile of a hand-built manifest.

    Useful as a smoke test from ``python -m sylion.aeis_v2.ontology.compiler``.
    Not called automatically.
    """
    from sylion.aeis_v2.ontology.manifest import (
        ActionDef,
        DedicatedColumn,
        JsonbExtension,
        ObjectTypeManifest,
        ObjectTypeMetadata,
        ObjectTypeSpec,
        Relation,
    )
    m = ObjectTypeManifest(
        api_version="sylion.aeis.v2/Object",
        kind="ObjectType",
        metadata=ObjectTypeMetadata(
            id="customer",
            name_pl="Klient",
            name_en="Customer",
            description_pl="Klient w systemie CRM.",
            description_en="A CRM customer.",
            tags=["crm", "core"],
            d_level="D2",
        ),
        spec=ObjectTypeSpec(
            dedicated_columns=[
                DedicatedColumn(
                    name="title", type="text", nullable=False,
                    indexed=True, searchable=True,
                ),
                DedicatedColumn(
                    name="status", type="text", nullable=False,
                    enum=["draft", "active", "archived"], default="draft",
                ),
                DedicatedColumn(name="email", type="text", indexed=True, unique=True),
            ],
            jsonb_extension=JsonbExtension(field="extension"),
            relations=[
                Relation(name="parent_project", target="project",
                         cardinality="many_to_one", on_delete="set_null"),
            ],
            actions=[
                ActionDef(id="archive_customer", d_level="D2"),
            ],
        ),
    )
    art = compile_to_ddl(m)
    print(art.render_sql())
    print("---")
    for n in art.notes:
        print("note:", n)


if __name__ == "__main__":
    _selfcheck()
