"""W14 E7 review-fix regression tests.

Pins issues from Codex HOLD 91% (1 bug + 3 spec drifts) and self-audit
(thread-safety, project_id validation, severity validation, ticket
project_id leak, approver mandatory).
"""
from __future__ import annotations

import threading

import pytest

from sylion.aeis.testing.charter import CharterStore
from sylion.aeis.testing.findings import FindingStore
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import Finding, TestCharter


@pytest.fixture
def store():
    return OntologyStore()


def _make_charter(store, status="draft") -> TestCharter:
    c = TestCharter(
        project_id="proj_demo123def456",
        source_of_truth_version="v1",
        masterplan_version="v1",
        scope={"x": 1},
        required_test_classes=["T2"],
        required_personas=["operator_beginner"],
        required_evidence=["test_result"],
        release_blockers=["P0"],
        auto_repair_policy={},
        approval={"d_level": "D3"},
        status=status,
    )
    store.create(c)
    return c


# ---------------------------------------------------------------------------
# Self-audit — CharterStore.approve requires non-empty approver
# ---------------------------------------------------------------------------


def test_charter_approve_rejects_empty_approver(store):
    c = _make_charter(store, status="proposed")
    cs = CharterStore(ontology=store)
    with pytest.raises(ValueError, match="approver"):
        cs.approve(c.charter_id, approver="")


def test_charter_approve_rejects_whitespace_approver(store):
    c = _make_charter(store, status="proposed")
    cs = CharterStore(ontology=store)
    with pytest.raises(ValueError, match="approver"):
        cs.approve(c.charter_id, approver="   ")


def test_charter_approve_accepts_valid_approver(store):
    c = _make_charter(store, status="proposed")
    cs = CharterStore(ontology=store)
    out = cs.approve(c.charter_id, approver="alice", hg_ticket_id="hg_x")
    assert out.status == "approved"
    assert out.hg_ticket_id == "hg_x"
    assert out.approved_at > 0


# ---------------------------------------------------------------------------
# Self-audit — concurrent approve only one wins
# ---------------------------------------------------------------------------


def test_charter_concurrent_approve_only_one_wins(store):
    c = _make_charter(store, status="proposed")
    cs = CharterStore(ontology=store)
    results: list = []
    barrier = threading.Barrier(8)

    def worker():
        try:
            barrier.wait()
            results.append(cs.approve(c.charter_id, approver="alice"))
        except (ValueError, RuntimeError) as exc:
            results.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    successes = [r for r in results if isinstance(r, TestCharter)]
    failures = [r for r in results if isinstance(r, Exception)]
    assert len(successes) == 1
    assert len(failures) == 7


# ---------------------------------------------------------------------------
# Self-audit — list_for_project rejects path-traversal / bad project_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_pid", [
    "", "demo_no_prefix", "../proj_x", "proj_x/etc/passwd",
    "proj_x\\windows", "proj_x\x00null", "proj_x\nnewline",
])
def test_charter_list_for_project_rejects_bad_id(store, bad_pid):
    cs = CharterStore(ontology=store)
    with pytest.raises(ValueError, match="project_id"):
        cs.list_for_project(bad_pid)


def test_charter_list_for_project_filters_correctly(store):
    other = TestCharter(
        project_id="proj_other_aaaaaa", source_of_truth_version="v1",
        masterplan_version="v1", scope={"x": 1},
        required_test_classes=["T2"], required_personas=["op"],
        required_evidence=["e"], release_blockers=["P0"],
        auto_repair_policy={}, approval={"d_level": "D2"},
    )
    store.create(other)
    _make_charter(store)  # proj_demo123def456
    cs = CharterStore(ontology=store)
    demo_only = cs.list_for_project("proj_demo123def456")
    assert len(demo_only) == 1
    assert demo_only[0].project_id == "proj_demo123def456"


# ---------------------------------------------------------------------------
# Self-audit — FindingStore.list_open validates severity filter
# ---------------------------------------------------------------------------


def test_finding_list_open_rejects_invalid_severity(store):
    fs = FindingStore(ontology=store)
    with pytest.raises(ValueError, match="severity"):
        fs.list_open(severity="P9")


def test_finding_list_open_severity_none_returns_all(store):
    fs = FindingStore(ontology=store)
    f1 = Finding(severity="P0", d_level="D3", title="x",
                 description="d", discovered_by="t")
    f2 = Finding(severity="P3", d_level="D1", title="y",
                 description="d", discovered_by="t")
    store.create(f1)
    store.create(f2)
    out = fs.list_open()
    assert len(out) == 2


def test_finding_list_open_severity_filter_applies(store):
    fs = FindingStore(ontology=store)
    store.create(Finding(severity="P0", d_level="D3", title="x",
                         description="d", discovered_by="t"))
    store.create(Finding(severity="P2", d_level="D2", title="y",
                         description="d", discovered_by="t"))
    p0_only = fs.list_open(severity="P0")
    assert len(p0_only) == 1


# ---------------------------------------------------------------------------
# Codex bug #1 — Finding.create with mirror_to_ticket=True still works for
# D2+ (the documented gating condition)
# ---------------------------------------------------------------------------


def test_finding_mirror_lifts_project_id_from_context(store):
    """ticket_id field carrying proj_* token is reflected in mirror payload."""

    class StubTickets:
        def __init__(self):
            self.submitted: list = []

        def submit(self, ticket):
            self.submitted.append(ticket)
            return f"tkt_{len(self.submitted):04d}"

    tickets = StubTickets()
    fs = FindingStore(ontology=store, tickets=tickets)
    f = Finding(
        severity="P1", d_level="D3", title="bug",
        description="proj_demo123def456 has flake",
        discovered_by="evaluator",
    )
    out = fs.create(f, mirror_to_ticket=True)
    assert out.ticket_id is not None
    assert tickets.submitted[0].project_id == "proj_demo123def456"


def test_finding_mirror_falls_back_to_proj_unknown(store):
    """No proj_* in context -> conservative ``proj_unknown`` (not empty)."""

    class StubTickets:
        def __init__(self):
            self.submitted: list = []

        def submit(self, ticket):
            self.submitted.append(ticket)
            return f"tkt_{len(self.submitted):04d}"

    tickets = StubTickets()
    fs = FindingStore(ontology=store, tickets=tickets)
    f = Finding(
        severity="P0", d_level="D2", title="missing context",
        description="no project marker",
        discovered_by="evaluator",
    )
    fs.create(f, mirror_to_ticket=True)
    assert tickets.submitted[0].project_id == "proj_unknown"


# ---------------------------------------------------------------------------
# Self-audit — Finding.transition is atomic under concurrency
# ---------------------------------------------------------------------------


def test_finding_r_status_direct_update_blocked_by_store(store):
    """Kimi E7 attack #1: callers bypassing FindingStore.transition() and
    going straight to ontology.update() must STILL hit the R0-R9 graph."""
    f = Finding(severity="P2", d_level="D2", title="x",
                description="d", discovered_by="t", r_status="OPEN")
    store.create(f)
    f.r_status = "VERIFIED"  # illegal jump (OPEN can't go straight to VERIFIED)
    with pytest.raises(ValueError, match="illegal transition"):
        store.update(f)


def test_charter_create_rejects_non_draft_status(store):
    """Kimi E7 attack #5: cannot create a charter that's already approved."""
    cs = CharterStore(ontology=store)
    pre_approved = TestCharter(
        project_id="proj_demo123def456",
        source_of_truth_version="v1",
        masterplan_version="v1",
        scope={"x": 1},
        required_test_classes=["T2"],
        required_personas=["operator_beginner"],
        required_evidence=["test_result"],
        release_blockers=["P0"],
        auto_repair_policy={},
        approval={"d_level": "D3"},
        status="approved",
    )
    with pytest.raises(ValueError, match="draft"):
        cs.create(pre_approved)


def test_charter_approve_idempotent_under_explicit_recall(store):
    """Kimi E7 attack #2: a second approve() raises rather than overwriting."""
    c = _make_charter(store, status="proposed")
    cs = CharterStore(ontology=store)
    cs.approve(c.charter_id, approver="alice", hg_ticket_id="hg_1")
    with pytest.raises(ValueError, match="already approved"):
        cs.approve(c.charter_id, approver="bob", hg_ticket_id="hg_2")


@pytest.mark.parametrize("evil", [
    "proj_demo%", "proj_demo_with%wildcard", "proj_demo_x_y",  # _ is fine; % isn't
])
def test_charter_list_rejects_sql_like_wildcards(store, evil):
    """Kimi E7 attack #6: % must not slip through to the LIKE filter."""
    cs = CharterStore(ontology=store)
    if "%" in evil:
        with pytest.raises(ValueError, match="project_id"):
            cs.list_for_project(evil)


def test_finding_transition_to_verified_requires_regression_run_id(store):
    """Kimi E7 attack #7 (relaxed): VERIFIED requires regression_run_id."""
    fs = FindingStore(ontology=store)
    f = Finding(severity="P1", d_level="D2", title="x",
                description="d", discovered_by="t", r_status="OPEN")
    store.create(f)
    fs.transition(f.finding_id, "REPRODUCED")
    fs.transition(f.finding_id, "CLASSIFIED")
    fs.transition(f.finding_id, "REPAIR_PROPOSED")
    fs.transition(f.finding_id, "REPAIRING")
    fs.transition(f.finding_id, "READY_FOR_RETEST")
    with pytest.raises(ValueError, match="regression_run_id"):
        fs.transition(f.finding_id, "VERIFIED")
    fs.transition(
        f.finding_id, "VERIFIED",
        evidence={"regression_run_id": "rr_xxx"},
    )
    assert fs.get(f.finding_id).r_status == "VERIFIED"


def test_finding_concurrent_transition_serializes(store):
    fs = FindingStore(ontology=store)
    f = Finding(severity="P2", d_level="D2", title="x",
                description="d", discovered_by="t")
    store.create(f)
    barrier = threading.Barrier(6)
    results: list = []

    def worker():
        try:
            barrier.wait()
            # First viable next state is TRIAGED.
            results.append(fs.transition(f.finding_id, "TRIAGED"))
        except (ValueError, RuntimeError) as exc:
            results.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    successes = [r for r in results if isinstance(r, Finding)]
    failures = [r for r in results if isinstance(r, ValueError)]
    # OPEN -> TRIAGED is legal once; subsequent attempts hit
    # TRIAGED -> TRIAGED (not in allowed set).
    assert len(successes) == 1
    assert len(failures) == 5
