"""Pure SQL helpers for the advisor preferences module."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from typing import Any

from sylion.aeis.advisor._db import get_pool


_sqlite_conn: sqlite3.Connection | None = None
_sqlite_lock = threading.RLock()


_DOMAIN_SEED: tuple[tuple[str, str, str], ...] = (
    ("funding", "Funding", "Grants, subsidies, public/private financing"),
    ("software", "Software", "Software development projects"),
    ("audit", "Audit", "Security/compliance/code audits"),
    ("mobile", "Mobile", "Mobile applications"),
    ("infrastructure", "Infrastructure", "DevOps, cloud, on-prem infra"),
    ("data_analytics", "Data Analytics", "Data pipelines, BI, ML"),
    ("security", "Security", "Security tooling, threat modeling"),
    ("governance", "Governance", "Policies, compliance frameworks"),
    ("research", "Research", "R&D, exploratory work"),
    ("marketing", "Marketing", "Marketing campaigns, content, growth"),
    ("legal", "Legal", "Contracts, IP, regulatory"),
    ("product_management", "Product Management", "Roadmaps, PRDs, prioritization"),
    ("finance", "Finance", "Budgets, accounting, treasury"),
    ("operations", "Operations", "Ops, support, internal tooling"),
)


_TYPE_SEED: tuple[tuple[str, str, str], ...] = (
    ("research", "Research", "Exploratory, lower bar for production-readiness"),
    ("production", "Production", "Customer-facing, high reliability bar"),
    ("experiment", "Experiment", "A/B tests, throwaway prototypes"),
    ("poc", "PoC", "Proof of concept, limited scope"),
    ("migration", "Migration", "Data/system migration projects"),
    ("refactor", "Refactor", "Internal code improvement, no new features"),
    ("integration", "Integration", "3rd party integrations"),
    ("hotfix", "Hotfix", "Urgent production fixes"),
)


_PREFERENCE_KEY_SEED: tuple[tuple[str, str, str, dict[str, Any], Any, bool], ...] = (
    (
        "autonomy_level",
        "Autonomy level",
        "Manual / suggest / auto",
        {"type": "string", "enum": ["manual", "suggest", "auto"]},
        "suggest",
        True,
    ),
    (
        "cost_sensitivity",
        "Cost sensitivity",
        "How aggressively to optimize for cost",
        {"type": "string", "enum": ["low", "medium", "high"]},
        "medium",
        False,
    ),
    (
        "preferred_providers",
        "Preferred model providers",
        "Ordered list of preferred provider IDs",
        {"type": "array", "items": {"type": "string"}},
        [],
        False,
    ),
    (
        "runtime_strategy",
        "Runtime strategy",
        "local-only / local+VPS / hybrid / VPS-only",
        {"type": "string", "enum": ["local_only", "local_plus_vps", "hybrid", "vps_only"]},
        "local_only",
        True,
    ),
    (
        "approval_timeout_behavior",
        "Approval timeout behavior",
        "Auto-approve / escalate / hold",
        {"type": "string", "enum": ["auto_approve", "escalate", "hold"]},
        "hold",
        True,
    ),
    (
        "council_size",
        "Council size",
        "Default Council size for D2+ decisions",
        {"type": "integer", "minimum": 1, "maximum": 11},
        5,
        False,
    ),
    (
        "budget_thresholds",
        "Budget thresholds",
        "Per-project default cost ceilings",
        {"type": "object"},
        {},
        False,
    ),
    (
        "quality_speed_cost",
        "Quality / Speed / Cost trade-off",
        "Slider weights (must sum to 1.0)",
        {"type": "object"},
        {"quality": 0.4, "speed": 0.3, "cost": 0.3},
        False,
    ),
    (
        "trusted_providers",
        "Trusted providers",
        "Provider IDs operator explicitly trusts",
        {"type": "array", "items": {"type": "string"}},
        [],
        True,
    ),
    (
        "blocked_providers",
        "Blocked providers",
        "Provider IDs operator explicitly blocks",
        {"type": "array", "items": {"type": "string"}},
        [],
        True,
    ),
    (
        "llm_judge_routing_override",
        "LLM judge routing override",
        "Per-risk-level model overrides",
        {"type": "object"},
        {},
        False,
    ),
    (
        "llm_judge_routing",
        "LLM judge routing",
        "Per-risk-level model routing selected in the wizard",
        {"type": "object"},
        {},
        False,
    ),
    (
        "cost_ceilings",
        "Cost ceilings per risk",
        "Per-risk-level USD ceiling for LLM calls",
        {"type": "object"},
        {"low": 0.10, "medium": 0.40, "high": 1.60, "critical": 6.00},
        False,
    ),
    (
        "funding_advisor_enabled",
        "Funding Advisor enabled",
        "Master toggle for funding module",
        {"type": "boolean"},
        False,
        True,
    ),
    (
        "funding_countries",
        "Funding countries",
        "Hierarchical country/region filter",
        {"type": "array"},
        [],
        True,
    ),
    (
        "funding_pl_regions",
        "Funding Polish regions",
        "Polish regional funding filter",
        {"type": "array"},
        [],
        True,
    ),
    (
        "funding_model_profile",
        "Funding model profile",
        "Research provider and Polish specialist model policy",
        {"type": "object"},
        {},
        True,
    ),
    (
        "funding_token_budget_monthly",
        "Funding monthly token budget",
        "Separate budget for funding research",
        {"type": "integer", "minimum": 0},
        100000,
        False,
    ),
    (
        "meta_recommendations_enabled",
        "Meta-recommendations enabled",
        "Allow advisor to recommend changes to advisor itself",
        {"type": "boolean"},
        False,
        True,
    ),
    (
        "default_project_domain",
        "Default project domain",
        "Default domain selected by the operator during onboarding",
        {"type": "string"},
        "software",
        False,
    ),
    (
        "operator_name",
        "Operator name",
        "Human-readable operator label from onboarding",
        {"type": "string"},
        "",
        False,
    ),
    (
        "operator_role",
        "Operator role",
        "Operator role used by governance, HumanGate and audit UX",
        {"type": "string"},
        "",
        False,
    ),
    (
        "operator_email",
        "Operator email",
        "Optional operator contact email used for local audit metadata",
        {"type": "string"},
        "",
        False,
    ),
    (
        "operator_language",
        "Operator language",
        "Primary UI and deliberation language selected by the operator",
        {"type": "string"},
        "pl-PL",
        False,
    ),
    (
        "operator_timezone",
        "Operator timezone",
        "Timezone used for audit timestamps and HumanGate deadlines",
        {"type": "string"},
        "Europe/Warsaw",
        False,
    ),
    (
        "operator_profile",
        "Operator profile",
        "Composite operator profile saved from the profile settings page",
        {"type": "object"},
        {},
        False,
    ),
    (
        "profile_notes",
        "Operator profile notes",
        "Free-form operator note injected into advisor and governance context",
        {"type": "string"},
        "",
        False,
    ),
    (
        "goals",
        "Operator goals",
        "Onboarding goal selections",
        {"type": "array"},
        [],
        False,
    ),
    (
        "usage_cadence",
        "Usage cadence",
        "Expected operator usage cadence",
        {"type": "string"},
        "",
        False,
    ),
    (
        "onboarding_state",
        "Onboarding state",
        "Raw wizard state persisted for first-run recovery",
        {"type": "object"},
        {},
        False,
    ),
    (
        "advisor_onboarded",
        "Advisor onboarded",
        "First-run completion marker",
        {"type": "boolean"},
        False,
        False,
    ),
)


def _use_sqlite_store() -> bool:
    """Use audit/local SQLite when PG is intentionally disabled.

    Preferences are part of the live advisor control surface. In a clean
    local distribution run the API advertises ``SYLION_DB_MODE=sqlite`` and
    does not provide a PostgreSQL DSN, so using the shared advisor PG pool here
    turns a real UI action into a 500. Match advisor.engine behavior: use the
    module SQLite store in audit mode and in normal local SQLite mode, unless a
    developer explicitly forces PostgreSQL.
    """
    if str(os.environ.get("SYLION_ADVISOR_FORCE_PG", "")).lower() in {"1", "true", "yes"}:
        return False
    try:
        from sylion.aeis_v2.audit_profile import is_audit_mode

        if is_audit_mode():
            return True
    except Exception:
        pass
    db_mode = str(os.environ.get("SYLION_DB_MODE", "sqlite")).strip().lower()
    has_pg_dsn = bool(os.environ.get("SYLION_DB_URL") or os.environ.get("SYLION_PG_DSN"))
    return db_mode != "postgres" or not has_pg_dsn


def _sqlite_db_path() -> str:
    from sylion.aeis_v2.audit_profile import resolve_db_path

    return str(resolve_db_path("advisor_preferences.db"))


def _get_sqlite_conn() -> sqlite3.Connection:
    global _sqlite_conn
    if _sqlite_conn is None:
        with _sqlite_lock:
            if _sqlite_conn is None:
                conn = sqlite3.connect(_sqlite_db_path(), check_same_thread=False, timeout=30.0)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                _sqlite_conn = conn
                _init_sqlite_schema(conn)
    return _sqlite_conn


def _init_sqlite_schema(conn: sqlite3.Connection) -> None:
    with _sqlite_lock:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS advisor_preferences_project_domain_catalog (
              domain_id TEXT PRIMARY KEY,
              display_name TEXT NOT NULL,
              is_system INTEGER NOT NULL DEFAULT 0,
              is_immutable INTEGER NOT NULL DEFAULT 0,
              description TEXT,
              created_at REAL NOT NULL,
              created_by TEXT NOT NULL DEFAULT 'system'
            );

            CREATE TABLE IF NOT EXISTS advisor_preferences_project_type_catalog (
              type_id TEXT PRIMARY KEY,
              display_name TEXT NOT NULL,
              is_system INTEGER NOT NULL DEFAULT 0,
              is_immutable INTEGER NOT NULL DEFAULT 0,
              description TEXT,
              created_at REAL NOT NULL,
              created_by TEXT NOT NULL DEFAULT 'system'
            );

            CREATE TABLE IF NOT EXISTS advisor_preferences_preference_key_catalog (
              preference_key TEXT PRIMARY KEY,
              display_name TEXT NOT NULL,
              description TEXT,
              value_schema TEXT NOT NULL,
              default_value TEXT,
              is_hard_change INTEGER NOT NULL DEFAULT 0,
              created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS advisor_preferences_preferences (
              user_id TEXT NOT NULL,
              project_type TEXT,
              project_domain TEXT,
              preference_key TEXT NOT NULL,
              preference_value TEXT NOT NULL,
              set_by TEXT NOT NULL,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_adv_pref_unique
              ON advisor_preferences_preferences(
                user_id,
                COALESCE(project_type, ''),
                COALESCE(project_domain, ''),
                preference_key
              );
            CREATE INDEX IF NOT EXISTS idx_adv_pref_user
              ON advisor_preferences_preferences(user_id);
            CREATE INDEX IF NOT EXISTS idx_adv_pref_lookup
              ON advisor_preferences_preferences(user_id, project_type, project_domain);
            CREATE INDEX IF NOT EXISTS idx_adv_pref_key
              ON advisor_preferences_preferences(preference_key);

            CREATE TABLE IF NOT EXISTS advisor_preferences_preferences_audit (
              audit_id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              project_type TEXT,
              project_domain TEXT,
              preference_key TEXT NOT NULL,
              old_value TEXT,
              new_value TEXT,
              change_type TEXT NOT NULL,
              changed_by TEXT NOT NULL,
              changed_at REAL NOT NULL,
              reason TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_adv_pref_audit_user
              ON advisor_preferences_preferences_audit(user_id, changed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_adv_pref_audit_key
              ON advisor_preferences_preferences_audit(preference_key, changed_at DESC);
            """
        )
        now = time.time()
        conn.executemany(
            """
            INSERT OR IGNORE INTO advisor_preferences_project_domain_catalog
              (domain_id, display_name, is_system, is_immutable, description, created_at, created_by)
            VALUES (?, ?, 1, 1, ?, ?, 'system')
            """,
            [(domain_id, display_name, description, now) for domain_id, display_name, description in _DOMAIN_SEED],
        )
        conn.executemany(
            """
            INSERT OR IGNORE INTO advisor_preferences_project_type_catalog
              (type_id, display_name, is_system, is_immutable, description, created_at, created_by)
            VALUES (?, ?, 1, 1, ?, ?, 'system')
            """,
            [(type_id, display_name, description, now) for type_id, display_name, description in _TYPE_SEED],
        )
        conn.executemany(
            """
            INSERT OR IGNORE INTO advisor_preferences_preference_key_catalog
              (preference_key, display_name, description, value_schema, default_value,
               is_hard_change, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    key,
                    display_name,
                    description,
                    json.dumps(schema, sort_keys=True),
                    json.dumps(default_value, sort_keys=True),
                    int(is_hard_change),
                    now,
                )
                for key, display_name, description, schema, default_value, is_hard_change
                in _PREFERENCE_KEY_SEED
            ],
        )
        conn.commit()


def _sqlite_row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = {key: row[key] for key in row.keys()}
    for key in ("preference_value", "old_value", "new_value", "default_value", "metadata", "value_schema"):
        if key in data:
            data[key] = _maybe_json_load(data[key])
    return data


def _sqlite_rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [_sqlite_row_to_dict(row) or {} for row in rows]


def _sqlite_nullsafe_where(prefix: str = "") -> str:
    p = f"{prefix}." if prefix else ""
    return (
        f"{p}user_id = ? "
        f"AND (({p}project_type IS NULL AND ? IS NULL) OR {p}project_type = ?) "
        f"AND (({p}project_domain IS NULL AND ? IS NULL) OR {p}project_domain = ?) "
        f"AND {p}preference_key = ?"
    )


def _row_dict(cur: Any, row: Any) -> dict[str, Any]:
    data = dict(zip([item[0] for item in cur.description], row))
    for key in ("preference_value", "old_value", "new_value", "default_value", "metadata"):
        if key in data:
            data[key] = _maybe_json_load(data[key])
    return data


def _maybe_json_load(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    if text[0] not in ('[', '{', '"') and text not in {"true", "false", "null"}:
        return value
    try:
        return json.loads(text)
    except Exception:
        return value


def get_preference_row(
    user_id: str,
    project_type: str | None,
    project_domain: str | None,
    preference_key: str,
) -> dict[str, Any] | None:
    """Return one explicit preference row."""
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            row = conn.execute(
                f"""
                SELECT user_id, project_type, project_domain, preference_key,
                       preference_value, set_by, created_at, updated_at
                FROM advisor_preferences_preferences
                WHERE {_sqlite_nullsafe_where()}
                """,
                (
                    user_id,
                    project_type,
                    project_type,
                    project_domain,
                    project_domain,
                    preference_key,
                ),
            ).fetchone()
        return _sqlite_row_to_dict(row)

    sql = """
        SELECT CAST(user_id AS TEXT) AS user_id, project_type, project_domain, preference_key,
               preference_value, set_by, created_at, updated_at
        FROM advisor_preferences.preferences
        WHERE CAST(user_id AS TEXT) = %s
          AND project_type IS NOT DISTINCT FROM %s
          AND project_domain IS NOT DISTINCT FROM %s
          AND preference_key = %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (user_id, project_type, project_domain, preference_key))
        row = cur.fetchone()
        return _row_dict(cur, row) if row else None


def list_preferences(
    user_id: str,
    *,
    project_type: str | None = None,
    project_domain: str | None = None,
    preference_key: str | None = None,
) -> list[dict[str, Any]]:
    """List explicit preference rows for a user."""
    if _use_sqlite_store():
        clauses = ["user_id = ?"]
        params: list[Any] = [user_id]
        if project_type not in (None, ""):
            clauses.append("project_type = ?")
            params.append(project_type)
        if project_domain not in (None, ""):
            clauses.append("project_domain = ?")
            params.append(project_domain)
        if preference_key not in (None, ""):
            clauses.append("preference_key = ?")
            params.append(preference_key)
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            rows = conn.execute(
                f"""
                SELECT user_id, project_type, project_domain, preference_key,
                       preference_value, set_by, created_at, updated_at
                FROM advisor_preferences_preferences
                WHERE {' AND '.join(clauses)}
                ORDER BY preference_key, project_type IS NULL, project_domain IS NULL
                """,
                tuple(params),
            ).fetchall()
        return _sqlite_rows_to_dicts(rows)

    clauses = ["CAST(user_id AS TEXT) = %s"]
    params: list[Any] = [user_id]
    if project_type not in (None, ""):
        clauses.append("project_type = %s")
        params.append(project_type)
    if project_domain not in (None, ""):
        clauses.append("project_domain = %s")
        params.append(project_domain)
    if preference_key not in (None, ""):
        clauses.append("preference_key = %s")
        params.append(preference_key)
    sql = f"""
        SELECT CAST(user_id AS TEXT) AS user_id, project_type, project_domain, preference_key,
               preference_value, set_by, created_at, updated_at
        FROM advisor_preferences.preferences
        WHERE {' AND '.join(clauses)}
        ORDER BY preference_key, project_type NULLS LAST, project_domain NULLS LAST
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        return [_row_dict(cur, row) for row in cur.fetchall()]


def upsert_preference(
    user_id: str,
    project_type: str | None,
    project_domain: str | None,
    preference_key: str,
    preference_value: Any,
    set_by: str,
) -> tuple[bool, Any]:
    """Insert or update one explicit preference row."""
    previous = get_preference_row(user_id, project_type, project_domain, preference_key)
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        now = time.time()
        encoded = json.dumps(preference_value, sort_keys=True)
        with _sqlite_lock:
            if previous is None:
                conn.execute(
                    """
                    INSERT INTO advisor_preferences_preferences
                      (user_id, project_type, project_domain, preference_key,
                       preference_value, set_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        project_type,
                        project_domain,
                        preference_key,
                        encoded,
                        set_by,
                        now,
                        now,
                    ),
                )
            else:
                conn.execute(
                    f"""
                    UPDATE advisor_preferences_preferences
                    SET preference_value = ?, set_by = ?, updated_at = ?
                    WHERE {_sqlite_nullsafe_where()}
                    """,
                    (
                        encoded,
                        set_by,
                        now,
                        user_id,
                        project_type,
                        project_type,
                        project_domain,
                        project_domain,
                        preference_key,
                    ),
                )
            conn.commit()
        return previous is None, None if previous is None else previous.get("preference_value")

    sql = """
        INSERT INTO advisor_preferences.preferences
          (user_id, project_type, project_domain, preference_key, preference_value, set_by)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, project_type, project_domain, preference_key)
        DO UPDATE SET
          preference_value = EXCLUDED.preference_value,
          set_by = EXCLUDED.set_by,
          updated_at = now()
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                user_id,
                project_type,
                project_domain,
                preference_key,
                json.dumps(preference_value),
                set_by,
            ),
        )
    return previous is None, None if previous is None else previous.get("preference_value")


def delete_preference(
    user_id: str,
    project_type: str | None,
    project_domain: str | None,
    preference_key: str,
) -> dict[str, Any] | None:
    """Delete one explicit preference row and return its prior value."""
    previous = get_preference_row(user_id, project_type, project_domain, preference_key)
    if previous is None:
        return None
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            conn.execute(
                f"""
                DELETE FROM advisor_preferences_preferences
                WHERE {_sqlite_nullsafe_where()}
                """,
                (
                    user_id,
                    project_type,
                    project_type,
                    project_domain,
                    project_domain,
                    preference_key,
                ),
            )
            conn.commit()
        return previous

    sql = """
        DELETE FROM advisor_preferences.preferences
        WHERE CAST(user_id AS TEXT) = %s
          AND project_type IS NOT DISTINCT FROM %s
          AND project_domain IS NOT DISTINCT FROM %s
          AND preference_key = %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (user_id, project_type, project_domain, preference_key))
    return previous


def clear_preference_key_for_user(user_id: str, preference_key: str) -> list[dict[str, Any]]:
    """Delete all explicit values for one key belonging to a user."""
    rows = list_preferences(user_id, preference_key=preference_key)
    if not rows:
        return []
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            conn.execute(
                """
                DELETE FROM advisor_preferences_preferences
                WHERE user_id = ? AND preference_key = ?
                """,
                (user_id, preference_key),
            )
            conn.commit()
        return rows

    sql = """
        DELETE FROM advisor_preferences.preferences
        WHERE CAST(user_id AS TEXT) = %s
          AND preference_key = %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (user_id, preference_key))
    return rows


def get_catalog_entries(catalog_type: str, include_custom: bool = True) -> list[dict[str, Any]]:
    """Return catalog rows for one catalog type."""
    if _use_sqlite_store():
        mapping = {
            "project_domain": (
                "advisor_preferences_project_domain_catalog",
                "domain_id",
                "NULL AS metadata",
            ),
            "project_type": (
                "advisor_preferences_project_type_catalog",
                "type_id",
                "NULL AS metadata",
            ),
            "preference_key": (
                "advisor_preferences_preference_key_catalog",
                "preference_key",
                "json_object('value_schema', value_schema, 'default_value', default_value, "
                "'is_hard_change', is_hard_change) AS metadata",
            ),
        }
        table_name, id_column, metadata_expr = mapping[catalog_type]
        where = "" if include_custom else "WHERE is_system = 1"
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            rows = conn.execute(
                f"""
                SELECT {id_column} AS entry_id,
                       display_name,
                       description,
                       is_system,
                       is_immutable,
                       {metadata_expr}
                FROM {table_name}
                {where}
                ORDER BY entry_id
                """
            ).fetchall()
        normalized = _sqlite_rows_to_dicts(rows)
        for row in normalized:
            if isinstance(row.get("metadata"), dict):
                metadata = row["metadata"]
                for key in ("value_schema", "default_value"):
                    if isinstance(metadata.get(key), str):
                        metadata[key] = _maybe_json_load(metadata[key])
        return normalized

    mapping = {
        "project_domain": (
            "advisor_preferences.project_domain_catalog",
            "domain_id",
            "{}::jsonb",
        ),
        "project_type": (
            "advisor_preferences.project_type_catalog",
            "type_id",
            "{}::jsonb",
        ),
        "preference_key": (
            "advisor_preferences.preference_key_catalog",
            "preference_key",
            "jsonb_build_object("
            "'value_schema', value_schema, "
            "'default_value', default_value, "
            "'is_hard_change', is_hard_change)",
        ),
    }
    table_name, id_column, metadata_expr = mapping[catalog_type]
    where = "" if include_custom else "WHERE is_system = true"
    sql = f"""
        SELECT {id_column} AS entry_id,
               display_name,
               description,
               is_system,
               is_immutable,
               {metadata_expr} AS metadata
        FROM {table_name}
        {where}
        ORDER BY entry_id
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [_row_dict(cur, row) for row in cur.fetchall()]


def add_custom_catalog_entry(
    catalog_type: str,
    entry_id: str,
    display_name: str,
    description: str,
    created_by: str,
) -> bool:
    """Insert a custom catalog row."""
    if not entry_id.startswith("custom:"):
        return False
    if _use_sqlite_store():
        if catalog_type not in {"project_domain", "project_type"}:
            return False
        table_name = (
            "advisor_preferences_project_domain_catalog"
            if catalog_type == "project_domain"
            else "advisor_preferences_project_type_catalog"
        )
        id_column = "domain_id" if catalog_type == "project_domain" else "type_id"
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            cur = conn.execute(
                f"""
                INSERT OR IGNORE INTO {table_name}
                  ({id_column}, display_name, is_system, is_immutable,
                   description, created_at, created_by)
                VALUES (?, ?, 0, 0, ?, ?, ?)
                """,
                (entry_id, display_name, description, time.time(), created_by),
            )
            conn.commit()
            return cur.rowcount > 0

    mapping = {
        "project_domain": (
            "advisor_preferences.project_domain_catalog",
            "domain_id",
            "(domain_id, display_name, is_system, is_immutable, description, created_by)",
        ),
        "project_type": (
            "advisor_preferences.project_type_catalog",
            "type_id",
            "(type_id, display_name, is_system, is_immutable, description, created_by)",
        ),
    }
    if catalog_type == "preference_key":
        return False
    table_name, _, columns = mapping[catalog_type]
    sql = f"""
        INSERT INTO {table_name}
          {columns}
        VALUES (%s, %s, false, false, %s, %s)
        ON CONFLICT DO NOTHING
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (entry_id, display_name, description, created_by))
        return cur.rowcount > 0


def get_preference_key_meta(preference_key: str) -> dict[str, Any] | None:
    """Return metadata for a preference key."""
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            row = conn.execute(
                """
                SELECT preference_key, display_name, description, value_schema,
                       default_value, is_hard_change
                FROM advisor_preferences_preference_key_catalog
                WHERE preference_key = ?
                """,
                (preference_key,),
            ).fetchone()
        return _sqlite_row_to_dict(row)

    sql = """
        SELECT preference_key, display_name, description, value_schema,
               default_value, is_hard_change
        FROM advisor_preferences.preference_key_catalog
        WHERE preference_key = %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (preference_key,))
        row = cur.fetchone()
        return _row_dict(cur, row) if row else None


def get_system_default(preference_key: str) -> Any:
    """Return catalog default for one preference key."""
    if _use_sqlite_store():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            row = conn.execute(
                """
                SELECT default_value
                FROM advisor_preferences_preference_key_catalog
                WHERE preference_key = ?
                """,
                (preference_key,),
            ).fetchone()
        return None if row is None else _maybe_json_load(row["default_value"])

    sql = """
        SELECT default_value
        FROM advisor_preferences.preference_key_catalog
        WHERE preference_key = %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (preference_key,))
        row = cur.fetchone()
        return None if row is None else _maybe_json_load(row[0])


def insert_audit_row(
    user_id: str,
    project_type: str | None,
    project_domain: str | None,
    preference_key: str,
    old_value: Any,
    new_value: Any,
    change_type: str,
    changed_by: str,
    reason: str | None,
) -> str:
    """Append one audit row and return its id."""
    if _use_sqlite_store():
        audit_id = str(uuid.uuid4())
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            conn.execute(
                """
                INSERT INTO advisor_preferences_preferences_audit
                  (audit_id, user_id, project_type, project_domain, preference_key,
                   old_value, new_value, change_type, changed_by, changed_at, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    user_id,
                    project_type,
                    project_domain,
                    preference_key,
                    json.dumps(old_value, sort_keys=True),
                    json.dumps(new_value, sort_keys=True),
                    change_type,
                    changed_by,
                    time.time(),
                    reason,
                ),
            )
            conn.commit()
        return audit_id

    sql = """
        INSERT INTO advisor_preferences.preferences_audit
          (user_id, project_type, project_domain, preference_key,
           old_value, new_value, change_type, changed_by, reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING CAST(audit_id AS TEXT)
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                user_id,
                project_type,
                project_domain,
                preference_key,
                json.dumps(old_value),
                json.dumps(new_value),
                change_type,
                changed_by,
                reason,
            ),
        )
        return str(cur.fetchone()[0])


def list_audit_rows(
    user_id: str,
    *,
    since: Any = None,
    limit: int = 100,
    preference_key: str | None = None,
) -> list[dict[str, Any]]:
    """Return audit history rows for a user."""
    if _use_sqlite_store():
        clauses = ["user_id = ?"]
        params: list[Any] = [user_id]
        if since is not None:
            if isinstance(since, datetime):
                since_value = since.timestamp()
            else:
                since_value = float(since)
            clauses.append("changed_at >= ?")
            params.append(since_value)
        if preference_key not in (None, ""):
            clauses.append("preference_key = ?")
            params.append(preference_key)
        params.append(int(limit))
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            rows = conn.execute(
                f"""
                SELECT audit_id, user_id, project_type, project_domain,
                       preference_key, old_value, new_value, change_type,
                       changed_by, changed_at, reason
                FROM advisor_preferences_preferences_audit
                WHERE {' AND '.join(clauses)}
                ORDER BY changed_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return _sqlite_rows_to_dicts(rows)

    clauses = ["CAST(user_id AS TEXT) = %s"]
    params: list[Any] = [user_id]
    if since is not None:
        clauses.append("changed_at >= %s")
        params.append(since)
    if preference_key not in (None, ""):
        clauses.append("preference_key = %s")
        params.append(preference_key)
    params.append(limit)
    sql = f"""
        SELECT CAST(audit_id AS TEXT) AS audit_id, CAST(user_id AS TEXT) AS user_id,
               project_type, project_domain, preference_key, old_value, new_value,
               change_type, changed_by, changed_at, reason
        FROM advisor_preferences.preferences_audit
        WHERE {' AND '.join(clauses)}
        ORDER BY changed_at DESC
        LIMIT %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        return [_row_dict(cur, row) for row in cur.fetchall()]
