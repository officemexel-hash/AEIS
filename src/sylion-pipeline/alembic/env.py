"""Alembic env — async-aware, reads URL from env or alembic.ini."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override URL from env so CI / prod don't have to edit alembic.ini.
runtime_url = os.environ.get("ALEMBIC_DATABASE_URL") or os.environ.get("SYLION_DB_URL")
if runtime_url:
    config.set_main_option("sqlalchemy.url", runtime_url)

# We don't use SQLAlchemy ORM models — schema lives in raw SQL inside
# sylion.db.pg_migration._PG_SCHEMA_SQL. Alembic only tracks revisions;
# autogenerate is intentionally NOT supported.
target_metadata = None


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (use --sql)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
