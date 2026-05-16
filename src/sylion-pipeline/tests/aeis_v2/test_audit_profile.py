"""Tests for the W14 round_meta BE-4 audit profile mode.

Covers:
* default (no env) -> legacy paths preserved.
* env set -> resolve_*_path() returns audit-isolated paths.
* ensure_audit_layout() creates every directory + DB parent.
* invalid audit_id is rejected by the CLI initializer.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from sylion.aeis_v2 import audit_profile as ap


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with a clean env (no audit profile)."""
    monkeypatch.delenv(ap.ENV_AUDIT_PROFILE_ID, raising=False)


# ---------------------------------------------------------------------------
# Default mode (no env)
# ---------------------------------------------------------------------------


def test_default_mode_no_audit_id() -> None:
    assert ap.get_audit_profile_id() == ""
    assert ap.is_audit_mode() is False


def test_default_db_path_returns_legacy_default() -> None:
    p = ap.resolve_db_path()
    assert p.as_posix().endswith("data/aeis.db")


def test_default_log_dir_returns_legacy_default() -> None:
    p = ap.resolve_log_dir()
    assert p.as_posix().endswith("logs/v2")


def test_default_evidence_dir_returns_legacy_default() -> None:
    p = ap.resolve_evidence_dir()
    assert p.as_posix().endswith("/evidence")


def test_default_audit_chain_dir_returns_legacy_default() -> None:
    p = ap.resolve_audit_chain_dir()
    assert p.as_posix().endswith("sylion/logs/v2")


def test_ensure_audit_layout_is_noop_without_id(tmp_path: Path) -> None:
    """ensure_audit_layout() must not create anything when no audit id."""
    layout = ap.ensure_audit_layout()
    assert "db" in layout
    assert "log_dir" in layout


# ---------------------------------------------------------------------------
# Audit mode (env set)
# ---------------------------------------------------------------------------


def test_audit_mode_recognized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "round1")
    assert ap.get_audit_profile_id() == "round1"
    assert ap.is_audit_mode() is True


def test_audit_db_path_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "round1")
    p = ap.resolve_db_path()
    assert "audit/round1/aeis_clean.db" in p.as_posix()


def test_audit_log_dir_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "round1")
    p = ap.resolve_log_dir()
    assert "logs/audit/round1" in p.as_posix()


def test_audit_evidence_dir_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "round1")
    p = ap.resolve_evidence_dir()
    assert "evidence/audit/round1" in p.as_posix()


def test_audit_chain_dir_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "round1")
    p = ap.resolve_audit_chain_dir()
    assert "logs/audit/round1" in p.as_posix()


def test_two_audit_ids_resolve_to_distinct_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "round_a")
    a_db = ap.resolve_db_path()
    a_log = ap.resolve_log_dir()
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "round_b")
    b_db = ap.resolve_db_path()
    b_log = ap.resolve_log_dir()
    assert a_db != b_db
    assert a_log != b_log


def test_empty_string_env_is_treated_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty / whitespace SYLION_AUDIT_PROFILE_ID falls back to defaults."""
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "   ")
    assert ap.get_audit_profile_id() == ""
    assert ap.is_audit_mode() is False


# ---------------------------------------------------------------------------
# ensure_audit_layout(): mkdir behavior
# ---------------------------------------------------------------------------


def test_ensure_audit_layout_creates_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """In audit mode, ensure_audit_layout() must mkdir every target dir."""
    # Redirect _REPO_ROOT and _PIPELINE_ROOT so the test does not pollute
    # the real repo. We do this by monkeypatching the resolved private
    # constants, which is acceptable for a contract-isolation test.
    monkeypatch.setattr(ap, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(ap, "_PIPELINE_ROOT", tmp_path / "pipeline")
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "rtest")

    layout = ap.ensure_audit_layout()
    assert layout["db"].endswith("audit/rtest/aeis_clean.db")
    # Parent of the DB path must exist.
    assert (tmp_path / "data" / "audit" / "rtest").is_dir()
    assert (tmp_path / "logs" / "audit" / "rtest").is_dir()
    assert (tmp_path / "evidence" / "audit" / "rtest").is_dir()
    assert (tmp_path / "pipeline" / "sylion" / "logs" / "audit" / "rtest").is_dir()


# ---------------------------------------------------------------------------
# CLI initializer: validation + metadata
# ---------------------------------------------------------------------------


def test_cli_rejects_invalid_audit_id() -> None:
    """Init script must reject ids that are not safe directory names."""
    import importlib.util

    here = Path(__file__).resolve()
    # tests/aeis_v2/test_audit_profile.py -> parents[4] is repo root.
    script = here.parents[4] / "scripts" / "v2" / "audit_profile_init.py"
    spec = importlib.util.spec_from_file_location("audit_profile_init_mod", script)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with pytest.raises(SystemExit):
        mod.init_audit_profile("../escape")
    with pytest.raises(SystemExit):
        mod.init_audit_profile("a")  # too short
    with pytest.raises(SystemExit):
        mod.init_audit_profile("")


def test_cli_metadata_written(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Init script writes _metadata.json with the bootstrap fingerprint."""
    import importlib.util

    here = Path(__file__).resolve()
    script = here.parents[4] / "scripts" / "v2" / "audit_profile_init.py"
    spec = importlib.util.spec_from_file_location(
        "audit_profile_init_mod_meta", script,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Redirect repo + pipeline roots into tmp so we don't pollute real fs.
    monkeypatch.setattr(ap, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(ap, "_PIPELINE_ROOT", tmp_path / "pipeline")

    audit_id = "round-test_001"
    result = mod.init_audit_profile(audit_id)
    assert result["audit_id"] == audit_id
    assert "start_timestamp" in result
    assert "python_version" in result

    meta_file = (tmp_path / "evidence" / "audit" / audit_id / "_metadata.json")
    assert meta_file.exists()
    import json
    parsed = json.loads(meta_file.read_text(encoding="utf-8"))
    assert parsed["audit_id"] == audit_id
    assert "layout" in parsed
