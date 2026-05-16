"""
Tests for CascadeAnalyzer -- analyze_change, get_analysis, list_analyses,
get_cascade_paths, get_stats, singleton lifecycle, thread safety, risk
calculation, path tracking, event emission, validation.

~40 tests covering CRUD, cascade analysis, risk calculation, path tracking.
"""

from __future__ import annotations

import json
import time
import threading

import pytest

from sylion.governance.cascade_analyzer import (
    CascadeAnalyzer,
    VALID_CHANGE_TYPES,
    VALID_RISK_LEVELS,
    get_cascade_analyzer,
    reset_cascade_analyzer,
)
from sylion.core.contract_registry import (
    ContractRegistry,
    Contract,
    ContractType,
)
from sylion.core import contract_registry as cr_mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset global singletons before and after every test."""
    reset_cascade_analyzer()
    cr_mod._contract_registry = None
    yield
    reset_cascade_analyzer()
    cr_mod._contract_registry = None


@pytest.fixture
def bus():
    from sylion.core.event_bus import EventBus
    return EventBus()


@pytest.fixture
def cr():
    """Fresh in-memory ContractRegistry."""
    return ContractRegistry()


@pytest.fixture
def ca():
    """Fresh in-memory CascadeAnalyzer."""
    return CascadeAnalyzer()


@pytest.fixture
def ca_bus(bus):
    """CascadeAnalyzer with EventBus."""
    return CascadeAnalyzer(event_bus=bus)


@pytest.fixture
def ca_cr(cr):
    """CascadeAnalyzer wired to the same in-memory ContractRegistry.

    We inject cr into the singleton so the lazy import picks it up.
    """
    cr_mod._contract_registry = cr
    return CascadeAnalyzer()


@pytest.fixture
def ca_cr_bus(cr, bus):
    """CascadeAnalyzer with ContractRegistry and EventBus."""
    cr_mod._contract_registry = cr
    return CascadeAnalyzer(event_bus=bus)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _publish_contract(cr, name, producer, consumers,
                      contract_type=ContractType.GRPC_SERVICE,
                      version="1.0.0"):
    """Publish a contract through the registry."""
    contract = Contract(
        name=name,
        contract_type=contract_type,
        version=version,
        producer_module=producer,
        consumer_modules=consumers,
    )
    return cr.publish(contract)


def _insert_analysis(ca, analysis_id, source_module="mod_a",
                     change_type="api_change", change_description="test",
                     affected_modules=None, risk_level="low",
                     metadata=None):
    """Directly insert an analysis row for controlled testing."""
    now = time.time()
    am = json.dumps(affected_modules) if affected_modules else "[]"
    md = json.dumps(metadata) if metadata else None
    with ca._lock:
        ca._conn.execute("""
            INSERT INTO cascade_analyses
            (analysis_id, source_module, change_type, change_description,
             affected_modules, risk_level, created_at, metadata)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            analysis_id, source_module, change_type, change_description,
            am, risk_level, now, md,
        ))
        ca._conn.commit()


def _insert_path(ca, path_id, analysis_id, from_module="mod_a",
                 to_module="mod_b", path_type="direct", confidence=1.0):
    """Directly insert a cascade path row."""
    with ca._lock:
        ca._conn.execute("""
            INSERT INTO cascade_paths
            (path_id, analysis_id, from_module, to_module,
             path_type, confidence)
            VALUES (?,?,?,?,?,?)
        """, (
            path_id, analysis_id, from_module, to_module,
            path_type, confidence,
        ))
        ca._conn.commit()


# ===========================================================================
# TestAnalyzeChange
# ===========================================================================

class TestAnalyzeChange:

    def test_basic_analysis(self, ca):
        result = ca.analyze_change("mod_a", "api_change", "changed endpoint")
        assert result is not None
        assert "analysis_id" in result
        assert result["source_module"] == "mod_a"
        assert result["change_type"] == "api_change"
        assert result["change_description"] == "changed endpoint"
        assert result["risk_level"] == "low"
        assert result["affected_modules"] == []

    def test_invalid_change_type_raises(self, ca):
        with pytest.raises(ValueError, match="Invalid change_type"):
            ca.analyze_change("mod_a", "invalid_type")

    def test_all_valid_change_types(self, ca):
        for ct in VALID_CHANGE_TYPES:
            result = ca.analyze_change("mod_a", ct)
            assert result["change_type"] == ct

    def test_analysis_with_affected_modules(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b", "mod_c"])
        result = ca_cr.analyze_change("mod_a", "api_change")
        assert "mod_b" in result["affected_modules"]
        assert "mod_c" in result["affected_modules"]

    def test_analysis_deduplicates_modules(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b"])
        _publish_contract(cr, "evt_a", "mod_a", ["mod_b"],
                          contract_type=ContractType.EVENT_SCHEMA)
        result = ca_cr.analyze_change("mod_a", "api_change")
        assert result["affected_modules"].count("mod_b") == 1

    def test_analysis_no_affected_when_no_contracts(self, ca):
        result = ca.analyze_change("mod_a", "api_change")
        assert result["affected_modules"] == []

    def test_analysis_with_no_description(self, ca):
        result = ca.analyze_change("mod_a", "api_change")
        assert result["change_description"] == ""

    def test_analysis_emits_event(self, ca_cr_bus, cr, bus):
        events = []
        bus.subscribe("cascade.analyzed", lambda e: events.append(e))
        ca_cr_bus.analyze_change("mod_a", "api_change", "test change")
        assert len(events) == 1
        assert events[0].payload["source_module"] == "mod_a"
        assert events[0].payload["change_type"] == "api_change"
        assert "risk_level" in events[0].payload

    def test_analysis_without_event_bus(self, ca):
        # Should not raise even with no event bus
        result = ca.analyze_change("mod_a", "api_change")
        assert result is not None

    def test_analysis_created_at_is_set(self, ca):
        before = time.time()
        result = ca.analyze_change("mod_a", "api_change")
        after = time.time()
        assert before <= result["created_at"] <= after

    def test_analysis_metadata(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b", "mod_c"])
        result = ca_cr.analyze_change("mod_a", "api_change")
        meta = result["metadata"]
        assert meta["contract_count"] >= 2
        assert meta["unique_affected"] == 2


# ===========================================================================
# TestGetAnalysis
# ===========================================================================

class TestGetAnalysis:

    def test_get_existing(self, ca):
        created = ca.analyze_change("mod_a", "api_change", "test")
        result = ca.get_analysis(created["analysis_id"])
        assert result is not None
        assert result["analysis_id"] == created["analysis_id"]
        assert result["source_module"] == "mod_a"

    def test_get_missing_returns_none(self, ca):
        assert ca.get_analysis("nonexistent") is None

    def test_get_parses_json_fields(self, ca):
        created = ca.analyze_change("mod_a", "api_change", "test")
        result = ca.get_analysis(created["analysis_id"])
        assert isinstance(result["affected_modules"], list)
        assert isinstance(result["metadata"], dict)

    def test_get_after_manual_insert(self, ca):
        _insert_analysis(ca, "a1", affected_modules=["mod_b", "mod_c"],
                         metadata={"key": "value"})
        result = ca.get_analysis("a1")
        assert result["affected_modules"] == ["mod_b", "mod_c"]
        assert result["metadata"]["key"] == "value"


# ===========================================================================
# TestListAnalyses
# ===========================================================================

class TestListAnalyses:

    def test_list_all(self, ca):
        ca.analyze_change("mod_a", "api_change")
        ca.analyze_change("mod_b", "schema_change")
        results = ca.list_analyses()
        assert len(results) == 2

    def test_list_ordered_newest_first(self, ca):
        ca.analyze_change("mod_a", "api_change")
        ca.analyze_change("mod_b", "schema_change")
        results = ca.list_analyses()
        assert results[0]["source_module"] == "mod_b"
        assert results[1]["source_module"] == "mod_a"

    def test_list_filter_by_source_module(self, ca):
        ca.analyze_change("mod_a", "api_change")
        ca.analyze_change("mod_b", "schema_change")
        ca.analyze_change("mod_a", "config_change")
        results = ca.list_analyses(source_module="mod_a")
        assert len(results) == 2
        assert all(r["source_module"] == "mod_a" for r in results)

    def test_list_filter_by_risk_level(self, ca_cr, cr):
        # Use low-risk contract type so risk is purely count-based
        _publish_contract(cr, "pol_a", "mod_a",
                          ["mod_b", "mod_c", "mod_d", "mod_e"],
                          contract_type=ContractType.POLICY_DEF)
        ca_cr.analyze_change("mod_a", "api_change")
        ca_cr.analyze_change("mod_z", "api_change")
        high_results = ca_cr.list_analyses(risk_level="high")
        low_results = ca_cr.list_analyses(risk_level="low")
        assert len(high_results) == 1
        assert len(low_results) == 1

    def test_list_with_limit(self, ca):
        for i in range(10):
            ca.analyze_change(f"mod_{i}", "api_change")
        results = ca.list_analyses(limit=5)
        assert len(results) == 5

    def test_list_empty(self, ca):
        assert ca.list_analyses() == []

    def test_list_combined_filters(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a",
                          ["mod_b", "mod_c", "mod_d", "mod_e"])
        ca_cr.analyze_change("mod_a", "api_change")
        ca_cr.analyze_change("mod_a", "config_change")
        ca_cr.analyze_change("mod_b", "api_change")
        results = ca_cr.list_analyses(
            source_module="mod_a", risk_level="low")
        # mod_a with 4 consumers is high risk, so filtering low returns 0
        assert len(results) == 0


# ===========================================================================
# TestGetCascadePaths
# ===========================================================================

class TestGetCascadePaths:

    def test_get_paths_for_analysis(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b", "mod_c"])
        analysis = ca_cr.analyze_change("mod_a", "api_change")
        paths = ca_cr.get_cascade_paths(analysis["analysis_id"])
        assert len(paths) >= 2
        modules_in_paths = {p["to_module"] for p in paths}
        assert "mod_b" in modules_in_paths
        assert "mod_c" in modules_in_paths

    def test_get_paths_empty_for_no_contracts(self, ca):
        analysis = ca.analyze_change("mod_a", "api_change")
        paths = ca.get_cascade_paths(analysis["analysis_id"])
        assert paths == []

    def test_get_paths_for_nonexistent_analysis(self, ca):
        paths = ca.get_cascade_paths("nonexistent")
        assert paths == []

    def test_path_has_correct_fields(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b"])
        analysis = ca_cr.analyze_change("mod_a", "api_change")
        paths = ca_cr.get_cascade_paths(analysis["analysis_id"])
        assert len(paths) >= 1
        path = paths[0]
        assert "path_id" in path
        assert "analysis_id" in path
        assert "from_module" in path
        assert "to_module" in path
        assert "path_type" in path
        assert "confidence" in path

    def test_direct_path_from_source(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b"])
        analysis = ca_cr.analyze_change("mod_a", "api_change")
        paths = ca_cr.get_cascade_paths(analysis["analysis_id"])
        direct_paths = [p for p in paths if p["path_type"] == "direct"]
        assert len(direct_paths) >= 1
        assert direct_paths[0]["from_module"] == "mod_a"
        assert direct_paths[0]["to_module"] == "mod_b"

    def test_transitive_paths(self, ca_cr, cr):
        # mod_a -> mod_b via svc_a
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b"])
        # mod_b -> mod_c via svc_b
        _publish_contract(cr, "svc_b", "mod_b", ["mod_c"])
        analysis = ca_cr.analyze_change("mod_a", "api_change")
        paths = ca_cr.get_cascade_paths(analysis["analysis_id"])
        transitive = [p for p in paths if p["path_type"] == "transitive"]
        transitive_targets = {p["to_module"] for p in transitive}
        assert "mod_c" in transitive_targets

    def test_no_transitive_back_to_source(self, ca_cr, cr):
        # mod_a -> mod_b
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b"])
        # mod_b -> mod_a (circular)
        _publish_contract(cr, "svc_b", "mod_b", ["mod_a"])
        analysis = ca_cr.analyze_change("mod_a", "api_change")
        paths = ca_cr.get_cascade_paths(analysis["analysis_id"])
        transitive = [p for p in paths if p["path_type"] == "transitive"]
        for p in transitive:
            assert p["to_module"] != "mod_a"

    def test_path_confidence_values(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b"])
        analysis = ca_cr.analyze_change("mod_a", "api_change")
        paths = ca_cr.get_cascade_paths(analysis["analysis_id"])
        for p in paths:
            assert 0.0 < p["confidence"] <= 1.0


# ===========================================================================
# TestRiskCalculation
# ===========================================================================

class TestRiskCalculation:

    def test_low_risk_no_affected(self, ca):
        result = ca.analyze_change("mod_a", "api_change")
        assert result["risk_level"] == "low"

    def test_low_risk_one_affected(self, ca_cr, cr):
        # Use policy_definition (not in high/medium risk sets) for pure count
        _publish_contract(cr, "pol_a", "mod_a", ["mod_b"],
                          contract_type=ContractType.POLICY_DEF)
        result = ca_cr.analyze_change("mod_a", "api_change")
        assert result["risk_level"] == "low"

    def test_medium_risk_two_affected(self, ca_cr, cr):
        _publish_contract(cr, "pol_a", "mod_a", ["mod_b", "mod_c"],
                          contract_type=ContractType.POLICY_DEF)
        result = ca_cr.analyze_change("mod_a", "api_change")
        assert result["risk_level"] == "medium"

    def test_high_risk_many_affected(self, ca_cr, cr):
        _publish_contract(cr, "pol_a", "mod_a",
                          ["mod_b", "mod_c", "mod_d", "mod_e"],
                          contract_type=ContractType.POLICY_DEF)
        result = ca_cr.analyze_change("mod_a", "api_change")
        assert result["risk_level"] == "high"

    def test_critical_risk_many_modules(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a",
                          ["m1", "m2", "m3", "m4", "m5", "m6"])
        result = ca_cr.analyze_change("mod_a", "api_change")
        assert result["risk_level"] == "critical"

    def test_interface_change_escalates_risk(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b"])
        result = ca_cr.analyze_change("mod_a", "interface_change")
        # 1 affected with interface_change -> medium
        assert result["risk_level"] == "medium"

    def test_interface_change_high_risk(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a",
                          ["mod_b", "mod_c"])
        result = ca_cr.analyze_change("mod_a", "interface_change")
        assert result["risk_level"] == "high"

    def test_interface_change_critical_risk(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a",
                          ["mod_b", "mod_c", "mod_d", "mod_e"])
        result = ca_cr.analyze_change("mod_a", "interface_change")
        assert result["risk_level"] == "critical"

    def test_high_risk_contract_type(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b"],
                          contract_type=ContractType.GRPC_SERVICE)
        result = ca_cr.analyze_change("mod_a", "api_change")
        # grpc_service is high-risk, 1 affected -> medium
        assert result["risk_level"] == "medium"

    def test_event_schema_high_risk(self, ca_cr, cr):
        _publish_contract(cr, "evt_a", "mod_a", ["mod_b"],
                          contract_type=ContractType.EVENT_SCHEMA)
        result = ca_cr.analyze_change("mod_a", "schema_change")
        assert result["risk_level"] == "medium"

    def test_config_schema_medium_risk(self, ca_cr, cr):
        _publish_contract(cr, "cfg_a", "mod_a", ["mod_b", "mod_c"],
                          contract_type=ContractType.CONFIG_SCHEMA)
        result = ca_cr.analyze_change("mod_a", "config_change")
        assert result["risk_level"] == "medium"


# ===========================================================================
# TestGetStats
# ===========================================================================

class TestGetStats:

    def test_empty_stats(self, ca):
        stats = ca.get_stats()
        assert stats["total"] == 0
        assert stats["by_risk_level"] == {}
        assert stats["by_change_type"] == {}
        assert stats["total_paths"] == 0
        assert stats["direct_paths"] == 0
        assert stats["transitive_paths"] == 0

    def test_stats_with_analyses(self, ca):
        ca.analyze_change("mod_a", "api_change")
        ca.analyze_change("mod_b", "schema_change")
        stats = ca.get_stats()
        assert stats["total"] == 2
        assert stats["by_change_type"]["api_change"] == 1
        assert stats["by_change_type"]["schema_change"] == 1

    def test_stats_by_risk_level(self, ca_cr, cr):
        _publish_contract(cr, "pol_a", "mod_a",
                          ["m1", "m2", "m3", "m4"],
                          contract_type=ContractType.POLICY_DEF)
        ca_cr.analyze_change("mod_a", "api_change")
        ca_cr.analyze_change("mod_z", "api_change")
        stats = ca_cr.get_stats()
        assert stats["by_risk_level"]["high"] == 1
        assert stats["by_risk_level"]["low"] == 1

    def test_stats_paths_count(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b", "mod_c"])
        ca_cr.analyze_change("mod_a", "api_change")
        stats = ca_cr.get_stats()
        assert stats["total_paths"] >= 2
        assert stats["direct_paths"] >= 2

    def test_stats_transitive_paths(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b"])
        _publish_contract(cr, "svc_b", "mod_b", ["mod_c"])
        ca_cr.analyze_change("mod_a", "api_change")
        stats = ca_cr.get_stats()
        assert stats["transitive_paths"] >= 1

    def test_stats_multiple_analyses_accumulate(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b"])
        ca_cr.analyze_change("mod_a", "api_change")
        ca_cr.analyze_change("mod_a", "schema_change")
        stats = ca_cr.get_stats()
        assert stats["total"] == 2


# ===========================================================================
# TestValidation
# ===========================================================================

class TestValidation:

    def test_invalid_change_type(self, ca):
        with pytest.raises(ValueError):
            ca.analyze_change("mod_a", "bad_type")

    def test_empty_string_change_type(self, ca):
        with pytest.raises(ValueError):
            ca.analyze_change("mod_a", "")

    def test_all_valid_change_types_accepted(self, ca):
        for ct in VALID_CHANGE_TYPES:
            result = ca.analyze_change("mod_a", ct)
            assert result["change_type"] == ct

    def test_valid_risk_levels_constant(self):
        assert "low" in VALID_RISK_LEVELS
        assert "medium" in VALID_RISK_LEVELS
        assert "high" in VALID_RISK_LEVELS
        assert "critical" in VALID_RISK_LEVELS

    def test_valid_change_types_constant(self):
        assert len(VALID_CHANGE_TYPES) == 5


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        assert isinstance(get_cascade_analyzer(), CascadeAnalyzer)

    def test_idempotent(self):
        a = get_cascade_analyzer()
        b = get_cascade_analyzer()
        assert a is b

    def test_reset_creates_new(self):
        a = get_cascade_analyzer()
        b = reset_cascade_analyzer()
        assert a is not b
        assert isinstance(b, CascadeAnalyzer)

    def test_get_after_reset(self):
        a = get_cascade_analyzer()
        reset_cascade_analyzer()
        c = get_cascade_analyzer()
        assert a is not c


# ===========================================================================
# TestThreadSafety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_analyze(self, ca):
        errors = []
        results = []

        def analyze(module):
            try:
                r = ca.analyze_change(module, "api_change", f"change on {module}")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=analyze, args=(f"mod_{i}",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10

    def test_concurrent_read_write(self, ca):
        errors = []

        # Insert initial analysis
        ca.analyze_change("mod_a", "api_change")

        def writer():
            try:
                for i in range(5):
                    ca.analyze_change(f"mod_w_{i}", "api_change")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(5):
                    ca.list_analyses()
                    ca.get_stats()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_analyze_with_contracts(self, ca_cr, cr):
        _publish_contract(cr, "svc_a", "mod_a", ["mod_b", "mod_c"])
        _publish_contract(cr, "svc_b", "mod_d", ["mod_e"])
        cr_mod._contract_registry = cr

        errors = []
        results = []

        def analyze(source):
            try:
                r = ca_cr.analyze_change(source, "api_change")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=analyze, args=("mod_a",)),
            threading.Thread(target=analyze, args=("mod_d",)),
            threading.Thread(target=analyze, args=("mod_z",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 3
        assert results[0]["analysis_id"] != results[1]["analysis_id"]


# ===========================================================================
# TestEdgeCases
# ===========================================================================

class TestEdgeCases:

    def test_analyze_module_with_no_contracts(self, ca):
        result = ca.analyze_change("unknown_module", "api_change")
        assert result["affected_modules"] == []
        assert result["risk_level"] == "low"

    def test_multiple_analyses_same_module(self, ca):
        r1 = ca.analyze_change("mod_a", "api_change", "first")
        r2 = ca.analyze_change("mod_a", "schema_change", "second")
        assert r1["analysis_id"] != r2["analysis_id"]
        all_results = ca.list_analyses()
        assert len(all_results) == 2

    def test_get_cascade_paths_for_manual_analysis(self, ca):
        _insert_analysis(ca, "a1")
        _insert_path(ca, "p1", "a1", "mod_a", "mod_b", "direct", 0.95)
        _insert_path(ca, "p2", "a1", "mod_b", "mod_c", "transitive", 0.76)
        paths = ca.get_cascade_paths("a1")
        assert len(paths) == 2

    def test_analysis_with_unicode_description(self, ca):
        result = ca.analyze_change("mod_a", "api_change",
                                   "Changed \u00e9ndp\u00f2int / \u7aef\u70b9")
        assert result["change_description"] == \
            "Changed \u00e9ndp\u00f2int / \u7aef\u70b9"

    def test_analysis_with_empty_description(self, ca):
        result = ca.analyze_change("mod_a", "api_change", "")
        assert result["change_description"] == ""

    def test_large_number_of_affected_modules(self, ca_cr, cr):
        consumers = [f"consumer_{i}" for i in range(20)]
        _publish_contract(cr, "svc_a", "mod_a", consumers)
        result = ca_cr.analyze_change("mod_a", "api_change")
        assert len(result["affected_modules"]) == 20
        assert result["risk_level"] == "critical"

    def test_contract_registry_unavailable(self, ca):
        """When contract registry raises, analysis still succeeds."""
        # The default CascadeAnalyzer has no registry wired up,
        # so _find_affected_modules will try to import and fail gracefully
        result = ca.analyze_change("mod_a", "api_change")
        assert result is not None
        assert result["affected_modules"] == []
