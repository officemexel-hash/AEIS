"""History DB layer — uses shared PG pool from `sylion.aeis.advisor._db`.

Per `08_audit_revisions.md` Revision 2 the advisor layer is PG-only. The
canonical schema (`advisor_history.*` partitioned monthly) lives in
`sylion/db/advisor_layer.sql` and ships via Alembic revision
`20260425_0002_advisor_layer.py`. This module reads/writes pre-existing PG
tables; it does NOT create them. SQLite remains permitted only as in-memory
test fixture (see `tests/aeis/advisor/history/_pg_test_pool.py`).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from psycopg.rows import dict_row

from sylion.aeis.advisor import _db as shared_db
from sylion.aeis.advisor.history._models import CardAction, LearningSignal

log = logging.getLogger("sylion.aeis.advisor.history._db")


def init_history_schema() -> None:
    """No-op in PG-only mode. Schema lives in Alembic migration."""
    return None


def reset_history_db() -> None:
    """No-op in PG-only mode. Test fixtures own per-test reset."""
    return None


def get_history_conn():
    """Return a pooled PG connection (context manager). Backward-compat shim."""
    return shared_db.get_pool().connection()


# ---------------------------------------------------------------------------
# Card actions
# ---------------------------------------------------------------------------


def insert_card_action(action: CardAction) -> None:
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_history.card_actions
               (action_event_id, card_id, operator_id, action, operator_note,
                modified_recommendation, context_jsonb, created_human_gate_ticket_id,
                created_masterplan_proposal_id, saved_preference_id,
                triggered_soft_learning, triggered_hard_learning_request,
                performed_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                action.action_event_id, action.card_id, action.operator_id,
                action.action, action.operator_note or None,
                action.modified_recommendation or None,
                json.dumps(action.context) if action.context else None,
                action.created_human_gate_ticket_id or None,
                action.created_masterplan_proposal_id or None,
                action.saved_preference_id or None,
                int(action.triggered_soft_learning),
                int(action.triggered_hard_learning_request),
                action.performed_at,
            ),
        )


def update_card_action_flags(
    *,
    action_event_id: str,
    triggered_soft_learning: bool | None = None,
    triggered_hard_learning_request: bool | None = None,
) -> None:
    sets: list[str] = []
    params: list[Any] = []
    if triggered_soft_learning is not None:
        sets.append("triggered_soft_learning = %s")
        params.append(int(triggered_soft_learning))
    if triggered_hard_learning_request is not None:
        sets.append("triggered_hard_learning_request = %s")
        params.append(int(triggered_hard_learning_request))
    if not sets:
        return
    params.append(action_event_id)
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE advisor_history.card_actions SET {', '.join(sets)} "
            "WHERE action_event_id = %s",
            tuple(params),
        )


def fetch_actions_for_card(card_id: str) -> list[CardAction]:
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_history.card_actions WHERE card_id = %s "
            "ORDER BY performed_at ASC",
            (card_id,),
        )
        return [_row_to_action(r) for r in cur.fetchall()]


def fetch_actions_for_operator(operator_id: str, limit: int = 100) -> list[CardAction]:
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_history.card_actions WHERE operator_id = %s "
            "ORDER BY performed_at DESC LIMIT %s",
            (operator_id, limit),
        )
        return [_row_to_action(r) for r in cur.fetchall()]


def fetch_recent_actions_for_operator_and_type(
    operator_id: str,
    recommendation_type: str,
    *,
    limit: int = 5,
) -> list[CardAction]:
    """Rolling window used by the soft-learning aggregator.

    Filters actions whose JSONB context contains a matching `recommendation_type`.
    Uses PG `->>` operator; the test SQLite shim falls back to LIKE-style match
    on the JSON-encoded text column.
    """
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_history.card_actions "
            "WHERE operator_id = %s "
            "AND context_jsonb LIKE %s "
            "ORDER BY performed_at DESC LIMIT %s",
            (operator_id, f'%"recommendation_type": "{recommendation_type}"%', limit),
        )
        return [_row_to_action(r) for r in cur.fetchall()]


def count_actions_by_status(
    operator_id: str,
    recommendation_type: str,
) -> tuple[int, int]:
    """Return (accepted, rejected) lifetime counts for `recommendation_type`."""
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT action, COUNT(*) AS c FROM advisor_history.card_actions "
            "WHERE operator_id = %s AND context_jsonb LIKE %s GROUP BY action",
            (operator_id, f'%"recommendation_type": "{recommendation_type}"%'),
        )
        rows = cur.fetchall()
    accepted = 0
    rejected = 0
    for r in rows:
        if r["action"] == "accept":
            accepted = int(r["c"])
        elif r["action"] == "reject":
            rejected = int(r["c"])
    return accepted, rejected


def count_similar_actions(
    operator_id: str,
    recommendation_type: str,
    project_type: str | None,
    project_domain: str | None,
) -> tuple[int, int]:
    """Lifetime counts for similar past cards in the same context."""
    clauses = ["operator_id = %s", "context_jsonb LIKE %s"]
    params: list[Any] = [operator_id, f'%"recommendation_type": "{recommendation_type}"%']
    if project_type:
        clauses.append("context_jsonb LIKE %s")
        params.append(f'%"project_type": "{project_type}"%')
    if project_domain:
        clauses.append("context_jsonb LIKE %s")
        params.append(f'%"project_domain": "{project_domain}"%')
    where = " AND ".join(clauses)
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT action, COUNT(*) AS c FROM advisor_history.card_actions "
            f"WHERE {where} GROUP BY action",
            tuple(params),
        )
        rows = cur.fetchall()
    accepted = 0
    rejected = 0
    for r in rows:
        if r["action"] == "accept":
            accepted = int(r["c"])
        elif r["action"] == "reject":
            rejected = int(r["c"])
    return accepted, rejected


# ---------------------------------------------------------------------------
# Learning signals
# ---------------------------------------------------------------------------


def insert_learning_signal(signal: LearningSignal) -> None:
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_history.learning_signals
               (signal_id, operator_id, signal_type, preference_key,
                context_project_type, context_project_domain, signal_strength,
                source_card_id, source_action_event_id, applied_to_preference,
                applied_at, created_at, hard_change_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                signal.signal_id, signal.operator_id, signal.signal_type,
                signal.preference_key or None,
                signal.context_project_type or None,
                signal.context_project_domain or None,
                float(signal.signal_strength),
                signal.source_card_id or None,
                signal.source_action_event_id or None,
                int(signal.applied_to_preference),
                signal.applied_at,
                signal.created_at,
                signal.hard_change_status or "",
            ),
        )


def fetch_learning_signals(
    operator_id: str,
    *,
    only_unapplied: bool = False,
) -> list[LearningSignal]:
    sql = "SELECT * FROM advisor_history.learning_signals WHERE operator_id = %s"
    params: tuple[Any, ...] = (operator_id,)
    if only_unapplied:
        sql += " AND applied_to_preference = 0"
    sql += " ORDER BY created_at DESC"
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return [_row_to_signal(r) for r in cur.fetchall()]


def fetch_pending_hard_change_signals(operator_id: str) -> list[LearningSignal]:
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_history.learning_signals "
            "WHERE operator_id = %s AND hard_change_status = 'pending' "
            "ORDER BY created_at DESC",
            (operator_id,),
        )
        return [_row_to_signal(r) for r in cur.fetchall()]


def fetch_signal_by_id(signal_id: str) -> LearningSignal | None:
    with shared_db.get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM advisor_history.learning_signals WHERE signal_id = %s",
            (signal_id,),
        )
        row = cur.fetchone()
    return _row_to_signal(row) if row else None


def update_signal_applied(signal_id: str, *, applied_at: float | None = None) -> None:
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE advisor_history.learning_signals "
            "SET applied_to_preference = 1, applied_at = %s WHERE signal_id = %s",
            (applied_at if applied_at is not None else time.time(), signal_id),
        )


def update_signal_hard_status(signal_id: str, status: str) -> None:
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE advisor_history.learning_signals "
            "SET hard_change_status = %s WHERE signal_id = %s",
            (status, signal_id),
        )


# ---------------------------------------------------------------------------
# Card emissions snapshot (lightweight metadata only — for trend analysis)
# ---------------------------------------------------------------------------


def insert_card_emission(
    *,
    card_id: str,
    operator_id: str,
    recommendation_type: str,
    project_type: str,
    project_domain: str,
    risk_level: str,
    emitted_at: float,
) -> None:
    with shared_db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_history.card_emissions
               (card_id, operator_id, recommendation_type, project_type,
                project_domain, risk_level, emitted_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (card_id) DO UPDATE SET
                 operator_id = EXCLUDED.operator_id,
                 recommendation_type = EXCLUDED.recommendation_type,
                 project_type = EXCLUDED.project_type,
                 project_domain = EXCLUDED.project_domain,
                 risk_level = EXCLUDED.risk_level,
                 emitted_at = EXCLUDED.emitted_at""",
            (
                card_id, operator_id, recommendation_type or None,
                project_type or None, project_domain or None, risk_level or None,
                emitted_at,
            ),
        )


# ---------------------------------------------------------------------------
# Row decoders
# ---------------------------------------------------------------------------


def _row_to_action(row: dict[str, Any]) -> CardAction:
    ctx_raw = row["context_jsonb"]
    if ctx_raw is None:
        ctx: dict[str, Any] = {}
    elif isinstance(ctx_raw, str):
        ctx = json.loads(ctx_raw)
    else:
        ctx = ctx_raw
    return CardAction(
        action_event_id=row["action_event_id"],
        card_id=row["card_id"],
        operator_id=row["operator_id"],
        action=row["action"],
        operator_note=row["operator_note"] or "",
        modified_recommendation=row["modified_recommendation"] or "",
        context=ctx,
        created_human_gate_ticket_id=row["created_human_gate_ticket_id"] or "",
        created_masterplan_proposal_id=row["created_masterplan_proposal_id"] or "",
        saved_preference_id=row["saved_preference_id"] or "",
        triggered_soft_learning=bool(row["triggered_soft_learning"]),
        triggered_hard_learning_request=bool(row["triggered_hard_learning_request"]),
        performed_at=float(row["performed_at"]),
    )


def _row_to_signal(row: dict[str, Any]) -> LearningSignal:
    return LearningSignal(
        signal_id=row["signal_id"],
        operator_id=row["operator_id"],
        signal_type=row["signal_type"],
        preference_key=row["preference_key"] or "",
        context_project_type=row["context_project_type"] or "",
        context_project_domain=row["context_project_domain"] or "",
        signal_strength=float(row["signal_strength"]),
        source_card_id=row["source_card_id"] or "",
        source_action_event_id=row["source_action_event_id"] or "",
        applied_to_preference=bool(row["applied_to_preference"]),
        applied_at=float(row["applied_at"]) if row["applied_at"] is not None else None,
        created_at=float(row["created_at"]),
        hard_change_status=row["hard_change_status"] or "",
    )
