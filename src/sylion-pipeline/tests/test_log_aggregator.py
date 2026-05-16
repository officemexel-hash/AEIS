from __future__ import annotations

import io
import json
import urllib.error

import pytest

import sylion.observability.log_aggregator as log_aggregator
from sylion.observability.log_aggregator import (
    ElasticsearchBackend,
    LocalLogBackend,
    LogAggregator,
    LogBackendNotConfiguredError,
    LogBackendRequestError,
    LokiBackend,
)


class _DummyResponse:
    def __init__(self, payload: str = "{}"):
        self._payload = payload.encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_local_backend_filters_and_limit():
    backend = LocalLogBackend(max_size=5)
    backend.emit({"service": "planner", "level": "info", "message": "one"})
    backend.emit({"service": "planner", "level": "error", "message": "two"})
    backend.emit({"service": "worker", "level": "error", "message": "three"})

    results = backend.query(service="planner", level="error", limit=2)

    assert results == [{"service": "planner", "level": "error", "message": "two"}]


def test_log_aggregator_defaults_to_local_backend():
    aggregator = LogAggregator()

    aggregator.log("planner", "info", "hello", extra={"task_id": "t1"})

    assert aggregator.get_backend_type() == "LocalLogBackend"
    assert aggregator.query(limit=1)[0]["task_id"] == "t1"


@pytest.mark.parametrize("backend_cls", [ElasticsearchBackend, LokiBackend])
@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("emit", ({"service": "planner", "level": "info", "message": "hello"},)),
        ("query", ()),
    ],
)
def test_external_backends_fail_closed_when_endpoint_missing(backend_cls, method_name, args):
    backend = backend_cls()

    with pytest.raises(LogBackendNotConfiguredError, match="configured endpoint"):
        getattr(backend, method_name)(*args)


def test_elasticsearch_emit_uses_live_http_request(monkeypatch):
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _DummyResponse('{"result":"created"}')

    monkeypatch.setattr(log_aggregator.urllib.request, "urlopen", fake_urlopen)

    backend = ElasticsearchBackend(endpoint="http://logs.example:9200", index_name="aeis-logs")
    backend.emit({"service": "planner", "level": "info", "message": "hello", "timestamp": 123.0})

    assert captured["url"] == "http://logs.example:9200/aeis-logs/_doc"
    assert captured["method"] == "POST"
    assert captured["timeout"] == 5.0
    assert captured["body"]["message"] == "hello"
    assert "@timestamp" in captured["body"]


def test_elasticsearch_query_parses_search_hits(monkeypatch):
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _DummyResponse(
            json.dumps(
                {
                    "hits": {
                        "hits": [
                            {
                                "_source": {
                                    "service": "planner",
                                    "level": "error",
                                    "message": "failed",
                                }
                            }
                        ]
                    }
                }
            )
        )

    monkeypatch.setattr(log_aggregator.urllib.request, "urlopen", fake_urlopen)

    backend = ElasticsearchBackend(endpoint="http://logs.example:9200")
    results = backend.query(service="planner", level="error", limit=3)

    assert captured["url"] == "http://logs.example:9200/sylion-logs/_search"
    assert captured["method"] == "POST"
    assert captured["body"]["size"] == 3
    assert captured["body"]["query"]["bool"]["filter"] == [
        {"term": {"service.keyword": "planner"}},
        {"term": {"level.keyword": "error"}},
    ]
    assert results == [{"service": "planner", "level": "error", "message": "failed"}]


def test_elasticsearch_http_failure_raises_honest_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"down"}'),
        )

    monkeypatch.setattr(log_aggregator.urllib.request, "urlopen", fake_urlopen)

    backend = ElasticsearchBackend(endpoint="http://logs.example:9200")
    with pytest.raises(LogBackendRequestError, match="HTTP 503"):
        backend.query(limit=1)


def test_loki_emit_uses_live_http_request(monkeypatch):
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _DummyResponse()

    monkeypatch.setattr(log_aggregator.urllib.request, "urlopen", fake_urlopen)

    backend = LokiBackend(endpoint="http://logs.example:3100", tenant_id="tenant-a")
    backend.emit({"service": "planner", "level": "warning", "message": "hello", "timestamp": 123.0})

    assert captured["url"] == "http://logs.example:3100/loki/api/v1/push"
    assert captured["method"] == "POST"
    assert captured["headers"]["X-scope-orgid"] == "tenant-a"
    assert captured["body"]["streams"][0]["stream"] == {
        "service": "planner",
        "level": "warning",
    }
    assert captured["body"]["streams"][0]["values"][0][0] == "123000000000"


def test_loki_query_parses_stream_results(monkeypatch):
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        return _DummyResponse(
            json.dumps(
                {
                    "data": {
                        "result": [
                            {
                                "stream": {"service": "planner", "level": "info"},
                                "values": [
                                    [
                                        "1710000000000000000",
                                        json.dumps({"message": "hello"}),
                                    ]
                                ],
                            }
                        ]
                    }
                }
            )
        )

    monkeypatch.setattr(log_aggregator.urllib.request, "urlopen", fake_urlopen)

    backend = LokiBackend(endpoint="http://logs.example:3100")
    results = backend.query(service="planner", limit=2)

    assert captured["method"] == "GET"
    assert "query=%7Bservice%3D%22planner%22%7D" in captured["url"]
    assert results == [
        {
            "message": "hello",
            "labels": {"service": "planner", "level": "info"},
            "service": "planner",
            "level": "info",
            "timestamp": 1710000000.0,
        }
    ]


def test_loki_network_failure_raises_honest_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(log_aggregator.urllib.request, "urlopen", fake_urlopen)

    backend = LokiBackend(endpoint="http://logs.example:3100")
    with pytest.raises(LogBackendRequestError, match="connection refused"):
        backend.query(limit=1)
