"""Tests for sylion.db.pg_migration -- PostgreSQL schema migration.

All database interactions are mocked. No live PostgreSQL required.
Covers:
  1. create_pg_engine -- URL resolution, env var fallback, error on missing URL
  2. run_pg_migration -- schema DDL execution, engine creation fallback
  3. check_pg_health -- ok path, error path, engine disposal
  4. _PG_SCHEMA_SQL -- contains expected table definitions
"""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sylion.db.pg_migration import (
    _PG_SCHEMA_SQL,
    check_pg_health,
    create_pg_engine,
    run_pg_migration,
)


def _run(coro):
    """Run an async coroutine synchronously for testing."""
    return asyncio.run(coro)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(autouse=True)
def _clean_env():
    """Remove PostgreSQL URL env vars before each test."""
    original = os.environ.pop("SYLION_DB_URL", None)
    original_database_url = os.environ.pop("DATABASE_URL", None)
    yield
    if original is not None:
        os.environ["SYLION_DB_URL"] = original
    else:
        os.environ.pop("SYLION_DB_URL", None)
    if original_database_url is not None:
        os.environ["DATABASE_URL"] = original_database_url
    else:
        os.environ.pop("DATABASE_URL", None)


def _make_mock_engine():
    """Create a mock AsyncEngine with begin() and connect() context managers."""
    engine = MagicMock()

    # Mock conn for begin() context manager
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 13
    mock_conn.execute = AsyncMock(return_value=mock_result)

    # begin() returns async context manager yielding mock_conn
    begin_cm = AsyncMock()
    begin_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    begin_cm.__aexit__ = AsyncMock(return_value=False)
    engine.begin.return_value = begin_cm

    # connect() returns async context manager yielding same mock_conn
    connect_cm = AsyncMock()
    connect_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    connect_cm.__aexit__ = AsyncMock(return_value=False)
    engine.connect.return_value = connect_cm

    engine.dispose = AsyncMock()
    return engine, mock_conn


# ===========================================================================
# create_pg_engine
# ===========================================================================


class TestCreatePgEngine:
    """Tests for create_pg_engine()."""

    @patch("sylion.db.pg_migration.create_async_engine")
    def test_creates_engine_with_explicit_url(self, mock_create):
        """Passing db_url directly creates engine with that URL."""
        mock_create.return_value = MagicMock(name="engine")
        engine = create_pg_engine("postgresql+asyncpg://user:pass@localhost/testdb")

        mock_create.assert_called_once_with(
            "postgresql+asyncpg://user:pass@localhost/testdb",
            echo=False,
            pool_pre_ping=True,
        )
        assert engine is mock_create.return_value

    @patch("sylion.db.pg_migration.create_async_engine")
    def test_uses_env_var_when_no_url_passed(self, mock_create):
        """Falls back to SYLION_DB_URL environment variable."""
        os.environ["SYLION_DB_URL"] = "postgresql+asyncpg://env:pw@dbhost/mydb"
        mock_create.return_value = MagicMock(name="engine")
        engine = create_pg_engine()

        mock_create.assert_called_once_with(
            "postgresql+asyncpg://env:pw@dbhost/mydb",
            echo=False,
            pool_pre_ping=True,
        )
        assert engine is mock_create.return_value

    @patch("sylion.db.pg_migration.create_async_engine")
    def test_uses_database_url_alias_when_no_sylion_url(self, mock_create):
        """Falls back to DATABASE_URL when SYLION_DB_URL is not set."""
        os.environ["DATABASE_URL"] = "postgresql+asyncpg://alias:pw@dbhost/mydb"
        mock_create.return_value = MagicMock(name="engine")
        engine = create_pg_engine()

        mock_create.assert_called_once_with(
            "postgresql+asyncpg://alias:pw@dbhost/mydb",
            echo=False,
            pool_pre_ping=True,
        )
        assert engine is mock_create.return_value

    def test_raises_value_error_when_no_url_available(self):
        """Raises ValueError when neither db_url nor env var is set."""
        with pytest.raises(ValueError, match="PostgreSQL URL required"):
            create_pg_engine()

    @patch("sylion.db.pg_migration.create_async_engine")
    def test_explicit_url_overrides_env_var(self, mock_create):
        """Explicit db_url takes precedence over SYLION_DB_URL."""
        os.environ["SYLION_DB_URL"] = "postgresql+asyncpg://env:pw@host/db"
        mock_create.return_value = MagicMock(name="engine")
        create_pg_engine("postgresql+asyncpg://explicit:pw@host/db")

        mock_create.assert_called_once_with(
            "postgresql+asyncpg://explicit:pw@host/db",
            echo=False,
            pool_pre_ping=True,
        )

    @patch("sylion.db.pg_migration.create_async_engine")
    def test_engine_options(self, mock_create):
        """Engine is created with echo=False and pool_pre_ping=True."""
        mock_create.return_value = MagicMock(name="engine")
        create_pg_engine("postgresql+asyncpg://u:p@h/d")

        _, kwargs = mock_create.call_args
        assert kwargs["echo"] is False
        assert kwargs["pool_pre_ping"] is True

    @patch("sylion.db.pg_migration.create_async_engine")
    def test_empty_string_url_raises(self, mock_create):
        """Empty string db_url should still raise ValueError."""
        with pytest.raises(ValueError, match="PostgreSQL URL required"):
            create_pg_engine("")


# ===========================================================================
# run_pg_migration
# ===========================================================================


class TestRunPgMigration:
    """Tests for run_pg_migration()."""

    @patch("sylion.db.pg_migration.create_pg_engine")
    def test_executes_schema_ddl(self, mock_create_engine):
        """run_pg_migration executes the full schema SQL."""
        engine, mock_conn = _make_mock_engine()

        with patch.object(asyncio, "get_event_loop") if False else patch(
            "sylion.db.pg_migration.create_pg_engine", return_value=engine
        ):
            result = _run(run_pg_migration(engine))

        # The DDL was executed via conn.execute
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0][0]
        # The text() wrapper contains our schema
        assert call_args.text == _PG_SCHEMA_SQL

    @patch("sylion.db.pg_migration.create_pg_engine")
    def test_uses_provided_engine(self, mock_create_engine):
        """When engine is passed, it is used and create_pg_engine is NOT called."""
        engine, mock_conn = _make_mock_engine()
        result = _run(run_pg_migration(engine))

        mock_create_engine.assert_not_called()
        assert result is engine

    @patch("sylion.db.pg_migration.create_pg_engine")
    def test_creates_engine_when_none_passed(self, mock_create_engine):
        """When engine=None, creates one from env var."""
        engine, mock_conn = _make_mock_engine()
        mock_create_engine.return_value = engine

        result = _run(run_pg_migration(None))

        mock_create_engine.assert_called_once()
        assert result is engine

    @patch("sylion.db.pg_migration.create_pg_engine")
    def test_returns_engine(self, mock_create_engine):
        """Returns the engine for caller to manage lifecycle."""
        engine, _ = _make_mock_engine()
        result = _run(run_pg_migration(engine))
        assert result is engine

    @patch("sylion.db.pg_migration.create_pg_engine")
    def test_schema_sql_contains_all_tables(self, mock_create_engine):
        """The embedded schema contains the 13 core expected tables."""
        expected_tables = [
            "modules", "module_events", "evidence_entries", "decisions",
            "council_sessions", "council_votes", "evidence_packs",
            "evidence_artefacts", "contracts", "agents", "skills",
            "runs", "audit_log",
        ]
        for table in expected_tables:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in _PG_SCHEMA_SQL, (
                f"Missing table: {table}"
            )

    @patch("sylion.db.pg_migration.create_pg_engine")
    def test_schema_uses_jsonb(self, mock_create_engine):
        """PostgreSQL schema uses JSONB for JSON columns."""
        assert "JSONB" in _PG_SCHEMA_SQL
        # module_events.payload should be JSONB
        assert "payload        JSONB" in _PG_SCHEMA_SQL

    @patch("sylion.db.pg_migration.create_pg_engine")
    def test_schema_uses_timestamptz(self, mock_create_engine):
        """PostgreSQL schema uses TIMESTAMPTZ for timestamps."""
        assert "TIMESTAMPTZ" in _PG_SCHEMA_SQL

    @patch("sylion.db.pg_migration.create_pg_engine")
    def test_schema_uses_if_not_exists(self, mock_create_engine):
        """All CREATE TABLE statements use IF NOT EXISTS for idempotency."""
        create_lines = [
            line.strip()
            for line in _PG_SCHEMA_SQL.splitlines()
            if line.strip().startswith("CREATE TABLE")
        ]
        assert len(create_lines) >= 13
        assert all(line.startswith("CREATE TABLE IF NOT EXISTS") for line in create_lines)

    @patch("sylion.db.pg_migration.create_pg_engine")
    def test_schema_has_indexes(self, mock_create_engine):
        """Schema creates indexes for efficient querying."""
        assert "CREATE INDEX IF NOT EXISTS" in _PG_SCHEMA_SQL
        index_count = _PG_SCHEMA_SQL.count("CREATE INDEX IF NOT EXISTS")
        assert index_count > 13  # At least one index per table


# ===========================================================================
# check_pg_health
# ===========================================================================


class TestCheckPgHealth:
    """Tests for check_pg_health()."""

    def test_healthy_check_returns_ok(self):
        """Successful health check returns status=ok with table count."""
        engine, mock_conn = _make_mock_engine()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 13
        mock_conn.execute = AsyncMock(return_value=mock_result)

        # Re-bind connect to use updated mock_conn
        connect_cm = AsyncMock()
        connect_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        connect_cm.__aexit__ = AsyncMock(return_value=False)
        engine.connect.return_value = connect_cm

        result = _run(check_pg_health(engine))

        assert result["status"] == "ok"
        assert result["db_mode"] == "postgres"
        assert result["tables"] == 13

    def test_error_check_returns_error_status(self):
        """Connection failure returns status=error with error message."""
        engine, _ = _make_mock_engine()
        connect_cm = AsyncMock()
        connect_cm.__aenter__ = AsyncMock(side_effect=Exception("connection refused"))
        connect_cm.__aexit__ = AsyncMock(return_value=False)
        engine.connect.return_value = connect_cm

        result = _run(check_pg_health(engine))

        assert result["status"] == "error"
        assert result["db_mode"] == "postgres"
        assert "connection refused" in result["error"]

    def test_disposes_engine_when_none_passed(self):
        """When engine=None (auto-created), health check disposes it on error."""
        mock_engine, _ = _make_mock_engine()
        connect_cm = AsyncMock()
        connect_cm.__aenter__ = AsyncMock(side_effect=Exception("fail"))
        connect_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect.return_value = connect_cm

        with patch("sylion.db.pg_migration.create_pg_engine", return_value=mock_engine):
            result = _run(check_pg_health(None))

        assert result["status"] == "error"
        mock_engine.dispose.assert_called_once()

    def test_does_not_dispose_provided_engine_on_success(self):
        """When engine is explicitly provided, it is NOT disposed."""
        engine, mock_conn = _make_mock_engine()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_conn.execute = AsyncMock(return_value=mock_result)

        connect_cm = AsyncMock()
        connect_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        connect_cm.__aexit__ = AsyncMock(return_value=False)
        engine.connect.return_value = connect_cm

        result = _run(check_pg_health(engine))

        assert result["status"] == "ok"
        engine.dispose.assert_not_called()

    def test_disposes_auto_engine_on_success(self):
        """Auto-created engine is disposed even on success path."""
        mock_engine, mock_conn = _make_mock_engine()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 7
        mock_conn.execute = AsyncMock(return_value=mock_result)

        connect_cm = AsyncMock()
        connect_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        connect_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect.return_value = connect_cm

        with patch("sylion.db.pg_migration.create_pg_engine", return_value=mock_engine):
            result = _run(check_pg_health(None))

        assert result["status"] == "ok"
        assert result["tables"] == 7
        mock_engine.dispose.assert_called_once()

    def test_query_uses_information_schema(self):
        """Health check queries information_schema for table count."""
        engine, mock_conn = _make_mock_engine()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_conn.execute = AsyncMock(return_value=mock_result)

        connect_cm = AsyncMock()
        connect_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        connect_cm.__aexit__ = AsyncMock(return_value=False)
        engine.connect.return_value = connect_cm

        _run(check_pg_health(engine))

        call_args = mock_conn.execute.call_args[0][0]
        assert "information_schema.tables" in call_args.text
        assert "table_schema = 'public'" in call_args.text


# ===========================================================================
# _PG_SCHEMA_SQL validation
# ===========================================================================


class TestSchemaContent:
    """Validate the embedded _PG_SCHEMA_SQL string."""

    def test_contains_foreign_keys(self):
        """Schema includes foreign key constraints."""
        assert "FOREIGN KEY (session_id) REFERENCES council_sessions" in _PG_SCHEMA_SQL
        assert "FOREIGN KEY (pack_id) REFERENCES evidence_packs" in _PG_SCHEMA_SQL

    def test_contains_defaults(self):
        """Schema includes DEFAULT values for columns."""
        assert "DEFAULT NOW()" in _PG_SCHEMA_SQL
        assert "DEFAULT 'active'" in _PG_SCHEMA_SQL
        assert "DEFAULT 'pending'" in _PG_SCHEMA_SQL
