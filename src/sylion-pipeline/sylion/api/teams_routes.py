from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

log = logging.getLogger("sylion.api.teams")

router = APIRouter(prefix="/api/v1/advisor/teams", tags=["advisor-teams"])

_NODE_ORDER = [
    ("planner", "Planner"),
    ("workers", "Workers"),
    ("verifier", "Verifier"),
    ("critic", "Critic"),
    ("council", "Council/HG"),
]

_EDGES = [
    ["planner", "workers"],
    ["workers", "verifier"],
    ["verifier", "critic"],
    ["critic", "council"],
]


def _empty_topology() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": node_id, "label": label, "active": False, "workers_count": 0}
            for node_id, label in _NODE_ORDER
        ],
        "edges": _EDGES,
    }


def _classify_bucket(agent_type: str, current_task: str) -> str:
    token = f"{agent_type} {current_task}".lower()
    if any(part in token for part in ("council", "human_gate", "human gate", "governance", "hg")):
        return "council"
    if any(part in token for part in ("critic", "security")):
        return "critic"
    if any(part in token for part in ("verifier", "verify", "audit", "qa", "test")):
        return "verifier"
    if any(part in token for part in ("planner", "plan", "architect")):
        return "planner"
    return "workers"


@router.get("/topology")
def teams_topology():
    try:
        from sylion.aeis.advisor.orchestration_config.service import get_orchestration_service

        teams = get_orchestration_service().get_active_teams()
    except Exception as exc:
        log.warning("advisor.teams_topology failed: %s", exc, exc_info=True)
        teams = []

    buckets = {node_id: 0 for node_id, _ in _NODE_ORDER}
    if teams:
        buckets["planner"] = 1

    for team in teams:
        current_task = str(getattr(team, "current_task", "") or "")
        agent_types = list(getattr(team, "agent_types", []) or [])
        if not agent_types:
            buckets["workers"] += 1
            continue
        for agent_type in agent_types:
            bucket = _classify_bucket(str(agent_type or ""), current_task)
            buckets[bucket] += 1

    return {
        "nodes": [
            {
                "id": node_id,
                "label": label,
                "active": bool(buckets[node_id]),
                "workers_count": int(buckets[node_id]),
            }
            for node_id, label in _NODE_ORDER
        ],
        "edges": _EDGES,
    }
