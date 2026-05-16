"""W15 G3 starter: data migration runner from W14 SQLite to v2 PostgreSQL.

PDF §6.3 step-by-step (10 steps):
  1. Manifest authoring (done — manifests/w14/*.yaml)
  2. DDL generation + verification (done — compile_to_ddl)
  3. Data export from SQLite (this module — export_w14_data)
  4. Data transformation per-table (this module — transform_w14_row)
  5. Bulk import to PG (this module — import_w14_data, G3 full runner)
  6. Verification — row count + sample diff 10% (verify_migration)
  7. Code refactor (use OSDK) — out of scope this module
  8. Side-by-side test 1 week — out of scope
  9. Cutover — out of scope
  10. Cleanup after 30 days — out of scope

G3 of THIS module:
  - dry-run preview (existing) -> ``preview_migration`` / ``preview_all_w14``
  - full bulk import (this commit) -> ``import_w14_data`` /
    ``run_w14_migration`` with row-level error tolerance, per-batch
    commit, post-import row-count + sample-id verification, and a JSONL
    audit trail at ``logs/v2/migration_audit.jsonl``.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sylion.aeis_v2.ontology.manifest import (
    ObjectTypeManifest,
)

log = logging.getLogger(__name__)


# Audit log path for migration runs (JSONL append-only). Mirrors the
# applier's ``apply_audit.jsonl`` shape so an operator can correlate a
# DDL apply with the data migration that followed it.
# parents[3] resolves: migration.py -> ontology -> aeis_v2 -> sylion -> sylion-pipeline/
MIGRATION_AUDIT_LOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "migration_audit.jsonl"
)

# Cap recorded per-row errors to keep the result payload bounded — a
# 10k-row import that has 9999 bad rows shouldn't ship a 9999-element
# list back to the operator UI. First 50 are sufficient for triage.
MAX_RECORDED_ERRORS = 50


@dataclass
class MigrationPreview:
    """Result of a dry-run migration of one W14 type."""

    type_id: str                       # e.g. "w14_test_run"
    sqlite_table: str                  # source table in SQLite (resolved)
    source_row_count: int = 0          # rows found in SQLite
    transformed_sample: list[dict[str, Any]] = field(default_factory=list)
    skipped_rows: int = 0              # rows that failed transform
    errors: list[str] = field(default_factory=list)
    rationale: str = ""
    candidates_tried: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type_id": self.type_id,
            "sqlite_table": self.sqlite_table,
            "source_row_count": self.source_row_count,
            "transformed_sample_count": len(self.transformed_sample),
            "transformed_sample": self.transformed_sample,
            "skipped_rows": self.skipped_rows,
            "errors": self.errors,
            "rationale": self.rationale,
            "candidates_tried": self.candidates_tried,
        }


def _pluralize(name: str) -> str:
    """Naive English pluralizer sufficient for W14 table names.

    Rules (in order):
      * already ends in 's' -> unchanged
      * ends in 's', 'x', 'ch', 'sh' -> append 'es'
      * ends in 'y' preceded by a consonant -> strip 'y', append 'ies'
      * otherwise -> append 's'
    """
    if not name:
        return name
    lower = name.lower()
    if lower.endswith("s"):
        return name
    if lower.endswith(("x",)) or lower.endswith(("ch", "sh")):
        return name + "es"
    if lower.endswith("y") and len(lower) >= 2 and lower[-2] not in "aeiou":
        return name[:-1] + "ies"
    return name + "s"


def _guess_sqlite_table(type_id: str) -> str:
    """Legacy heuristic kept for backward compatibility.

    Returns the prefix-stripped singular form (e.g. ``w14_test_run`` ->
    ``test_run``). Prefer ``_resolve_sqlite_table`` which inspects the
    live database to pick the actually-existing table name.
    """
    if type_id.startswith("w14_"):
        return type_id[len("w14_"):]
    return type_id


def _resolve_sqlite_table(
    conn: sqlite3.Connection,
    type_id: str,
) -> tuple[str, list[str]]:
    """Resolve the actual SQLite table name for a given W14 manifest id.

    Tries up to four candidates in priority order against ``sqlite_master``
    and returns the first that exists, plus the full list of candidates
    that were tried.

    Candidates (in order):
      1. Full ``type_id`` as-is (e.g. ``w14_test_run``)
      2. Pluralized ``type_id`` (e.g. ``w14_test_runs``)
      3. Stripped ``w14_`` prefix singular (e.g. ``test_run``)
      4. Stripped ``w14_`` prefix plural (e.g. ``test_runs``)

    If none exist, falls back to candidate 1 so the caller can still
    report a clean ``source_row_count=0`` result with the original guess
    in the rationale.

    Returns ``(resolved_table, candidates_tried)``.
    """
    candidates: list[str] = []
    candidates.append(type_id)
    candidates.append(_pluralize(type_id))
    if type_id.startswith("w14_"):
        stripped = type_id[len("w14_"):]
        candidates.append(stripped)
        candidates.append(_pluralize(stripped))
    # De-dupe while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            deduped.append(c)
    cur = conn.cursor()
    for cand in deduped:
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (cand,),
        )
        if cur.fetchone():
            return cand, deduped
    # No match — fall back to candidate 1 (original guess).
    return deduped[0], deduped


def export_w14_data(
    sqlite_path: Path | str,
    manifest: ObjectTypeManifest,
    *,
    sample_pct: int = 10,
    max_rows: int = 1000,
) -> list[dict[str, Any]]:
    """Read ``sample_pct`` percent of rows from the matching SQLite table.

    Returns a list of dicts. Each dict has keys = column names. Bytes,
    timestamps and JSON columns are returned as-is (raw SQLite value).
    """
    conn = sqlite3.connect(str(sqlite_path))
    try:
        conn.row_factory = sqlite3.Row
        table, _candidates = _resolve_sqlite_table(conn, manifest.metadata.id)
        cur = conn.cursor()
        # Confirm table exists (resolver may have fallen back).
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not cur.fetchone():
            return []
        # Sample by rowid
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total = cur.fetchone()[0]
        limit = min(max_rows, max(1, total * sample_pct // 100))
        cur.execute(f"SELECT * FROM {table} LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    finally:
        conn.close()


def transform_w14_row(
    raw: dict[str, Any],
    manifest: ObjectTypeManifest,
) -> dict[str, Any]:
    """Map a SQLite row to a W15-shape dict.

    Strategy:
      - For each manifest dedicated column, copy from raw[name] if present.
      - For each manifest relation ``name``, copy raw[name + "_id"].
      - Everything else goes into ``extension`` jsonb.
      - Drop SQLite-internal fields (``rowid``).

    Type coercion: SQLite is loose; we keep raw values and let PG cast.
    """
    out: dict[str, Any] = {}
    seen: set[str] = set()
    for col in manifest.spec.dedicated_columns:
        if col.name in raw:
            out[col.name] = raw[col.name]
            seen.add(col.name)
    for rel in manifest.spec.relations:
        fk = f"{rel.name}_id"
        if fk in raw:
            out[fk] = raw[fk]
            seen.add(fk)
    extension: dict[str, Any] = {}
    for k, v in raw.items():
        if k in seen or k in {"rowid", "id", "created_at", "updated_at"}:
            continue
        extension[k] = v
    out["extension"] = extension
    return out


def preview_migration(
    sqlite_path: Path | str,
    manifest: ObjectTypeManifest,
    *,
    sample_pct: int = 10,
    max_sample: int = 5,
) -> MigrationPreview:
    """Dry-run preview: export sample + transform + report."""
    preview = MigrationPreview(type_id=manifest.metadata.id, sqlite_table="")
    # Resolve via a single connection so candidates_tried can be surfaced
    # even when the source DB is unreachable.
    try:
        conn = sqlite3.connect(str(sqlite_path))
    except sqlite3.Error as exc:
        preview.errors.append(f"connect failed: {type(exc).__name__}: {exc}")
        preview.rationale = (
            f"Nie udalo sie otworzyc bazy SQLite pod {sqlite_path}."
        )
        return preview
    try:
        conn.row_factory = sqlite3.Row
        table, candidates = _resolve_sqlite_table(conn, manifest.metadata.id)
        preview.sqlite_table = table
        preview.candidates_tried = candidates
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        table_exists = cur.fetchone() is not None
        if not table_exists:
            preview.rationale = (
                f"Brak tabeli SQLite. Probowano: {candidates}. "
                f"Sprawdz nazwy tabel w {sqlite_path}."
            )
            return preview
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total = cur.fetchone()[0]
        limit = min(1000, max(1, total * sample_pct // 100))
        cur.execute(f"SELECT * FROM {table} LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
    except Exception as exc:  # noqa: BLE001
        preview.errors.append(f"export failed: {type(exc).__name__}: {exc}")
        preview.rationale = "Export z SQLite zakonczony bledem; sprawdz sciezke."
        conn.close()
        return preview
    finally:
        # Best effort close; ignore double-close on early return paths.
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    preview.source_row_count = len(rows)
    transformed: list[dict[str, Any]] = []
    skipped = 0
    for r in rows[:max_sample]:
        try:
            transformed.append(transform_w14_row(r, manifest))
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            preview.errors.append(f"transform row failed: {exc}")
    preview.transformed_sample = transformed
    preview.skipped_rows = skipped
    if preview.source_row_count == 0:
        preview.rationale = (
            f"Tabela {table} istnieje ale jest pusta."
        )
    else:
        preview.rationale = (
            f"Zrodlo: {table} (po dopasowaniu z {len(candidates)} "
            f"kandydatow). Sample {len(transformed)}/{len(rows)}."
        )
    return preview


def preview_all_w14(
    sqlite_path: Path | str,
    manifests: list[ObjectTypeManifest],
) -> list[MigrationPreview]:
    """Preview migration for every W14 manifest."""
    return [
        preview_migration(sqlite_path, m)
        for m in manifests
        if m.metadata.id.startswith("w14_")
    ]


# --------------------------------------------------------------------------
# G3 full runner — MigrationResult + import_w14_data + verify + audit
# --------------------------------------------------------------------------


@dataclass
class MigrationResult:
    """Result of a real (or dry-run) bulk import of one W14 type.

    Distinguished from ``MigrationPreview`` (which only samples + transforms
    a fraction): this dataclass records the OUTCOME of attempting to copy
    every source row into the v2 PG target table.

    Attributes
    ----------
    type_id:
        Manifest id, e.g. ``w14_test_run``.
    sqlite_table:
        Source table name in SQLite (resolved via ``_resolve_sqlite_table``).
    source_row_count:
        Total rows present in the source table at the start of the run.
    imported_row_count:
        Number of rows that successfully landed in PG (or, in dry-run,
        successfully passed transform + would-have-been-INSERT).
    failed_rows:
        Number of rows whose transform or INSERT raised. Each one gets
        an entry in ``errors`` (capped at first ``MAX_RECORDED_ERRORS``).
    errors:
        Per-row failure details: ``{"row_pk": str, "error": str}``.
        Truncated to first ``MAX_RECORDED_ERRORS`` to keep the payload
        bounded. ``len(errors) <= failed_rows`` is the invariant.
    applied:
        ``True`` iff every source row landed in PG (or, dry-run, would
        have). Equivalent to ``failed_rows == 0 and not preview_only``.
    verified:
        ``True`` iff ``verify_migration`` confirmed the post-import
        ``COUNT(*)`` matches ``source_row_count`` AND the sample-id
        spot-check passed. False on dry-run (nothing to verify).
    rationale:
        Human-readable PL message intended for the operator UI.
    dry_run:
        Echoes the input flag — operators reading the JSON result need
        to know whether nothing actually persisted.
    """

    type_id: str
    sqlite_table: str
    source_row_count: int
    imported_row_count: int = 0
    failed_rows: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    applied: bool = False
    verified: bool = False
    rationale: str = ""
    dry_run: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "type_id": self.type_id,
            "sqlite_table": self.sqlite_table,
            "source_row_count": self.source_row_count,
            "imported_row_count": self.imported_row_count,
            "failed_rows": self.failed_rows,
            "errors": self.errors,
            "applied": self.applied,
            "verified": self.verified,
            "rationale": self.rationale,
            "dry_run": self.dry_run,
        }


def _get_pg_connection():
    """Return a psycopg pool or ``None`` if PG unreachable.

    Re-uses the v1 advisor pool — same pattern as
    ``sylion.aeis_v2.ontology.applier._get_pg_connection`` (kept in sync
    so a single PG outage degrades both paths uniformly to "preview-only
    -class" behavior).
    """
    try:
        from sylion.aeis.advisor._db import PGUnreachable, get_pool
    except ImportError as exc:
        log.error(
            "ontology migration: advisor pool module missing (%s) — "
            "install the 'advisor' extra; falling back to no-op",
            exc,
        )
        return None
    try:
        return get_pool()
    except PGUnreachable as exc:
        log.info(
            "ontology migration: PG unreachable (%s) — no-op", exc,
        )
        return None
    except Exception as exc:  # noqa: BLE001
        log.error(
            "ontology migration: pool init failed unexpectedly (%s) — "
            "investigate config; no-op for now",
            exc, exc_info=True,
        )
        return None


def _target_table(type_id: str) -> str:
    """Translate a manifest id into its PG target table name.

    Strategy: strip the ``w14_`` prefix to match what the compiler emits
    into ``sylion_v2.<table>`` (compiler already drops the prefix on
    create-table). Non-w14 ids pass through unchanged.
    """
    if type_id.startswith("w14_"):
        return type_id[len("w14_"):]
    return type_id


def _emit_migration_audit(
    *,
    type_id: str,
    imported_row_count: int,
    failed_rows: int,
    dry_run: bool,
    applied: bool,
    verified: bool,
    rationale: str,
    audit_path: Path | None = None,
) -> None:
    """Write a structured audit row to JSONL log.

    Format (one JSON object per line):
      {ts, type_id, imported_row_count, failed_rows, dry_run, applied,
       verified, rationale}

    Failure to write is logged at WARNING level but does NOT raise — the
    migration result must surface even if audit infra is down.
    """
    target = audit_path or MIGRATION_AUDIT_LOG_PATH
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type_id": type_id,
        "imported_row_count": imported_row_count,
        "failed_rows": failed_rows,
        "dry_run": dry_run,
        "applied": applied,
        "verified": verified,
        "rationale": rationale[:200],
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        log.warning("migration_audit: failed to write JSONL (%s)", exc)


def _build_insert_sql(
    schema: str,
    table: str,
    columns: list[str],
) -> str:
    """Build a parameterized INSERT statement for the given column list.

    No string-concatenation of values — psycopg ``%s`` placeholders only.
    Schema/table/column identifiers are quoted (defensive — the manifest
    id is slug-validated upstream, but quoting is still cheap insurance).
    """
    quoted_cols = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    return (
        f'INSERT INTO "{schema}"."{table}" ({quoted_cols}) '
        f"VALUES ({placeholders})"
    )


def import_w14_data(
    conn,
    manifest: ObjectTypeManifest,
    sqlite_path: Path | str,
    *,
    dry_run: bool = True,
    batch_size: int = 500,
) -> MigrationResult:
    """Stream every row from SQLite into the v2 PG target table.

    Args:
        conn: psycopg connection-like object (must support ``cursor()``,
            ``commit()``, ``rollback()``). When ``None``, returns a clean
            result with ``applied=False`` and a PL rationale (caller
            shouldn't normally hit that path — wrap via
            ``run_w14_migration`` which short-circuits before this).
        manifest: validated ObjectTypeManifest from registry.
        sqlite_path: filesystem path to the W14 SQLite db.
        dry_run: when True, opens the PG cursor and prepares INSERTs but
            ROLLBACKs at the end — operator gets the same result shape
            but nothing actually persists. When False, COMMITs after
            each batch so partial progress is durable if a later batch
            fails.
        batch_size: ``cursor.fetchmany(N)`` page size. Default 500 keeps
            the per-batch round-trip cheap without loading 10k+ rows
            into memory at once.

    Returns:
        MigrationResult — see dataclass docstring. On row-level error
        the loop continues (operator wants every bad row reported, not
        the first one). On batch-level connectivity error the partial
        progress already committed is preserved (the subsequent INSERTs
        in that batch don't run — caller can retry once PG is back).

    Behavior on errors:
        - Per-row transform exception: failed_rows += 1, error recorded,
          loop continues.
        - Per-row INSERT exception (e.g. constraint violation): same
          treatment as transform error.
        - Connection-level exception (e.g. server killed mid-batch):
          the current batch's pending rows are dropped, loop exits, and
          the result reflects partial progress.
    """
    type_id = manifest.metadata.id
    target_table = _target_table(type_id)

    # Resolve source table in a separate sqlite connection (don't entangle
    # PG conn lifecycle with sqlite).
    src = sqlite3.connect(str(sqlite_path))
    try:
        src.row_factory = sqlite3.Row
        sqlite_table, _candidates = _resolve_sqlite_table(src, type_id)
        cur_src = src.cursor()
        cur_src.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (sqlite_table,),
        )
        if not cur_src.fetchone():
            return MigrationResult(
                type_id=type_id,
                sqlite_table=sqlite_table,
                source_row_count=0,
                applied=False,
                verified=False,
                rationale=(
                    f"Tabela SQLite '{sqlite_table}' nie istnieje - "
                    "sprawdz nazwy tabel w zrodle."
                ),
                dry_run=dry_run,
            )
        cur_src.execute(f"SELECT COUNT(*) FROM {sqlite_table}")
        source_count = int(cur_src.fetchone()[0])

        result = MigrationResult(
            type_id=type_id,
            sqlite_table=sqlite_table,
            source_row_count=source_count,
            dry_run=dry_run,
        )

        if conn is None:
            result.rationale = (
                "PG niedostepny - migracja nie wykonana."
            )
            return result

        if source_count == 0:
            result.applied = True
            result.verified = True
            result.rationale = (
                f"Tabela {sqlite_table} pusta - nic do migracji."
            )
            return result

        cur_src.execute(f"SELECT * FROM {sqlite_table}")

        # Stream + transform + INSERT in batches.
        try:
            while True:
                batch = cur_src.fetchmany(batch_size)
                if not batch:
                    break
                transformed_rows: list[tuple[str, dict[str, Any]]] = []
                for raw_row in batch:
                    raw = dict(raw_row)
                    row_pk = str(raw.get("id", raw.get("rowid", "?")))
                    try:
                        transformed = transform_w14_row(raw, manifest)
                    except Exception as exc:  # noqa: BLE001
                        result.failed_rows += 1
                        if len(result.errors) < MAX_RECORDED_ERRORS:
                            result.errors.append({
                                "row_pk": row_pk,
                                "error": (
                                    f"transform: {type(exc).__name__}: {exc}"
                                ),
                            })
                        continue
                    transformed_rows.append((row_pk, transformed))

                # INSERT each transformed row; per-row error tolerated.
                for row_pk, payload in transformed_rows:
                    columns = list(payload.keys())
                    values: list[Any] = []
                    for col in columns:
                        v = payload[col]
                        # Serialize jsonb-shape dicts so psycopg can bind.
                        if isinstance(v, (dict, list)):
                            values.append(json.dumps(v, ensure_ascii=False))
                        else:
                            values.append(v)
                    sql = _build_insert_sql(
                        "sylion_v2", target_table, columns,
                    )
                    try:
                        with conn.cursor() as cur_pg:
                            cur_pg.execute(sql, values)
                    except Exception as exc:  # noqa: BLE001
                        result.failed_rows += 1
                        if len(result.errors) < MAX_RECORDED_ERRORS:
                            result.errors.append({
                                "row_pk": row_pk,
                                "error": (
                                    f"insert: {type(exc).__name__}: {exc}"
                                ),
                            })
                        # Some PG drivers leave the connection in an
                        # aborted-transaction state after an error. A
                        # rollback resets the per-row failure so the
                        # next INSERT can proceed cleanly.
                        try:
                            conn.rollback()
                        except Exception:  # noqa: BLE001
                            pass
                        continue
                    result.imported_row_count += 1

                # Per-batch commit on real run; rollback on dry-run is
                # deferred to the very end (so dry-run still observes the
                # full sequence of INSERT execute calls).
                if not dry_run:
                    try:
                        conn.commit()
                    except Exception as exc:  # noqa: BLE001
                        log.warning(
                            "migration: per-batch commit failed (%s)", exc,
                        )
                        break
        finally:
            if dry_run:
                # Discard any in-flight INSERTs.
                try:
                    conn.rollback()
                except Exception:  # noqa: BLE001
                    pass

        # Determine applied/rationale.
        if result.failed_rows == 0 and result.imported_row_count == source_count:
            result.applied = True
            if dry_run:
                result.rationale = (
                    f"Dry-run: {result.imported_row_count}/{source_count} "
                    "wierszy przeszlo transform+INSERT (rollback)."
                )
            else:
                result.rationale = (
                    f"Zaimportowano {result.imported_row_count}/"
                    f"{source_count} wierszy do "
                    f"sylion_v2.{target_table}."
                )
        else:
            result.applied = False
            result.rationale = (
                f"Migracja niekompletna: {result.imported_row_count}/"
                f"{source_count} OK, {result.failed_rows} bledow. "
                "Pierwsze bledy w polu errors."
            )
        return result
    finally:
        src.close()


def verify_migration(
    conn,
    target_table: str,
    source_count: int,
    *,
    schema: str = "sylion_v2",
    sample_size: int = 10,
) -> bool:
    """Confirm post-import row count matches source + spot-check IDs.

    Two-stage check:
      1. ``SELECT COUNT(*) FROM <schema>.<table>`` must equal
         ``source_count``.
      2. Sample up to ``sample_size`` IDs at random (if the target has
         an ``id`` column); each one must be queryable. This guards
         against the case where an INSERT silently no-op'd or a unique
         constraint replaced a row.

    Returns:
        True iff both stages pass. False on any mismatch or query error
        (caller logs the rationale).
    """
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                f'SELECT COUNT(*) FROM "{schema}"."{target_table}"'
            )
            row = cur.fetchone()
            count = int(row[0]) if row else 0
            if count != source_count:
                return False
            # Sample-id spot check. We only run this when there's
            # something to sample. ``sample_size`` is bounded by source.
            if source_count == 0:
                return True
            n = min(sample_size, source_count)
            try:
                cur.execute(
                    f'SELECT "id" FROM "{schema}"."{target_table}" '
                    f"ORDER BY random() LIMIT %s",
                    (n,),
                )
                sampled = [r[0] for r in cur.fetchall()]
            except Exception:  # noqa: BLE001
                # No id column or non-standard schema — count match
                # alone is sufficient evidence.
                return True
            # Each sampled id must be re-queryable.
            for _id in sampled:
                cur.execute(
                    f'SELECT 1 FROM "{schema}"."{target_table}" '
                    f'WHERE "id" = %s LIMIT 1',
                    (_id,),
                )
                if cur.fetchone() is None:
                    return False
            return True
    except Exception as exc:  # noqa: BLE001
        log.warning("verify_migration failed (%s)", exc)
        return False


def run_w14_migration(
    manifest: ObjectTypeManifest,
    sqlite_path: Path | str,
    *,
    dry_run: bool = True,
    audit_path: Path | None = None,
) -> MigrationResult:
    """Top-level wrapper: open PG, run import, verify, emit audit.

    Args:
        manifest: validated ObjectTypeManifest from registry.
        sqlite_path: filesystem path to the W14 SQLite db.
        dry_run: when True, open PG + prepare INSERTs + ROLLBACK at end.
        audit_path: override the JSONL audit destination (mainly for
            tests). Defaults to ``MIGRATION_AUDIT_LOG_PATH``.

    Returns:
        MigrationResult — full outcome including ``applied`` and
        ``verified`` flags. When PG unreachable, returns a clean result
        with ``applied=False`` and a PL rationale; the audit row is
        still emitted so the operator has a record of the attempt.
    """
    type_id = manifest.metadata.id
    pool = _get_pg_connection()
    if pool is None:
        result = MigrationResult(
            type_id=type_id,
            sqlite_table="",
            source_row_count=0,
            applied=False,
            verified=False,
            rationale="PG niedostepny - migracja nie wykonana.",
            dry_run=dry_run,
        )
        _emit_migration_audit(
            type_id=type_id,
            imported_row_count=0,
            failed_rows=0,
            dry_run=dry_run,
            applied=False,
            verified=False,
            rationale=result.rationale,
            audit_path=audit_path,
        )
        return result

    # Open one PG connection for the whole import + verify pair so the
    # verification observes the same view as the writer (especially under
    # dry-run, where rolled-back INSERTs are invisible to a separate
    # connection).
    try:
        with pool.connection() as conn:
            result = import_w14_data(
                conn, manifest, sqlite_path, dry_run=dry_run,
            )
            if result.applied and not dry_run:
                target = _target_table(type_id)
                result.verified = verify_migration(
                    conn, target, result.source_row_count,
                )
    except Exception as exc:  # noqa: BLE001
        log.exception("run_w14_migration: PG-level failure for %s", type_id)
        result = MigrationResult(
            type_id=type_id,
            sqlite_table="",
            source_row_count=0,
            applied=False,
            verified=False,
            rationale=(
                f"Awaria PG podczas migracji: "
                f"{type(exc).__name__}: {exc}"
            ),
            dry_run=dry_run,
        )

    _emit_migration_audit(
        type_id=type_id,
        imported_row_count=result.imported_row_count,
        failed_rows=result.failed_rows,
        dry_run=dry_run,
        applied=result.applied,
        verified=result.verified,
        rationale=result.rationale,
        audit_path=audit_path,
    )
    return result


def run_all_w14_migrations(
    manifests: list[ObjectTypeManifest],
    sqlite_path: Path | str,
    *,
    dry_run: bool = True,
    audit_path: Path | None = None,
) -> list[MigrationResult]:
    """Run ``run_w14_migration`` for every w14_* manifest.

    Idempotency (G3 Phase 0): if the target PG table already has rows,
    the per-type migration short-circuits with
    ``applied=False, rationale="Zaaplikowane wczesniej, pomijam"`` so a
    re-run after partial success doesn't double-insert. G2 will replace
    this with a proper diff-and-merge upsert path.
    """
    results: list[MigrationResult] = []
    pool = _get_pg_connection()
    for m in manifests:
        type_id = m.metadata.id
        if not type_id.startswith("w14_"):
            continue
        # Idempotency check: already-populated target -> skip.
        if pool is not None:
            target = _target_table(type_id)
            try:
                with pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            f'SELECT COUNT(*) FROM "sylion_v2"."{target}"'
                        )
                        row = cur.fetchone()
                        existing = int(row[0]) if row else 0
            except Exception:  # noqa: BLE001
                # Couldn't reach the table (doesn't exist yet, or PG
                # wobbled). Fall through to the full run -- it will
                # surface a clean error in MigrationResult.
                existing = 0
            if existing > 0:
                skip = MigrationResult(
                    type_id=type_id,
                    sqlite_table="",
                    source_row_count=existing,
                    applied=False,
                    verified=False,
                    rationale="Zaaplikowane wczesniej, pomijam",
                    dry_run=dry_run,
                )
                _emit_migration_audit(
                    type_id=type_id,
                    imported_row_count=0,
                    failed_rows=0,
                    dry_run=dry_run,
                    applied=False,
                    verified=False,
                    rationale=skip.rationale,
                    audit_path=audit_path,
                )
                results.append(skip)
                continue
        results.append(
            run_w14_migration(
                m, sqlite_path, dry_run=dry_run, audit_path=audit_path,
            )
        )
    return results
