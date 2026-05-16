from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import pytest

import sylion.api.ai_workspace_routes as workspace_routes
import sylion.api.notification_routes as engine_routes
import sylion.api.projects_routes as project_routes
from sylion.monitoring.notification_engine import NotificationEngine
from sylion.project_mode.store import ProjectModeStore


@pytest.fixture
def notification_surface(monkeypatch: pytest.MonkeyPatch):
    store = ProjectModeStore(db_path=":memory:")
    engine = NotificationEngine(db_path=":memory:")

    monkeypatch.setattr(project_routes, "get_project_mode_store", lambda: store)
    monkeypatch.setattr(workspace_routes, "_project_store", store)
    monkeypatch.setattr(engine_routes, "_notification_engine", engine)
    monkeypatch.setattr(engine_routes, "_get_notification_engine", lambda: engine)

    app = FastAPI()
    app.include_router(workspace_routes.router)
    app.include_router(project_routes.router)
    app.include_router(engine_routes.router)

    client = TestClient(app)
    try:
        yield client, store, engine
    finally:
        store.close()


def test_project_feed_routes_support_read_unread_and_ack(notification_surface):
    client, store, _ = notification_surface
    item = store.add_notification(
        "workspace-default",
        "Approval required",
        "Review the canon book.",
        notification_type="approval_required",
    )

    listed = client.get("/api/v1/notifications", params={"owner_id": "workspace-default"})
    assert listed.status_code == 200
    assert listed.json()["notifications"][0]["notification_id"] == item["notification_id"]

    read = client.post(f"/api/v1/notifications/{item['notification_id']}/read")
    assert read.status_code == 200
    assert read.json()["status"] == "read"

    unread = client.post(f"/api/v1/notifications/{item['notification_id']}/unread")
    assert unread.status_code == 200
    assert unread.json()["status"] == "unread"

    ack = client.post(f"/api/v1/notifications/{item['notification_id']}/ack")
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"


def test_workspace_notification_routes_update_unread_count(notification_surface):
    client, store, _ = notification_surface
    item = store.add_notification(
        "workspace-default",
        "Launch ready",
        "Project can move into execution.",
    )

    unread = client.get("/api/v1/workspace/notifications/workspace-default/unread-count")
    assert unread.status_code == 200
    assert unread.json()["count"] == 1

    read = client.post(f"/api/v1/workspace/notifications/{item['notification_id']}/read")
    assert read.status_code == 200
    assert read.json()["status"] == "read"

    unread_after_read = client.get("/api/v1/workspace/notifications/workspace-default/unread-count")
    assert unread_after_read.json()["count"] == 0

    reopen = client.post(f"/api/v1/workspace/notifications/{item['notification_id']}/unread")
    assert reopen.status_code == 200
    assert reopen.json()["status"] == "unread"

    ack = client.post(f"/api/v1/workspace/notifications/{item['notification_id']}/ack")
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"

    unread_after_ack = client.get("/api/v1/workspace/notifications/workspace-default/unread-count")
    assert unread_after_ack.json()["count"] == 0


def test_engine_routes_use_dedicated_prefix_and_delivery_state(notification_surface):
    client, _, _ = notification_surface

    channel = client.post(
        "/api/v1/notification-engine/channels",
        json={
            "name": "ops-email",
            "channel_type": "email",
            "config_json": {"to": "ops@example.com"},
        },
    )
    assert channel.status_code == 201
    channel_id = channel.json()["channel_id"]

    rule = client.post(
        "/api/v1/notification-engine/rules",
        json={"name": "ops-email", "channel_id": channel_id},
    )
    assert rule.status_code == 201
    rule_id = rule.json()["rule_id"]

    sent = client.post(
        "/api/v1/notification-engine/send",
        json={
            "rule_id": rule_id,
            "title": "CPU high",
            "message": "CPU crossed the threshold.",
            "severity": "warning",
        },
    )
    assert sent.status_code == 201
    assert sent.json()["delivery_state"] == "degraded"

    engine_feed = client.get("/api/v1/notification-engine")
    assert engine_feed.status_code == 200
    notification = engine_feed.json()["notifications"][0]
    assert notification["title"] == "CPU high"
    assert notification["delivery_state"] == "degraded"


def test_project_feed_and_engine_feed_are_separated(notification_surface):
    client, store, engine = notification_surface

    store_item = store.add_notification(
        "workspace-default",
        "Project ready",
        "Project is ready to launch.",
    )

    channel = engine.create_channel("ui", "in_app")
    rule = engine.create_rule("ui-rule", channel["channel_id"])
    engine_item = engine.send_notification(rule["rule_id"], "Engine event", "Body")

    project_feed = client.get("/api/v1/notifications", params={"owner_id": "workspace-default"})
    assert project_feed.status_code == 200
    project_ids = {item["notification_id"] for item in project_feed.json()["notifications"]}
    assert store_item["notification_id"] in project_ids
    assert engine_item["notification_id"] not in project_ids

    engine_feed = client.get("/api/v1/notification-engine")
    assert engine_feed.status_code == 200
    engine_ids = {item["notification_id"] for item in engine_feed.json()["notifications"]}
    assert engine_item["notification_id"] in engine_ids
    assert store_item["notification_id"] not in engine_ids
