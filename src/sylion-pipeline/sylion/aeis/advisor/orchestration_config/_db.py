"""PostgreSQL helpers for advisor orchestration_config."""
from __future__ import annotations

import json
from typing import Any

from sylion.aeis.advisor._db import get_pool


_DEFAULT_OPERATOR_ID = "00000000-0000-0000-0000-000000000001"


def _json_load(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return value


def _columns(cursor) -> list[str]:
    return [item[0] for item in cursor.description]


def _row_dict(cursor, row: tuple[Any, ...] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(zip(_columns(cursor), row))


def _rows_dicts(cursor, rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    cols = _columns(cursor)
    return [dict(zip(cols, row)) for row in rows]


def get_default_operator_id() -> str:
    return _DEFAULT_OPERATOR_ID


def load_llm_judge_routing(operator_id: str = _DEFAULT_OPERATOR_ID) -> list[dict[str, Any]]:
    sql = """
        SELECT recommendation_type, risk_level, model_id, enabled
        FROM advisor_orchestration.llm_judge_routing
        WHERE operator_id = %s::uuid
        ORDER BY recommendation_type, risk_level
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (operator_id,))
        return _rows_dicts(cur, cur.fetchall())


def replace_llm_judge_routing(
    cells: list[dict[str, Any]],
    operator_id: str = _DEFAULT_OPERATOR_ID,
) -> None:
    delete_sql = "DELETE FROM advisor_orchestration.llm_judge_routing WHERE operator_id = %s::uuid"
    insert_sql = """
        INSERT INTO advisor_orchestration.llm_judge_routing
          (operator_id, recommendation_type, risk_level, model_id, enabled, updated_at)
        VALUES (%s::uuid, %s, %s, %s, %s, now())
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(delete_sql, (operator_id,))
        for cell in cells:
            cur.execute(
                insert_sql,
                (
                    operator_id,
                    cell["recommendation_type"],
                    cell["risk_level"],
                    cell["model_id"],
                    bool(cell.get("enabled", True)),
                ),
            )


def load_council_rules(operator_id: str = _DEFAULT_OPERATOR_ID) -> dict[str, Any] | None:
    sql = """
        SELECT rank_weights, critic_gate_enabled, critic_gate_threshold,
               quorum_min, quorum_type, sentinel_requirements, updated_at
        FROM advisor_orchestration.council_rules
        WHERE operator_id = %s::uuid
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (operator_id,))
        row = _row_dict(cur, cur.fetchone())
    if row is None:
        return None
    row["rank_weights"] = _json_load(row["rank_weights"], [])
    row["sentinel_requirements"] = _json_load(row["sentinel_requirements"], [])
    return row


def upsert_council_rules(data: dict[str, Any], operator_id: str = _DEFAULT_OPERATOR_ID) -> None:
    sql = """
        INSERT INTO advisor_orchestration.council_rules
          (operator_id, rank_weights, critic_gate_enabled, critic_gate_threshold,
           quorum_min, quorum_type, sentinel_requirements, updated_at)
        VALUES (%s::uuid, %s::jsonb, %s, %s, %s, %s, %s::jsonb, now())
        ON CONFLICT (operator_id) DO UPDATE SET
          rank_weights = EXCLUDED.rank_weights,
          critic_gate_enabled = EXCLUDED.critic_gate_enabled,
          critic_gate_threshold = EXCLUDED.critic_gate_threshold,
          quorum_min = EXCLUDED.quorum_min,
          quorum_type = EXCLUDED.quorum_type,
          sentinel_requirements = EXCLUDED.sentinel_requirements,
          updated_at = EXCLUDED.updated_at
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                operator_id,
                json.dumps(data["rank_weights"]),
                data["critic_gate_enabled"],
                data["critic_gate_threshold"],
                data["quorum_min"],
                data["quorum_type"],
                json.dumps(data["sentinel_requirements"]),
            ),
        )


def load_auditor_cadence(operator_id: str = _DEFAULT_OPERATOR_ID) -> dict[str, Any] | None:
    sql = """
        SELECT tick_frequency_seconds, enabled_dimensions, phase_boundary_cron,
               last_audit_at, last_10_audits, updated_at
        FROM advisor_orchestration.auditor_cadence
        WHERE operator_id = %s::uuid
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (operator_id,))
        row = _row_dict(cur, cur.fetchone())
    if row is None:
        return None
    row["enabled_dimensions"] = _json_load(row["enabled_dimensions"], [])
    row["last_10_audits"] = _json_load(row["last_10_audits"], [])
    return row


def upsert_auditor_cadence(data: dict[str, Any], operator_id: str = _DEFAULT_OPERATOR_ID) -> None:
    sql = """
        INSERT INTO advisor_orchestration.auditor_cadence
          (operator_id, tick_frequency_seconds, enabled_dimensions, phase_boundary_cron,
           last_audit_at, last_10_audits, updated_at)
        VALUES (%s::uuid, %s, %s::jsonb, %s, %s, %s::jsonb, now())
        ON CONFLICT (operator_id) DO UPDATE SET
          tick_frequency_seconds = EXCLUDED.tick_frequency_seconds,
          enabled_dimensions = EXCLUDED.enabled_dimensions,
          phase_boundary_cron = EXCLUDED.phase_boundary_cron,
          last_audit_at = EXCLUDED.last_audit_at,
          last_10_audits = EXCLUDED.last_10_audits,
          updated_at = EXCLUDED.updated_at
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                operator_id,
                data["tick_frequency_seconds"],
                json.dumps(data["enabled_dimensions"]),
                data["phase_boundary_cron"],
                data.get("last_audit_at"),
                json.dumps(data.get("last_10_audits", [])),
            ),
        )


def load_fixer_protocol(operator_id: str = _DEFAULT_OPERATOR_ID) -> dict[str, Any] | None:
    sql = """
        SELECT retry_budgets, escalation_path, max_nogo_iterations,
               auto_revert_on_critical_security, updated_at
        FROM advisor_orchestration.fixer_protocol
        WHERE operator_id = %s::uuid
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (operator_id,))
        row = _row_dict(cur, cur.fetchone())
    if row is None:
        return None
    row["retry_budgets"] = _json_load(row["retry_budgets"], [])
    row["escalation_path"] = _json_load(row["escalation_path"], [])
    return row


def upsert_fixer_protocol(data: dict[str, Any], operator_id: str = _DEFAULT_OPERATOR_ID) -> None:
    sql = """
        INSERT INTO advisor_orchestration.fixer_protocol
          (operator_id, retry_budgets, escalation_path, max_nogo_iterations,
           auto_revert_on_critical_security, updated_at)
        VALUES (%s::uuid, %s::jsonb, %s::jsonb, %s, %s, now())
        ON CONFLICT (operator_id) DO UPDATE SET
          retry_budgets = EXCLUDED.retry_budgets,
          escalation_path = EXCLUDED.escalation_path,
          max_nogo_iterations = EXCLUDED.max_nogo_iterations,
          auto_revert_on_critical_security = EXCLUDED.auto_revert_on_critical_security,
          updated_at = EXCLUDED.updated_at
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                operator_id,
                json.dumps(data["retry_budgets"]),
                json.dumps(data["escalation_path"]),
                data["max_nogo_iterations"],
                data["auto_revert_on_critical_security"],
            ),
        )


def load_dispatch_config(operator_id: str = _DEFAULT_OPERATOR_ID) -> dict[str, Any] | None:
    sql = """
        SELECT parallelism_mode, max_simultaneous, stage_allocation_rules,
               cost_ceiling_usd_per_hour, sub_agent_permission_by_type, updated_at
        FROM advisor_orchestration.dispatch_config
        WHERE operator_id = %s::uuid
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (operator_id,))
        row = _row_dict(cur, cur.fetchone())
    if row is None:
        return None
    row["stage_allocation_rules"] = _json_load(row["stage_allocation_rules"], [])
    row["sub_agent_permission_by_type"] = _json_load(row["sub_agent_permission_by_type"], {})
    return row


def upsert_dispatch_config(data: dict[str, Any], operator_id: str = _DEFAULT_OPERATOR_ID) -> None:
    sql = """
        INSERT INTO advisor_orchestration.dispatch_config
          (operator_id, parallelism_mode, max_simultaneous, stage_allocation_rules,
           cost_ceiling_usd_per_hour, sub_agent_permission_by_type, updated_at)
        VALUES (%s::uuid, %s, %s, %s::jsonb, %s, %s::jsonb, now())
        ON CONFLICT (operator_id) DO UPDATE SET
          parallelism_mode = EXCLUDED.parallelism_mode,
          max_simultaneous = EXCLUDED.max_simultaneous,
          stage_allocation_rules = EXCLUDED.stage_allocation_rules,
          cost_ceiling_usd_per_hour = EXCLUDED.cost_ceiling_usd_per_hour,
          sub_agent_permission_by_type = EXCLUDED.sub_agent_permission_by_type,
          updated_at = EXCLUDED.updated_at
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                operator_id,
                data["parallelism_mode"],
                data.get("max_simultaneous"),
                json.dumps(data["stage_allocation_rules"]),
                data.get("cost_ceiling_usd_per_hour"),
                json.dumps(data["sub_agent_permission_by_type"]),
            ),
        )


def list_test_catalog(operator_id: str = _DEFAULT_OPERATOR_ID) -> list[dict[str, Any]]:
    sql = """
        SELECT test_id::text, name, module, suite, test_type, status,
               last_run_at, last_run_output
        FROM advisor_orchestration.test_catalog
        WHERE operator_id = %s::uuid
        ORDER BY module, name
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (operator_id,))
        return _rows_dicts(cur, cur.fetchall())


def replace_test_catalog(entries: list[dict[str, Any]], operator_id: str = _DEFAULT_OPERATOR_ID) -> None:
    delete_sql = "DELETE FROM advisor_orchestration.test_catalog WHERE operator_id = %s::uuid"
    insert_sql = """
        INSERT INTO advisor_orchestration.test_catalog
          (test_id, operator_id, name, module, suite, test_type, status, last_run_at, last_run_output, updated_at)
        VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, now())
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(delete_sql, (operator_id,))
        for entry in entries:
            cur.execute(
                insert_sql,
                (
                    entry["test_id"],
                    operator_id,
                    entry["name"],
                    entry["module"],
                    entry["suite"],
                    entry["test_type"],
                    entry.get("status", "never_run"),
                    entry.get("last_run_at"),
                    entry.get("last_run_output"),
                ),
            )


def list_test_catalog_runs(limit: int = 20, operator_id: str = _DEFAULT_OPERATOR_ID) -> list[dict[str, Any]]:
    sql = """
        SELECT run_id::text, test_id::text, suite, status, triggered_at, completed_at, output
        FROM advisor_orchestration.test_catalog_runs
        WHERE operator_id = %s::uuid
        ORDER BY triggered_at DESC
        LIMIT %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (operator_id, limit))
        return _rows_dicts(cur, cur.fetchall())


def insert_test_catalog_run(data: dict[str, Any], operator_id: str = _DEFAULT_OPERATOR_ID) -> None:
    sql = """
        INSERT INTO advisor_orchestration.test_catalog_runs
          (run_id, operator_id, test_id, suite, status, triggered_at, completed_at, output)
        VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s)
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                data["run_id"],
                operator_id,
                data.get("test_id"),
                data.get("suite"),
                data["status"],
                data.get("triggered_at"),
                data.get("completed_at"),
                data.get("output"),
            ),
        )


def list_team_formation_rules(operator_id: str = _DEFAULT_OPERATOR_ID) -> list[dict[str, Any]]:
    sql = """
        SELECT rule_id::text, trigger_pattern, agent_types, lifetime, action, enabled, created_at, updated_at
        FROM advisor_orchestration.team_formation_rules
        WHERE operator_id = %s::uuid
        ORDER BY created_at ASC
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (operator_id,))
        rows = _rows_dicts(cur, cur.fetchall())
    for row in rows:
        row["agent_types"] = _json_load(row["agent_types"], [])
    return rows


def replace_team_formation_rules(
    rules: list[dict[str, Any]],
    operator_id: str = _DEFAULT_OPERATOR_ID,
) -> None:
    delete_sql = "DELETE FROM advisor_orchestration.team_formation_rules WHERE operator_id = %s::uuid"
    insert_sql = """
        INSERT INTO advisor_orchestration.team_formation_rules
          (rule_id, operator_id, trigger_pattern, agent_types, lifetime, action, enabled, created_at, updated_at)
        VALUES (%s::uuid, %s::uuid, %s, %s::jsonb, %s, %s, %s, %s, now())
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(delete_sql, (operator_id,))
        for rule in rules:
            cur.execute(
                insert_sql,
                (
                    rule["rule_id"],
                    operator_id,
                    rule["trigger_pattern"],
                    json.dumps(rule["agent_types"]),
                    rule["lifetime"],
                    rule["action"],
                    rule.get("enabled", True),
                    rule.get("created_at"),
                ),
            )


def insert_team_formation_rule(rule: dict[str, Any], operator_id: str = _DEFAULT_OPERATOR_ID) -> None:
    sql = """
        INSERT INTO advisor_orchestration.team_formation_rules
          (rule_id, operator_id, trigger_pattern, agent_types, lifetime, action, enabled, created_at, updated_at)
        VALUES (%s::uuid, %s::uuid, %s, %s::jsonb, %s, %s, %s, %s, now())
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                rule["rule_id"],
                operator_id,
                rule["trigger_pattern"],
                json.dumps(rule["agent_types"]),
                rule["lifetime"],
                rule["action"],
                rule.get("enabled", True),
                rule.get("created_at"),
            ),
        )


def list_active_teams(operator_id: str = _DEFAULT_OPERATOR_ID) -> list[dict[str, Any]]:
    sql = """
        SELECT team_id::text, rule_id::text, agent_types, current_task, formed_at, lifetime
        FROM advisor_orchestration.active_teams
        WHERE operator_id = %s::uuid AND disbanded_at IS NULL
        ORDER BY formed_at DESC
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (operator_id,))
        rows = _rows_dicts(cur, cur.fetchall())
    for row in rows:
        row["agent_types"] = _json_load(row["agent_types"], [])
    return rows


def load_event_map_cache(operator_id: str = _DEFAULT_OPERATOR_ID) -> dict[str, Any] | None:
    sql = """
        SELECT nodes, edges, generated_at, updated_at
        FROM advisor_orchestration.event_map_cache
        WHERE operator_id = %s::uuid
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (operator_id,))
        row = _row_dict(cur, cur.fetchone())
    if row is None:
        return None
    row["nodes"] = _json_load(row["nodes"], [])
    row["edges"] = _json_load(row["edges"], [])
    return row


def upsert_event_map_cache(data: dict[str, Any], operator_id: str = _DEFAULT_OPERATOR_ID) -> None:
    sql = """
        INSERT INTO advisor_orchestration.event_map_cache
          (operator_id, nodes, edges, generated_at, updated_at)
        VALUES (%s::uuid, %s::jsonb, %s::jsonb, %s, now())
        ON CONFLICT (operator_id) DO UPDATE SET
          nodes = EXCLUDED.nodes,
          edges = EXCLUDED.edges,
          generated_at = EXCLUDED.generated_at,
          updated_at = EXCLUDED.updated_at
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                operator_id,
                json.dumps(data["nodes"]),
                json.dumps(data["edges"]),
                data.get("generated_at"),
            ),
        )


def load_inter_model_conversations(operator_id: str = _DEFAULT_OPERATOR_ID) -> dict[str, Any] | None:
    sql = """
        SELECT enabled, max_turns, arbiter_model_id, disagreement_voting,
               recent_conversations, updated_at
        FROM advisor_orchestration.inter_model_conversations
        WHERE operator_id = %s::uuid
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (operator_id,))
        row = _row_dict(cur, cur.fetchone())
    if row is None:
        return None
    row["recent_conversations"] = _json_load(row["recent_conversations"], [])
    return row


def upsert_inter_model_conversations(
    data: dict[str, Any],
    operator_id: str = _DEFAULT_OPERATOR_ID,
) -> None:
    sql = """
        INSERT INTO advisor_orchestration.inter_model_conversations
          (operator_id, enabled, max_turns, arbiter_model_id, disagreement_voting,
           recent_conversations, updated_at)
        VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb, now())
        ON CONFLICT (operator_id) DO UPDATE SET
          enabled = EXCLUDED.enabled,
          max_turns = EXCLUDED.max_turns,
          arbiter_model_id = EXCLUDED.arbiter_model_id,
          disagreement_voting = EXCLUDED.disagreement_voting,
          recent_conversations = EXCLUDED.recent_conversations,
          updated_at = EXCLUDED.updated_at
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                operator_id,
                data["enabled"],
                data["max_turns"],
                data.get("arbiter_model_id"),
                data["disagreement_voting"],
                json.dumps(data.get("recent_conversations", [])),
            ),
        )
