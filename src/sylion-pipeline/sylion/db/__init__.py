"""sylion.db -- database migration and connectivity layer.

Supports two modes, selected via environment variables:

- **SQLite** (default): synchronous, used by tests and local development.
  Tables are created by ``sylion.db.migration.run_migration``.

- **PostgreSQL** (opt-in): async via asyncpg + SQLAlchemy.
  Activate with ``SYLION_DB_MODE=postgres`` and ``SYLION_DB_URL=postgresql+asyncpg://...``.
  Tables are created by ``sylion.db.pg_migration.run_pg_migration``.
"""
import os

from sylion.db.migration import run_migration


def get_db_mode() -> str:
    """Return the active database mode: 'sqlite' or 'postgres'."""
    return os.environ.get("SYLION_DB_MODE", "sqlite")


def is_postgres() -> bool:
    """Check if PostgreSQL mode is active."""
    return get_db_mode() == "postgres"


async def init_database():
    """Initialize the database based on the active mode.

    For SQLite: runs synchronous migration.
    For PostgreSQL: runs async migration.
    """
    if is_postgres():
        from sylion.db.pg_migration import run_pg_migration
        await run_pg_migration()
    else:
        run_migration()


__all__ = ["run_migration", "get_db_mode", "is_postgres", "init_database"]
