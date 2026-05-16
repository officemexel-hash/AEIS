from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.api import event_backbone_routes
from sylion.core.event_backbone import EventBackboneError


class StubBackbone:
    def __init__(self, *, health_payload: dict, catalog=None, query=None):
        self._health_payload = health_payload
        self._catalog = catalog if catalog is not None else {}
        self._query = query if query is not None else []

    def health(self) -> dict:
        return self._health_payload

    def get_catalog(self):
        if isinstance(self._catalog, Exception):
            raise self._catalog
        return self._catalog

    def query(self, topic: str | None = None, limit: int = 100):
        if isinstance(self._query, Exception):
            raise self._query
        return self._query


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(event_backbone_routes.router)
    return TestClient(app)


def test_health_returns_200_when_backbone_is_ok():
    event_backbone_routes._backbone = StubBackbone(
        health_payload={"backend": "local", "status": "ok", "ready": True}
    )
    client = _make_client()

    response = client.get("/api/v1/event-backbone/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_returns_503_when_backbone_is_degraded():
    event_backbone_routes._backbone = StubBackbone(
        health_payload={"backend": "nats", "status": "degraded", "ready": True}
    )
    client = _make_client()

    response = client.get("/api/v1/event-backbone/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_events_returns_backend_error_instead_of_fake_empty_success():
    event_backbone_routes._backbone = StubBackbone(
        health_payload={"backend": "nats", "status": "degraded", "ready": True},
        query=EventBackboneError(
            "nats",
            "query",
            "NATS backbone does not provide event history query in this runtime",
            status="degraded",
            http_status=501,
        ),
    )
    client = _make_client()

    response = client.get("/api/v1/event-backbone/events", params={"topic": "jobs.run"})

    assert response.status_code == 501
    detail = response.json()["detail"]
    assert detail["backend"] == "nats"
    assert detail["operation"] == "query"
    assert detail["status"] == "degraded"


def test_catalog_returns_backend_error_instead_of_fake_success():
    event_backbone_routes._backbone = StubBackbone(
        health_payload={"backend": "redis", "status": "degraded", "ready": True},
        catalog=EventBackboneError(
            "redis",
            "catalog",
            "Redis Pub/Sub does not provide a global topic catalog in this runtime",
            status="degraded",
            http_status=501,
        ),
    )
    client = _make_client()

    response = client.get("/api/v1/event-backbone/catalog")

    assert response.status_code == 501
    detail = response.json()["detail"]
    assert detail["backend"] == "redis"
    assert detail["operation"] == "catalog"
    assert detail["status"] == "degraded"
