"""
SYLION Governance -- Decision Snapshot

Captures snapshots of decision state including context, outcome, confidence,
and contributing factors. Supports comparison between snapshots and timeline
reconstruction.

Thread-safe. SQLite-backed. EventBus integration.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.governance.decision_snapshot")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_OUTCOMES: tuple[str, ...] = (
    "approved", "rejected", "deferred", "escalated", "auto_approved",
)


# ---------------------------------------------------------------------------
# DecisionSnapshotManager
# ---------------------------------------------------------------------------

class DecisionSnapshotManager:
    """Captures and compares decision state snapshots.

    Each snapshot records a decision's context, outcome, confidence score,
    and contributing factors at a point in time. Snapshots can be compared
    to track how decisions evolve.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_snapshots (
                    snapshot_id   TEXT PRIMARY KEY,
                    decision_id   TEXT NOT NULL,
                    context_json  TEXT NOT NULL DEFAULT '{}',
                    outcome       TEXT NOT NULL,
                    confidence    REAL NOT NULL DEFAULT 0.0,
                    created_at    REAL NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS snapshot_factors (
                    factor_id    TEXT PRIMARY KEY,
                    snapshot_id  TEXT NOT NULL,
                    name         TEXT NOT NULL,
                    value        TEXT NOT NULL DEFAULT '',
                    weight       REAL NOT NULL DEFAULT 1.0
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_decision "
                "ON decision_snapshots(decision_id)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_ts "
                "ON decision_snapshots(created_at)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_factors_snapshot "
                "ON snapshot_factors(snapshot_id)"
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_snapshot(self, decision_id: str,
                        context_json: dict[str, Any] | str | None = None,
                        outcome: str = "approved",
                        confidence: float = 1.0,
                        factors_list: list[dict] | None = None) -> dict:
        """Create a new decision snapshot.

        Args:
            decision_id: The decision this snapshot belongs to.
            context_json: Context dict or JSON string.
            outcome: One of VALID_OUTCOMES.
            confidence: Confidence score 0.0-1.0.
            factors_list: List of factor dicts with name, value, weight.

        Returns:
            Dict with snapshot details.
        """
        if not decision_id or not decision_id.strip():
            raise ValueError("decision_id must not be empty.")
        if outcome not in VALID_OUTCOMES:
            raise ValueError(
                f"Invalid outcome '{outcome}'. Must be one of {VALID_OUTCOMES}."
            )
        confidence = max(0.0, min(1.0, float(confidence)))

        if context_json is None:
            context = {}
        elif isinstance(context_json, str):
            context = json.loads(context_json)
        else:
            context = context_json

        snapshot_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO decision_snapshots
                (snapshot_id, decision_id, context_json, outcome, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (snapshot_id, decision_id, json.dumps(context),
                  outcome, confidence, now))

            if factors_list:
                for factor in factors_list:
                    factor_id = uuid.uuid4().hex
                    self._conn.execute("""
                        INSERT INTO snapshot_factors
                        (factor_id, snapshot_id, name, value, weight)
                        VALUES (?, ?, ?, ?, ?)
                    """, (factor_id, snapshot_id,
                          factor.get("name", ""),
                          str(factor.get("value", "")),
                          float(factor.get("weight", 1.0))))

            self._conn.commit()

        self._emit("snapshot_created", {
            "snapshot_id": snapshot_id,
            "decision_id": decision_id,
            "outcome": outcome,
            "confidence": confidence,
        })

        log.info("created snapshot %s for decision %s (%s/%.2f)",
                 snapshot_id, decision_id, outcome, confidence)

        return {
            "snapshot_id": snapshot_id,
            "decision_id": decision_id,
            "context": context,
            "outcome": outcome,
            "confidence": confidence,
            "factors": factors_list or [],
            "created_at": now,
        }

    def get_snapshot(self, snapshot_id: str) -> dict | None:
        """Retrieve a snapshot with its factors."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM decision_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
            if not row:
                return None

            factor_rows = self._conn.execute(
                "SELECT * FROM snapshot_factors WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchall()

        return self._to_full_dict(row, factor_rows)

    def list_snapshots(self, decision_id: str | None = None,
                       decision_class: str | None = None,
                       is_active: bool | None = None,
                       limit: int = 100) -> list[dict]:
        """List snapshots with optional filters.

        ``decision_class`` and ``is_active`` are accepted for forward
        compatibility but currently filter post-hoc on the snapshot dict
        since the underlying schema doesn't store those fields.
        """
        with self._lock:
            q = "SELECT * FROM decision_snapshots WHERE 1=1"
            params: list[Any] = []
            if decision_id is not None:
                q += " AND decision_id = ?"
                params.append(decision_id)
            q += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = self._conn.execute(q, params).fetchall()

        result = []
        for row in rows:
            with self._lock:
                factor_rows = self._conn.execute(
                    "SELECT * FROM snapshot_factors WHERE snapshot_id = ?",
                    (row["snapshot_id"],),
                ).fetchall()
            result.append(self._to_full_dict(row, factor_rows))

        if decision_class is not None:
            result = [r for r in result
                      if r.get("decision_class") == decision_class]
        if is_active is not None:
            result = [r for r in result
                      if bool(r.get("is_active", True)) == is_active]
        return result

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare_snapshots(self, snapshot_id_1: str,
                          snapshot_id_2: str) -> dict | None:
        """Compare two snapshots, returning a diff.

        Returns:
            Dict with context_diff, factors_diff, outcome_changed,
            confidence_delta, or None if either snapshot is missing.
        """
        snap1 = self.get_snapshot(snapshot_id_1)
        snap2 = self.get_snapshot(snapshot_id_2)

        if snap1 is None or snap2 is None:
            return None

        # Context diff
        ctx1 = snap1.get("context", {})
        ctx2 = snap2.get("context", {})
        all_keys = set(ctx1.keys()) | set(ctx2.keys())
        context_diff = {}
        for key in sorted(all_keys):
            v1 = ctx1.get(key)
            v2 = ctx2.get(key)
            if v1 != v2:
                context_diff[key] = {"before": v1, "after": v2}

        # Factors diff
        factors1 = {f["name"]: f for f in snap1.get("factors", [])}
        factors2 = {f["name"]: f for f in snap2.get("factors", [])}
        all_factor_names = set(factors1.keys()) | set(factors2.keys())
        factors_diff = {}
        for name in sorted(all_factor_names):
            f1 = factors1.get(name)
            f2 = factors2.get(name)
            if f1 != f2:
                factors_diff[name] = {
                    "before": f1,
                    "after": f2,
                }

        outcome_changed = snap1["outcome"] != snap2["outcome"]
        confidence_delta = round(snap2["confidence"] - snap1["confidence"], 6)

        result = {
            "snapshot_1": snapshot_id_1,
            "snapshot_2": snapshot_id_2,
            "context_diff": context_diff,
            "factors_diff": factors_diff,
            "outcome_changed": outcome_changed,
            "outcome_before": snap1["outcome"],
            "outcome_after": snap2["outcome"],
            "confidence_delta": confidence_delta,
        }

        self._emit("snapshots_compared", {
            "snapshot_id_1": snapshot_id_1,
            "snapshot_id_2": snapshot_id_2,
            "outcome_changed": outcome_changed,
            "confidence_delta": confidence_delta,
            "context_changes": len(context_diff),
            "factor_changes": len(factors_diff),
        })

        return result

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------

    def get_timeline(self, decision_id: str | None = None,
                     gate_id: str | None = None,
                     session_id: str | None = None) -> list[dict]:
        """Get an ordered timeline of snapshots, filtered by any of:
        decision_id, gate_id, session_id.

        ``gate_id`` and ``session_id`` are filtered post-hoc on the
        snapshot dict since the underlying schema doesn't store them
        as first-class columns yet.
        """
        with self._lock:
            q = "SELECT * FROM decision_snapshots WHERE 1=1"
            params: list[Any] = []
            if decision_id is not None:
                q += " AND decision_id = ?"
                params.append(decision_id)
            q += " ORDER BY created_at ASC"
            rows = self._conn.execute(q, params).fetchall()

        result = []
        for row in rows:
            with self._lock:
                factor_rows = self._conn.execute(
                    "SELECT * FROM snapshot_factors WHERE snapshot_id = ?",
                    (row["snapshot_id"],),
                ).fetchall()
            result.append(self._to_full_dict(row, factor_rows))

        if gate_id is not None:
            result = [r for r in result if r.get("gate_id") == gate_id]
        if session_id is not None:
            result = [r for r in result if r.get("session_id") == session_id]
        return result

    # ------------------------------------------------------------------
    # Active chain & cascade
    # ------------------------------------------------------------------

    def get_active_chain(self) -> dict:
        """Return the active decision chain.

        The "active chain" is the sequence of most recent snapshots per
        decision_id, ordered chronologically. Useful for surfacing the
        currently-effective decisions in the dashboard.
        """
        with self._lock:
            rows = self._conn.execute("""
                SELECT decision_id, snapshot_id, outcome, confidence, created_at
                FROM decision_snapshots
                WHERE snapshot_id IN (
                    SELECT snapshot_id FROM decision_snapshots ds1
                    WHERE created_at = (
                        SELECT MAX(created_at) FROM decision_snapshots ds2
                        WHERE ds2.decision_id = ds1.decision_id
                    )
                )
                ORDER BY created_at ASC
            """).fetchall()
        chain = [dict(r) for r in rows]
        return {"chain": chain, "length": len(chain)}

    def get_cascade_impact(self, snapshot_id: str) -> dict | None:
        """Compute cascade impact tree for a snapshot.

        Returns the snapshot itself plus the chronological successors
        for the same decision_id, treated as the cascade chain.
        """
        snap = self.get_snapshot(snapshot_id)
        if snap is None:
            return None
        decision_id = snap.get("decision_id")
        with self._lock:
            rows = self._conn.execute("""
                SELECT * FROM decision_snapshots
                WHERE decision_id = ? AND created_at > ?
                ORDER BY created_at ASC
            """, (decision_id, snap.get("created_at", 0))).fetchall()
        successors = [dict(r) for r in rows]
        return {
            "snapshot_id": snapshot_id,
            "decision_id": decision_id,
            "outcome": snap.get("outcome"),
            "successors_count": len(successors),
            "successors": successors,
        }

    def diff_snapshots(self, snapshot_id_1: str,
                       snapshot_id_2: str) -> dict | None:
        """Workspace alias for ``compare_snapshots``."""
        return self.compare_snapshots(snapshot_id_1, snapshot_id_2)

    def list_cascade_events(self, requires_human: bool | None = None) -> list[dict]:
        """List cascade events.

        Cascade events are emitted when ``change_decision`` is invoked or
        when a downstream snapshot supersedes an upstream one. The
        cascade-events table is created lazily on first use.
        """
        self._ensure_cascade_tables()
        clauses: list[str] = []
        params: list[Any] = []
        if requires_human is not None:
            clauses.append("requires_human = ?")
            params.append(1 if requires_human else 0)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM cascade_events{where} "
                f"ORDER BY created_at DESC",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def acknowledge_cascade(self, event_id: str,
                            action_taken: str = "") -> dict | None:
        self._ensure_cascade_tables()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cascade_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if not row:
                return None
            self._conn.execute(
                "UPDATE cascade_events SET acknowledged_at = ?, "
                "action_taken = ? WHERE event_id = ?",
                (time.time(), action_taken, event_id),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM cascade_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        return dict(row) if row else None

    def change_decision(self, snapshot_id: str,
                        new_choice: str = "",
                        new_consequences: dict | None = None) -> dict | None:
        """Change a decision and emit a cascade event."""
        snap = self.get_snapshot(snapshot_id)
        if snap is None:
            return None
        self._ensure_cascade_tables()
        event_id = uuid.uuid4().hex
        now = time.time()
        consequences = json.dumps(new_consequences or {}, default=str)
        with self._lock:
            self._conn.execute(
                "INSERT INTO cascade_events "
                "(event_id, source_snapshot_id, decision_id, new_choice, "
                "consequences_json, requires_human, acknowledged_at, "
                "action_taken, created_at) "
                "VALUES (?, ?, ?, ?, ?, 1, 0, '', ?)",
                (event_id, snapshot_id, snap.get("decision_id", ""),
                 new_choice, consequences, now),
            )
            self._conn.commit()
        return {
            "event_id": event_id,
            "source_snapshot_id": snapshot_id,
            "decision_id": snap.get("decision_id", ""),
            "new_choice": new_choice,
            "created_at": now,
        }

    def capture_snapshot(self, decision_id: str = "",
                         gate_id: str = "",
                         session_id: str = "",
                         pipeline_run_id: str = "",
                         choice_made: str = "",
                         choice_id: str = "",
                         **kwargs: Any) -> dict:
        """Workspace alias for create_snapshot, accepting wider kwargs."""
        outcome = kwargs.get("outcome", choice_made or "approved")
        # outcomes are constrained — coerce unknown to 'approved'
        if outcome not in VALID_OUTCOMES:
            outcome = "approved"
        confidence = float(kwargs.get("confidence", 1.0))
        context = kwargs.get("context_json") or {
            "gate_id": gate_id,
            "session_id": session_id,
            "pipeline_run_id": pipeline_run_id,
            "choice_id": choice_id,
        }
        return self.create_snapshot(
            decision_id=decision_id or uuid.uuid4().hex,
            context_json=context,
            outcome=outcome,
            confidence=confidence,
            factors_list=kwargs.get("factors_list"),
        )

    def _ensure_cascade_tables(self) -> None:
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS cascade_events (
                    event_id            TEXT PRIMARY KEY,
                    source_snapshot_id  TEXT NOT NULL,
                    decision_id         TEXT NOT NULL DEFAULT '',
                    new_choice          TEXT NOT NULL DEFAULT '',
                    consequences_json   TEXT NOT NULL DEFAULT '{}',
                    requires_human      INTEGER NOT NULL DEFAULT 1,
                    acknowledged_at     REAL NOT NULL DEFAULT 0,
                    action_taken        TEXT NOT NULL DEFAULT '',
                    created_at          REAL NOT NULL
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cascade_source "
                "ON cascade_events(source_snapshot_id)"
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_full_dict(row: sqlite3.Row,
                      factor_rows: list[sqlite3.Row]) -> dict:
        d = dict(row)
        d["context"] = json.loads(d.get("context_json", "{}"))
        if "context_json" in d:
            del d["context_json"]
        d["factors"] = [
            {
                "factor_id": fr["factor_id"],
                "name": fr["name"],
                "value": fr["value"],
                "weight": fr["weight"],
            }
            for fr in factor_rows
        ]
        return d

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="governance.decision_snapshot",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: DecisionSnapshotManager | None = None


def get_decision_snapshot_manager(db_path: str | Path | None = None,
                                  event_bus: EventBus | None = None) -> DecisionSnapshotManager:
    """Return the global DecisionSnapshotManager singleton."""
    global _manager
    if _manager is None:
        _manager = DecisionSnapshotManager(db_path, event_bus)
    return _manager


def reset_decision_snapshot_manager() -> None:
    """Reset the global singleton (for testing)."""
    global _manager
    _manager = None


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------
DecisionSnapshot = DecisionSnapshotManager
get_decision_snapshot = get_decision_snapshot_manager
reset_decision_snapshot = reset_decision_snapshot_manager
