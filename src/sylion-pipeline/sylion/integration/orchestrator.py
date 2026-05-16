"""
SYLION Integration -- Orchestrator

Manages candidate builds from worker patch proposals:
  1. Collects completed patch proposals from workers
  2. Creates a candidate build (bundle of patches)
  3. Runs validation: contract tests, smoke tests, lint, typecheck
  4. Checks promotion readiness
  5. Creates evidence pack for governance

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.integration.orchestrator")

VALID_BUILD_STATES = (
    "draft", "validating", "contract_tests_passed", "contract_tests_failed",
    "integration_tests_passed", "integration_tests_failed",
    "smoke_tests_passed", "smoke_tests_failed",
    "lint_passed", "lint_failed",
    "typecheck_passed", "typecheck_failed",
    "ready", "rejected", "promoted",
)


class IntegrationOrchestrator:
    """Orchestrates candidate builds and validation pipelines."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        event_bus: EventBus | None = None,
        worker_registry: Any | None = None,
        sandbox_manager: Any | None = None,
    ):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._worker_registry = worker_registry
        self._sandbox = sandbox_manager
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS candidate_builds (
                build_id          TEXT PRIMARY KEY,
                name              TEXT NOT NULL,
                description       TEXT NOT NULL DEFAULT '',
                status            TEXT NOT NULL DEFAULT 'draft',
                patch_ids         TEXT NOT NULL DEFAULT '[]',
                module_ids        TEXT NOT NULL DEFAULT '[]',
                validation_results TEXT NOT NULL DEFAULT '{}',
                evidence_pack     TEXT,
                error_log         TEXT,
                metadata_json     TEXT NOT NULL DEFAULT '{}',
                created_at        REAL NOT NULL,
                updated_at        REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_build_status ON candidate_builds(status);

            CREATE TABLE IF NOT EXISTS integration_results (
                result_id         TEXT PRIMARY KEY,
                build_id          TEXT NOT NULL,
                stage             TEXT NOT NULL,
                success           INTEGER NOT NULL DEFAULT 0,
                stdout            TEXT,
                stderr            TEXT,
                duration_ms       INTEGER,
                created_at        REAL NOT NULL,
                FOREIGN KEY (build_id) REFERENCES candidate_builds(build_id)
            );
            CREATE INDEX IF NOT EXISTS idx_result_build ON integration_results(build_id);
        """)
        self._conn.commit()

    def _emit(self, topic: str, payload: dict[str, Any]):
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(
                SylionEvent(
                    event_id="",
                    topic=topic,
                    payload=payload,
                    source_module="core.integration",
                )
            )
        except Exception as exc:
            log.warning("EventBus publish failed: %s", exc)

    # ------------------------------------------------------------------
    # Candidate Build CRUD
    # ------------------------------------------------------------------

    def create_candidate_build(
        self,
        name: str,
        description: str = "",
        patch_ids: list[str] | None = None,
        module_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        build_id = f"bld_{uuid.uuid4().hex[:12]}"
        now = time.time()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO candidate_builds
                (build_id, name, description, status, patch_ids, module_ids,
                 validation_results, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    build_id, name, description, "draft",
                    json.dumps(patch_ids or []),
                    json.dumps(module_ids or []),
                    json.dumps({}),
                    json.dumps(metadata or {}),
                    now, now,
                ),
            )
            self._conn.commit()
        self._emit("integration.build.created", {"build_id": build_id, "name": name, "modules": module_ids or []})
        return self.get_candidate_build(build_id)

    def get_candidate_build(self, build_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM candidate_builds WHERE build_id = ?", (build_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_build(row)

    def list_candidate_builds(self, status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM candidate_builds"
        params: list[Any] = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_build(r) for r in rows]

    def update_build_status(self, build_id: str, status: str, error_log: str | None = None) -> dict[str, Any] | None:
        if status not in VALID_BUILD_STATES:
            raise ValueError(f"Invalid status: {status}")
        updates = {"status": status, "updated_at": time.time()}
        if error_log is not None:
            updates["error_log"] = error_log
        cols = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [build_id]
        with self._lock:
            self._conn.execute(
                f"UPDATE candidate_builds SET {cols} WHERE build_id = ?", vals
            )
            self._conn.commit()
        self._emit("integration.build.status_changed", {"build_id": build_id, "status": status})
        return self.get_candidate_build(build_id)

    def delete_candidate_build(self, build_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM candidate_builds WHERE build_id = ?", (build_id,)
            )
            self._conn.commit()
        if cur.rowcount:
            self._emit("integration.build.deleted", {"build_id": build_id})
            return True
        return False

    # ------------------------------------------------------------------
    # Validation pipeline
    # ------------------------------------------------------------------

    def _prepare_build_sandbox(self, build_id: str) -> Path | None:
        """Create sandbox, apply all patches from the build's assignments."""
        if self._sandbox is None or self._worker_registry is None:
            return None
        build = self.get_candidate_build(build_id)
        if not build:
            return None

        # Use build_id as sandbox name
        sandbox_path = self._sandbox.create_sandbox(build_id)
        self._sandbox.reset_hard(build_id)

        # Find assignments with patch proposals for modules in this build
        patch_count = 0
        for module_id in build.get("module_ids", []):
            assignments = self._worker_registry.list_assignments(module_id=module_id, status="completed")
            for asg in assignments:
                patch = asg.get("patch_proposal")
                if patch:
                    result = self._sandbox.apply_patch(build_id, patch)
                    if result["success"]:
                        patch_count += 1
                    else:
                        log.warning("Patch apply failed for %s: %s", asg["assignment_id"], result.get("stderr", ""))

        log.info("Build %s sandbox prepared with %d patches applied", build_id, patch_count)
        return sandbox_path

    def run_validation(self, build_id: str, sandbox_dir: str | Path | None = None) -> dict[str, Any]:
        """Run full validation pipeline for a candidate build."""
        build = self.get_candidate_build(build_id)
        if not build:
            raise ValueError(f"Build {build_id} not found")

        self.update_build_status(build_id, "validating")
        results: dict[str, Any] = {"build_id": build_id, "stages": {}}

        # Prepare sandbox with patches
        build_sandbox = self._prepare_build_sandbox(build_id)
        cwd_override = str(build_sandbox) if build_sandbox else None

        stages = ["contract_tests", "integration_tests", "smoke_tests", "lint", "typecheck"]
        overall_success = True

        for stage in stages:
            result = self._run_stage(build_id, stage, cwd_override)
            results["stages"][stage] = result
            if not result["success"]:
                overall_success = False
                self.update_build_status(build_id, f"{stage}_failed", error_log=result.get("stderr", ""))
                break
            else:
                self.update_build_status(build_id, f"{stage}_passed")

        if overall_success:
            self.update_build_status(build_id, "ready")

        # Store aggregated results
        with self._lock:
            self._conn.execute(
                "UPDATE candidate_builds SET validation_results = ?, updated_at = ? WHERE build_id = ?",
                (json.dumps(results), time.time(), build_id),
            )
            self._conn.commit()

        self._emit("integration.build.validated", {"build_id": build_id, "success": overall_success})
        return results

    def _discover_stage_targets(self, workdir: Path, stage: str) -> list[str]:
        """Discover pytest targets for validation stages that rely on test files."""
        stage_patterns = {
            "contract_tests": ("*contract*.py", "*contracts*.py"),
            "integration_tests": ("*integration*.py", "*api_integration*.py"),
        }
        patterns = stage_patterns.get(stage, ())
        if not patterns:
            return []

        discovered: list[str] = []
        seen: set[str] = set()
        for pattern in patterns:
            for path in workdir.rglob(pattern):
                if not path.is_file():
                    continue
                if not any(part.startswith("tests") for part in path.parts):
                    continue
                resolved = str(path.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)
                discovered.append(resolved)
        return discovered

    def _run_pytest_stage(
        self,
        workdir: Path,
        stage: str,
        timeout_s: int,
    ) -> tuple[bool, str, str]:
        import subprocess

        targets = self._discover_stage_targets(workdir, stage)
        if not targets:
            return (
                False,
                "",
                f"No {stage} targets discovered under {workdir}",
            )

        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *targets],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return proc.returncode == 0, proc.stdout, proc.stderr

    def _run_stage(self, build_id: str, stage: str, cwd: str | None = None) -> dict[str, Any]:
        """Execute a single validation stage against the candidate build sandbox."""
        import subprocess
        start = time.time()

        workdir_path = Path(cwd or Path(__file__).parent.parent).resolve()
        workdir = str(workdir_path)
        stdout = f"{stage} completed successfully"
        stderr = ""
        success = True

        if stage == "lint":
            try:
                proc = subprocess.run(
                    ["python", "-m", "ruff", "check", "sylion"],
                    cwd=workdir,
                    capture_output=True, text=True, timeout=60, check=False,
                )
                stdout = proc.stdout
                stderr = proc.stderr
                success = proc.returncode == 0
            except Exception as exc:
                success = False
                stderr = str(exc)

        elif stage == "typecheck":
            try:
                proc = subprocess.run(
                    ["python", "-m", "mypy", "sylion", "--ignore-missing-imports"],
                    cwd=workdir,
                    capture_output=True, text=True, timeout=120, check=False,
                )
                stdout = proc.stdout
                stderr = proc.stderr
                success = proc.returncode == 0
            except Exception as exc:
                success = False
                stderr = str(exc)

        elif stage == "smoke_tests":
            try:
                import urllib.request
                resp = urllib.request.urlopen("http://localhost:8000/health", timeout=5)
                success = resp.status == 200
                stdout = f"Backend health: OK ({resp.status})"
            except Exception as exc:
                success = False
                stderr = str(exc)

        elif stage == "contract_tests":
            try:
                success, stdout, stderr = self._run_pytest_stage(
                    workdir_path,
                    stage,
                    timeout_s=180,
                )
            except Exception as exc:
                success = False
                stderr = str(exc)

        elif stage == "integration_tests":
            try:
                success, stdout, stderr = self._run_pytest_stage(
                    workdir_path,
                    stage,
                    timeout_s=300,
                )
            except Exception as exc:
                success = False
                stderr = str(exc)

        duration_ms = int((time.time() - start) * 1000)
        result_id = f"res_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO integration_results
                (result_id, build_id, stage, success, stdout, stderr, duration_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (result_id, build_id, stage, int(success), stdout, stderr, duration_ms, time.time()),
            )
            self._conn.commit()
        return {"success": success, "stdout": stdout, "stderr": stderr, "duration_ms": duration_ms}

    # ------------------------------------------------------------------
    # Promotion
    # ------------------------------------------------------------------

    def promote(self, build_id: str) -> dict[str, Any] | None:
        build = self.get_candidate_build(build_id)
        if not build:
            return None
        if build["status"] != "ready":
            raise ValueError(f"Build {build_id} is not ready for promotion (status={build['status']})")
        return self.update_build_status(build_id, "promoted")

    def reject(self, build_id: str, reason: str = "") -> dict[str, Any] | None:
        build = self.get_candidate_build(build_id)
        if not build:
            return None
        with self._lock:
            self._conn.execute(
                "UPDATE candidate_builds SET status = ?, error_log = ?, updated_at = ? WHERE build_id = ?",
                ("rejected", reason, time.time(), build_id),
            )
            self._conn.commit()
        self._emit("integration.build.rejected", {"build_id": build_id, "reason": reason})
        return self.get_candidate_build(build_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_results_for_build(self, build_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM integration_results WHERE build_id = ? ORDER BY created_at ASC",
                (build_id,),
            ).fetchall()
        return [
            {
                "result_id": r["result_id"],
                "build_id": r["build_id"],
                "stage": r["stage"],
                "success": bool(r["success"]),
                "stdout": r["stdout"],
                "stderr": r["stderr"],
                "duration_ms": r["duration_ms"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def _row_to_build(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "build_id": row["build_id"],
            "name": row["name"],
            "description": row["description"],
            "status": row["status"],
            "patch_ids": json.loads(row["patch_ids"]),
            "module_ids": json.loads(row["module_ids"]),
            "validation_results": json.loads(row["validation_results"]),
            "evidence_pack": row["evidence_pack"],
            "error_log": row["error_log"],
            "metadata": json.loads(row["metadata_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_orchestrator_instance: IntegrationOrchestrator | None = None


def get_integration_orchestrator(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
    worker_registry: Any | None = None,
    sandbox_manager: Any | None = None,
) -> IntegrationOrchestrator:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = IntegrationOrchestrator(db_path, event_bus, worker_registry, sandbox_manager)
    return _orchestrator_instance


def reset_integration_orchestrator():
    global _orchestrator_instance
    _orchestrator_instance = None
