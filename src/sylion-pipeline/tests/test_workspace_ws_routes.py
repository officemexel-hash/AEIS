"""Tests for the AI Workspace WebSocket event forwarding."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from sylion.api.app import app
from sylion.core.event_bus import SylionEvent, get_event_bus


client = TestClient(app)


def test_workspace_ws_forwards_pipeline_events():
    bus = get_event_bus()
    with client.websocket_connect("/ws/workspace") as ws:
        ws.send_text(json.dumps({"type": "subscribe", "topics": ["pipeline."]}))
        subscribed = ws.receive_json()
        assert subscribed["type"] == "subscribed"

        bus.publish(
            SylionEvent(
                event_id="",
                topic="pipeline.run_completed",
                payload={"run_id": "run_ws_001"},
                source_module="tests.workspace_ws",
            )
        )

        event = ws.receive_json()
        assert event["type"] == "event"
        assert event["topic"] == "pipeline.run_completed"
        assert event["payload"]["run_id"] == "run_ws_001"


def test_workspace_ws_forwards_notification_events():
    bus = get_event_bus()
    with client.websocket_connect("/ws/workspace") as ws:
        ws.send_text(json.dumps({"type": "subscribe", "topics": ["notification."]}))
        subscribed = ws.receive_json()
        assert subscribed["type"] == "subscribed"

        bus.publish(
            SylionEvent(
                event_id="",
                topic="notification.sent",
                payload={"notification_id": "notif_ws_001"},
                source_module="tests.workspace_ws",
            )
        )

        event = ws.receive_json()
        assert event["type"] == "event"
        assert event["topic"] == "notification.sent"
        assert event["payload"]["notification_id"] == "notif_ws_001"
