"""
SYLION AEIS -- Integration Controller

Manages external system integrations with health monitoring and event tracking.
Each integration records events, health checks, and configuration.

Tables:
  integrations, integration_events, integration_health

Singleton: get_integration_controller() / reset_integration_controller()
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

log = logging.getLogger("sylion.aeis.integration_controller")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_INTEGRATION_TYPES = (
    "api", "webhook", "database", "messaging", "storage", "llm_provider",
    "monitoring", "auth_provider", "custom",
)

VALID_HEALTH_STATUSES = ("healthy", "degraded", "unhealthy", "unknown")


# ---------------------------------------------------------------------------
# IntegrationController
# ---------------------------------------------------------------------------

class IntegrationController:
    """External integration management with health monitoring.

    Thread-safe. SQLite-backed. Emits events on mutations.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS integrations (
                integration_id    TEXT PRIMARY KEY,
                name              TEXT NOT NULL,
                integration_type  TEXT NOT NULL DEFAULT 'custom',
                config            TEXT NOT NULL DEFAULT '{}',
                status            TEXT NOT NULL DEFAULT 'active',
                created_at        REAL NOT NULL,
                updated_at        REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS integration_events (
                event_id         TEXT PRIMARY KEY,
                integration_id   TEXT NOT NULL,
                event_type       TEXT NOT NULL DEFAULT '',
                payload          TEXT NOT NULL DEFAULT '{}',
                recorded_at      REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS integration_health (
                health_id        TEXT PRIMARY KEY,
                integration_id   TEXT NOT NULL,
                status           TEXT NOT NULL DEFAULT 'unknown',
                details          TEXT NOT NULL DEFAULT '',
                checked_at       REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS integration_stages (
                stage_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                stage         TEXT NOT NULL,
                from_stage    TEXT NOT NULL DEFAULT '',
                actor         TEXT NOT NULL DEFAULT '',
                reason        TEXT NOT NULL DEFAULT '',
                entered_at    REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_int_type ON integrations(integration_type);
            CREATE INDEX IF NOT EXISTS idx_int_status ON integrations(status);
            CREATE INDEX IF NOT EXISTS idx_ie_int ON integration_events(integration_id);
            CREATE INDEX IF NOT EXISTS idx_ie_type ON integration_events(event_type);
            CREATE INDEX IF NOT EXISTS idx_ih_int ON integration_health(integration_id);
            CREATE INDEX IF NOT EXISTS idx_ih_checked ON integration_health(checked_at);
            CREATE INDEX IF NOT EXISTS idx_stage_at ON integration_stages(entered_at);
        """)
        # Seed initial stage if none exists
        existing = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM integration_stages"
        ).fetchone()
        if existing and existing["cnt"] == 0:
            self._conn.execute(
                "INSERT INTO integration_stages (stage, from_stage, actor, "
                "reason, entered_at) VALUES ('observe', '', 'system', "
                "'initial seed', ?)", (time.time(),),
            )
        self._conn.commit()

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.integration_controller",
            ))

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_integration_type(integration_type: str):
        if integration_type not in VALID_INTEGRATION_TYPES:
            raise ValueError(
                f"Invalid integration_type '{integration_type}'. "
                f"Must be one of {VALID_INTEGRATION_TYPES}"
            )

    @staticmethod
    def _validate_health_status(status: str):
        if status not in VALID_HEALTH_STATUSES:
            raise ValueError(
                f"Invalid health status '{status}'. "
                f"Must be one of {VALID_HEALTH_STATUSES}"
            )

    # ------------------------------------------------------------------
    # Integration CRUD
    # ------------------------------------------------------------------

    def register_integration(self, name: str, integration_type: str = "custom",
                             config: dict | None = None) -> dict:
        """Register a new integration. Returns integration dict."""
        if not name:
            raise ValueError("name must not be empty")
        self._validate_integration_type(integration_type)

        integration_id = self._uid()
        now = time.time()
        config_json = json.dumps(config or {})

        with self._lock:
            self._conn.execute(
                "INSERT INTO integrations "
                "(integration_id, name, integration_type, config, "
                "status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'active', ?, ?)",
                (integration_id, name, integration_type, config_json, now, now),
            )
            self._conn.commit()

        self._emit("integration_registered", {
            "integration_id": integration_id,
            "name": name,
            "integration_type": integration_type,
        })
        log.info("register_integration %s: %s (%s)",
                 integration_id[:12], name, integration_type)
        return self.get_integration(integration_id)

    def update_integration(self, integration_id: str, name: str | None = None,
                           integration_type: str | None = None,
                           config: dict | None = None) -> dict | None:
        """Update an integration. Returns updated dict or None."""
        sets: list[str] = []
        params: list[Any] = []

        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if integration_type is not None:
            self._validate_integration_type(integration_type)
            sets.append("integration_type = ?")
            params.append(integration_type)
        if config is not None:
            sets.append("config = ?")
            params.append(json.dumps(config))

        if not sets:
            return self.get_integration(integration_id)

        now = time.time()
        sets.append("updated_at = ?")
        params.append(now)
        params.append(integration_id)

        with self._lock:
            n = self._conn.execute(
                f"UPDATE integrations SET {', '.join(sets)} "
                f"WHERE integration_id = ?",
                params,
            ).rowcount
            self._conn.commit()
            if not n:
                return None

        return self.get_integration(integration_id)

    def deregister_integration(self, integration_id: str) -> bool:
        """Deregister an integration and its events/health records."""
        with self._lock:
            row = self._conn.execute(
                "SELECT integration_id FROM integrations WHERE integration_id = ?",
                (integration_id,),
            ).fetchone()
            if not row:
                return False

            self._conn.execute(
                "DELETE FROM integration_events WHERE integration_id = ?",
                (integration_id,),
            )
            self._conn.execute(
                "DELETE FROM integration_health WHERE integration_id = ?",
                (integration_id,),
            )
            self._conn.execute(
                "DELETE FROM integrations WHERE integration_id = ?",
                (integration_id,),
            )
            self._conn.commit()
        log.info("deregister_integration %s", integration_id[:12])
        return True

    def get_integration(self, integration_id: str) -> dict | None:
        """Retrieve a single integration by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM integrations WHERE integration_id = ?",
                (integration_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["config"] = json.loads(d.get("config", "{}"))
        return d

    def list_integrations(self, integration_type: str | None = None,
                          limit: int = 100) -> list[dict]:
        """List integrations with optional type filter."""
        with self._lock:
            clauses: list[str] = []
            params: list[Any] = []

            if integration_type is not None:
                self._validate_integration_type(integration_type)
                clauses.append("integration_type = ?")
                params.append(integration_type)

            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = self._conn.execute(
                f"SELECT * FROM integrations{where} "
                f"ORDER BY created_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["config"] = json.loads(d.get("config", "{}"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def record_event(self, integration_id: str, event_type: str,
                     payload: dict | None = None) -> dict | None:
        """Record an integration event. Returns event dict or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT integration_id FROM integrations WHERE integration_id = ?",
                (integration_id,),
            ).fetchone()
            if not row:
                return None

        event_id = self._uid()
        now = time.time()
        payload_json = json.dumps(payload or {})

        with self._lock:
            self._conn.execute(
                "INSERT INTO integration_events "
                "(event_id, integration_id, event_type, payload, recorded_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (event_id, integration_id, event_type, payload_json, now),
            )
            self._conn.commit()

        self._emit("integration_event", {
            "event_id": event_id,
            "integration_id": integration_id,
            "event_type": event_type,
        })
        log.info("record_event %s for %s: %s",
                 event_id[:12], integration_id[:12], event_type)
        return {
            "event_id": event_id,
            "integration_id": integration_id,
            "event_type": event_type,
            "recorded_at": now,
        }

    def get_events(self, integration_id: str,
                   limit: int = 50) -> list[dict]:
        """Get events for an integration."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM integration_events "
                "WHERE integration_id = ? ORDER BY recorded_at DESC LIMIT ?",
                (integration_id, limit),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d.get("payload", "{}"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def check_health(self, integration_id: str,
                     status: str = "healthy",
                     details: str = "") -> dict | None:
        """Record a health check for an integration."""
        self._validate_health_status(status)

        with self._lock:
            row = self._conn.execute(
                "SELECT integration_id FROM integrations WHERE integration_id = ?",
                (integration_id,),
            ).fetchone()
            if not row:
                return None

        health_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute(
                "INSERT INTO integration_health "
                "(health_id, integration_id, status, details, checked_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (health_id, integration_id, status, details, now),
            )
            self._conn.commit()

        if status == "unhealthy":
            self._emit("integration_unhealthy", {
                "integration_id": integration_id,
                "status": status,
                "details": details,
            })

        return {
            "health_id": health_id,
            "integration_id": integration_id,
            "status": status,
            "details": details,
            "checked_at": now,
        }

    def get_health_history(self, integration_id: str,
                           limit: int = 50) -> list[dict]:
        """Get health check history for an integration."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM integration_health "
                "WHERE integration_id = ? ORDER BY checked_at DESC LIMIT ?",
                (integration_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_integration_stats(self) -> dict:
        """Aggregate integration statistics."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM integrations",
            ).fetchone()["cnt"]

            type_rows = self._conn.execute(
                "SELECT integration_type, COUNT(*) as cnt "
                "FROM integrations GROUP BY integration_type",
            ).fetchall()
            by_type = {r["integration_type"]: r["cnt"] for r in type_rows}

            total_events = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM integration_events",
            ).fetchone()["cnt"]

            # Latest health per integration
            health_rows = self._conn.execute(
                "SELECT ih.integration_id, ih.status "
                "FROM integration_health ih "
                "INNER JOIN ("
                "  SELECT integration_id, MAX(checked_at) as max_ts "
                "  FROM integration_health GROUP BY integration_id"
                ") latest ON ih.integration_id = latest.integration_id "
                "AND ih.checked_at = latest.max_ts",
            ).fetchall()
            health_summary = {r["integration_id"]: r["status"] for r in health_rows}

            unhealthy_count = sum(
                1 for s in health_summary.values() if s == "unhealthy"
            )

        return {
            "total": total,
            "by_type": by_type,
            "total_events": total_events,
            "health_summary": health_summary,
            "unhealthy_count": unhealthy_count,
        }

    # Alias kept for ``sylion.api.aeis_routes.integration_stats`` which calls
    # ``ctrl.get_stats()``.
    def get_stats(self) -> dict:
        return self.get_integration_stats()

    # ------------------------------------------------------------------
    # Staged rollout state machine — used by /api/v1/aeis/integration/*
    # ------------------------------------------------------------------

    STAGES = ("observe", "shadow", "partial", "full")

    def get_current_stage(self) -> dict:
        """Return the current AEIS integration stage record."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM integration_stages "
                "ORDER BY entered_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            now = time.time()
            with self._lock:
                self._conn.execute(
                    "INSERT INTO integration_stages "
                    "(stage, from_stage, actor, reason, entered_at) "
                    "VALUES ('observe', '', 'system', 'auto seed', ?)",
                    (now,),
                )
                self._conn.commit()
                row = self._conn.execute(
                    "SELECT * FROM integration_stages "
                    "ORDER BY entered_at DESC LIMIT 1"
                ).fetchone()
        return dict(row)

    def advance_stage(self, actor: str = "system",
                      reason: str = "") -> dict:
        """Advance to the next stage in the rollout sequence. If already
        at the final stage, returns the current stage unchanged.
        """
        current = self.get_current_stage()
        cur_name = current.get("stage", "observe")
        seq = list(self.STAGES)
        try:
            idx = seq.index(cur_name)
        except ValueError:
            idx = 0
        if idx >= len(seq) - 1:
            return {
                **current,
                "advanced": False,
                "message": "already at final stage",
            }
        next_name = seq[idx + 1]
        return self._enter_stage(next_name, from_stage=cur_name,
                                 actor=actor, reason=reason or "advance")

    def emergency_downgrade(self, reason: str,
                            actor: str = "system") -> dict:
        """Force the rollout back to 'observe' (most conservative stage)."""
        current = self.get_current_stage()
        cur_name = current.get("stage", "observe")
        return self._enter_stage(
            "observe", from_stage=cur_name,
            actor=actor or "system",
            reason=reason or "emergency downgrade",
        )

    def get_stage_history(self, limit: int = 100) -> list[dict]:
        """Chronological log of stage transitions (newest first)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM integration_stages "
                "ORDER BY entered_at DESC LIMIT ?", (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]

    def _enter_stage(self, stage: str, from_stage: str,
                     actor: str, reason: str) -> dict:
        if stage not in self.STAGES:
            raise ValueError(
                f"Invalid stage '{stage}'. Must be one of {self.STAGES}")
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO integration_stages "
                "(stage, from_stage, actor, reason, entered_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (stage, from_stage, actor, reason, now),
            )
            self._conn.commit()
        self._emit("aeis.integration.stage_entered", {
            "stage": stage, "from_stage": from_stage,
            "actor": actor, "reason": reason,
        })
        log.info("integration stage: %s -> %s (actor=%s reason=%s)",
                 from_stage, stage, actor, reason)
        return {
            "stage": stage, "from_stage": from_stage,
            "actor": actor, "reason": reason,
            "entered_at": now, "advanced": True,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_controller: IntegrationController | None = None


def get_integration_controller(db_path: str | Path | None = None,
                               event_bus: EventBus | None = None) -> IntegrationController:
    global _controller
    if _controller is None:
        _controller = IntegrationController(db_path, event_bus)
    return _controller


def reset_integration_controller(db_path: str | Path | None = None,
                                 event_bus: EventBus | None = None) -> IntegrationController:
    global _controller
    _controller = IntegrationController(db_path, event_bus)
    return _controller
