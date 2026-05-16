"""Test-only psycopg-compatible pool backed by SQLite (in-memory).

Per `08_audit_revisions.md` Revision 2 the advisor layer is PG-only in
production code. This shim satisfies the audit's allowance for "SQLite only as
in-memory test fixtures": module code calls `sylion.aeis.advisor._db.get_pool()`
which we monkey-patch to return this shim during pytest.

The shim translates the subset of PG idioms used by advisor `_db.py` modules:
    %s         -> ?
    JSONB      -> TEXT
    UUID       -> TEXT
    TIMESTAMPTZ-> REAL (epoch seconds, set at app layer)
    BOOLEAN    -> INTEGER (0/1)
    DOUBLE PRECISION -> REAL
    gen_random_uuid() -> lower(hex(randomblob(16)))
    now()      -> CURRENT_TIMESTAMP

Limitations: array types, enums, partitions, and PL/pgSQL triggers are not
supported. Module code must avoid those constructs (per audit_revisions.md the
canonical PG schema uses them, but module SQL only INSERT/SELECT/UPDATEs scalar
columns; arrays are JSON-encoded text in tests).
"""
from __future__ import annotations

import re
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterable


_PG_PARAM_RE = re.compile(r"%s")
_TYPE_TRANSLATIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bJSONB\b", re.IGNORECASE), "TEXT"),
    (re.compile(r"\bJSON\b(?![A-Z])", re.IGNORECASE), "TEXT"),
    (re.compile(r"\bUUID\b", re.IGNORECASE), "TEXT"),
    (re.compile(r"\bTIMESTAMPTZ\b", re.IGNORECASE), "REAL"),
    (re.compile(r"\bTIMESTAMP\b", re.IGNORECASE), "REAL"),
    (re.compile(r"\bBOOLEAN\b", re.IGNORECASE), "INTEGER"),
    (re.compile(r"\bDOUBLE PRECISION\b", re.IGNORECASE), "REAL"),
    (re.compile(r"\bSERIAL PRIMARY KEY\b", re.IGNORECASE), "INTEGER PRIMARY KEY AUTOINCREMENT"),
    (re.compile(r"\bgen_random_uuid\(\)", re.IGNORECASE), "lower(hex(randomblob(16)))"),
    (re.compile(r"\bnow\(\)", re.IGNORECASE), "CURRENT_TIMESTAMP"),
]


def translate_pg_to_sqlite(sql: str) -> str:
    """Translate a PG SQL fragment to SQLite-compatible form."""
    out = sql
    for pattern, replacement in _TYPE_TRANSLATIONS:
        out = pattern.sub(replacement, out)
    return out


def translate_query(query: str) -> str:
    """Translate %s param placeholders to ? for SQLite."""
    return _PG_PARAM_RE.sub("?", query)


class _CursorShim:
    """Mimics the subset of psycopg Cursor used by advisor _db modules."""

    def __init__(self, conn: sqlite3.Connection, lock: threading.RLock, *, dict_rows: bool):
        self._lock = lock
        self._conn = conn
        self._dict_rows = dict_rows
        self._cur: sqlite3.Cursor | None = None

    def __enter__(self) -> "_CursorShim":
        with self._lock:
            self._cur = self._conn.cursor()
        if self._dict_rows:
            self._cur.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._cur is not None:
            self._cur.close()
            self._cur = None

    def execute(self, query: str, params: Iterable[Any] | None = None) -> "_CursorShim":
        assert self._cur is not None
        with self._lock:
            self._cur.execute(translate_query(query), tuple(params) if params else ())
        return self

    def fetchone(self) -> Any:
        assert self._cur is not None
        with self._lock:
            row = self._cur.fetchone()
        if row is None:
            return None
        return dict(row) if self._dict_rows else tuple(row)

    def fetchall(self) -> list[Any]:
        assert self._cur is not None
        with self._lock:
            rows = self._cur.fetchall()
        if self._dict_rows:
            return [dict(r) for r in rows]
        return [tuple(r) for r in rows]

    @property
    def description(self):
        return self._cur.description if self._cur else None

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount if self._cur else -1


class _ConnectionShim:
    """Mimics the subset of psycopg Connection used by advisor _db modules."""

    def __init__(self, conn: sqlite3.Connection, lock: threading.RLock):
        self._conn = conn
        self._lock = lock

    def cursor(self, *, row_factory: Any = None) -> _CursorShim:
        # Treat anything truthy as dict_row request; modules use psycopg.rows.dict_row.
        return _CursorShim(self._conn, self._lock, dict_rows=row_factory is not None)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def rollback(self) -> None:
        with self._lock:
            self._conn.rollback()


class TestPool:
    """In-memory SQLite-backed pool that quacks like psycopg_pool.ConnectionPool."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(":memory:", check_same_thread=False, timeout=30.0)
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._closed = False

    @contextmanager
    def connection(self):
        conn_shim = _ConnectionShim(self._conn, self._lock)
        try:
            yield conn_shim
            conn_shim.commit()
        except Exception:
            conn_shim.rollback()
            raise

    def execute_script(self, script: str) -> None:
        """Run a multi-statement SQL script (translates PG types to SQLite)."""
        translated = translate_pg_to_sqlite(script)
        with self._lock:
            self._conn.executescript(translated)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def install_test_pool(monkeypatch: Any) -> TestPool:
    """Replace sylion.aeis.advisor._db._pool with a fresh SQLite-backed shim."""
    from sylion.aeis.advisor import _db as shared_db

    pool = TestPool()
    monkeypatch.setenv("SYLION_ADVISOR_FORCE_PG", "1")
    monkeypatch.setenv("SYLION_ALLOW_LLM_STUB", "1")
    monkeypatch.setenv("SYLION_FORCE_LLM_STUB", "1")
    shared_db.reset_pg_reachability()
    monkeypatch.setattr(shared_db, "_pool", pool, raising=False)
    return pool
