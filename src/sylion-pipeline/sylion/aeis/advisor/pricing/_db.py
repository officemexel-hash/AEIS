"""Database helpers for the advisor pricing module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sylion.aeis.advisor._db import get_pool


def upsert_provider(
    provider_id: str,
    display_name: str,
    is_local: bool,
    metadata_url: str | None,
) -> None:
    """Insert or update a provider row."""
    sql = """
        INSERT INTO advisor_pricing.providers
          (provider_id, display_name, is_local, is_active, metadata_url)
        VALUES (%s, %s, %s, true, %s)
        ON CONFLICT (provider_id) DO UPDATE SET
          display_name = EXCLUDED.display_name,
          is_local = EXCLUDED.is_local,
          metadata_url = EXCLUDED.metadata_url,
          updated_at = NOW()
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (provider_id, display_name, is_local, metadata_url))


def get_provider(provider_id: str) -> dict[str, Any] | None:
    """Return provider metadata."""
    sql = """
        SELECT provider_id, display_name, is_local, is_active, metadata_url
        FROM advisor_pricing.providers
        WHERE provider_id = %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (provider_id,))
        row = cur.fetchone()
        if not row:
            return None
        columns = [item[0] for item in cur.description]
        return dict(zip(columns, row))


def list_providers(active_only: bool = True) -> list[dict[str, Any]]:
    """List providers."""
    where = "WHERE is_active = true" if active_only else ""
    sql = f"""
        SELECT provider_id, display_name, is_local, is_active, metadata_url
        FROM advisor_pricing.providers
        {where}
        ORDER BY provider_id
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        columns = [item[0] for item in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def upsert_model(
    model_id: str,
    provider_id: str,
    display_name: str,
    context_window: int | None,
    is_local: bool,
    capabilities: list[str],
    is_default_judge: bool,
    is_default_local: bool,
    is_deprecated: bool = False,
) -> None:
    """Insert or update a model row."""
    sql = """
        INSERT INTO advisor_pricing.provider_models
          (model_id, provider_id, display_name, context_window, is_local,
           capabilities, is_default_judge, is_default_local, is_deprecated)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
        ON CONFLICT (model_id) DO UPDATE SET
          provider_id = EXCLUDED.provider_id,
          display_name = EXCLUDED.display_name,
          context_window = EXCLUDED.context_window,
          is_local = EXCLUDED.is_local,
          capabilities = EXCLUDED.capabilities,
          is_default_judge = EXCLUDED.is_default_judge,
          is_default_local = EXCLUDED.is_default_local,
          is_deprecated = EXCLUDED.is_deprecated
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                model_id,
                provider_id,
                display_name,
                context_window,
                is_local,
                json.dumps(capabilities),
                is_default_judge,
                is_default_local,
                is_deprecated,
            ),
        )


def get_model(model_id: str) -> dict[str, Any] | None:
    """Return a single model row."""
    sql = """
        SELECT model_id, provider_id, display_name, context_window, is_local,
               capabilities, is_default_judge, is_default_local, is_deprecated
        FROM advisor_pricing.provider_models
        WHERE model_id = %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (model_id,))
        row = cur.fetchone()
        if not row:
            return None
        columns = [item[0] for item in cur.description]
        return _decode_model_dict(dict(zip(columns, row)))


def list_models(
    provider_id: str | None = None,
    include_deprecated: bool = False,
) -> list[dict[str, Any]]:
    """List provider models."""
    clauses: list[str] = []
    params: list[Any] = []
    if provider_id:
        clauses.append("provider_id = %s")
        params.append(provider_id)
    if not include_deprecated:
        clauses.append("is_deprecated = false")
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT model_id, provider_id, display_name, context_window, is_local,
               capabilities, is_default_judge, is_default_local, is_deprecated
        FROM advisor_pricing.provider_models
        {where_sql}
        ORDER BY model_id
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        columns = [item[0] for item in cur.description]
        return [_decode_model_dict(dict(zip(columns, row))) for row in cur.fetchall()]


def insert_pricing_table(
    model_id: str,
    input_per_million: Decimal | None,
    output_per_million: Decimal | None,
    cache_per_million: Decimal | None,
    source: str,
    source_url: str | None,
    is_assumption: bool,
    assumption_note: str | None,
) -> str:
    """Insert a new active pricing row for a model."""
    now = datetime.now(timezone.utc)
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE advisor_pricing.pricing_tables
            SET effective_until = %s
            WHERE model_id = %s AND effective_until IS NULL
            """,
            (now, model_id),
        )
        cur.execute(
            """
            INSERT INTO advisor_pricing.pricing_tables
              (model_id, input_tokens_usd_per_million, output_tokens_usd_per_million,
               cache_hit_tokens_usd_per_million, source, source_url, is_assumption,
               assumption_note, effective_from)
            VALUES (%s, %s, %s, %s, %s::advisor_engine.impact_confidence, %s, %s, %s, %s)
            RETURNING pricing_id
            """,
            (
                model_id,
                input_per_million,
                output_per_million,
                cache_per_million,
                source,
                source_url,
                is_assumption,
                assumption_note,
                now,
            ),
        )
        row = cur.fetchone()
        return str(row[0])


def get_active_pricing(model_id: str) -> dict[str, Any] | None:
    """Return active pricing for a model."""
    sql = """
        SELECT pricing_id, model_id, input_tokens_usd_per_million,
               output_tokens_usd_per_million, cache_hit_tokens_usd_per_million,
               source, source_url, is_assumption, assumption_note,
               effective_from, effective_until
        FROM advisor_pricing.pricing_tables
        WHERE model_id = %s AND effective_until IS NULL
        ORDER BY effective_from DESC
        LIMIT 1
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (model_id,))
        row = cur.fetchone()
        if not row:
            return None
        columns = [item[0] for item in cur.description]
        return dict(zip(columns, row))


def insert_pricing_history(
    model_id: str,
    source: str,
    raw_response: dict[str, Any] | None,
    resolved_pricing_id: str | None,
    is_assumption: bool,
    error: str | None,
) -> str:
    """Insert a pricing refresh history row."""
    sql = """
        INSERT INTO advisor_pricing.pricing_history
          (model_id, source, raw_response, resolved_pricing_id, is_assumption, error_message)
        VALUES (%s, %s::advisor_engine.impact_confidence, %s::jsonb, %s, %s, %s)
        RETURNING history_id
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                model_id,
                source,
                json.dumps(raw_response) if raw_response is not None else None,
                resolved_pricing_id,
                is_assumption,
                error,
            ),
        )
        row = cur.fetchone()
        return str(row[0])


def get_pricing_history(
    model_id: str,
    since: datetime | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return pricing history for a model."""
    clauses = ["model_id = %s"]
    params: list[Any] = [model_id]
    if since is not None:
        clauses.append("fetched_at >= %s")
        params.append(since)
    params.append(limit)
    sql = f"""
        SELECT history_id, model_id, fetched_at, source, is_assumption, error_message
        FROM advisor_pricing.pricing_history
        WHERE {' AND '.join(clauses)}
        ORDER BY fetched_at DESC
        LIMIT %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        columns = [item[0] for item in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def _decode_model_dict(model: dict[str, Any]) -> dict[str, Any]:
    capabilities = model.get("capabilities")
    if isinstance(capabilities, str):
        model["capabilities"] = json.loads(capabilities)
    elif capabilities is None:
        model["capabilities"] = []
    return model
