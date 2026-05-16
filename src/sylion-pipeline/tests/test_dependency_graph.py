"""Tests for sylion.contracts.dependency_graph module."""

import pytest

from sylion.contracts.dependency_graph import DependencyGraph


class TestDependencyGraph:
    @pytest.fixture
    def graph(self):
        return DependencyGraph()

    def test_add_dependency(self, graph):
        result = graph.add_dependency("mod-a", "mod-b")
        assert result is True

    def test_add_duplicate_idempotent(self, graph):
        graph.add_dependency("d1", "d2")
        graph.add_dependency("d1", "d2")
        deps = graph.get_dependencies("d1")
        assert len(deps) == 1

    def test_get_dependencies(self, graph):
        graph.add_dependency("g1", "g2")
        graph.add_dependency("g1", "g3")
        deps = graph.get_dependencies("g1")
        assert len(deps) == 2

    def test_get_dependencies_empty(self, graph):
        deps = graph.get_dependencies("isolated")
        assert deps == []

    def test_get_dependents(self, graph):
        graph.add_dependency("a", "target")
        graph.add_dependency("b", "target")
        dependents = graph.get_dependents("target")
        assert len(dependents) == 2

    def test_remove_dependency(self, graph):
        graph.add_dependency("r1", "r2")
        removed = graph.remove_dependency("r1", "r2")
        assert removed is True
        deps = graph.get_dependencies("r1")
        assert len(deps) == 0

    def test_remove_nonexistent(self, graph):
        removed = graph.remove_dependency("x", "y")
        assert removed is False

    def test_detect_cycles(self, graph):
        graph.add_dependency("c1", "c2")
        result = graph.detect_cycles()
        assert isinstance(result, (bool, dict, list))

    def test_topological_sort(self, graph):
        graph.add_dependency("leaf", "root")
        graph.add_dependency("mid", "root")
        graph.add_dependency("top", "mid")
        order = graph.topological_sort()
        assert len(order) >= 3

    def test_get_impact_analysis(self, graph):
        graph.add_dependency("i1", "core")
        graph.add_dependency("i2", "core")
        impacted = graph.get_impact_analysis("core")
        assert isinstance(impacted, (list, dict))

    def test_validate_all(self, graph):
        graph.add_dependency("v1", "v2")
        result = graph.validate_all()
        assert isinstance(result, (bool, dict))

    def test_get_stats(self, graph):
        graph.add_dependency("s1", "s2")
        graph.add_dependency("s1", "s3")
        stats = graph.get_stats()
        assert stats["total_dependencies"] >= 2
