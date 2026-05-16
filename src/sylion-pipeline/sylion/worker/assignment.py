"""
SYLION Worker -- Assignment Orchestrator

Auto-assigns modules to workers using:
  1. Topological sort of dependency graph (core first)
  2. Worker capacity balancing (least-loaded first)
  3. Tag matching (worker tags vs module domain)
  4. Budget awareness (skip workers near limit)

Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus
from sylion.worker.registry import WorkerRegistry

log = logging.getLogger("sylion.worker.assignment")


def _topological_sort(modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort modules by dependencies (core first)."""
    ids = {m["module_id"] for m in modules}
    in_degree: dict[str, int] = {m["module_id"]: 0 for m in modules}
    adj: dict[str, list[str]] = {m["module_id"]: [] for m in modules}
    for m in modules:
        for dep in m.get("depends_on", []):
            if dep in ids:
                in_degree[m["module_id"]] += 1
                adj[dep].append(m["module_id"])
    queue = [mid for mid, deg in in_degree.items() if deg == 0]
    order: list[str] = []
    while queue:
        queue.sort()
        mid = queue.pop(0)
        order.append(mid)
        for nxt in adj[mid]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)
    id_map = {m["module_id"]: m for m in modules}
    return [id_map[mid] for mid in order if mid in id_map]


class AssignmentOrchestrator:
    """Balances module assignments across the worker fleet."""

    def __init__(
        self,
        worker_registry: WorkerRegistry,
        event_bus: EventBus | None = None,
    ):
        self._wr = worker_registry
        self._event_bus = event_bus or get_event_bus()

    def _emit(self, topic: str, payload: dict[str, Any]):
        try:
            self._event_bus.emit(SylionEvent(topic=topic, payload=payload, source_module="core.worker"))
        except Exception as exc:
            log.warning("EventBus emit failed: %s", exc)

    # ------------------------------------------------------------------
    # Auto-assign
    # ------------------------------------------------------------------

    def auto_assign(
        self,
        modules: list[dict[str, Any]],
        strategy: str = "balanced",
    ) -> dict[str, Any]:
        """
        Assign unassigned modules to available workers.

        modules: list of dicts with keys: module_id, domain, depends_on (list), priority (int)
        strategy: 'balanced' | 'domain_affinity' | 'budget_aware'
        """
        workers = self._wr.list_workers(status="active")
        if not workers:
            return {"assigned": 0, "skipped": len(modules), "errors": ["No active workers"]}

        existing = self._wr.list_assignments(status="assigned") + self._wr.list_assignments(status="in_progress")
        assigned_module_ids = {a["module_id"] for a in existing}

        unassigned = [m for m in modules if m.get("module_id") not in assigned_module_ids]
        sorted_modules = _topological_sort(unassigned)

        results: list[dict[str, Any]] = []
        errors: list[str] = []

        for mod in sorted_modules:
            worker = self._pick_worker(mod, workers, strategy)
            if worker is None:
                errors.append(f"No capacity for module {mod.get('module_id')}")
                continue
            try:
                asg = self._wr.create_assignment(
                    worker_id=worker["worker_id"],
                    module_id=mod["module_id"],
                    priority=mod.get("priority", 5),
                    metadata={"strategy": strategy, "domain": mod.get("domain", "")},
                )
                results.append(asg)
                # Refresh worker local data for next pick
                for i, w in enumerate(workers):
                    if w["worker_id"] == worker["worker_id"]:
                        workers[i] = self._wr.get_worker(worker["worker_id"]) or w
                        break
            except Exception as exc:
                errors.append(str(exc))

        self._emit(
            "assignment.auto_assigned",
            {"assigned": len(results), "skipped": len(unassigned) - len(results), "errors": errors},
        )
        return {"assigned": len(results), "skipped": len(unassigned) - len(results), "errors": errors}

    def _pick_worker(
        self,
        module: dict[str, Any],
        workers: list[dict[str, Any]],
        strategy: str,
    ) -> dict[str, Any] | None:
        domain = module.get("domain", "")
        candidates: list[tuple[float, dict[str, Any]]] = []
        for w in workers:
            load = len(w.get("assigned_modules", []))
            cap = w.get("capacity", 1)
            if load >= cap:
                continue
            score = float(load) / float(cap)
            # Domain affinity boost
            tags = w.get("tags", [])
            if domain and any(domain.startswith(t) or t in domain for t in tags):
                score -= 0.3
            # Budget penalty
            budget_limit = w.get("budget_limit", 0.0)
            budget_spent = w.get("budget_spent", 0.0)
            if budget_limit > 0 and budget_spent / budget_limit > 0.9:
                continue
            if budget_limit > 0:
                score += (budget_spent / budget_limit) * 0.2
            candidates.append((score, w))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    # ------------------------------------------------------------------
    # Rebalance
    # ------------------------------------------------------------------

    def rebalance(self) -> dict[str, Any]:
        """Re-distribute assignments to balance load."""
        workers = self._wr.list_workers(status="active")
        assignments = self._wr.list_assignments(status="assigned")
        if not workers or not assignments:
            return {"moved": 0, "reason": "No workers or assignments"}

        # Simple rebalance: if any worker is over capacity and another is under, move lowest-priority
        moved = 0
        for w in workers:
            load = len(w.get("assigned_modules", []))
            cap = w.get("capacity", 1)
            if load > cap:
                w_asgns = [a for a in assignments if a["worker_id"] == w["worker_id"]]
                w_asgns.sort(key=lambda a: a.get("priority", 5), reverse=True)
                overflow = load - cap
                for a in w_asgns[:overflow]:
                    target = self._find_underloaded_worker(workers, exclude=w["worker_id"])
                    if target:
                        self._wr.delete_assignment(a["assignment_id"])
                        self._wr.create_assignment(
                            worker_id=target["worker_id"],
                            module_id=a["module_id"],
                            priority=a.get("priority", 5),
                            metadata=a.get("metadata", {}),
                        )
                        moved += 1
        self._emit("assignment.rebalanced", {"moved": moved})
        return {"moved": moved}

    def _find_underloaded_worker(
        self, workers: list[dict[str, Any]], exclude: str
    ) -> dict[str, Any] | None:
        best: dict[str, Any] | None = None
        best_ratio = 1.0
        for w in workers:
            if w["worker_id"] == exclude:
                continue
            load = len(w.get("assigned_modules", []))
            cap = w.get("capacity", 1)
            if load < cap:
                ratio = load / cap
                if ratio < best_ratio:
                    best_ratio = ratio
                    best = w
        return best

    # ------------------------------------------------------------------
    # Build topology generators
    # ------------------------------------------------------------------

    def generate_topology_config(
        self,
        variant: str = "8_server",
    ) -> dict[str, Any]:
        """Generate a topology config matching the AEIS Distributed Build doc."""
        configs: dict[str, Any] = {
            "5_server": {
                "servers": [
                    {"role": "control_plane", "components": ["canon", "planning", "coordination", "governance"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "worker_a", "components": ["core", "registry", "contracts"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "worker_b", "components": ["cognitive", "memory"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "worker_c", "components": ["execution", "skills", "connectors"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "worker_d_integration", "components": ["security", "monitoring", "ui", "integration_tests"], "min_vcpus": 2, "min_ram_gb": 4},
                ]
            },
            "8_server": {
                "servers": [
                    {"role": "canon_planning", "components": ["canon_manager", "decomposition_engine"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "coordination_governance", "components": ["assignment_orchestrator", "governance_engine"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "data_backbone", "components": ["postgres", "nats", "minio", "vault"], "min_vcpus": 2, "min_ram_gb": 8},
                    {"role": "worker_a", "components": ["core", "contracts", "registry"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "worker_b", "components": ["cognitive", "memory"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "worker_c", "components": ["execution", "skills", "connectors"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "worker_d", "components": ["security", "monitoring", "audit"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "integration_dashboard", "components": ["integration_orchestrator", "dashboard_pro"], "min_vcpus": 2, "min_ram_gb": 4},
                ]
            },
            "10_server": {
                "servers": [
                    {"role": "canon_layer", "components": ["canon_manager"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "planning_layer", "components": ["decomposition_engine"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "coordination_layer", "components": ["assignment_orchestrator"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "governance_layer", "components": ["governance_engine"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "data_backbone", "components": ["postgres", "nats", "minio", "vault"], "min_vcpus": 2, "min_ram_gb": 8},
                    {"role": "worker_a", "components": ["core", "contracts"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "worker_b", "components": ["cognitive", "memory", "self_model"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "worker_c", "components": ["execution", "connectors", "skills"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "worker_d", "components": ["security", "observability", "audit"], "min_vcpus": 2, "min_ram_gb": 4},
                    {"role": "worker_e", "components": ["dashboard", "ui", "operator_console"], "min_vcpus": 2, "min_ram_gb": 4},
                ]
            },
        }
        return configs.get(variant, configs["8_server"])
