"""
SYLION -- PostgreSQL Migration CLI

Runs the PostgreSQL schema migration for SYLION AEIS.

Usage:
    python scripts/migrate_postgres.py --url postgresql+asyncpg://user:pass@localhost/sylion
    python scripts/migrate_postgres.py  # uses SYLION_DATABASE_URL env var
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), "..", "src", "sylion-pipeline")))

from sylion.db.pg_migration import create_pg_engine, run_pg_migration


async def main():
    parser = argparse.ArgumentParser(description="Run SYLION PostgreSQL schema migration")
    parser.add_argument("--url", default=os.environ.get("SYLION_DATABASE_URL"), help="PostgreSQL connection URL")
    args = parser.parse_args()

    if not args.url:
        print("Error: No database URL provided. Set SYLION_DATABASE_URL or use --url", file=sys.stderr)
        sys.exit(1)

    engine = create_pg_engine(args.url)
    try:
        await run_pg_migration(engine)
        print("PostgreSQL migration completed successfully.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
