"""Regression tests for the W14 E3 review-fix pass.

Each test pins an issue surfaced by Codex / Kimi / self-audit.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from sylion.aeis.testing.branches import BranchManager, BranchSnapshot
from sylion.aeis.testing.ontology import OntologyStore


@pytest.fixture
def store() -> OntologyStore:
    return OntologyStore()


@pytest.fixture
def mgr(store: OntologyStore) -> BranchManager:
    return BranchManager(ontology=store)


# ---------------------------------------------------------------------------
# Codex bug — create_branch positional contract from the brief
# ---------------------------------------------------------------------------


def test_create_branch_positional_signature_matches_brief(mgr) -> None:
    """Brief positional: (branch_type, parent_branch_id, project_id, sot, mp)."""
    branch = mgr.create_branch(
        "repair",          # branch_type
        "main",            # parent_branch_id
        "proj_abc",        # project_id
        "sot_v1",          # sot_version
        "mp_v1",           # masterplan_version
    )
    assert branch.branch_type == "repair"
    assert branch.parent_branch_id == "main"
    assert branch.project_id == "proj_abc"


def test_create_branch_none_parent_defaults_to_main(mgr) -> None:
    branch = mgr.create_branch(
        "test",
        parent_branch_id=None,
        project_id="proj_x",
        sot_version="sot_v1",
        masterplan_version="mp_v1",
    )
    assert branch.parent_branch_id == "main"


# ---------------------------------------------------------------------------
# Codex bug + Kimi attack — merge HARD invariants are NEVER bypassed by force
# ---------------------------------------------------------------------------


def test_merge_force_does_not_bypass_branch_id_main(mgr, monkeypatch) -> None:
    """A hijacked Branch object whose branch_id reads 'main' (via attribute
    spoofing) must still be rejected even when caller passes force=True."""
    from sylion.aeis.testing.ontology.objects import Branch

    fake = Branch(
        branch_id="br_legitcb1234",
        branch_type="repair",
        parent_branch_id="main",
        project_id="proj_x",
        sot_version="sot_v1",
        masterplan_version="mp_v1",
        state="open",
        created_by="alice",
    )
    # Tamper after construction (simulating a corrupted persistence row).
    fake.branch_id = "main"

    monkeypatch.setattr(mgr._ontology, "get", lambda cls, oid: fake)
    result = mgr.merge("main", force=True)
    assert result["status"] == "rejected"
    assert "branch_id_is_main" in result.get("hard_violations", [])


def test_merge_force_rejects_main_with_case_variants(mgr, monkeypatch) -> None:
    """' Main\\n', 'MAIN', 'mAiN' must all hit the normalization rejection."""
    from sylion.aeis.testing.ontology.objects import Branch

    for variant in ("MAIN", " main", "main\n", "Main"):
        fake = Branch(
            branch_id="br_legitcb1234",
            branch_type="repair",
            parent_branch_id="main",
            project_id="proj_x",
            sot_version="sot_v1",
            masterplan_version="mp_v1",
            state="open",
            created_by="alice",
        )
        fake.branch_id = variant
        monkeypatch.setattr(mgr._ontology, "get", lambda cls, oid, fake=fake: fake)
        result = mgr.merge(variant, force=True)
        assert result["status"] == "rejected"
        assert "attempted_merge_of_main" in result.get("hard_violations", [])


# ---------------------------------------------------------------------------
# Codex bug — list_changes returns the right primary key per kind
# ---------------------------------------------------------------------------


def test_list_changes_uses_correct_primary_key_per_kind(store) -> None:
    """TestRun's PK is run_id, not testrun_id; PatchProposal's PK is
    proposal_id, not patchproposal_id. The earlier dynamic name-derivation
    fell back to proposal_id for TestRun rows, which was wrong."""
    from sylion.aeis.testing.ontology.objects import (
        Finding, PatchProposal, TestRun,
    )
    finding = Finding(title="x", description="y", discovered_by="z")
    store.create(finding)
    proposal = PatchProposal(
        finding_id=finding.finding_id,
        branch_id="br_abc12345abcd",
        diff_text="x",
        files_touched=["a.py"],
        diff_lines_added=1,
        diff_lines_removed=0,
        risk_assessment={},
        tests_to_run=["pytest"],
        proposed_by="claude",
    )
    run = TestRun(branch_id="br_abc12345abcd", trace_id="trace_x")
    store.create(proposal)
    store.create(run)

    mgr = BranchManager(ontology=store)
    changes = mgr.list_changes("br_abc12345abcd")
    by_kind = {c["kind"]: c["id"] for c in changes}
    assert by_kind["PatchProposal"] == proposal.proposal_id
    assert by_kind["TestRun"] == run.run_id


# ---------------------------------------------------------------------------
# Spec coverage — branches/snapshot.py file-backed isolation
# ---------------------------------------------------------------------------


def test_snapshot_creates_sim_prefixed_file(tmp_path: Path) -> None:
    snap = BranchSnapshot.create_for(
        branch_id="br_abc12345",
        base_dir=tmp_path,
    )
    try:
        assert snap.path.exists()
        assert snap.path.name.startswith("sim_br_abc12345_")
        assert snap.path.suffix == ".db"
        assert snap.hash  # 64 chars
    finally:
        snap.discard()


def test_snapshot_discard_idempotent(tmp_path: Path) -> None:
    snap = BranchSnapshot.create_for(
        branch_id="br_xyz98765", base_dir=tmp_path,
    )
    assert snap.discard() is True
    assert snap.discard() is False
    assert not snap.path.exists()


def test_snapshot_refuses_main_in_branch_id(tmp_path: Path) -> None:
    """Defensive: cannot produce a sim_main_*.db file."""
    with pytest.raises(ValueError, match="main"):
        BranchSnapshot.create_for(branch_id="MAIN", base_dir=tmp_path)


@pytest.mark.parametrize("evil_branch_id", [
    "../../../etc/passwd",
    "..\\..\\..\\windows\\system32",
    "br/with/slashes",
    "br\\with\\backslashes",
    "br..traversal",
    ".hidden",
    "br\x00null",
    "br\nnewline",
    "br with spaces",
    "br$shell$cmd",
])
def test_snapshot_rejects_path_traversal(tmp_path: Path, evil_branch_id: str) -> None:
    """Kimi attack #1: branch_id must not be able to escape sandbox dir."""
    with pytest.raises(ValueError, match="branch_id"):
        BranchSnapshot.create_for(branch_id=evil_branch_id, base_dir=tmp_path)


def test_snapshot_cleanup_orphans_skips_active(tmp_path: Path) -> None:
    keep = BranchSnapshot.create_for(branch_id="br_keep", base_dir=tmp_path)
    drop = BranchSnapshot.create_for(branch_id="br_drop", base_dir=tmp_path)
    try:
        removed = BranchSnapshot.cleanup_orphans(
            active_branch_ids={"br_keep"},
            base_dir=tmp_path,
        )
        # `drop` should have been removed; `keep` remains.
        removed_names = {p.name for p in removed}
        assert any("br_drop" in n for n in removed_names)
        assert keep.path.exists()
        assert not drop.path.exists()
    finally:
        keep.discard()


def test_snapshot_copies_source_db(tmp_path: Path) -> None:
    """Source DB is byte-copied via SQLite backup (preserves WAL)."""
    src = tmp_path / "source.db"
    conn = sqlite3.connect(str(src))
    conn.execute("CREATE TABLE foo (x INTEGER)")
    conn.execute("INSERT INTO foo VALUES (42)")
    conn.commit()
    conn.close()

    snap = BranchSnapshot.create_for(
        branch_id="br_xfer",
        source_db=src,
        base_dir=tmp_path,
    )
    try:
        c2 = sqlite3.connect(str(snap.path))
        rows = c2.execute("SELECT x FROM foo").fetchall()
        c2.close()
        assert rows == [(42,)]
    finally:
        snap.discard()


# ---------------------------------------------------------------------------
# Spec coverage — change_proposal extended append-only with branch_id
# ---------------------------------------------------------------------------


def test_change_proposal_has_optional_branch_id() -> None:
    from sylion.governance.change_proposal import ChangeProposal

    legacy = ChangeProposal(title="t", description="d")
    assert legacy.branch_id is None  # default

    branched = ChangeProposal(
        title="t", description="d", branch_id="br_abcdef",
    )
    assert branched.branch_id == "br_abcdef"
