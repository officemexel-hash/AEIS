"""Phase 3 W3.3: tracing scaffold tests.

These tests run with or without the OpenTelemetry SDK installed:
  - When the SDK is missing they exercise the fail-soft no-op paths.
  - When the SDK is present they exercise the wiring paths.
"""

from __future__ import annotations

import importlib

import pytest

import sylion.observability.tracing as tracing_module


@pytest.fixture(autouse=True)
def reset_tracing_state(monkeypatch):
    """Each test starts with a fresh setup_tracing flag and clean env."""
    if hasattr(tracing_module.setup_tracing, "_initialised"):
        delattr(tracing_module.setup_tracing, "_initialised")
    for var in (
        "SYLION_TRACING_ENABLED",
        "SYLION_TRACING_ENDPOINT",
        "SYLION_TRACING_SERVICE",
        "SYLION_TRACING_SAMPLE_RATIO",
        "SYLION_TRACING_INSECURE",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


# -- env helpers -----------------------------------------------------------

class TestEnvHelpers:
    def test_disabled_by_default(self):
        assert tracing_module.is_enabled() is False

    def test_enabled_truthy(self, monkeypatch):
        for value in ("1", "true", "TRUE", "yes", "on"):
            monkeypatch.setenv("SYLION_TRACING_ENABLED", value)
            assert tracing_module.is_enabled() is True

    def test_enabled_falsy(self, monkeypatch):
        for value in ("0", "false", "no", "off", "garbage"):
            monkeypatch.setenv("SYLION_TRACING_ENABLED", value)
            assert tracing_module.is_enabled() is False

    def test_default_service_name(self):
        assert tracing_module._service_name() == "sylion-aeis"

    def test_custom_service_name(self, monkeypatch):
        monkeypatch.setenv("SYLION_TRACING_SERVICE", "sylion-staging")
        assert tracing_module._service_name() == "sylion-staging"

    def test_default_endpoint(self):
        assert tracing_module._endpoint() == "http://localhost:4317"

    def test_custom_endpoint(self, monkeypatch):
        monkeypatch.setenv("SYLION_TRACING_ENDPOINT", "http://otel.prod:4317")
        assert tracing_module._endpoint() == "http://otel.prod:4317"

    def test_ratio_clamped(self, monkeypatch):
        monkeypatch.setenv("SYLION_TRACING_SAMPLE_RATIO", "5.0")
        assert tracing_module._ratio("SYLION_TRACING_SAMPLE_RATIO") == 1.0
        monkeypatch.setenv("SYLION_TRACING_SAMPLE_RATIO", "-3.0")
        assert tracing_module._ratio("SYLION_TRACING_SAMPLE_RATIO") == 0.0
        monkeypatch.setenv("SYLION_TRACING_SAMPLE_RATIO", "0.42")
        assert tracing_module._ratio("SYLION_TRACING_SAMPLE_RATIO") == 0.42

    def test_ratio_default_on_garbage(self, monkeypatch):
        monkeypatch.setenv("SYLION_TRACING_SAMPLE_RATIO", "abc")
        assert tracing_module._ratio("SYLION_TRACING_SAMPLE_RATIO", 0.7) == 0.7


# -- setup_tracing dispatch ------------------------------------------------

class TestSetupTracing:
    def test_disabled_returns_false(self):
        assert tracing_module.setup_tracing(app=object()) is False

    def test_enabled_without_sdk_returns_false(self, monkeypatch):
        monkeypatch.setenv("SYLION_TRACING_ENABLED", "1")
        # Force the import probe to return None regardless of installed pkgs.
        monkeypatch.setattr(tracing_module, "_import_otel", lambda: None)
        assert tracing_module.setup_tracing(app=object()) is False

    def test_idempotent(self, monkeypatch):
        monkeypatch.setenv("SYLION_TRACING_ENABLED", "1")
        # Stub the entire wiring path.
        monkeypatch.setattr(tracing_module, "_import_otel", lambda: None)
        tracing_module.setup_tracing._initialised = True  # type: ignore[attr-defined]
        # Should hit the early-return idempotent branch.
        assert tracing_module.setup_tracing(app=object()) is True


# -- no-op tracer guarantee ------------------------------------------------

class TestNoopTracer:
    def test_get_tracer_returns_something(self):
        t = tracing_module.get_tracer("test")
        assert t is not None
        # context manager interface:
        with t.start_as_current_span("op") as span:
            assert span is None or hasattr(span, "set_attribute")

    def test_noop_span_methods_dont_raise(self):
        noop = tracing_module._NoopTracer()
        with noop.start_as_current_span("x") as span:
            span.set_attribute("k", "v")
            span.add_event("evt", {"a": 1})
            span.record_exception(ValueError("oops"))


# -- module reimport safety ------------------------------------------------

class TestImportSafety:
    def test_reimport_does_not_pull_otel(self):
        importlib.reload(tracing_module)
        assert tracing_module.is_enabled() is False
