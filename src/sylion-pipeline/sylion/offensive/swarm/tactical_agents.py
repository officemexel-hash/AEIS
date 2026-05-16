"""
Tactical Agents — Specialized offensive AI workers

Each agent:
- Receives a DelegatedTask from StrategicAI
- Executes (simulated or real) against target nodes
- Returns structured telemetry
- Can self-report capability bounds (stealth, speed, accuracy)

Base class provides:
- common telemetry schema
- stealth budget tracking
- loop detection hook
"""
from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sylion.offensive.attack_graph.models import AttackNode, NodeType

log = logging.getLogger("sylion.offensive.tactical_agents")


@dataclass
class AgentCapability:
    agent_type: str = ""
    max_stealth: float = 1.0      # 0-1, higher = can be more quiet
    speed_factor: float = 1.0     # multiplier on task duration
    accuracy: float = 0.85        # probability of correct intel
    mutation_enabled: bool = False
    self_propagate: bool = False


@dataclass
class TacticalResult:
    result_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_id: str = ""
    agent_type: str = ""
    success: bool = False
    discovered_nodes: list[dict] = field(default_factory=list)
    credentials_found: list[dict] = field(default_factory=list)
    lateral_options: list[str] = field(default_factory=list)   # node_ids
    stealth_used: float = 0.0
    detection_risk_raised: float = 0.0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    path_fingerprint: str = ""
    technique: str = "GENERIC"
    timestamp: float = field(default_factory=time.time)


class TacticalAgent(ABC):
    def __init__(self, capability: AgentCapability | None = None):
        self.cap = capability or AgentCapability(agent_type=self.__class__.__name__)
        self.history: list[TacticalResult] = []

    @abstractmethod
    def execute(self, task: dict[str, Any], target_nodes: list[AttackNode]) -> TacticalResult:
        """Execute the task and return telemetry."""
        ...

    def _base_result(self, task: dict, targets: list[AttackNode]) -> TacticalResult:
        return TacticalResult(
            task_id=task.get("task_id", ""),
            agent_type=self.cap.agent_type,
            path_fingerprint=">".join([t.node_id for t in targets]),
            technique=task.get("payload", {}).get("technique", "GENERIC"),
        )

    def _simulate_stealth(self, base_cost: float) -> float:
        """Apply agent stealth capability to reduce noise."""
        return base_cost * (1.0 - self.cap.max_stealth * 0.5)

    def _simulate_detection(self, node: AttackNode, stealth_used: float) -> float:
        """Return delta detection probability based on node + our noise."""
        return min(1.0, node.detection_prob + stealth_used * 0.5)


class ReconAgent(TacticalAgent):
    """Enumeration, service mapping, technology identification."""

    def __init__(self):
        super().__init__(AgentCapability(
            agent_type="recon",
            max_stealth=0.9,
            speed_factor=0.8,
            accuracy=0.95,
        ))

    def execute(self, task: dict[str, Any], target_nodes: list[AttackNode]) -> TacticalResult:
        result = self._base_result(task, target_nodes)
        if not target_nodes:
            result.error = "no targets"
            return result

        node = target_nodes[0]
        # Simulate recon: discover neighbors, exposures, services
        discovered: list[dict] = []
        stealth = self._simulate_stealth(0.1)
        result.stealth_used = stealth
        result.detection_risk_raised = self._simulate_detection(node, stealth)

        # Heuristic discovery based on node type
        if node.node_type in (NodeType.HOST, NodeType.IDENTITY):
            discovered.append({
                "id": f"exp_{node.node_id}",
                "type": NodeType.EXPOSURE.value,
                "label": f"open_port_{hash(node.node_id) % 65535}",
                "risk": 0.4,
                "stealth": 0.3,
                "detection": 0.2,
                "value": 0.3,
                "edge_type": "exposes",
                "metadata": {"service": "http", "version": "unknown"},
            })
        if node.node_type == NodeType.TRUST:
            discovered.append({
                "id": f"priv_{node.node_id}",
                "type": NodeType.PRIVILEGE.value,
                "label": f"delegation_{node.node_id}",
                "risk": 0.7,
                "stealth": 0.5,
                "detection": 0.4,
                "value": 0.6,
                "edge_type": "grants",
            })

        result.success = True
        result.discovered_nodes = discovered
        result.metadata = {"scanned_ports": [80, 443, 22, 3389][:hash(node.node_id) % 3 + 1]}
        self.history.append(result)
        return result


class CredentialAgent(TacticalAgent):
    """Secret analysis, reuse detection, path analysis."""

    def __init__(self):
        super().__init__(AgentCapability(
            agent_type="credential",
            max_stealth=0.85,
            speed_factor=1.0,
            accuracy=0.90,
        ))

    def execute(self, task: dict[str, Any], target_nodes: list[AttackNode]) -> TacticalResult:
        result = self._base_result(task, target_nodes)
        if not target_nodes:
            result.error = "no targets"
            return result

        node = target_nodes[0]
        stealth = self._simulate_stealth(0.25)
        result.stealth_used = stealth
        result.detection_risk_raised = self._simulate_detection(node, stealth)

        if node.node_type in (NodeType.IDENTITY, NodeType.PRIVILEGE, NodeType.TRUST):
            result.credentials_found = [{
                "type": "hash",
                "source": node.node_id,
                "reuse_risk": 0.6,
                "lateral_leads": [f"host_{hash(node.node_id) % 100}"],
            }]
            result.success = True
        else:
            result.success = False
            result.error = "no credential surface"

        self.history.append(result)
        return result


class CloudAgent(TacticalAgent):
    """IAM review, privilege paths, misconfiguration graph."""

    def __init__(self):
        super().__init__(AgentCapability(
            agent_type="cloud",
            max_stealth=0.8,
            speed_factor=0.9,
            accuracy=0.88,
        ))

    def execute(self, task: dict[str, Any], target_nodes: list[AttackNode]) -> TacticalResult:
        result = self._base_result(task, target_nodes)
        if not target_nodes:
            result.error = "no targets"
            return result

        node = target_nodes[0]
        stealth = self._simulate_stealth(0.2)
        result.stealth_used = stealth
        result.detection_risk_raised = self._simulate_detection(node, stealth)

        if node.node_type in (NodeType.ASSET, NodeType.EXPOSURE, NodeType.HOST):
            result.discovered_nodes = [{
                "id": f"iam_{node.node_id}",
                "type": NodeType.PRIVILEGE.value,
                "label": f"overprivileged_role_{node.node_id}",
                "risk": 0.75,
                "stealth": 0.4,
                "detection": 0.35,
                "value": 0.8,
                "edge_type": "grants",
                "metadata": {"cloud": "aws", "iam_policy": "AdministratorAccess"},
            }]
            result.success = True
        else:
            result.success = False
            result.error = "not a cloud target"

        self.history.append(result)
        return result


class WebAgent(TacticalAgent):
    """Validation findings, workflow analysis, injection testing."""

    def __init__(self):
        super().__init__(AgentCapability(
            agent_type="web",
            max_stealth=0.75,
            speed_factor=0.7,
            accuracy=0.82,
        ))

    def execute(self, task: dict[str, Any], target_nodes: list[AttackNode]) -> TacticalResult:
        result = self._base_result(task, target_nodes)
        if not target_nodes:
            result.error = "no targets"
            return result

        node = target_nodes[0]
        stealth = self._simulate_stealth(0.3)
        result.stealth_used = stealth
        result.detection_risk_raised = self._simulate_detection(node, stealth)

        if node.node_type == NodeType.EXPOSURE or "web" in node.label.lower():
            result.discovered_nodes = [{
                "id": f"vuln_{node.node_id}",
                "type": NodeType.EXPOSURE.value,
                "label": f"sqli_{node.node_id}",
                "risk": 0.85,
                "stealth": 0.5,
                "detection": 0.6,
                "value": 0.7,
                "edge_type": "leads_to",
                "metadata": {"cwe": "CWE-89", "param": "id"},
            }]
            result.success = True
            result.technique = "T1190"
        else:
            result.success = False
            result.error = "no web surface"

        self.history.append(result)
        return result


class ADAgent(TacticalAgent):
    """Trust relationships, delegation paths, Kerberos exposure."""

    def __init__(self):
        super().__init__(AgentCapability(
            agent_type="ad",
            max_stealth=0.7,
            speed_factor=1.1,
            accuracy=0.80,
        ))

    def execute(self, task: dict[str, Any], target_nodes: list[AttackNode]) -> TacticalResult:
        result = self._base_result(task, target_nodes)
        if not target_nodes:
            result.error = "no targets"
            return result

        node = target_nodes[0]
        stealth = self._simulate_stealth(0.35)
        result.stealth_used = stealth
        result.detection_risk_raised = self._simulate_detection(node, stealth)

        if node.node_type in (NodeType.TRUST, NodeType.IDENTITY):
            result.discovered_nodes = [{
                "id": f"del_{node.node_id}",
                "type": NodeType.TRUST.value,
                "label": f"unconstrained_delegation_{node.node_id}",
                "risk": 0.9,
                "stealth": 0.6,
                "detection": 0.5,
                "value": 0.95,
                "edge_type": "trusts",
                "metadata": {"kerberos": "TGT", "spn": "HTTP/svc"},
            }]
            result.lateral_options = [f"host_{hash(node.node_id) % 50}"]
            result.success = True
            result.technique = "T1558"
        else:
            result.success = False
            result.error = "no AD surface"

        self.history.append(result)
        return result


class AgentSwarm:
    """Registry of all tactical agents."""

    def __init__(self):
        self._agents: dict[str, TacticalAgent] = {
            "recon": ReconAgent(),
            "credential": CredentialAgent(),
            "cloud": CloudAgent(),
            "web": WebAgent(),
            "ad": ADAgent(),
        }

    def get(self, agent_type: str) -> TacticalAgent | None:
        return self._agents.get(agent_type)

    def list_types(self) -> list[str]:
        return list(self._agents.keys())

    def dispatch(self, task: dict[str, Any], target_nodes: list[AttackNode]) -> TacticalResult:
        agent = self.get(task.get("agent_type", ""))
        if not agent:
            return TacticalResult(
                task_id=task.get("task_id", ""),
                success=False,
                error=f"unknown agent type: {task.get('agent_type')}",
            )
        return agent.execute(task, target_nodes)
