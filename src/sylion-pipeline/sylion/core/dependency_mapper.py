"""
SYLION Core -- Dependency Mapper

Maps and analyzes dependencies between modules using the contract registry.
Detects circular dependencies, computes transitive graphs via BFS,
and stores dependency snapshots for later analysis.

Tables:
  dependency_edges  -- individual from->to edges with type and strength
  dependency_graphs  -- BFS-computed graphs stored as JSON snapshots

Events:
  dependency.cycle_detected  -- emitted when detect_cycles() finds cycles

gRPC planned: AddEdge, RemoveEdge, ComputeGraph, DetectCycles, GetStats
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.core.dependency_mapper")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_DEPENDENCY_TYPES = ("direct", "transitive", "optional", "runtime", "build")


class DependencyMapper:
    """Maps and analyses inter-module dependencies. SQLite-backed. Thread-safe."""

    def __init__(self, db_path: str | Path | None = None, event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS dependency_edges (
                edge_id         TEXT PRIMARY KEY,
                from_module     TEXT NOT NULL,
                to_module       TEXT NOT NULL,
                dependency_type TEXT NOT NULL,
                contract_name   TEXT NOT NULL DEFAULT '',
                strength        REAL NOT NULL DEFAULT 1.0,
                detected_at     REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_dep_edges_from
                ON dependency_edges(from_module)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_dep_edges_to
                ON dependency_edges(to_module)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_dep_edges_type
                ON dependency_edges(dependency_type)
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS dependency_graphs (
                graph_id    TEXT PRIMARY KEY,
                root_module TEXT NOT NULL,
                depth       INTEGER NOT NULL,
                node_count  INTEGER NOT NULL,
                edge_count  INTEGER NOT NULL,
                computed_at REAL NOT NULL,
                snapshot    TEXT NOT NULL DEFAULT '{}'
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_dep_graphs_root
                ON dependency_graphs(root_module)
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Edge CRUD
    # ------------------------------------------------------------------

    def add_edge(
        self,
        from_module: str,
        to_module: str,
        dependency_type: str = "direct",
        contract_name: str = "",
        strength: float = 1.0,
    ) -> dict:
        """Add a dependency edge. Returns the edge record as a dict."""
        if dependency_type not in VALID_DEPENDENCY_TYPES:
            raise ValueError(
                f"Invalid dependency_type '{dependency_type}'. "
                f"Must be one of {VALID_DEPENDENCY_TYPES}"
            )
        if strength < 0 or strength > 1.0:
            raise ValueError("strength must be between 0.0 and 1.0")
        if not from_module or not to_module:
            raise ValueError("from_module and to_module must be non-empty")

        edge_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO dependency_edges
                    (edge_id, from_module, to_module, dependency_type,
                     contract_name, strength, detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                edge_id, from_module, to_module, dependency_type,
                contract_name, strength, now,
            ))
            self._conn.commit()

        log.info("added edge %s -> %s (%s)", from_module, to_module, dependency_type)
        return {
            "edge_id": edge_id,
            "from_module": from_module,
            "to_module": to_module,
            "dependency_type": dependency_type,
            "contract_name": contract_name,
            "strength": strength,
            "detected_at": now,
        }

    def remove_edge(self, edge_id: str) -> bool:
        """Remove a dependency edge by edge_id. Returns True if found."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM dependency_edges WHERE edge_id = ?",
                (edge_id,),
            ).rowcount
            self._conn.commit()
        if n:
            log.info("removed edge %s", edge_id)
        return bool(n)

    def list_edges(
        self,
        from_module: str | None = None,
        to_module: str | None = None,
        dependency_type: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        """List edges with optional filters."""
        q = "SELECT * FROM dependency_edges WHERE 1=1"
        params: list[Any] = []
        if from_module:
            q += " AND from_module = ?"
            params.append(from_module)
        if to_module:
            q += " AND to_module = ?"
            params.append(to_module)
        if dependency_type:
            q += " AND dependency_type = ?"
            params.append(dependency_type)
        q += " ORDER BY detected_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Dependency queries
    # ------------------------------------------------------------------

    def get_dependents(self, module_id: str) -> list[dict]:
        """Get all modules that depend on *module_id* (i.e. from_module -> module_id)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM dependency_edges WHERE to_module = ? ORDER BY detected_at DESC",
                (module_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_dependencies(self, module_id: str) -> list[dict]:
        """Get all modules that *module_id* depends on (i.e. module_id -> to_module)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM dependency_edges WHERE from_module = ? ORDER BY detected_at DESC",
                (module_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Graph computation (BFS)
    # ------------------------------------------------------------------

    def compute_graph(self, root_module: str, depth: int = 3) -> dict:
        """Compute dependency graph from *root_module* using BFS up to *depth*.

        Returns dict with graph_id, node_count, edge_count, nodes, edges.
        Also stores the graph as a JSON snapshot in dependency_graphs.
        """
        graph_id = uuid.uuid4().hex
        now = time.time()

        nodes: set[str] = set()
        edges: list[dict] = []
        visited_edges: set[str] = set()

        # Load all edges into memory for BFS
        with self._lock:
            all_rows = self._conn.execute(
                "SELECT * FROM dependency_edges"
            ).fetchall()
        adj: dict[str, list[dict]] = {}
        for r in all_rows:
            fm = r["from_module"]
            adj.setdefault(fm, []).append(dict(r))

        # BFS
        queue: deque[tuple[str, int]] = deque()
        queue.append((root_module, 0))
        visited_nodes: set[str] = set()

        while queue:
            current, current_depth = queue.popleft()
            if current in visited_nodes:
                continue
            visited_nodes.add(current)
            nodes.add(current)

            if current_depth >= depth:
                continue

            for edge in adj.get(current, []):
                edge_key = edge["edge_id"]
                if edge_key not in visited_edges:
                    visited_edges.add(edge_key)
                    edges.append(edge)
                    target = edge["to_module"]
                    if target not in visited_nodes:
                        queue.append((target, current_depth + 1))

        snapshot = json.dumps({
            "root_module": root_module,
            "depth": depth,
            "nodes": sorted(nodes),
            "edges": edges,
        }, default=str)

        node_count = len(nodes)
        edge_count = len(edges)

        with self._lock:
            self._conn.execute("""
                INSERT INTO dependency_graphs
                    (graph_id, root_module, depth, node_count, edge_count,
                     computed_at, snapshot)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (graph_id, root_module, depth, node_count, edge_count, now, snapshot))
            self._conn.commit()

        log.info(
            "computed graph %s from %s (depth=%d, nodes=%d, edges=%d)",
            graph_id, root_module, depth, node_count, edge_count,
        )
        return {
            "graph_id": graph_id,
            "root_module": root_module,
            "depth": depth,
            "node_count": node_count,
            "edge_count": edge_count,
            "nodes": sorted(nodes),
            "edges": edges,
            "computed_at": now,
        }

    def get_graph(self, graph_id: str) -> dict | None:
        """Retrieve a stored graph by graph_id."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM dependency_graphs WHERE graph_id = ?",
                (graph_id,),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["snapshot"] = json.loads(result["snapshot"])
        return result

    def list_graphs(
        self,
        root_module: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List stored graphs with optional root_module filter."""
        q = "SELECT * FROM dependency_graphs WHERE 1=1"
        params: list[Any] = []
        if root_module:
            q += " AND root_module = ?"
            params.append(root_module)
        q += " ORDER BY computed_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["snapshot"] = json.loads(d["snapshot"])
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Cycle detection (DFS with 3-colouring)
    # ------------------------------------------------------------------

    def detect_cycles(self) -> list[list[str]]:
        """Find circular dependencies using DFS with 3-colouring.

        Returns a list of cycles, each cycle is a list of module names
        forming the back-edge path. Emits 'dependency.cycle_detected'
        event when cycles are found.
        """
        # Build adjacency list
        with self._lock:
            rows = self._conn.execute(
                "SELECT from_module, to_module FROM dependency_edges"
            ).fetchall()

        adj: dict[str, list[str]] = {}
        for r in rows:
            adj.setdefault(r["from_module"], []).append(r["to_module"])
            # Ensure all modules appear as keys
            adj.setdefault(r["to_module"], [])

        WHITE, GRAY, BLACK = 0, 1, 2
        colour: dict[str, int] = {m: WHITE for m in adj}
        parent: dict[str, str | None] = {m: None for m in adj}
        cycles: list[list[str]] = []

        def _dfs(u: str):
            colour[u] = GRAY
            for v in adj.get(u, []):
                if colour.get(v) == GRAY:
                    # Back edge found -- reconstruct cycle
                    cycle = [v, u]
                    cur = u
                    while parent.get(cur) is not None and parent[cur] != v:
                        cur = parent[cur]
                        cycle.append(cur)
                    # Only keep the actual cycle portion
                    cycle.reverse()
                    cycles.append(cycle)
                elif colour.get(v) == WHITE:
                    parent[v] = u
                    _dfs(v)
            colour[u] = BLACK

        for module_id in list(adj.keys()):
            if colour[module_id] == WHITE:
                _dfs(module_id)

        if cycles and self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic="dependency.cycle_detected",
                payload={
                    "cycle_count": len(cycles),
                    "cycles": cycles,
                },
                source_module="core.dependency_mapper",
            ))

        if cycles:
            log.warning("detected %d cycle(s): %s", len(cycles), cycles)
        return cycles

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about the dependency map."""
        with self._lock:
            edge_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM dependency_edges"
            ).fetchone()["cnt"]

            graph_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM dependency_graphs"
            ).fetchone()["cnt"]

            # Distinct modules
            modules = self._conn.execute("""
                SELECT COUNT(DISTINCT m) as cnt FROM (
                    SELECT from_module AS m FROM dependency_edges
                    UNION
                    SELECT to_module AS m FROM dependency_edges
                )
            """).fetchone()["cnt"]

            # By type
            type_rows = self._conn.execute(
                "SELECT dependency_type, COUNT(*) as cnt FROM dependency_edges "
                "GROUP BY dependency_type ORDER BY cnt DESC"
            ).fetchall()
            by_type = {r["dependency_type"]: r["cnt"] for r in type_rows}

            # Average strength
            avg_row = self._conn.execute(
                "SELECT AVG(strength) as avg_s FROM dependency_edges"
            ).fetchone()
            avg_strength = avg_row["avg_s"] if avg_row["avg_s"] is not None else 0.0

        return {
            "total_edges": edge_count,
            "total_graphs": graph_count,
            "distinct_modules": modules,
            "by_type": by_type,
            "avg_strength": round(avg_strength, 4),
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_mapper: DependencyMapper | None = None


def get_dependency_mapper(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> DependencyMapper:
    global _mapper
    if _mapper is None:
        _mapper = DependencyMapper(db_path, event_bus)
    return _mapper


def reset_dependency_mapper() -> None:
    global _mapper
    _mapper = None
