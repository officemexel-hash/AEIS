"""
SYLION Observability -- Distributed Log Aggregator.

Collects structured logs from workers, integration, and core systems.
Supports multiple backends:
  - local (in-memory ring buffer, default)
  - elasticsearch (HTTP API)
  - loki (HTTP API)

External backends fail closed when they are not configured or unavailable.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime, timezone
from typing import Any


class LogBackendError(RuntimeError):
    """Base exception for log backend failures."""


class LogBackendNotConfiguredError(LogBackendError):
    """Raised when an external backend is selected without a live endpoint."""


class LogBackendRequestError(LogBackendError):
    """Raised when an external backend request fails."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LogBackend(ABC):
    @abstractmethod
    def emit(self, record: dict[str, Any]) -> None: ...

    @abstractmethod
    def query(
        self,
        service: str | None = None,
        level: str | None = None,
        limit: int = 100,
    ) -> list[dict]: ...


class LocalLogBackend(LogBackend):
    """In-memory ring buffer for local dev / testing."""

    def __init__(self, max_size: int = 10000):
        self._buffer: deque[dict[str, Any]] = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def emit(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._buffer.append(dict(record))

    def query(
        self,
        service: str | None = None,
        level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        with self._lock:
            results = list(self._buffer)
        if service:
            results = [r for r in results if r.get("service") == service]
        if level:
            results = [r for r in results if r.get("level") == level]
        return results[-max(limit, 0):]


class _HttpLogBackend(LogBackend):
    """Shared HTTP plumbing for external log backends."""

    def __init__(self, endpoint: str | None, timeout_s: float = 5.0):
        self._endpoint = endpoint.rstrip("/") if endpoint else None
        self._timeout_s = timeout_s

    def _require_endpoint(self) -> str:
        if not self._endpoint:
            raise LogBackendNotConfiguredError(
                f"{type(self).__name__} requires a configured endpoint"
            )
        return self._endpoint

    def _request_json(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
            body = json.dumps(payload, default=str).encode("utf-8")
        if headers:
            request_headers.update(headers)

        request = urllib.request.Request(
            url=url,
            data=body,
            headers=request_headers,
            method=method.upper(),
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            detail = error_body.strip() or str(exc.reason)
            raise LogBackendRequestError(
                f"{type(self).__name__} request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            detail = getattr(exc, "reason", exc)
            raise LogBackendRequestError(
                f"{type(self).__name__} request failed: {detail}"
            ) from exc

        if not raw_body.strip():
            return {}

        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise LogBackendRequestError(
                f"{type(self).__name__} returned invalid JSON"
            ) from exc
        if not isinstance(parsed, dict):
            raise LogBackendRequestError(
                f"{type(self).__name__} returned a non-object JSON payload"
            )
        return parsed


class ElasticsearchBackend(_HttpLogBackend):
    """Elasticsearch-backed log storage over the HTTP API."""

    def __init__(
        self,
        endpoint: str | None = None,
        index_name: str = "sylion-logs",
        timeout_s: float = 5.0,
    ):
        super().__init__(endpoint=endpoint, timeout_s=timeout_s)
        self._index_name = index_name

    def emit(self, record: dict[str, Any]) -> None:
        endpoint = self._require_endpoint()
        es_record = dict(record)
        es_record.setdefault("@timestamp", _utc_now_iso())
        self._request_json(
            "POST",
            f"{endpoint}/{urllib.parse.quote(self._index_name)}/_doc",
            payload=es_record,
        )

    def query(
        self,
        service: str | None = None,
        level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        endpoint = self._require_endpoint()
        filters: list[dict[str, Any]] = []
        if service:
            filters.append({"term": {"service.keyword": service}})
        if level:
            filters.append({"term": {"level.keyword": level}})
        query: dict[str, Any]
        if filters:
            query = {"bool": {"filter": filters}}
        else:
            query = {"match_all": {}}

        response = self._request_json(
            "POST",
            f"{endpoint}/{urllib.parse.quote(self._index_name)}/_search",
            payload={
                "size": limit,
                "sort": [{"@timestamp": {"order": "desc"}}],
                "query": query,
            },
        )
        hits = response.get("hits", {}).get("hits", [])
        if not isinstance(hits, list):
            raise LogBackendRequestError(
                "ElasticsearchBackend returned invalid hits payload"
            )
        results = []
        for hit in hits:
            if isinstance(hit, dict) and isinstance(hit.get("_source"), dict):
                results.append(hit["_source"])
        return results[:limit]


class LokiBackend(_HttpLogBackend):
    """Grafana Loki-backed log storage over the HTTP API."""

    def __init__(
        self,
        endpoint: str | None = None,
        tenant_id: str | None = None,
        timeout_s: float = 5.0,
    ):
        super().__init__(endpoint=endpoint, timeout_s=timeout_s)
        self._tenant_id = tenant_id

    def _extra_headers(self) -> dict[str, str]:
        if not self._tenant_id:
            return {}
        return {"X-Scope-OrgID": self._tenant_id}

    def emit(self, record: dict[str, Any]) -> None:
        endpoint = self._require_endpoint()
        loki_record = dict(record)
        labels = loki_record.get("labels") or {}
        stream = {
            "service": str(labels.get("service", loki_record.get("service", "unknown"))),
            "level": str(labels.get("level", loki_record.get("level", "info"))),
        }
        timestamp_value = loki_record.get("timestamp", time.time())
        try:
            timestamp_ns = str(int(float(timestamp_value) * 1_000_000_000))
        except (TypeError, ValueError) as exc:
            raise LogBackendRequestError("LokiBackend requires a numeric timestamp") from exc

        self._request_json(
            "POST",
            f"{endpoint}/loki/api/v1/push",
            payload={
                "streams": [
                    {
                        "stream": stream,
                        "values": [[timestamp_ns, json.dumps(loki_record, default=str)]],
                    }
                ]
            },
            headers=self._extra_headers(),
        )

    def query(
        self,
        service: str | None = None,
        level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        endpoint = self._require_endpoint()
        label_parts = []
        if service:
            label_parts.append(f'service="{service}"')
        if level:
            label_parts.append(f'level="{level}"')
        selector = "{" + ",".join(label_parts) + "}" if label_parts else "{}"
        url = (
            f"{endpoint}/loki/api/v1/query_range?"
            + urllib.parse.urlencode({"query": selector, "limit": limit})
        )
        response = self._request_json("GET", url, headers=self._extra_headers())
        results_payload = response.get("data", {}).get("result", [])
        if not isinstance(results_payload, list):
            raise LogBackendRequestError("LokiBackend returned invalid result payload")

        results: list[dict[str, Any]] = []
        for stream_payload in results_payload:
            if not isinstance(stream_payload, dict):
                continue
            stream = stream_payload.get("stream", {})
            values = stream_payload.get("values", [])
            if not isinstance(values, list):
                continue
            for entry in values:
                if not isinstance(entry, list) or len(entry) != 2:
                    continue
                timestamp_ns, line = entry
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        record = {"message": line}
                except json.JSONDecodeError:
                    record = {"message": line}
                if isinstance(stream, dict):
                    record.setdefault("labels", dict(stream))
                    if "service" not in record and "service" in stream:
                        record["service"] = stream["service"]
                    if "level" not in record and "level" in stream:
                        record["level"] = stream["level"]
                try:
                    record.setdefault("timestamp", int(timestamp_ns) / 1_000_000_000)
                except (TypeError, ValueError):
                    pass
                results.append(record)
        return results[-max(limit, 0):]


class LogAggregator:
    """Facade for log aggregation. Zero-code-change backend switching.

    Phase 3 W3.4: PII redactor runs on every record before backend.emit() so
    no sensitive payload reaches Loki/Elasticsearch unredacted. Disable for
    targeted tests via redact=False.
    """

    def __init__(self, backend: LogBackend | None = None, *, redact: bool = True):
        self._backend = backend or LocalLogBackend()
        self._redact = redact

    def log(
        self,
        service: str,
        level: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        record = {
            "timestamp": time.time(),
            "service": service,
            "level": level,
            "message": message,
            **(extra or {}),
        }
        if self._redact:
            from sylion.observability.pii_redactor import redact_record
            record = redact_record(record)
        self._backend.emit(record)

    def query(
        self,
        service: str | None = None,
        level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        return self._backend.query(service, level, limit)

    def get_backend_type(self) -> str:
        return type(self._backend).__name__
