"""
Strategic AI — Central Brain

Responsibilities:
- Maintain campaign goals & priorities
- Build & update attack graph from telemetry
- Score paths and select optimal strategies
- Delegate tasks to Tactical Agents
- Prevent loops via Safety integration
- Update knowledge base after each campaign phase

Does NOT execute operations. Pure planner / scorer / delegator.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sylion.offensive.attack_graph.engine import AttackGraphEngine
from sylion.offensive.attack_graph.models import AttackNode, AttackPath, NodeType

log = logging.getLogger("sylion.offensive.strategic_ai")


class GoalStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class StrategyMode(str, Enum):
    SPEED = "speed"           # shortest path
    STEALTH = "stealth"       # minimal noise
    VALUE = "value"           # highest-value targets first
    BALANCED = "balanced"     # composite optimizer
    CHAOS = "chaos"           # maximal disruption (risky)


@dataclass
class CampaignGoal:
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    target_assets: list[str] = field(default_factory=list)   # node_ids or labels
    target_types: list[NodeType] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)    # where we start
    status: GoalStatus = GoalStatus.PENDING
    strategy: StrategyMode = StrategyMode.BALANCED
    constraints: dict[str, Any] = field(default_factory=dict)
    # constraints example: {"max_noise": 2.0, "max_time_sec": 3600, "avoid_detection_above": 0.8}
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DelegatedTask:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    goal_id: str = ""
    agent_type: str = ""       # e.g. "recon", "credential", "cloud"
    objective: str = ""        # human-readable
    target_node_ids: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 5          # 1 = highest
    max_duration_sec: float = 300.0
    stealth_budget: float = 1.0
    assigned_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    result_summary: dict[str, Any] = field(default_factory=dict)


class StrategicAI:
    def __init__(self, graph: AttackGraphEngine | None = None):
        self.graph = graph or AttackGraphEngine()
        self.goals: dict[str, CampaignGoal] = {}
        self.tasks: dict[str, DelegatedTask] = {}
        self.knowledge: dict[str, Any] = {}   # persistent learnings
        self.campaign_history: list[dict] = []
        self._loop_memory: set[str] = set()   # fingerprints of past failed paths

    # ------------------------------------------------------------------ #
    # Goal Management
    # ------------------------------------------------------------------ #
    def add_goal(self, goal: CampaignGoal) -> str:
        self.goals[goal.goal_id] = goal
        log.info("strategic-ai: goal %s added (%s)", goal.goal_id, goal.name)
        return goal.goal_id

    def remove_goal(self, goal_id: str) -> bool:
        return self.goals.pop(goal_id, None) is not None

    def update_goal_status(self, goal_id: str, status: GoalStatus):
        goal = self.goals.get(goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")
        goal.status = status
        if status in (GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.ABORTED):
            goal.completed_at = time.time()
        log.info("strategic-ai: goal %s -> %s", goal_id, status.value)

    # ------------------------------------------------------------------ #
    # Planning
    # ------------------------------------------------------------------ #
    def plan_campaign(self, goal_id: str) -> list[DelegatedTask]:
        """Given a goal, generate an ordered list of tasks for tactical agents."""
        goal = self.goals.get(goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")

        if goal.status != GoalStatus.PENDING:
            raise ValueError(f"Goal {goal_id} is not pending")

        goal.status = GoalStatus.ACTIVE
        tasks: list[DelegatedTask] = []

        # Determine start nodes (entry points or any identity/host)
        start_nodes = goal.entry_points or [
            n.node_id for n in self.graph.nodes_by_type(NodeType.IDENTITY)
        ] or [n.node_id for n in self.graph.nodes_by_type(NodeType.EXPOSURE)]

        # Determine target nodes
        target_nodes: list[str] = []
        for t in goal.target_assets:
            if t in self.graph._nodes:
                target_nodes.append(t)
        for nt in goal.target_types:
            target_nodes += [n.node_id for n in self.graph.nodes_by_type(nt)]
        if not target_nodes:
            target_nodes = [n.node_id for n in self.graph.nodes_by_type(NodeType.ASSET)]

        if not start_nodes or not target_nodes:
            log.warning("strategic-ai: no start or target nodes for goal %s", goal_id)
            return tasks

        # Pick strategy
        pathfinder = self._pick_pathfinder(goal.strategy)

        # Find best paths from any start to any target
        scored_paths: list[tuple[float, AttackPath]] = []
        for src in start_nodes:
            for tgt in target_nodes:
                if src == tgt:
                    continue
                path = pathfinder(src, tgt)
                if path is None:
                    continue
                # fingerprint for loop detection
                fp = ">".join(path.nodes)
                if fp in self._loop_memory:
                    continue
                score = self._score_path(path, goal)
                scored_paths.append((score, path))

        scored_paths.sort(key=lambda x: x[0], reverse=True)
        if not scored_paths:
            log.warning("strategic-ai: no viable paths for goal %s", goal_id)
            goal.status = GoalStatus.FAILED
            return tasks

        # Select top N paths and convert to tasks
        top_n = goal.constraints.get("max_parallel_paths", 3)
        for _score, path in scored_paths[:top_n]:
            # Phase 1: Recon along path
            for i, nid in enumerate(path.nodes):
                node = self.graph.get_node(nid)
                if not node:
                    continue
                tasks.append(DelegatedTask(
                    goal_id=goal_id,
                    agent_type="recon",
                    objective=f"Map {node.node_type.value} '{node.label}'",
                    target_node_ids=[nid],
                    priority=i + 1,
                    stealth_budget=goal.constraints.get("max_noise", 2.0) / max(len(path.nodes), 1),
                    payload={"path_id": path.path_id, "phase": "recon", "node_type": node.node_type.value},
                ))
            # Phase 2: Exploit / Privilege / Credential based on node types
            for i, nid in enumerate(path.nodes):
                node = self.graph.get_node(nid)
                if not node:
                    continue
                if node.node_type == NodeType.EXPOSURE:
                    tasks.append(DelegatedTask(
                        goal_id=goal_id,
                        agent_type="web" if "web" in node.label.lower() else "cloud",
                        objective=f"Exploit exposure on '{node.label}'",
                        target_node_ids=[nid],
                        priority=10 + i,
                        payload={"path_id": path.path_id, "phase": "exploit", "technique": "T1190"},
                    ))
                elif node.node_type == NodeType.PRIVILEGE:
                    tasks.append(DelegatedTask(
                        goal_id=goal_id,
                        agent_type="credential",
                        objective=f"Escalate privilege '{node.label}'",
                        target_node_ids=[nid],
                        priority=10 + i,
                        payload={"path_id": path.path_id, "phase": "escalate"},
                    ))
                elif node.node_type in (NodeType.ASSET, NodeType.TRUST):
                    tasks.append(DelegatedTask(
                        goal_id=goal_id,
                        agent_type="ad" if node.node_type == NodeType.TRUST else "cloud",
                        objective=f"Access {node.node_type.value} '{node.label}'",
                        target_node_ids=[nid],
                        priority=20 + i,
                        payload={"path_id": path.path_id, "phase": "access"},
                    ))

        # Deduplicate by objective + target
        seen = set()
        deduped = []
        for t in tasks:
            key = (t.objective, tuple(t.target_node_ids))
            if key not in seen:
                seen.add(key)
                deduped.append(t)

        for t in deduped:
            self.tasks[t.task_id] = t

        log.info("strategic-ai: planned %d tasks for goal %s", len(deduped), goal_id)
        return deduped

    def _pick_pathfinder(self, strategy: StrategyMode):
        if strategy == StrategyMode.STEALTH:
            return self.graph.stealthiest_path
        if strategy == StrategyMode.VALUE:
            return self.graph.highest_value_path
        if strategy == StrategyMode.SPEED:
            return self.graph.shortest_path
        # balanced: shortest with custom weights
        def balanced(src, tgt):
            def cost_fn(edge, target_node):
                return (edge.weight + target_node.composite_cost(0.35, 0.35, 0.30))
            return self.graph.shortest_path(src, tgt, cost_fn)
        return balanced

    def _score_path(self, path: AttackPath, goal: CampaignGoal) -> float:
        """Higher = better. Composite score balancing speed, stealth, value, success."""
        # speed score (inverse time)
        speed_s = 1.0 / (1.0 + path.estimated_time_sec / 60.0)
        # stealth score (inverse noise)
        stealth_s = 1.0 / (1.0 + path.total_stealth)
        # success score
        success_s = path.success_probability
        # value score: average value of target nodes
        values = [self.graph.get_node(n).value for n in path.nodes if self.graph.get_node(n)]
        value_s = sum(values) / max(len(values), 1)

        # strategy weights
        w = {
            StrategyMode.SPEED: (0.5, 0.1, 0.2, 0.2),
            StrategyMode.STEALTH: (0.1, 0.5, 0.2, 0.2),
            StrategyMode.VALUE: (0.1, 0.1, 0.3, 0.5),
            StrategyMode.BALANCED: (0.25, 0.25, 0.25, 0.25),
            StrategyMode.CHAOS: (0.3, 0.0, 0.5, 0.2),
        }.get(goal.strategy, (0.25, 0.25, 0.25, 0.25))

        return speed_s * w[0] + stealth_s * w[1] + success_s * w[2] + value_s * w[3]

    # ------------------------------------------------------------------ #
    # Telemetry / Learning
    # ------------------------------------------------------------------ #
    def ingest_telemetry(self, task_id: str, result: dict[str, Any]):
        """Ingest results from tactical agents and update graph + knowledge."""
        task = self.tasks.get(task_id)
        if not task:
            log.warning("strategic-ai: telemetry for unknown task %s", task_id)
            return

        task.result_summary = result
        task.completed_at = time.time()

        # Update graph nodes based on new intel
        for nid in task.target_node_ids:
            node = self.graph.get_node(nid)
            if not node:
                continue
            # If recon found new exposure/privilege, add nodes/edges
            discovered = result.get("discovered_nodes", [])
            for nd in discovered:
                if nd.get("id") not in self.graph._nodes:
                    new_node = AttackNode(
                        node_id=nd.get("id"),
                        node_type=NodeType(nd.get("type", "host")),
                        label=nd.get("label", ""),
                        risk_score=nd.get("risk", 0.5),
                        stealth_footprint=nd.get("stealth", 0.5),
                        detection_prob=nd.get("detection", 0.5),
                        value=nd.get("value", 0.5),
                        metadata=nd.get("metadata", {}),
                    )
                    self.graph.add_node(new_node)
                    # connect to parent
                    from sylion.offensive.attack_graph.models import AttackEdge, EdgeType
                    self.graph.add_edge(AttackEdge(
                        source_id=nid,
                        target_id=new_node.node_id,
                        edge_type=EdgeType(nd.get("edge_type", "leads_to")),
                    ))

        # Loop memory: if task failed, remember path fingerprint
        if not result.get("success", True):
            fp = result.get("path_fingerprint")
            if fp:
                self._loop_memory.add(fp)

        # Knowledge update
        technique = result.get("technique")
        if technique:
            self.knowledge.setdefault("technique_effectiveness", {})
            self.knowledge["technique_effectiveness"].setdefault(technique, {"success": 0, "fail": 0})
            self.knowledge["technique_effectiveness"][technique]["success" if result.get("success") else "fail"] += 1

        self.campaign_history.append({
            "task_id": task_id,
            "goal_id": task.goal_id,
            "agent_type": task.agent_type,
            "success": result.get("success"),
            "timestamp": time.time(),
        })
        log.info("strategic-ai: telemetry ingested for task %s (success=%s)", task_id, result.get("success"))

    def get_campaign_summary(self, goal_id: str) -> dict:
        goal = self.goals.get(goal_id)
        if not goal:
            return {}
        tasks = [t for t in self.tasks.values() if t.goal_id == goal_id]
        successes = sum(1 for t in tasks if t.result_summary.get("success"))
        return {
            "goal_id": goal_id,
            "name": goal.name,
            "status": goal.status.value,
            "strategy": goal.strategy.value,
            "tasks_total": len(tasks),
            "tasks_completed": sum(1 for t in tasks if t.completed_at),
            "tasks_success": successes,
            "score": goal.score,
            "duration_sec": (goal.completed_at or time.time()) - goal.created_at,
        }

    def recommend_next_move(self, goal_id: str) -> dict | None:
        """Given current state, recommend the next best task or abort."""
        goal = self.goals.get(goal_id)
        if not goal or goal.status != GoalStatus.ACTIVE:
            return None
        pending = [t for t in self.tasks.values() if t.goal_id == goal_id and not t.completed_at]
        if not pending:
            return {"action": "complete", "reason": "all tasks done"}
        # pick highest priority, lowest stealth budget remaining
        pending.sort(key=lambda t: (t.priority, -t.stealth_budget))
        next_task = pending[0]
        detection = self.graph.predict_detection(
            self.graph.shortest_path(next_task.target_node_ids[0], next_task.target_node_ids[-1])
        ) if len(next_task.target_node_ids) >= 2 else {"likely": False}
        if detection.get("likely") and goal.strategy != StrategyMode.CHAOS:
            return {"action": "pause", "reason": "detection likely", "task_id": next_task.task_id}
        return {"action": "execute", "task_id": next_task.task_id, "agent_type": next_task.agent_type}
