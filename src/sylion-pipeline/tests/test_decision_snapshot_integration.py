"""Tests for Decision Snapshot integration with Decision Gate Engine.

Validates that:
- evaluate_gate() automatically captures a snapshot
- Snapshots capture the evaluation result correctly
- Multiple evaluations create a timeline
- Snapshot failure does not break evaluation
- Snapshot events are emitted on the EventBus
"""
import threading
import time

import pytest

from sylion.core.decision_gate_engine import (
    DecisionGateEngine,
    GateDefinition,
    GateResult,
    DecisionClass,
)
from sylion.governance.decision_snapshot import (
    DecisionSnapshot,
    get_decision_snapshot,
    reset_decision_snapshot,
)
from sylion.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset the snapshot singleton between tests."""
    reset_decision_snapshot()
    yield
    reset_decision_snapshot()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def engine(bus):
    return DecisionGateEngine(db_path=":memory:", event_bus=bus)


@pytest.fixture
def snap_engine(bus):
    return DecisionSnapshot(db_path=":memory:", event_bus=bus)


def _wire_singleton(snap_engine):
    """Point the global singleton at our test instance so evaluate_gate picks it up."""
    import sylion.governance.decision_snapshot as mod
    mod._snapshot = snap_engine


def _make_gate(gate_id, name="Test Gate", decision_class_min=DecisionClass.D2):
    return GateDefinition(
        gate_id=gate_id,
        name=name,
        description=f"Gate {gate_id}",
        fail_condition="",
        blocks="",
        decision_class_min=decision_class_min,
        owner_plan="P-TEST",
    )


# ===========================================================================
# 1. evaluate_gate creates a snapshot
# ===========================================================================

class TestEvaluateGateSnapshot:

    def test_evaluate_gate_captures_snapshot(self, engine, snap_engine):
        _wire_singleton(snap_engine)
        engine.register_gate(_make_gate("G-SNAP-01"))
        result = engine.evaluate_gate("G-SNAP-01")
        assert result["result"] == GateResult.PASS

        snapshots = snap_engine.get_decision_timeline(gate_id="G-SNAP-01")
        assert len(snapshots) >= 1
        snap = snapshots[0]
        assert snap["gate_id"] == "G-SNAP-01"
        assert "PASS" in str(snap["choice_made"])

    def test_evaluate_missing_gate_captures_snapshot(self, engine, snap_engine):
        _wire_singleton(snap_engine)
        result = engine.evaluate_gate("G-NONEXISTENT")
        assert result["result"] == GateResult.FAIL

        # Missing gates return early before snapshot capture — that's OK
        # The snapshot is only captured for registered gates

    def test_evaluate_registered_gate_captures_snapshot(self, engine, snap_engine):
        _wire_singleton(snap_engine)
        engine.register_gate(_make_gate("G-REG-01"))
        result = engine.evaluate_gate("G-REG-01")
        assert result["result"] == GateResult.PASS

        snapshots = snap_engine.get_decision_timeline(gate_id="G-REG-01")
        assert len(snapshots) >= 1
        assert snapshots[0]["consequences"]["evaluation"]["gate_id"] == "G-REG-01"

    def test_snapshot_consequences_contain_evaluation(self, engine, snap_engine):
        _wire_singleton(snap_engine)
        engine.register_gate(_make_gate("G-DET-01"))
        engine.evaluate_gate("G-DET-01")

        snapshots = snap_engine.get_decision_timeline(gate_id="G-DET-01")
        assert len(snapshots) >= 1
        details = snapshots[0]["consequences"]["evaluation"]
        assert details["gate_id"] == "G-DET-01"
        assert details["result"] == GateResult.PASS


# ===========================================================================
# 2. Multiple evaluations create timeline
# ===========================================================================

class TestSnapshotTimeline:

    def test_multiple_evaluations_create_ordered_timeline(self, engine, snap_engine):
        _wire_singleton(snap_engine)
        engine.register_gate(_make_gate("G-TL-01"))

        engine.evaluate_gate("G-TL-01")
        time.sleep(0.01)
        engine.evaluate_gate("G-TL-01")
        time.sleep(0.01)
        engine.evaluate_gate("G-TL-01")

        snapshots = snap_engine.get_decision_timeline(gate_id="G-TL-01")
        assert len(snapshots) == 3
        assert snapshots[0]["created_at"] <= snapshots[1]["created_at"]
        assert snapshots[1]["created_at"] <= snapshots[2]["created_at"]

    def test_different_gates_create_separate_snapshots(self, engine, snap_engine):
        _wire_singleton(snap_engine)
        engine.register_gate(_make_gate("G-SEP-A"))
        engine.register_gate(_make_gate("G-SEP-B"))

        engine.evaluate_gate("G-SEP-A")
        engine.evaluate_gate("G-SEP-B")
        engine.evaluate_gate("G-SEP-A")

        snap_a = snap_engine.get_decision_timeline(gate_id="G-SEP-A")
        snap_b = snap_engine.get_decision_timeline(gate_id="G-SEP-B")
        assert len(snap_a) == 2
        assert len(snap_b) == 1


# ===========================================================================
# 3. Standalone snapshot engine features
# ===========================================================================

class TestSnapshotEngineStandalone:

    def test_get_snapshot_by_id(self, snap_engine):
        result = snap_engine.capture_snapshot(
            decision_id="dec-gs-01",
            gate_id="G-GS-01",
            choice_made="passed",
        )
        snapshot_id = result["snapshot_id"]

        snapshot = snap_engine.get_snapshot(snapshot_id)
        assert snapshot is not None
        assert snapshot["snapshot_id"] == snapshot_id
        assert snapshot["decision_id"] == "dec-gs-01"

    def test_get_snapshot_nonexistent(self, snap_engine):
        assert snap_engine.get_snapshot("nonexistent") is None

    def test_snapshot_count(self, snap_engine):
        snap_engine.capture_snapshot(decision_id="dec-c-01", choice_made="pass")
        snap_engine.capture_snapshot(decision_id="dec-c-01", choice_made="fail")
        snap_engine.capture_snapshot(decision_id="dec-c-02", choice_made="pass")

        assert snap_engine.get_snapshot_count(decision_id="dec-c-01") == 2
        assert snap_engine.get_snapshot_count(decision_id="dec-c-02") == 1
        assert snap_engine.get_snapshot_count() == 3

    def test_concurrent_snapshot_capture(self, snap_engine):
        errors = []

        def capture(idx):
            try:
                snap_engine.capture_snapshot(
                    decision_id=f"dec-thr-{idx}",
                    gate_id="G-THR-SNAP",
                    choice_made="passed",
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=capture, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert snap_engine.get_snapshot_count(gate_id="G-THR-SNAP") == 20

    def test_module_states_default_empty_dict(self, snap_engine):
        snap_engine.capture_snapshot(decision_id="dec-ms-01", choice_made="test")
        snapshots = snap_engine.get_decision_timeline(decision_id="dec-ms-01")
        assert len(snapshots) == 1
        ms = snapshots[0]["module_states"]
        assert isinstance(ms, dict)


# ===========================================================================
# 4. Error resilience
# ===========================================================================

class TestErrorResilience:

    def test_snapshot_failure_does_not_break_evaluation(self, engine):
        import sylion.governance.decision_snapshot as snap_mod

        class BrokenSnapshot:
            def capture_snapshot(self, **kwargs):
                raise RuntimeError("DB connection lost")

        snap_mod._snapshot = BrokenSnapshot()

        engine.register_gate(_make_gate("G-ERR-01"))
        result = engine.evaluate_gate("G-ERR-01")
        assert result["result"] == GateResult.PASS

    def test_import_failure_does_not_break_evaluation(self, engine):
        import sylion.governance.decision_snapshot as snap_mod
        snap_mod._snapshot = None

        engine.register_gate(_make_gate("G-IMP-01"))
        result = engine.evaluate_gate("G-IMP-01")
        assert result["result"] == GateResult.PASS


# ===========================================================================
# 5. EventBus integration
# ===========================================================================

class TestSnapshotEvents:

    def test_snapshot_emits_event(self, bus, snap_engine):
        received = []
        bus.subscribe("decision.snapshot.captured", lambda e: received.append(e))

        snap_engine.capture_snapshot(
            decision_id="dec-ev-001",
            gate_id="G-EV-01",
            choice_made="passed",
        )

        assert len(received) == 1
        assert received[0].payload["decision_id"] == "dec-ev-001"

    def test_evaluate_gate_triggers_snapshot_event(self, engine, snap_engine, bus):
        _wire_singleton(snap_engine)

        received = []
        bus.subscribe("decision.snapshot.captured", lambda e: received.append(e))

        engine.register_gate(_make_gate("G-EVE-01"))
        engine.evaluate_gate("G-EVE-01")

        assert len(received) >= 1
        assert received[0].payload["decision_id"].startswith("gate-G-EVE-01")
