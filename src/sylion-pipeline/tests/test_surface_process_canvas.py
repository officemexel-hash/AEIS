"""Comprehensive tests for sylion.surface.process_canvas module.

Covers: create_canvas, add_node, add_edge, remove_node, remove_edge,
        validate_dag, get_canvas, list_canvases, get_dag_projection,
        stats, edge cases, thread safety, event emission.
"""
import threading

import pytest

from sylion.core.event_bus import EventBus
from sylion.surface.process_canvas import (
    CanvasEdge,
    CanvasNode,
    ProcessCanvas,
    get_process_canvas,
)
import sylion.surface.process_canvas as mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    mod._canvas = None
    yield
    mod._canvas = None


@pytest.fixture
def canvas():
    return ProcessCanvas()


@pytest.fixture
def canvas_with_events():
    eb = EventBus()
    collected = []
    eb.subscribe("*", lambda e: collected.append(e))
    pc = ProcessCanvas(event_bus=eb)
    return pc, collected


def _build_linear_chain(canvas, n):
    """Helper: create canvas with n connected nodes. Returns (canvas_id, node_ids)."""
    c = canvas.create_canvas(f"Chain-{n}")
    node_ids = []
    for i in range(n):
        node = canvas.add_node(c["canvas_id"], "TASK", f"N{i}", float(i * 100), 0.0)
        node_ids.append(node["node_id"])
    for i in range(n - 1):
        canvas.add_edge(c["canvas_id"], node_ids[i], node_ids[i + 1], "SEQUENCE")
    return c["canvas_id"], node_ids


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

class TestCanvasNodeDataclass:
    def test_auto_id(self):
        n = CanvasNode()
        assert len(n.node_id) == 32

    def test_defaults(self):
        n = CanvasNode()
        assert n.node_type == "TASK"
        assert n.label == ""
        assert n.position_x == 0.0
        assert n.metadata == {}
        assert n.version == 1


class TestCanvasEdgeDataclass:
    def test_auto_id(self):
        e = CanvasEdge()
        assert len(e.edge_id) == 32

    def test_defaults(self):
        e = CanvasEdge()
        assert e.edge_type == "SEQUENCE"
        assert e.label == ""


# ---------------------------------------------------------------------------
# Create canvas
# ---------------------------------------------------------------------------

class TestCreateCanvas:
    def test_basic(self, canvas):
        result = canvas.create_canvas("Deployment Pipeline")
        assert result["status"] == "DRAFT"
        assert result["name"] == "Deployment Pipeline"
        assert len(result["canvas_id"]) == 32

    def test_multiple_canvases(self, canvas):
        c1 = canvas.create_canvas("Canvas A")
        c2 = canvas.create_canvas("Canvas B")
        assert c1["canvas_id"] != c2["canvas_id"]


# ---------------------------------------------------------------------------
# Add node
# ---------------------------------------------------------------------------

class TestAddNode:
    def test_basic(self, canvas):
        c = canvas.create_canvas("Test")
        node = canvas.add_node(c["canvas_id"], "TASK", "Build", 100.0, 200.0)
        assert len(node["node_id"]) == 32
        assert node["canvas_id"] == c["canvas_id"]

    def test_node_in_canvas(self, canvas):
        c = canvas.create_canvas("Test")
        canvas.add_node(c["canvas_id"], "TASK", "Build", 100.0, 200.0)
        data = canvas.get_canvas(c["canvas_id"])
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["label"] == "Build"
        assert data["nodes"][0]["position_x"] == 100.0
        assert data["nodes"][0]["position_y"] == 200.0

    def test_node_with_metadata(self, canvas):
        c = canvas.create_canvas("Test")
        canvas.add_node(
            c["canvas_id"], "TASK", "Deploy", 0, 0,
            metadata={"timeout": 30},
        )
        data = canvas.get_canvas(c["canvas_id"])
        assert data["nodes"][0]["metadata"] == {"timeout": 30}

    def test_multiple_node_types(self, canvas):
        c = canvas.create_canvas("Types")
        canvas.add_node(c["canvas_id"], "TASK", "Task")
        canvas.add_node(c["canvas_id"], "GATE", "Gate")
        canvas.add_node(c["canvas_id"], "EVENT", "Event")
        data = canvas.get_canvas(c["canvas_id"])
        types = {n["node_type"] for n in data["nodes"]}
        assert types == {"TASK", "GATE", "EVENT"}


# ---------------------------------------------------------------------------
# Add edge
# ---------------------------------------------------------------------------

class TestAddEdge:
    def test_basic(self, canvas):
        c = canvas.create_canvas("Flow")
        n1 = canvas.add_node(c["canvas_id"], "TASK", "Start")
        n2 = canvas.add_node(c["canvas_id"], "TASK", "End")
        edge = canvas.add_edge(c["canvas_id"], n1["node_id"], n2["node_id"], "SEQUENCE")
        assert len(edge["edge_id"]) == 32

    def test_edge_in_canvas(self, canvas):
        c = canvas.create_canvas("Flow")
        n1 = canvas.add_node(c["canvas_id"], "TASK", "A")
        n2 = canvas.add_node(c["canvas_id"], "TASK", "B")
        canvas.add_edge(c["canvas_id"], n1["node_id"], n2["node_id"], "CONDITIONAL", "Yes")
        data = canvas.get_canvas(c["canvas_id"])
        assert len(data["edges"]) == 1
        assert data["edges"][0]["edge_type"] == "CONDITIONAL"
        assert data["edges"][0]["label"] == "Yes"

    def test_edge_types(self, canvas):
        c = canvas.create_canvas("Types")
        n1 = canvas.add_node(c["canvas_id"], "TASK", "A")
        n2 = canvas.add_node(c["canvas_id"], "TASK", "B")
        n3 = canvas.add_node(c["canvas_id"], "TASK", "C")
        canvas.add_edge(c["canvas_id"], n1["node_id"], n2["node_id"], "SEQUENCE")
        canvas.add_edge(c["canvas_id"], n2["node_id"], n3["node_id"], "PARALLEL")
        data = canvas.get_canvas(c["canvas_id"])
        types = {e["edge_type"] for e in data["edges"]}
        assert types == {"SEQUENCE", "PARALLEL"}


# ---------------------------------------------------------------------------
# Remove node
# ---------------------------------------------------------------------------

class TestRemoveNode:
    def test_basic(self, canvas):
        c = canvas.create_canvas("Remove Test")
        n1 = canvas.add_node(c["canvas_id"], "TASK", "X")
        n2 = canvas.add_node(c["canvas_id"], "TASK", "Y")
        canvas.add_edge(c["canvas_id"], n1["node_id"], n2["node_id"])
        canvas.remove_node(c["canvas_id"], n1["node_id"])
        data = canvas.get_canvas(c["canvas_id"])
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["label"] == "Y"

    def test_removes_connected_edges(self, canvas):
        c = canvas.create_canvas("Edge Cleanup")
        n1 = canvas.add_node(c["canvas_id"], "TASK", "A")
        n2 = canvas.add_node(c["canvas_id"], "TASK", "B")
        n3 = canvas.add_node(c["canvas_id"], "TASK", "C")
        canvas.add_edge(c["canvas_id"], n1["node_id"], n2["node_id"])
        canvas.add_edge(c["canvas_id"], n2["node_id"], n3["node_id"])
        canvas.remove_node(c["canvas_id"], n2["node_id"])
        data = canvas.get_canvas(c["canvas_id"])
        assert len(data["edges"]) == 0

    def test_remove_only_node(self, canvas):
        c = canvas.create_canvas("Single")
        n = canvas.add_node(c["canvas_id"], "TASK", "Solo")
        canvas.remove_node(c["canvas_id"], n["node_id"])
        data = canvas.get_canvas(c["canvas_id"])
        assert len(data["nodes"]) == 0

    def test_remove_nonexistent_node(self, canvas):
        c = canvas.create_canvas("Test")
        result = canvas.remove_node(c["canvas_id"], "nonexistent")
        assert result["removed"] is True


# ---------------------------------------------------------------------------
# Remove edge
# ---------------------------------------------------------------------------

class TestRemoveEdge:
    def test_basic(self, canvas):
        c = canvas.create_canvas("Remove Edge")
        n1 = canvas.add_node(c["canvas_id"], "TASK", "A")
        n2 = canvas.add_node(c["canvas_id"], "TASK", "B")
        edge = canvas.add_edge(c["canvas_id"], n1["node_id"], n2["node_id"])
        canvas.remove_edge(c["canvas_id"], edge["edge_id"])
        data = canvas.get_canvas(c["canvas_id"])
        assert len(data["edges"]) == 0
        assert len(data["nodes"]) == 2


# ---------------------------------------------------------------------------
# Validate DAG
# ---------------------------------------------------------------------------

class TestValidateDAG:
    def test_valid_linear(self, canvas):
        cid, _ = _build_linear_chain(canvas, 3)
        result = canvas.validate_dag(cid)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_valid_branching(self, canvas):
        c = canvas.create_canvas("Branch")
        root = canvas.add_node(c["canvas_id"], "TASK", "Root")
        left = canvas.add_node(c["canvas_id"], "TASK", "Left")
        right = canvas.add_node(c["canvas_id"], "TASK", "Right")
        canvas.add_edge(c["canvas_id"], root["node_id"], left["node_id"])
        canvas.add_edge(c["canvas_id"], root["node_id"], right["node_id"])
        result = canvas.validate_dag(c["canvas_id"])
        assert result["valid"] is True

    def test_cycle_detected(self, canvas):
        c = canvas.create_canvas("Cycle")
        n1 = canvas.add_node(c["canvas_id"], "TASK", "A")
        n2 = canvas.add_node(c["canvas_id"], "TASK", "B")
        n3 = canvas.add_node(c["canvas_id"], "TASK", "C")
        canvas.add_edge(c["canvas_id"], n1["node_id"], n2["node_id"])
        canvas.add_edge(c["canvas_id"], n2["node_id"], n3["node_id"])
        canvas.add_edge(c["canvas_id"], n3["node_id"], n1["node_id"])
        result = canvas.validate_dag(c["canvas_id"])
        assert result["valid"] is False
        assert any("cycle" in e for e in result["errors"])

    def test_empty_canvas(self, canvas):
        c = canvas.create_canvas("Empty")
        result = canvas.validate_dag(c["canvas_id"])
        assert result["valid"] is False
        assert "empty canvas" in result["errors"]

    def test_single_node_valid(self, canvas):
        c = canvas.create_canvas("Single")
        canvas.add_node(c["canvas_id"], "TASK", "Only")
        result = canvas.validate_dag(c["canvas_id"])
        assert result["valid"] is True

    def test_orphan_nodes_detected(self, canvas):
        c = canvas.create_canvas("Orphans")
        n1 = canvas.add_node(c["canvas_id"], "TASK", "Connected")
        n2 = canvas.add_node(c["canvas_id"], "TASK", "Connected2")
        canvas.add_node(c["canvas_id"], "TASK", "Orphan")
        canvas.add_edge(c["canvas_id"], n1["node_id"], n2["node_id"])
        result = canvas.validate_dag(c["canvas_id"])
        assert result["valid"] is False
        assert any("orphan" in e for e in result["errors"])

    def test_updates_canvas_status_valid(self, canvas):
        cid, _ = _build_linear_chain(canvas, 3)
        canvas.validate_dag(cid)
        data = canvas.get_canvas(cid)
        assert data["status"] == "VALID"

    def test_updates_canvas_status_invalid(self, canvas):
        c = canvas.create_canvas("Cycle")
        n1 = canvas.add_node(c["canvas_id"], "TASK", "A")
        n2 = canvas.add_node(c["canvas_id"], "TASK", "B")
        canvas.add_edge(c["canvas_id"], n1["node_id"], n2["node_id"])
        canvas.add_edge(c["canvas_id"], n2["node_id"], n1["node_id"])
        canvas.validate_dag(c["canvas_id"])
        data = canvas.get_canvas(c["canvas_id"])
        assert data["status"] == "INVALID"


# ---------------------------------------------------------------------------
# Get canvas
# ---------------------------------------------------------------------------

class TestGetCanvas:
    def test_found(self, canvas):
        c = canvas.create_canvas("Test")
        data = canvas.get_canvas(c["canvas_id"])
        assert data is not None
        assert data["name"] == "Test"
        assert data["nodes"] == []
        assert data["edges"] == []

    def test_not_found(self, canvas):
        assert canvas.get_canvas("nonexistent") is None

    def test_metadata_parsed(self, canvas):
        c = canvas.create_canvas("Test")
        canvas.add_node(c["canvas_id"], "TASK", "N", metadata={"key": "val"})
        data = canvas.get_canvas(c["canvas_id"])
        assert data["nodes"][0]["metadata"] == {"key": "val"}


# ---------------------------------------------------------------------------
# List canvases
# ---------------------------------------------------------------------------

class TestListCanvases:
    def test_list_all(self, canvas):
        canvas.create_canvas("A")
        canvas.create_canvas("B")
        assert len(canvas.list_canvases()) == 2

    def test_list_by_status(self, canvas):
        canvas.create_canvas("Draft1")
        cid, _ = _build_linear_chain(canvas, 2)
        canvas.validate_dag(cid)
        drafts = canvas.list_canvases(status="DRAFT")
        valid = canvas.list_canvases(status="VALID")
        assert len(drafts) >= 1
        assert len(valid) == 1

    def test_list_limit(self, canvas):
        for i in range(10):
            canvas.create_canvas(f"C{i}")
        assert len(canvas.list_canvases(limit=3)) == 3


# ---------------------------------------------------------------------------
# DAG projection
# ---------------------------------------------------------------------------

class TestDagProjection:
    def test_basic(self, canvas):
        c = canvas.create_canvas("DAG Proj")
        n1 = canvas.add_node(c["canvas_id"], "TASK", "A")
        n2 = canvas.add_node(c["canvas_id"], "GATE", "G1")
        canvas.add_edge(c["canvas_id"], n1["node_id"], n2["node_id"], "CONDITIONAL")
        dag = canvas.get_dag_projection(c["canvas_id"])
        assert dag is not None
        assert len(dag["nodes"]) == 2
        assert n1["node_id"] in dag["adjacency"]
        assert dag["adjacency"][n1["node_id"]][0]["type"] == "CONDITIONAL"

    def test_nonexistent_canvas(self, canvas):
        assert canvas.get_dag_projection("nonexistent") is None

    def test_empty_canvas_projection(self, canvas):
        c = canvas.create_canvas("Empty")
        dag = canvas.get_dag_projection(c["canvas_id"])
        assert dag["nodes"] == {}
        assert dag["adjacency"] == {}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_empty(self, canvas):
        stats = canvas.get_stats()
        assert stats["total_canvases"] == 0
        assert stats["total_nodes"] == 0
        assert stats["total_edges"] == 0
        assert stats["by_status"] == {}

    def test_with_data(self, canvas):
        c = canvas.create_canvas("Stats")
        canvas.add_node(c["canvas_id"], "TASK", "T1")
        canvas.add_node(c["canvas_id"], "TASK", "T2")
        canvas.add_edge(c["canvas_id"], "id1", "id2")
        stats = canvas.get_stats()
        assert stats["total_canvases"] >= 1
        assert stats["total_nodes"] >= 2
        assert stats["total_edges"] >= 1


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

class TestEventEmission:
    def test_create_emits(self, canvas_with_events):
        canvas, events = canvas_with_events
        canvas.create_canvas("Test")
        assert any("canvas_created" in e.topic for e in events)

    def test_add_node_emits(self, canvas_with_events):
        canvas, events = canvas_with_events
        c = canvas.create_canvas("Test")
        canvas.add_node(c["canvas_id"], "TASK", "N")
        assert any("node_added" in e.topic for e in events)

    def test_add_edge_emits(self, canvas_with_events):
        canvas, events = canvas_with_events
        c = canvas.create_canvas("Test")
        n1 = canvas.add_node(c["canvas_id"], "TASK", "A")
        n2 = canvas.add_node(c["canvas_id"], "TASK", "B")
        canvas.add_edge(c["canvas_id"], n1["node_id"], n2["node_id"])
        assert any("edge_added" in e.topic for e in events)

    def test_remove_node_emits(self, canvas_with_events):
        canvas, events = canvas_with_events
        c = canvas.create_canvas("Test")
        n = canvas.add_node(c["canvas_id"], "TASK", "X")
        canvas.remove_node(c["canvas_id"], n["node_id"])
        assert any("node_removed" in e.topic for e in events)

    def test_no_event_bus_no_crash(self, canvas):
        c = canvas.create_canvas("Test")
        canvas.add_node(c["canvas_id"], "TASK", "N")


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_get_returns_same(self):
        p1 = get_process_canvas()
        p2 = get_process_canvas()
        assert p1 is p2


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_canvas_creation(self, canvas):
        errors = []
        results = []

        def create(idx):
            try:
                r = canvas.create_canvas(f"Canvas-{idx}")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert canvas.get_stats()["total_canvases"] == 10

    def test_concurrent_node_addition(self, canvas):
        errors = []
        c = canvas.create_canvas("Concurrent")

        def add_node(idx):
            try:
                canvas.add_node(c["canvas_id"], "TASK", f"N{idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_node, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        data = canvas.get_canvas(c["canvas_id"])
        assert len(data["nodes"]) == 20
