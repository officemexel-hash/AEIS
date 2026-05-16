"""
Tests for ConflictResolver -- detect, analyze, resolve, auto-resolve, escalate.

Covers all public methods: detect_conflicts, analyze_conflict, resolve_conflict,
get_conflict, list_conflicts, get_unresolved, auto_resolve, escalate_to_council,
get_conflict_stats, singleton lifecycle, thread safety.
"""

from __future__ import annotations

import json
import time
import threading

import pytest

from sylion.governance.conflict_resolver import (
    ConflictResolver,
    get_conflict_resolver,
    reset_conflict_resolver,
)
from sylion.governance.decision_snapshot import (
    DecisionSnapshot,
    reset_decision_snapshot,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset global singletons before and after every test."""
    reset_conflict_resolver()
    reset_decision_snapshot()
    yield
    reset_conflict_resolver()
    reset_decision_snapshot()


@pytest.fixture
def bus():
    from sylion.core.event_bus import EventBus
    return EventBus()


@pytest.fixture
def ds():
    """Fresh in-memory DecisionSnapshot instance."""
    return DecisionSnapshot()


@pytest.fixture
def cr(ds):
    """Fresh ConflictResolver wired to the same in-memory store.

    We inject the ds into the singleton so the lazy import picks it up.
    """
    from sylion.governance import decision_snapshot as ds_mod
    ds_mod._snapshot = ds
    return ConflictResolver()


@pytest.fixture
def cr_bus(ds, bus):
    """ConflictResolver with EventBus."""
    from sylion.governance import decision_snapshot as ds_mod
    ds_mod._snapshot = ds
    return ConflictResolver(event_bus=bus)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_snapshot(ds, snapshot_id, decision_id="DEC-001",
                     decision_class="D0", module_states=None,
                     pipeline_run_id=None, cascade_depth=0,
                     impact_radius="local", affected_decisions=None):
    """Directly insert a snapshot row for controlled testing."""
    now = time.time()
    ms = json.dumps(module_states) if module_states else "{}"
    ad = json.dumps(affected_decisions) if affected_decisions else None
    with ds._lock:
        ds._conn.execute("""
            INSERT INTO decision_snapshots
            (snapshot_id, decision_id, decision_class, module_states,
             pipeline_run_id, cascade_depth, impact_radius,
             affected_decisions, codebase_hash, created_at, is_active)
            VALUES (?,?,?,?,?,?,?,?,?,?,1)
        """, (
            snapshot_id, decision_id, decision_class, ms,
            pipeline_run_id, cascade_depth, impact_radius,
            ad, "hash_" + snapshot_id, now,
        ))
        ds._conn.commit()


# ===========================================================================
# TestDetectConflicts
# ===========================================================================

class TestDetectConflicts:

    def test_detect_module_overlap(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_type"] == "contract_mismatch"
        assert "mod_1" in conflicts[0]["affected_modules"]

    def test_detect_resource_contention(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}},
                         pipeline_run_id="run_1")
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}},
                         pipeline_run_id="run_1")
        conflicts = cr.detect_conflicts("snap_b")
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_type"] == "resource_contention"

    def test_no_conflict_when_modules_dont_overlap(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_2": {"v": 1}})
        conflicts = cr.detect_conflicts("snap_b")
        assert len(conflicts) == 0

    def test_no_conflict_for_missing_snapshot(self, cr, ds):
        conflicts = cr.detect_conflicts("nonexistent")
        assert len(conflicts) == 0

    def test_no_duplicate_conflicts(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        cr.detect_conflicts("snap_b")
        cr.detect_conflicts("snap_a")
        all_conflicts = cr.list_conflicts()
        assert len(all_conflicts) == 1

    def test_detect_cascade_collision(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}},
                         affected_decisions=["snap_x"])
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}, "mod_2": {"v": 1}},
                         affected_decisions=["snap_x"])
        conflicts = cr.detect_conflicts("snap_b")
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_type"] == "cascade_collision"

    def test_detect_module_overlap_identical_states(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 1}})
        conflicts = cr.detect_conflicts("snap_b")
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_type"] == "module_overlap"

    def test_no_conflict_for_empty_modules(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={})
        _insert_snapshot(ds, "snap_b", module_states={})
        conflicts = cr.detect_conflicts("snap_b")
        assert len(conflicts) == 0

    def test_multiple_overlapping_modules(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={
            "mod_1": {"v": 1}, "mod_2": {"v": 1}, "mod_3": {"v": 1}
        })
        _insert_snapshot(ds, "snap_b", module_states={
            "mod_1": {"v": 2}, "mod_2": {"v": 2}, "mod_3": {"v": 2}
        })
        conflicts = cr.detect_conflicts("snap_b")
        assert len(conflicts) == 1
        assert len(conflicts[0]["affected_modules"]) == 3

    def test_conflict_with_severity(self, cr, ds):
        _insert_snapshot(ds, "snap_a", decision_class="D3",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D3",
                         module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        assert len(conflicts) == 1
        assert conflicts[0]["severity"] == "high"

    def test_emits_detected_event(self, cr_bus, ds):
        events = []
        cr_bus._event_bus.subscribe(
            "decision.conflict.detected", lambda e: events.append(e))
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        cr_bus.detect_conflicts("snap_b")
        assert len(events) == 1
        assert events[0].payload["conflict_type"] == "contract_mismatch"

    def test_detect_against_multiple_active(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_2": {"v": 1}})
        _insert_snapshot(ds, "snap_c",
                         module_states={"mod_1": {"v": 2}, "mod_2": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_c")
        assert len(conflicts) == 2


# ===========================================================================
# TestAnalyzeConflict
# ===========================================================================

class TestAnalyzeConflict:

    def test_analyze_returns_suggestion(self, cr, ds):
        _insert_snapshot(ds, "snap_a", decision_class="D2",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D2",
                         module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        analysis = cr.analyze_conflict(cid)
        assert analysis is not None
        assert analysis["conflict_id"] == cid
        assert "suggested_resolution" in analysis
        assert "affected_modules" in analysis
        assert "analysis" in analysis

    def test_analyze_includes_snapshot_info(self, cr, ds):
        # detect_conflicts("snap_b") stores snap_b as snapshot_id_a,
        # snap_a as snapshot_id_b
        _insert_snapshot(ds, "snap_a", decision_class="D3",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D2",
                         module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        analysis = cr.analyze_conflict(cid)
        assert analysis["analysis"]["snapshot_a"]["decision_class"] == "D2"
        assert analysis["analysis"]["snapshot_b"]["decision_class"] == "D3"

    def test_analyze_suggests_priority_for_higher_class(self, cr, ds):
        # detect_conflicts("snap_b") stores snap_b as A, snap_a as B.
        # snap_a is D3 (higher) so priority_b should win (B = snap_a = D3)
        _insert_snapshot(ds, "snap_a", decision_class="D3",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D2",
                         module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        analysis = cr.analyze_conflict(cid)
        # B (snap_a, D3) has higher class than A (snap_b, D2)
        assert analysis["suggested_resolution"] == "priority_b"

    def test_analyze_suggests_merge_for_compatible(self, cr, ds):
        _insert_snapshot(ds, "snap_a", decision_class="D0",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D0",
                         module_states={"mod_1": {"v": 1}})
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        analysis = cr.analyze_conflict(cid)
        assert analysis["suggested_resolution"] == "merge"

    def test_analyze_returns_none_for_missing(self, cr):
        assert cr.analyze_conflict("nonexistent") is None

    def test_analyze_updates_status(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        cr.analyze_conflict(cid)
        conflict = cr.get_conflict(cid)
        assert conflict["status"] == "analyzing"

    def test_analyze_emits_event(self, cr_bus, ds):
        events = []
        cr_bus._event_bus.subscribe(
            "decision.conflict.analyzed", lambda e: events.append(e))
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        conflicts = cr_bus.detect_conflicts("snap_b")
        cr_bus.analyze_conflict(conflicts[0]["conflict_id"])
        assert len(events) == 1


# ===========================================================================
# TestResolveConflict
# ===========================================================================

class TestResolveConflict:

    def _make_conflict(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        return conflicts[0]["conflict_id"]

    def test_resolve_with_merge(self, cr, ds):
        cid = self._make_conflict(cr, ds)
        result = cr.resolve_conflict(cid, "merge")
        assert result is not None
        assert result["resolution"] == "merge"
        assert result["status"] == "resolved"
        assert result["resolution_details"]["action"] == "dependencies_updated"

    def test_resolve_with_priority_a(self, cr, ds):
        cid = self._make_conflict(cr, ds)
        # _make_conflict calls detect_conflicts("snap_b"), so:
        # snapshot_id_a = snap_b, snapshot_id_b = snap_a
        # priority_a supersedes B (snap_a)
        result = cr.resolve_conflict(cid, "priority_a")
        assert result is not None
        assert result["resolution"] == "priority_a"
        assert result["resolution_details"]["action"] == "snapshot_b_superseded"
        assert result["resolution_details"]["superseded_snapshot"] == "snap_a"

    def test_resolve_priority_a_marks_b_superseded(self, cr, ds):
        cid = self._make_conflict(cr, ds)
        # priority_a supersedes snapshot_id_b = snap_a
        cr.resolve_conflict(cid, "priority_a")
        snap_a = ds.get_snapshot("snap_a")
        assert snap_a["is_active"] == 0

    def test_resolve_with_priority_b(self, cr, ds):
        cid = self._make_conflict(cr, ds)
        # priority_b supersedes snapshot_id_a = snap_b
        result = cr.resolve_conflict(cid, "priority_b")
        assert result is not None
        assert result["resolution"] == "priority_b"
        assert result["resolution_details"]["action"] == "snapshot_a_superseded"
        assert result["resolution_details"]["superseded_snapshot"] == "snap_b"

    def test_resolve_priority_b_marks_a_superseded(self, cr, ds):
        cid = self._make_conflict(cr, ds)
        # priority_b supersedes snapshot_id_a = snap_b
        cr.resolve_conflict(cid, "priority_b")
        snap_b = ds.get_snapshot("snap_b")
        assert snap_b["is_active"] == 0

    def test_resolve_with_escalate(self, cr, ds):
        cid = self._make_conflict(cr, ds)
        result = cr.resolve_conflict(cid, "escalate")
        assert result is not None
        assert result["resolution"] == "escalate"
        assert result["status"] == "escalated"
        assert "hg_session_id" in result["resolution_details"]

    def test_resolve_with_split(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={
            "mod_1": {"v": 1}, "mod_2": {"v": 1}, "mod_3": {"v": 1}
        })
        _insert_snapshot(ds, "snap_b", module_states={
            "mod_1": {"v": 2}, "mod_2": {"v": 2}, "mod_3": {"v": 2}
        })
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        result = cr.resolve_conflict(cid, "split")
        assert result is not None
        assert result["resolution"] == "split"
        details = result["resolution_details"]
        assert details["action"] == "modules_split"
        assert "modules_a" in details
        assert "modules_b" in details

    def test_resolve_unknown_strategy_returns_none(self, cr, ds):
        cid = self._make_conflict(cr, ds)
        result = cr.resolve_conflict(cid, "unknown_strategy")
        assert result is None

    def test_resolve_nonexistent_returns_none(self, cr):
        result = cr.resolve_conflict("nonexistent", "merge")
        assert result is None

    def test_resolve_records_resolver(self, cr, ds):
        cid = self._make_conflict(cr, ds)
        result = cr.resolve_conflict(cid, "merge", resolved_by="human")
        assert result["resolved_by"] == "human"

    def test_resolve_records_timestamp(self, cr, ds):
        cid = self._make_conflict(cr, ds)
        result = cr.resolve_conflict(cid, "merge")
        assert result["resolved_at"] is not None

    def test_resolve_emits_event(self, cr_bus, ds):
        events = []
        cr_bus._event_bus.subscribe(
            "decision.conflict.resolved", lambda e: events.append(e))
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        conflicts = cr_bus.detect_conflicts("snap_b")
        cr_bus.resolve_conflict(conflicts[0]["conflict_id"], "merge")
        assert len(events) == 1
        assert events[0].payload["resolution"] == "merge"


# ===========================================================================
# TestAutoResolve
# ===========================================================================

class TestAutoResolve:

    def test_auto_resolve_by_class_priority(self, cr, ds):
        # detect_conflicts("snap_b") stores snap_b as A, snap_a as B
        # snap_a is D3 (higher), snap_b is D2 -> priority_b wins
        _insert_snapshot(ds, "snap_a", decision_class="D3",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D2",
                         module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        result = cr.auto_resolve(cid)
        assert result["resolved"] is True
        assert result["resolution"] == "priority_b"
        assert "D3" in result["reason"]

    def test_auto_resolve_by_cascade_depth(self, cr, ds):
        # detect_conflicts("snap_b"): A=snap_b(depth=3), B=snap_a(depth=1)
        # B has shallower cascade -> priority_b wins
        _insert_snapshot(ds, "snap_a", decision_class="D2",
                         module_states={"mod_1": {"v": 1}},
                         cascade_depth=1)
        _insert_snapshot(ds, "snap_b", decision_class="D2",
                         module_states={"mod_1": {"v": 2}},
                         cascade_depth=3)
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        result = cr.auto_resolve(cid)
        assert result["resolved"] is True
        assert result["resolution"] == "priority_b"
        assert "cascade depth" in result["reason"]

    def test_auto_resolve_by_impact_radius(self, cr, ds):
        # detect_conflicts("snap_b"): A=snap_b(system), B=snap_a(local)
        # B has smaller impact radius -> priority_b wins
        _insert_snapshot(ds, "snap_a", decision_class="D2",
                         module_states={"mod_1": {"v": 1}},
                         impact_radius="local")
        _insert_snapshot(ds, "snap_b", decision_class="D2",
                         module_states={"mod_1": {"v": 2}},
                         impact_radius="system")
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        result = cr.auto_resolve(cid)
        assert result["resolved"] is True
        assert result["resolution"] == "priority_b"

    def test_auto_resolve_equal_priority_escalates(self, cr, ds):
        _insert_snapshot(ds, "snap_a", decision_class="D2",
                         module_states={"mod_1": {"v": 1}},
                         cascade_depth=0, impact_radius="local")
        _insert_snapshot(ds, "snap_b", decision_class="D2",
                         module_states={"mod_1": {"v": 2}},
                         cascade_depth=0, impact_radius="local")
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        result = cr.auto_resolve(cid)
        assert result["resolved"] is False
        assert result["resolution"] == "escalate"

    def test_auto_resolve_missing_conflict(self, cr):
        result = cr.auto_resolve("nonexistent")
        assert result["resolved"] is False
        assert result["reason"] == "conflict not found"

    def test_auto_resolve_missing_snapshot(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        # Delete snap_a to simulate missing snapshot
        with ds._lock:
            ds._conn.execute(
                "DELETE FROM decision_snapshots WHERE snapshot_id = 'snap_a'")
            ds._conn.commit()

        result = cr.auto_resolve(cid)
        assert result["resolved"] is False

    def test_auto_resolve_updates_conflict_record(self, cr, ds):
        # detect_conflicts("snap_b"): A=snap_b(D2), B=snap_a(D4)
        # D4 > D2 -> priority_b wins
        _insert_snapshot(ds, "snap_a", decision_class="D4",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D2",
                         module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        cr.auto_resolve(cid)
        conflict = cr.get_conflict(cid)
        assert conflict["status"] == "resolved"
        assert conflict["resolution"] == "priority_b"
        assert conflict["resolved_by"] == "system"


# ===========================================================================
# TestEscalateToCouncil
# ===========================================================================

class TestEscalateToCouncil:

    def test_escalate_to_council(self, cr, ds):
        _insert_snapshot(ds, "snap_a", decision_class="D3",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D4",
                         module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        result = cr.escalate_to_council(cid)
        # May fall back to HumanGate if CouncilWorkflow not fully available
        # but should not return None
        assert result is not None

    def test_escalate_missing_conflict(self, cr):
        result = cr.escalate_to_council("nonexistent")
        assert result is None

    def test_escalate_updates_conflict_status(self, cr, ds):
        _insert_snapshot(ds, "snap_a", decision_class="D3",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D3",
                         module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        cr.escalate_to_council(cid)
        conflict = cr.get_conflict(cid)
        assert conflict["status"] == "escalated"
        assert conflict["resolved_by"] == "council"


# ===========================================================================
# TestGetConflict
# ===========================================================================

class TestGetConflict:

    def test_get_existing_conflict(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        result = cr.get_conflict(cid)
        assert result is not None
        assert result["conflict_id"] == cid
        assert isinstance(result["affected_modules"], list)

    def test_get_missing_conflict(self, cr):
        assert cr.get_conflict("nonexistent") is None

    def test_get_parses_json_fields(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        cid = conflicts[0]["conflict_id"]

        result = cr.get_conflict(cid)
        assert isinstance(result["affected_modules"], list)
        assert result["resolution_details"] is None


# ===========================================================================
# TestListConflicts
# ===========================================================================

class TestListConflicts:

    def test_list_all(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        _insert_snapshot(ds, "snap_c", module_states={"mod_2": {"v": 1}})
        cr.detect_conflicts("snap_b")
        cr.detect_conflicts("snap_c")
        assert len(cr.list_conflicts()) == 1

    def test_list_by_status(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        cr.detect_conflicts("snap_b")
        detected = cr.list_conflicts(status="detected")
        resolved = cr.list_conflicts(status="resolved")
        assert len(detected) == 1
        assert len(resolved) == 0

    def test_list_by_severity(self, cr, ds):
        _insert_snapshot(ds, "snap_a", decision_class="D3",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D3",
                         module_states={"mod_1": {"v": 2}})
        cr.detect_conflicts("snap_b")
        high = cr.list_conflicts(severity="high")
        low = cr.list_conflicts(severity="low")
        assert len(high) == 1
        assert len(low) == 0

    def test_list_empty(self, cr):
        assert cr.list_conflicts() == []


# ===========================================================================
# TestGetUnresolved
# ===========================================================================

class TestGetUnresolved:

    def test_get_unresolved(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        cr.detect_conflicts("snap_b")
        unresolved = cr.get_unresolved()
        assert len(unresolved) == 1

    def test_resolved_excluded(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        cr.resolve_conflict(conflicts[0]["conflict_id"], "merge")
        unresolved = cr.get_unresolved()
        assert len(unresolved) == 0

    def test_empty_when_no_conflicts(self, cr):
        assert cr.get_unresolved() == []


# ===========================================================================
# TestGetConflictStats
# ===========================================================================

class TestGetConflictStats:

    def test_empty_stats(self, cr):
        stats = cr.get_conflict_stats()
        assert stats["total"] == 0
        assert stats["by_status"] == {}
        assert stats["by_severity"] == {}
        assert stats["auto_resolved_rate"] == 0.0

    def test_stats_with_conflicts(self, cr, ds):
        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        cr.detect_conflicts("snap_b")
        stats = cr.get_conflict_stats()
        assert stats["total"] == 1
        assert stats["by_status"]["detected"] == 1

    def test_auto_resolved_rate(self, cr, ds):
        _insert_snapshot(ds, "snap_a", decision_class="D3",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D2",
                         module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        cr.auto_resolve(conflicts[0]["conflict_id"])
        stats = cr.get_conflict_stats()
        assert stats["total"] == 1
        assert stats["auto_resolved_rate"] == 100.0

    def test_stats_by_severity(self, cr, ds):
        _insert_snapshot(ds, "snap_a", decision_class="D3",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D3",
                         module_states={"mod_1": {"v": 2}})
        cr.detect_conflicts("snap_b")
        stats = cr.get_conflict_stats()
        assert "high" in stats["by_severity"]


# ===========================================================================
# TestSeverityClassification
# ===========================================================================

class TestSeverityClassification:

    def test_critical_for_d4(self, cr, ds):
        _insert_snapshot(ds, "snap_a", decision_class="D4",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D4",
                         module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        assert conflicts[0]["severity"] == "critical"

    def test_high_for_d3(self, cr, ds):
        _insert_snapshot(ds, "snap_a", decision_class="D3",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D3",
                         module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        assert conflicts[0]["severity"] == "high"

    def test_medium_for_d2(self, cr, ds):
        _insert_snapshot(ds, "snap_a", decision_class="D2",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D2",
                         module_states={"mod_1": {"v": 2}})
        conflicts = cr.detect_conflicts("snap_b")
        assert conflicts[0]["severity"] == "medium"

    def test_critical_for_many_overlapping(self, cr, ds):
        modules = {f"mod_{i}": {"v": 1} for i in range(6)}
        modules_b = {f"mod_{i}": {"v": 2} for i in range(6)}
        _insert_snapshot(ds, "snap_a", module_states=modules)
        _insert_snapshot(ds, "snap_b", module_states=modules_b)
        conflicts = cr.detect_conflicts("snap_b")
        assert conflicts[0]["severity"] == "critical"


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        assert isinstance(get_conflict_resolver(), ConflictResolver)

    def test_idempotent(self):
        a = get_conflict_resolver()
        b = get_conflict_resolver()
        assert a is b

    def test_reset_creates_new(self):
        a = get_conflict_resolver()
        b = reset_conflict_resolver()
        assert a is not b
        assert isinstance(b, ConflictResolver)


# ===========================================================================
# TestThreadSafety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_detect(self, ds):
        from sylion.governance import decision_snapshot as ds_mod
        ds_mod._snapshot = ds
        cr = ConflictResolver()

        _insert_snapshot(ds, "snap_a", module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", module_states={"mod_1": {"v": 2}})
        _insert_snapshot(ds, "snap_c", module_states={"mod_2": {"v": 1}})

        results = []
        errors = []

        def detect(sid):
            try:
                r = cr.detect_conflicts(sid)
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=detect, args=("snap_b",)),
            threading.Thread(target=detect, args=("snap_c",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 2

    def test_concurrent_resolve(self, ds):
        from sylion.governance import decision_snapshot as ds_mod
        ds_mod._snapshot = ds
        cr = ConflictResolver()

        _insert_snapshot(ds, "snap_a", decision_class="D3",
                         module_states={"mod_1": {"v": 1}})
        _insert_snapshot(ds, "snap_b", decision_class="D2",
                         module_states={"mod_1": {"v": 2}})
        _insert_snapshot(ds, "snap_c", decision_class="D2",
                         module_states={"mod_2": {"v": 1}})

        conflicts_ab = cr.detect_conflicts("snap_b")
        conflicts_bc = cr.detect_conflicts("snap_c")

        errors = []

        def resolve(cid):
            try:
                cr.resolve_conflict(cid, "merge")
            except Exception as e:
                errors.append(e)

        cids = []
        if conflicts_ab:
            cids.append(conflicts_ab[0]["conflict_id"])
        if conflicts_bc:
            cids.append(conflicts_bc[0]["conflict_id"])

        threads = [threading.Thread(target=resolve, args=(c,)) for c in cids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
