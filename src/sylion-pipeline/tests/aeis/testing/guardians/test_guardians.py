"""W14 E5 — comprehensive guardian tests (5+ pos / 5+ neg per guardian).

Single test module instead of 13 to avoid copy-paste churn; each guardian
has its own block clearly delimited so per-guardian test discovery is
trivially possible (``pytest -k SoTGuardian`` works).
"""
from __future__ import annotations

import threading

import pytest

from sylion.aeis.testing.guardians import (
    ALL_GUARDIAN_CLASSES, register_all_guardians,
)
from sylion.aeis.testing.guardians.base import GuardianBase
from sylion.aeis.testing.guardians.implementations import (
    CostSentinel, CouncilGuardian, EvidenceGuardian, GateGuardian,
    LLMDriftGuardian, LoopGuardian, MasterplanGuardian, MockFallbackGuardian,
    PIIGuardian, ReleaseGuardian, SoTGuardian, TestIntegrityGuardian,
    TraceCompletenessGuardian,
)
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import (
    Finding, GuardianAlert, LoopReport, RepairAttempt,
)
from sylion.core.event_bus import SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store():
    return OntologyStore()


def _ev(topic: str, **payload) -> SylionEvent:
    return SylionEvent(event_id="", topic=topic, payload=payload)


# ---------------------------------------------------------------------------
# Registry sanity
# ---------------------------------------------------------------------------


def test_all_13_guardians_registered():
    assert len(ALL_GUARDIAN_CLASSES) == 13


def test_register_all_guardians_returns_13(store):
    out = register_all_guardians(ontology=store)
    assert len(out) == 13


def test_register_all_guardians_subscribes_to_bus(store):
    """Each guardian must subscribe its topics on the provided bus."""

    class FakeBus:
        def __init__(self):
            self.subs: dict[str, list] = {}

        def subscribe(self, topic, handler):
            self.subs.setdefault(topic, []).append(handler)

    bus = FakeBus()
    register_all_guardians(ontology=store, event_bus=bus)
    # Every subscribed_events topic across the 13 guardians should
    # have at least one subscriber registered.
    expected = {t for cls in ALL_GUARDIAN_CLASSES for t in cls.subscribed_events}
    assert expected.issubset(set(bus.subs.keys()))


# ---------------------------------------------------------------------------
# GuardianBase: idempotency + crash isolation
# ---------------------------------------------------------------------------


class _AlwaysAlert(GuardianBase):
    """Test stub. Uses a real GuardianClass enum value for ontology validity."""
    name = "sot_guardian"
    subscribed_events = ("test.x",)

    def on_event(self, event):  # noqa: D401
        return self._alert(self.name, "P2", "always",
                           evidence_link={"event_id": getattr(event, "event_id", "")},
                           trace_id="t1")


def test_guardian_handle_event_is_idempotent(store):
    g = _AlwaysAlert(ontology=store)
    e = SylionEvent(event_id="ev_1", topic="test.x", payload={})
    g.handle_event(e)
    g.handle_event(e)  # same event_id -> deduplicated
    alerts = store.list(GuardianAlert, limit=10)
    assert len(alerts) == 1


def test_guardian_handle_event_isolates_crashes(store):
    class _Crash(GuardianBase):
        name = "sot_guardian"
        subscribed_events = ("test.x",)

        def on_event(self, event):
            raise RuntimeError("boom")

    g = _Crash(ontology=store)
    out = g.handle_event(SylionEvent(event_id="ev_2", topic="test.x", payload={}))
    assert out is None  # exception swallowed


def test_guardian_handle_event_survives_non_string_event_id(store):
    """Kimi attack #1: dedup must not crash subscriber on weird event_id types."""
    g = _AlwaysAlert(ontology=store)

    class _BadEv:
        event_id = 42  # int, not str
        topic = "test.x"
        payload = {}

    out = g.handle_event(_BadEv())
    # Coerced to "42" and processed without crash
    assert out is not None


def test_guardian_alert_marks_health_red_on_persist_failure(store):
    """Kimi attack #5: ontology.create failure must surface on health."""

    class _BrokenStore:
        def create(self, _obj):
            raise RuntimeError("persist failed")

        def list(self, *a, **kw):
            return []

    g = _AlwaysAlert(ontology=_BrokenStore())
    g.handle_event(SylionEvent(event_id="ev_persist", topic="test.x", payload={}))
    assert g.health == "RED"
    assert g.persistence_failed is True


def test_guardian_status_thread_safe(store):
    g = _AlwaysAlert(ontology=store)

    def worker(i):
        ev = SylionEvent(event_id=f"ev_{i}", topic="test.x", payload={})
        g.handle_event(ev)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # No crashes; alerts_24h reflects 50 unique event ids.
    assert g.alerts_24h == 50


# ---------------------------------------------------------------------------
# 1. SoTGuardian
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topic,kw", [
    ("aeis.testing.run.completed", {"feature_id": "f1", "in_sot": False}),
    ("advisor.action.executed", {"feature_id": "f2", "in_sot": False}),
    ("aeis.testing.run.completed", {"feature_id": "x", "in_sot": False, "trace_id": "t"}),
    ("advisor.action.executed", {"feature_id": "z", "in_sot": False}),
    ("aeis.testing.run.completed", {"feature_id": "shadow", "in_sot": False}),
])
def test_sot_guardian_alerts_when_feature_outside_sot(store, topic, kw):
    g = SoTGuardian(ontology=store)
    alert = g.on_event(_ev(topic, **kw))
    assert alert is not None and alert.severity == "P1"


@pytest.mark.parametrize("topic,kw", [
    ("aeis.testing.run.completed", {"feature_id": "f1", "in_sot": True}),
    ("advisor.action.executed", {"feature_id": "f1"}),  # in_sot defaults True
    ("aeis.testing.run.completed", {}),  # no feature_id
    ("aeis.testing.run.completed", {"feature_id": "", "in_sot": False}),  # empty
    ("advisor.action.executed", {"feature_id": "ok", "in_sot": True}),
])
def test_sot_guardian_quiet_when_in_sot(store, topic, kw):
    g = SoTGuardian(ontology=store)
    assert g.on_event(_ev(topic, **kw)) is None


# ---------------------------------------------------------------------------
# 2. MasterplanGuardian
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kw", [
    {"module_id": "m1", "in_masterplan": False},
    {"module_id": "m2", "in_masterplan": False},
    {"module_id": "shadow", "in_masterplan": False, "trace_id": "t"},
    {"module_id": "rogue", "in_masterplan": False},
    {"module_id": "x", "in_masterplan": False},
])
def test_masterplan_guardian_alerts_outside(store, kw):
    g = MasterplanGuardian(ontology=store)
    assert g.on_event(_ev("module.executed", **kw)) is not None


@pytest.mark.parametrize("kw", [
    {"module_id": "m1", "in_masterplan": True},
    {},
    {"module_id": "", "in_masterplan": False},
    {"module_id": "ok"},  # default in_masterplan=True
    {"module_id": "x", "in_masterplan": True},
])
def test_masterplan_guardian_quiet_when_in_plan(store, kw):
    g = MasterplanGuardian(ontology=store)
    assert g.on_event(_ev("module.registered", **kw)) is None


# ---------------------------------------------------------------------------
# 3. TestIntegrityGuardian
# ---------------------------------------------------------------------------


def test_test_integrity_alerts_on_disable_without_council(store):
    g = TestIntegrityGuardian(ontology=store)
    e = _ev("aeis.testing.case.disabled", hg_ticket_id="hg_x")  # no council
    assert g.on_event(e) is not None


def test_test_integrity_alerts_on_disable_with_blank_hg(store):
    g = TestIntegrityGuardian(ontology=store)
    e = _ev("aeis.testing.case.disabled",
            hg_ticket_id="   ", council_session_id="cs_1")
    assert g.on_event(e) is not None


def test_test_integrity_alerts_on_test_file_deletion(store):
    g = TestIntegrityGuardian(ontology=store)
    e = _ev("git.commit.applied", test_file_deleted=True, file="tests/x.py")
    assert g.on_event(e) is not None


def test_test_integrity_alerts_on_assertion_weakening(store):
    g = TestIntegrityGuardian(ontology=store)
    e = _ev("git.commit.applied",
            diff_text="-    assert user.is_admin\n+    pass\n")
    assert g.on_event(e) is not None


def test_test_integrity_alerts_on_xfail_marker(store):
    g = TestIntegrityGuardian(ontology=store)
    e = _ev("git.commit.applied", diff_text="@pytest.mark.xfail\n")
    assert g.on_event(e) is not None


def test_test_integrity_quiet_when_disable_has_council_and_hg(store):
    g = TestIntegrityGuardian(ontology=store)
    e = _ev("aeis.testing.case.disabled",
            council_session_id="cs_1", hg_ticket_id="hg_x")
    assert g.on_event(e) is None


def test_test_integrity_quiet_on_clean_diff(store):
    g = TestIntegrityGuardian(ontology=store)
    e = _ev("git.commit.applied", diff_text="+    return 42\n")
    assert g.on_event(e) is None


def test_test_integrity_quiet_when_assertion_weakening_has_hg(store):
    g = TestIntegrityGuardian(ontology=store)
    e = _ev("git.commit.applied",
            diff_text="-assert user.is_admin\n", hg_ticket_id="hg_x")
    assert g.on_event(e) is None


def test_test_integrity_quiet_on_no_relevant_signal(store):
    g = TestIntegrityGuardian(ontology=store)
    assert g.on_event(_ev("git.commit.applied")) is None


def test_test_integrity_quiet_when_test_file_deleted_false(store):
    g = TestIntegrityGuardian(ontology=store)
    assert g.on_event(_ev("git.commit.applied", test_file_deleted=False)) is None


# ---------------------------------------------------------------------------
# 4. MockFallbackGuardian
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("data_source", ["mock", "demo", "fallback", "cache_stale"])
def test_mock_guardian_alerts_on_bad_source_d3(store, data_source):
    g = MockFallbackGuardian(ontology=store)
    e = _ev("advisor.action.about_to_execute",
            data_source=data_source, d_level="D3")
    assert g.on_event(e) is not None


@pytest.mark.parametrize("variant", ["MOCK", "Mock", " mock ", "Demo "])
def test_mock_guardian_normalizes_case_and_whitespace(store, variant):
    """Kimi attack #5: 'Mock' / ' demo ' must not bypass the rule."""
    g = MockFallbackGuardian(ontology=store)
    e = _ev("advisor.action.about_to_execute",
            data_source=variant, d_level="D4")
    assert g.on_event(e) is not None


def test_mock_guardian_quiet_on_live_data(store):
    g = MockFallbackGuardian(ontology=store)
    e = _ev("advisor.action.about_to_execute",
            data_source="live", d_level="D5")
    assert g.on_event(e) is None


def test_mock_guardian_quiet_on_low_d_level(store):
    g = MockFallbackGuardian(ontology=store)
    e = _ev("advisor.action.about_to_execute",
            data_source="mock", d_level="D1")
    assert g.on_event(e) is None


def test_mock_guardian_quiet_on_missing_fields(store):
    g = MockFallbackGuardian(ontology=store)
    assert g.on_event(_ev("advisor.action.about_to_execute")) is None


# ---------------------------------------------------------------------------
# 5. EvidenceGuardian — only alerts on PASS semantics now
# ---------------------------------------------------------------------------


def test_evidence_alerts_on_case_passed_without_run_id(store):
    g = EvidenceGuardian(ontology=store)
    e = _ev("aeis.testing.case.passed", trace_id="t")
    assert g.on_event(e) is not None


def test_evidence_alerts_on_run_completed_with_status_passed_no_evidence(store):
    g = EvidenceGuardian(ontology=store)
    e = _ev("aeis.testing.run.completed", status="passed")
    assert g.on_event(e) is not None


def test_evidence_alerts_when_only_run_id_present(store):
    g = EvidenceGuardian(ontology=store)
    e = _ev("aeis.testing.case.passed", run_id="tr_x")  # missing trace_id
    assert g.on_event(e) is not None


def test_evidence_alerts_when_only_trace_id_present(store):
    g = EvidenceGuardian(ontology=store)
    e = _ev("aeis.testing.case.passed", trace_id="t")  # missing run_id
    assert g.on_event(e) is not None


def test_evidence_alerts_on_blank_run_id(store):
    g = EvidenceGuardian(ontology=store)
    e = _ev("aeis.testing.case.passed", run_id="  ", trace_id="t")
    assert g.on_event(e) is not None


def test_evidence_quiet_when_run_completed_status_not_passed(store):
    g = EvidenceGuardian(ontology=store)
    e = _ev("aeis.testing.run.completed", status="failed")
    assert g.on_event(e) is None


def test_evidence_quiet_when_pass_has_evidence(store):
    g = EvidenceGuardian(ontology=store)
    e = _ev("aeis.testing.case.passed", run_id="tr_x", trace_id="t1")
    assert g.on_event(e) is None


def test_evidence_quiet_on_run_completed_no_status(store):
    g = EvidenceGuardian(ontology=store)
    assert g.on_event(_ev("aeis.testing.run.completed")) is None


# ---------------------------------------------------------------------------
# 6. GateGuardian
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("d", ["D3", "D4", "D5"])
def test_gate_guardian_alerts_on_high_d_no_hg(store, d):
    g = GateGuardian(ontology=store)
    e = _ev("advisor.action.executed", d_level=d)
    assert g.on_event(e) is not None


def test_gate_guardian_alerts_on_blank_hg(store):
    """Kimi attack #6: hg_ticket_id='   ' must not satisfy the check."""
    g = GateGuardian(ontology=store)
    e = _ev("advisor.action.executed", d_level="D3", hg_ticket_id="   ")
    assert g.on_event(e) is not None


def test_gate_guardian_alerts_with_lowercase_d(store):
    g = GateGuardian(ontology=store)
    e = _ev("advisor.action.executed", d_level="d4")
    assert g.on_event(e) is not None


def test_gate_guardian_quiet_with_hg(store):
    g = GateGuardian(ontology=store)
    e = _ev("advisor.action.executed", d_level="D3", hg_ticket_id="hg_x")
    assert g.on_event(e) is None


@pytest.mark.parametrize("d", ["D0", "D1", "D2"])
def test_gate_guardian_quiet_on_low_d(store, d):
    g = GateGuardian(ontology=store)
    e = _ev("advisor.action.executed", d_level=d)
    assert g.on_event(e) is None


# ---------------------------------------------------------------------------
# 7. CouncilGuardian
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("d", ["D4", "D5"])
def test_council_guardian_alerts_when_missing_session(store, d):
    g = CouncilGuardian(ontology=store)
    assert g.on_event(_ev("advisor.action.executed", d_level=d)) is not None


def test_council_guardian_alerts_on_release_promotion_d4(store):
    g = CouncilGuardian(ontology=store)
    assert g.on_event(_ev("release.candidate.promoted", d_level="D4")) is not None


def test_council_guardian_alerts_d5_no_session(store):
    g = CouncilGuardian(ontology=store)
    assert g.on_event(_ev("advisor.action.executed", d_level="D5")) is not None


def test_council_guardian_alerts_d5_blank_session(store):
    g = CouncilGuardian(ontology=store)
    e = _ev("advisor.action.executed", d_level="D5", council_session_id="")
    assert g.on_event(e) is not None


def test_council_guardian_quiet_with_session(store):
    g = CouncilGuardian(ontology=store)
    e = _ev("advisor.action.executed", d_level="D4", council_session_id="cs_1")
    assert g.on_event(e) is None


@pytest.mark.parametrize("d", ["D0", "D1", "D2", "D3"])
def test_council_guardian_quiet_on_lower_d(store, d):
    g = CouncilGuardian(ontology=store)
    assert g.on_event(_ev("advisor.action.executed", d_level=d)) is None


# ---------------------------------------------------------------------------
# 8. ReleaseGuardian
# ---------------------------------------------------------------------------


def test_release_alerts_on_unmet_checklist(store):
    g = ReleaseGuardian(ontology=store)
    e = _ev("aeis.testing.release.candidate_ready",
            checklist_results={"sot_approved": True, "no_p0_p1_findings": False})
    alert = g.on_event(e)
    assert alert is not None and alert.severity == "P0"


def test_release_alerts_on_unresolved_findings(store):
    g = ReleaseGuardian(ontology=store)
    e = _ev("aeis.testing.release.candidate_ready",
            unresolved_findings=["find_1", "find_2"])
    alert = g.on_event(e)
    assert alert is not None and alert.severity == "P1"


def test_release_alerts_when_both_unmet_and_unresolved(store):
    g = ReleaseGuardian(ontology=store)
    e = _ev("aeis.testing.release.production_ready",
            checklist_results={"all_mandatory_tests_passed": False},
            unresolved_findings=["find_1"])
    assert g.on_event(e) is not None


def test_release_alerts_on_multiple_unmet(store):
    g = ReleaseGuardian(ontology=store)
    e = _ev("aeis.testing.release.candidate_ready",
            checklist_results={
                "sot_approved": False,
                "regression_passed": False,
                "no_mock_as_live": False,
            })
    assert g.on_event(e) is not None


def test_release_alerts_unmet_overrides_severity(store):
    g = ReleaseGuardian(ontology=store)
    e = _ev("aeis.testing.release.candidate_ready",
            checklist_results={"audit_chain_intact": False})
    alert = g.on_event(e)
    assert alert.severity == "P0"


def test_release_quiet_on_clean_release(store):
    g = ReleaseGuardian(ontology=store)
    e = _ev("aeis.testing.release.candidate_ready",
            checklist_results={"sot_approved": True})
    assert g.on_event(e) is None


def test_release_quiet_no_unresolved_no_checklist(store):
    g = ReleaseGuardian(ontology=store)
    assert g.on_event(_ev("aeis.testing.release.candidate_ready")) is None


# ---------------------------------------------------------------------------
# 9. LoopGuardian
# ---------------------------------------------------------------------------


def _make_attempts(store, finding_id: str, count: int) -> None:
    for n in range(1, count + 1):
        store.create(RepairAttempt(
            finding_id=finding_id, n=n, r_phase="REPAIRING",
            result="failed_same",
        ))


def test_loop_alerts_on_loop_detected(store):
    g = LoopGuardian(ontology=store)
    e = _ev("aeis.testing.loop.detected",
            finding_id="find_xxx", report_id="lr_xxx")
    assert g.on_event(e) is not None


def test_loop_alerts_when_attempts_above_threshold_no_report(store):
    f = Finding(title="x", description="y", discovered_by="z")
    store.create(f)
    _make_attempts(store, f.finding_id, 3)
    g = LoopGuardian(ontology=store)
    e = _ev("aeis.testing.repair.attempt_completed", finding_id=f.finding_id)
    assert g.on_event(e) is not None


def test_loop_quiet_when_attempts_at_threshold(store):
    f = Finding(title="x", description="y", discovered_by="z")
    store.create(f)
    _make_attempts(store, f.finding_id, 2)
    g = LoopGuardian(ontology=store)
    e = _ev("aeis.testing.repair.attempt_completed", finding_id=f.finding_id)
    assert g.on_event(e) is None


def test_loop_quiet_when_loop_report_exists(store):
    f = Finding(title="x", description="y", discovered_by="z")
    store.create(f)
    _make_attempts(store, f.finding_id, 5)
    store.create(LoopReport(
        finding_id=f.finding_id, loop_type="same_failure",
        attempts_n=5, similarity_score=0.5,
        suspected_root_cause=["x"], blocked_actions=["y"],
        required_decision={"q": "?"},
    ))
    g = LoopGuardian(ontology=store)
    e = _ev("aeis.testing.repair.attempt_completed", finding_id=f.finding_id)
    assert g.on_event(e) is None


def test_loop_quiet_without_finding_id(store):
    g = LoopGuardian(ontology=store)
    assert g.on_event(_ev("aeis.testing.repair.attempt_completed")) is None


def test_loop_quiet_unknown_topic(store):
    g = LoopGuardian(ontology=store)
    assert g.on_event(_ev("random.topic", finding_id="find_x")) is None


# ---------------------------------------------------------------------------
# 10. LLMDriftGuardian
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rate", [0.06, 0.1, 0.2, 0.5, 1.0])
def test_drift_alerts_above_threshold(store, rate):
    g = LLMDriftGuardian(ontology=store)
    e = _ev("llm.evaluation.completed", divergence_rate=rate)
    assert g.on_event(e) is not None


@pytest.mark.parametrize("rate", [0.0, 0.01, 0.04, 0.05])
def test_drift_quiet_below_or_at_threshold(store, rate):
    g = LLMDriftGuardian(ontology=store)
    e = _ev("llm.evaluation.completed", divergence_rate=rate)
    assert g.on_event(e) is None


def test_drift_quiet_no_divergence_field(store):
    g = LLMDriftGuardian(ontology=store)
    assert g.on_event(_ev("llm.evaluation.completed")) is None


# ---------------------------------------------------------------------------
# 11. CostSentinel
# ---------------------------------------------------------------------------


def test_cost_alerts_on_spike(store):
    g = CostSentinel(ontology=store)
    e = _ev("llm.request.completed", cost_usd=10.0, baseline_cost_usd=0.1)
    assert g.on_event(e) is not None


def test_cost_alerts_on_budget_overrun(store):
    g = CostSentinel(ontology=store)
    assert g.on_event(_ev("project.budget.snapshot", used_pct=1.05)) is not None


def test_cost_warns_at_70_pct_budget(store):
    g = CostSentinel(ontology=store)
    alert = g.on_event(_ev("project.budget.snapshot", used_pct=0.75))
    assert alert is not None and alert.severity == "P2"


def test_cost_safe_against_nan_baseline(store):
    """Kimi attack #3: NaN baseline must not slip past comparison."""
    g = CostSentinel(ontology=store)
    e = _ev("llm.request.completed", cost_usd=1.0,
            baseline_cost_usd=float("nan"))
    # Treat NaN as missing -> floor 1e-6 -> 1.0 > 1e-5 -> alert
    assert g.on_event(e) is not None


def test_cost_safe_against_negative_baseline(store):
    g = CostSentinel(ontology=store)
    e = _ev("llm.request.completed", cost_usd=0.001,
            baseline_cost_usd=-100.0)
    # Negative baseline -> floor; 0.001 > 1e-5 by 100x -> alert
    assert g.on_event(e) is not None


def test_cost_quiet_within_normal(store):
    g = CostSentinel(ontology=store)
    e = _ev("llm.request.completed", cost_usd=0.5, baseline_cost_usd=0.1)
    assert g.on_event(e) is None


def test_cost_quiet_low_budget(store):
    g = CostSentinel(ontology=store)
    assert g.on_event(_ev("project.budget.snapshot", used_pct=0.4)) is None


# ---------------------------------------------------------------------------
# 12. PIIGuardian
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,kind", [
    ("Contact: alice@example.com", "email"),
    ("Phone: +48 600 700 800", "phone_pl"),
    ("PESEL: 12345678901", "pesel"),
    ("Card 4111 1111 1111 1111", "credit_card"),
    ("My email john.doe@x.io please", "email"),
])
def test_pii_alerts_on_known_patterns(store, text, kind):
    g = PIIGuardian(ontology=store)
    alert = g.on_event(_ev("log.line.emitted", log_line=text))
    assert alert is not None
    assert alert.evidence_link.get("pii_kind") == kind


def test_pii_alerts_on_email_in_summary(store):
    g = PIIGuardian(ontology=store)
    e = _ev("evidence_pack.artefact_added", summary="from a@b.co")
    assert g.on_event(e) is not None


def test_pii_alert_redacts_sample(store):
    g = PIIGuardian(ontology=store)
    alert = g.on_event(_ev("log.line.emitted", log_line="alice@example.com"))
    assert alert is not None
    assert alert.evidence_link.get("redacted_match") == "[REDACTED]"


def test_pii_quiet_on_clean_text(store):
    g = PIIGuardian(ontology=store)
    e = _ev("log.line.emitted", log_line="hello world (no secrets)")
    assert g.on_event(e) is None


def test_pii_quiet_when_no_scannable_field(store):
    g = PIIGuardian(ontology=store)
    assert g.on_event(_ev("log.line.emitted")) is None


def test_pii_quiet_on_empty_text(store):
    g = PIIGuardian(ontology=store)
    e = _ev("log.line.emitted", content="", log_line="")
    assert g.on_event(e) is None


# ---------------------------------------------------------------------------
# 13. TraceCompletenessGuardian
# ---------------------------------------------------------------------------


def test_trace_alerts_on_d3_no_chain(store):
    g = TraceCompletenessGuardian(ontology=store)
    assert g.on_event(_ev("advisor.action.executed", d_level="D3")) is not None


def test_trace_alerts_on_d4_partial_chain(store):
    g = TraceCompletenessGuardian(ontology=store)
    e = _ev("advisor.action.executed", d_level="D4", trace_id="t",
            correlation_id="c")  # causation_id missing
    assert g.on_event(e) is not None


def test_trace_alerts_on_blank_trace_id(store):
    """Whitespace-only chain fields don't satisfy the rule."""
    g = TraceCompletenessGuardian(ontology=store)
    e = _ev("advisor.action.executed", d_level="D5",
            trace_id=" ", correlation_id="c", causation_id="cz")
    assert g.on_event(e) is not None


def test_trace_alerts_on_d5_no_correlation(store):
    g = TraceCompletenessGuardian(ontology=store)
    e = _ev("advisor.action.executed", d_level="D5",
            trace_id="t", causation_id="cz")
    assert g.on_event(e) is not None


def test_trace_alerts_on_d3_lowercase(store):
    g = TraceCompletenessGuardian(ontology=store)
    e = _ev("advisor.action.executed", d_level="d3")
    assert g.on_event(e) is not None


def test_trace_quiet_with_full_chain(store):
    g = TraceCompletenessGuardian(ontology=store)
    e = _ev("advisor.action.executed", d_level="D3",
            trace_id="t", correlation_id="c", causation_id="cz")
    assert g.on_event(e) is None


@pytest.mark.parametrize("d", ["D0", "D1", "D2"])
def test_trace_quiet_on_low_d(store, d):
    g = TraceCompletenessGuardian(ontology=store)
    e = _ev("advisor.action.executed", d_level=d)
    assert g.on_event(e) is None
