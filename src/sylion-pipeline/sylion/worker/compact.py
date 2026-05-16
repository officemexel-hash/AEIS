"""
SYLION Worker -- Compact Generator

Generates a "compact" for each worker: a scoped, formal snapshot of everything
the worker needs to implement its assigned modules, without reading the full repo.

Compact includes:
  - assigned modules + direct dependencies
  - relevant contract stubs (public API, events, schemas)
  - recent decisions affecting the worker's scope
  - integration blockers
  - priority, deadline, acceptance criteria

Designed for minimal token/context usage per worker.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from sylion.worker.registry import WorkerRegistry

log = logging.getLogger("sylion.worker.compact")


class CompactGenerator:
    """Builds scoped compact documents for workers."""

    def __init__(
        self,
        worker_registry: WorkerRegistry,
        manifest_dir: Path | None = None,
    ):
        self._wr = worker_registry
        self._manifest_dir = manifest_dir

    def generate(
        self,
        worker_id: str,
        module_registry: list[dict[str, Any]] | None = None,
        recent_decisions: list[dict[str, Any]] | None = None,
        blockers: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Return a compact dict for the given worker."""
        worker = self._wr.get_worker(worker_id)
        if worker is None:
            raise ValueError(f"Worker {worker_id} not found")

        assignments = self._wr.list_assignments(worker_id=worker_id)
        assigned_ids = [a["module_id"] for a in assignments]

        # Resolve dependency closure (direct only)
        dependency_ids: set[str] = set()
        if module_registry:
            id_map = {m["module_id"]: m for m in module_registry}
            for mid in assigned_ids:
                m = id_map.get(mid)
                if m:
                    for dep in m.get("depends_on", []):
                        if dep != mid:
                            dependency_ids.add(dep)

        # Load manifest stubs for assigned + dependencies
        manifest_stubs: list[dict[str, Any]] = []
        if self._manifest_dir:
            for mid in list(set(assigned_ids) | dependency_ids):
                stub = self._load_manifest_stub(mid)
                if stub:
                    manifest_stubs.append(stub)

        # Filter decisions affecting this worker
        relevant_decisions = []
        if recent_decisions:
            scope_set = set(assigned_ids) | dependency_ids
            for d in recent_decisions:
                affected = d.get("affected_modules", [])
                if any(m in scope_set for m in affected):
                    relevant_decisions.append(d)

        compact = {
            "compact_version": "1.0",
            "generated_at": time.time(),
            "worker_id": worker_id,
            "worker_name": worker["name"],
            "host": worker["host"],
            "capacity": worker["capacity"],
            "assigned_modules": assigned_ids,
            "dependency_modules": sorted(dependency_ids),
            "assignments": [
                {
                    "assignment_id": a["assignment_id"],
                    "module_id": a["module_id"],
                    "status": a["status"],
                    "priority": a["priority"],
                    "metadata": a.get("metadata", {}),
                }
                for a in assignments
            ],
            "manifest_stubs": manifest_stubs,
            "relevant_decisions": relevant_decisions[:20],  # cap context size
            "integration_blockers": blockers or [],
            "acceptance_criteria": self._build_acceptance_criteria(assignments),
            "local_test_command": "pytest tests/ -q",
            "budget_remaining": max(0.0, (worker["budget_limit"] or 0.0) - (worker["budget_spent"] or 0.0)),
        }
        return compact

    def _load_manifest_stub(self, module_id: str) -> dict[str, Any] | None:
        if self._manifest_dir is None:
            return None
        path = self._manifest_dir / f"{module_id}.json"
        if not path.exists():
            # Try with dots replaced by underscores if not found
            path = self._manifest_dir / f"{module_id.replace('.', '_')}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Strip to public contract info only
            return {
                "module_id": data.get("module_id", module_id),
                "name": data.get("name", ""),
                "version": data.get("version", ""),
                "domain": data.get("domain", ""),
                "description": data.get("description", ""),
                "depends_on": data.get("depends_on", []),
                "public_api": data.get("public_api", []),
                "events": data.get("events", []),
                "owner": data.get("owner", ""),
            }
        except Exception as exc:
            log.warning("Failed to load manifest stub for %s: %s", module_id, exc)
            return None

    def _build_acceptance_criteria(self, assignments: list[dict[str, Any]]) -> list[str]:
        criteria = [
            "All local tests pass (pytest).",
            "Contract tests pass against frozen public API.",
            "No cross-module drift introduced.",
            "Lint and typecheck pass cleanly.",
            "Evidence pack attached for D3+ changes.",
        ]
        if assignments:
            criteria.append(f"Complete {len(assignments)} assigned module(s).")
        return criteria

    @staticmethod
    def render_markdown_static(compact: dict[str, Any]) -> str:
        """Render compact as markdown (static version for SandboxManager)."""
        lines: list[str] = [
            f"# Worker Compact: {compact.get('worker_name', 'Unknown')} ({compact.get('worker_id', '')})",
            f"**Host:** {compact.get('host', '')}  |  **Capacity:** {compact.get('capacity', '')}  |  **Generated:** {compact.get('generated_at', '')}",
            "",
            "## Assigned Modules",
        ]
        for mid in compact.get("assigned_modules", []):
            lines.append(f"- `{mid}`")
        if compact.get("dependency_modules"):
            lines += ["", "## Direct Dependencies"]
            for mid in compact["dependency_modules"]:
                lines.append(f"- `{mid}`")
        lines += ["", "## Assignments"]
        for a in compact.get("assignments", []):
            lines.append(f"- `{a.get('module_id')}` → status={a.get('status')} priority={a.get('priority')}")
        lines += ["", "## Acceptance Criteria"]
        for c in compact.get("acceptance_criteria", []):
            lines.append(f"- [ ] {c}")
        if compact.get("relevant_decisions"):
            lines += ["", "## Relevant Decisions"]
            for d in compact["relevant_decisions"]:
                lines.append(f"- {d.get('title', 'Decision')}: {d.get('summary', '')}")
        if compact.get("integration_blockers"):
            lines += ["", "## Blockers"]
            for b in compact["integration_blockers"]:
                lines.append(f"- {b.get('description', '')}")
        lines += ["", "## Budget Remaining"]
        lines.append(f"${compact.get('budget_remaining', 0):.2f}")
        lines.append("")
        return "\n".join(lines)

    def render_markdown(self, compact: dict[str, Any]) -> str:
        """Render compact as markdown for human/AI consumption."""
        lines: list[str] = [
            f"# Worker Compact: {compact['worker_name']} ({compact['worker_id']})",
            f"**Host:** {compact['host']}  |  **Capacity:** {compact['capacity']}  |  **Generated:** {compact['generated_at']}",
            "",
            "## Assigned Modules",
        ]
        for mid in compact["assigned_modules"]:
            lines.append(f"- `{mid}`")
        if compact["dependency_modules"]:
            lines += ["", "## Direct Dependencies"]
            for mid in compact["dependency_modules"]:
                lines.append(f"- `{mid}`")
        lines += ["", "## Assignments"]
        for a in compact["assignments"]:
            lines.append(f"- `{a['module_id']}` → status={a['status']} priority={a['priority']}")
        lines += ["", "## Acceptance Criteria"]
        for c in compact["acceptance_criteria"]:
            lines.append(f"- [ ] {c}")
        if compact["relevant_decisions"]:
            lines += ["", "## Relevant Decisions"]
            for d in compact["relevant_decisions"]:
                lines.append(f"- {d.get('title', 'Decision')}: {d.get('summary', '')}")
        if compact["integration_blockers"]:
            lines += ["", "## Blockers"]
            for b in compact["integration_blockers"]:
                lines.append(f"- {b.get('description', '')}")
        lines += ["", "## Budget Remaining"]
        lines.append(f"${compact['budget_remaining']:.2f}")
        lines.append("")
        return "\n".join(lines)
