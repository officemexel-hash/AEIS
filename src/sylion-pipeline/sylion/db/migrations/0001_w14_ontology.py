"""W14 Testing Ontology — DB migration #0001.

Creates 25 per-object tables + ``w14_testing_relations`` + ``w14_testing_history``.

The runtime store (``sylion.aeis.testing.ontology.store.OntologyStore``)
also calls ``CREATE TABLE IF NOT EXISTS`` to keep tests self-contained, but
this migration is the canonical schema definition. Operators run it as part
of the SYLION cold-boot sequence to provision the production database.

Idempotent: ``up`` can be replayed; ``down`` drops the tables in reverse
order. A migration log row is written to ``sylion_migrations`` so re-runs
are auditable.
"""
from __future__ import annotations

import logging
import sqlite3
import time

log = logging.getLogger("sylion.db.migrations.0001_w14_ontology")

MIGRATION_ID = "0001_w14_ontology"

# Per-object tables. Ordered for deterministic deploy logs.
OBJECT_TABLES: tuple[str, ...] = (
    "w14_requirements",
    "w14_test_charters",
    "w14_test_plans",
    "w14_test_suites",
    "w14_test_cases",
    "w14_evaluation_suites",
    "w14_test_runs",
    "w14_regression_runs",
    "w14_findings",
    "w14_patch_proposals",
    "w14_repair_attempts",
    "w14_loop_reports",
    "w14_guardian_alerts",
    "w14_simulation_contracts",
    "w14_simulation_branches",
    "w14_simulation_evidence",
    "w14_human_personas",
    "w14_human_scenarios",
    "w14_human_error_injections",
    "w14_human_decision_traces",
    "w14_human_near_misses",
    "w14_branches",
    "w14_release_candidates",
    "w14_release_decisions",
    "w14_release_readiness_reports",
)


def _ensure_migration_log(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sylion_migrations (
            migration_id TEXT PRIMARY KEY,
            applied_at   REAL NOT NULL,
            direction    TEXT NOT NULL DEFAULT 'up'
        )
    """)


def _record(conn: sqlite3.Connection, direction: str) -> None:
    _ensure_migration_log(conn)
    conn.execute(
        "INSERT OR REPLACE INTO sylion_migrations "
        "(migration_id, applied_at, direction) VALUES (?,?,?)",
        (MIGRATION_ID, time.time(), direction),
    )


def up(conn: sqlite3.Connection) -> dict:
    """Create all W14 ontology tables. Returns deployment metadata."""
    conn.execute("PRAGMA foreign_keys=ON")

    for table in OBJECT_TABLES:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                obj_id      TEXT PRIMARY KEY,
                payload     TEXT NOT NULL,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL,
                deleted_at  REAL
            )
        """)
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_created "
            f"ON {table}(created_at)"
        )
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_deleted "
            f"ON {table}(deleted_at)"
        )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS w14_testing_relations (
            relation_id  TEXT PRIMARY KEY,
            src_id       TEXT NOT NULL,
            dst_id       TEXT NOT NULL,
            relation     TEXT NOT NULL,
            created_at   REAL NOT NULL
        )
    """)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_rel_triple "
        "ON w14_testing_relations(src_id, dst_id, relation)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rel_src "
        "ON w14_testing_relations(src_id, relation)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rel_dst "
        "ON w14_testing_relations(dst_id, relation)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS w14_testing_history (
            history_id  TEXT PRIMARY KEY,
            obj_id      TEXT NOT NULL,
            obj_kind    TEXT NOT NULL,
            verb        TEXT NOT NULL,
            payload     TEXT NOT NULL,
            actor       TEXT NOT NULL DEFAULT '',
            timestamp   REAL NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_hist_obj "
        "ON w14_testing_history(obj_id, timestamp)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_hist_kind "
        "ON w14_testing_history(obj_kind, timestamp)"
    )

    _record(conn, "up")
    conn.commit()

    log.info("[%s] up: %d object tables + relations + history",
             MIGRATION_ID, len(OBJECT_TABLES))
    return {
        "migration_id": MIGRATION_ID,
        "direction": "up",
        "tables_created": len(OBJECT_TABLES) + 2,
        "ts": time.time(),
    }


def down(conn: sqlite3.Connection) -> dict:
    """Drop all W14 ontology tables (reverse of up)."""
    conn.execute("DROP INDEX IF EXISTS idx_hist_kind")
    conn.execute("DROP INDEX IF EXISTS idx_hist_obj")
    conn.execute("DROP TABLE IF EXISTS w14_testing_history")

    conn.execute("DROP INDEX IF EXISTS idx_rel_dst")
    conn.execute("DROP INDEX IF EXISTS idx_rel_src")
    conn.execute("DROP INDEX IF EXISTS uq_rel_triple")
    conn.execute("DROP TABLE IF EXISTS w14_testing_relations")

    for table in reversed(OBJECT_TABLES):
        conn.execute(f"DROP INDEX IF EXISTS idx_{table}_deleted")
        conn.execute(f"DROP INDEX IF EXISTS idx_{table}_created")
        conn.execute(f"DROP TABLE IF EXISTS {table}")

    _record(conn, "down")
    conn.commit()

    log.info("[%s] down: %d object tables dropped", MIGRATION_ID, len(OBJECT_TABLES))
    return {
        "migration_id": MIGRATION_ID,
        "direction": "down",
        "tables_dropped": len(OBJECT_TABLES) + 2,
        "ts": time.time(),
    }


if __name__ == "__main__":  # pragma: no cover
    import argparse
    parser = argparse.ArgumentParser(description="W14 ontology migration #0001")
    parser.add_argument("--db-path", default="sylion_aeis.db")
    parser.add_argument("--direction", choices=("up", "down"), default="up")
    args = parser.parse_args()
    conn = sqlite3.connect(args.db_path)
    result = up(conn) if args.direction == "up" else down(conn)
    conn.close()
    print(result)
