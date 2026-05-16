"""
SYLION AEIS -- Migration Runner

Applies PostgreSQL migration scripts in order.
Tracks applied migrations in a _migrations table.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

log = logging.getLogger("sylion.db.migrate")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def run_migrations(engine: Optional[AsyncEngine] = None,
                         db_url: Optional[str] = None,
                         migrations_dir: Optional[Path] = None) -> list[str]:
    """Apply all pending PostgreSQL migration scripts.

    Returns list of applied migration filenames.
    """
    _engine = engine or _create_engine(db_url)
    mdir = migrations_dir or MIGRATIONS_DIR

    applied = []

    try:
        async with _engine.begin() as conn:
            # Ensure migration tracking table exists
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    filename    TEXT PRIMARY KEY,
                    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    checksum    TEXT NOT NULL DEFAULT ''
                )
            """))

            # Get already-applied migrations
            result = await conn.execute(text(
                "SELECT filename FROM _migrations ORDER BY filename"
            ))
            applied_set = {row[0] for row in result.fetchall()}

            # Find and sort migration files
            sql_files = sorted(mdir.glob("*.sql"))

            for sql_file in sql_files:
                fname = sql_file.name
                if fname in applied_set:
                    log.debug("skip already applied: %s", fname)
                    continue

                log.info("applying migration: %s", fname)
                sql_content = sql_file.read_text(encoding="utf-8")

                await conn.execute(text(sql_content))
                await conn.execute(
                    text("INSERT INTO _migrations (filename) VALUES (:f)"),
                    {"f": fname},
                )
                applied.append(fname)
                log.info("applied migration: %s", fname)

    finally:
        if engine is None:
            await _engine.dispose()

    return applied


def _create_engine(db_url: Optional[str] = None) -> AsyncEngine:
    url = db_url or os.environ.get("SYLION_DB_URL", "")
    if not url:
        raise ValueError("PostgreSQL URL required: set SYLION_DB_URL or pass db_url")
    return create_async_engine(url, echo=False, pool_pre_ping=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def _main():
        applied = await run_migrations()
        if applied:
            print(f"Applied {len(applied)} migrations:")
            for f in applied:
                print(f"  - {f}")
        else:
            print("All migrations already applied.")

    asyncio.run(_main())
