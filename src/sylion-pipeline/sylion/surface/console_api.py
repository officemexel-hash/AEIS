"""
SYLION Surface -- Console API

Endpoint registry and request tracking for the SYLION console.
Manages API endpoint definitions, auth/RBAC metadata, and request metrics.

SQLite-backed. Thread-safe. Emits events via EventBus.
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
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.surface.console_api")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class APIEndpoint:
    """Registered API endpoint descriptor."""
    endpoint_id: str = ""
    path: str = ""
    method: str = "GET"
    handler: str = ""
    auth_required: int = 1
    rbac_roles: list[str] = field(default_factory=list)
    description: str = ""
    active: int = 1

    def __post_init__(self):
        if not self.endpoint_id:
            self.endpoint_id = uuid.uuid4().hex


@dataclass
class APIRequest:
    """A recorded API request."""
    request_id: str = ""
    endpoint_id: str = ""
    user_id: str = ""
    status_code: int = 200
    latency_ms: int = 0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.request_id:
            self.request_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Console API
# ---------------------------------------------------------------------------

class ConsoleAPI:
    """Endpoint registry and request tracking.

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

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS api_endpoints (
                endpoint_id   TEXT PRIMARY KEY,
                path          TEXT NOT NULL DEFAULT '',
                method        TEXT NOT NULL DEFAULT 'GET',
                handler       TEXT NOT NULL DEFAULT '',
                auth_required INTEGER NOT NULL DEFAULT 1,
                rbac_roles    TEXT NOT NULL DEFAULT '[]',
                description   TEXT NOT NULL DEFAULT '',
                active        INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS api_requests (
                request_id  TEXT PRIMARY KEY,
                endpoint_id TEXT NOT NULL DEFAULT '',
                user_id     TEXT NOT NULL DEFAULT '',
                status_code INTEGER NOT NULL DEFAULT 200,
                latency_ms  INTEGER NOT NULL DEFAULT 0,
                timestamp   REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_apireq_ep ON api_requests(endpoint_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_apireq_ts ON api_requests(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, path: str, method: str = "GET",
                 handler: str = "", auth_required: bool = True,
                 rbac_roles: list[str] | None = None,
                 description: str = "") -> dict:
        """Register an API endpoint. Returns endpoint descriptor dict."""
        if rbac_roles is None:
            rbac_roles = []

        endpoint = APIEndpoint(
            path=path,
            method=method,
            handler=handler,
            auth_required=1 if auth_required else 0,
            rbac_roles=rbac_roles,
            description=description,
        )

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO api_endpoints
                    (endpoint_id, path, method, handler, auth_required,
                     rbac_roles, description, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                endpoint.endpoint_id, endpoint.path, endpoint.method,
                endpoint.handler, endpoint.auth_required,
                json.dumps(rbac_roles), endpoint.description,
            ))
            self._conn.commit()

        self._emit("surface.console_api.registered", {
            "endpoint_id": endpoint.endpoint_id,
            "path": path, "method": method,
        })

        log.info("registered endpoint %s %s (%s)", method, path, endpoint.endpoint_id[:12])
        return {
            "endpoint_id": endpoint.endpoint_id,
            "path": path,
            "method": method,
        }

    # ------------------------------------------------------------------
    # Request tracking
    # ------------------------------------------------------------------

    def record_request(self, endpoint_id: str, user_id: str = "",
                       status_code: int = 200,
                       latency_ms: int = 0) -> dict:
        """Record an API request. Returns request descriptor dict."""
        req = APIRequest(
            endpoint_id=endpoint_id,
            user_id=user_id,
            status_code=status_code,
            latency_ms=latency_ms,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO api_requests
                    (request_id, endpoint_id, user_id, status_code,
                     latency_ms, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                req.request_id, req.endpoint_id, req.user_id,
                req.status_code, req.latency_ms, req.timestamp,
            ))
            self._conn.commit()

        self._emit("surface.console_api.request_recorded", {
            "request_id": req.request_id, "endpoint_id": endpoint_id,
            "status_code": status_code,
        })

        log.info("recorded request %s: endpoint=%s status=%d",
                 req.request_id[:12], endpoint_id[:12], status_code)
        return {
            "request_id": req.request_id,
            "endpoint_id": endpoint_id,
            "status_code": status_code,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_endpoint(self, endpoint_id: str) -> dict | None:
        """Get a single endpoint by ID."""
        row = self._conn.execute(
            "SELECT * FROM api_endpoints WHERE endpoint_id = ?", (endpoint_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["rbac_roles"] = json.loads(result.get("rbac_roles", "[]"))
        return result

    def list_endpoints(self, active_only: bool = True,
                       limit: int = 100) -> list[dict]:
        """List registered endpoints."""
        if active_only:
            rows = self._conn.execute(
                "SELECT * FROM api_endpoints WHERE active = 1 ORDER BY path LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM api_endpoints ORDER BY path LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["rbac_roles"] = json.loads(d.get("rbac_roles", "[]"))
            results.append(d)
        return results

    def get_stats(self) -> dict:
        """Aggregate request statistics."""
        total_requests = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM api_requests"
        ).fetchone()["cnt"]

        total_endpoints = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM api_endpoints WHERE active = 1"
        ).fetchone()["cnt"]

        by_status_rows = self._conn.execute(
            "SELECT status_code, COUNT(*) as cnt FROM api_requests GROUP BY status_code"
        ).fetchall()
        by_status = {r["status_code"]: r["cnt"] for r in by_status_rows}

        avg_latency_row = self._conn.execute(
            "SELECT AVG(latency_ms) as avg_lat FROM api_requests"
        ).fetchone()
        avg_latency = round(avg_latency_row["avg_lat"] or 0, 2)

        return {
            "total_requests": total_requests,
            "active_endpoints": total_endpoints,
            "by_status_code": by_status,
            "avg_latency_ms": avg_latency,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="surface.console_api",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_api: ConsoleAPI | None = None


def get_console_api(db_path: str | Path | None = None,
                    event_bus: EventBus | None = None) -> ConsoleAPI:
    global _api
    if _api is None:
        _api = ConsoleAPI(db_path, event_bus)
    return _api
