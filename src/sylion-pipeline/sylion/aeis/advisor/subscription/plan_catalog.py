"""AEIS Advisor — Subscription plan catalog."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from psycopg.rows import dict_row

from sylion.aeis.advisor import _db as shared_db
from sylion.aeis.advisor.subscription._db import ensure_tables
from sylion.aeis.advisor.subscription._models import Plan

log = logging.getLogger("sylion.aeis.advisor.subscription.plan_catalog")

DEFAULT_PLANS = [
    {
        "plan_id": "anthropic_pro",
        "provider_id": "anthropic",
        "monthly_price_usd": 200,
        "included_tokens": 5_000_000,
        "rate_limits": {"rpm": 4000, "tpm": 400_000},
        "is_assumption": True,
        "source_url": "https://www.anthropic.com/pricing",
    },
    {
        "plan_id": "openai_team",
        "provider_id": "openai",
        "monthly_price_usd": 500,
        "included_tokens": 10_000_000,
        "rate_limits": {"rpm": 10_000, "tpm": 2_000_000},
        "is_assumption": True,
        "source_url": "https://openai.com/pricing",
    },
    {
        "plan_id": "google_paid",
        "provider_id": "google",
        "monthly_price_usd": 100,
        "included_tokens": 5_000_000,
        "rate_limits": {"rpm": 3600, "tpm": 2_000_000},
        "is_assumption": True,
        "source_url": "https://ai.google.dev/pricing",
    },
]


def seed_defaults() -> None:
    """Seed default plans if table is empty."""
    ensure_tables()
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM subscription_plans")
        row = cur.fetchone()
        if row and row["cnt"] > 0:
            return
    for plan in DEFAULT_PLANS:
        with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO subscription_plans
                (plan_id, provider_id, monthly_price_usd, included_tokens, rate_limits, is_assumption, source_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (plan_id) DO UPDATE SET
                  provider_id = EXCLUDED.provider_id,
                  monthly_price_usd = EXCLUDED.monthly_price_usd,
                  included_tokens = EXCLUDED.included_tokens,
                  rate_limits = EXCLUDED.rate_limits,
                  is_assumption = EXCLUDED.is_assumption,
                  source_url = EXCLUDED.source_url""",
                (
                    plan["plan_id"],
                    plan["provider_id"],
                    plan["monthly_price_usd"],
                    plan["included_tokens"],
                    json.dumps(plan["rate_limits"]),
                    plan["is_assumption"],
                    plan["source_url"],
                ),
            )
    log.info("seeded %d default plans", len(DEFAULT_PLANS))


def list_plans(provider_id: str | None = None) -> list[Plan]:
    """List available plans."""
    ensure_tables()
    seed_defaults()
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        if provider_id:
            cur.execute(
                "SELECT * FROM subscription_plans WHERE provider_id = %s ORDER BY monthly_price_usd",
                (provider_id,),
            )
        else:
            cur.execute("SELECT * FROM subscription_plans ORDER BY monthly_price_usd")
        rows = cur.fetchall()
    return [_row_to_plan(r) for r in rows]


def get_plan(plan_id: str) -> Plan | None:
    """Get a plan by ID."""
    ensure_tables()
    seed_defaults()
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM subscription_plans WHERE plan_id = %s", (plan_id,))
        row = cur.fetchone()
    return _row_to_plan(row) if row else None


def register_custom_plan(plan_data: dict[str, Any]) -> None:
    """Register a custom plan."""
    ensure_tables()
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO subscription_custom_plans
            (plan_id, operator_id, plan_data, created_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (plan_id) DO UPDATE SET
              operator_id = EXCLUDED.operator_id,
              plan_data = EXCLUDED.plan_data,
              created_at = EXCLUDED.created_at""",
            (
                plan_data["plan_id"],
                plan_data.get("operator_id", ""),
                json.dumps(plan_data),
                time.time(),
            ),
        )


def _row_to_plan(row: dict[str, Any]) -> Plan:
    return Plan(
        plan_id=row["plan_id"],
        provider_id=row["provider_id"],
        monthly_price_usd=row["monthly_price_usd"],
        included_tokens=row["included_tokens"],
        rate_limits=json.loads(row.get("rate_limits", "{}")),
        is_assumption=bool(row.get("is_assumption", 0)),
        source_url=row.get("source_url", ""),
    )
