from __future__ import annotations

from sylion.api.health_v2_routes import assemble_v2_health


def test_assemble_v2_health_all_ok() -> None:
    out = assemble_v2_health({"a": "clean"}, {"svc": "up"}, "v2.7")
    assert out == {"status": "ok", "audit_chains": {"a": "clean"}, "services": {"svc": "up"}, "version": "v2.7"}


def test_assemble_v2_health_degraded_on_chain_violation() -> None:
    assert assemble_v2_health({"a": "violated"}, {"svc": "up"}, "v2.7")["status"] == "degraded"


def test_assemble_v2_health_idle_chain_ok() -> None:
    assert assemble_v2_health({"a": "idle"}, {"svc": "up"}, "v2.7")["status"] == "ok"


def test_assemble_v2_health_degraded_on_service_down() -> None:
    assert assemble_v2_health({"a": "clean"}, {"svc": "down"}, "v2.7")["status"] == "degraded"


def test_assemble_v2_health_uses_version_override() -> None:
    assert assemble_v2_health({}, {}, "custom")["version"] == "custom"
