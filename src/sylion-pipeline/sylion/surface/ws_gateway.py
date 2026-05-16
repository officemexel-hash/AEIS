"""
SYLION Surface -- WebSocket Gateway

Manages WebSocket connections, channels, and message routing.
Tracks connection lifecycle and message history for monitoring.

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

log = logging.getLogger("sylion.surface.ws_gateway")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class WSConnection:
    """A WebSocket connection record."""
    conn_id: str = ""
    user_id: str = ""
    client_id: str = ""
    channels: list[str] = field(default_factory=list)
    connected_at: float = 0.0
    disconnected_at: float = 0.0
    status: str = "connected"

    def __post_init__(self):
        if not self.conn_id:
            self.conn_id = uuid.uuid4().hex
        if not self.connected_at:
            self.connected_at = time.time()


@dataclass
class WSMessage:
    """A WebSocket message record."""
    msg_id: str = ""
    conn_id: str = ""
    channel: str = ""
    direction: str = "out"
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.msg_id:
            self.msg_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# WebSocket Gateway
# ---------------------------------------------------------------------------

class WSGateway:
    """WebSocket connection and message manager.

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
            CREATE TABLE IF NOT EXISTS ws_connections (
                conn_id        TEXT PRIMARY KEY,
                user_id        TEXT NOT NULL DEFAULT '',
                client_id      TEXT NOT NULL DEFAULT '',
                channels       TEXT NOT NULL DEFAULT '[]',
                connected_at   REAL NOT NULL,
                disconnected_at REAL NOT NULL DEFAULT 0,
                status         TEXT NOT NULL DEFAULT 'connected'
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS ws_messages (
                msg_id    TEXT PRIMARY KEY,
                conn_id   TEXT NOT NULL,
                channel   TEXT NOT NULL DEFAULT '',
                direction TEXT NOT NULL DEFAULT 'out',
                payload   TEXT NOT NULL DEFAULT '{}',
                timestamp REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_wsmsg_conn ON ws_messages(conn_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_wsmsg_chan ON ws_messages(channel)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_wsconn_status ON ws_connections(status)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self, user_id: str = "", client_id: str = "",
                channels: list[str] | None = None) -> dict:
        """Register a new WebSocket connection. Returns connection descriptor."""
        if channels is None:
            channels = []

        ws = WSConnection(
            user_id=user_id,
            client_id=client_id,
            channels=channels,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO ws_connections
                    (conn_id, user_id, client_id, channels,
                     connected_at, disconnected_at, status)
                VALUES (?, ?, ?, ?, ?, 0, 'connected')
            """, (
                ws.conn_id, ws.user_id, ws.client_id,
                json.dumps(channels), ws.connected_at,
            ))
            self._conn.commit()

        self._emit("surface.ws_gateway.connected", {
            "conn_id": ws.conn_id, "user_id": user_id,
            "client_id": client_id,
        })

        log.info("WS connected: %s (user=%s client=%s)",
                 ws.conn_id[:12], user_id, client_id)
        return {"conn_id": ws.conn_id, "status": "connected"}

    def disconnect(self, conn_id: str) -> dict:
        """Mark a WebSocket connection as disconnected."""
        now = time.time()

        with self._lock:
            updated = self._conn.execute("""
                UPDATE ws_connections
                SET status = 'disconnected', disconnected_at = ?
                WHERE conn_id = ? AND status = 'connected'
            """, (now, conn_id))
            self._conn.commit()

        if updated.rowcount == 0:
            log.warning("WS disconnect: connection %s not found or already closed",
                        conn_id[:12])
            return {"conn_id": conn_id, "error": "not found or already disconnected"}

        self._emit("surface.ws_gateway.disconnected", {
            "conn_id": conn_id,
        })

        log.info("WS disconnected: %s", conn_id[:12])
        return {"conn_id": conn_id, "status": "disconnected", "disconnected_at": now}

    # ------------------------------------------------------------------
    # Channel subscriptions
    # ------------------------------------------------------------------

    def subscribe(self, conn_id: str, channels: list[str]) -> dict:
        """Subscribe a connection to additional channels."""
        row = self._conn.execute(
            "SELECT channels FROM ws_connections WHERE conn_id = ? AND status = 'connected'",
            (conn_id,),
        ).fetchone()
        if not row:
            return {"conn_id": conn_id, "error": "connection not found"}

        current = json.loads(row["channels"])
        updated = list(set(current + channels))

        with self._lock:
            self._conn.execute("""
                UPDATE ws_connections SET channels = ? WHERE conn_id = ?
            """, (json.dumps(updated), conn_id))
            self._conn.commit()

        self._emit("surface.ws_gateway.subscribed", {
            "conn_id": conn_id, "channels": channels,
        })

        log.info("WS %s subscribed to %s", conn_id[:12], channels)
        return {"conn_id": conn_id, "channels": updated}

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    def send(self, conn_id: str, channel: str,
             payload: dict | None = None) -> dict:
        """Send a message to a specific connection. Returns message descriptor."""
        if payload is None:
            payload = {}

        msg = WSMessage(
            conn_id=conn_id,
            channel=channel,
            direction="out",
            payload=payload,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO ws_messages
                    (msg_id, conn_id, channel, direction, payload, timestamp)
                VALUES (?, ?, ?, 'out', ?, ?)
            """, (
                msg.msg_id, msg.conn_id, msg.channel,
                json.dumps(payload, default=str), msg.timestamp,
            ))
            self._conn.commit()

        self._emit("surface.ws_gateway.message_sent", {
            "msg_id": msg.msg_id, "conn_id": conn_id, "channel": channel,
        })

        log.info("WS sent to %s on %s: %s", conn_id[:12], channel, msg.msg_id[:12])
        return {"msg_id": msg.msg_id, "conn_id": conn_id, "channel": channel}

    def broadcast(self, channel: str, payload: dict | None = None) -> dict:
        """Broadcast a message to all connections subscribed to a channel."""
        if payload is None:
            payload = {}

        # Find all active connections subscribed to the channel
        rows = self._conn.execute(
            "SELECT conn_id, channels FROM ws_connections WHERE status = 'connected'"
        ).fetchall()

        target_conns = []
        for r in rows:
            channels = json.loads(r["channels"])
            if channel in channels:
                target_conns.append(r["conn_id"])

        msg_ids = []
        now = time.time()

        with self._lock:
            for conn_id in target_conns:
                msg_id = uuid.uuid4().hex
                self._conn.execute("""
                    INSERT INTO ws_messages
                        (msg_id, conn_id, channel, direction, payload, timestamp)
                    VALUES (?, ?, ?, 'out', ?, ?)
                """, (
                    msg_id, conn_id, channel,
                    json.dumps(payload, default=str), now,
                ))
                msg_ids.append(msg_id)
            self._conn.commit()

        self._emit("surface.ws_gateway.broadcast", {
            "channel": channel, "recipient_count": len(msg_ids),
        })

        log.info("WS broadcast on %s to %d connections", channel, len(msg_ids))
        return {
            "channel": channel,
            "recipient_count": len(msg_ids),
            "msg_ids": msg_ids,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_connections(self, status: str | None = None,
                        limit: int = 100) -> list[dict]:
        """List connections, optionally filtered by status."""
        if status:
            rows = self._conn.execute(
                "SELECT * FROM ws_connections WHERE status = ? ORDER BY connected_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM ws_connections ORDER BY connected_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["channels"] = json.loads(d.get("channels", "[]"))
            results.append(d)
        return results

    def get_messages(self, conn_id: str | None = None,
                     channel: str | None = None,
                     limit: int = 100) -> list[dict]:
        """List messages, optionally filtered by connection and/or channel."""
        query = "SELECT * FROM ws_messages WHERE 1=1"
        params: list[Any] = []
        if conn_id:
            query += " AND conn_id = ?"
            params.append(conn_id)
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d.get("payload", "{}"))
            results.append(d)
        return results

    def get_stats(self) -> dict:
        """Aggregate WebSocket statistics."""
        total_connections = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM ws_connections"
        ).fetchone()["cnt"]

        active_connections = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM ws_connections WHERE status = 'connected'"
        ).fetchone()["cnt"]

        total_messages = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM ws_messages"
        ).fetchone()["cnt"]

        by_direction_rows = self._conn.execute(
            "SELECT direction, COUNT(*) as cnt FROM ws_messages GROUP BY direction"
        ).fetchall()
        by_direction = {r["direction"]: r["cnt"] for r in by_direction_rows}

        return {
            "total_connections": total_connections,
            "active_connections": active_connections,
            "total_messages": total_messages,
            "messages_by_direction": by_direction,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="surface.ws_gateway",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_gateway: WSGateway | None = None


def get_ws_gateway(db_path: str | Path | None = None,
                   event_bus: EventBus | None = None) -> WSGateway:
    global _gateway
    if _gateway is None:
        _gateway = WSGateway(db_path, event_bus)
    return _gateway
