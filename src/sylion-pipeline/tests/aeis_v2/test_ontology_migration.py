"""Tests for sylion.aeis_v2.ontology.migration - W15 G3 starter.

Phase 0 covers dry-run preview only:
1. ``_guess_sqlite_table`` strips ``w14_`` prefix from manifest id.
2. ``export_w14_data`` returns empty list when source table is missing.
3. ``export_w14_data`` returns sample (~10%) when source table has rows.
4. ``transform_w14_row`` routes dedicated columns to top-level keys and
   spills the rest into ``extension`` jsonb.
5. ``preview_migration`` produces a Polish rationale string when the
   source table is empty/missing.

Tests use ``tmp_path`` for ephemeral SQLite databases - never touch the
real ``sylion_aeis.db``.
"""
from __future__ import annotations

import sqlite3

import pytest

from sylion.aeis_v2.ontology import (
    DedicatedColumn,
    ObjectTypeManifest,
    ObjectTypeMetadata,
    ObjectTypeSpec,
    Relation,
)
from sylion.aeis_v2.ontology import migration as migration_mod
from sylion.aeis_v2.ontology.migration import (
    MigrationPreview,
    MigrationResult,
    _guess_sqlite_table,
    _pluralize,
    _resolve_sqlite_table,
    export_w14_data,
    import_w14_data,
    preview_migration,
    run_w14_migration,
    transform_w14_row,
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _manifest(
    type_id: str = "w14_test_run",
    columns: list[DedicatedColumn] | None = None,
    relations: list[Relation] | None = None,
) -> ObjectTypeManifest:
    """Minimal manifest for migration tests."""
    return ObjectTypeManifest(
        api_version="sylion.aeis.v2/Object",
        kind="ObjectType",
        metadata=ObjectTypeMetadata(
            id=type_id, name_pl="X", name_en="X",
        ),
        spec=ObjectTypeSpec(
            dedicated_columns=columns or [
                DedicatedColumn(name="title", type="text", nullable=False),
            ],
            relations=relations or [],
        ),
    )


# --------------------------------------------------------------------------
# 1. _guess_sqlite_table
# --------------------------------------------------------------------------


def test_guess_sqlite_table_strips_w14_prefix():
    """``w14_test_run`` -> ``test_run``; non-w14 ids pass through."""
    assert _guess_sqlite_table("w14_test_run") == "test_run"
    assert _guess_sqlite_table("w14_finding") == "finding"
    # No prefix -> identity.
    assert _guess_sqlite_table("customer") == "customer"
    # Prefix-only edge case.
    assert _guess_sqlite_table("w14_") == ""


# --------------------------------------------------------------------------
# 2. export_w14_data - missing table
# --------------------------------------------------------------------------


def test_export_w14_data_returns_empty_for_missing_table(tmp_path):
    """Fresh sqlite with no matching table -> empty list, no exception."""
    db_path = tmp_path / "empty.db"
    # Touch the file so it exists as a valid (empty) SQLite db.
    sqlite3.connect(str(db_path)).close()

    rows = export_w14_data(db_path, _manifest("w14_test_run"))

    assert rows == []


# --------------------------------------------------------------------------
# 3. export_w14_data - sampled rows
# --------------------------------------------------------------------------


def test_export_w14_data_returns_sample(tmp_path):
    """100 rows, sample_pct=10 -> ~10 rows returned."""
    db_path = tmp_path / "with_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE test_run (id TEXT PRIMARY KEY, title TEXT)")
        conn.executemany(
            "INSERT INTO test_run VALUES (?, ?)",
            [(f"id-{i}", f"title-{i}") for i in range(100)],
        )
        conn.commit()
    finally:
        conn.close()

    rows = export_w14_data(
        db_path,
        _manifest("w14_test_run"),
        sample_pct=10,
    )

    # 100 * 10 // 100 = 10 -> exactly 10 rows.
    assert len(rows) == 10
    # Each row is a dict keyed on the table column names.
    assert all(isinstance(r, dict) for r in rows)
    assert all("id" in r and "title" in r for r in rows)


# --------------------------------------------------------------------------
# 4. transform_w14_row - column / extension routing
# --------------------------------------------------------------------------


def test_transform_w14_row_routes_dedicated_columns():
    """Dedicated cols go to top level; everything else -> extension jsonb."""
    manifest = _manifest(
        "w14_test_run",
        columns=[
            DedicatedColumn(name="title", type="text", nullable=False),
            DedicatedColumn(name="status", type="text", nullable=False),
        ],
        relations=[
            Relation(
                name="suite",
                target="w14_test_suite",
                cardinality="many_to_one",
            ),
        ],
    )
    raw = {
        "id": "id-1",                     # reserved -> dropped
        "title": "Hello",                 # dedicated col -> top level
        "status": "passed",               # dedicated col -> top level
        "suite_id": "suite-42",           # relation FK -> top level
        "extra": "extra-value",           # unknown -> extension
        "rowid": 7,                       # SQLite-internal -> dropped
        "created_at": 1700000000.0,       # reserved -> dropped
    }

    out = transform_w14_row(raw, manifest)

    assert out["title"] == "Hello"
    assert out["status"] == "passed"
    assert out["suite_id"] == "suite-42"
    # Unknown field went into extension jsonb.
    assert out["extension"] == {"extra": "extra-value"}
    # Reserved + rowid + dedicated cols + FK must NOT appear in extension.
    assert "id" not in out["extension"]
    assert "rowid" not in out["extension"]
    assert "title" not in out["extension"]
    assert "suite_id" not in out["extension"]
    assert "created_at" not in out["extension"]


# --------------------------------------------------------------------------
# 5. preview_migration - empty table rationale
# --------------------------------------------------------------------------


def test_preview_migration_produces_rationale_for_empty_table(tmp_path):
    """Empty sqlite -> MigrationPreview with PL rationale flag word.

    With the plural-aware resolver, when no candidate matches the
    fallback is candidate 1 (the manifest id as-is). The rationale must
    surface either ``brak`` (no table) or ``pusta`` (empty) in Polish.
    """
    db_path = tmp_path / "empty.db"
    sqlite3.connect(str(db_path)).close()

    preview = preview_migration(db_path, _manifest("w14_test_run"))

    assert isinstance(preview, MigrationPreview)
    assert preview.type_id == "w14_test_run"
    # No candidate matched -> fallback to candidate 1 (the type_id).
    assert preview.sqlite_table == "w14_test_run"
    assert preview.source_row_count == 0
    assert preview.transformed_sample == []
    assert preview.skipped_rows == 0
    # All four candidates must have been tried.
    assert "w14_test_run" in preview.candidates_tried
    assert "w14_test_runs" in preview.candidates_tried
    assert "test_run" in preview.candidates_tried
    assert "test_runs" in preview.candidates_tried
    # Rationale must mention the missing condition in Polish.
    rationale_lower = preview.rationale.lower()
    assert "brak" in rationale_lower or "nie istnieje" in rationale_lower


# --------------------------------------------------------------------------
# 6. _resolve_sqlite_table - candidate priority order
# --------------------------------------------------------------------------


def test_resolve_sqlite_table_finds_singular_when_present():
    """Candidate 1 wins: ``w14_test_run`` table present -> resolved as-is."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE w14_test_run (id TEXT PRIMARY KEY)")
        resolved, candidates = _resolve_sqlite_table(conn, "w14_test_run")
        assert resolved == "w14_test_run"
        # Candidate 1 hit -> all four candidates still recorded (the
        # resolver records the full plan it would have tried).
        assert candidates[0] == "w14_test_run"
        assert "w14_test_runs" in candidates
        assert "test_run" in candidates
        assert "test_runs" in candidates
    finally:
        conn.close()


def test_resolve_sqlite_table_finds_plural_when_singular_missing():
    """Candidate 2 wins: only the plural ``w14_test_runs`` exists.

    This is the bug the v2 cron is closing — the live SQLite store at
    ``sylion_aeis.db`` uses plural names but the manifest id is singular.
    """
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE w14_test_runs (id TEXT PRIMARY KEY)")
        resolved, candidates = _resolve_sqlite_table(conn, "w14_test_run")
        assert resolved == "w14_test_runs"
        # Resolver must have visited candidate 1 first (and missed) before
        # finding candidate 2.
        assert candidates.index("w14_test_run") < candidates.index(
            "w14_test_runs"
        )
    finally:
        conn.close()


def test_resolve_sqlite_table_finds_stripped_prefix_singular():
    """Candidate 3 wins: only the legacy ``test_run`` table exists.

    Mirrors the old heuristic for tables already migrated under the
    stripped-prefix convention.
    """
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE test_run (id TEXT PRIMARY KEY)")
        resolved, candidates = _resolve_sqlite_table(conn, "w14_test_run")
        assert resolved == "test_run"
        assert "test_run" in candidates
    finally:
        conn.close()


def test_resolve_sqlite_table_falls_back_with_candidates_in_preview(tmp_path):
    """No candidate exists -> fallback to candidate 1, candidates surfaced.

    The preview must still produce a clean object (no exception raised),
    ``source_row_count=0``, and ``candidates_tried`` populated so the
    caller can see exactly which names were attempted.
    """
    db_path = tmp_path / "no_match.db"
    # Create a sqlite db with an unrelated table so connection succeeds
    # but no candidate name matches.
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE unrelated_table (id TEXT PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()

    preview = preview_migration(db_path, _manifest("w14_test_run"))

    assert preview.source_row_count == 0
    assert preview.skipped_rows == 0
    assert preview.errors == []
    # Fallback to candidate 1 (the type_id as-is).
    assert preview.sqlite_table == "w14_test_run"
    # All four candidates surfaced for diagnostics.
    assert preview.candidates_tried == [
        "w14_test_run",
        "w14_test_runs",
        "test_run",
        "test_runs",
    ]
    # Rationale references the diagnostic list and the db path.
    assert "Probowano" in preview.rationale
    assert "w14_test_runs" in preview.rationale
    # to_dict() must surface the new field.
    payload = preview.to_dict()
    assert payload["candidates_tried"] == preview.candidates_tried


# --------------------------------------------------------------------------
# 7. W15 G3 full runner — import_w14_data + verify + audit
# --------------------------------------------------------------------------
#
# These tests exercise the real bulk-import path. The PG side is stubbed
# (mirrors test_ontology_applier.py's _StubPool/_StubConnection/_StubCursor
# pattern but extended to record per-batch commit/rollback transitions).
# The SQLite source is a real on-disk db built per-test under tmp_path.


class _MigrationStubCursor:
    """Records every parameterized INSERT into the parent connection.

    Parameters land in ``conn.pending`` (in-flight) and are moved to
    ``conn.executed`` on ``conn.commit()`` — mirrors P0-2 semantics from
    the applier test stub. Optional ``fail_on_row_index`` raises when
    the n-th INSERT (0-based) is executed, simulating a per-row error
    that import_w14_data must tolerate without aborting the batch.
    """

    def __init__(self, conn: "_MigrationStubConnection") -> None:
        self._conn = conn

    def __enter__(self) -> "_MigrationStubCursor":
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN001
        return None

    def execute(self, stmt: str, params=None) -> None:  # noqa: ANN001
        # Track INSERT calls only — everything else (COUNT, SELECT id, etc)
        # passes through.
        if stmt.lstrip().lower().startswith("insert"):
            idx = self._conn.insert_call_index
            self._conn.insert_call_index += 1
            if (
                self._conn.fail_on_row_index is not None
                and idx == self._conn.fail_on_row_index
            ):
                raise RuntimeError(
                    f"stub PG insert error at row #{idx}"
                )
            self._conn.pending.append((stmt, list(params or [])))
        # COUNT(*) for verify_migration / idempotency check.
        elif "count(*)" in stmt.lower():
            # Default 0 — tests can override via ``conn.count_override``.
            self._conn._last_count_query = stmt
        elif stmt.lstrip().lower().startswith("select"):
            self._conn._last_select_query = stmt

    def fetchone(self):
        # Used by COUNT(*) — return committed row count by default.
        return (len(self._conn.executed),)

    def fetchall(self):
        return []


class _MigrationStubConnection:
    def __init__(self, fail_on_row_index: int | None = None) -> None:
        self.executed: list[tuple[str, list]] = []
        self.pending: list[tuple[str, list]] = []
        self.commit_count = 0
        self.rollback_count = 0
        self.fail_on_row_index = fail_on_row_index
        self.insert_call_index = 0
        self._last_count_query: str | None = None
        self._last_select_query: str | None = None

    def __enter__(self) -> "_MigrationStubConnection":
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN001
        return None

    def cursor(self) -> _MigrationStubCursor:
        return _MigrationStubCursor(self)

    def commit(self) -> None:
        self.executed.extend(self.pending)
        self.pending = []
        self.commit_count += 1

    def rollback(self) -> None:
        self.pending = []
        self.rollback_count += 1


class _MigrationStubPool:
    def __init__(self, fail_on_row_index: int | None = None) -> None:
        self.conn = _MigrationStubConnection(
            fail_on_row_index=fail_on_row_index,
        )

    def connection(self) -> _MigrationStubConnection:
        return self.conn


def _seed_sqlite(tmp_path, table: str, n_rows: int):
    """Build a tiny SQLite source with ``n_rows`` rows; return the path."""
    db_path = tmp_path / "src.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(f"CREATE TABLE {table} (id TEXT PRIMARY KEY, title TEXT)")
        conn.executemany(
            f"INSERT INTO {table} VALUES (?, ?)",
            [(f"id-{i}", f"title-{i}") for i in range(n_rows)],
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_import_w14_data_dry_run_does_not_commit(tmp_path):
    """Dry-run: every row passes transform+INSERT but rollback wins.

    Source has 7 rows, batch_size=3 -> 3 batches (3+3+1). With
    ``dry_run=True`` import_w14_data must:
      - record imported_row_count == 7 (every row's INSERT stub call
        was made successfully)
      - leave conn.executed empty (no commits ever fired)
      - call rollback at least once (final cleanup)
    """
    db_path = _seed_sqlite(tmp_path, "w14_test_run", 7)
    conn = _MigrationStubConnection()

    result = import_w14_data(
        conn, _manifest("w14_test_run"), db_path,
        dry_run=True, batch_size=3,
    )

    assert isinstance(result, MigrationResult)
    assert result.dry_run is True
    assert result.source_row_count == 7
    assert result.imported_row_count == 7
    assert result.failed_rows == 0
    # No batch commits in dry-run.
    assert conn.commit_count == 0
    assert conn.executed == []
    # At least one rollback (the dry-run cleanup).
    assert conn.rollback_count >= 1
    # applied=True even on dry-run when every row would have landed.
    assert result.applied is True


def test_import_w14_data_real_run_commits_per_batch(tmp_path):
    """Real run: COMMIT fires once per complete batch.

    Source has 10 rows, batch_size=3 -> batches of (3, 3, 3, 1).
    Expect commit_count == 4 (one per batch) and len(executed) == 10.
    """
    db_path = _seed_sqlite(tmp_path, "w14_test_run", 10)
    conn = _MigrationStubConnection()

    result = import_w14_data(
        conn, _manifest("w14_test_run"), db_path,
        dry_run=False, batch_size=3,
    )

    assert result.dry_run is False
    assert result.source_row_count == 10
    assert result.imported_row_count == 10
    assert result.failed_rows == 0
    assert result.applied is True
    # Four batches -> four commits.
    assert conn.commit_count == 4
    # Every row landed in executed (committed) state.
    assert len(conn.executed) == 10
    # Sanity: every executed entry is an INSERT.
    assert all(
        stmt.lstrip().lower().startswith("insert")
        for stmt, _ in conn.executed
    )


def test_import_w14_data_continues_past_row_error(tmp_path):
    """Per-row INSERT error is tolerated; loop completes; error recorded.

    Source has 10 rows, fail_on_row_index=2 -> row #3 (0-based 2)
    raises mid-INSERT. Expect imported_row_count == 9, failed_rows == 1,
    errors list has exactly 1 entry whose row_pk is 'id-2'.
    """
    db_path = _seed_sqlite(tmp_path, "w14_test_run", 10)
    conn = _MigrationStubConnection(fail_on_row_index=2)

    result = import_w14_data(
        conn, _manifest("w14_test_run"), db_path,
        dry_run=False, batch_size=5,
    )

    assert result.source_row_count == 10
    assert result.imported_row_count == 9
    assert result.failed_rows == 1
    assert len(result.errors) == 1
    assert result.errors[0]["row_pk"] == "id-2"
    assert "RuntimeError" in result.errors[0]["error"]
    assert "stub PG insert error" in result.errors[0]["error"]
    # applied=False because not every row landed.
    assert result.applied is False
    assert "Migracja niekompletna" in result.rationale


def test_run_w14_migration_pg_unreachable_returns_clean_result(
    tmp_path, monkeypatch,
):
    """PG unreachable: MigrationResult(applied=False, rationale mentions PG).

    Monkeypatches ``_get_pg_connection`` to return None — the wrapper
    must short-circuit before touching SQLite (so even a missing source
    file wouldn't matter) and emit a single audit row reflecting the
    aborted attempt.
    """
    audit_path = tmp_path / "migration_audit.jsonl"
    monkeypatch.setattr(migration_mod, "_get_pg_connection", lambda: None)

    # SQLite path is a sentinel — PG unreachable short-circuits early.
    result = run_w14_migration(
        _manifest("w14_test_run"),
        tmp_path / "ignored_unreachable.db",
        dry_run=False,
        audit_path=audit_path,
    )

    assert isinstance(result, MigrationResult)
    assert result.applied is False
    assert result.verified is False
    assert result.imported_row_count == 0
    assert "PG niedostepny" in result.rationale
    # Audit row still emitted.
    assert audit_path.exists()
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    import json as _json
    row = _json.loads(lines[0])
    assert row["type_id"] == "w14_test_run"
    assert row["applied"] is False
    assert row["dry_run"] is False
    assert "PG" in row["rationale"]


def test_run_w14_migration_emits_audit_jsonl(tmp_path, monkeypatch):
    """run_w14_migration appends one JSONL row per attempt to audit log.

    Pool stub returns a fresh _MigrationStubPool so the import path
    actually exercises commits + verify. Audit path is redirected via
    the ``audit_path`` kwarg so we can read it back for assertions.
    """
    db_path = _seed_sqlite(tmp_path, "w14_test_run", 4)
    audit_path = tmp_path / "migration_audit.jsonl"
    pool = _MigrationStubPool()
    monkeypatch.setattr(migration_mod, "_get_pg_connection", lambda: pool)

    result = run_w14_migration(
        _manifest("w14_test_run"), db_path,
        dry_run=False, audit_path=audit_path,
    )

    assert result.applied is True
    assert result.imported_row_count == 4
    # Exactly one JSONL row per migrated type.
    assert audit_path.exists()
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    import json as _json
    row = _json.loads(lines[0])
    assert row["type_id"] == "w14_test_run"
    assert row["imported_row_count"] == 4
    assert row["failed_rows"] == 0
    assert row["dry_run"] is False
    assert row["applied"] is True
    assert "ts" in row
    # rationale is truncated to <= 200 chars per the audit emitter.
    assert len(row["rationale"]) <= 200


def test_migration_result_to_dict_shape():
    """MigrationResult.to_dict() exposes the full G3 contract surface.

    Sanity check that the JSON shape returned to the operator UI carries
    every field consumers depend on: applied, verified, dry_run, errors,
    failed_rows, imported_row_count, source_row_count, rationale,
    sqlite_table, type_id.
    """
    r = MigrationResult(
        type_id="w14_test_run",
        sqlite_table="w14_test_runs",
        source_row_count=42,
        imported_row_count=40,
        failed_rows=2,
        errors=[{"row_pk": "id-7", "error": "insert: ValueError: bad json"}],
        applied=False,
        verified=False,
        rationale="Migracja niekompletna",
        dry_run=False,
    )
    payload = r.to_dict()
    expected_keys = {
        "type_id", "sqlite_table", "source_row_count",
        "imported_row_count", "failed_rows", "errors",
        "applied", "verified", "rationale", "dry_run",
    }
    assert set(payload.keys()) == expected_keys
    assert payload["errors"][0]["row_pk"] == "id-7"
