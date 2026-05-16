"""
Attack Graph Data Models

Graph ontology:
    Identity → Trust → Host → Exposure → Privilege → Asset

Each node carries:
- risk score (0.0-1.0)
- stealth footprint (0.0-1.0, higher = more noise)
- detection probability (0.0-1.0)
- value (0.0-1.0, target worth)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    IDENTITY = "identity"       # user, service account, token
    TRUST = "trust"             # trust relationship, delegation
    HOST = "host"               # machine, vm, container
    EXPOSURE = "exposure"       # open port, misconfig, vuln
    PRIVILEGE = "privilege"     # role, permission, elevation
    ASSET = "asset"             # data, secret, critical resource
    PIVOT = "pivot"             # intermediate hop / bridge node


class EdgeType(str, Enum):
    AUTHENTICATES = "authenticates"     # identity → host/trust
    TRUSTS = "trusts"                   # trust → trust/host/identity
    RUNS_ON = "runs_on"                 # identity/privilege → host
    EXPOSES = "exposes"                 # host → exposure
    GRANTS = "grants"                   # exposure/privilege → privilege
    LEADS_TO = "leads_to"               # exposure → asset
    PIVOTS = "pivots"                   # host → host (lateral)
    DEPENDS = "depends"                 # privilege → asset


class TechniqueMITRE(str, Enum):
    """Stub for MITRE ATT&CK technique references."""
    T1078 = "T1078"  # Valid Accounts
    T1552 = "T1552"  # Unsecured Credentials
    T1190 = "T1190"  # Exploit Public-Facing Application
    T1210 = "T1210"  # Exploitation of Remote Services
    T1098 = "T1098"  # Account Manipulation
    T1003 = "T1003"  # OS Credential Dumping
    T1087 = "T1087"  # Account Discovery
    T1136 = "T1136"  # Create Account
    T1548 = "T1548"  # Abuse Elevation Control Mechanism
    T1486 = "T1486"  # Data Encrypted for Impact
    GENERIC = "GENERIC"


@dataclass
class AttackNode:
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    node_type: NodeType = NodeType.HOST
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    # scoring dimensions
    risk_score: float = 0.5          # inherent risk
    stealth_footprint: float = 0.5   # noise generated (0=ghost, 1=klaxon)
    detection_prob: float = 0.5      # likelihood of being caught
    value: float = 0.5               # target value
    compromised: bool = False        # has this node been pwned in simulation
    x: float = 0.0                   # layout coordinate
    y: float = 0.0                   # layout coordinate

    def composite_cost(self, weight_stealth: float = 0.4,
                       weight_detection: float = 0.4,
                       weight_risk: float = 0.2) -> float:
        """Lower is better. Balances stealth, detection, risk."""
        return (weight_stealth * self.stealth_footprint +
                weight_detection * self.detection_prob +
                weight_risk * (1.0 - self.risk_score))


@dataclass
class AttackEdge:
    edge_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_id: str = ""
    target_id: str = ""
    edge_type: EdgeType = EdgeType.LEADS_TO
    technique: TechniqueMITRE = TechniqueMITRE.GENERIC
    weight: float = 1.0              # graph traversal cost
    stealth_cost: float = 0.5        # additional noise from taking this edge
    detection_delta: float = 0.1     # how much detection probability rises
    success_prob: float = 0.8        # probability this edge works
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AttackPath:
    path_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    nodes: list[str] = field(default_factory=list)   # ordered node_ids
    edges: list[str] = field(default_factory=list)   # ordered edge_ids
    total_cost: float = 0.0
    total_stealth: float = 0.0
    total_detection: float = 0.0
    success_probability: float = 1.0
    estimated_time_sec: float = 0.0
    path_type: str = "default"       # shortest, stealthiest, highest_value

    def __len__(self) -> int:
        return len(self.nodes)
