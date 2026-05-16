"""Tests for ``sylion.aeis_v2.deployment.cost_ledger_pg_migrator``.

Mocks psycopg via a fake connection factory — no live Postgres required.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sylion.aeis_v2.audit_chain import verify_chain
from sylion.aeis_v2.deployment.cost_ledger_pg_migrator import (
    DEFAULT_BATCH_SIZE,
    PG_COST_LEDGER_DDL,
    CostLedgerPgMigrator,
    FileMigrationOutcome,
    MigrationReport,
    parse_jsonl,
)


# ---------------------------------------------------------------------------
# Fake psycopg connection — tracks executemany batches in-memory.
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self, conn: "_FakeConn") -> None:
        self._conn = conn
        self.rowcount: int = 0

    def execute(self, sql: str, params: tuple = ()) -> None:
        # DDL goes here; just track it.
        self._conn.executed.append(("execute", sql, params))

    def executemany(self, sql: str, batch: list[tuple]) -> None:
        new_rows = 0
        for row in batch:
            decision_id = row[0]
            if decision_id in self._conn.records:
                # ON CONFLICT DO NOTHING simulates here as skip.
                continue
            self._conn.records[decision_id] = row
            new_rows += 1
        self.rowcount = new_rows
        self._conn.executed.append(("executemany", sql, len(batch)))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeConn:
    def __init__(self) -> None:
        self.records: dict[str, tuple] = {}
        self.executed: list[tuple] = []

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)

    def commit(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _factory_for(conn: _FakeConn):
    return lambda: conn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _row(decision_id: str, **overrides: Any) -> dict[str, Any]:
    base = {
        "ts": 1714298400.0,
        "session_id": "sess-1",
        "decision_id": decision_id,
        "host": "host-1",
        "model": "claude-opus-4.7",
        "tokens_in": 100,
        "tokens_out": 50,
        "cost_usd": 0.05,
        "metadata": {"trace": "x"},
    }
    base.update(overrides)
    return base


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


def test_pg_ddl_is_idempotent() -> None:
    assert "CREATE TABLE IF NOT EXISTS cost_records" in PG_COST_LEDGER_DDL
    assert "CREATE INDEX IF NOT EXISTS cost_records_ts_idx" in PG_COST_LEDGER_DDL


def test_default_batch_size_is_500() -> None:
    assert DEFAULT_BATCH_SIZE == 500


def test_constructor_rejects_zero_batch_size() -> None:
    with pytest.raises(ValueError):
        CostLedgerPgMigrator(connection_factory=lambda: _FakeConn(), batch_size=0)


def test_constructor_rejects_missing_factory() -> None:
    with pytest.raises(ValueError):
        CostLedgerPgMigrator(connection_factory=None)


# ---------------------------------------------------------------------------
# parse_jsonl helper
# ---------------------------------------------------------------------------


def test_parse_jsonl_yields_rows(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    _write_jsonl(p, [_row("d1"), _row("d2")])
    pairs = list(parse_jsonl(p))
    assert len(pairs) == 2
    assert all(row is not None for _, row in pairs)


def test_parse_jsonl_yields_none_for_bad_line(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text(json.dumps(_row("d1")) + "\nnot-json\n", encoding="utf-8")
    pairs = list(parse_jsonl(p))
    assert pairs[0][1] is not None
    assert pairs[1][1] is None


def test_parse_jsonl_skips_empty_lines(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text(json.dumps(_row("d1")) + "\n\n\n", encoding="utf-8")
    assert len(list(parse_jsonl(p))) == 1


def test_parse_jsonl_missing_file_returns_empty(tmp_path: Path) -> None:
    assert list(parse_jsonl(tmp_path / "absent.jsonl")) == []


# ---------------------------------------------------------------------------
# ensure_schema
# ---------------------------------------------------------------------------


def test_ensure_schema_runs_ddl_once(tmp_path: Path) -> None:
    conn = _FakeConn()
    m = CostLedgerPgMigrator(
        connection_factory=_factory_for(conn),
        audit_log_path=tmp_path / "audit.jsonl",
    )
    m.ensure_schema()
    m.ensure_schema()
    ddl_calls = [
        c for c in conn.executed
        if c[0] == "execute" and "create table" in c[1].lower()
    ]
    assert len(ddl_calls) == 1


# ---------------------------------------------------------------------------
# migrate_file — happy + edge paths
# ---------------------------------------------------------------------------


def test_migrate_file_happy_path(tmp_path: Path) -> None:
    conn = _FakeConn()
    m = CostLedgerPgMigrator(
        connection_factory=_factory_for(conn),
        audit_log_path=tmp_path / "audit.jsonl",
    )
    p = tmp_path / "cost.jsonl"
    _write_jsonl(p, [_row("d1"), _row("d2"), _row("d3")])
    out = m.migrate_file(p)
    assert isinstance(out, FileMigrationOutcome)
    assert out.rows_seen == 3
    assert out.rows_inserted == 3
    assert out.rows_invalid == 0
    assert out.sha256


def test_migrate_file_idempotent(tmp_path: Path) -> None:
    """Re-running the same migration on the same file: zero new rows."""
    conn = _FakeConn()
    m = CostLedgerPgMigrator(
        connection_factory=_factory_for(conn),
        audit_log_path=tmp_path / "audit.jsonl",
    )
    p = tmp_path / "cost.jsonl"
    _write_jsonl(p, [_row("d1"), _row("d2")])

    first = m.migrate_file(p)
    second = m.migrate_file(p)
    assert first.rows_inserted == 2
    assert second.rows_inserted == 0
    assert second.rows_skipped_existing == 2


def test_migrate_file_counts_invalid_rows(tmp_path: Path) -> None:
    conn = _FakeConn()
    m = CostLedgerPgMigrator(
        connection_factory=_factory_for(conn),
        audit_log_path=tmp_path / "audit.jsonl",
    )
    p = tmp_path / "cost.jsonl"
    valid = json.dumps(_row("d1"))
    invalid_no_decision = json.dumps({"ts": 1.0, "model": "x"})
    not_json = "garbage"
    p.write_text(
        valid + "\n" + invalid_no_decision + "\n" + not_json + "\n",
        encoding="utf-8",
    )
    out = m.migrate_file(p)
    assert out.rows_seen == 3
    assert out.rows_inserted == 1
    assert out.rows_invalid == 2


def test_migrate_file_missing_returns_zero(tmp_path: Path) -> None:
    conn = _FakeConn()
    m = CostLedgerPgMigrator(
        connection_factory=_factory_for(conn),
        audit_log_path=tmp_path / "audit.jsonl",
    )
    out = m.migrate_file(tmp_path / "absent.jsonl")
    assert out.rows_seen == 0
    assert out.rows_inserted == 0
    assert out.sha256 == ""


def test_migrate_file_respects_batch_size(tmp_path: Path) -> None:
    """Small batch_size triggers multiple executemany invocations."""
    conn = _FakeConn()
    m = CostLedgerPgMigrator(
        connection_factory=_factory_for(conn),
        batch_size=2,
        audit_log_path=tmp_path / "audit.jsonl",
    )
    p = tmp_path / "cost.jsonl"
    _write_jsonl(p, [_row(f"d{i}") for i in range(5)])
    out = m.migrate_file(p)
    assert out.rows_inserted == 5
    em_calls = [c for c in conn.executed if c[0] == "executemany"]
    # 5 rows / batch=2 → 3 batches (2, 2, 1).
    assert len(em_calls) == 3


# ---------------------------------------------------------------------------
# migrate_directory
# ---------------------------------------------------------------------------


def test_migrate_directory_aggregates_outcomes(tmp_path: Path) -> None:
    conn = _FakeConn()
    m = CostLedgerPgMigrator(
        connection_factory=_factory_for(conn),
        audit_log_path=tmp_path / "audit.jsonl",
    )
    _write_jsonl(tmp_path / "cost_ledger.jsonl", [_row("d1")])
    _write_jsonl(tmp_path / "cost_ledger.2026-04-27.1.jsonl", [_row("d2")])
    report = m.migrate_directory(tmp_path)
    assert isinstance(report, MigrationReport)
    assert report.total_rows_inserted == 2
    assert len(report.files) == 2


def test_migrate_directory_glob_excludes_other_files(tmp_path: Path) -> None:
    """Default glob matches only cost_ledger*.jsonl."""
    conn = _FakeConn()
    m = CostLedgerPgMigrator(
        connection_factory=_factory_for(conn),
        audit_log_path=tmp_path / "audit.jsonl",
    )
    _write_jsonl(tmp_path / "cost_ledger.jsonl", [_row("d1")])
    _write_jsonl(tmp_path / "gdpr_dsr.jsonl", [{"action": "access"}])
    report = m.migrate_directory(tmp_path)
    assert len(report.files) == 1
    assert "cost_ledger" in report.files[0].path


def test_migrate_directory_empty_dir_no_files(tmp_path: Path) -> None:
    conn = _FakeConn()
    m = CostLedgerPgMigrator(
        connection_factory=_factory_for(conn),
        audit_log_path=tmp_path / "audit.jsonl",
    )
    report = m.migrate_directory(tmp_path / "empty")
    assert report.files == []
    assert report.total_rows_inserted == 0


# ---------------------------------------------------------------------------
# Audit chain emission
# ---------------------------------------------------------------------------


def test_migration_audit_chain_verifies(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    conn = _FakeConn()
    m = CostLedgerPgMigrator(
        connection_factory=_factory_for(conn), audit_log_path=audit,
    )
    m.ensure_schema()
    _write_jsonl(tmp_path / "cost_ledger.jsonl", [_row("d1")])
    m.migrate_directory(tmp_path)
    assert verify_chain(audit) == []
    contents = [
        json.loads(l)["content"]
        for l in audit.read_text(encoding="utf-8").splitlines() if l
    ]
    kinds = {c.get("kind") for c in contents}
    assert "cost_ledger_migration.schema_applied" in kinds
    assert "cost_ledger_migration.file" in kinds
    assert "cost_ledger_migration.run" in kinds


# ---------------------------------------------------------------------------
# Dataclass round-trip
# ---------------------------------------------------------------------------


def test_outcome_to_dict_serialisable() -> None:
    o = FileMigrationOutcome(
        path="/x.jsonl", rows_seen=10, rows_inserted=8,
        rows_skipped_existing=1, rows_invalid=1,
        elapsed_ms=12.345, sha256="abc",
    )
    d = o.to_dict()
    json.dumps(d)
    assert d["rows_inserted"] == 8


def test_report_duration_clamps_negative_to_zero() -> None:
    r = MigrationReport(
        files=[], started_at=20.0, finished_at=15.0,
    )
    assert r.duration_s == 0.0
