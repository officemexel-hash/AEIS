"""W17 cost-ledger — event-sourced cost tracking per ADR-001 Decision #3.

Architectural decision (ADR-001 #3): the cost-ledger is event-sourced.
Every LLM call (or routing decision in Phase 0) emits a ``cost.recorded``
event to the in-process event_bus. The event stream is the source of
truth — immutable, append-only, and (in G2) hash-chained for
tamper-evidence.

Phase 0 of THIS module:
    - Synchronous emit of ``CostRecord`` to ``logs/v2/cost_ledger.jsonl``
      (durable, always written — operator can grep raw lines on disk).
    - Best-effort fan-out to ``sylion.core.event_bus`` (subscribers can
      pick the events up live; failure is non-fatal).
    - Stream-from-JSONL query helpers for `/recent` and `/aggregate`
      REST routes so Phase 0 has a working operator UI before the PG
      layer lands.

G2 will add the PostgreSQL materialized view ``mv_cost_ledger``:
    - A subscriber on the event bus persists each ``cost.recorded`` to
      the ``sylion_v2.cost_event`` append-only PG table.
    - ``mv_cost_ledger`` aggregates per (model, host, hour-bucket) for
      fast operator dashboard queries; it refreshes every N seconds via
      ``REFRESH MATERIALIZED VIEW CONCURRENTLY``.
    - The JSONL file remains as the disaster-recovery fallback when PG
      is unreachable — same code path, audit-trail parity.

Mirrors the W15 ``_emit_apply_audit`` pattern (JSONL + event-bus) so the
two audit surfaces stay structurally consistent for the operator console.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# parents[3] resolves: cost_ledger.py -> deployment -> aeis_v2 -> sylion -> sylion-pipeline/
COST_AUDIT_LOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "cost_ledger.jsonl"
)


@dataclass
class CostRecord:
    """One cost row emitted per LLM-call (or per routing decision in Phase 0).

    Field semantics:

    - ``ts`` — epoch seconds when the cost was attributed. Phase 0 uses
      decision-finalization time; G2 will switch to the actual
      adapter-call wallclock (post-completion) so reconciliation is
      precise.
    - ``session_id`` — bind to ``TerminalSession.session_id`` when the
      caller has one (e.g. operator chat). Empty string when the cost
      is not session-attributable (smoke test, background sweep).
    - ``decision_id`` — bind to ``RoutingDecision.decision_id`` (W17
      P1-5). Lets the audit trail correlate "cost row → routing audit
      row" by the same uuid.
    - ``host`` — ``Node.node_id`` where the call landed (or "" when no
      node was chosen, e.g. all candidates rejected).
    - ``model`` — model_id that was actually used (after fallback, if
      any).
    - ``tokens_in`` / ``tokens_out`` — Phase 0 records 0/0 because the
      adapter call hasn't happened yet at decision time. G2 will
      reconcile via a follow-up "cost.refined" event keyed on
      ``decision_id``.
    - ``cost_usd`` — Phase 0 records 0.0 (placeholder) since tokens are
      0; the cost-per-1k is captured separately on the routing audit
      row. G2 reconciles ``cost_usd = (tokens_in + tokens_out) / 1000 *
      cost_per_1k`` after adapter completion.
    """

    ts: float
    session_id: str
    decision_id: str
    host: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly dump.

        Field order is stable so JSONL grep + sort lines deterministically.
        """
        return {
            "ts": self.ts,
            "session_id": self.session_id,
            "decision_id": self.decision_id,
            "host": self.host,
            "model": self.model,
            "tokens_in": int(self.tokens_in),
            "tokens_out": int(self.tokens_out),
            "cost_usd": float(self.cost_usd),
            "metadata": dict(self.metadata),
        }


def emit_cost_record(record: CostRecord) -> None:
    """Emit a cost event — best-effort to event_bus, always to JSONL.

    Mirrors ``_emit_apply_audit`` from ``aeis_v2/ontology/applier.py``.
    The two stages are independent: a JSONL write failure is logged at
    WARNING but does NOT prevent the event-bus broadcast (a downstream
    materialized-view subscriber may still pick up the in-memory event
    even when the disk is full). Conversely, an event-bus failure is
    swallowed at DEBUG since the JSONL file is the durable record.

    Phase 0: file is the durable spine. G2 will add a PG event-table
    subscriber whose failure-recovery path replays the JSONL on
    reconnect.
    """
    payload = record.to_dict()

    # 1. JSONL append (durable — always attempted).
    # Sprint 3: migrated to chained format (commit ac97e957) so the DPO
    # can verify cost_ledger integrity end-to-end via verify_chain.
    # The chained row stamps ``kind="cost_ledger.record"`` so consumers
    # filter by content.kind.
    try:
        from sylion.aeis_v2.audit_chain import append_to_chain

        append_to_chain(
            COST_AUDIT_LOG_PATH,
            {"kind": "cost_ledger.record", **payload},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("cost_ledger: jsonl write failed (%s)", exc)

    # 2. Event-bus broadcast (best-effort).
    try:
        from sylion.core.event_bus import get_event_bus
        bus = get_event_bus()
        if hasattr(bus, "publish"):
            bus.publish("aeis.v2.cost.recorded", payload)
    except Exception as exc:  # noqa: BLE001
        log.debug("cost_ledger: event bus emit failed (%s)", exc)


# --------------------------------------------------------------------------
# Phase 0 query API — JSONL streaming.
# --------------------------------------------------------------------------
#
# G2 will introduce ``query_cost_pg(...)`` backed by ``mv_cost_ledger``;
# the operator UI will switch endpoints transparently. We keep the JSONL
# path forever as the disaster-recovery fallback when PG is offline.


def _iter_jsonl_records() -> "list[CostRecord]":
    """Read the JSONL file line by line, yielding ``CostRecord`` instances.

    Returns an empty list when the file does not exist (fresh deployment
    that has never emitted a cost event). Malformed lines are skipped
    with a WARNING — a single bad row from a partial write must not
    poison the whole query.
    """
    out: list[CostRecord] = []
    if not COST_AUDIT_LOG_PATH.exists():
        return out
    try:
        with open(COST_AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    log.warning(
                        "cost_ledger: malformed JSONL line %d skipped (%s)",
                        lineno, exc,
                    )
                    continue
                # Sprint 3 chained-format support: rows are
                # ``{"prev_hash": ..., "content": {...}, "content_hash": ...}``.
                # Pre-migration (legacy) rows are flat dicts. Detect both.
                if (
                    isinstance(raw, dict)
                    and "content" in raw
                    and isinstance(raw.get("content"), dict)
                    and "content_hash" in raw
                ):
                    row = raw["content"]
                    # Filter by kind — skip non-cost-record rows on the
                    # same chain (defensive; today the chain is dedicated
                    # but future tools may share it).
                    if row.get("kind") not in (None, "cost_ledger.record"):
                        continue
                else:
                    row = raw
                try:
                    out.append(CostRecord(
                        ts=float(row.get("ts", 0.0)),
                        session_id=str(row.get("session_id", "")),
                        decision_id=str(row.get("decision_id", "")),
                        host=str(row.get("host", "")),
                        model=str(row.get("model", "")),
                        tokens_in=int(row.get("tokens_in", 0)),
                        tokens_out=int(row.get("tokens_out", 0)),
                        cost_usd=float(row.get("cost_usd", 0.0)),
                        metadata=dict(row.get("metadata", {}) or {}),
                    ))
                except (TypeError, ValueError) as exc:
                    log.warning(
                        "cost_ledger: row %d failed coercion (%s)", lineno, exc,
                    )
                    continue
    except Exception as exc:  # noqa: BLE001
        log.warning("cost_ledger: jsonl read failed (%s)", exc)
    return out


def query_cost_jsonl(
    since_ts: float = 0.0,
    until_ts: float | None = None,
    *,
    session_id: str | None = None,
    model: str | None = None,
    host: str | None = None,
    limit: int | None = None,
) -> list[CostRecord]:
    """Stream cost records from JSONL with optional filters.

    Phase 0 query API. G2 replaces with PG materialized-view query but
    keeps this signature for the operator UI.

    Args:
        since_ts: epoch seconds lower bound (inclusive). Default 0.0
            returns all rows ever recorded.
        until_ts: epoch seconds upper bound (inclusive). ``None`` means
            no upper bound (unbounded).
        session_id: exact match filter; ``None`` = no filter.
        model: exact match filter; ``None`` = no filter.
        host: exact match filter on node_id; ``None`` = no filter.
        limit: cap returned record count to the ``limit`` MOST RECENT
            entries (newest-first, then re-sorted oldest-first in the
            response). ``None`` = no cap.

    Returns:
        List of ``CostRecord`` sorted ascending by ``ts``.
    """
    rows = _iter_jsonl_records()
    out: list[CostRecord] = []
    for r in rows:
        if r.ts < since_ts:
            continue
        if until_ts is not None and r.ts > until_ts:
            continue
        if session_id is not None and r.session_id != session_id:
            continue
        if model is not None and r.model != model:
            continue
        if host is not None and r.host != host:
            continue
        out.append(r)
    out.sort(key=lambda r: r.ts)
    if limit is not None and limit >= 0 and len(out) > limit:
        # Take the LAST ``limit`` rows (most recent) when capping.
        out = out[-limit:]
    return out


_VALID_GROUP_BY = {"model", "host", "session_id"}


def aggregate_cost_by(
    since_ts: float = 0.0,
    until_ts: float | None = None,
    *,
    group_by: str = "model",
) -> dict[str, dict[str, float]]:
    """Aggregate cost rows by a single dimension.

    Args:
        since_ts / until_ts: time window (see ``query_cost_jsonl``).
        group_by: one of ``"model"``, ``"host"``, ``"session_id"``.

    Returns:
        ``{group_value: {"total_usd", "total_tokens_in", "total_tokens_out",
        "call_count"}}`` keyed on the group dimension. Empty dict when no
        rows match the filter.

    Raises:
        ValueError: when ``group_by`` is not in the allowed set.
    """
    if group_by not in _VALID_GROUP_BY:
        raise ValueError(
            f"group_by must be one of {sorted(_VALID_GROUP_BY)}, got {group_by!r}"
        )

    rows = query_cost_jsonl(since_ts=since_ts, until_ts=until_ts)
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        key = getattr(r, group_by, "") or ""
        bucket = out.setdefault(
            key,
            {
                "total_usd": 0.0,
                "total_tokens_in": 0.0,
                "total_tokens_out": 0.0,
                "call_count": 0.0,
            },
        )
        bucket["total_usd"] += float(r.cost_usd)
        bucket["total_tokens_in"] += float(r.tokens_in)
        bucket["total_tokens_out"] += float(r.tokens_out)
        bucket["call_count"] += 1.0
    return out


def _now() -> float:
    """Indirection so tests can ``monkeypatch`` time without touching ``time``."""
    return time.time()
