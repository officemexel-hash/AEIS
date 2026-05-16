"""Tests for charter actions (4)."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.actions.charter_actions import (
    ApproveTestCharterHandler, CreateEvalSuiteHandler,
    ProposeTestCharterHandler, RunEvalSuiteHandler,
)
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import (
    EvaluationSuite, TestCharter, TestRun,
)


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def valid_charter_payload():
    return {
        "project_id": "proj_demo",
        "source_of_truth_version": "sot_v1",
        "masterplan_version": "mp_v1",
        "scope": {"modules": ["mod_a"]},
        "required_test_classes": ["T2", "T3"],
        "required_personas": ["operator_beginner"],
    }


# -------- propose_test_charter --------

def test_propose_creates_charter(store, valid_charter_payload):
    h = ProposeTestCharterHandler(ontology=store)
    h.validate(valid_charter_payload)
    result = h.execute(valid_charter_payload, intent_id="intent_1")
    assert result["status"] == "proposed"
    assert result["charter_id"].startswith("tc_")
    persisted = store.get(TestCharter, result["charter_id"])
    assert persisted is not None
    assert persisted.project_id == "proj_demo"


def test_propose_rejects_bad_project_id(store, valid_charter_payload):
    h = ProposeTestCharterHandler(ontology=store)
    valid_charter_payload["project_id"] = "wrong_prefix"
    with pytest.raises(ValueError, match="proj_"):
        h.validate(valid_charter_payload)


def test_propose_rejects_invalid_test_class(store, valid_charter_payload):
    h = ProposeTestCharterHandler(ontology=store)
    valid_charter_payload["required_test_classes"] = ["T99"]
    with pytest.raises(ValueError, match="invalid test classes"):
        h.validate(valid_charter_payload)


def test_propose_rejects_empty_test_classes(store, valid_charter_payload):
    h = ProposeTestCharterHandler(ontology=store)
    valid_charter_payload["required_test_classes"] = []
    with pytest.raises(ValueError, match="non-empty list"):
        h.validate(valid_charter_payload)


# -------- approve_test_charter --------

def test_approve_changes_status(store, valid_charter_payload):
    p = ProposeTestCharterHandler(ontology=store)
    p.validate(valid_charter_payload)
    proposed = p.execute(valid_charter_payload, intent_id="i1")
    a = ApproveTestCharterHandler(ontology=store)
    payload = {
        "charter_id": proposed["charter_id"],
        "hg_ticket_id": "hg_123",
        "approver": "operator",
        "rationale": "ok",
    }
    a.validate(payload)
    result = a.execute(payload, intent_id="i2")
    assert result["status"] == "approved"
    persisted = store.get(TestCharter, proposed["charter_id"])
    assert persisted.status == "approved"
    assert persisted.hg_ticket_id == "hg_123"


def test_approve_rejects_unknown_charter(store):
    h = ApproveTestCharterHandler(ontology=store)
    payload = {
        "charter_id": "tc_doesnotexist",
        "hg_ticket_id": "hg_1",
        "approver": "op",
        "rationale": "x",
    }
    h.validate(payload)
    with pytest.raises(ValueError, match="not found"):
        h.execute(payload, intent_id="i")


def test_approve_rejects_already_approved(store, valid_charter_payload):
    p = ProposeTestCharterHandler(ontology=store)
    p.validate(valid_charter_payload)
    proposed = p.execute(valid_charter_payload, intent_id="i1")
    a = ApproveTestCharterHandler(ontology=store)
    payload = {
        "charter_id": proposed["charter_id"],
        "hg_ticket_id": "hg_1",
        "approver": "op",
        "rationale": "x",
    }
    a.validate(payload)
    a.execute(payload, intent_id="i2")  # first approve
    with pytest.raises(ValueError, match="status must be"):
        a.execute(payload, intent_id="i3")  # second rejected


# -------- create_eval_suite --------

def test_create_eval_suite(store):
    h = CreateEvalSuiteHandler(ontology=store)
    payload = {
        "target_function": "advisor.compute_card",
        "target_module": "sylion.aeis.advisor",
        "test_case_ids": ["tc_1", "tc_2"],
        "evaluators": ["exact_match"],
        "metrics": ["pass_rate"],
    }
    h.validate(payload)
    result = h.execute(payload, intent_id="i")
    assert result["status"] == "created"
    persisted = store.get(EvaluationSuite, result["suite_id"])
    assert persisted is not None
    assert persisted.target_function == "advisor.compute_card"


def test_create_eval_suite_rejects_empty_evaluators(store):
    h = CreateEvalSuiteHandler(ontology=store)
    payload = {
        "target_function": "f", "target_module": "m",
        "test_case_ids": ["x"], "evaluators": [], "metrics": ["m"],
    }
    with pytest.raises(ValueError, match="non-empty list"):
        h.validate(payload)


# -------- run_eval_suite --------

def test_run_eval_suite_creates_runs(store):
    # First create a suite
    c = CreateEvalSuiteHandler(ontology=store)
    payload_create = {
        "target_function": "f", "target_module": "m",
        "test_case_ids": ["case_1", "case_2", "case_3"],
        "evaluators": ["exact"], "metrics": ["pr"],
    }
    c.validate(payload_create)
    created = c.execute(payload_create, intent_id="i1")

    # Now run
    r = RunEvalSuiteHandler(ontology=store)
    payload_run = {"suite_id": created["suite_id"], "branch_id": "br_test"}
    r.validate(payload_run)
    result = r.execute(payload_run, intent_id="i2")
    assert result["total"] == 3
    assert len(result["runs_started"]) == 3
    # All persisted as TestRun
    for run_id in result["runs_started"]:
        run = store.get(TestRun, run_id)
        assert run is not None
        assert run.status == "running"
        assert run.branch_id == "br_test"


def test_run_eval_suite_rejects_unknown_suite(store):
    h = RunEvalSuiteHandler(ontology=store)
    payload = {"suite_id": "es_doesnotexist", "branch_id": "br_test"}
    h.validate(payload)
    with pytest.raises(ValueError, match="not found"):
        h.execute(payload, intent_id="i")


def test_run_eval_suite_rejects_bad_prefix(store):
    h = RunEvalSuiteHandler(ontology=store)
    with pytest.raises(ValueError, match="es_"):
        h.validate({"suite_id": "wrong_prefix_id", "branch_id": "br_test"})


def test_run_eval_suite_rejects_main_branch(store):
    """Regression: branch_id='main' must NOT be accepted as the eval target."""
    h = RunEvalSuiteHandler(ontology=store)
    with pytest.raises(ValueError, match="main"):
        h.validate({"suite_id": "es_anything", "branch_id": "main"})


def test_run_eval_suite_rejects_main_with_case_variants(store):
    """Regression: case/whitespace normalization must reject 'MAIN', ' main '."""
    h = RunEvalSuiteHandler(ontology=store)
    for variant in ("MAIN", "Main", " main", "main\n"):
        with pytest.raises(ValueError, match="main"):
            h.validate({"suite_id": "es_x", "branch_id": variant})


def test_run_eval_suite_rejects_missing_branch(store):
    """Regression: branch_id is now mandatory (no implicit 'main' default)."""
    h = RunEvalSuiteHandler(ontology=store)
    with pytest.raises(ValueError, match="branch_id"):
        h.validate({"suite_id": "es_anything"})
