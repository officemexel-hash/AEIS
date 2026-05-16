"""
SYLION Contracts -- Dependency Graph

Tracks inter-module dependencies with cycle detection, topological sorting,
impact analysis, and validation.  SQLite-backed with WAL mode, thread-safe
via threading.Lock, singleton pattern.

Event emissions:
  - contracts.dependency.added    -- new dependency edge registered
  - contracts.dependency.removed  -- dependency edge removed
  - contracts.dependency.cycle    -- cycle detected during operation
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from typing import Any

log = logging.getLogger("sylion.contracts.dependency_graph")


class DependencyGraph:
    """Directed graph of inter-module dependencies backed by SQLite.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  ``":memory:"`` for transient
        in-memory graphs (default, ideal for tests).
    event_bus:
        Optional :class:`EventBus` instance for publishing lifecycle events.
    """

    def __init__(self, db_path: str = ":memory:", event_bus: Any = None):
        self._db_path = str(db_path)
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sylion_dependencies (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id   TEXT    NOT NULL,
                depends_on  TEXT    NOT NULL,
                type        TEXT    NOT NULL DEFAULT 'hard',
                UNIQUE(module_id, depends_on)
            );
            CREATE INDEX IF NOT EXISTS idx_dep_module
                ON sylion_dependencies(module_id);
            CREATE INDEX IF NOT EXISTS idx_dep_target
                ON sylion_dependencies(depends_on);
            CREATE INDEX IF NOT EXISTS idx_dep_type
                ON sylion_dependencies(type);
        """)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict[str, Any]):
        """Emit an event through the EventBus if available."""
        if self._event_bus is not None:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="contracts.dependency_graph",
            ))

    def _all_edges(self) -> list[tuple[str, str, str]]:
        """Return all (module_id, depends_on, type) tuples."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT module_id, depends_on, type FROM sylion_dependencies"
            ).fetchall()
        return [(r["module_id"], r["depends_on"], r["type"]) for r in rows]

    @staticmethod
    def _build_adjacency(
        edges: list[tuple[str, str, str]],
    ) -> dict[str, list[str]]:
        """Build forward adjacency list from edges (module -> its dependencies)."""
        adj: dict[str, list[str]] = {}
        for src, dst, _ in edges:
            adj.setdefault(src, []).append(dst)
            adj.setdefault(dst, [])  # ensure target node exists
        return adj

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_dependency(
        self, module_id: str, depends_on: str, type: str = "hard"
    ) -> bool:
        """Register a dependency edge.

        Returns ``True`` if the edge was inserted, ``False`` if it already
        existed.
        """
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO sylion_dependencies (module_id, depends_on, type) "
                    "VALUES (?, ?, ?)",
                    (module_id, depends_on, type),
                )
                self._conn.commit()
            except sqlite3.IntegrityError:
                return False

        self._emit("contracts.dependency.added", {
            "module_id": module_id,
            "depends_on": depends_on,
            "type": type,
        })
        return True

    def remove_dependency(self, module_id: str, depends_on: str) -> bool:
        """Remove a dependency edge.

        Returns ``True`` if a row was deleted, ``False`` otherwise.
        """
        with self._lock:
            deleted = self._conn.execute(
                "DELETE FROM sylion_dependencies "
                "WHERE module_id=? AND depends_on=?",
                (module_id, depends_on),
            ).rowcount
            self._conn.commit()

        if deleted:
            self._emit("contracts.dependency.removed", {
                "module_id": module_id,
                "depends_on": depends_on,
            })
        return bool(deleted)

    def get_dependencies(
        self, module_id: str, transitive: bool = False
    ) -> list[str]:
        """Return direct (default) or transitive dependencies of *module_id*.

        Transitive resolution follows the full closure using BFS, stopping
        when a cycle would be re-entered.
        """
        if not transitive:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT depends_on FROM sylion_dependencies "
                    "WHERE module_id=? ORDER BY depends_on",
                    (module_id,),
                ).fetchall()
            return [r["depends_on"] for r in rows]

        # Transitive closure via BFS
        adj = self._build_adjacency(self._all_edges())
        visited: set[str] = set()
        queue: list[str] = list(adj.get(module_id, []))
        result: list[str] = []

        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            result.append(node)
            for child in adj.get(node, []):
                if child not in visited:
                    queue.append(child)

        return sorted(result)

    def get_dependents(self, module_id: str) -> list[str]:
        """Return modules that depend on *module_id* (reverse edges)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT module_id FROM sylion_dependencies "
                "WHERE depends_on=? ORDER BY module_id",
                (module_id,),
            ).fetchall()
        return [r["module_id"] for r in rows]

    def detect_cycles(self) -> list[list[str]]:
        """Detect circular dependencies.

        Returns a list of cycles, where each cycle is a list of module IDs
        forming the loop (e.g. ``[A, B, C]`` means A -> B -> C -> A).
        """
        adj = self._build_adjacency(self._all_edges())
        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles: list[list[str]] = []

        def _dfs(node: str, path: list[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    _dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # Found cycle — extract the cycle from path
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.discard(node)

        for node in list(adj.keys()):
            if node not in visited:
                _dfs(node, [])

        return cycles

    def topological_sort(self) -> list[str]:
        """Return all known modules in dependency order (Kahn's algorithm).

        Modules with no dependencies come first.  If cycles exist they are
        appended at the end in arbitrary order.

        Returns
        -------
        list[str]
            Module IDs in topological order.
        """
        edges = self._all_edges()
        adj = self._build_adjacency(edges)

        # Build reverse adjacency for in-degree computation
        in_degree: dict[str, int] = {n: 0 for n in adj}
        reverse: dict[str, list[str]] = {n: [] for n in adj}
        for src, dst, _ in edges:
            reverse.setdefault(dst, []).append(src)
            in_degree[src] = in_degree.get(src, 0) + 1

        # Seed with zero in-degree nodes
        queue: list[str] = sorted(
            n for n in in_degree if in_degree[n] == 0
        )
        result: list[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for dependent in sorted(reverse.get(node, [])):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Any remaining nodes are part of cycles — include them anyway
        remaining = sorted(n for n in in_degree if n not in set(result))
        result.extend(remaining)

        return result

    def validate_all(self) -> dict[str, Any]:
        """Check for missing dependencies.

        A dependency is *missing* when *depends_on* references a module that
        is never registered as a *module_id* in any edge.

        Returns
        -------
        dict
            ``{"valid": bool, "missing": list[dict], "cycle_count": int}``
        """
        edges = self._all_edges()
        modules_with_deps: set[str] = set()
        dep_targets: set[str] = set()

        for src, dst, _ in edges:
            modules_with_deps.add(src)
            dep_targets.add(dst)

        # A target is valid if it appears as any module_id in the graph
        all_modules = modules_with_deps | dep_targets
        missing: list[dict[str, str]] = []
        for src, dst, dtype in edges:
            if dst not in modules_with_deps:
                missing.append({
                    "module_id": src,
                    "depends_on": dst,
                    "type": dtype,
                })

        cycles = self.detect_cycles()
        valid = len(missing) == 0 and len(cycles) == 0

        return {
            "valid": valid,
            "missing": missing,
            "cycle_count": len(cycles),
        }

    def get_impact_analysis(self, module_id: str) -> dict[str, Any]:
        """Analyse what would break if *module_id* changes.

        Returns
        -------
        dict
            ``{"module_id": str, "direct_dependents": list[str],
              "transitive_dependents": list[str], "dependency_depth": int,
              "total_impact": int}``
        """
        # Direct dependents (modules that directly depend on module_id)
        direct = self.get_dependents(module_id)

        # Transitive dependents via BFS on reverse edges
        edges = self._all_edges()
        reverse_adj: dict[str, list[str]] = {}
        for src, dst, _ in edges:
            reverse_adj.setdefault(dst, []).append(src)

        visited: set[str] = set()
        queue: list[str] = list(reverse_adj.get(module_id, []))
        transitive: list[str] = []

        depth = 0
        while queue:
            depth += 1
            next_level: list[str] = []
            for node in queue:
                if node in visited:
                    continue
                visited.add(node)
                transitive.append(node)
                for child in reverse_adj.get(node, []):
                    if child not in visited:
                        next_level.append(child)
            queue = next_level

        return {
            "module_id": module_id,
            "direct_dependents": sorted(direct),
            "transitive_dependents": sorted(transitive),
            "dependency_depth": depth,
            "total_impact": len(transitive),
        }

    def get_stats(self) -> dict[str, Any]:
        """Aggregate statistics about the dependency graph.

        Returns
        -------
        dict
            ``{"total_dependencies": int, "by_type": dict[str, int],
              "cycle_count": int, "module_count": int}``
        """
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sylion_dependencies"
            ).fetchone()["cnt"]

            by_type_rows = self._conn.execute(
                "SELECT type, COUNT(*) as cnt FROM sylion_dependencies "
                "GROUP BY type"
            ).fetchall()

            modules = self._conn.execute(
                "SELECT COUNT(DISTINCT module_id) as cnt "
                "FROM sylion_dependencies"
            ).fetchone()["cnt"]

        by_type = {r["type"]: r["cnt"] for r in by_type_rows}
        cycles = self.detect_cycles()

        return {
            "total_dependencies": total,
            "by_type": by_type,
            "cycle_count": len(cycles),
            "module_count": modules,
        }

    def close(self):
        """Close the database connection."""
        self._conn.close()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_graph: DependencyGraph | None = None


def get_dependency_graph(
    db_path: str = ":memory:", event_bus: Any = None
) -> DependencyGraph:
    """Return the global DependencyGraph singleton."""
    global _graph
    if _graph is None:
        _graph = DependencyGraph(db_path=db_path, event_bus=event_bus)
    return _graph
