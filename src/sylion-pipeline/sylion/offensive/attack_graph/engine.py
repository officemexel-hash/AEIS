"""
Attack Graph Engine

Core capabilities:
- Add/remove nodes & edges
- Shortest path (weighted composite cost)
- Stealthiest path (minimize cumulative stealth + detection)
- Highest-value path (maximize value / minimize cost)
- Detection prediction along a path
- Loop detection / cycle breaking
- Subgraph extraction (e.g., from Identity to Asset class)
"""
from __future__ import annotations

import heapq
import logging
from collections import defaultdict
from typing import Callable

from .models import AttackEdge, AttackNode, AttackPath, EdgeType, NodeType

log = logging.getLogger("sylion.offensive.attack_graph")


class AttackGraphEngine:
    def __init__(self):
        self._nodes: dict[str, AttackNode] = {}
        self._edges: dict[str, AttackEdge] = {}
        self._adj: dict[str, list[str]] = defaultdict(list)  # node_id -> [edge_id, ...]
        self._rev: dict[str, list[str]] = defaultdict(list)  # reverse adjacency

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def add_node(self, node: AttackNode) -> str:
        if not node.node_id:
            node.node_id = node.node_id or "n_" + hex(hash(node.label))[2:10]
        self._nodes[node.node_id] = node
        log.debug("added node %s (%s)", node.node_id, node.node_type.value)
        return node.node_id

    def add_edge(self, edge: AttackEdge) -> str:
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            raise ValueError("source or target node missing")
        self._edges[edge.edge_id] = edge
        self._adj[edge.source_id].append(edge.edge_id)
        self._rev[edge.target_id].append(edge.edge_id)
        log.debug("added edge %s (%s -> %s)", edge.edge_id, edge.source_id, edge.target_id)
        return edge.edge_id

    def remove_node(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        for eid in list(self._adj[node_id]) + list(self._rev[node_id]):
            self.remove_edge(eid)
        del self._nodes[node_id]
        del self._adj[node_id]
        del self._rev[node_id]
        return True

    def remove_edge(self, edge_id: str) -> bool:
        edge = self._edges.pop(edge_id, None)
        if not edge:
            return False
        self._adj[edge.source_id].remove(edge_id)
        self._rev[edge.target_id].remove(edge_id)
        return True

    def get_node(self, node_id: str) -> AttackNode | None:
        return self._nodes.get(node_id)

    def get_edge(self, edge_id: str) -> AttackEdge | None:
        return self._edges.get(edge_id)

    def nodes_by_type(self, node_type: NodeType) -> list[AttackNode]:
        return [n for n in self._nodes.values() if n.node_type == node_type]

    def all_paths_to(self, target_type: NodeType, source_type: NodeType | None = None) -> list[AttackPath]:
        """Enumerate all simple paths from any source_type node to any target_type node.
        Bounded to avoid combinatorial explosion."""
        targets = [n.node_id for n in self.nodes_by_type(target_type)]
        sources = ([n.node_id for n in self.nodes_by_type(source_type)]
                   if source_type else list(self._nodes.keys()))
        paths: list[AttackPath] = []
        max_paths_per_pair = 50
        max_depth = 12
        for src in sources:
            for tgt in targets:
                if src == tgt:
                    continue
                found = self._dfs_paths(src, tgt, max_depth)
                for node_list in found[:max_paths_per_pair]:
                    paths.append(self._build_path(node_list))
        return paths

    def _dfs_paths(self, src: str, tgt: str, max_depth: int) -> list[list[str]]:
        result: list[list[str]] = []
        stack = [(src, [src])]
        while stack:
            current, path = stack.pop()
            if current == tgt:
                result.append(path)
                continue
            if len(path) >= max_depth:
                continue
            for eid in self._adj[current]:
                edge = self._edges[eid]
                nxt = edge.target_id
                if nxt not in path:  # simple path, no cycles
                    stack.append((nxt, path + [nxt]))
        return result

    def _build_path(self, node_ids: list[str]) -> AttackPath:
        edges: list[str] = []
        total_cost = 0.0
        total_stealth = 0.0
        total_detection = 0.0
        success_prob = 1.0
        for i in range(len(node_ids) - 1):
            # find edge
            eid = None
            for cand in self._adj[node_ids[i]]:
                if self._edges[cand].target_id == node_ids[i + 1]:
                    eid = cand
                    break
            if not eid:
                continue
            edge = self._edges[eid]
            edges.append(eid)
            src_node = self._nodes[node_ids[i]]
            tgt_node = self._nodes[node_ids[i + 1]]
            total_cost += edge.weight + tgt_node.composite_cost()
            total_stealth += edge.stealth_cost + tgt_node.stealth_footprint
            total_detection = max(total_detection, tgt_node.detection_prob)
            success_prob *= edge.success_prob
        return AttackPath(
            nodes=node_ids,
            edges=edges,
            total_cost=round(total_cost, 4),
            total_stealth=round(total_stealth, 4),
            total_detection=round(total_detection, 4),
            success_probability=round(success_prob, 4),
            estimated_time_sec=len(node_ids) * 30.0,
        )

    # ------------------------------------------------------------------ #
    # AI Pathfinders
    # ------------------------------------------------------------------ #
    def shortest_path(self, source_id: str, target_id: str,
                      cost_fn: Callable[[AttackEdge, AttackNode], float] | None = None) -> AttackPath | None:
        """Dijkstra. Default cost = edge.weight + target.composite_cost()."""
        if cost_fn is None:
            def cost_fn(edge, target_node):
                return edge.weight + target_node.composite_cost()

        dist: dict[str, float] = {n: float("inf") for n in self._nodes}
        prev: dict[str, str | None] = {n: None for n in self._nodes}
        prev_edge: dict[str, str | None] = {n: None for n in self._nodes}
        dist[source_id] = 0.0
        heap = [(0.0, source_id)]
        visited = set()

        while heap:
            d, u = heapq.heappop(heap)
            if u in visited:
                continue
            visited.add(u)
            if u == target_id:
                break
            for eid in self._adj[u]:
                edge = self._edges[eid]
                v = edge.target_id
                if v in visited:
                    continue
                w = cost_fn(edge, self._nodes[v])
                if d + w < dist[v]:
                    dist[v] = d + w
                    prev[v] = u
                    prev_edge[v] = eid
                    heapq.heappush(heap, (dist[v], v))

        if prev[target_id] is None and source_id != target_id:
            return None

        # reconstruct
        node_ids = []
        edge_ids = []
        cur = target_id
        while cur is not None:
            node_ids.append(cur)
            if prev_edge[cur]:
                edge_ids.append(prev_edge[cur])
            cur = prev[cur]
        node_ids.reverse()
        edge_ids.reverse()
        return self._build_path(node_ids)

    def stealthiest_path(self, source_id: str, target_id: str) -> AttackPath | None:
        """Minimize cumulative stealth footprint + detection probability."""
        def cost_fn(edge, target_node):
            return (edge.stealth_cost + target_node.stealth_footprint) * 2.0 + target_node.detection_prob
        return self.shortest_path(source_id, target_id, cost_fn)

    def highest_value_path(self, source_id: str, target_id: str) -> AttackPath | None:
        """Maximize value while keeping cost reasonable."""
        def cost_fn(edge, target_node):
            return (edge.weight + target_node.composite_cost()) / max(0.1, target_node.value)
        return self.shortest_path(source_id, target_id, cost_fn)

    def predict_detection(self, path: AttackPath) -> dict:
        """Predict detection timeline and weakest link."""
        if not path.nodes:
            return {"likely": False, "confidence": 0.0}
        max_detection = 0.0
        weakest_node = ""
        cumulative_noise = 0.0
        for nid in path.nodes:
            node = self._nodes[nid]
            cumulative_noise += node.stealth_footprint
            if node.detection_prob > max_detection:
                max_detection = node.detection_prob
                weakest_node = nid
        # simple heuristic: if cumulative noise > threshold, detection likely
        likely = cumulative_noise > 1.5 or max_detection > 0.7
        confidence = min(1.0, max_detection + cumulative_noise * 0.3)
        return {
            "likely": likely,
            "confidence": round(confidence, 3),
            "weakest_node": weakest_node,
            "max_detection": round(max_detection, 3),
            "cumulative_noise": round(cumulative_noise, 3),
        }

    # ------------------------------------------------------------------ #
    # Utility
    # ------------------------------------------------------------------ #
    def export_json(self) -> dict:
        return {
            "nodes": [
                {
                    "id": n.node_id,
                    "type": n.node_type.value,
                    "label": n.label,
                    "risk": n.risk_score,
                    "stealth": n.stealth_footprint,
                    "detection": n.detection_prob,
                    "value": n.value,
                    "compromised": n.compromised,
                    "metadata": n.metadata,
                }
                for n in self._nodes.values()
            ],
            "edges": [
                {
                    "id": e.edge_id,
                    "source": e.source_id,
                    "target": e.target_id,
                    "type": e.edge_type.value,
                    "technique": e.technique.value,
                    "weight": e.weight,
                    "stealth_cost": e.stealth_cost,
                    "success_prob": e.success_prob,
                }
                for e in self._edges.values()
            ],
        }

    def import_json(self, data: dict):
        self._nodes.clear()
        self._edges.clear()
        self._adj.clear()
        self._rev.clear()
        for nd in data.get("nodes", []):
            node = AttackNode(
                node_id=nd["id"],
                node_type=NodeType(nd["type"]),
                label=nd.get("label", ""),
                risk_score=nd.get("risk", 0.5),
                stealth_footprint=nd.get("stealth", 0.5),
                detection_prob=nd.get("detection", 0.5),
                value=nd.get("value", 0.5),
                compromised=nd.get("compromised", False),
                metadata=nd.get("metadata", {}),
            )
            self.add_node(node)
        for ed in data.get("edges", []):
            edge = AttackEdge(
                edge_id=ed["id"],
                source_id=ed["source"],
                target_id=ed["target"],
                edge_type=EdgeType(ed["type"]),
                technique=ed.get("technique", "GENERIC"),
                weight=ed.get("weight", 1.0),
                stealth_cost=ed.get("stealth_cost", 0.5),
                success_prob=ed.get("success_prob", 0.8),
            )
            self.add_edge(edge)

    def stats(self) -> dict:
        return {
            "nodes": len(self._nodes),
            "edges": len(self._edges),
            "by_type": {t.value: len(self.nodes_by_type(t)) for t in NodeType},
        }
