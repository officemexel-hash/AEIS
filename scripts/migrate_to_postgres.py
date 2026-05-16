"""
SYLION -- SQLite to Postgres migration script for Worker + Integration modules.

Usage:
    python scripts/migrate_to_postgres.py --sqlite-path sylion_aeis.db --pg-url postgresql://user:pass@localhost/sylion

Requires:
    pip install psycopg[binary]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "sylion-pipeline"))

from sylion.db.pg_migration_worker import get_all_ddl, sync_sqlite_to_postgres


def main():
    parser = argparse.ArgumentParser(description="Migrate Worker + Integration data from SQLite to Postgres")
    parser.add_argument("--sqlite-path", required=True, help="Path to SQLite DB")
    parser.add_argument("--pg-url", required=True, help="PostgreSQL connection URL")
    parser.add_argument("--schema-only", action="store_true", help="Only create schema, do not sync data")
    args = parser.parse_args()

    try:
        import psycopg
    except ImportError:
        print("ERROR: psycopg is required. Install: pip install psycopg[binary]")
        sys.exit(1)

    conn = psycopg.connect(args.pg_url)
    with conn.cursor() as cur:
        cur.execute(get_all_ddl())
    conn.commit()
    conn.close()
    print("Postgres schema created.")

    if not args.schema_only:
        result = sync_sqlite_to_postgres(args.sqlite_path, args.pg_url)
        for table, count in result["synced"].items():
            print(f"  Synced {count} rows into {table}")
        print("Migration complete.")


if __name__ == "__main__":
    main()
