"""Tests for 13 W14 Guardians."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.guardians import (
    ALL_GUARDIAN_CLASSES, register_all_guardians,
)
from sylion.aeis.testing.guardians.implementations import (
    CostSentinel, CouncilGuardian, EvidenceGuardian, GateGuardian,
    LLMDriftGuardian, LoopGuardian, MasterplanGuardian, MockFallbackGuardian,
    PIIGuardian, ReleaseGuardian, SoTGuardian, TestIntegrityGuardian,
    TraceCompletenessGuardian,
)
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import GuardianAlert


class _Evt:
    """Minimal mock event for testing."""
    def __init__(self, topic: str, payload: dict | None = None):
        self.topic = topic
        self.payload = payload or {}


@pytest.fixture
def store():
    return OntologyStore()


# -------- Registry / API --------

def test_register_all_returns_13_guardians(store):
    guards = register_all_guardians(ontology=store)
    assert len(guards) == 13


def test_each_guardian_class_distinct():
    names = {cls.name for cls in ALL_GUARDIAN_CLASSES}
    assert len(names) == 13


def test_all_guardians_have_subscribed_events():
    for cls in ALL_GUARDIAN_CLASSES:
        assert cls.subscribed_events, f"{cls.__name__} missing subscribed_events"


# -------- 1. SoT Guardian --------

def test_sot_guardian_alerts_on_feature_outside_sot(store):
    g = SoTGuardian(ontology=store)
    alert = g.on_event(_Evt("aeis.testing.run.completed", {
        "feature_id": "feat_x", "in_sot": False,
    }))
    assert alert is not None
    assert alert.severity == "P1"
    assert "Source of Truth" in alert.reason


def test_sot_guardian_silent_when_in_sot(store):
    g = SoTGuardian(ontology=store)
    assert g.on_event(_Evt("aeis.testing.run.completed", {
        "feature_id": "feat_x", "in_sot": True,
    })) is None


# -------- 2. Masterplan Guardian --------

def test_masterplan_guardian_alerts_on_unplanned_module(store):
    g = MasterplanGuardian(ontology=store)
    alert = g.on_event(_Evt("module.executed", {
        "module_id": "mod_rogue", "in_masterplan": False,
    }))
    assert alert is not None
    assert alert.severity == "P1"


# -------- 3. Test Integrity Guardian --------

def test_test_integrity_alerts_on_disable_without_council(store):
    g = TestIntegrityGuardian(ontology=store)
    alert = g.on_event(_Evt("aeis.testing.case.disabled", {
        "case_id": "tc_x", "council_session_id": None, "hg_ticket_id": None,
    }))
    assert alert is not None
    assert alert.severity == "P0"


def test_test_integrity_silent_with_council(store):
    g = TestIntegrityGuardian(ontology=store)
    assert g.on_event(_Evt("aeis.testing.case.disabled", {
        "case_id": "tc_x", "council_session_id": "cs_1", "hg_ticket_id": "hg_1",
    })) is None


# -------- 4. Mock Fallback Guardian --------

def test_mock_guardian_alerts_d3_on_mock(store):
    g = MockFallbackGuardian(ontology=store)
    alert = g.on_event(_Evt("advisor.action.about_to_execute", {
        "data_source": "mock", "d_level": "D3",
    }))
    assert alert is not None
    assert alert.severity == "P0"


def test_mock_guardian_silent_d2_on_mock(store):
    g = MockFallbackGuardian(ontology=store)
    assert g.on_event(_Evt("advisor.action.about_to_execute", {
        "data_source": "mock", "d_level": "D2",
    })) is None


def test_mock_guardian_silent_live_d3(store):
    g = MockFallbackGuardian(ontology=store)
    assert g.on_event(_Evt("advisor.action.about_to_execute", {
        "data_source": "live", "d_level": "D3",
    })) is None


# -------- 5. Evidence Guardian --------

def test_evidence_guardian_alerts_missing_run_id(store):
    g = EvidenceGuardian(ontology=store)
    alert = g.on_event(_Evt("aeis.testing.case.passed", {
        "trace_id": "trace_x",
    }))
    assert alert is not None
    assert "missing evidence fields" in alert.reason


def test_evidence_guardian_silent_with_full_evidence(store):
    g = EvidenceGuardian(ontology=store)
    assert g.on_event(_Evt("aeis.testing.case.passed", {
        "run_id": "tr_x", "trace_id": "trace_x",
    })) is None


# -------- 6. Gate Guardian --------

def test_gate_guardian_alerts_d3_no_hg(store):
    g = GateGuardian(ontology=store)
    alert = g.on_event(_Evt("advisor.action.executed", {
        "d_level": "D3", "hg_ticket_id": None,
    }))
    assert alert is not None
    assert alert.severity == "P0"


def test_gate_guardian_silent_d2(store):
    g = GateGuardian(ontology=store)
    assert g.on_event(_Evt("advisor.action.executed", {
        "d_level": "D2", "hg_ticket_id": None,
    })) is None


# -------- 7. Council Guardian --------

def test_council_guardian_alerts_d4_no_council(store):
    g = CouncilGuardian(ontology=store)
    alert = g.on_event(_Evt("advisor.action.executed", {
        "d_level": "D4", "council_session_id": None,
    }))
    assert alert is not None
    assert alert.severity == "P0"


# -------- 8. Release Guardian --------

def test_release_guardian_alerts_unresolved_findings(store):
    g = ReleaseGuardian(ontology=store)
    alert = g.on_event(_Evt("aeis.testing.release.candidate_ready", {
        "unresolved_findings": ["find_x", "find_y"],
    }))
    assert alert is not None
    assert "2 unresolved" in alert.reason


# -------- 9. Loop Guardian --------

def test_loop_guardian_confirms_loop_detected(store):
    g = LoopGuardian(ontology=store)
    alert = g.on_event(_Evt("aeis.testing.loop.detected", {
        "report_id": "lr_x", "finding_id": "find_x",
    }))
    assert alert is not None
    assert alert.finding_id == "find_x"


# -------- 10. LLM Drift Guardian --------

def test_llm_drift_alerts_above_threshold(store):
    g = LLMDriftGuardian(ontology=store)
    alert = g.on_event(_Evt("llm.evaluation.completed", {
        "divergence_rate": 0.07, "baseline_model": "claude-4-6",
        "new_model": "claude-4-7",
    }))
    assert alert is not None
    assert "drift" in alert.reason.lower()


def test_llm_drift_silent_below_threshold(store):
    g = LLMDriftGuardian(ontology=store)
    assert g.on_event(_Evt("llm.evaluation.completed", {
        "divergence_rate": 0.02, "baseline_model": "x", "new_model": "y",
    })) is None


# -------- 11. Cost Sentinel --------

def test_cost_sentinel_alerts_10x_spike(store):
    g = CostSentinel(ontology=store)
    alert = g.on_event(_Evt("llm.request.completed", {
        "cost_usd": 0.5, "baseline_cost_usd": 0.01,
    }))
    assert alert is not None
    assert "spike" in alert.reason.lower()


def test_cost_sentinel_alerts_budget_overrun(store):
    g = CostSentinel(ontology=store)
    alert = g.on_event(_Evt("project.budget.snapshot", {
        "used_pct": 1.05,
    }))
    assert alert is not None
    assert alert.severity == "P0"


def test_cost_sentinel_warn_at_70_pct(store):
    g = CostSentinel(ontology=store)
    alert = g.on_event(_Evt("project.budget.snapshot", {
        "used_pct": 0.75,
    }))
    assert alert is not None
    assert alert.severity == "P2"


# -------- 12. PII Guardian --------

def test_pii_guardian_detects_email(store):
    g = PIIGuardian(ontology=store)
    alert = g.on_event(_Evt("evidence_pack.artefact_added", {
        "content": "contact: jan.kowalski@example.com",
    }))
    assert alert is not None
    assert "email" in alert.reason


def test_pii_guardian_detects_pesel(store):
    g = PIIGuardian(ontology=store)
    alert = g.on_event(_Evt("log.line.emitted", {
        "log_line": "user identifier 80010112345 found",
    }))
    assert alert is not None


def test_pii_guardian_silent_clean_text(store):
    g = PIIGuardian(ontology=store)
    assert g.on_event(_Evt("log.line.emitted", {
        "log_line": "info: starting service xyz",
    })) is None


# -------- 13. Trace Completeness Guardian --------

def test_trace_guardian_alerts_d3_no_trace(store):
    g = TraceCompletenessGuardian(ontology=store)
    alert = g.on_event(_Evt("advisor.action.executed", {
        "d_level": "D3", "trace_id": None,
    }))
    assert alert is not None
    assert "trace_id" in alert.reason


# -------- Status reporting --------

def test_guardian_status_after_alert(store):
    g = SoTGuardian(ontology=store)
    g.on_event(_Evt("aeis.testing.run.completed", {
        "feature_id": "x", "in_sot": False,
    }))
    s = g.status()
    assert s["alerts_24h"] == 1
    assert s["last_alert_at"] > 0


def test_guardian_alert_persisted_to_store(store):
    g = SoTGuardian(ontology=store)
    alert = g.on_event(_Evt("aeis.testing.run.completed", {
        "feature_id": "x", "in_sot": False,
    }))
    persisted = store.get(GuardianAlert, alert.alert_id)
    assert persisted is not None
