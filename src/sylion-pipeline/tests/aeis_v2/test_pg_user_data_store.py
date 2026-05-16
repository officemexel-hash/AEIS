"""Tests for ``sylion.aeis_v2.gdpr_v2.pg_store.PgUserDataStore``.

These tests don't require a running Postgres instance — every test
injects a mocked connection_factory so we can verify the SQL surface,
the deep-merge semantics on upsert, and the soft-delete / hard-purge
contracts without external dependencies.
"""
from __future__ import annotations

import datetime as _dt
import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from sylion.aeis_v2.gdpr_v2 import (
    PG_SCHEMA_DDL,
    PgUserDataStore,
)


# ---------------------------------------------------------------------------
# Fake psycopg connection
# ---------------------------------------------------------------------------


class _FakeCursor:
    """Implements the subset of psycopg.Cursor PgUserDataStore needs."""

    def __init__(self, conn: "_FakeConnection") -> None:
        self._conn = conn
        self.executed: list[tuple[str, tuple]] = []
        self._fetchone_result: Any = None
        self._fetchall_result: list[Any] = []
        self.rowcount: int = 0

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.executed.append((sql, params))
        # Lookup behaviour from parent.
        self._conn._handle_execute(self, sql, params)

    def fetchone(self) -> Any:
        return self._fetchone_result

    def fetchall(self) -> list[Any]:
        return self._fetchall_result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeConnection:
    """Backed by an in-memory dict — implements the psycopg surface tests use."""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.committed = 0
        self.rolled_back = 0
        self._all_cursors: list[_FakeCursor] = []
        self.last_executed: list[tuple[str, tuple]] = []

    def cursor(self) -> _FakeCursor:
        c = _FakeCursor(self)
        self._all_cursors.append(c)
        return c

    def commit(self) -> None:
        self.committed += 1

    def rollback(self) -> None:
        self.rolled_back += 1

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    # Behaviour for execute — minimal SQL dispatcher.
    def _handle_execute(
        self, cur: _FakeCursor, sql: str, params: tuple,
    ) -> None:
        self.last_executed.append((sql, params))
        sql_n = " ".join(sql.split()).strip().lower()

        if "create table" in sql_n:
            return  # DDL no-op

        if sql_n.startswith("select user_id, data, deleted_at"):
            user_id = params[0]
            row = self.rows.get(user_id)
            if row is None:
                cur._fetchone_result = None
                return
            cur._fetchone_result = (
                user_id,
                json.dumps(row.get("data", {})),
                row.get("deleted_at"),
                row.get("updated_at", _dt.datetime(2026, 4, 28)),
                row.get("created_at", _dt.datetime(2026, 4, 28)),
            )
            return

        if sql_n.startswith("select data from gdpr_users"):
            user_id = params[0]
            row = self.rows.get(user_id)
            if row is None:
                cur._fetchone_result = None
            else:
                cur._fetchone_result = (json.dumps(row.get("data", {})),)
            return

        if sql_n.startswith("insert into gdpr_users"):
            user_id, data_json = params
            existing = self.rows.get(user_id, {})
            self.rows[user_id] = {
                **existing,
                "data": json.loads(data_json),
                "deleted_at": None,
                "updated_at": _dt.datetime(2026, 4, 28),
            }
            cur.rowcount = 1
            return

        if sql_n.startswith("update gdpr_users set deleted_at"):
            ts, user_id = params
            row = self.rows.get(user_id)
            if row is None or row.get("deleted_at") is not None:
                cur.rowcount = 0
                return
            row["deleted_at"] = _dt.datetime.fromtimestamp(
                ts, tz=_dt.timezone.utc,
            )
            cur.rowcount = 1
            return

        if sql_n.startswith("delete from gdpr_users"):
            user_id = params[0]
            row = self.rows.get(user_id)
            if row is None or row.get("deleted_at") is None:
                cur.rowcount = 0
                return
            del self.rows[user_id]
            cur.rowcount = 1
            return

        if sql_n.startswith("select user_id from gdpr_users"):
            cur._fetchall_result = [
                (uid,) for uid, row in self.rows.items()
                if row.get("deleted_at") is None
            ]
            return

        if sql_n.startswith("select user_id, deleted_at from gdpr_users"):
            cur._fetchall_result = [
                (uid, row["deleted_at"]) for uid, row in self.rows.items()
                if row.get("deleted_at") is not None
            ]
            return


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


def test_pg_schema_ddl_is_idempotent_text() -> None:
    """The DDL string must contain ``IF NOT EXISTS`` for safety."""
    assert "CREATE TABLE IF NOT EXISTS gdpr_users" in PG_SCHEMA_DDL
    assert "CREATE INDEX IF NOT EXISTS gdpr_users_deleted_at_idx" in PG_SCHEMA_DDL


# ---------------------------------------------------------------------------
# ensure_schema
# ---------------------------------------------------------------------------


def test_ensure_schema_runs_ddl_once() -> None:
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    store.ensure_schema()
    store.ensure_schema()  # idempotent — second call is a no-op
    # First call ran the DDL; second one didn't open a new cursor.
    create_executions = [
        call for call in conn.last_executed
        if "create table" in call[0].lower()
    ]
    assert len(create_executions) == 1


# ---------------------------------------------------------------------------
# get / upsert
# ---------------------------------------------------------------------------


def test_upsert_creates_row() -> None:
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    store.upsert("u-1", {"name": "Robert", "tier": "ops"})
    row = store.get("u-1")
    assert row is not None
    assert row["name"] == "Robert"
    assert row["tier"] == "ops"
    assert row["user_id"] == "u-1"


def test_upsert_deep_merges_existing() -> None:
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    store.upsert("u-1", {"profile": {"name": "Robert", "city": "Wro"}})
    store.upsert("u-1", {"profile": {"city": "Krk"}, "tier": "ops"})
    row = store.get("u-1")
    assert row["profile"]["name"] == "Robert"
    assert row["profile"]["city"] == "Krk"
    assert row["tier"] == "ops"


def test_get_missing_returns_none() -> None:
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    assert store.get("absent") is None


def test_get_soft_deleted_returns_none() -> None:
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    store.upsert("u-1", {"name": "Robert"})
    store.soft_delete("u-1", ts=1000.0)
    assert store.get("u-1") is None


def test_upsert_resurrects_soft_deleted() -> None:
    """RECTIFICATION on a soft-deleted user clears deleted_at (Article 12.3)."""
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    store.upsert("u-1", {"name": "Robert"})
    store.soft_delete("u-1", ts=1000.0)
    assert store.get("u-1") is None  # soft-deleted hidden
    store.upsert("u-1", {"email": "robert@x.com"})
    row = store.get("u-1")
    assert row is not None
    assert row["email"] == "robert@x.com"
    # The deleted_at must be cleared on the underlying row.
    assert conn.rows["u-1"]["deleted_at"] is None


# ---------------------------------------------------------------------------
# soft_delete
# ---------------------------------------------------------------------------


def test_soft_delete_missing_returns_false() -> None:
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    assert store.soft_delete("absent", ts=1.0) is False


def test_soft_delete_alive_returns_true() -> None:
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    store.upsert("u-1", {"name": "x"})
    assert store.soft_delete("u-1", ts=1000.0) is True


def test_soft_delete_already_erased_returns_false() -> None:
    """Double-erase returns False — only flips on the first call."""
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    store.upsert("u-1", {"name": "x"})
    store.soft_delete("u-1", ts=1000.0)
    assert store.soft_delete("u-1", ts=2000.0) is False


# ---------------------------------------------------------------------------
# export_portable
# ---------------------------------------------------------------------------


def test_export_portable_returns_versioned_bundle() -> None:
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    store.upsert("u-1", {"name": "Robert"})
    bundle = store.export_portable("u-1")
    assert bundle is not None
    assert bundle["schema"] == "sylion.gdpr.dsr.portability/v1"
    assert "exported_at" in bundle
    assert bundle["user"]["name"] == "Robert"


def test_export_portable_missing_returns_none() -> None:
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    assert store.export_portable("absent") is None


# ---------------------------------------------------------------------------
# list_users + list_with_deleted_at + hard_purge — PurgeableStore surface
# ---------------------------------------------------------------------------


def test_list_users_skips_deleted() -> None:
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    store.upsert("u-1", {})
    store.upsert("u-2", {})
    store.soft_delete("u-1", ts=1.0)
    assert store.list_users() == ["u-2"]


def test_list_with_deleted_at_returns_only_soft_deleted() -> None:
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    store.upsert("u-1", {})
    store.upsert("u-2", {})
    store.soft_delete("u-1", ts=99.0)
    rows = list(store.list_with_deleted_at())
    assert len(rows) == 1
    assert rows[0][0] == "u-1"
    assert rows[0][1] == pytest.approx(99.0, abs=1.0)


def test_hard_purge_only_acts_on_soft_deleted() -> None:
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    store.upsert("u-1", {"name": "x"})
    # Refuses alive user.
    assert store.hard_purge("u-1") is False
    assert "u-1" in conn.rows  # row still there
    # Accepts soft-deleted user.
    store.soft_delete("u-1", ts=1.0)
    assert store.hard_purge("u-1") is True
    assert "u-1" not in conn.rows


def test_hard_purge_missing_returns_false() -> None:
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    assert store.hard_purge("absent") is False


# ---------------------------------------------------------------------------
# Concurrency primitives — SELECT … FOR UPDATE serialisation marker.
# ---------------------------------------------------------------------------


def test_upsert_executes_select_for_update_under_lock() -> None:
    """Per Kimi k2: upsert must SELECT … FOR UPDATE before merging."""
    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    store.upsert("u-1", {"name": "x"})
    # First execute should be the SELECT FOR UPDATE.
    assert any("for update" in sql.lower() for sql, _ in conn.last_executed)


# ---------------------------------------------------------------------------
# Compatibility with HardPurgeCron
# ---------------------------------------------------------------------------


def test_pg_store_is_purgeable_store_for_hard_purge_cron(tmp_path) -> None:
    """End-to-end: HardPurgeCron picks up PgUserDataStore unchanged."""
    from sylion.aeis_v2.gdpr_v2 import HardPurgeCron

    conn = _FakeConnection()
    store = PgUserDataStore(connection_factory=lambda: conn)
    store.upsert("u-old", {"x": 1})
    store.soft_delete("u-old", ts=0.0)

    cron = HardPurgeCron(
        store,
        audit_log_path=tmp_path / "purge.jsonl",
        grace_period_s=10,
    )
    report = cron.purge_expired(now=1000.0)
    assert "u-old" in report.purged
    assert "u-old" not in conn.rows
