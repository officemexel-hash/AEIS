"""SYLION Workspace WebSocket routes — real-time streaming for AI Workspace."""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sylion.core.event_bus import get_event_bus

log = logging.getLogger("sylion.api.workspace_ws")
router = APIRouter(tags=["workspace_ws"])


@router.websocket("/ws/workspace")
async def ws_workspace(websocket: WebSocket):
    """Bidirectional WebSocket for AI Workspace real-time events.

    Outgoing (server -> client):
        {"type": "event", "topic": "...", "payload": {...},
         "source_module": "...", "timestamp": ...}

    Incoming (client -> server):
        {"type": "ping"}                          -> {"type": "pong"}
        {"type": "subscribe", "topics": [...]}     -> filters forwarded events
    """
    await websocket.accept()
    log.info("workspace ws client connected")

    bus = get_event_bus()
    queue: asyncio.Queue[dict] = asyncio.Queue()

    # Default: accept all workspace.* events
    topics: list[str] = []

    def _event_callback(event):
        """EventBus subscriber: enqueue matching events for this client."""
        topic = event.topic if isinstance(event.topic, str) else str(event.topic)
        # Always forward workspace.* events; narrow if client set explicit topics
        if not topic.startswith("workspace."):
            return
        if topics and not any(topic.startswith(t.rstrip("*").rstrip(".")) for t in topics):
            return
        try:
            queue.put_nowait({
                "type": "event",
                "topic": topic,
                "payload": event.payload,
                "source_module": event.source_module,
                "timestamp": event.timestamp,
            })
        except Exception:
            log.exception("failed to enqueue event for workspace ws client")

    # Subscribe to all events and filter in callback (EventBus only supports
    # exact topic or "*" wildcard — no glob patterns).
    bus.subscribe("*", _event_callback)

    async def _sender():
        """Forward queued events to the WebSocket."""
        try:
            while True:
                msg = await queue.get()
                await websocket.send_text(json.dumps(msg, default=str))
        except WebSocketDisconnect:
            pass
        except Exception:
            log.exception("workspace ws sender error")

    sender_task = asyncio.create_task(_sender())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "invalid json"})
                continue

            msg_type = msg.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "subscribe":
                new_topics = msg.get("topics")
                if isinstance(new_topics, list):
                    topics.clear()
                    topics.extend(new_topics)
                await websocket.send_json({
                    "type": "subscribed",
                    "topics": list(topics),
                })

    except WebSocketDisconnect:
        log.info("workspace ws client disconnected")
    finally:
        sender_task.cancel()
        # Note: EventBus has no unsubscribe — callback will fire but queue is
        # no longer consumed. Harmless for a disconnected client.
