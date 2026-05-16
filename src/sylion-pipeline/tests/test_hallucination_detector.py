"""
Comprehensive tests for sylion.cognitive.hallucination_detector -- HallucinationDetector

Covers:
  - check_claim CRUD (create, read via get_check, list_checks)
  - verify_check status transitions
  - resolve_check
  - list_checks with filters (status, source_type, limit)
  - get_stats aggregation (total, by_status, by_source_type, avg_confidence)
  - detect_patterns (source_type recurring, claim_prefix recurring, upsert)
  - event emission on hallucination.detected
  - input validation (source_type, status)
  - confidence clamping
  - get_check returns None for unknown IDs
  - verify_check / resolve_check return None for unknown IDs
  - empty-db edge cases
  - thread safety under concurrent writes
  - singleton get/reset functions
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.hallucination_detector import (
    HallucinationDetector,
    get_hallucination_detector,
    reset_hallucination_detector,
    VALID_STATUSES,
    VALID_SOURCE_TYPES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def detector():
    """Fresh in-memory HallucinationDetector with no event bus."""
    return HallucinationDetector()


@pytest.fixture
def detector_with_bus():
    """Detector wired to a fresh EventBus so events can be captured."""
    bus = EventBus()
    d = HallucinationDetector(event_bus=bus)
    return d, bus


# ===========================================================================
# 1. check_claim() -- create
# ===========================================================================

class TestCheckClaim:

    def test_returns_check_id(self, detector):
        result = detector.check_claim("llm_call", "call-001", "The sky is green")
        assert "check_id" in result
        assert len(result["check_id"]) == 32  # uuid hex

    def test_preserves_fields(self, detector):
        result = detector.check_claim(
            "chat_message", "msg-42", "2+2=5", expected_answer="4",
        )
        assert result["source_type"] == "chat_message"
        assert result["source_id"] == "msg-42"
        assert result["claim"] == "2+2=5"
        assert result["evidence"] == "4"

    def test_default_status_is_pending(self, detector):
        result = detector.check_claim("llm_call", "c1", "claim text")
        assert result["verification_status"] == "pending"

    def test_default_confidence_is_zero(self, detector):
        result = detector.check_claim("llm_call", "c1", "claim")
        assert result["confidence"] == 0.0

    def test_auto_sets_detected_at(self, detector):
        before = time.time()
        result = detector.check_claim("llm_call", "c1", "claim")
        after = time.time()
        assert before <= result["detected_at"] <= after

    def test_resolved_at_is_none_initially(self, detector):
        result = detector.check_claim("llm_call", "c1", "claim")
        assert result["resolved_at"] is None

    def test_invalid_source_type_raises(self, detector):
        with pytest.raises(ValueError, match="Invalid source_type"):
            detector.check_claim("invalid_type", "c1", "claim")

    def test_expected_answer_stored_as_evidence(self, detector):
        result = detector.check_claim(
            "plan_task", "task-7", "The function returns True",
            expected_answer="The function returns False",
        )
        assert result["evidence"] == "The function returns False"


# ===========================================================================
# 2. get_check() -- read
# ===========================================================================

class TestGetCheck:

    def test_returns_full_record(self, detector):
        created = detector.check_claim("llm_call", "call-99", "test claim")
        fetched = detector.get_check(created["check_id"])
        assert fetched is not None
        assert fetched["check_id"] == created["check_id"]
        assert fetched["source_type"] == "llm_call"
        assert fetched["source_id"] == "call-99"
        assert fetched["claim"] == "test claim"
        assert fetched["verification_status"] == "pending"

    def test_nonexistent_returns_none(self, detector):
        assert detector.get_check("does_not_exist") is None


# ===========================================================================
# 3. verify_check() -- status transitions
# ===========================================================================

class TestVerifyCheck:

    def test_verify_as_hallucination(self, detector):
        created = detector.check_claim("llm_call", "c1", "wrong answer")
        result = detector.verify_check(created["check_id"], True, 0.92, "Fact check failed")
        assert result is not None
        assert result["verification_status"] == "hallucination"
        assert result["confidence"] == 0.92
        assert result["evidence"] == "Fact check failed"

    def test_verify_as_not_hallucination(self, detector):
        created = detector.check_claim("council_analysis", "ca-1", "correct claim")
        result = detector.verify_check(created["check_id"], False, 0.15, "Looks correct")
        assert result is not None
        assert result["verification_status"] == "verified"
        assert result["confidence"] == 0.15

    def test_nonexistent_check_returns_none(self, detector):
        result = detector.verify_check("nonexistent_id", True, 0.9, "evidence")
        assert result is None

    def test_confidence_clamped_high(self, detector):
        created = detector.check_claim("llm_call", "c1", "claim")
        result = detector.verify_check(created["check_id"], True, 1.5, "")
        assert result["confidence"] == 1.0

    def test_confidence_clamped_low(self, detector):
        created = detector.check_claim("llm_call", "c1", "claim")
        result = detector.verify_check(created["check_id"], False, -0.5, "")
        assert result["confidence"] == 0.0

    def test_confidence_boundary_zero(self, detector):
        created = detector.check_claim("llm_call", "c1", "claim")
        result = detector.verify_check(created["check_id"], True, 0.0, "")
        assert result["confidence"] == 0.0

    def test_confidence_boundary_one(self, detector):
        created = detector.check_claim("llm_call", "c1", "claim")
        result = detector.verify_check(created["check_id"], True, 1.0, "")
        assert result["confidence"] == 1.0

    def test_verify_persists_in_db(self, detector):
        created = detector.check_claim("evaluation", "eval-1", "claim")
        detector.verify_check(created["check_id"], True, 0.88, "wrong")
        fetched = detector.get_check(created["check_id"])
        assert fetched["verification_status"] == "hallucination"
        assert fetched["confidence"] == 0.88


# ===========================================================================
# 4. resolve_check()
# ===========================================================================

class TestResolveCheck:

    def test_resolve_sets_timestamp(self, detector):
        created = detector.check_claim("llm_call", "c1", "claim")
        before = time.time()
        result = detector.resolve_check(created["check_id"])
        after = time.time()
        assert result is not None
        assert result["resolved_at"] is not None
        assert before <= result["resolved_at"] <= after

    def test_resolve_nonexistent_returns_none(self, detector):
        result = detector.resolve_check("nonexistent")
        assert result is None

    def test_resolve_preserves_other_fields(self, detector):
        created = detector.check_claim("chat_message", "msg-1", "claim text")
        detector.verify_check(created["check_id"], True, 0.75, "bad")
        result = detector.resolve_check(created["check_id"])
        assert result["check_id"] == created["check_id"]
        assert result["verification_status"] == "hallucination"
        assert result["confidence"] == 0.75
        assert result["claim"] == "claim text"

    def test_resolve_idempotent(self, detector):
        created = detector.check_claim("llm_call", "c1", "claim")
        first = detector.resolve_check(created["check_id"])
        second = detector.resolve_check(created["check_id"])
        assert second is not None
        # Second resolve updates the timestamp
        assert second["resolved_at"] >= first["resolved_at"]


# ===========================================================================
# 5. list_checks() -- filtering
# ===========================================================================

class TestListChecks:

    def test_list_all(self, detector):
        detector.check_claim("llm_call", "c1", "claim 1")
        detector.check_claim("chat_message", "c2", "claim 2")
        results = detector.list_checks()
        assert len(results) == 2

    def test_filter_by_status(self, detector):
        r1 = detector.check_claim("llm_call", "c1", "claim 1")
        detector.check_claim("llm_call", "c2", "claim 2")
        detector.verify_check(r1["check_id"], True, 0.9, "bad")
        results = detector.list_checks(status="hallucination")
        assert len(results) == 1
        assert results[0]["verification_status"] == "hallucination"

    def test_filter_by_source_type(self, detector):
        detector.check_claim("llm_call", "c1", "claim 1")
        detector.check_claim("chat_message", "c2", "claim 2")
        detector.check_claim("llm_call", "c3", "claim 3")
        results = detector.list_checks(source_type="llm_call")
        assert len(results) == 2

    def test_filter_by_both(self, detector):
        r1 = detector.check_claim("llm_call", "c1", "claim 1")
        detector.check_claim("llm_call", "c2", "claim 2")
        detector.check_claim("chat_message", "c3", "claim 3")
        detector.verify_check(r1["check_id"], True, 0.9, "")
        results = detector.list_checks(status="hallucination", source_type="llm_call")
        assert len(results) == 1
        assert results[0]["check_id"] == r1["check_id"]

    def test_limit(self, detector):
        for i in range(20):
            detector.check_claim("llm_call", f"c{i}", f"claim {i}")
        results = detector.list_checks(limit=5)
        assert len(results) == 5

    def test_no_match_returns_empty(self, detector):
        detector.check_claim("llm_call", "c1", "claim")
        results = detector.list_checks(source_type="chat_message")
        assert results == []

    def test_invalid_status_filter_raises(self, detector):
        with pytest.raises(ValueError, match="Invalid status"):
            detector.list_checks(status="invalid_status")

    def test_invalid_source_type_filter_raises(self, detector):
        with pytest.raises(ValueError, match="Invalid source_type"):
            detector.list_checks(source_type="invalid_source")

    def test_ordered_by_detected_at_desc(self, detector):
        r1 = detector.check_claim("llm_call", "c1", "first")
        r2 = detector.check_claim("llm_call", "c2", "second")
        results = detector.list_checks()
        assert results[0]["check_id"] == r2["check_id"]
        assert results[1]["check_id"] == r1["check_id"]


# ===========================================================================
# 6. get_stats() -- aggregation
# ===========================================================================

class TestGetStats:

    def test_empty_db(self, detector):
        stats = detector.get_stats()
        assert stats["total"] == 0
        assert stats["by_status"]["pending"] == 0
        assert stats["by_status"]["hallucination"] == 0
        assert stats["avg_hallucination_confidence"] == 0.0

    def test_counts_by_status(self, detector):
        r1 = detector.check_claim("llm_call", "c1", "claim 1")
        r2 = detector.check_claim("llm_call", "c2", "claim 2")
        r3 = detector.check_claim("llm_call", "c3", "claim 3")
        detector.verify_check(r1["check_id"], True, 0.9, "bad")
        detector.verify_check(r2["check_id"], False, 0.1, "ok")
        # r3 stays pending
        stats = detector.get_stats()
        assert stats["total"] == 3
        assert stats["by_status"]["hallucination"] == 1
        assert stats["by_status"]["verified"] == 1
        assert stats["by_status"]["pending"] == 1

    def test_counts_by_source_type(self, detector):
        detector.check_claim("llm_call", "c1", "claim 1")
        detector.check_claim("llm_call", "c2", "claim 2")
        detector.check_claim("chat_message", "c3", "claim 3")
        stats = detector.get_stats()
        assert stats["by_source_type"]["llm_call"] == 2
        assert stats["by_source_type"]["chat_message"] == 1

    def test_avg_hallucination_confidence(self, detector):
        r1 = detector.check_claim("llm_call", "c1", "claim 1")
        r2 = detector.check_claim("llm_call", "c2", "claim 2")
        detector.verify_check(r1["check_id"], True, 0.8, "")
        detector.verify_check(r2["check_id"], True, 0.6, "")
        stats = detector.get_stats()
        assert stats["avg_hallucination_confidence"] == pytest.approx(0.7, abs=0.01)

    def test_avg_confidence_excludes_non_hallucinations(self, detector):
        r1 = detector.check_claim("llm_call", "c1", "claim 1")
        r2 = detector.check_claim("llm_call", "c2", "claim 2")
        detector.verify_check(r1["check_id"], True, 0.9, "")
        detector.verify_check(r2["check_id"], False, 0.1, "")
        stats = detector.get_stats()
        assert stats["avg_hallucination_confidence"] == pytest.approx(0.9, abs=0.01)

    def test_all_status_keys_present(self, detector):
        stats = detector.get_stats()
        for status in VALID_STATUSES:
            assert status in stats["by_status"]


# ===========================================================================
# 7. detect_patterns()
# ===========================================================================

class TestDetectPatterns:

    def test_no_hallucinations_returns_empty(self, detector):
        patterns = detector.detect_patterns()
        assert patterns == []

    def test_single_hallucination_creates_source_pattern(self, detector):
        r = detector.check_claim("llm_call", "c1", "wrong fact")
        detector.verify_check(r["check_id"], True, 0.9, "incorrect")
        patterns = detector.detect_patterns()
        assert len(patterns) >= 1
        source_patterns = [p for p in patterns if p["pattern_type"] == "source_type_recurring"]
        assert len(source_patterns) == 1
        assert source_patterns[0]["source_type"] == "llm_call"

    def test_multiple_source_types(self, detector):
        r1 = detector.check_claim("llm_call", "c1", "claim 1")
        r2 = detector.check_claim("chat_message", "c2", "claim 2")
        detector.verify_check(r1["check_id"], True, 0.9, "")
        detector.verify_check(r2["check_id"], True, 0.8, "")
        patterns = detector.detect_patterns()
        source_patterns = [p for p in patterns if p["pattern_type"] == "source_type_recurring"]
        assert len(source_patterns) == 2

    def test_claim_prefix_pattern(self, detector):
        # Both claims must share the same first 80 characters so the
        # SUBSTR(claim, 1, 80) GROUP BY produces cnt > 1.
        shared_prefix = "X" * 70 + "shared_prefix_here"
        r1 = detector.check_claim("llm_call", "c1", shared_prefix + " variant A extra")
        r2 = detector.check_claim("llm_call", "c2", shared_prefix + " variant B extra")
        detector.verify_check(r1["check_id"], True, 0.9, "")
        detector.verify_check(r2["check_id"], True, 0.9, "")
        patterns = detector.detect_patterns()
        claim_patterns = [p for p in patterns if p["pattern_type"] == "claim_prefix_recurring"]
        assert len(claim_patterns) >= 1

    def test_pattern_upsert_updates_frequency(self, detector):
        r1 = detector.check_claim("llm_call", "c1", "claim")
        detector.verify_check(r1["check_id"], True, 0.9, "")
        detector.detect_patterns()

        r2 = detector.check_claim("llm_call", "c2", "another claim")
        detector.verify_check(r2["check_id"], True, 0.8, "")
        patterns = detector.detect_patterns()
        source_patterns = [p for p in patterns if p["pattern_type"] == "source_type_recurring"
                           and p["source_type"] == "llm_call"]
        assert len(source_patterns) == 1
        assert source_patterns[0]["frequency"] >= 2

    def test_non_hallucinations_not_counted(self, detector):
        r1 = detector.check_claim("llm_call", "c1", "correct claim")
        detector.verify_check(r1["check_id"], False, 0.1, "correct")
        patterns = detector.detect_patterns()
        assert patterns == []


# ===========================================================================
# 8. Event emission
# ===========================================================================

class TestEventEmission:

    def test_hallucination_confirmed_emits_event(self, detector_with_bus):
        d, bus = detector_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("hallucination.detected", lambda e: events.append(e))

        created = d.check_claim("llm_call", "c1", "wrong claim")
        d.verify_check(created["check_id"], True, 0.95, "fact check failed")

        assert len(events) == 1
        assert events[0].payload["check_id"] == created["check_id"]
        assert events[0].payload["confidence"] == 0.95
        assert events[0].payload["evidence"] == "fact check failed"
        assert events[0].source_module == "cognitive.hallucination_detector"

    def test_verified_does_not_emit(self, detector_with_bus):
        d, bus = detector_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("hallucination.detected", lambda e: events.append(e))

        created = d.check_claim("llm_call", "c1", "correct claim")
        d.verify_check(created["check_id"], False, 0.1, "looks fine")

        assert len(events) == 0

    def test_event_payload_contains_source_info(self, detector_with_bus):
        d, bus = detector_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("hallucination.detected", lambda e: events.append(e))

        created = d.check_claim("council_analysis", "ca-7", "bad analysis")
        d.verify_check(created["check_id"], True, 0.88, "wrong")

        assert events[0].payload["source_type"] == "council_analysis"
        assert events[0].payload["source_id"] == "ca-7"
        assert events[0].payload["claim"] == "bad analysis"

    def test_no_event_bus_does_not_raise(self):
        d = HallucinationDetector(event_bus=None)
        created = d.check_claim("llm_call", "c1", "claim")
        # Should not raise
        d.verify_check(created["check_id"], True, 0.9, "evidence")

    def test_check_claim_does_not_emit(self, detector_with_bus):
        d, bus = detector_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("hallucination.detected", lambda e: events.append(e))

        d.check_claim("llm_call", "c1", "claim")
        assert len(events) == 0


# ===========================================================================
# 9. Input validation
# ===========================================================================

class TestInputValidation:

    def test_all_valid_source_types(self, detector):
        for st in VALID_SOURCE_TYPES:
            result = detector.check_claim(st, "c1", "claim")
            assert result["source_type"] == st

    def test_all_valid_statuses_in_list(self, detector):
        for st in VALID_SOURCE_TYPES:
            r = detector.check_claim(st, "c1", "claim")
            fetched = detector.get_check(r["check_id"])
            assert fetched["verification_status"] == "pending"

    def test_invalid_source_type_message(self, detector):
        with pytest.raises(ValueError) as exc_info:
            detector.check_claim("not_a_type", "c1", "claim")
        assert "not_a_type" in str(exc_info.value)

    def test_invalid_status_filter_message(self, detector):
        with pytest.raises(ValueError) as exc_info:
            detector.list_checks(status="bogus")
        assert "bogus" in str(exc_info.value)


# ===========================================================================
# 10. Thread safety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_check_claims(self):
        d = HallucinationDetector()
        results: list[dict] = []
        results_lock = threading.Lock()

        def write_claim(idx):
            res = d.check_claim(
                source_type="llm_call",
                source_id=f"call-{idx}",
                claim=f"claim number {idx}",
            )
            with results_lock:
                results.append(res)

        threads = [threading.Thread(target=write_claim, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(results) == 20
        check_ids = [r["check_id"] for r in results]
        assert len(set(check_ids)) == 20

        stats = d.get_stats()
        assert stats["total"] == 20

    def test_concurrent_verify_and_resolve(self):
        d = HallucinationDetector()
        created = [d.check_claim("llm_call", f"c{i}", f"claim {i}") for i in range(10)]
        errors: list[Exception] = []
        errors_lock = threading.Lock()

        def verify_claim(idx):
            try:
                d.verify_check(created[idx]["check_id"], True, 0.9, "bad")
            except Exception as e:
                with errors_lock:
                    errors.append(e)

        def resolve_claim(idx):
            try:
                d.resolve_check(created[idx]["check_id"])
            except Exception as e:
                with errors_lock:
                    errors.append(e)

        threads = []
        for i in range(10):
            threads.append(threading.Thread(target=verify_claim, args=(i,)))
            threads.append(threading.Thread(target=resolve_claim, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        stats = d.get_stats()
        assert stats["total"] == 10


# ===========================================================================
# 11. Singleton functions
# ===========================================================================

class TestSingleton:

    def test_get_returns_same_instance(self):
        reset_hallucination_detector()
        d1 = get_hallucination_detector()
        d2 = get_hallucination_detector()
        assert d1 is d2
        reset_hallucination_detector()

    def test_reset_creates_new_instance(self):
        reset_hallucination_detector()
        d1 = get_hallucination_detector()
        reset_hallucination_detector()
        d2 = get_hallucination_detector()
        assert d1 is not d2
        reset_hallucination_detector()

    def test_singleton_with_custom_db(self):
        reset_hallucination_detector()
        d = get_hallucination_detector()
        assert d is not None
        reset_hallucination_detector()
