"""AEIS Advisor — Environment inventory."""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from sylion.aeis.advisor import _db as shared_db
from sylion.aeis.advisor.scaling._db import ensure_tables
from sylion.aeis.advisor.scaling._models import Env


def register_env(env_data: dict[str, Any]) -> Env:
    """Register a new environment."""
    ensure_tables()
    env = Env(
        env_id=env_data.get("env_id", ""),
        operator_id=env_data.get("operator_id", ""),
        name=env_data.get("name", ""),
        kind=env_data.get("kind", ""),
        capacity_tokens_per_day=env_data.get("capacity_tokens_per_day", 0),
    )
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO scaling_envs
            (env_id, operator_id, name, kind, capacity_tokens_per_day, registered_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (env_id) DO UPDATE SET
              operator_id = EXCLUDED.operator_id,
              name = EXCLUDED.name,
              kind = EXCLUDED.kind,
              capacity_tokens_per_day = EXCLUDED.capacity_tokens_per_day,
              registered_at = EXCLUDED.registered_at""",
            (env.env_id, env.operator_id, env.name, env.kind, env.capacity_tokens_per_day, env.registered_at),
        )
    return env


def get_env_inventory(operator_id: str) -> list[Env]:
    """List environments for an operator."""
    ensure_tables()
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM scaling_envs WHERE operator_id = %s ORDER BY registered_at",
            (operator_id,),
        )
        rows = cur.fetchall()
    return [_row_to_env(r) for r in rows]


def _row_to_env(row: dict[str, Any]) -> Env:
    return Env(
        env_id=row["env_id"],
        operator_id=row["operator_id"],
        name=row["name"],
        kind=row["kind"],
        capacity_tokens_per_day=row["capacity_tokens_per_day"],
        registered_at=row["registered_at"],
    )
