"""
SYLION Surface -- Command Bus

Intent lifecycle with TWO_PHASE default. Apply orchestration.
Thread-safe. SQLite-backed. Emits events via EventBus.

Frozen decisions:
- TWO_PHASE default, NOT immediate
- Full event sourcing, NOT just audit log
- Event store is append-only
- Policy: IMMEDIATE only when explicitly allowed AND D0-D1
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.surface.command_bus")


@dataclass
class Intent:
    intent_id: str = ""
    intent_type: str = "SUBMIT"
    target_module: str = ""
    target_action: str = ""
    payload: dict = field(default_factory=dict)
    expected_version: int = 0
    status: str = "PENDING"
    phase: str = "TWO_PHASE"
    created_by: str = ""
    created_at: float = 0.0
    resolved_by: str = ""
    resolved_at: float = 0.0
    rejection_reason: str = ""

    def __post_init__(self):
        if not self.intent_id:
            self.intent_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


class CommandBus:
    """Intent lifecycle manager. TWO_PHASE by default.

    Thread-safe. SQLite-backed. Emits events to EventBus.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()
        # Handler registry for typed action dispatch (W14 E2 Testing).
        # Keyed by (target_module, target_action) -> handler instance with
        # validate(payload) / execute(payload, intent_id) methods.
        self._handlers: dict[tuple[str, str], object] = {}

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS intents (
                intent_id       TEXT PRIMARY KEY,
                intent_type     TEXT NOT NULL DEFAULT 'SUBMIT',
                target_module   TEXT NOT NULL DEFAULT '',
                target_action   TEXT NOT NULL DEFAULT '',
                payload         TEXT NOT NULL DEFAULT '{}',
                expected_version INTEGER NOT NULL DEFAULT 0,
                status          TEXT NOT NULL DEFAULT 'PENDING',
                phase           TEXT NOT NULL DEFAULT 'TWO_PHASE',
                created_by      TEXT NOT NULL DEFAULT '',
                created_at      REAL NOT NULL,
                resolved_by     TEXT NOT NULL DEFAULT '',
                resolved_at     REAL NOT NULL DEFAULT 0,
                rejection_reason TEXT NOT NULL DEFAULT ''
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS intent_events (
                event_id    TEXT PRIMARY KEY,
                intent_id   TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                timestamp   REAL NOT NULL,
                metadata    TEXT NOT NULL DEFAULT '{}'
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_intent_mod ON intents(target_module)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_intent_status ON intents(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ie_intent ON intent_events(intent_id)"
        )
        self._conn.commit()

    def _append_event(self, intent_id: str, event_type: str, metadata: dict = None):
        self._conn.execute("""
            INSERT INTO intent_events (event_id, intent_id, event_type, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (uuid.uuid4().hex, intent_id, event_type, time.time(),
              json.dumps(metadata or {})))
        self._conn.commit()

    def submit_intent(self, intent_type: str = "SUBMIT",
                      target_module: str = "",
                      target_action: str = "",
                      payload: dict | None = None,
                      created_by: str = "",
                      expected_version: int = 0,
                      phase: str = "TWO_PHASE") -> dict:
        """Submit a new intent. TWO_PHASE by default."""
        intent = Intent(
            intent_type=intent_type,
            target_module=target_module,
            target_action=target_action,
            payload=payload or {},
            expected_version=expected_version,
            status="PENDING",
            phase=phase,
            created_by=created_by,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO intents
                    (intent_id, intent_type, target_module, target_action,
                     payload, expected_version, status, phase,
                     created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                intent.intent_id, intent.intent_type,
                intent.target_module, intent.target_action,
                json.dumps(intent.payload), intent.expected_version,
                intent.status, intent.phase,
                intent.created_by, intent.created_at,
            ))
            self._conn.commit()
            self._append_event(intent.intent_id, "INTENT_SUBMITTED", {
                "phase": phase, "target": target_module,
            })

        self._emit("surface.command_bus.intent_submitted", {
            "intent_id": intent.intent_id,
            "target_module": target_module,
            "phase": phase,
        })

        log.info("submitted intent %s: %s/%s (%s)",
                 intent.intent_id[:12], target_module, target_action, phase)
        return {
            "intent_id": intent.intent_id,
            "status": intent.status,
            "phase": intent.phase,
        }

    def approve_intent(self, intent_id: str, approver: str = "") -> dict:
        """Approve and apply a pending intent."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM intents WHERE intent_id = ?", (intent_id,),
            ).fetchone()
            if not row:
                return {"error": "intent not found", "intent_id": intent_id}
            if dict(row)["status"] != "PENDING":
                return {"error": "intent not pending", "status": dict(row)["status"]}

            now = time.time()
            self._conn.execute("""
                UPDATE intents SET status = 'APPLIED', resolved_by = ?, resolved_at = ?
                WHERE intent_id = ?
            """, (approver, now, intent_id))
            self._conn.commit()
            self._append_event(intent_id, "INTENT_APPROVED", {"approver": approver})

        self._emit("surface.command_bus.intent_approved", {
            "intent_id": intent_id, "approver": approver,
        })

        log.info("approved intent %s by %s", intent_id[:12], approver)
        return {"intent_id": intent_id, "status": "APPLIED"}

    def reject_intent(self, intent_id: str, reason: str = "",
                      rejector: str = "") -> dict:
        """Reject a pending intent."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM intents WHERE intent_id = ?", (intent_id,),
            ).fetchone()
            if not row:
                return {"error": "intent not found", "intent_id": intent_id}
            if dict(row)["status"] != "PENDING":
                return {"error": "intent not pending", "status": dict(row)["status"]}

            now = time.time()
            self._conn.execute("""
                UPDATE intents SET status = 'REJECTED', resolved_by = ?,
                                   resolved_at = ?, rejection_reason = ?
                WHERE intent_id = ?
            """, (rejector, now, reason, intent_id))
            self._conn.commit()
            self._append_event(intent_id, "INTENT_REJECTED", {
                "rejector": rejector, "reason": reason,
            })

        self._emit("surface.command_bus.intent_rejected", {
            "intent_id": intent_id, "rejector": rejector,
        })

        log.info("rejected intent %s by %s: %s", intent_id[:12], rejector, reason)
        return {"intent_id": intent_id, "status": "REJECTED"}

    def get_intent(self, intent_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM intents WHERE intent_id = ?", (intent_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.get("payload", "{}"))
        return result

    def list_intents(self, status: str | None = None,
                     limit: int = 100) -> list[dict]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM intents WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM intents ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d.get("payload", "{}"))
            results.append(d)
        return results

    def get_pending_for_module(self, target_module: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM intents WHERE target_module = ? AND status = 'PENDING' ORDER BY created_at",
            (target_module,),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d.get("payload", "{}"))
            results.append(d)
        return results

    def get_stats(self) -> dict:
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM intents"
        ).fetchone()["cnt"]

        by_status_rows = self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM intents GROUP BY status"
        ).fetchall()
        by_status = {r["status"]: r["cnt"] for r in by_status_rows}

        by_phase_rows = self._conn.execute(
            "SELECT phase, COUNT(*) as cnt FROM intents GROUP BY phase"
        ).fetchall()
        by_phase = {r["phase"]: r["cnt"] for r in by_phase_rows}

        return {
            "total_intents": total,
            "by_status": by_status,
            "by_phase": by_phase,
        }

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="surface.command_bus",
            ))

    # ------------------------------------------------------------------
    # Handler registry (W14 E2 Testing)
    #
    # Append-only addition to CommandBus: lets domain modules register
    # typed handlers under (target_module, target_action). Existing intent
    # APIs (submit_intent / approve_intent / reject_intent) are unchanged;
    # downstream callers may look up the handler via lookup_handler() and
    # invoke handler.validate / handler.execute themselves. Real dispatch
    # routing inside CommandBus comes in E3 once the full intent flow is
    # wired through the surface layer.
    # ------------------------------------------------------------------

    def register_handler(self, handler: object,
                         target_module: str = "testing") -> None:
        """Register a typed action handler under (target_module, target_action).

        ``handler`` must expose ``target_action: str``, ``validate(payload)``
        and ``execute(payload, intent_id)``. Re-registration is rejected so
        startup order issues surface loudly rather than silently dropping a
        handler.
        """
        action = getattr(handler, "target_action", None)
        if not isinstance(action, str) or not action:
            raise ValueError(
                "register_handler: handler must expose non-empty target_action"
            )
        if not callable(getattr(handler, "validate", None)):
            raise ValueError(
                f"register_handler: {action} missing validate(payload) method"
            )
        if not callable(getattr(handler, "execute", None)):
            raise ValueError(
                f"register_handler: {action} missing execute(payload, intent_id)"
            )
        key = (target_module, action)
        with self._lock:
            if key in self._handlers:
                raise RuntimeError(
                    f"register_handler: duplicate ({target_module}, {action})"
                )
            self._handlers[key] = handler

    def lookup_handler(self, target_module: str, target_action: str):
        """Return the registered handler for (target_module, target_action), or None."""
        return self._handlers.get((target_module, target_action))

    def list_handlers(self, target_module: str | None = None) -> list[dict]:
        """List registered handlers (debug / introspection)."""
        rows: list[dict] = []
        for (mod, act), h in self._handlers.items():
            if target_module is not None and mod != target_module:
                continue
            rows.append({
                "target_module": mod,
                "target_action": act,
                "handler_class": type(h).__name__,
                "d_level": getattr(getattr(h, "d_level", None), "value", None),
                "phase": getattr(h, "phase", None),
                "mirror_to_ticket": getattr(h, "mirror_to_ticket", False),
            })
        return rows


_bus: CommandBus | None = None


def get_command_bus(db_path: str | Path | None = None,
                    event_bus: EventBus | None = None) -> CommandBus:
    global _bus
    if _bus is None:
        _bus = CommandBus(db_path, event_bus)
    return _bus
