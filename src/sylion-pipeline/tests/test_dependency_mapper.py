"""
Tests for sylion.core.dependency_mapper -- DependencyMapper

Covers:
  - add_edge: validation, idempotent inserts, defaults
  - remove_edge: found / not-found
  - list_edges: filters, limit
  - get_dependents / get_dependencies: directional lookups
  - compute_graph: BFS traversal, depth limiting, snapshot storage
  - get_graph / list_graphs: retrieval and filtering
  - detect_cycles: DFS with 3-colouring, cycle reconstruction, event emission
  - get_stats: aggregate counters
  - Thread safety: concurrent add_edge calls
  - Singleton: get_dependency_mapper / reset_dependency_mapper
"""
from __future__ import annotations

import threading
import time

import pytest

from sylion.core.dependency_mapper import (
    VALID_DEPENDENCY_TYPES,
    DependencyMapper,
    get_dependency_mapper,
    reset_dependency_mapper,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    eb = EventBus()
    eb._captured: list[SylionEvent] = []

    _orig = eb.publish

    def _capture(event: SylionEvent):
        eb._captured.append(event)
        return _orig(event)

    eb.publish = _capture
    return eb


@pytest.fixture
def mapper():
    """Fresh DependencyMapper (in-memory, no event bus)."""
    return DependencyMapper()


@pytest.fixture
def mapper_with_bus(bus):
    """DependencyMapper wired to the captured EventBus."""
    return DependencyMapper(event_bus=bus)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_chain(mapper: DependencyMapper, modules: list[str], **kwargs) -> list[dict]:
    """Add edges forming a chain: modules[0]->modules[1]->...->modules[n]."""
    results = []
    for i in range(len(modules) - 1):
        results.append(mapper.add_edge(modules[i], modules[i + 1], **kwargs))
    return results


# ============================================================================
# TestAddEdge
# ============================================================================

class TestAddEdge:
    def test_add_basic_edge(self, mapper):
        result = mapper.add_edge("core.a", "core.b")
        assert result["from_module"] == "core.a"
        assert result["to_module"] == "core.b"
        assert result["dependency_type"] == "direct"
        assert result["strength"] == 1.0
        assert result["edge_id"]
        assert result["detected_at"] > 0

    def test_add_edge_with_all_params(self, mapper):
        result = mapper.add_edge(
            "core.x", "core.y",
            dependency_type="runtime",
            contract_name="contract.xy",
            strength=0.5,
        )
        assert result["dependency_type"] == "runtime"
        assert result["contract_name"] == "contract.xy"
        assert result["strength"] == 0.5

    def test_add_edge_invalid_type_raises(self, mapper):
        with pytest.raises(ValueError, match="Invalid dependency_type"):
            mapper.add_edge("core.a", "core.b", dependency_type="unknown")

    def test_add_edge_strength_zero(self, mapper):
        result = mapper.add_edge("core.a", "core.b", strength=0.0)
        assert result["strength"] == 0.0

    def test_add_edge_strength_above_one_raises(self, mapper):
        with pytest.raises(ValueError, match="strength"):
            mapper.add_edge("core.a", "core.b", strength=1.5)

    def test_add_edge_negative_strength_raises(self, mapper):
        with pytest.raises(ValueError, match="strength"):
            mapper.add_edge("core.a", "core.b", strength=-0.1)

    def test_add_edge_empty_from_raises(self, mapper):
        with pytest.raises(ValueError, match="non-empty"):
            mapper.add_edge("", "core.b")

    def test_add_edge_empty_to_raises(self, mapper):
        with pytest.raises(ValueError, match="non-empty"):
            mapper.add_edge("core.a", "")

    def test_add_edge_stores_in_db(self, mapper):
        mapper.add_edge("core.a", "core.b")
        edges = mapper.list_edges()
        assert len(edges) == 1
        assert edges[0]["from_module"] == "core.a"

    def test_all_valid_dependency_types(self, mapper):
        for dt in VALID_DEPENDENCY_TYPES:
            result = mapper.add_edge(f"mod.{dt}", f"dep.{dt}", dependency_type=dt)
            assert result["dependency_type"] == dt


# ============================================================================
# TestRemoveEdge
# ============================================================================

class TestRemoveEdge:
    def test_remove_existing_edge(self, mapper):
        edge = mapper.add_edge("core.a", "core.b")
        assert mapper.remove_edge(edge["edge_id"]) is True
        assert mapper.list_edges() == []

    def test_remove_nonexistent_edge(self, mapper):
        assert mapper.remove_edge("nonexistent_id") is False

    def test_remove_twice_returns_false(self, mapper):
        edge = mapper.add_edge("core.a", "core.b")
        assert mapper.remove_edge(edge["edge_id"]) is True
        assert mapper.remove_edge(edge["edge_id"]) is False


# ============================================================================
# TestListEdges
# ============================================================================

class TestListEdges:
    def test_list_all_edges(self, mapper):
        mapper.add_edge("a", "b")
        mapper.add_edge("c", "d")
        edges = mapper.list_edges()
        assert len(edges) == 2

    def test_filter_by_from_module(self, mapper):
        mapper.add_edge("a", "b")
        mapper.add_edge("a", "c")
        mapper.add_edge("x", "y")
        edges = mapper.list_edges(from_module="a")
        assert len(edges) == 2
        assert all(e["from_module"] == "a" for e in edges)

    def test_filter_by_to_module(self, mapper):
        mapper.add_edge("a", "b")
        mapper.add_edge("c", "b")
        mapper.add_edge("x", "y")
        edges = mapper.list_edges(to_module="b")
        assert len(edges) == 2
        assert all(e["to_module"] == "b" for e in edges)

    def test_filter_by_type(self, mapper):
        mapper.add_edge("a", "b", dependency_type="runtime")
        mapper.add_edge("c", "d", dependency_type="build")
        edges = mapper.list_edges(dependency_type="runtime")
        assert len(edges) == 1
        assert edges[0]["dependency_type"] == "runtime"

    def test_limit(self, mapper):
        for i in range(10):
            mapper.add_edge(f"mod{i}", f"dep{i}")
        edges = mapper.list_edges(limit=5)
        assert len(edges) == 5

    def test_combined_filters(self, mapper):
        mapper.add_edge("a", "b", dependency_type="direct")
        mapper.add_edge("a", "c", dependency_type="runtime")
        mapper.add_edge("b", "c", dependency_type="direct")
        edges = mapper.list_edges(from_module="a", dependency_type="direct")
        assert len(edges) == 1
        assert edges[0]["to_module"] == "b"

    def test_empty_db(self, mapper):
        assert mapper.list_edges() == []


# ============================================================================
# TestGetDependents
# ============================================================================

class TestGetDependents:
    def test_get_dependents(self, mapper):
        mapper.add_edge("a", "target")
        mapper.add_edge("b", "target")
        mapper.add_edge("c", "other")
        deps = mapper.get_dependents("target")
        assert len(deps) == 2
        sources = {d["from_module"] for d in deps}
        assert sources == {"a", "b"}

    def test_get_dependents_none(self, mapper):
        assert mapper.get_dependents("unknown") == []


# ============================================================================
# TestGetDependencies
# ============================================================================

class TestGetDependencies:
    def test_get_dependencies(self, mapper):
        mapper.add_edge("source", "a")
        mapper.add_edge("source", "b")
        mapper.add_edge("other", "c")
        deps = mapper.get_dependencies("source")
        assert len(deps) == 2
        targets = {d["to_module"] for d in deps}
        assert targets == {"a", "b"}

    def test_get_dependencies_none(self, mapper):
        assert mapper.get_dependencies("unknown") == []


# ============================================================================
# TestComputeGraph
# ============================================================================

class TestComputeGraph:
    def test_simple_chain(self, mapper):
        _add_chain(mapper, ["a", "b", "c"])
        graph = mapper.compute_graph("a", depth=3)
        assert graph["root_module"] == "a"
        assert "a" in graph["nodes"]
        assert "b" in graph["nodes"]
        assert "c" in graph["nodes"]
        assert graph["node_count"] == 3
        assert graph["edge_count"] == 2

    def test_depth_one(self, mapper):
        _add_chain(mapper, ["a", "b", "c"])
        graph = mapper.compute_graph("a", depth=1)
        assert "a" in graph["nodes"]
        assert "b" in graph["nodes"]
        # c should not be reachable at depth 1 from a (a->b is depth 1)
        assert graph["edge_count"] == 1

    def test_depth_zero(self, mapper):
        mapper.add_edge("a", "b")
        graph = mapper.compute_graph("a", depth=0)
        assert graph["node_count"] == 1
        assert graph["edge_count"] == 0
        assert graph["nodes"] == ["a"]

    def test_diamond_graph(self, mapper):
        # a->b, a->c, b->d, c->d
        mapper.add_edge("a", "b")
        mapper.add_edge("a", "c")
        mapper.add_edge("b", "d")
        mapper.add_edge("c", "d")
        graph = mapper.compute_graph("a", depth=3)
        assert graph["node_count"] == 4
        assert graph["edge_count"] == 4

    def test_isolated_root(self, mapper):
        graph = mapper.compute_graph("lonely", depth=3)
        assert graph["node_count"] == 1
        assert graph["edge_count"] == 0

    def test_graph_stored_and_retrieved(self, mapper):
        mapper.add_edge("a", "b")
        result = mapper.compute_graph("a", depth=3)
        stored = mapper.get_graph(result["graph_id"])
        assert stored is not None
        assert stored["root_module"] == "a"
        assert stored["snapshot"]["nodes"] == ["a", "b"]

    def test_compute_graph_returns_graph_id(self, mapper):
        mapper.add_edge("x", "y")
        graph = mapper.compute_graph("x")
        assert "graph_id" in graph
        assert len(graph["graph_id"]) == 32  # uuid hex


# ============================================================================
# TestGetGraph
# ============================================================================

class TestGetGraph:
    def test_get_existing_graph(self, mapper):
        mapper.add_edge("a", "b")
        result = mapper.compute_graph("a")
        stored = mapper.get_graph(result["graph_id"])
        assert stored is not None
        assert stored["graph_id"] == result["graph_id"]

    def test_get_nonexistent_graph(self, mapper):
        assert mapper.get_graph("nonexistent") is None

    def test_snapshot_is_parsed(self, mapper):
        mapper.add_edge("a", "b")
        result = mapper.compute_graph("a")
        stored = mapper.get_graph(result["graph_id"])
        assert isinstance(stored["snapshot"], dict)
        assert "nodes" in stored["snapshot"]
        assert "edges" in stored["snapshot"]


# ============================================================================
# TestListGraphs
# ============================================================================

class TestListGraphs:
    def test_list_all_graphs(self, mapper):
        mapper.add_edge("a", "b")
        mapper.add_edge("c", "d")
        mapper.compute_graph("a")
        mapper.compute_graph("c")
        graphs = mapper.list_graphs()
        assert len(graphs) == 2

    def test_filter_by_root_module(self, mapper):
        mapper.add_edge("a", "b")
        mapper.add_edge("c", "d")
        mapper.compute_graph("a")
        mapper.compute_graph("c")
        graphs = mapper.list_graphs(root_module="a")
        assert len(graphs) == 1
        assert graphs[0]["root_module"] == "a"

    def test_limit(self, mapper):
        mapper.add_edge("a", "b")
        for i in range(5):
            mapper.compute_graph("a")
        graphs = mapper.list_graphs(limit=3)
        assert len(graphs) == 3

    def test_empty_db(self, mapper):
        assert mapper.list_graphs() == []


# ============================================================================
# TestDetectCycles
# ============================================================================

class TestDetectCycles:
    def test_no_cycles(self, mapper):
        _add_chain(mapper, ["a", "b", "c"])
        cycles = mapper.detect_cycles()
        assert cycles == []

    def test_simple_cycle(self, mapper):
        mapper.add_edge("a", "b")
        mapper.add_edge("b", "a")
        cycles = mapper.detect_cycles()
        assert len(cycles) >= 1
        # Verify the cycle involves a and b
        all_modules_in_cycles = {m for c in cycles for m in c}
        assert "a" in all_modules_in_cycles
        assert "b" in all_modules_in_cycles

    def test_three_node_cycle(self, mapper):
        mapper.add_edge("a", "b")
        mapper.add_edge("b", "c")
        mapper.add_edge("c", "a")
        cycles = mapper.detect_cycles()
        assert len(cycles) >= 1
        all_modules = {m for c in cycles for m in c}
        assert "a" in all_modules
        assert "b" in all_modules
        assert "c" in all_modules

    def test_self_loop(self, mapper):
        mapper.add_edge("a", "a")
        cycles = mapper.detect_cycles()
        assert len(cycles) >= 1
        assert any("a" in c for c in cycles)

    def test_complex_with_cycle(self, mapper):
        # a->b->c (no cycle) + d->e->d (cycle)
        mapper.add_edge("a", "b")
        mapper.add_edge("b", "c")
        mapper.add_edge("d", "e")
        mapper.add_edge("e", "d")
        cycles = mapper.detect_cycles()
        assert len(cycles) >= 1
        all_modules = {m for c in cycles for m in c}
        assert "d" in all_modules
        assert "e" in all_modules

    def test_cycle_emits_event(self, mapper_with_bus, bus):
        mapper_with_bus.add_edge("x", "y")
        mapper_with_bus.add_edge("y", "x")
        mapper_with_bus.detect_cycles()
        events = bus.query(topic="dependency.cycle_detected")
        assert len(events) >= 1
        import json
        payload = json.loads(events[0]["payload"])
        assert payload["cycle_count"] >= 1

    def test_no_cycle_no_event(self, mapper_with_bus, bus):
        mapper_with_bus.add_edge("a", "b")
        mapper_with_bus.add_edge("b", "c")
        mapper_with_bus.detect_cycles()
        events = bus.query(topic="dependency.cycle_detected")
        assert len(events) == 0


# ============================================================================
# TestGetStats
# ============================================================================

class TestGetStats:
    def test_empty_stats(self, mapper):
        stats = mapper.get_stats()
        assert stats["total_edges"] == 0
        assert stats["total_graphs"] == 0
        assert stats["distinct_modules"] == 0
        assert stats["by_type"] == {}
        assert stats["avg_strength"] == 0.0

    def test_stats_after_edges(self, mapper):
        mapper.add_edge("a", "b", strength=0.5)
        mapper.add_edge("a", "c", dependency_type="runtime", strength=1.0)
        stats = mapper.get_stats()
        assert stats["total_edges"] == 2
        assert stats["distinct_modules"] == 3  # a, b, c
        assert stats["by_type"]["direct"] == 1
        assert stats["by_type"]["runtime"] == 1
        assert stats["avg_strength"] == 0.75

    def test_stats_includes_graphs(self, mapper):
        mapper.add_edge("a", "b")
        mapper.compute_graph("a")
        stats = mapper.get_stats()
        assert stats["total_graphs"] == 1


# ============================================================================
# TestThreadSafety
# ============================================================================

class TestThreadSafety:
    def test_concurrent_add_edges(self, mapper):
        errors: list[Exception] = []

        def worker(start: int):
            try:
                for i in range(20):
                    mapper.add_edge(f"mod_{start}_{i}", f"dep_{start}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert mapper.get_stats()["total_edges"] == 100

    def test_concurrent_read_write(self, mapper):
        """Reads should not fail while writes are happening."""
        errors: list[Exception] = []

        def writer():
            for i in range(20):
                try:
                    mapper.add_edge(f"w_{i}", f"wd_{i}")
                except Exception as e:
                    errors.append(e)

        def reader():
            for _ in range(20):
                try:
                    mapper.list_edges()
                    mapper.get_stats()
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

        assert errors == []


# ============================================================================
# TestSingleton
# ============================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        reset_dependency_mapper()
        m = get_dependency_mapper()
        assert isinstance(m, DependencyMapper)

    def test_get_returns_same_instance(self):
        reset_dependency_mapper()
        m1 = get_dependency_mapper()
        m2 = get_dependency_mapper()
        assert m1 is m2
        reset_dependency_mapper()

    def test_reset_clears_singleton(self):
        reset_dependency_mapper()
        m1 = get_dependency_mapper()
        reset_dependency_mapper()
        m2 = get_dependency_mapper()
        assert m1 is not m2
        reset_dependency_mapper()
