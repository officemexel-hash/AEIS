"""Database helpers for advisor actions."""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Any

from sylion.aeis.advisor._db import fetch_all, fetch_one, get_pool
from sylion.aeis.advisor.engine import _db as engine_db

from ._models import CardAction, RouteAuditRow, RouteStatus


def _use_sqlite_store() -> bool:
    return bool(engine_db._use_sqlite_store())


def _sqlite_conn():
    conn = engine_db._get_sqlite_conn()
    with engine_db._sqlite_lock:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS advisor_actions_route_audit (
              route_audit_id TEXT PRIMARY KEY,
              card_id TEXT NOT NULL,
              action TEXT NOT NULL,
              routed_to_module TEXT NOT NULL,
              routed_target_id TEXT,
              payload_sent_jsonb TEXT NOT NULL DEFAULT '{}',
              response_jsonb TEXT,
              status TEXT NOT NULL,
              error_message TEXT,
              routed_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_adv_actions_card "
            "ON advisor_actions_route_audit(card_id, routed_at)"
        )
        conn.commit()
    return conn


def _json_loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def log_route_row(
    *,
    card_id: str,
    action: CardAction,
    routed_to_module: str,
    routed_target_id: str | None,
    payload_sent: dict[str, Any],
    response: dict[str, Any] | None,
    status: RouteStatus,
    error_message: str | None,
) -> str:
    if _use_sqlite_store():
        route_audit_id = str(uuid.uuid4())
        conn = _sqlite_conn()
        with engine_db._sqlite_lock:
            conn.execute(
                """INSERT INTO advisor_actions_route_audit
                   (route_audit_id, card_id, action, routed_to_module, routed_target_id,
                    payload_sent_jsonb, response_jsonb, status, error_message, routed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    route_audit_id,
                    card_id,
                    action.value,
                    routed_to_module,
                    routed_target_id,
                    json.dumps(payload_sent),
                    json.dumps(response) if response is not None else None,
                    status.value,
                    error_message,
                    time.time(),
                ),
            )
            conn.commit()
        return route_audit_id

    sql = """
        INSERT INTO advisor_actions.action_routes_audit
          (card_id, action, routed_to_module, routed_target_id,
           payload_sent_jsonb, response_jsonb, status, error_message)
        VALUES (%s, %s::advisor_engine.card_action, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
        RETURNING route_audit_id
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                card_id,
                action.value,
                routed_to_module,
                routed_target_id,
                json.dumps(payload_sent),
                json.dumps(response) if response is not None else None,
                status.value,
                error_message,
            ),
        )
        return str(cur.fetchone()[0])


def list_route_rows(card_id: str) -> list[RouteAuditRow]:
    if _use_sqlite_store():
        conn = _sqlite_conn()
        with engine_db._sqlite_lock:
            rows = conn.execute(
                """SELECT route_audit_id, card_id, action, routed_to_module, routed_target_id,
                          payload_sent_jsonb, response_jsonb, status, error_message, routed_at
                   FROM advisor_actions_route_audit
                   WHERE card_id = ?
                   ORDER BY routed_at ASC""",
                (card_id,),
            ).fetchall()
        return [
            RouteAuditRow(
                route_audit_id=str(row["route_audit_id"]),
                card_id=str(row["card_id"]),
                action=CardAction(str(row["action"])),
                routed_to_module=str(row["routed_to_module"]),
                routed_target_id=str(row["routed_target_id"]) if row["routed_target_id"] else None,
                payload_sent=_json_loads(row["payload_sent_jsonb"], {}),
                response=_json_loads(row["response_jsonb"], None),
                status=RouteStatus(str(row["status"])),
                error_message=row["error_message"],
                routed_at=datetime.fromtimestamp(float(row["routed_at"])),
            )
            for row in rows
        ]

    sql = """
        SELECT route_audit_id, card_id, action, routed_to_module, routed_target_id,
               payload_sent_jsonb, response_jsonb, status, error_message, routed_at
        FROM advisor_actions.action_routes_audit
        WHERE card_id = %s
        ORDER BY routed_at ASC
    """
    rows = fetch_all(sql, (card_id,))
    return [
        RouteAuditRow(
            route_audit_id=str(row[0]),
            card_id=str(row[1]),
            action=CardAction(str(row[2])),
            routed_to_module=str(row[3]),
            routed_target_id=str(row[4]) if row[4] else None,
            payload_sent=row[5] or {},
            response=row[6],
            status=RouteStatus(str(row[7])),
            error_message=row[8],
            routed_at=row[9] if isinstance(row[9], datetime) else datetime.utcnow(),
        )
        for row in rows
    ]


def update_route_status(route_audit_id: str, status: RouteStatus, error_message: str | None) -> None:
    if _use_sqlite_store():
        conn = _sqlite_conn()
        with engine_db._sqlite_lock:
            conn.execute(
                "UPDATE advisor_actions_route_audit SET status = ?, error_message = ? WHERE route_audit_id = ?",
                (status.value, error_message, route_audit_id),
            )
            conn.commit()
        return

    sql = """
        UPDATE advisor_actions.action_routes_audit
        SET status = %s, error_message = %s
        WHERE route_audit_id = %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (status.value, error_message, route_audit_id))


def get_route_for_retry(route_audit_id: str) -> tuple[Any, ...] | None:
    if _use_sqlite_store():
        conn = _sqlite_conn()
        with engine_db._sqlite_lock:
            row = conn.execute(
                """SELECT route_audit_id, card_id, action, payload_sent_jsonb, status
                   FROM advisor_actions_route_audit
                   WHERE route_audit_id = ?""",
                (route_audit_id,),
            ).fetchone()
        if row is None:
            return None
        return (
            row["route_audit_id"],
            row["card_id"],
            row["action"],
            _json_loads(row["payload_sent_jsonb"], {}),
            row["status"],
        )

    sql = """
        SELECT route_audit_id, card_id, action, payload_sent_jsonb, status
        FROM advisor_actions.action_routes_audit
        WHERE route_audit_id = %s
    """
    return fetch_one(sql, (route_audit_id,))


def fetch_card_snapshot(card_id: str) -> tuple[Any, ...] | None:
    if _use_sqlite_store():
        row = engine_db.fetch_recommendation_by_id(card_id)
        if not row:
            return None
        return (
            row.get("card_id"),
            row.get("title"),
            row.get("rationale"),
            row.get("d_level"),
            row.get("evidence_pack_id"),
            row.get("project_id"),
            _json_loads(row.get("body_jsonb"), {}),
        )

    sql = """
        SELECT card_id, title, rationale, d_level, evidence_pack_id, project_id, body_jsonb
        FROM advisor_engine.recommendations
        WHERE card_id = %s
    """
    return fetch_one(sql, (card_id,))


def append_card_tag(card_id: str, tag: str) -> None:
    if _use_sqlite_store():
        row = engine_db.fetch_recommendation_by_id(card_id)
        if not row:
            return
        tags = _json_loads(row.get("tags"), [])
        if tag not in tags:
            tags.append(tag)
        conn = _sqlite_conn()
        with engine_db._sqlite_lock:
            conn.execute(
                "UPDATE advisor_engine_recommendations SET tags = ?, updated_at = ? WHERE card_id = ?",
                (json.dumps(tags), time.time(), card_id),
            )
            conn.commit()
        return

    sql = """
        UPDATE advisor_engine.recommendations
        SET tags = CASE
            WHEN tags IS NULL THEN ARRAY[%s]
            WHEN NOT (%s = ANY(tags)) THEN array_append(tags, %s)
            ELSE tags
        END,
        updated_at = NOW()
        WHERE card_id = %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (tag, tag, tag, card_id))


def apply_card_modification(card_id: str, modified_recommendation: str) -> bool:
    """Persist an operator-edited recommendation as the new card content.

    The dashboard renders both ``header.rationale`` and ``body.recommendation``.
    Storing the edit only as a metadata flag makes the UI report success while
    showing the old recommendation, so the canonical card fields must change.
    """
    text = str(modified_recommendation or "").strip()
    if not text:
        return False

    now = time.time()
    if _use_sqlite_store():
        row = engine_db.fetch_recommendation_by_id(card_id)
        if not row:
            return False
        body = _json_loads(row.get("body_jsonb"), {})
        if "original_recommendation" not in body:
            body["original_recommendation"] = body.get("recommendation") or row.get("rationale") or ""
        body["recommendation"] = text
        body["modified_recommendation"] = text
        body["operator_modified_recommendation"] = text
        body["operator_modified_at"] = now
        body["modified_by_operator"] = True

        tags = _json_loads(row.get("tags"), [])
        if "modified_by_operator" not in tags:
            tags.append("modified_by_operator")

        conn = _sqlite_conn()
        with engine_db._sqlite_lock:
            cur = conn.execute(
                """UPDATE advisor_engine_recommendations
                   SET rationale = ?, body_jsonb = ?, tags = ?, updated_at = ?
                   WHERE card_id = ?""",
                (text, json.dumps(body), json.dumps(tags), now, card_id),
            )
            conn.commit()
        return cur.rowcount > 0

    sql = """
        UPDATE advisor_engine.recommendations
        SET rationale = %s,
            body_jsonb = (
                CASE
                    WHEN NOT (COALESCE(body_jsonb, '{}'::jsonb) ? 'original_recommendation')
                    THEN COALESCE(body_jsonb, '{}'::jsonb)
                         || jsonb_build_object(
                             'original_recommendation',
                             COALESCE(body_jsonb->>'recommendation', rationale, '')
                         )
                    ELSE COALESCE(body_jsonb, '{}'::jsonb)
                END
            ) || jsonb_build_object(
                'recommendation', %s,
                'modified_recommendation', %s,
                'operator_modified_recommendation', %s,
                'operator_modified_at', %s,
                'modified_by_operator', true
            ),
            tags = CASE
                WHEN tags IS NULL THEN ARRAY['modified_by_operator']
                WHEN NOT ('modified_by_operator' = ANY(tags)) THEN array_append(tags, 'modified_by_operator')
                ELSE tags
            END,
            updated_at = NOW()
        WHERE card_id = %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (text, text, text, text, now, card_id))
        return int(cur.rowcount or 0) > 0


def set_card_flag(card_id: str, flag_name: str, flag_value: Any) -> None:
    if _use_sqlite_store():
        row = engine_db.fetch_recommendation_by_id(card_id)
        if not row:
            return
        body = _json_loads(row.get("body_jsonb"), {})
        body[str(flag_name)] = flag_value
        conn = _sqlite_conn()
        with engine_db._sqlite_lock:
            conn.execute(
                "UPDATE advisor_engine_recommendations SET body_jsonb = ?, updated_at = ? WHERE card_id = ?",
                (json.dumps(body), time.time(), card_id),
            )
            conn.commit()
        return

    sql = """
        UPDATE advisor_engine.recommendations
        SET body_jsonb = COALESCE(body_jsonb, '{}'::jsonb) || jsonb_build_object(%s, %s),
            updated_at = NOW()
        WHERE card_id = %s
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (flag_name, flag_value, card_id))
