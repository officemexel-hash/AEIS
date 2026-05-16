"""
SYLION Observability -- OpenTelemetry tracing scaffold.

Phase 3 W3.3: provides a single `setup_tracing(app)` entrypoint that
instruments FastAPI + SQLAlchemy + Redis + httpx with OTLP export.

Design constraints:
  - **Optional dependency.** Packages are only required when tracing is
    explicitly enabled (``SYLION_TRACING_ENABLED=1``). If the OTel
    SDK is missing the function logs a warning and returns False -- the
    app boots normally without tracing.
  - **No-op safe at import time.** Importing this module never imports
    the OTel SDK; SDK imports are deferred to ``setup_tracing()``.
  - **Sampling honoured via env.** ``SYLION_TRACING_SAMPLE_RATIO``
    (default 0.8 dev, recommend 0.1 prod) maps to TraceIdRatioBased.

Environment variables consumed:
  - ``SYLION_TRACING_ENABLED``    1 to enable, anything else -> no-op
  - ``SYLION_TRACING_ENDPOINT``   OTLP gRPC endpoint (default localhost:4317)
  - ``SYLION_TRACING_SERVICE``    service name resource label (default sylion-aeis)
  - ``SYLION_TRACING_SAMPLE_RATIO`` 0.0-1.0 (default 0.8)
  - ``SYLION_TRACING_INSECURE``   1 -> insecure gRPC (dev), default 1
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger(__name__)


def _flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _ratio(name: str, default: float = 0.8) -> float:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.0, min(1.0, value))


def is_enabled() -> bool:
    """Return True if tracing should be active. Read once per process."""
    return _flag("SYLION_TRACING_ENABLED")


def _service_name() -> str:
    return os.environ.get("SYLION_TRACING_SERVICE", "sylion-aeis").strip() or "sylion-aeis"


def _endpoint() -> str:
    return os.environ.get(
        "SYLION_TRACING_ENDPOINT", "http://localhost:4317",
    ).strip() or "http://localhost:4317"


def _import_otel():
    """Attempt to import the OTel SDK. Return None on ImportError."""
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace.export import (  # type: ignore[import-not-found]
            BatchSpanProcessor,
        )
        from opentelemetry.sdk.trace.sampling import (  # type: ignore[import-not-found]
            TraceIdRatioBased,
        )
        return {
            "trace": trace,
            "Resource": Resource,
            "TracerProvider": TracerProvider,
            "BatchSpanProcessor": BatchSpanProcessor,
            "TraceIdRatioBased": TraceIdRatioBased,
        }
    except ImportError as exc:
        log.warning(
            "tracing: opentelemetry-sdk not installed (%s); tracing disabled. "
            "Install with: pip install opentelemetry-sdk "
            "opentelemetry-exporter-otlp-proto-grpc",
            exc,
        )
        return None


def _build_exporter():
    """Build OTLP gRPC exporter; fall back to console exporter on failure."""
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import-not-found]
            OTLPSpanExporter,
        )
        return OTLPSpanExporter(
            endpoint=_endpoint(),
            insecure=_flag("SYLION_TRACING_INSECURE", "1"),
        )
    except ImportError:
        log.warning(
            "tracing: OTLP gRPC exporter unavailable; falling back to console.",
        )
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter  # type: ignore[import-not-found]
        return ConsoleSpanExporter()


def _instrument_libraries(app: Any) -> list[str]:
    """Instrument FastAPI + SQLAlchemy + Redis + httpx if available.

    Returns the list of names successfully instrumented.
    """
    instrumented: list[str] = []

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore[import-not-found]
        FastAPIInstrumentor.instrument_app(app)
        instrumented.append("fastapi")
    except ImportError:
        log.info("tracing: opentelemetry-instrumentation-fastapi missing")
    except Exception as exc:
        log.warning("tracing: fastapi instrument failed: %s", exc)

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor  # type: ignore[import-not-found]
        SQLAlchemyInstrumentor().instrument()
        instrumented.append("sqlalchemy")
    except ImportError:
        log.info("tracing: opentelemetry-instrumentation-sqlalchemy missing")
    except Exception as exc:
        log.warning("tracing: sqlalchemy instrument failed: %s", exc)

    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor  # type: ignore[import-not-found]
        RedisInstrumentor().instrument()
        instrumented.append("redis")
    except ImportError:
        log.info("tracing: opentelemetry-instrumentation-redis missing")
    except Exception as exc:
        log.warning("tracing: redis instrument failed: %s", exc)

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor  # type: ignore[import-not-found]
        HTTPXClientInstrumentor().instrument()
        instrumented.append("httpx")
    except ImportError:
        log.info("tracing: opentelemetry-instrumentation-httpx missing")
    except Exception as exc:
        log.warning("tracing: httpx instrument failed: %s", exc)

    return instrumented


def setup_tracing(app: Any) -> bool:
    """Initialise OTel tracing for the given FastAPI app.

    Returns True if tracing was wired, False if disabled or unavailable.
    Idempotent: a second call on the same process is a no-op.
    """
    if not is_enabled():
        log.info("tracing: SYLION_TRACING_ENABLED not set; skipping")
        return False

    if getattr(setup_tracing, "_initialised", False):
        return True

    sdk = _import_otel()
    if sdk is None:
        return False

    resource = sdk["Resource"].create({"service.name": _service_name()})
    sample_ratio = _ratio("SYLION_TRACING_SAMPLE_RATIO", 0.8)
    provider = sdk["TracerProvider"](
        resource=resource,
        sampler=sdk["TraceIdRatioBased"](sample_ratio),
    )
    exporter = _build_exporter()
    provider.add_span_processor(sdk["BatchSpanProcessor"](exporter))
    sdk["trace"].set_tracer_provider(provider)

    instrumented = _instrument_libraries(app)
    setup_tracing._initialised = True  # type: ignore[attr-defined]

    log.info(
        "tracing: enabled service=%s endpoint=%s sample=%.2f instrumented=%s",
        _service_name(), _endpoint(), sample_ratio, ",".join(instrumented),
    )
    return True


def get_tracer(name: str = "sylion"):
    """Return a tracer; safe to call even when tracing is disabled.

    When the OTel SDK is not installed this returns a no-op object whose
    ``start_as_current_span`` is a context manager that yields None.
    """
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]
        return trace.get_tracer(name)
    except ImportError:
        return _NoopTracer()


class _NoopTracer:
    """Drop-in no-op when opentelemetry is not installed."""

    class _NoopSpan:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def set_attribute(self, *a, **kw): pass
        def add_event(self, *a, **kw): pass
        def record_exception(self, *a, **kw): pass

    def start_as_current_span(self, *a, **kw):
        return _NoopTracer._NoopSpan()
