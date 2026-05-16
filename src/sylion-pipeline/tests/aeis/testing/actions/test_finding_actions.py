"""Tests for finding actions (3) including 24h waiver minimum + D4 disable_test."""
from __future__ import annotations

import time

import pytest

from sylion.aeis.testing.actions.finding_actions import (
    DisableTestHandler, MarkFindingReproducedHandler, WaiveFindingHandler,
)
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import Finding, TestCase


@pytest.fixture
def store():
    return OntologyStore()


# -------- mark_finding_reproduced --------

def test_mark_reproduced_open_to_reproduced(store):
    f = Finding(severity="P2", d_level="D2", title="x",
                description="d", discovered_by="t", r_status="OPEN")
    store.create(f)
    h = MarkFindingReproducedHandler(ontology=store)
    payload = {
        "finding_id": f.finding_id,
        "reproducer": "test_runner",
        "evidence": {"log": "..."},
    }
    h.validate(payload)
    result = h.execute(payload, intent_id="i")
    assert result["r_status"] == "REPRODUCED"


def test_mark_reproduced_rejects_closed_finding(store):
    f = Finding(severity="P3", d_level="D1", title="x",
                description="d", discovered_by="t", r_status="CLOSED")
    store.create(f)
    h = MarkFindingReproducedHandler(ontology=store)
    payload = {
        "finding_id": f.finding_id,
        "reproducer": "x", "evidence": {},
    }
    h.validate(payload)
    with pytest.raises(ValueError, match="OPEN or TRIAGED"):
        h.execute(payload, intent_id="i")


def test_mark_reproduced_rejects_bad_prefix(store):
    h = MarkFindingReproducedHandler(ontology=store)
    with pytest.raises(ValueError, match="find_"):
        h.validate({"finding_id": "wrong", "reproducer": "x", "evidence": {}})


# -------- waive_finding --------

def test_waive_with_valid_expiry(store):
    f = Finding(severity="P3", d_level="D3", title="x",
                description="d", discovered_by="t")
    store.create(f)
    h = WaiveFindingHandler(ontology=store)
    payload = {
        "finding_id": f.finding_id,
        "hg_ticket_id": "hg_1",
        "rationale": "low risk for v1.0",
        "expiry_at": time.time() + 7 * 24 * 3600,  # 7 days
    }
    h.validate(payload)
    result = h.execute(payload, intent_id="i")
    assert result["r_status"] == "WAIVED_BY_HUMAN"


def test_waive_REJECTS_short_expiry(store):
    h = WaiveFindingHandler(ontology=store)
    payload = {
        "finding_id": "find_x",
        "hg_ticket_id": "hg",
        "rationale": "x",
        "expiry_at": time.time() + 3600,  # only 1h, too short
    }
    with pytest.raises(ValueError, match="24h in the future"):
        h.validate(payload)


def test_waive_REJECTS_perpetual_expiry_far_future_ok(store):
    """24h minimum is OK; only short-term is rejected."""
    h = WaiveFindingHandler(ontology=store)
    payload = {
        "finding_id": "find_x",
        "hg_ticket_id": "hg",
        "rationale": "x",
        "expiry_at": time.time() + 365 * 24 * 3600,  # 1 year — allowed
    }
    h.validate(payload)  # passes


# -------- disable_test (D4: ONLY action that disables) --------

def test_disable_test_changes_enabled(store):
    case = TestCase(
        requirement_id="req_1",
        input_payload={"x": 1},
        expected_output={"y": 2},
        evaluator="exact",
    )
    store.create(case)
    h = DisableTestHandler(ontology=store)
    payload = {
        "case_id": case.case_id,
        "council_session_id": "cs_1",
        "hg_ticket_id": "hg_1",
        "rationale": "test obsolete after spec change",
    }
    h.validate(payload)
    result = h.execute(payload, intent_id="i")
    assert result["enabled"] is False
    persisted = store.get(TestCase, case.case_id)
    assert persisted.enabled is False


def test_disable_test_d_level_is_D4(store):
    h = DisableTestHandler(ontology=store)
    from sylion.aeis.testing.ontology.enums import DLevel
    assert h.d_level == DLevel.D4


def test_disable_test_rejects_missing_council(store):
    h = DisableTestHandler(ontology=store)
    payload = {
        "case_id": "tc_x",
        "hg_ticket_id": "hg_1",
        "rationale": "x",
    }  # missing council_session_id
    with pytest.raises(ValueError, match="council_session_id"):
        h.validate(payload)
