"""FindingStore tests — R-status lifecycle."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.findings import TERMINAL_STATUSES, FindingStore
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.enums import RStatus
from sylion.aeis.testing.ontology.objects import Finding


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def fs(store):
    return FindingStore(ontology=store)


def _new(severity="P2", d_level="D2", status="OPEN") -> Finding:
    return Finding(
        severity=severity, d_level=d_level,
        title="x", description="d", discovered_by="t",
        r_status=status,
    )


# -------- create --------

def test_create_with_explicit_open(fs):
    """Finding dataclass enforces valid r_status; FindingStore persists it."""
    f = Finding(severity="P3", d_level="D1", title="x",
                description="d", discovered_by="t", r_status="OPEN")
    persisted = fs.create(f)
    assert persisted.r_status == "OPEN"


def test_create_persists_to_store(fs, store):
    f = fs.create(_new())
    assert store.get(Finding, f.finding_id) is not None


# -------- transition --------

def test_transition_open_to_reproduced(fs):
    f = fs.create(_new())
    fs.transition(f.finding_id, "REPRODUCED")
    fetched = fs.get(f.finding_id)
    assert fetched.r_status == "REPRODUCED"


def test_transition_classified_to_repair_proposed(fs):
    f = fs.create(_new(status="CLASSIFIED"))
    fs.transition(f.finding_id, "REPAIR_PROPOSED")
    assert fs.get(f.finding_id).r_status == "REPAIR_PROPOSED"


def test_transition_repairing_to_ready_for_retest(fs):
    f = fs.create(_new(status="REPAIRING"))
    fs.transition(f.finding_id, "READY_FOR_RETEST")
    assert fs.get(f.finding_id).r_status == "READY_FOR_RETEST"


def test_transition_verified_to_closed_sets_closed_at(fs):
    f = fs.create(_new(status="VERIFIED"))
    fs.transition(f.finding_id, "CLOSED")
    fetched = fs.get(f.finding_id)
    assert fetched.r_status == "CLOSED"
    assert fetched.closed_at is not None


def test_transition_invalid_raises(fs):
    f = fs.create(_new(status="OPEN"))
    # OPEN -> VERIFIED is not allowed
    with pytest.raises(ValueError, match="invalid transition"):
        fs.transition(f.finding_id, "VERIFIED")


def test_transition_unknown_finding_raises(fs):
    with pytest.raises(ValueError, match="not found"):
        fs.transition("find_doesnotexist", "REPRODUCED")


def test_transition_terminal_status_blocked(fs):
    f = fs.create(_new(status="VERIFIED"))
    fs.transition(f.finding_id, "CLOSED")
    with pytest.raises(ValueError, match="invalid transition"):
        fs.transition(f.finding_id, "REPRODUCED")


def test_transition_to_waived_from_any(fs):
    """WAIVED_BY_HUMAN reachable from many states (with required evidence)."""
    waiver = {"hg_ticket_id": "hg_test", "rationale": "test override"}
    for src in ("OPEN", "TRIAGED", "REPAIR_PROPOSED", "REGRESSION_FAILED"):
        f = fs.create(_new(status=src))
        fs.transition(f.finding_id, "WAIVED_BY_HUMAN", evidence=waiver)
        assert fs.get(f.finding_id).r_status == "WAIVED_BY_HUMAN"


def test_transition_waived_requires_evidence(fs):
    """Kimi E7 attack #7: WAIVED_BY_HUMAN demands hg_ticket_id + rationale."""
    f = fs.create(_new(status="OPEN"))
    with pytest.raises(ValueError, match="hg_ticket_id"):
        fs.transition(f.finding_id, "WAIVED_BY_HUMAN")


# -------- list_open --------

def test_list_open_excludes_closed(fs):
    fs.create(_new(status="OPEN"))
    fs.create(_new(status="VERIFIED"))
    f3 = fs.create(_new(status="VERIFIED"))
    fs.transition(f3.finding_id, "CLOSED")  # terminal
    open_f = fs.list_open()
    assert len(open_f) == 2  # OPEN + VERIFIED (not terminal)


def test_list_open_filter_by_severity(fs):
    fs.create(_new(severity="P0"))
    fs.create(_new(severity="P1"))
    fs.create(_new(severity="P3"))
    p0 = fs.list_open(severity="P0")
    assert len(p0) == 1


def test_list_critical_returns_p0_p1_only(fs):
    fs.create(_new(severity="P0"))
    fs.create(_new(severity="P1"))
    fs.create(_new(severity="P2"))
    fs.create(_new(severity="P3"))
    crit = fs.list_critical()
    assert len(crit) == 2
    assert all(f.severity in ("P0", "P1") for f in crit)


def test_list_by_d_level(fs):
    fs.create(_new(d_level="D2"))
    fs.create(_new(d_level="D4"))
    fs.create(_new(d_level="D4"))
    d4 = fs.list_by_d_level("D4")
    assert len(d4) == 2


# -------- terminal --------

def test_terminal_statuses_constant():
    assert "CLOSED" in TERMINAL_STATUSES
