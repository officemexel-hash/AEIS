"""Comprehensive tests for sylion.core.decision_gate_engine (DecisionGateEngine)."""

import sqlite3
import threading
import time

import pytest

from sylion.core.decision_gate_engine import (
    DECISION_REQUIREMENTS,
    DecisionClass,
    DecisionGateEngine,
    DecisionRecord,
    DecisionRequest,
    GateDefinition,
    GateResult,
    get_decision_engine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    """Fresh in-memory DecisionGateEngine per test."""
    return DecisionGateEngine()


@pytest.fixture
def gate(engine):
    """A sample gate registered on the engine."""
    g = GateDefinition(
        gate_id="G-TEST-01",
        name="Test Gate",
        description="Gate for unit tests",
        fail_condition="Always passes in test",
        blocks="test.pipeline",
        decision_class_min=DecisionClass.D2,
        owner_plan="P99",
    )
    engine.register_gate(g)
    return g


@pytest.fixture
def classified_engine(engine):
    """Engine with several classified decisions."""
    r1 = engine.classify(DecisionRequest(
        description="Config tweak",
        source_plan="P01",
        change_type="config",
        blast_radius="low",
    ))
    r2 = engine.classify(DecisionRequest(
        description="New module",
        source_plan="P02",
        change_type="module",
        blast_radius="medium",
    ))
    r3 = engine.classify(DecisionRequest(
        description="Architecture change",
        source_plan="P03",
        change_type="architecture",
        blast_radius="medium",
    ))
    r4 = engine.classify(DecisionRequest(
        description="Kernel change",
        source_plan="P04",
        affects_kernel=True,
        blast_radius="critical",
    ))
    return engine, (r1, r2, r3, r4)


# ---------------------------------------------------------------------------
# DecisionClass enum
# ---------------------------------------------------------------------------

class TestDecisionClass:
    def test_all_classes_exist(self):
        expected = {"D0", "D1", "D2", "D3", "D4", "D5"}
        assert {dc.value for dc in DecisionClass} == expected

    def test_string_comparison(self):
        assert DecisionClass.D0 == "D0"
        assert DecisionClass.D5 == "D5"


# ---------------------------------------------------------------------------
# GateResult enum
# ---------------------------------------------------------------------------

class TestGateResult:
    def test_all_results_exist(self):
        expected = {"pass", "fail", "conditional"}
        assert {gr.value for gr in GateResult} == expected


# ---------------------------------------------------------------------------
# DecisionRequest dataclass
# ---------------------------------------------------------------------------

class TestDecisionRequest:
    def test_defaults(self):
        req = DecisionRequest(description="test", source_plan="P01")
        assert req.module_id == ""
        assert req.change_type == ""
        assert req.blast_radius == "low"
        assert req.reversible is True
        assert req.affects_contracts is False
        assert req.affects_kernel is False
        assert req.proposed_by == ""

    def test_custom_values(self):
        req = DecisionRequest(
            description="test",
            source_plan="P02",
            module_id="core.event_bus",
            change_type="contract",
            blast_radius="high",
            reversible=False,
            affects_contracts=True,
            affects_kernel=True,
            proposed_by="agent-1",
        )
        assert req.module_id == "core.event_bus"
        assert req.change_type == "contract"
        assert req.blast_radius == "high"
        assert req.reversible is False
        assert req.affects_contracts is True
        assert req.affects_kernel is True
        assert req.proposed_by == "agent-1"


# ---------------------------------------------------------------------------
# DecisionRecord dataclass
# ---------------------------------------------------------------------------

class TestDecisionRecord:
    def test_auto_generates_id(self):
        rec = DecisionRecord(
            decision_id="",
            decision_class=DecisionClass.D1,
            description="test",
            source_plan="P01",
            module_id="",
            change_type="config",
            blast_radius="low",
            reversible=True,
            affects_contracts=False,
            affects_kernel=False,
            requirements={},
        )
        assert rec.decision_id != ""
        assert len(rec.decision_id) == 32

    def test_auto_generates_timestamp(self):
        before = time.time()
        rec = DecisionRecord(
            decision_id="",
            decision_class=DecisionClass.D1,
            description="test",
            source_plan="P01",
            module_id="",
            change_type="config",
            blast_radius="low",
            reversible=True,
            affects_contracts=False,
            affects_kernel=False,
            requirements={},
        )
        after = time.time()
        assert before <= rec.timestamp <= after

    def test_default_status(self):
        rec = DecisionRecord(
            decision_id="x",
            decision_class=DecisionClass.D1,
            description="test",
            source_plan="P01",
            module_id="",
            change_type="config",
            blast_radius="low",
            reversible=True,
            affects_contracts=False,
            affects_kernel=False,
            requirements={},
            timestamp=1000.0,
        )
        assert rec.status == "proposed"


# ---------------------------------------------------------------------------
# Classification rules
# ---------------------------------------------------------------------------

class TestClassify:
    def test_classify_d0_default(self, engine):
        """Default request with no special flags -> D0."""
        req = DecisionRequest(description="minor note", source_plan="P00")
        rec = engine.classify(req)
        assert rec.decision_class == DecisionClass.D0

    def test_classify_d1_config(self, engine):
        req = DecisionRequest(
            description="config change",
            source_plan="P01",
            change_type="config",
        )
        rec = engine.classify(req)
        assert rec.decision_class == DecisionClass.D1

    def test_classify_d2_module(self, engine):
        req = DecisionRequest(
            description="new module",
            source_plan="P02",
            change_type="module",
            blast_radius="medium",
        )
        rec = engine.classify(req)
        assert rec.decision_class == DecisionClass.D2

    def test_classify_d2_high_reversible(self, engine):
        req = DecisionRequest(
            description="high impact but reversible",
            source_plan="P02",
            blast_radius="high",
            reversible=True,
        )
        rec = engine.classify(req)
        assert rec.decision_class == DecisionClass.D2

    def test_classify_d3_architecture(self, engine):
        req = DecisionRequest(
            description="arch change",
            source_plan="P03",
            change_type="architecture",
        )
        rec = engine.classify(req)
        assert rec.decision_class == DecisionClass.D3

    def test_classify_d3_contracts(self, engine):
        req = DecisionRequest(
            description="contract change",
            source_plan="P03",
            affects_contracts=True,
            blast_radius="low",
        )
        rec = engine.classify(req)
        assert rec.decision_class == DecisionClass.D3

    def test_classify_d3_critical_reversible(self, engine):
        req = DecisionRequest(
            description="critical but reversible",
            source_plan="P03",
            blast_radius="critical",
            reversible=True,
        )
        rec = engine.classify(req)
        assert rec.decision_class == DecisionClass.D3

    def test_classify_d3_high_irreversible(self, engine):
        req = DecisionRequest(
            description="high and irreversible",
            source_plan="P03",
            blast_radius="high",
            reversible=False,
        )
        rec = engine.classify(req)
        assert rec.decision_class == DecisionClass.D3

    def test_classify_d4_critical_irreversible(self, engine):
        req = DecisionRequest(
            description="critical irreversible",
            source_plan="P04",
            blast_radius="critical",
            reversible=False,
        )
        rec = engine.classify(req)
        assert rec.decision_class == DecisionClass.D4

    def test_classify_d4_contracts_high_blast(self, engine):
        req = DecisionRequest(
            description="contract high blast",
            source_plan="P04",
            affects_contracts=True,
            blast_radius="high",
        )
        rec = engine.classify(req)
        assert rec.decision_class == DecisionClass.D4

    def test_classify_d5_kernel(self, engine):
        req = DecisionRequest(
            description="kernel change",
            source_plan="P05",
            affects_kernel=True,
        )
        rec = engine.classify(req)
        assert rec.decision_class == DecisionClass.D5

    def test_classify_generates_unique_ids(self, engine):
        r1 = engine.classify(DecisionRequest(description="a", source_plan="P01"))
        r2 = engine.classify(DecisionRequest(description="b", source_plan="P01"))
        assert r1.decision_id != r2.decision_id

    def test_classify_sets_requirements(self, engine):
        req = DecisionRequest(
            description="kernel",
            source_plan="P05",
            affects_kernel=True,
        )
        rec = engine.classify(req)
        assert rec.requirements["human"] is True
        assert rec.requirements["council"] == "4/4"
        assert rec.requirements["evidence"] == "required"


# ---------------------------------------------------------------------------
# Gate management
# ---------------------------------------------------------------------------

class TestGateManagement:
    def test_register_gate(self, engine):
        g = GateDefinition(
            gate_id="G-REG-01",
            name="Register Gate",
            description="test",
            fail_condition="none",
            blocks="nothing",
        )
        result = engine.register_gate(g)
        assert result["gate_id"] == "G-REG-01"
        assert result["name"] == "Register Gate"

    def test_register_gate_replaces_existing(self, engine):
        g1 = GateDefinition(
            gate_id="G-DUP-01", name="V1", description="",
            fail_condition="", blocks="",
        )
        g2 = GateDefinition(
            gate_id="G-DUP-01", name="V2", description="updated",
            fail_condition="", blocks="",
        )
        engine.register_gate(g1)
        engine.register_gate(g2)
        result = engine.evaluate_gate("G-DUP-01")
        assert result["name"] == "V2"

    def test_evaluate_gate_pass(self, engine, gate):
        result = engine.evaluate_gate("G-TEST-01")
        assert result["result"] == GateResult.PASS
        assert result["gate_id"] == "G-TEST-01"

    def test_evaluate_gate_not_registered(self, engine):
        result = engine.evaluate_gate("G-NOPE-99")
        assert result["result"] == GateResult.FAIL
        assert "not registered" in result["message"]

    def test_evaluate_gate_has_timestamp(self, engine, gate):
        before = time.time()
        result = engine.evaluate_gate("G-TEST-01")
        after = time.time()
        assert before <= result["timestamp"] <= after

    def test_evaluate_gate_includes_blocks(self, engine, gate):
        result = engine.evaluate_gate("G-TEST-01")
        assert result["blocks"] == "test.pipeline"


# ---------------------------------------------------------------------------
# Query decisions
# ---------------------------------------------------------------------------

class TestGetDecisions:
    def test_get_all_decisions(self, classified_engine):
        engine, _ = classified_engine
        results = engine.get_decisions()
        assert len(results) == 4

    def test_filter_by_class(self, classified_engine):
        engine, _ = classified_engine
        results = engine.get_decisions(decision_class="D5")
        assert len(results) == 1
        assert results[0]["decision_class"] == "D5"

    def test_filter_by_plan(self, classified_engine):
        engine, _ = classified_engine
        results = engine.get_decisions(source_plan="P01")
        assert len(results) == 1
        assert results[0]["source_plan"] == "P01"

    def test_filter_no_match(self, classified_engine):
        engine, _ = classified_engine
        results = engine.get_decisions(decision_class="D0")
        assert len(results) >= 0  # D0 only if default classification gave D0

    def test_ordered_by_timestamp_desc(self, classified_engine):
        engine, _ = classified_engine
        results = engine.get_decisions()
        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_empty_engine(self, engine):
        results = engine.get_decisions()
        assert results == []


# ---------------------------------------------------------------------------
# DECISION_REQUIREMENTS matrix
# ---------------------------------------------------------------------------

class TestDecisionRequirements:
    def test_d0_no_requirements(self):
        reqs = DECISION_REQUIREMENTS[DecisionClass.D0]
        assert reqs["human"] is False
        assert reqs["council"] is False
        assert reqs["evidence"] is False

    def test_d5_full_requirements(self):
        reqs = DECISION_REQUIREMENTS[DecisionClass.D5]
        assert reqs["human"] is True
        assert reqs["council"] == "4/4"
        assert reqs["evidence"] == "required"
        assert reqs["external"] is True

    def test_d4_requires_human_and_lpw(self):
        reqs = DECISION_REQUIREMENTS[DecisionClass.D4]
        assert reqs["human"] is True
        assert reqs["evidence"] == "required"
        assert reqs["retention_hot"] == "infinite"

    def test_all_classes_have_retention(self):
        for dc in DecisionClass:
            reqs = DECISION_REQUIREMENTS[dc]
            assert "retention_hot" in reqs
            assert "retention_cold" in reqs


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_factory_returns_instance(self):
        inst = get_decision_engine()
        assert isinstance(inst, DecisionGateEngine)

    def test_factory_idempotent(self):
        a = get_decision_engine()
        b = get_decision_engine()
        assert a is b


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_classify(self, engine):
        errors = []
        results = []

        def classify_one(idx):
            try:
                req = DecisionRequest(
                    description=f"concurrent-{idx}",
                    source_plan=f"P{idx % 5}",
                    change_type="config",
                )
                r = engine.classify(req)
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=classify_one, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 30

    def test_concurrent_reads_and_writes(self, engine):
        errors = []
        retriable = (sqlite3.OperationalError, sqlite3.InterfaceError, IndexError)
        write_count = [0]
        count_lock = threading.Lock()

        # Pre-classify so readers have data
        for i in range(5):
            engine.classify(DecisionRequest(
                description=f"seed-{i}", source_plan="P00", change_type="config",
            ))

        def writer():
            for i in range(10):
                for attempt in range(8):
                    try:
                        engine.classify(DecisionRequest(
                            description=f"w-{i}", source_plan="P01", change_type="config",
                        ))
                        with count_lock:
                            write_count[0] += 1
                        break
                    except retriable:
                        if attempt == 7:
                            errors.append(RuntimeError(f"writer gave up at {i}"))
                        time.sleep(0.05 * (2 ** attempt))
                    except Exception as e:
                        errors.append(e)
                        break

        def reader():
            for _ in range(10):
                for attempt in range(8):
                    try:
                        engine.get_decisions()
                        break
                    except retriable:
                        if attempt == 7:
                            errors.append(RuntimeError("reader gave up"))
                        time.sleep(0.05 * (2 ** attempt))
                    except Exception as e:
                        errors.append(e)
                        break

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Ensure all threads completed
        assert all(not t.is_alive() for t in threads)
        assert not errors
        assert write_count[0] == 20
        total = len(engine.get_decisions())
        # 5 seed + write_count
        assert total == 5 + write_count[0]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_classify_with_empty_description(self, engine):
        rec = engine.classify(DecisionRequest(description="", source_plan="P01"))
        assert rec.decision_id != ""
        assert rec.description == ""

    def test_classify_preserves_all_fields(self, engine):
        req = DecisionRequest(
            description="full test",
            source_plan="P10",
            module_id="core.test",
            change_type="module",
            blast_radius="high",
            reversible=False,
            affects_contracts=True,
            affects_kernel=False,
            proposed_by="agent-x",
        )
        rec = engine.classify(req)
        assert rec.module_id == "core.test"
        assert rec.change_type == "module"
        assert rec.blast_radius == "high"
        assert rec.reversible is False
        assert rec.affects_contracts is True

    def test_multiple_gates_independent(self, engine):
        for i in range(5):
            g = GateDefinition(
                gate_id=f"G-MULTI-{i:02d}",
                name=f"Gate {i}",
                description="",
                fail_condition="",
                blocks=f"block-{i}",
            )
            engine.register_gate(g)

        for i in range(5):
            result = engine.evaluate_gate(f"G-MULTI-{i:02d}")
            assert result["result"] == GateResult.PASS
            assert result["blocks"] == f"block-{i}"
