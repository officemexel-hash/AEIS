"""Tests for ``sylion.aeis_v2.rbac_v2`` — W7 capability extension."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sylion.aeis_v2.audit_chain import verify_chain
from sylion.aeis_v2.rbac_v2 import (
    DEFAULT_ROLE_CAPABILITIES,
    NEW_V2_ROLES,
    RoleCapabilities,
    audit_capability_check,
    grant_role_capabilities,
    has_capability,
    list_capabilities_for_role,
    list_roles_with_capability,
    register_role_capabilities,
    reset_capability_registry,
)


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Each test runs against a clean capability registry + tmp audit."""
    import sylion.aeis_v2.rbac_v2.capabilities as mod

    monkeypatch.setattr(mod, "RBAC_V2_AUDIT_LOG_PATH", tmp_path / "rbac.jsonl")
    reset_capability_registry()
    yield
    reset_capability_registry()


# ---------------------------------------------------------------------------
# Module invariants
# ---------------------------------------------------------------------------


def test_new_v2_roles_canonical_set() -> None:
    assert NEW_V2_ROLES == (
        "replay_operator", "lifecycle_manager", "metrics_viewer",
    )


def test_owner_has_superuser_sentinel() -> None:
    assert "*" in DEFAULT_ROLE_CAPABILITIES["owner"]


def test_canonical_tier_present_in_default_matrix() -> None:
    """Both canonical (5) and new (3) roles are seeded by default."""
    canonical = {"owner", "operator", "auditor", "security", "viewer"}
    for r in canonical:
        assert r in DEFAULT_ROLE_CAPABILITIES
    for r in NEW_V2_ROLES:
        assert r in DEFAULT_ROLE_CAPABILITIES


# ---------------------------------------------------------------------------
# has_capability
# ---------------------------------------------------------------------------


def test_owner_has_every_capability() -> None:
    """The * sentinel makes owner pass every check."""
    assert has_capability({"owner"}, "anything.you.want") is True
    assert has_capability({"owner"}, "gdpr.dsr.access") is True


def test_replay_operator_caps() -> None:
    assert has_capability({"replay_operator"}, "replay.run") is True
    assert has_capability({"replay_operator"}, "replay.list") is True
    assert has_capability({"replay_operator"}, "gdpr.dsr.access") is False


def test_lifecycle_manager_caps() -> None:
    assert has_capability({"lifecycle_manager"}, "lifecycle.transition") is True
    assert has_capability({"lifecycle_manager"}, "lifecycle.read") is True
    assert has_capability({"lifecycle_manager"}, "metrics.read") is False


def test_metrics_viewer_caps() -> None:
    assert has_capability({"metrics_viewer"}, "metrics.read") is True
    assert has_capability({"metrics_viewer"}, "health.read") is True
    assert has_capability({"metrics_viewer"}, "lifecycle.transition") is False


def test_unknown_role_no_caps() -> None:
    assert has_capability({"alien_role"}, "anything") is False


def test_empty_roles_no_caps() -> None:
    assert has_capability(set(), "metrics.read") is False


def test_empty_capability_returns_false() -> None:
    assert has_capability({"owner"}, "") is False


def test_capability_union_across_multiple_roles() -> None:
    """Holding two roles → caps unioned."""
    caps = {"replay_operator", "metrics_viewer"}
    assert has_capability(caps, "replay.run") is True
    assert has_capability(caps, "metrics.read") is True


# ---------------------------------------------------------------------------
# list_capabilities_for_role + list_roles_with_capability
# ---------------------------------------------------------------------------


def test_list_capabilities_for_known_role() -> None:
    caps = list_capabilities_for_role("replay_operator")
    assert "replay.run" in caps


def test_list_capabilities_for_unknown_role_empty() -> None:
    assert list_capabilities_for_role("alien") == frozenset()


def test_list_roles_with_capability() -> None:
    roles = list_roles_with_capability("metrics.read")
    assert "metrics_viewer" in roles
    assert "owner" in roles  # via * sentinel
    assert "replay_operator" not in roles


def test_list_roles_with_unknown_capability() -> None:
    """Unknown caps surface only owner (via the * sentinel)."""
    roles = list_roles_with_capability("nonexistent.capability")
    # owner has * so always shows up.
    assert "owner" in roles


# ---------------------------------------------------------------------------
# register_role_capabilities + grant_role_capabilities
# ---------------------------------------------------------------------------


def test_register_creates_new_role() -> None:
    snap = register_role_capabilities("custom_role", {"custom.cap"})
    assert isinstance(snap, RoleCapabilities)
    assert "custom.cap" in list_capabilities_for_role("custom_role")


def test_register_merges_by_default() -> None:
    register_role_capabilities("replay_operator", {"replay.export"})
    caps = list_capabilities_for_role("replay_operator")
    assert "replay.run" in caps  # original
    assert "replay.export" in caps  # new


def test_register_replace_when_merge_false() -> None:
    register_role_capabilities(
        "replay_operator", {"replay.only_thing"}, merge=False,
    )
    caps = list_capabilities_for_role("replay_operator")
    assert caps == frozenset({"replay.only_thing"})


def test_register_invalid_role_raises() -> None:
    with pytest.raises(ValueError):
        register_role_capabilities("", {"x"})


def test_grant_role_capabilities_alias_for_merge_true() -> None:
    grant_role_capabilities("replay_operator", {"replay.archive"})
    caps = list_capabilities_for_role("replay_operator")
    assert "replay.archive" in caps
    assert "replay.run" in caps  # original kept


# ---------------------------------------------------------------------------
# Audit emission
# ---------------------------------------------------------------------------


def test_register_emits_chained_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sylion.aeis_v2.rbac_v2.capabilities as mod

    audit = tmp_path / "rbac.jsonl"
    monkeypatch.setattr(mod, "RBAC_V2_AUDIT_LOG_PATH", audit)

    register_role_capabilities("test_role", {"test.cap"}, actor="ops")
    assert audit.exists()
    assert verify_chain(audit) == []
    rows = [
        json.loads(line)["content"]
        for line in audit.read_text(encoding="utf-8").splitlines() if line
    ]
    assert any(r.get("kind") == "rbac_v2.register" for r in rows)
    assert any(r.get("actor") == "ops" for r in rows)


def test_audit_capability_check_emits_chained_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sylion.aeis_v2.rbac_v2.capabilities as mod

    audit = tmp_path / "rbac.jsonl"
    monkeypatch.setattr(mod, "RBAC_V2_AUDIT_LOG_PATH", audit)

    audit_capability_check(
        "user-1", {"replay_operator"}, "replay.run", granted=True,
    )
    rows = [
        json.loads(line)["content"]
        for line in audit.read_text(encoding="utf-8").splitlines() if line
    ]
    assert any(r.get("kind") == "rbac_v2.check" for r in rows)
    check_row = next(r for r in rows if r["kind"] == "rbac_v2.check")
    assert check_row["user_id"] == "user-1"
    assert check_row["granted"] is True


def test_chain_remains_clean_across_many_grants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sylion.aeis_v2.rbac_v2.capabilities as mod

    audit = tmp_path / "rbac.jsonl"
    monkeypatch.setattr(mod, "RBAC_V2_AUDIT_LOG_PATH", audit)

    for i in range(10):
        grant_role_capabilities(f"role_{i}", {f"cap_{i}"})
    assert verify_chain(audit) == []


# ---------------------------------------------------------------------------
# RoleCapabilities serialisation
# ---------------------------------------------------------------------------


def test_role_capabilities_to_dict_sorted() -> None:
    rc = RoleCapabilities(
        role="x", capabilities=frozenset({"c.b", "c.a", "c.c"}),
    )
    d = rc.to_dict()
    assert d["capabilities"] == ["c.a", "c.b", "c.c"]
    json.dumps(d)


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


def test_reset_restores_defaults() -> None:
    register_role_capabilities("custom", {"x.y"})
    assert "custom" in list_roles_with_capability("x.y")
    reset_capability_registry()
    assert list_capabilities_for_role("custom") == frozenset()
    # Defaults are back.
    assert "replay.run" in list_capabilities_for_role("replay_operator")
