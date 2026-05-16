"""W14 BE-6 — round_meta post-approval listener tests.

These tests cover the missing seam between
``api/projects_freeze_routes.py`` (BE-1/BE-2/BE-3) and the project
state mutation that flips ``canon_frozen_at`` /
``masterplan_frozen_at`` / ``build_authorized_at``.

Setup pattern:

* a fresh in-memory ``ProjectModeStore`` (via ``SYLION_DB_PATH=:memory:``)
* a fresh in-memory ``TicketStore`` via ``reset_ticket_store(':memory:')``
* hook registry cleared then ``register_round_meta_hook()``
* audit-chain dir redirected to ``tmp_path`` so completion entries are
  isolated per test

Each test asserts BOTH the project columns and (where relevant) the
matching ``round_meta.<round>.completed`` audit row.
"""
from __future__ import annotations

import importlib
import threading
from pathlib import Path
from typing import Any

import pytest

import sylion.project_mode.round_meta_hooks as rm_hooks
from sylion.aeis_v2 import audit_profile as audit_profile_mod
from sylion.aeis_v2.audit_chain import verify_chain
from sylion.governance import tickets as tickets_mod
from sylion.governance.ticket import (
    GovernanceTicket,
    reset_ticket_store,
)
from sylion.project_mode import store as store_mod
from sylion.project_mode.store import ProjectModeStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_store(monkeypatch: pytest.MonkeyPatch) -> ProjectModeStore:
    """Spin up a fresh ProjectModeStore against :memory: for each test
    and patch ``get_project_mode_store`` so the hook reads the same
    instance."""
    fresh = ProjectModeStore(db_path=":memory:")
    fresh._get_conn()  # force migrate before patching
    monkeypatch.setattr(store_mod, "_store", fresh)
    monkeypatch.setattr(store_mod, "get_project_mode_store", lambda: fresh)
    # The hook module imports get_project_mode_store lazily inside _store(),
    # so the monkeypatch above is enough — but be paranoid in case the
    # symbol got bound elsewhere.
    return fresh


@pytest.fixture
def isolated_ticket_store():
    """Reset the governance ticket store singleton to a :memory: backend."""
    reset_ticket_store(":memory:")
    yield
    reset_ticket_store(":memory:")


@pytest.fixture
def chain_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirect the audit chain dir to tmp_path so completion entries
    don't bleed across tests."""
    target = tmp_path / "chains"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        audit_profile_mod, "resolve_audit_chain_dir", lambda *a, **kw: target,
    )
    return target


@pytest.fixture(autouse=True)
def fresh_hook_registry(
    isolated_store: ProjectModeStore,
    isolated_ticket_store,
    chain_dir: Path,
):
    """Re-register only our hook so test ordering is deterministic."""
    tickets_mod.clear_post_resolve_hooks()
    # Force module-level _REGISTERED back to False then re-register so
    # the hook lands in the freshly-cleared registry.
    rm_hooks._REGISTERED = False
    rm_hooks.register_round_meta_hook()
    yield
    tickets_mod.clear_post_resolve_hooks()
    rm_hooks._REGISTERED = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    store: ProjectModeStore,
    project_id: str = "proj_alpha",
    *,
    canon: str = "Source of truth body.",
    masterplan: str = "Masterplan body.",
    canon_frozen: bool = False,
    masterplan_frozen: bool = False,
    build_authorized: bool = False,
) -> dict[str, Any]:
    return store.upsert_project({
        "project_id": project_id,
        "title": "alpha",
        "idea": "demo",
        "constraints": "",
        "canonical_book": canon,
        "masterplan": masterplan,
        "approvals": {
            "book": canon_frozen,
            "operating_model": masterplan_frozen,
        },
        "canon_frozen_at": 1.0 if canon_frozen else None,
        "masterplan_frozen_at": 1.0 if masterplan_frozen else None,
        "build_authorized_at": 1.0 if build_authorized else None,
    })


def _submit_freeze_ticket(
    project_id: str, action: str, target: str,
    extra: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "action": action, "target": target, "requires_human_gate": True,
    }
    if extra:
        payload.update(extra)
    return tickets_mod.submit(GovernanceTicket(
        origin="workspace",
        project_id=project_id,
        decision_class="D3",
        gate_type="production",
        priority="P1",
        title=f"freeze {target}",
        summary=f"freeze {target} on {project_id}",
        payload=payload,
        requested_by="test",
    ))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_canon_freeze_post_approval_sets_timestamp(
    isolated_store: ProjectModeStore, chain_dir: Path,
) -> None:
    _make_project(isolated_store)
    ticket_id = _submit_freeze_ticket(
        "proj_alpha", "project_freeze", "canon",
    )

    assert tickets_mod.resolve(ticket_id, "approved", reviewer="op1") is True

    project = isolated_store.get_project("proj_alpha")
    assert project is not None
    assert project["canon_frozen_at"] is not None
    assert project["canon_frozen_at"] > 0
    assert project["canon_hash"]  # non-empty sha256
    # Legacy back-compat: approval_book must also flip.
    assert project["approvals"]["book"] is True
    assert "book_pending_ticket_id" not in project["approvals"]
    # Audit chain entry written.
    chain = chain_dir / "canon_freeze.jsonl"
    assert chain.exists()
    assert verify_chain(chain) == []
    text = chain.read_text(encoding="utf-8")
    assert "round_meta.canon.freeze.completed" in text


def test_masterplan_freeze_post_approval_sets_timestamp(
    isolated_store: ProjectModeStore, chain_dir: Path,
) -> None:
    _make_project(isolated_store, canon_frozen=True)
    ticket_id = _submit_freeze_ticket(
        "proj_alpha", "project_freeze", "masterplan",
    )

    assert tickets_mod.resolve(ticket_id, "approved", reviewer="op1") is True

    project = isolated_store.get_project("proj_alpha")
    assert project is not None
    assert project["masterplan_frozen_at"] is not None
    assert project["masterplan_hash"]
    # Legacy compat for operating_model approval.
    assert project["approvals"]["operating_model"] is True
    assert "operating_model_pending_ticket_id" not in project["approvals"]
    assert project["phase"] == "build_authorization"
    chain = chain_dir / "masterplan_freeze.jsonl"
    assert chain.exists()
    assert verify_chain(chain) == []
    assert "round_meta.masterplan.freeze.completed" in chain.read_text("utf-8")


def test_build_authorize_post_approval_sets_timestamp_and_status(
    isolated_store: ProjectModeStore, chain_dir: Path,
) -> None:
    _make_project(
        isolated_store, canon_frozen=True, masterplan_frozen=True,
    )
    ticket_id = _submit_freeze_ticket(
        "proj_alpha", "project_build_authorize", "build",
        extra={
            "cost_cap_usd": 50.0,
            "autonomy_level": "L2",
            "external_actions_policy": {"vps_deploy": "human_gate"},
        },
    )

    assert tickets_mod.resolve(ticket_id, "approved", reviewer="op1") is True

    project = isolated_store.get_project("proj_alpha")
    assert project is not None
    assert project["build_authorized_at"] is not None
    assert "build_pending_ticket_id" not in project["approvals"]
    assert project["cost_cap_usd"] == 50.0
    assert project["autonomy_level"] == "L2"
    assert project["status"] in {"building", "completed", "blocked_on_audit"}
    assert project["phase"] in {"execution", "broadcast", "governance"}
    chain = chain_dir / "build_authorize.jsonl"
    assert chain.exists()
    assert verify_chain(chain) == []
    assert "round_meta.build.authorize.completed" in chain.read_text("utf-8")


def test_post_approval_idempotent(
    isolated_store: ProjectModeStore, chain_dir: Path,
) -> None:
    """Resolve fires once, the subsequent re-resolve is a no-op (state
    is already 'approved') and the listener also has its own
    ``frozen_at != None`` short-circuit."""
    _make_project(isolated_store)
    ticket_id = _submit_freeze_ticket(
        "proj_alpha", "project_freeze", "canon",
    )

    assert tickets_mod.resolve(ticket_id, "approved", reviewer="op1") is True
    project_after_first = isolated_store.get_project("proj_alpha")
    assert project_after_first is not None
    first_ts = project_after_first["canon_frozen_at"]

    # Second resolve returns False (ticket already final) and must not
    # mutate the timestamp.
    assert tickets_mod.resolve(ticket_id, "approved", reviewer="op1") is False
    project_after_second = isolated_store.get_project("proj_alpha")
    assert project_after_second is not None
    assert project_after_second["canon_frozen_at"] == first_ts

    # Direct re-fire of the listener with the same project must also
    # be a no-op (defence-in-depth against future retry paths).
    fake_ticket = type("T", (), {
        "ticket_id": ticket_id,
        "project_id": "proj_alpha",
        "payload": {"action": "project_freeze", "target": "canon"},
    })()
    rm_hooks.round_meta_post_resolve(fake_ticket, "approved")
    assert isolated_store.get_project(
        "proj_alpha",
    )["canon_frozen_at"] == first_ts


def test_post_approval_only_fires_on_approved(
    isolated_store: ProjectModeStore, chain_dir: Path,
) -> None:
    _make_project(isolated_store)
    ticket_id = _submit_freeze_ticket(
        "proj_alpha", "project_freeze", "canon",
    )

    assert tickets_mod.resolve(
        ticket_id, "rejected", reviewer="op1", reason="nope",
    ) is True

    project = isolated_store.get_project("proj_alpha")
    assert project is not None
    assert project["canon_frozen_at"] is None
    assert project["canon_hash"] == ""
    assert project["approvals"]["book"] is False
    chain = chain_dir / "canon_freeze.jsonl"
    # Chain might not exist (no completion entry) — assert no completion line.
    if chain.exists():
        assert "round_meta.canon.freeze.completed" not in chain.read_text("utf-8")


def test_legacy_approval_book_compat(
    isolated_store: ProjectModeStore, chain_dir: Path,
) -> None:
    """Setting approvals.book=True via upsert still works and is
    independent of the new canon_frozen_at column. Legacy callers that
    have not been migrated to the new column must keep functioning."""
    project = isolated_store.upsert_project({
        "project_id": "proj_legacy",
        "title": "legacy",
        "idea": "legacy idea",
        "constraints": "",
        "canonical_book": "legacy canon",
        "approvals": {"book": True, "operating_model": True},
    })
    assert project["approvals"]["book"] is True
    assert project["approvals"]["operating_model"] is True
    # Round-trip through get_project to ensure the legacy approvals
    # survive a read alongside the new (still NULL) round_meta columns.
    fetched = isolated_store.get_project("proj_legacy")
    assert fetched is not None
    assert fetched["approvals"]["book"] is True
    assert fetched["approvals"]["operating_model"] is True
    assert fetched["canon_frozen_at"] is None
    assert fetched["masterplan_frozen_at"] is None
    assert fetched["build_authorized_at"] is None


def test_schema_migration_idempotent(tmp_path: Path) -> None:
    """Calling ``_migrate`` twice on the same connection must not raise
    duplicate-column errors and must leave all 7 round_meta columns
    in place."""
    db_path = str(tmp_path / "idem.db")
    s = ProjectModeStore(db_path=db_path)
    conn = s._get_conn()  # first migrate
    s._migrate(conn)      # second migrate — must be no-op
    s._migrate(conn)      # third migrate — still no-op

    cols = {row["name"] for row in conn.execute(
        "PRAGMA table_info(project_projects)",
    ).fetchall()}
    for required in (
        "canon_frozen_at",
        "masterplan_frozen_at",
        "build_authorized_at",
        "canon_hash",
        "masterplan_hash",
        "cost_cap_usd",
        "autonomy_level",
    ):
        assert required in cols, f"missing column after migrate: {required}"
    s.close()


def test_post_approval_concurrent_resolves_single_completion(
    isolated_store: ProjectModeStore, chain_dir: Path,
) -> None:
    """If the operator console double-clicks resolve, only ONE
    completion row must land in the chain (idempotency under
    concurrency)."""
    _make_project(isolated_store)
    ticket_id = _submit_freeze_ticket(
        "proj_alpha", "project_freeze", "canon",
    )

    statuses: list[bool] = []
    statuses_lock = threading.Lock()

    def _do_resolve() -> None:
        ok = tickets_mod.resolve(ticket_id, "approved", reviewer="op1")
        with statuses_lock:
            statuses.append(ok)

    threads = [threading.Thread(target=_do_resolve) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one resolve transitions; the others see a final ticket.
    assert statuses.count(True) == 1
    assert statuses.count(False) == 9
    chain = chain_dir / "canon_freeze.jsonl"
    assert chain.exists()
    completion_lines = [
        line for line in chain.read_text("utf-8").splitlines()
        if "round_meta.canon.freeze.completed" in line
    ]
    assert len(completion_lines) == 1, (
        f"expected exactly one completion line, got {len(completion_lines)}"
    )
