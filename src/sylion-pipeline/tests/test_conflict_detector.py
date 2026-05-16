"""
tests/test_conflict_detector.py -- Conflict Detector comprehensive tests

Covers:
- Conflict detection (CRUD, validation, defaults)
- Conflict resolution
- Listing and filtering
- Statistics
- Rules management
- EventBus integration (event emission)
- Singleton functions
- Edge cases and thread-safety basics
"""

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.conflict_detector import (
    VALID_CONFLICT_TYPES,
    VALID_SEVERITIES,
    VALID_STATUSES,
    ConflictDetector,
    get_conflict_detector,
    reset_conflict_detector,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def detector(bus):
    return ConflictDetector(event_bus=bus)


@pytest.fixture
def detector_no_bus():
    return ConflictDetector()


# =====================================================================
# Constants
# =====================================================================

class TestConstants:

    def test_valid_conflict_types(self):
        assert "concurrent_edit" in VALID_CONFLICT_TYPES
        assert "contract_mismatch" in VALID_CONFLICT_TYPES
        assert "version_conflict" in VALID_CONFLICT_TYPES
        assert "dependency_cycle" in VALID_CONFLICT_TYPES
        assert len(VALID_CONFLICT_TYPES) == 4

    def test_valid_severities(self):
        assert "low" in VALID_SEVERITIES
        assert "medium" in VALID_SEVERITIES
        assert "high" in VALID_SEVERITIES
        assert "critical" in VALID_SEVERITIES
        assert len(VALID_SEVERITIES) == 4

    def test_valid_statuses(self):
        assert "detected" in VALID_STATUSES
        assert "analyzing" in VALID_STATUSES
        assert "resolved" in VALID_STATUSES
        assert "escalated" in VALID_STATUSES
        assert len(VALID_STATUSES) == 4


# =====================================================================
# Detection
# =====================================================================

class TestDetectConflict:

    def test_detect_basic(self, detector):
        result = detector.detect_conflict(
            "mod-auth", "change-a-123", "change-b-456"
        )
        assert result["conflict_id"]
        assert result["module_id"] == "mod-auth"
        assert result["change_a"] == "change-a-123"
        assert result["change_b"] == "change-b-456"
        assert result["conflict_type"] == "concurrent_edit"
        assert result["status"] == "detected"
        assert result["detected_at"] > 0
        assert result["resolved_at"] is None
        assert result["resolution"] is None

    def test_detect_with_type(self, detector):
        result = detector.detect_conflict(
            "mod-api", "v1-contract", "v2-contract",
            change_type="contract_mismatch",
        )
        assert result["conflict_type"] == "contract_mismatch"

    def test_detect_dependency_cycle_is_critical(self, detector):
        result = detector.detect_conflict(
            "mod-core", "dep-add-a", "dep-add-b",
            change_type="dependency_cycle",
        )
        assert result["severity"] == "critical"

    def test_detect_concurrent_edit_is_medium(self, detector):
        result = detector.detect_conflict(
            "mod-ui", "edit-header", "edit-footer"
        )
        assert result["severity"] == "medium"

    def test_detect_contract_mismatch_is_high(self, detector):
        result = detector.detect_conflict(
            "mod-api", "contract-v1", "contract-v2",
            change_type="contract_mismatch",
        )
        assert result["severity"] == "high"

    def test_detect_version_conflict_is_medium(self, detector):
        result = detector.detect_conflict(
            "mod-pkg", "pin-v2", "pin-v3",
            change_type="version_conflict",
        )
        assert result["severity"] == "medium"

    def test_detect_generates_unique_ids(self, detector):
        r1 = detector.detect_conflict("mod-1", "a", "b")
        r2 = detector.detect_conflict("mod-2", "c", "d")
        assert r1["conflict_id"] != r2["conflict_id"]

    def test_detect_empty_module_id_rejected(self, detector):
        with pytest.raises(ValueError, match="module_id must not be empty"):
            detector.detect_conflict("", "a", "b")

    def test_detect_empty_change_a_rejected(self, detector):
        with pytest.raises(ValueError, match="change_a must not be empty"):
            detector.detect_conflict("mod", "", "b")

    def test_detect_empty_change_b_rejected(self, detector):
        with pytest.raises(ValueError, match="change_b must not be empty"):
            detector.detect_conflict("mod", "a", "")

    def test_detect_invalid_change_type_rejected(self, detector):
        with pytest.raises(ValueError, match="Invalid change_type"):
            detector.detect_conflict("mod", "a", "b", change_type="unknown")


# =====================================================================
# Resolution
# =====================================================================

class TestResolveConflict:

    def test_resolve_basic(self, detector):
        conflict = detector.detect_conflict("mod-r1", "a", "b")
        result = detector.resolve_conflict(
            conflict["conflict_id"], "merged both changes"
        )
        assert result is not None
        assert result["status"] == "resolved"
        assert result["resolution"] == "merged both changes"
        assert result["resolved_at"] is not None
        assert result["resolved_at"] >= conflict["detected_at"]

    def test_resolve_nonexistent_returns_none(self, detector):
        result = detector.resolve_conflict("nonexistent-id", "nothing")
        assert result is None

    def test_resolve_empty_resolution_rejected(self, detector):
        conflict = detector.detect_conflict("mod-r2", "a", "b")
        with pytest.raises(ValueError, match="resolution must not be empty"):
            detector.resolve_conflict(conflict["conflict_id"], "")

    def test_resolve_preserves_fields(self, detector):
        conflict = detector.detect_conflict(
            "mod-r3", "edit-1", "edit-2",
            change_type="contract_mismatch",
        )
        result = detector.resolve_conflict(
            conflict["conflict_id"], "priority_a"
        )
        assert result["module_id"] == "mod-r3"
        assert result["change_a"] == "edit-1"
        assert result["change_b"] == "edit-2"
        assert result["conflict_type"] == "contract_mismatch"
        assert result["severity"] == "high"

    def test_resolve_twice_overwrites(self, detector):
        conflict = detector.detect_conflict("mod-r4", "a", "b")
        detector.resolve_conflict(conflict["conflict_id"], "first")
        result = detector.resolve_conflict(conflict["conflict_id"], "second")
        assert result["resolution"] == "second"
        assert result["status"] == "resolved"


# =====================================================================
# Get / List
# =====================================================================

class TestGetConflict:

    def test_get_existing(self, detector):
        conflict = detector.detect_conflict("mod-g1", "a", "b")
        result = detector.get_conflict(conflict["conflict_id"])
        assert result is not None
        assert result["conflict_id"] == conflict["conflict_id"]
        assert result["module_id"] == "mod-g1"

    def test_get_nonexistent(self, detector):
        result = detector.get_conflict("no-such-id")
        assert result is None


class TestListConflicts:

    def test_list_all(self, detector):
        detector.detect_conflict("mod-l1", "a", "b")
        detector.detect_conflict("mod-l2", "c", "d")
        results = detector.list_conflicts()
        assert len(results) == 2

    def test_list_by_status(self, detector):
        c1 = detector.detect_conflict("mod-ls1", "a", "b")
        detector.detect_conflict("mod-ls2", "c", "d")
        detector.resolve_conflict(c1["conflict_id"], "done")

        detected = detector.list_conflicts(status="detected")
        resolved = detector.list_conflicts(status="resolved")
        assert len(detected) == 1
        assert len(resolved) == 1

    def test_list_by_module_id(self, detector):
        detector.detect_conflict("mod-lm1", "a", "b")
        detector.detect_conflict("mod-lm2", "c", "d")
        detector.detect_conflict("mod-lm1", "e", "f")

        results = detector.list_conflicts(module_id="mod-lm1")
        assert len(results) == 2
        assert all(r["module_id"] == "mod-lm1" for r in results)

    def test_list_with_limit(self, detector):
        for i in range(10):
            detector.detect_conflict("mod-ll", f"a-{i}", f"b-{i}")
        results = detector.list_conflicts(limit=3)
        assert len(results) == 3

    def test_list_by_status_and_module(self, detector):
        c1 = detector.detect_conflict("mod-lsm", "a", "b")
        detector.detect_conflict("mod-lsm", "c", "d")
        detector.resolve_conflict(c1["conflict_id"], "done")

        results = detector.list_conflicts(status="resolved", module_id="mod-lsm")
        assert len(results) == 1
        assert results[0]["conflict_id"] == c1["conflict_id"]

    def test_list_invalid_status_rejected(self, detector):
        with pytest.raises(ValueError, match="Invalid status filter"):
            detector.list_conflicts(status="unknown")

    def test_list_empty(self, detector):
        results = detector.list_conflicts()
        assert results == []


# =====================================================================
# Statistics
# =====================================================================

class TestGetStats:

    def test_stats_empty(self, detector):
        stats = detector.get_stats()
        assert stats["total"] == 0
        assert stats["by_severity"] == {}
        assert stats["by_status"] == {}

    def test_stats_after_detection(self, detector):
        detector.detect_conflict("mod-s1", "a", "b")
        detector.detect_conflict("mod-s2", "c", "d", change_type="contract_mismatch")

        stats = detector.get_stats()
        assert stats["total"] == 2
        assert stats["by_status"]["detected"] == 2
        assert "medium" in stats["by_severity"]
        assert "high" in stats["by_severity"]

    def test_stats_after_resolution(self, detector):
        c1 = detector.detect_conflict("mod-s3", "a", "b")
        detector.resolve_conflict(c1["conflict_id"], "resolved")

        stats = detector.get_stats()
        assert stats["total"] == 1
        assert stats["by_status"]["resolved"] == 1
        assert "detected" not in stats["by_status"]

    def test_stats_mixed(self, detector):
        detector.detect_conflict("mod-sm1", "a", "b")
        c2 = detector.detect_conflict("mod-sm2", "c", "d")
        detector.resolve_conflict(c2["conflict_id"], "done")
        detector.detect_conflict(
            "mod-sm3", "e", "f", change_type="dependency_cycle"
        )

        stats = detector.get_stats()
        assert stats["total"] == 3
        assert stats["by_status"]["detected"] == 2
        assert stats["by_status"]["resolved"] == 1
        assert stats["by_severity"]["critical"] == 1


# =====================================================================
# Rules
# =====================================================================

class TestRules:

    def test_add_rule(self, detector):
        rule = detector.add_rule(
            "concurrent_edit",
            "same_module_and_branch",
            auto_resolve="priority_newer",
        )
        assert rule["rule_id"]
        assert rule["conflict_type"] == "concurrent_edit"
        assert rule["detection_pattern"] == "same_module_and_branch"
        assert rule["auto_resolve"] == "priority_newer"

    def test_add_rule_no_auto_resolve(self, detector):
        rule = detector.add_rule(
            "version_conflict",
            "semver_range_overlap",
        )
        assert rule["auto_resolve"] == ""

    def test_add_rule_invalid_type_rejected(self, detector):
        with pytest.raises(ValueError, match="Invalid conflict_type"):
            detector.add_rule("invalid_type", "pattern")

    def test_add_rule_empty_pattern_rejected(self, detector):
        with pytest.raises(ValueError, match="detection_pattern must not be empty"):
            detector.add_rule("concurrent_edit", "")

    def test_list_rules_empty(self, detector):
        rules = detector.list_rules()
        assert rules == []

    def test_list_rules_multiple(self, detector):
        detector.add_rule("concurrent_edit", "pat1", "auto1")
        detector.add_rule("contract_mismatch", "pat2", "auto2")
        rules = detector.list_rules()
        assert len(rules) == 2

    def test_rule_appears_in_list(self, detector):
        added = detector.add_rule("version_conflict", "semver_clash", "pick_highest")
        rules = detector.list_rules()
        found = [r for r in rules if r["rule_id"] == added["rule_id"]]
        assert len(found) == 1
        assert found[0]["detection_pattern"] == "semver_clash"


# =====================================================================
# Events
# =====================================================================

class TestEvents:

    @staticmethod
    def _parse_payload(event_row: dict) -> dict:
        raw = event_row["payload"]
        if isinstance(raw, dict):
            return raw
        return __import__("json").loads(raw)

    def test_conflict_detected_event(self, bus):
        detector = ConflictDetector(event_bus=bus)
        detector.detect_conflict("mod-ev1", "a", "b")

        events = bus.query(topic="conflict.detected")
        assert len(events) >= 1

        payload = self._parse_payload(events[-1])
        assert payload["module_id"] == "mod-ev1"
        assert payload["conflict_type"] == "concurrent_edit"
        assert payload["severity"] == "medium"
        assert payload["conflict_id"]

    def test_conflict_detected_event_with_type(self, bus):
        detector = ConflictDetector(event_bus=bus)
        detector.detect_conflict(
            "mod-ev2", "a", "b", change_type="contract_mismatch"
        )

        events = bus.query(topic="conflict.detected")
        assert len(events) >= 1
        payload = self._parse_payload(events[-1])
        assert payload["conflict_type"] == "contract_mismatch"
        assert payload["severity"] == "high"

    def test_conflict_resolved_event(self, bus):
        detector = ConflictDetector(event_bus=bus)
        conflict = detector.detect_conflict("mod-ev3", "a", "b")
        detector.resolve_conflict(conflict["conflict_id"], "merged")

        events = bus.query(topic="conflict.resolved")
        assert len(events) >= 1

        payload = self._parse_payload(events[-1])
        assert payload["conflict_id"] == conflict["conflict_id"]
        assert payload["resolution"] == "merged"
        assert payload["module_id"] == "mod-ev3"

    def test_no_events_without_bus(self, detector_no_bus):
        # Should not raise -- event_bus is None
        detector_no_bus.detect_conflict("mod-ev4", "a", "b")
        conflict = detector_no_bus.detect_conflict("mod-ev5", "c", "d")
        detector_no_bus.resolve_conflict(conflict["conflict_id"], "ok")


# =====================================================================
# Singleton
# =====================================================================

class TestSingleton:

    def test_get_conflict_detector_creates_instance(self):
        detector = get_conflict_detector()
        assert isinstance(detector, ConflictDetector)

    def test_get_conflict_detector_returns_same(self):
        d1 = get_conflict_detector()
        d2 = get_conflict_detector()
        assert d1 is d2

    def test_reset_conflict_detector_creates_new(self):
        d1 = get_conflict_detector()
        d2 = reset_conflict_detector()
        assert d1 is not d2
        assert isinstance(d2, ConflictDetector)

    def test_reset_then_get_returns_new(self):
        d1 = reset_conflict_detector()
        d2 = get_conflict_detector()
        assert d1 is d2


# =====================================================================
# Thread safety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_detect(self, detector):
        """Multiple threads detect conflicts simultaneously without errors."""
        results = []
        errors = []

        def detect_worker(idx):
            try:
                r = detector.detect_conflict(
                    f"mod-thread-{idx}", f"change-a-{idx}", f"change-b-{idx}"
                )
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=detect_worker, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        assert len(detector.list_conflicts()) == 20

    def test_concurrent_detect_and_resolve(self, detector):
        """Detect and resolve from different threads simultaneously."""
        conflicts = []
        errors = []

        # Create conflicts first
        for i in range(10):
            c = detector.detect_conflict(
                f"mod-ts-{i}", f"a-{i}", f"b-{i}"
            )
            conflicts.append(c["conflict_id"])

        resolved = []

        def resolve_worker(cid):
            try:
                r = detector.resolve_conflict(cid, f"resolved-{cid}")
                if r:
                    resolved.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=resolve_worker, args=(cid,))
                   for cid in conflicts]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(resolved) == 10
        stats = detector.get_stats()
        assert stats["by_status"]["resolved"] == 10
