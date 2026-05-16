from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def run_migration(db_path: str | Path) -> dict[str, Any]:
    path = Path(db_path)
    with closing(sqlite3.connect(path)) as conn:
        already_applied = _has_table(conn, "health_history")
        if not already_applied:
            conn.execute(
                """
                CREATE TABLE health_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_at REAL NOT NULL,
                    overall TEXT NOT NULL,
                    elapsed_ms INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX idx_hh_run_at ON health_history(run_at)")
            conn.commit()
    return {"success": True, "applied": not already_applied}


def verify_migration(db_path: str | Path) -> dict[str, Any]:
    with closing(sqlite3.connect(Path(db_path))) as conn:
        table = _has_table(conn, "health_history")
        index = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_hh_run_at'"
        ).fetchone() is not None
    return {"ok": table and index, "checks": {"health_history_table": table, "idx_hh_run_at": index}}
