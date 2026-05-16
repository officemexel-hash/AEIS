"""SYLION WebSocket routes — live event streaming."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sylion.core.event_bus import get_event_bus

log = logging.getLogger("sylion.api.ws")
router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts events."""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
        log.info("ws client connected (total: %d)", len(self._connections))

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)
        log.info("ws client disconnected (total: %d)", len(self._connections))

    async def broadcast(self, message: dict):
        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


_manager = ConnectionManager()


def get_manager() -> ConnectionManager:
    return _manager


def _overview_payload() -> dict:
    """Return a small compatibility snapshot for legacy overview clients."""
    return {
        "type": "overview",
        "status": "ok",
        "as_of": time.time(),
        "active_connections": _manager.active_count,
        "websockets": {
            "events": "/ws/events",
            "workspace": "/ws/workspace",
            "overview": "/ws/overview",
        },
        "compatibility": {
            "route": "/ws/overview",
            "canonical": "/ws/workspace",
        },
    }


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    """Stream EventBus events to connected WebSocket clients.

    Client can optionally send JSON to subscribe to specific topics:
      {"action": "subscribe", "topic": "module.*"}
    """
    await _manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "invalid json"})
                continue
            if msg.get("action") == "ping":
                await websocket.send_json({"action": "pong"})
            elif msg.get("action") == "subscribe":
                await websocket.send_json({
                    "action": "subscribed",
                    "topic": msg.get("topic", "*"),
                })
    except WebSocketDisconnect:
        await _manager.disconnect(websocket)


@router.websocket("/ws/overview")
async def ws_overview(websocket: WebSocket):
    """Compatibility endpoint for legacy dashboard overview clients.

    The current frontend uses /ws/workspace. Older builds can still attempt
    /ws/overview with a token query parameter; accepting the connection keeps
    dev logs clean and gives the client a minimal live status payload.
    """
    await websocket.accept()
    interval = 5.0
    await websocket.send_json(_overview_payload())

    while True:
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=interval)
        except asyncio.TimeoutError:
            await websocket.send_json(_overview_payload())
            continue
        except WebSocketDisconnect:
            break

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "detail": "invalid json"})
            continue

        action = msg.get("type") or msg.get("action")
        if action == "ping":
            await websocket.send_json({"type": "pong", "action": "pong"})
        elif action == "set_interval":
            try:
                seconds = float(msg.get("seconds", interval))
                interval = max(1.0, min(seconds, 30.0))
                await websocket.send_json({"type": "interval_set", "seconds": interval})
            except Exception:
                await websocket.send_json({
                    "type": "error",
                    "detail": "invalid set_interval payload",
                })
        elif action in {"overview", "snapshot", "subscribe", None}:
            await websocket.send_json(_overview_payload())
        else:
            await websocket.send_json({
                "type": "error",
                "detail": f"unknown message type: {action!r}",
            })


@router.get("/ws/stats")
async def ws_stats():
    """Return current WebSocket connection stats."""
    return {"active_connections": _manager.active_count}


async def start_event_bridge():
    """Bridge EventBus events to WebSocket clients (run on startup)."""
    bus = get_event_bus()

    def _on_event(event):
        try:
            data = event if isinstance(event, dict) else {"data": str(event)}
            asyncio.get_event_loop().create_task(_manager.broadcast(data))
        except RuntimeError:
            pass

    bus.subscribe("*", _on_event)
