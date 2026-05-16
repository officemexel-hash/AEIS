"""W14 Agent Team Theater read-only aggregator.

The theater is an operator surface, so it must not invent live actors. It reads
from existing truth planes only: W14 ontology, model registry, active
orchestration teams, guardians and unified governance tickets.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

from sylion.aeis.testing.guardians import GuardianBase, register_all_guardians
from sylion.aeis.testing.ontology.objects import Finding, LoopReport, RepairAttempt
from sylion.aeis.testing.ontology.store import OntologyStore


def _value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


class AgentTheaterAggregator:
    """Aggregates live agent and governance state for the dashboard.

    Pure read API. It never mutates runtime state.
    """

    def __init__(
        self,
        ontology: OntologyStore,
        guardian_registry: dict[str, GuardianBase] | None = None,
        model_registry: Any | None = None,
        team_provider: Any | None = None,
        ticket_fetcher: Any | None = None,
    ) -> None:
        self._ontology = ontology
        self._guardians = guardian_registry or register_all_guardians(ontology)
        self._model_registry = model_registry
        self._team_provider = team_provider
        self._ticket_fetcher = ticket_fetcher

    def get_topology(self, project_id: str | None = None) -> dict:
        """Return a snapshot of live actors and edges.

        Sources:
        - model registry / project council for model actors
        - orchestration config for active teams
        - W14 ontology for open findings
        """
        actors: list[dict] = []
        edges: list[dict] = []
        warnings: list[str] = []

        model_actors = self._model_actors(project_id=project_id)
        actors.extend(model_actors)

        team_data = self._active_team_actors()
        actors.extend(team_data["actors"])
        edges.extend(team_data["edges"])

        findings = self._ontology.list(Finding, limit=100)
        open_findings = [
            f for f in findings
            if f.r_status not in ("CLOSED", "WAIVED_BY_HUMAN")
        ]
        repair_source = self._repair_source_actor_id(model_actors, actors)
        if open_findings and repair_source == "unassigned_repair_queue":
            actors.append({
                "id": repair_source,
                "name": "Unassigned repair queue",
                "role": "repair_queue",
                "status": "open",
                "kind": "queue",
                "source": "w14_ontology",
            })
            warnings.append("open_findings_without_live_repair_model")

        for finding in open_findings[:20]:
            actor_id = f"finding_{finding.finding_id}"
            actors.append({
                "id": actor_id,
                "name": finding.title[:60],
                "role": "finding",
                "status": finding.r_status.lower(),
                "kind": "task",
                "severity": finding.severity,
                "d_level": finding.d_level,
                "source": "w14_ontology",
            })
            edges.append({
                "source": repair_source,
                "target": actor_id,
                "kind": "works_on",
            })

        return {
            "as_of": time.time(),
            "project_id": project_id,
            "actors": actors,
            "edges": edges,
            "source": {
                "ontology_db": getattr(self._ontology, "_db_path", None),
                "models": "model_registry",
                "teams": "orchestration_config",
                "findings": "w14_ontology",
            },
            "counts": {
                "models": len(model_actors),
                "teams": len(team_data["team_ids"]),
                "open_findings": len(open_findings),
            },
            "warnings": warnings,
        }

    def get_council_session_view(self, session_id: str) -> dict:
        """Return a council session view backed by a governance ticket."""
        fetcher = self._ticket_fetcher
        if fetcher is None:
            from sylion.governance.tickets import fetch_by_id
            fetcher = fetch_by_id

        ticket = fetcher(session_id)
        if ticket is None:
            return {
                "error": "council_session_not_found",
                "session_id": session_id,
            }

        payload = _value(ticket, "payload", {}) or {}
        participants = self._participants_from_payload(payload)
        critic_status = str(payload.get("critic_status") or "").strip()
        if not critic_status:
            critics = [
                p for p in participants
                if "critic" in str(p.get("role", "")).lower()
            ]
            if critics:
                critic_status = (
                    "signed" if any(bool(p.get("signed")) for p in critics)
                    else "pending"
                )
            else:
                critic_status = "not_recorded"

        sentinel_status = str(payload.get("sentinel_status") or "").strip()
        if not sentinel_status:
            sentinel_status = (
                "pass" if _value(ticket, "state") == "approved"
                else "pending"
            )

        return {
            "session_id": session_id,
            "source": "governance_ticket",
            "phase": (
                "resolved"
                if _value(ticket, "state") in {"approved", "rejected", "expired"}
                else "pending"
            ),
            "participants": participants,
            "critic_status": critic_status,
            "sentinel_status": sentinel_status,
            "consensus": {
                "state": _value(ticket, "state"),
                "decision_class": _value(ticket, "decision_class"),
                "gate_type": _value(ticket, "gate_type"),
                "priority": _value(ticket, "priority"),
            },
            "ticket": {
                "ticket_id": _value(ticket, "ticket_id"),
                "origin": _value(ticket, "origin"),
                "project_id": _value(ticket, "project_id"),
                "title": _value(ticket, "title"),
                "summary": _value(ticket, "summary"),
                "requested_by": _value(ticket, "requested_by"),
                "resolved_by": _value(ticket, "resolved_by"),
                "resolved_at": _value(ticket, "resolved_at"),
                "payload_keys": sorted(payload.keys()),
            },
        }

    def get_repair_theater(self, finding_id: str) -> dict:
        """Repair session view: R-status and Loop Governor budget."""
        finding = self._ontology.get(Finding, finding_id)
        if finding is None:
            return {"error": "finding_not_found", "finding_id": finding_id}

        attempts = self._ontology.list(
            RepairAttempt, filters={"finding_id": finding_id}, limit=100,
        )
        loops = self._ontology.list(
            LoopReport, filters={"finding_id": finding_id}, limit=10,
        )

        from sylion.aeis.testing.loop_governor import DEFAULT_LIMITS
        attempts_max = DEFAULT_LIMITS["max_auto_fix_attempts_per_finding"]

        files_total = sum(a.files_touched_count for a in attempts)
        diff_total = sum(a.diff_lines for a in attempts)
        time_in_loop = (
            (time.time() - min(a.started_at for a in attempts))
            if attempts else 0.0
        )

        return {
            "finding_id": finding_id,
            "r_status": finding.r_status,
            "severity": finding.severity,
            "d_level": finding.d_level,
            "attempts_used": len(attempts),
            "attempts_max": attempts_max,
            "files_touched": files_total,
            "diff_lines": diff_total,
            "time_in_loop_s": time_in_loop,
            "loop_status": "BLOCKED" if loops else "CLEAR",
            "loop_reports": [
                {"id": loop.report_id, "type": loop.loop_type}
                for loop in loops
            ],
        }

    def get_guardian_status(self) -> list[dict]:
        return [guardian.status() for guardian in self._guardians.values()]

    def get_local_models_status(self) -> list[dict]:
        """Return registered local models.

        Unknown models are not reported as idle, because that would look live
        while no runtime source confirms it.
        """
        registry = self._registry()
        if registry is None or not hasattr(registry, "list_models"):
            return []

        local_markers = ("ollama", "local", "qwen", "gpt-oss", "bielik", "pllum")
        rows: list[dict] = []
        for model in registry.list_models():
            haystack = " ".join(
                str(_value(model, key, "")).lower()
                for key in ("model_id", "provider", "display_name", "model_family")
            )
            if not any(marker in haystack for marker in local_markers):
                continue
            latest = _value(model, "latest_health", None) or {}
            rows.append({
                "name": _value(model, "display_name") or _value(model, "model_id"),
                "model_id": _value(model, "model_id"),
                "provider": _value(model, "provider", ""),
                "status": str(latest.get("status") or "registered"),
                "tasks_today": int(latest.get("tasks_today") or 0),
                "cost_usd": float(latest.get("cost_usd") or 0.0),
                "source": "model_registry",
            })
        return rows

    async def stream_updates(
        self, interval_s: float = 1.0,
    ) -> AsyncIterator[dict]:
        """Yield rolling snapshots for WebSocket consumers."""
        if interval_s <= 0:
            interval_s = 1.0
        while True:
            yield {
                "as_of": time.time(),
                "topology": self.get_topology(),
                "guardians": self.get_guardian_status(),
                "locals": self.get_local_models_status(),
            }
            await asyncio.sleep(interval_s)

    def _registry(self) -> Any | None:
        if self._model_registry is not None:
            return self._model_registry
        try:
            from sylion.cognitive.model_registry import get_model_registry
            return get_model_registry()
        except Exception:
            return None

    def _model_actors(self, project_id: str | None = None) -> list[dict]:
        registry = self._registry()
        if registry is None or not hasattr(registry, "get_active_members"):
            return []
        try:
            members = registry.get_active_members(project_id=project_id)
        except TypeError:
            members = registry.get_active_members(project_id)
        except Exception:
            return []

        actors: list[dict] = []
        seen: set[str] = set()
        for member in members:
            if not bool(_value(member, "active", True)):
                continue
            model_id = str(
                _value(member, "model_id") or _value(member, "member_id") or ""
            ).strip()
            if not model_id:
                continue
            actor_id = f"model_{model_id}"
            if actor_id in seen:
                continue
            seen.add(actor_id)
            actors.append({
                "id": actor_id,
                "name": model_id,
                "role": _value(member, "member_role", "model") or "model",
                "status": "idle",
                "kind": "model",
                "provider": _value(member, "provider", ""),
                "project_id": _value(member, "project_id", project_id),
                "voting_weight": float(_value(member, "voting_weight", 1.0) or 1.0),
                "source": "model_registry",
            })
        return actors

    def _active_team_actors(self) -> dict[str, Any]:
        provider = self._team_provider
        if provider is None:
            try:
                from sylion.aeis.advisor.orchestration_config.service import (
                    get_orchestration_service,
                )
                provider = get_orchestration_service()
            except Exception:
                provider = None
        if provider is None or not hasattr(provider, "get_active_teams"):
            return {"actors": [], "edges": [], "team_ids": []}

        try:
            teams = provider.get_active_teams()
        except Exception:
            return {"actors": [], "edges": [], "team_ids": []}

        actors: list[dict] = []
        edges: list[dict] = []
        team_ids: list[str] = []
        for team in teams[:20]:
            team_id = str(_value(team, "team_id", "")).strip()
            if not team_id:
                continue
            actor_id = f"team_{team_id}"
            team_ids.append(team_id)
            actors.append({
                "id": actor_id,
                "name": team_id,
                "role": _value(team, "lifetime", "team"),
                "status": "working" if _value(team, "current_task") else "idle",
                "kind": "team",
                "current_task": _value(team, "current_task"),
                "formed_at": _value(team, "formed_at"),
                "source": "orchestration_config",
            })
            for agent_type in list(_value(team, "agent_types", []) or []):
                agent_id = f"agent_{team_id}_{agent_type}"
                actors.append({
                    "id": agent_id,
                    "name": str(agent_type),
                    "role": "team_agent",
                    "status": "working",
                    "kind": "agent",
                    "source": "orchestration_config",
                })
                edges.append({
                    "source": agent_id,
                    "target": actor_id,
                    "kind": "works_on",
                })
        return {"actors": actors, "edges": edges, "team_ids": team_ids}

    @staticmethod
    def _repair_source_actor_id(
        model_actors: list[dict],
        all_actors: list[dict],
    ) -> str:
        for actor in model_actors:
            role = str(actor.get("role", "")).lower()
            name = str(actor.get("name", "")).lower()
            if "repair" in role or "codex" in name:
                return str(actor["id"])
        if model_actors:
            return str(model_actors[0]["id"])
        for actor in all_actors:
            if actor.get("kind") == "team":
                return str(actor["id"])
        return "unassigned_repair_queue"

    @staticmethod
    def _participants_from_payload(payload: dict[str, Any]) -> list[dict]:
        raw = (
            payload.get("participants")
            or payload.get("votes")
            or payload.get("council_members")
            or payload.get("members")
            or []
        )
        if isinstance(raw, dict):
            raw = list(raw.values())
        if not isinstance(raw, list):
            return []

        participants: list[dict] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            participants.append({
                "role": (
                    item.get("role")
                    or item.get("member_role")
                    or item.get("voter")
                    or "unknown"
                ),
                "rank": item.get("rank") or item.get("tier") or "",
                "weight": float(
                    item.get("weight") or item.get("voting_weight") or 1.0
                ),
                "verdict": (
                    item.get("verdict")
                    or item.get("vote")
                    or item.get("decision")
                ),
                "signed": bool(
                    item.get("signed")
                    or item.get("signature")
                    or item.get("critic_signature")
                ),
            })
        return participants


__all__ = ["AgentTheaterAggregator"]
