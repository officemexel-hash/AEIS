"""
SYLION Surface -- Process Canvas

Yjs sync, DAG projection, validation.
Thread-safe. SQLite-backed. Emits events via EventBus.

Frozen decisions:
- Yjs + tldraw, NOT React Flow, NOT locking-based editor
- Yjs is source of truth for Canvas; SQL = projection only
- Two concurrency worlds: Canvas/freeform = CRDT/Yjs;
  Domain changes protected by governance = Command Bus + expected_version
- Do NOT mix freeform canvas fields with governance-protected fields
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.surface.process_canvas")


@dataclass
class CanvasNode:
    node_id: str = ""
    canvas_id: str = ""
    node_type: str = "TASK"
    label: str = ""
    position_x: float = 0.0
    position_y: float = 0.0
    metadata: dict = field(default_factory=dict)
    version: int = 1

    def __post_init__(self):
        if not self.node_id:
            self.node_id = uuid.uuid4().hex


@dataclass
class CanvasEdge:
    edge_id: str = ""
    canvas_id: str = ""
    source_node_id: str = ""
    target_node_id: str = ""
    edge_type: str = "SEQUENCE"
    label: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.edge_id:
            self.edge_id = uuid.uuid4().hex


class ProcessCanvas:
    """DAG canvas with nodes, edges, validation.

    Thread-safe. SQLite-backed (projection only; Yjs is source of truth).
    Emits events to EventBus.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS canvases (
                canvas_id  TEXT PRIMARY KEY,
                name       TEXT NOT NULL DEFAULT '',
                status     TEXT NOT NULL DEFAULT 'DRAFT',
                version    INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS canvas_nodes (
                node_id    TEXT PRIMARY KEY,
                canvas_id  TEXT NOT NULL,
                node_type  TEXT NOT NULL DEFAULT 'TASK',
                label      TEXT NOT NULL DEFAULT '',
                position_x REAL NOT NULL DEFAULT 0,
                position_y REAL NOT NULL DEFAULT 0,
                metadata   TEXT NOT NULL DEFAULT '{}',
                version    INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS canvas_edges (
                edge_id         TEXT PRIMARY KEY,
                canvas_id       TEXT NOT NULL,
                source_node_id  TEXT NOT NULL DEFAULT '',
                target_node_id  TEXT NOT NULL DEFAULT '',
                edge_type       TEXT NOT NULL DEFAULT 'SEQUENCE',
                label           TEXT NOT NULL DEFAULT '',
                metadata        TEXT NOT NULL DEFAULT '{}'
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cn_canvas ON canvas_nodes(canvas_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ce_canvas ON canvas_edges(canvas_id)"
        )
        self._conn.commit()

    def create_canvas(self, name: str) -> dict:
        canvas_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO canvases (canvas_id, name, status, version, created_at, updated_at)
                VALUES (?, ?, 'DRAFT', 1, ?, ?)
            """, (canvas_id, name, now, now))
            self._conn.commit()

        self._emit("surface.process_canvas.canvas_created", {
            "canvas_id": canvas_id, "name": name,
        })

        log.info("created canvas %s: %s", canvas_id[:12], name)
        return {"canvas_id": canvas_id, "name": name, "status": "DRAFT"}

    def add_node(self, canvas_id: str, node_type: str = "TASK",
                 label: str = "", position_x: float = 0.0,
                 position_y: float = 0.0,
                 metadata: dict | None = None) -> dict:
        node = CanvasNode(
            canvas_id=canvas_id,
            node_type=node_type,
            label=label,
            position_x=position_x,
            position_y=position_y,
            metadata=metadata or {},
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO canvas_nodes
                    (node_id, canvas_id, node_type, label,
                     position_x, position_y, metadata, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (node.node_id, canvas_id, node_type, label,
                  position_x, position_y, json.dumps(node.metadata)))
            self._conn.execute("""
                UPDATE canvases SET updated_at = ? WHERE canvas_id = ?
            """, (time.time(), canvas_id))
            self._conn.commit()

        self._emit("surface.process_canvas.node_added", {
            "canvas_id": canvas_id, "node_id": node.node_id,
        })

        log.info("added node %s to canvas %s", node.node_id[:12], canvas_id[:12])
        return {"node_id": node.node_id, "canvas_id": canvas_id}

    def add_edge(self, canvas_id: str, source_node_id: str,
                 target_node_id: str, edge_type: str = "SEQUENCE",
                 label: str = "") -> dict:
        edge = CanvasEdge(
            canvas_id=canvas_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            label=label,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO canvas_edges
                    (edge_id, canvas_id, source_node_id, target_node_id,
                     edge_type, label, metadata)
                VALUES (?, ?, ?, ?, ?, ?, '{}')
            """, (edge.edge_id, canvas_id, source_node_id,
                  target_node_id, edge_type, label))
            self._conn.execute("""
                UPDATE canvases SET updated_at = ? WHERE canvas_id = ?
            """, (time.time(), canvas_id))
            self._conn.commit()

        self._emit("surface.process_canvas.edge_added", {
            "canvas_id": canvas_id, "edge_id": edge.edge_id,
        })

        log.info("added edge %s -> %s in canvas %s",
                 source_node_id[:8], target_node_id[:8], canvas_id[:8])
        return {"edge_id": edge.edge_id, "canvas_id": canvas_id}

    def remove_node(self, canvas_id: str, node_id: str) -> dict:
        with self._lock:
            self._conn.execute(
                "DELETE FROM canvas_edges WHERE canvas_id = ? AND (source_node_id = ? OR target_node_id = ?)",
                (canvas_id, node_id, node_id),
            )
            self._conn.execute(
                "DELETE FROM canvas_nodes WHERE canvas_id = ? AND node_id = ?",
                (canvas_id, node_id),
            )
            self._conn.execute(
                "UPDATE canvases SET updated_at = ? WHERE canvas_id = ?",
                (time.time(), canvas_id),
            )
            self._conn.commit()

        self._emit("surface.process_canvas.node_removed", {
            "canvas_id": canvas_id, "node_id": node_id,
        })

        log.info("removed node %s from canvas %s", node_id[:12], canvas_id[:12])
        return {"removed": True, "node_id": node_id}

    def remove_edge(self, canvas_id: str, edge_id: str) -> dict:
        with self._lock:
            self._conn.execute(
                "DELETE FROM canvas_edges WHERE canvas_id = ? AND edge_id = ?",
                (canvas_id, edge_id),
            )
            self._conn.execute(
                "UPDATE canvases SET updated_at = ? WHERE canvas_id = ?",
                (time.time(), canvas_id),
            )
            self._conn.commit()

        return {"removed": True, "edge_id": edge_id}

    def validate_dag(self, canvas_id: str) -> dict:
        """Validate DAG: no cycles, no orphans, proper structure."""
        nodes = self._conn.execute(
            "SELECT node_id FROM canvas_nodes WHERE canvas_id = ?",
            (canvas_id,),
        ).fetchall()
        edges = self._conn.execute(
            "SELECT source_node_id, target_node_id FROM canvas_edges WHERE canvas_id = ?",
            (canvas_id,),
        ).fetchall()

        node_ids = {r["node_id"] for r in nodes}
        errors = []

        if not node_ids:
            return {"valid": False, "errors": ["empty canvas"], "canvas_id": canvas_id}

        # Check orphans (nodes with no edges)
        connected = set()
        for e in edges:
            connected.add(e["source_node_id"])
            connected.add(e["target_node_id"])
        orphans = node_ids - connected
        if orphans and len(node_ids) > 1:
            errors.append(f"orphan nodes: {[n[:8] for n in orphans]}")

        # Check for cycles (DFS)
        adj = {nid: [] for nid in node_ids}
        for e in edges:
            if e["source_node_id"] in adj:
                adj[e["source_node_id"]].append(e["target_node_id"])

        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for nid in node_ids:
            if nid not in visited:
                if has_cycle(nid):
                    errors.append("cycle detected")
                    break

        # Check dangling edge references
        for e in edges:
            if e["source_node_id"] not in node_ids:
                errors.append(f"edge references missing source: {e['source_node_id'][:8]}")
            if e["target_node_id"] not in node_ids:
                errors.append(f"edge references missing target: {e['target_node_id'][:8]}")

        valid = len(errors) == 0

        with self._lock:
            self._conn.execute(
                "UPDATE canvases SET status = ? WHERE canvas_id = ?",
                ("VALID" if valid else "INVALID", canvas_id),
            )
            self._conn.commit()

        return {"valid": valid, "errors": errors, "canvas_id": canvas_id}

    def get_canvas(self, canvas_id: str) -> dict | None:
        canvas = self._conn.execute(
            "SELECT * FROM canvases WHERE canvas_id = ?", (canvas_id,),
        ).fetchone()
        if not canvas:
            return None

        nodes = self._conn.execute(
            "SELECT * FROM canvas_nodes WHERE canvas_id = ?", (canvas_id,),
        ).fetchall()
        edges = self._conn.execute(
            "SELECT * FROM canvas_edges WHERE canvas_id = ?", (canvas_id,),
        ).fetchall()

        result = dict(canvas)
        result["nodes"] = []
        for n in nodes:
            d = dict(n)
            d["metadata"] = json.loads(d.get("metadata", "{}"))
            result["nodes"].append(d)
        result["edges"] = []
        for e in edges:
            d = dict(e)
            d["metadata"] = json.loads(d.get("metadata", "{}"))
            result["edges"].append(d)
        return result

    def list_canvases(self, status: str | None = None,
                      limit: int = 100) -> list[dict]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM canvases WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM canvases ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_dag_projection(self, canvas_id: str) -> dict | None:
        """Return DAG structure as adjacency list."""
        canvas = self.get_canvas(canvas_id)
        if not canvas:
            return None

        nodes = {n["node_id"]: {
            "label": n["label"], "type": n["node_type"],
        } for n in canvas["nodes"]}

        adjacency = {nid: [] for nid in nodes}
        for e in canvas["edges"]:
            if e["source_node_id"] in adjacency:
                adjacency[e["source_node_id"]].append({
                    "target": e["target_node_id"],
                    "type": e["edge_type"],
                    "label": e["label"],
                })

        return {
            "canvas_id": canvas_id,
            "status": canvas["status"],
            "nodes": nodes,
            "adjacency": adjacency,
        }

    def get_stats(self) -> dict:
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM canvases"
        ).fetchone()["cnt"]
        by_status = {r["status"]: r["cnt"] for r in self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM canvases GROUP BY status"
        ).fetchall()}
        total_nodes = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM canvas_nodes"
        ).fetchone()["cnt"]
        total_edges = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM canvas_edges"
        ).fetchone()["cnt"]
        return {
            "total_canvases": total,
            "by_status": by_status,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
        }

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="surface.process_canvas",
            ))


_canvas: ProcessCanvas | None = None


def get_process_canvas(db_path: str | Path | None = None,
                       event_bus: EventBus | None = None) -> ProcessCanvas:
    global _canvas
    if _canvas is None:
        _canvas = ProcessCanvas(db_path, event_bus)
    return _canvas
