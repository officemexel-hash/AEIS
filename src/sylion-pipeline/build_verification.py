"""
SYLION Anti-Hallucination Layer 2: BuildVerification

Runs `go vet`, `go build`, and `go test` after each agent modification
to catch hallucinated code changes that don't compile or break tests.

This layer is invoked by the orchestrator after any agent writes to
the workspace. If the build fails, the change is flagged and optionally
rolled back.

Phase: Enhancement (not a blocker for Phase 1, required for Phase 2-3 autonomy)
Estimated effort: ~200 lines, 1 day
"""

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger("build_verification")


class BuildStatus(str, Enum):
    """Result of a build verification check."""
    PASS = "PASS"
    FAIL_VET = "FAIL_VET"          # go vet failed
    FAIL_BUILD = "FAIL_BUILD"      # go build failed
    FAIL_TEST = "FAIL_TEST"        # go test failed
    SKIPPED = "SKIPPED"            # build verification disabled or no Go files changed
    ERROR = "ERROR"                # internal error (subprocess crash, etc.)


@dataclass
class BuildResult:
    """Outcome of a single build verification run."""
    status: BuildStatus = BuildStatus.SKIPPED
    agent_name: str = ""
    stage: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    vet_output: str = ""
    build_output: str = ""
    test_output: str = ""
    elapsed_seconds: float = 0.0
    changed_files: list[str] = field(default_factory=list)
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "agent_name": self.agent_name,
            "stage": self.stage,
            "timestamp": self.timestamp,
            "vet_output": self.vet_output[:2000],  # Truncate long output
            "build_output": self.build_output[:2000],
            "test_output": self.test_output[:2000],
            "elapsed_seconds": self.elapsed_seconds,
            "changed_files": self.changed_files[:50],
            "error_message": self.error_message,
        }


class BuildVerification:
    """Layer 2 anti-hallucination: compile + test verification after agent changes.

    After each agent writes code to the workspace, this layer runs:
      1. `go vet ./...`           — catches suspicious constructs
      2. `go build ./...`         — catches compilation errors
      3. `go test ./... -count=1` — catches broken tests (optional, configurable)

    If any step fails, the result is flagged and the orchestrator decides
    whether to roll back, retry, or escalate to Human Gate.

    Usage:
        bv = BuildVerification(workspace=Path("/path/to/sylion"))
        result = bv.verify(agent_name="patcher_1", stage="5", changed_files=["pkg/auth/handler.go"])
        if result.status != BuildStatus.PASS:
            # handle failure
    """

    def __init__(
        self,
        workspace: Path,
        *,
        run_tests: bool = True,
        test_timeout_s: int = 120,
        vet_timeout_s: int = 30,
        build_timeout_s: int = 60,
        packages: list[str] | None = None,
        log_dir: Path | None = None,
        env_overrides: dict[str, str] | None = None,
    ):
        """
        Args:
            workspace: Root of the Go workspace.
            run_tests: Whether to also run `go test` (slower but more thorough).
            test_timeout_s: Timeout for `go test`.
            vet_timeout_s: Timeout for `go vet`.
            build_timeout_s: Timeout for `go build`.
            packages: Specific packages to check (default: ./...).
            log_dir: Directory to write verification logs (JSON).
            env_overrides: Extra env vars for Go commands (e.g. CGO_ENABLED=0).
        """
        self.workspace = workspace.resolve()
        self.run_tests = run_tests
        self.test_timeout_s = test_timeout_s
        self.vet_timeout_s = vet_timeout_s
        self.build_timeout_s = build_timeout_s
        self.packages = packages or ["./..."]
        self.log_dir = log_dir
        self.env_overrides = env_overrides or {}

        # Counters
        self._total_checks = 0
        self._total_pass = 0
        self._total_fail = 0
        self._results: list[BuildResult] = []

        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify(
        self,
        agent_name: str,
        stage: str,
        changed_files: list[str] | None = None,
    ) -> BuildResult:
        """Run build verification and return result.

        Args:
            agent_name: Which agent triggered the change.
            stage: Pipeline stage number (e.g. "5" for patch).
            changed_files: List of files modified by the agent.

        Returns:
            BuildResult with status and captured output.
        """
        t0 = time.monotonic()
        self._total_checks += 1

        result = BuildResult(
            agent_name=agent_name,
            stage=stage,
            changed_files=changed_files or [],
        )

        # Skip if no Go files changed
        if changed_files and not any(f.endswith(".go") for f in changed_files):
            result.status = BuildStatus.SKIPPED
            result.elapsed_seconds = time.monotonic() - t0
            log.info(
                "BuildVerification SKIPPED for %s (no .go files changed)",
                agent_name,
            )
            self._save_result(result)
            return result

        pkg_args = " ".join(self.packages)
        env = self._build_env()

        # Step 1: go vet
        vet_ok, vet_out = self._run_command(
            f"go vet {pkg_args}",
            timeout=self.vet_timeout_s,
            env=env,
        )
        result.vet_output = vet_out
        if not vet_ok:
            result.status = BuildStatus.FAIL_VET
            result.elapsed_seconds = time.monotonic() - t0
            self._total_fail += 1
            log.error(
                "BuildVerification FAIL_VET for %s: %s",
                agent_name, vet_out[:500],
            )
            self._save_result(result)
            return result

        # Step 2: go build
        build_ok, build_out = self._run_command(
            f"go build {pkg_args}",
            timeout=self.build_timeout_s,
            env=env,
        )
        result.build_output = build_out
        if not build_ok:
            result.status = BuildStatus.FAIL_BUILD
            result.elapsed_seconds = time.monotonic() - t0
            self._total_fail += 1
            log.error(
                "BuildVerification FAIL_BUILD for %s: %s",
                agent_name, build_out[:500],
            )
            self._save_result(result)
            return result

        # Step 3: go test (optional)
        if self.run_tests:
            test_ok, test_out = self._run_command(
                f"go test {pkg_args} -count=1",
                timeout=self.test_timeout_s,
                env=env,
            )
            result.test_output = test_out
            if not test_ok:
                result.status = BuildStatus.FAIL_TEST
                result.elapsed_seconds = time.monotonic() - t0
                self._total_fail += 1
                log.error(
                    "BuildVerification FAIL_TEST for %s: %s",
                    agent_name, test_out[:500],
                )
                self._save_result(result)
                return result

        # All checks passed
        result.status = BuildStatus.PASS
        result.elapsed_seconds = time.monotonic() - t0
        self._total_pass += 1
        log.info(
            "BuildVerification PASS for %s (%.1fs)",
            agent_name, result.elapsed_seconds,
        )
        self._save_result(result)
        return result

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        return {
            "total_checks": self._total_checks,
            "total_pass": self._total_pass,
            "total_fail": self._total_fail,
            "pass_rate": (
                self._total_pass / self._total_checks
                if self._total_checks > 0
                else 0.0
            ),
        }

    def export_report(self) -> dict[str, Any]:
        """Export full report with all results."""
        return {
            "stats": self.get_stats(),
            "results": [r.to_dict() for r in self._results],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_env(self) -> dict[str, str]:
        """Build environment for Go commands."""
        import os
        env = os.environ.copy()
        env["CGO_ENABLED"] = "0"
        env["GOOS"] = "linux"
        env.update(self.env_overrides)
        return env

    def _run_command(
        self,
        cmd: str,
        timeout: int,
        env: dict[str, str],
    ) -> tuple[bool, str]:
        """Run a shell command and return (success, combined_output).

        IMPORTANT: This runs pre-approved Go toolchain commands only.
        No arbitrary shell execution — only `go vet`, `go build`, `go test`.
        """
        allowed_prefixes = ("go vet", "go build", "go test")
        if not any(cmd.startswith(prefix) for prefix in allowed_prefixes):
            return False, f"BLOCKED: command not in allowlist: {cmd}"

        # Security: use shell=False with shlex.split to prevent injection (v5.8.5 fix)
        import shlex
        try:
            argv = shlex.split(cmd)
        except ValueError as e:
            return False, f"BLOCKED: malformed command: {e}"
        # Re-validate after splitting — first two tokens must be 'go' + verb
        if len(argv) < 2 or argv[0] != "go" or argv[1] not in ("vet", "build", "test"):
            return False, f"BLOCKED: parsed command not in allowlist: {argv}"

        try:
            proc = subprocess.run(
                argv,
                shell=False,
                cwd=str(self.workspace),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            combined = proc.stdout + proc.stderr
            return proc.returncode == 0, combined.strip()

        except subprocess.TimeoutExpired:
            return False, f"TIMEOUT after {timeout}s: {cmd}"
        except OSError as e:
            return False, f"OS error running '{cmd}': {e}"

    def _save_result(self, result: BuildResult) -> None:
        """Persist result to internal list and optionally to disk."""
        self._results.append(result)
        if self.log_dir:
            log_file = self.log_dir / f"build_{result.agent_name}_{result.stage}.json"
            try:
                with open(log_file, "w", encoding="utf-8") as f:
                    json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            except OSError as e:
                log.warning("Failed to write build log to %s: %s", log_file, e)
