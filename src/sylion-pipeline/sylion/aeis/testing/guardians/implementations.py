"""13 W14 Guardian implementations (8 core + 5 NEW from canonical spec sec 13)."""
from __future__ import annotations

import re as _re
import unicodedata as _ud
from typing import Any

from sylion.aeis.testing.guardians.base import GuardianBase
from sylion.aeis.testing.ontology.enums import GuardianClass, Severity
from sylion.aeis.testing.ontology.objects import GuardianAlert


def _ev(event: Any, key: str, default: Any = None) -> Any:
    """Safe payload field access — works for SylionEvent and dict."""
    if event is None:
        return default
    payload = getattr(event, "payload", None)
    if isinstance(payload, dict):
        return payload.get(key, default)
    if isinstance(event, dict):
        inner = event.get("payload", {})
        if isinstance(inner, dict):
            return inner.get(key, default)
    return default


def _topic(event: Any) -> str:
    if event is None:
        return ""
    return getattr(event, "topic", None) or getattr(event, "event_type", "") or ""


def _norm(value: Any) -> str:
    """Defensive normalization for header-like fields: strip+casefold."""
    if not isinstance(value, str):
        return ""
    return value.strip().casefold()


def _truthy(value: Any) -> bool:
    """A 'present' check that treats whitespace-only strings as falsy.

    Counters Kimi attack #6 (hg_ticket_id=' ' bypasses ``not hg``).
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


# ----------------------------------------------------------------------
# 1. SoT Guardian — runtime function/endpoint not in SoT
# ----------------------------------------------------------------------

class SoTGuardian(GuardianBase):
    name = GuardianClass.SOT_GUARDIAN.value
    subscribed_events = (
        "aeis.testing.run.completed",
        "advisor.action.executed",
    )

    def on_event(self, event: Any) -> GuardianAlert | None:
        feature_id = _ev(event, "feature_id")
        in_sot = _ev(event, "in_sot", True)
        if feature_id and not in_sot:
            return self._alert(
                self.name, Severity.P1,
                f"Feature '{feature_id}' executed but not in Source of Truth",
                evidence_link={"event_topic": _topic(event), "feature_id": feature_id},
            )
        return None


# ----------------------------------------------------------------------
# 2. Masterplan Guardian — module not declared in Masterplan
# ----------------------------------------------------------------------

class MasterplanGuardian(GuardianBase):
    name = GuardianClass.MASTERPLAN_GUARDIAN.value
    subscribed_events = ("module.registered", "module.executed")

    def on_event(self, event: Any) -> GuardianAlert | None:
        module_id = _ev(event, "module_id")
        in_masterplan = _ev(event, "in_masterplan", True)
        if module_id and not in_masterplan:
            return self._alert(
                self.name, Severity.P1,
                f"Module '{module_id}' active but not in Masterplan",
                evidence_link={"event_topic": _topic(event), "module_id": module_id},
            )
        return None


# ----------------------------------------------------------------------
# 3. Test Integrity Guardian — assertion weakening / test deletion
# ----------------------------------------------------------------------

class TestIntegrityGuardian(GuardianBase):
    name = GuardianClass.TEST_INTEGRITY_GUARDIAN.value
    subscribed_events = ("git.commit.applied", "aeis.testing.case.disabled")

    # Codex bug #5: detect assertion weakening (removed asserts /
    # converted to skip / xfail) on top of deletion + disable.
    _ASSERT_WEAK_MARKERS: tuple[str, ...] = (
        "-    assert ", "-assert ",
        "@pytest.mark.skip", "@pytest.mark.xfail",
    )

    def on_event(self, event: Any) -> GuardianAlert | None:
        topic = _topic(event)
        trace_id = _ev(event, "trace_id")
        if topic == "aeis.testing.case.disabled":
            council = _ev(event, "council_session_id")
            hg = _ev(event, "hg_ticket_id")
            if not _truthy(council) or not _truthy(hg):
                return self._alert(
                    self.name, Severity.P0,
                    "Test disabled without Council session or HG ticket",
                    evidence_link={"event_topic": topic},
                    trace_id=trace_id,
                )
        if _ev(event, "test_file_deleted"):
            return self._alert(
                self.name, Severity.P0,
                f"Test file deleted: {_ev(event, 'file', '?')}",
                evidence_link={"event_topic": topic},
                trace_id=trace_id,
            )
        diff = _ev(event, "diff_text", "") or ""
        if isinstance(diff, str) and diff:
            lower = diff.casefold()
            if any(m in lower for m in self._ASSERT_WEAK_MARKERS):
                if not _truthy(_ev(event, "hg_ticket_id")):
                    return self._alert(
                        self.name, Severity.P0,
                        "Assertion weakened or test marked skip/xfail without HG",
                        evidence_link={"event_topic": topic},
                        trace_id=trace_id,
                    )
        return None


# ----------------------------------------------------------------------
# 4. Mock / Fallback Guardian — mock-as-live + production action on mock
# ----------------------------------------------------------------------

class MockFallbackGuardian(GuardianBase):
    name = GuardianClass.MOCK_FALLBACK_GUARDIAN.value
    subscribed_events = (
        "advisor.action.about_to_execute",
        "ui.endpoint.response_emitted",
    )

    BLOCK_DLEVELS = ("D3", "D4", "D5")
    BAD_SOURCES = ("mock", "demo", "fallback", "cache_stale")

    def on_event(self, event: Any) -> GuardianAlert | None:
        data_source = _norm(_ev(event, "data_source", "live")) or "live"
        d_level = _norm(_ev(event, "d_level", "D0")).upper()
        # Compare against case-folded variants so "Mock", "MOCK ", " demo "
        # cannot slip past (Kimi attack #5).
        bad = tuple(s.casefold() for s in self.BAD_SOURCES)
        block = tuple(s.upper() for s in self.BLOCK_DLEVELS)
        if data_source in bad and d_level in block:
            return self._alert(
                self.name, Severity.P0,
                f"D3+ action attempted on '{data_source}' data",
                evidence_link={
                    "event_topic": _topic(event),
                    "data_source": data_source,
                    "d_level": d_level,
                },
            )
        return None


# ----------------------------------------------------------------------
# 5. Evidence Guardian — PASS event without evidence fields
# ----------------------------------------------------------------------

class EvidenceGuardian(GuardianBase):
    name = GuardianClass.EVIDENCE_GUARDIAN.value
    subscribed_events = (
        "aeis.testing.case.passed",
        "aeis.testing.run.completed",
    )

    REQUIRED_FIELDS = ("run_id", "trace_id")

    def on_event(self, event: Any) -> GuardianAlert | None:
        topic = _topic(event)
        # Codex bug #10: only fire on PASS semantics, not every subscribed
        # topic. case.passed is intrinsically PASS; run.completed is PASS
        # iff payload.status == 'passed'.
        is_pass = topic.endswith(".case.passed") or (
            topic.endswith(".run.completed")
            and _norm(_ev(event, "status", "")) == "passed"
        )
        if not is_pass:
            return None
        missing = [
            f for f in self.REQUIRED_FIELDS
            if not _truthy(_ev(event, f))
        ]
        if missing:
            return self._alert(
                self.name, Severity.P1,
                f"PASS event missing evidence fields: {missing}",
                evidence_link={"event_topic": topic, "missing": missing},
                trace_id=_ev(event, "trace_id"),
            )
        return None


# ----------------------------------------------------------------------
# 6. Gate Guardian — D3+ action without HG ticket
# ----------------------------------------------------------------------

class GateGuardian(GuardianBase):
    name = GuardianClass.GATE_GUARDIAN.value
    subscribed_events = ("advisor.action.executed", "intent.applied")

    def on_event(self, event: Any) -> GuardianAlert | None:
        d = _norm(_ev(event, "d_level", "D0")).upper()
        hg = _ev(event, "hg_ticket_id")
        if d in ("D3", "D4", "D5") and not _truthy(hg):
            return self._alert(
                self.name, Severity.P0,
                f"{d} action executed without Human Gate ticket",
                evidence_link={"event_topic": _topic(event), "d_level": d},
            )
        return None


# ----------------------------------------------------------------------
# 7. Council Guardian — D4/D5 without Council session
# ----------------------------------------------------------------------

class CouncilGuardian(GuardianBase):
    name = GuardianClass.COUNCIL_GUARDIAN.value
    subscribed_events = ("advisor.action.executed", "release.candidate.promoted")

    def on_event(self, event: Any) -> GuardianAlert | None:
        d = _ev(event, "d_level", "D0")
        council = _ev(event, "council_session_id")
        if d in ("D4", "D5") and not council:
            return self._alert(
                self.name, Severity.P0,
                f"{d} action without Council session_id",
                evidence_link={"event_topic": _topic(event), "d_level": d},
            )
        return None


# ----------------------------------------------------------------------
# 8. Release Guardian — release event with unmet checklist
# ----------------------------------------------------------------------

class ReleaseGuardian(GuardianBase):
    name = GuardianClass.RELEASE_GUARDIAN.value
    subscribed_events = (
        "aeis.testing.release.candidate_ready",
        "aeis.testing.release.production_ready",
    )

    # Canonical 12+6 ReleaseRail checklist items. We treat any item
    # explicitly set to False as an unmet check; missing keys are not
    # treated as failures because the publisher may not have evaluated
    # them yet (the gate downstream still enforces).
    RELEASE_CHECKLIST: tuple[str, ...] = (
        "sot_approved", "masterplan_approved", "test_charter_approved",
        "all_mandatory_tests_passed", "every_pass_has_evidence",
        "no_p0_p1_findings", "d3_findings_decided",
        "regression_passed", "human_like_passed",
        "audit_chain_intact", "no_mock_as_live",
        "artifact_hashes_present",
    )

    def on_event(self, event: Any) -> GuardianAlert | None:
        topic = _topic(event)
        trace_id = _ev(event, "trace_id")
        unresolved = _ev(event, "unresolved_findings", []) or []
        checklist = _ev(event, "checklist_results", {}) or {}
        unmet: list[str] = []
        if isinstance(checklist, dict):
            for item in self.RELEASE_CHECKLIST:
                if item in checklist and checklist[item] is False:
                    unmet.append(item)
        if unmet:
            return self._alert(
                self.name, Severity.P0,
                f"Release event with {len(unmet)} unmet checklist item(s): {unmet}",
                evidence_link={
                    "event_topic": topic,
                    "unmet_checklist": unmet,
                    "unresolved_findings": len(unresolved) if unresolved else 0,
                },
                trace_id=trace_id,
            )
        if unresolved:
            return self._alert(
                self.name, Severity.P1,
                f"Release event with {len(unresolved)} unresolved finding(s)",
                evidence_link={"event_topic": topic, "count": len(unresolved)},
                trace_id=trace_id,
            )
        return None


# ----------------------------------------------------------------------
# 9. Loop Guardian — confirms Loop Governor blocks visibly
# ----------------------------------------------------------------------

class LoopGuardian(GuardianBase):
    name = GuardianClass.LOOP_GUARDIAN.value
    subscribed_events = (
        "aeis.testing.repair.attempt_completed",
        "aeis.testing.loop.detected",
    )

    # C5 contract: alert when repair attempts > 2 without an open LoopReport.
    ATTEMPT_THRESHOLD = 2

    def on_event(self, event: Any) -> GuardianAlert | None:
        topic = _topic(event)
        trace_id = _ev(event, "trace_id")
        if topic == "aeis.testing.loop.detected":
            return self._alert(
                self.name, Severity.P1,
                "Loop Governor detected blocking pattern",
                evidence_link={
                    "event_topic": topic,
                    "report_id": _ev(event, "report_id"),
                },
                finding_id=_ev(event, "finding_id"),
                trace_id=trace_id,
            )
        # attempt_completed: count attempts vs LoopReport for the finding.
        if topic == "aeis.testing.repair.attempt_completed":
            finding_id = _ev(event, "finding_id")
            if not finding_id or self.ontology is None:
                return None
            try:
                from sylion.aeis.testing.ontology.objects import (
                    LoopReport, RepairAttempt,
                )
                attempts = self.ontology.list(
                    RepairAttempt,
                    filters={"finding_id": finding_id},
                    limit=1000,
                )
                if len(attempts) <= self.ATTEMPT_THRESHOLD:
                    return None
                reports = self.ontology.list(
                    LoopReport,
                    filters={"finding_id": finding_id},
                    limit=10,
                )
                if reports:
                    return None
            except Exception:  # pragma: no cover
                return None
            return self._alert(
                self.name, Severity.P1,
                f"Repair attempts ({len(attempts)}) > {self.ATTEMPT_THRESHOLD} "
                f"without a LoopReport for finding {finding_id}",
                evidence_link={
                    "event_topic": topic,
                    "finding_id": finding_id,
                    "attempts": len(attempts),
                },
                finding_id=finding_id,
                trace_id=trace_id,
            )
        return None


# ----------------------------------------------------------------------
# 10. LLM Drift Guardian — model A vs B divergence > 5%
# ----------------------------------------------------------------------

class LLMDriftGuardian(GuardianBase):
    name = GuardianClass.LLM_DRIFT_GUARDIAN.value
    subscribed_events = ("llm.evaluation.completed",)

    DRIFT_THRESHOLD = 0.05

    def on_event(self, event: Any) -> GuardianAlert | None:
        divergence = float(_ev(event, "divergence_rate", 0.0) or 0.0)
        if divergence > self.DRIFT_THRESHOLD:
            return self._alert(
                self.name, Severity.P2,
                f"Model drift detected: {divergence:.2%} divergence",
                evidence_link={
                    "event_topic": _topic(event),
                    "baseline_model": _ev(event, "baseline_model"),
                    "new_model": _ev(event, "new_model"),
                    "divergence": divergence,
                },
            )
        return None


# ----------------------------------------------------------------------
# 11. Cost Sentinel — request cost > 10x baseline OR project budget overrun
# ----------------------------------------------------------------------

class CostSentinel(GuardianBase):
    name = GuardianClass.COST_SENTINEL.value
    subscribed_events = ("llm.request.completed", "project.budget.snapshot")

    SPIKE_MULTIPLIER = 10.0
    BUDGET_WARN_PCT = 0.7
    # Floor + ceiling guards for caller-supplied numerics so NaN / inf /
    # negative tricks (Kimi attack #3) can't bypass thresholds.
    BASELINE_FLOOR = 1e-6
    COST_CEILING = 1e9

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        import math
        try:
            f = float(value if value is not None else default)
        except (TypeError, ValueError, OverflowError):
            return default
        if not math.isfinite(f):
            return default
        return f

    def on_event(self, event: Any) -> GuardianAlert | None:
        topic = _topic(event)
        trace_id = _ev(event, "trace_id")
        if topic == "llm.request.completed":
            cost = max(0.0, self._safe_float(_ev(event, "cost_usd", 0.0)))
            baseline = self._safe_float(
                _ev(event, "baseline_cost_usd", 0.0), default=0.0,
            )
            # Treat absent / non-positive baseline as the floor so the
            # threshold math is well-defined and integer overflow is
            # impossible (Kimi attack #3).
            if baseline <= 0 or baseline > self.COST_CEILING:
                baseline = self.BASELINE_FLOOR
            cost = min(cost, self.COST_CEILING)
            if cost > baseline * self.SPIKE_MULTIPLIER:
                return self._alert(
                    self.name, Severity.P1,
                    f"LLM cost spike: {cost:.4f} USD vs baseline {baseline:.4f}",
                    evidence_link={"event_topic": topic, "ratio": cost / baseline},
                    trace_id=trace_id,
                )
        elif topic == "project.budget.snapshot":
            used = max(0.0, self._safe_float(_ev(event, "used_pct", 0.0)))
            if used >= 1.0:
                return self._alert(
                    self.name, Severity.P0,
                    f"Project budget OVERRUN ({used:.0%})",
                    evidence_link={"event_topic": topic, "used_pct": used},
                    trace_id=trace_id,
                )
            elif used >= self.BUDGET_WARN_PCT:
                return self._alert(
                    self.name, Severity.P2,
                    f"Project budget warning ({used:.0%})",
                    evidence_link={"event_topic": topic, "used_pct": used},
                    trace_id=trace_id,
                )
        return None


# ----------------------------------------------------------------------
# 12. PII Guardian — payload/log/evidence contains PII
# ----------------------------------------------------------------------

class PIIGuardian(GuardianBase):
    name = GuardianClass.PII_GUARDIAN.value
    subscribed_events = (
        "evidence_pack.artefact_added",
        "log.line.emitted",
    )

    # Wider field set; case-insensitive scan over NFKC-normalized text so
    # Unicode look-alikes (Kimi attack #2) can't bypass detection.
    SCAN_FIELDS: tuple[str, ...] = (
        "content", "log_line", "summary", "description",
        "title", "rationale", "message", "body", "text",
    )
    PATTERNS: tuple[tuple[str, "_re.Pattern"], ...] = (
        ("email", _re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", _re.IGNORECASE)),
        ("phone_pl", _re.compile(r"\b\+?48[ -]?\d{3}[ -]?\d{3}[ -]?\d{3}\b")),
        ("pesel", _re.compile(r"\b\d{11}\b")),
        ("credit_card", _re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    )

    @staticmethod
    def _redact(text: str, pattern: "_re.Pattern") -> str:
        return pattern.sub("[REDACTED]", text)

    def on_event(self, event: Any) -> GuardianAlert | None:
        # Aggregate scannable text — NFKC-normalize so visually-equivalent
        # Unicode glyphs collapse to ASCII for pattern matching.
        parts: list[str] = []
        for k in self.SCAN_FIELDS:
            v = _ev(event, k)
            if isinstance(v, str):
                parts.append(_ud.normalize("NFKC", v))
        if not parts:
            return None
        text = " ".join(parts)
        if not text.strip():
            return None
        for pii_kind, pattern in self.PATTERNS:
            match = pattern.search(text)
            if match:
                redacted_sample = self._redact(match.group(0), pattern)
                return self._alert(
                    self.name, Severity.P1,
                    f"PII detected in event payload: {pii_kind}",
                    evidence_link={
                        "event_topic": _topic(event),
                        "pii_kind": pii_kind,
                        "redacted_match": redacted_sample,
                    },
                    trace_id=_ev(event, "trace_id"),
                )
        return None


# ----------------------------------------------------------------------
# 13. Trace Completeness Guardian — D3+ action without trace_id chain
# ----------------------------------------------------------------------

class TraceCompletenessGuardian(GuardianBase):
    name = GuardianClass.TRACE_COMPLETENESS_GUARDIAN.value
    subscribed_events = ("advisor.action.executed", "intent.applied")

    # Required chain fields per W14 sec 16 (causation linkage):
    # trace_id (correlates the whole flow) plus correlation_id +
    # causation_id (links this event to its trigger).
    CHAIN_FIELDS: tuple[str, ...] = ("trace_id", "correlation_id", "causation_id")

    def on_event(self, event: Any) -> GuardianAlert | None:
        d = _norm(_ev(event, "d_level", "D0")).upper()
        if d not in ("D3", "D4", "D5"):
            return None
        missing = [f for f in self.CHAIN_FIELDS if not _truthy(_ev(event, f))]
        if missing:
            return self._alert(
                self.name, Severity.P1,
                f"{d} action with incomplete trace chain (missing: {missing})",
                evidence_link={
                    "event_topic": _topic(event),
                    "d_level": d,
                    "missing_chain_fields": missing,
                },
                trace_id=_ev(event, "trace_id"),
            )
        return None


ALL_GUARDIAN_CLASSES: tuple[type[GuardianBase], ...] = (
    SoTGuardian,
    MasterplanGuardian,
    TestIntegrityGuardian,
    MockFallbackGuardian,
    EvidenceGuardian,
    GateGuardian,
    CouncilGuardian,
    ReleaseGuardian,
    LoopGuardian,
    LLMDriftGuardian,
    CostSentinel,
    PIIGuardian,
    TraceCompletenessGuardian,
)


__all__ = [
    "ALL_GUARDIAN_CLASSES",
    "SoTGuardian", "MasterplanGuardian", "TestIntegrityGuardian",
    "MockFallbackGuardian", "EvidenceGuardian", "GateGuardian",
    "CouncilGuardian", "ReleaseGuardian", "LoopGuardian",
    "LLMDriftGuardian", "CostSentinel", "PIIGuardian",
    "TraceCompletenessGuardian",
]
