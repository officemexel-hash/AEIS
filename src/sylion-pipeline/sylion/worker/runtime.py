"""
SYLION Worker -- Runtime

Executes the build lifecycle for a single worker:
  1. Pull next assignment from the queue
  2. Generate / load compact
  3. Prepare sandbox (git worktree or isolated folder)
  4. Run local validation (lint, typecheck, tests)
  5. Build patch proposal
  6. Submit patch + evidence to backend

Designed to run as a standalone process per worker:
    python -m sylion.worker.runtime --worker-id wk_xxx --loop --interval 60
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from sylion.worker.registry import WorkerRegistry, get_worker_registry
from sylion.worker.assignment import AssignmentOrchestrator
from sylion.worker.compact import CompactGenerator
from sylion.worker.sandbox import SandboxManager
from sylion.core.event_bus import get_event_bus

log = logging.getLogger("sylion.worker.runtime")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


class WorkerRuntime:
    """Local runtime for a single build worker."""

    def __init__(
        self,
        worker_id: str,
        registry: WorkerRegistry | None = None,
        sandbox: SandboxManager | None = None,
        compact_generator: CompactGenerator | None = None,
    ):
        self.worker_id = worker_id
        self._registry = registry or get_worker_registry(event_bus=get_event_bus())
        self._sandbox = sandbox or SandboxManager()
        self._compact_gen = compact_generator or CompactGenerator(
            worker_registry=self._registry,
            manifest_dir=Path(__file__).parent.parent / "contracts" / "manifests",
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def pull_assignment(self) -> dict[str, Any] | None:
        """Fetch the highest-priority pending/assigned assignment for this worker."""
        assignments = self._registry.list_assignments(
            worker_id=self.worker_id, status="assigned"
        )
        if not assignments:
            return None
        assignments.sort(key=lambda a: (a.get("priority", 5), a.get("created_at", 0)))
        return assignments[0]

    def generate_compact(self) -> dict[str, Any]:
        """Generate compact for this worker."""
        return self._compact_gen.generate(self.worker_id)

    def prepare_sandbox(self, repo_url: str | None = None) -> Path:
        """Ensure sandbox exists and is ready."""
        return self._sandbox.create_sandbox(self.worker_id, repo_url=repo_url)

    def write_compact_to_sandbox(self, compact: dict[str, Any]) -> Path:
        """Write WORKER_COMPACT.md into the sandbox."""
        return self._sandbox.write_compact(self.worker_id, compact)

    def run_validation(self) -> dict[str, Any]:
        """Run lint, typecheck, and tests in the sandbox."""
        results: dict[str, Any] = {
            "lint": {"success": False, "stdout": "", "stderr": "ruff not available"},
            "typecheck": {"success": False, "stdout": "", "stderr": "mypy not available"},
            "tests": {"success": False, "stdout": "", "stderr": "pytest not available"},
        }
        try:
            results["lint"] = self._sandbox.run_lint(self.worker_id)
        except Exception as exc:
            results["lint"]["stderr"] = str(exc)
        try:
            results["typecheck"] = self._sandbox.run_typecheck(self.worker_id)
        except Exception as exc:
            results["typecheck"]["stderr"] = str(exc)
        try:
            results["tests"] = self._sandbox.run_tests(self.worker_id)
        except Exception as exc:
            results["tests"]["stderr"] = str(exc)
        results["overall_success"] = all(
            results[k].get("success", False) for k in ("lint", "typecheck", "tests")
        )
        return results

    def build_patch(self) -> str:
        """Generate git diff patch from sandbox."""
        return self._sandbox.build_patch(self.worker_id)

    def submit_patch(
        self,
        assignment_id: str,
        patch_content: str,
        validation_results: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Submit patch proposal + evidence pack to backend."""
        evidence = {
            "worker_id": self.worker_id,
            "validation": validation_results,
            "patch_size": len(patch_content),
            "submitted_at": time.time(),
        }
        return self._registry.submit_patch_proposal(assignment_id, patch_content, evidence)

    def execute_cycle(self, repo_url: str | None = None) -> dict[str, Any]:
        """Execute one full build cycle."""
        log.info("[%s] Starting cycle", self.worker_id)
        cycle_result = {"status": "no_assignment", "assignment_id": None, "patch_size": 0}

        # 1. Pull assignment
        assignment = self.pull_assignment()
        if assignment is None:
            log.info("[%s] No assignments available", self.worker_id)
            return cycle_result

        assignment_id = assignment["assignment_id"]
        module_id = assignment["module_id"]
        cycle_result["assignment_id"] = assignment_id
        log.info("[%s] Picked assignment %s for module %s", self.worker_id, assignment_id, module_id)

        # 2. Update status to in_progress
        self._registry.update_assignment(assignment_id, status="in_progress", started_at=time.time())

        # 3. Generate compact
        compact = self.generate_compact()
        log.info("[%s] Compact generated", self.worker_id)

        # 4. Prepare sandbox
        sandbox_path = self.prepare_sandbox(repo_url)
        self.write_compact_to_sandbox(compact)
        log.info("[%s] Sandbox ready at %s", self.worker_id, sandbox_path)

        # 5. Run validation against the current sandbox contents.
        validation = self.run_validation()
        log.info("[%s] Validation overall=%s", self.worker_id, validation["overall_success"])

        # 6. Build patch (even if empty for now — real worker would have changes)
        patch = self.build_patch()
        cycle_result["patch_size"] = len(patch)
        log.info("[%s] Patch size %d bytes", self.worker_id, len(patch))

        # 7. Submit
        result = self.submit_patch(assignment_id, patch, validation)
        if result:
            cycle_result["status"] = "submitted"
            log.info("[%s] Patch submitted for %s", self.worker_id, assignment_id)
        else:
            cycle_result["status"] = "submit_failed"
            log.error("[%s] Patch submission failed for %s", self.worker_id, assignment_id)

        return cycle_result

    def loop(self, interval: int = 60, max_cycles: int | None = None, repo_url: str | None = None):
        """Run execute_cycle in a loop."""
        cycles = 0
        try:
            while True:
                cycles += 1
                try:
                    self.execute_cycle(repo_url=repo_url)
                except Exception as exc:
                    log.error("[%s] Cycle error: %s", self.worker_id, exc)
                if max_cycles and cycles >= max_cycles:
                    log.info("[%s] Max cycles reached (%d), exiting", self.worker_id, max_cycles)
                    break
                log.info("[%s] Sleeping %ds before next cycle", self.worker_id, interval)
                time.sleep(interval)
        except KeyboardInterrupt:
            log.info("[%s] Interrupted, shutting down", self.worker_id)


# ------------------------------------------------------------------
# CLI entrypoint
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SYLION Worker Runtime")
    parser.add_argument("--worker-id", required=True, help="Worker ID to run as")
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval in seconds")
    parser.add_argument("--max-cycles", type=int, default=None, help="Max cycles before exit")
    parser.add_argument("--repo-url", type=str, default=None, help="Git repo URL to clone")
    parser.add_argument("--sandbox-dir", type=str, default=None, help="Base sandbox directory")
    args = parser.parse_args()

    registry = get_worker_registry(event_bus=get_event_bus())
    sandbox = SandboxManager(base_dir=args.sandbox_dir)
    compact_gen = CompactGenerator(
        worker_registry=registry,
        manifest_dir=Path(__file__).parent.parent / "contracts" / "manifests",
    )
    runtime = WorkerRuntime(
        worker_id=args.worker_id,
        registry=registry,
        sandbox=sandbox,
        compact_generator=compact_gen,
    )

    if args.loop:
        runtime.loop(interval=args.interval, max_cycles=args.max_cycles, repo_url=args.repo_url)
    else:
        result = runtime.execute_cycle(repo_url=args.repo_url)
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
