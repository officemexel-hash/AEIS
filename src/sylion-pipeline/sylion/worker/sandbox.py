"""
SYLION Worker -- Sandbox Manager

Manages isolated working directories for build workers.
Each worker gets its own sandbox (folder or git worktree) where it can:
  - checkout code
  - run local tests
  - build patches
  - without touching the main repo

Supports both local folders (VM on laptop) and git worktrees.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.worker.sandbox")


class SandboxManager:
    """Creates and manages per-worker sandboxes."""

    def __init__(self, base_dir: str | Path | None = None):
        self._base = Path(base_dir) if base_dir else Path(tempfile.gettempdir()) / "sylion_worker_sandboxes"
        self._base.mkdir(parents=True, exist_ok=True)

    def create_sandbox(self, worker_id: str, repo_url: str | None = None) -> Path:
        """Create a fresh sandbox for a worker."""
        sandbox = self._base / worker_id
        if sandbox.exists():
            log.warning("Sandbox %s already exists, reusing", worker_id)
            return sandbox

        sandbox.mkdir(parents=True, exist_ok=True)

        # If repo_url given, clone; otherwise copy current repo
        if repo_url:
            self._run(["git", "clone", repo_url, str(sandbox)], cwd=str(self._base))
        else:
            # Copy current source tree (shallow copy for sandbox isolation)
            src = Path(__file__).parent.parent.parent  # sylion-pipeline dir
            if (src / ".git").exists():
                # Use git worktree for efficiency
                self._run(
                    ["git", "worktree", "add", str(sandbox), "HEAD"],
                    cwd=str(src),
                )
            else:
                shutil.copytree(src, sandbox, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", ".next", "node_modules"))

        log.info("Sandbox created for %s at %s", worker_id, sandbox)
        return sandbox

    def remove_sandbox(self, worker_id: str) -> bool:
        """Remove a worker's sandbox."""
        sandbox = self._base / worker_id
        if not sandbox.exists():
            return False
        try:
            # If it's a git worktree, remove properly
            git_dir = sandbox / ".git"
            if git_dir.is_file() or (sandbox / ".git").exists():
                try:
                    self._run(["git", "worktree", "remove", "-f", str(sandbox)], cwd=str(sandbox.parent))
                except Exception:
                    pass
            if sandbox.exists():
                shutil.rmtree(sandbox, ignore_errors=True)
            log.info("Sandbox removed for %s", worker_id)
            return True
        except Exception as exc:
            log.error("Failed to remove sandbox %s: %s", worker_id, exc)
            return False

    def write_compact(self, worker_id: str, compact: dict[str, Any]) -> Path:
        """Write compact.md into the sandbox."""
        sandbox = self._base / worker_id
        compact_path = sandbox / "WORKER_COMPACT.md"
        from sylion.worker.compact import CompactGenerator
        compact_path.write_text(CompactGenerator.render_markdown_static(compact), encoding="utf-8")
        return compact_path

    def run_command(self, worker_id: str, cmd: list[str], cwd: str | None = None, timeout: int = 300) -> dict[str, Any]:
        """Run a command inside the worker sandbox."""
        sandbox = self._base / worker_id
        workdir = Path(cwd) if cwd else sandbox
        return self._run(cmd, cwd=str(workdir), timeout=timeout)

    def run_tests(self, worker_id: str, test_path: str = "tests/", timeout: int = 300) -> dict[str, Any]:
        """Run pytest in the sandbox."""
        return self.run_command(worker_id, ["python", "-m", "pytest", test_path, "-q", "--tb=short"], timeout=timeout)

    def run_lint(self, worker_id: str, path: str = "sylion", timeout: int = 120) -> dict[str, Any]:
        """Run ruff/flake8 lint in the sandbox."""
        return self.run_command(worker_id, ["python", "-m", "ruff", "check", path], timeout=timeout)

    def run_typecheck(self, worker_id: str, path: str = "sylion", timeout: int = 120) -> dict[str, Any]:
        """Run mypy typecheck in the sandbox."""
        return self.run_command(worker_id, ["python", "-m", "mypy", path, "--ignore-missing-imports"], timeout=timeout)

    def build_patch(self, worker_id: str) -> str:
        """Generate a git diff patch from the sandbox."""
        sandbox = self._base / worker_id
        result = self._run(["git", "diff", "HEAD"], cwd=str(sandbox), check=False)
        return result.get("stdout", "")

    def stage_all(self, worker_id: str) -> dict[str, Any]:
        """Stage all changes in the sandbox."""
        return self.run_command(worker_id, ["git", "add", "-A"])

    def commit(self, worker_id: str, message: str) -> dict[str, Any]:
        """Commit changes in the sandbox (local only)."""
        return self.run_command(worker_id, ["git", "commit", "-m", message])

    def apply_patch(self, worker_id: str, patch_content: str) -> dict[str, Any]:
        """Apply a git diff patch into the sandbox."""
        sandbox = self._base / worker_id
        patch_file = sandbox / "_incoming.patch"
        patch_file.write_text(patch_content, encoding="utf-8")
        result = self._run(["git", "apply", "--check", str(patch_file)], cwd=str(sandbox), check=False)
        if result["success"]:
            result = self._run(["git", "apply", str(patch_file)], cwd=str(sandbox), check=False)
        # Clean up patch file regardless
        try:
            patch_file.unlink()
        except Exception:
            pass
        return result

    def reset_hard(self, worker_id: str) -> dict[str, Any]:
        """Reset sandbox to HEAD (discard all changes)."""
        return self.run_command(worker_id, ["git", "reset", "--hard", "HEAD"])

    def stash(self, worker_id: str) -> dict[str, Any]:
        """Stash changes in the sandbox."""
        return self.run_command(worker_id, ["git", "stash", "-u"])

    def _run(self, cmd: list[str], cwd: str | None = None, timeout: int = 300, check: bool = True) -> dict[str, Any]:
        log.info("[sandbox] %s (cwd=%s)", " ".join(cmd), cwd)
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=check,
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
            }
        except subprocess.CalledProcessError as exc:
            return {
                "returncode": exc.returncode,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "success": False,
            }
        except Exception as exc:
            return {"returncode": -1, "stdout": "", "stderr": str(exc), "success": False}
