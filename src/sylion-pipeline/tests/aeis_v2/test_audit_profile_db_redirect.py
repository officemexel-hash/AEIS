"""W14 round_meta BE-7 — audit profile DB redirect contract.

Asserts the AEIS audit clean-room invariant from
``docs/v2/AEIS_AUDIT_AND_HUMAN_SIMULATION_PLAN.md`` sec 4.2.1: with
``SYLION_AUDIT_PROFILE_ID`` set the runtime sees 0 ideas, 0 projects,
0 tickets — operator state stays in ``sylion_aeis.db`` and the audit
profile lives entirely under ``data/audit/<id>/``.

Coverage:

* ``resolve_db_path`` — env unset, env set with shared-default,
  env set with module-specific default, parent-dir auto-creation,
  ``:memory:`` passthrough.
* IdeaVault, ProjectModeStore, HumanGate, TicketStore, KeyVault —
  smoke tests that the singleton factories honour the redirect.
* Clean-room invariant — fresh audit id starts with empty stores
  even when the operator DB on disk has rows.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from sylion.aeis_v2 import audit_profile as ap


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts without an audit profile."""
    monkeypatch.delenv(ap.ENV_AUDIT_PROFILE_ID, raising=False)


@pytest.fixture()
def audit_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirect _REPO_ROOT into tmp so the test never touches the real repo."""
    monkeypatch.setattr(ap, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(ap, "_PIPELINE_ROOT", tmp_path / "pipeline")
    return tmp_path


# ---------------------------------------------------------------------------
# resolve_db_path() unit tests
# ---------------------------------------------------------------------------


def test_resolve_db_path_no_env_returns_default(tmp_path: Path) -> None:
    target = tmp_path / "module.db"
    assert ap.resolve_db_path(target) == target


def test_resolve_db_path_no_env_no_default_returns_legacy() -> None:
    assert ap.resolve_db_path().as_posix().endswith("data/aeis.db")


def test_resolve_db_path_with_env_redirects_shared(
    monkeypatch: pytest.MonkeyPatch, audit_root: Path,
) -> None:
    """Shared-store basenames collapse onto aeis_clean.db."""
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "round1")
    out = ap.resolve_db_path(Path("sylion_aeis.db"))
    assert out == audit_root / "data" / "audit" / "round1" / "aeis_clean.db"


def test_resolve_db_path_with_env_preserves_module_basename(
    monkeypatch: pytest.MonkeyPatch, audit_root: Path,
) -> None:
    """Module-specific DBs keep their filename under data/audit/<id>/."""
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "round1")
    out = ap.resolve_db_path(audit_root / "data" / "project_freeze.db")
    assert out.name == "project_freeze.db"
    assert "audit/round1" in out.as_posix()


def test_resolve_db_path_creates_parent_dir(
    monkeypatch: pytest.MonkeyPatch, audit_root: Path,
) -> None:
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "round_mkdir")
    out = ap.resolve_db_path(Path("sylion_aeis.db"))
    assert out.parent.is_dir()


def test_resolve_db_path_memory_passthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`:memory:` is a SQLite sentinel — must never be redirected."""
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "round1")
    assert str(ap.resolve_db_path(":memory:")) == ":memory:"


def test_resolve_db_path_idempotent_on_audit_basename(
    monkeypatch: pytest.MonkeyPatch, audit_root: Path,
) -> None:
    """Calling twice with already-redirected path stays inside audit/."""
    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "round1")
    first = ap.resolve_db_path(Path("sylion_aeis.db"))
    second = ap.resolve_db_path(first)
    assert second == first


# ---------------------------------------------------------------------------
# Module smoke tests — singleton factories honour the redirect
# ---------------------------------------------------------------------------


def _disk_db(tmp_path: Path, name: str) -> Path:
    """Return tmp DB path that the module factory will create-on-demand."""
    return tmp_path / name


def test_idea_vault_uses_audit_profile(
    monkeypatch: pytest.MonkeyPatch, audit_root: Path,
) -> None:
    from sylion.cognitive import idea_vault as iv

    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "iv_round")
    iv._vault = None  # noqa: SLF001 — explicit singleton reset for test
    operator_db = audit_root / "sylion_aeis.db"
    vault = iv.get_idea_vault(db_path=str(operator_db))
    try:
        # Vault must point inside audit subtree, NOT at the operator DB.
        assert "audit/iv_round" in vault._db_path.replace("\\", "/")  # noqa: SLF001
        assert vault.list_ideas() == []
    finally:
        iv._vault = None  # noqa: SLF001


def test_project_mode_store_uses_audit_profile(
    monkeypatch: pytest.MonkeyPatch, audit_root: Path,
) -> None:
    from sylion.project_mode import store as pms

    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "pm_round")
    monkeypatch.setenv("SYLION_DB_PATH", str(audit_root / "sylion_aeis.db"))
    monkeypatch.setattr(pms, "_store", None, raising=False)
    s = pms.ProjectModeStore()  # uses module-level _db_path() helper
    assert "audit/pm_round" in s.db_path.replace("\\", "/")


def test_human_gate_uses_audit_profile(
    monkeypatch: pytest.MonkeyPatch, audit_root: Path,
) -> None:
    from sylion.governance import human_gate as hg

    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "hg_round")
    hg._instance = None  # noqa: SLF001
    operator_db = audit_root / "sylion_aeis.db"
    gate = hg.get_human_gate(db_path=str(operator_db))
    try:
        assert "audit/hg_round" in gate._db_path.replace("\\", "/")  # noqa: SLF001
    finally:
        hg._instance = None  # noqa: SLF001


def test_ticket_store_uses_audit_profile(
    monkeypatch: pytest.MonkeyPatch, audit_root: Path,
) -> None:
    from sylion.governance import ticket as tk

    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "tk_round")
    tk._instance = None  # noqa: SLF001
    operator_db = audit_root / "sylion_aeis.db"
    store = tk.reset_ticket_store(db_path=str(operator_db))
    try:
        assert "audit/tk_round" in store._db_path.replace("\\", "/")  # noqa: SLF001
        assert store.list() == []
    finally:
        tk._instance = None  # noqa: SLF001


def test_key_vault_uses_audit_profile(
    monkeypatch: pytest.MonkeyPatch, audit_root: Path,
) -> None:
    from sylion.security import key_vault as kv

    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "kv_round")
    kv._vault = None  # noqa: SLF001
    operator_db = audit_root / "sylion_aeis.db"
    vault = kv.reset_key_vault(db_path=str(operator_db), vault_secret="x")
    try:
        # KeyVault stores db_path on attribute self._db_path or self.db_path.
        # Inspect both for resilience across refactors.
        path_attr = getattr(vault, "_db_path", None) or getattr(vault, "db_path", "")
        assert "audit/kv_round" in str(path_attr).replace("\\", "/")
    finally:
        kv._vault = None  # noqa: SLF001


def test_chat_engine_default_uses_audit_profile(
    monkeypatch: pytest.MonkeyPatch, audit_root: Path,
) -> None:
    from sylion.cognitive import chat_engine as ce

    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "chat_round")
    ce._engine = None  # noqa: SLF001
    chat = ce.get_chat_engine()
    try:
        assert "audit/chat_round" in chat._db_path.replace("\\", "/")  # noqa: SLF001
        assert chat._db_path.replace("\\", "/").endswith("/chat_engine.db")  # noqa: SLF001
    finally:
        ce._engine = None  # noqa: SLF001


# ---------------------------------------------------------------------------
# Clean-room invariant — sec 4.2.1
# ---------------------------------------------------------------------------


def test_clean_audit_state_zero_ideas_zero_tickets(
    monkeypatch: pytest.MonkeyPatch, audit_root: Path,
) -> None:
    """With audit profile set the new runtime sees no operator state.

    We seed a fake operator DB with one row to prove the audit subtree
    is genuinely independent (operator data must NOT leak in).
    """
    from sylion.cognitive import idea_vault as iv
    from sylion.governance import ticket as tk

    operator_db = audit_root / "sylion_aeis.db"
    # Seed operator DB with a fake table+row so leak is detectable.
    conn = sqlite3.connect(operator_db)
    conn.execute(
        "CREATE TABLE ideas (idea_id TEXT, title TEXT)"
    )
    conn.execute("INSERT INTO ideas VALUES ('op1', 'operator-only')")
    conn.commit()
    conn.close()

    monkeypatch.setenv(ap.ENV_AUDIT_PROFILE_ID, "clean_round")
    iv._vault = None  # noqa: SLF001
    tk._instance = None  # noqa: SLF001
    try:
        vault = iv.get_idea_vault(db_path=str(operator_db))
        store = tk.reset_ticket_store(db_path=str(operator_db))
        # Both stores see ZERO rows — the operator-only row is firewalled.
        assert vault.list_ideas() == []
        assert store.list() == []
        # Sanity: the operator DB still contains the seeded row.
        conn = sqlite3.connect(operator_db)
        rows = list(conn.execute("SELECT idea_id FROM ideas"))
        conn.close()
        assert rows == [("op1",)]
    finally:
        iv._vault = None  # noqa: SLF001
        tk._instance = None  # noqa: SLF001
