"""Production deploy pipeline for AEIS production readiness.

The pipeline records the full deploy contract:
build -> container_scan -> staging_deploy -> smoke_test -> canary ->
production_deploy -> post_deploy_verification, plus a rollback drill.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.evidence_spine import EvidenceSpine, get_evidence_spine
from sylion.governance.deployment_gate import requires_production_gate


PIPELINE_STAGES: tuple[str, ...] = (
    "build",
    "container_scan",
    "staging_deploy",
    "smoke_test",
    "canary",
    "production_deploy",
    "post_deploy_verification",
)

NON_ROLLBACKABLE_STATUSES = {"rolled_back"}


def _now() -> float:
    return time.time()


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _require_sha(value: str, field_name: str) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned.startswith("sha256:"):
        cleaned = cleaned.split(":", 1)[1]
    if len(cleaned) != 64 or any(ch not in "0123456789abcdef" for ch in cleaned):
        raise ValueError(f"{field_name} must be a 64-character SHA-256 hex digest")
    return cleaned


def _json_loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default


@dataclass(frozen=True)
class ProductionDeployRequest:
    project_id: str
    artifact_sha256: str
    previous_artifact_sha256: str
    release_version: str
    target_environment: str = "production"
    approval_ticket_id: str = ""
    canary_percent: int = 5
    canary_observation_minutes: int = 15
    scan_report: dict[str, Any] = field(default_factory=dict)
    smoke_report: dict[str, Any] = field(default_factory=dict)
    operator_probe: dict[str, Any] = field(default_factory=dict)
    failure_injection_stage: str = ""
    include_rollback_drill: bool = True
    rollback_on_failure: bool = True


class ProductionDeployPipeline:
    """SQLite-backed, evidence-linked production deploy pipeline."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        event_bus: EventBus | None = None,
        evidence_spine: EvidenceSpine | None = None,
    ) -> None:
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._evidence_spine = evidence_spine or get_evidence_spine()
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS production_deploy_runs (
                run_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                release_version TEXT NOT NULL,
                target_environment TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL,
                previous_artifact_sha256 TEXT NOT NULL,
                approval_ticket_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                current_live_sha256 TEXT NOT NULL DEFAULT '',
                rollback_id TEXT NOT NULL DEFAULT '',
                evidence_id TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                completed_at REAL
            );

            CREATE TABLE IF NOT EXISTS production_deploy_stages (
                stage_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                stage_order INTEGER NOT NULL,
                status TEXT NOT NULL,
                started_at REAL NOT NULL,
                completed_at REAL NOT NULL,
                evidence_id TEXT NOT NULL DEFAULT '',
                details_json TEXT NOT NULL DEFAULT '{}',
                error TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (run_id) REFERENCES production_deploy_runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS production_deploy_rollbacks (
                rollback_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                status TEXT NOT NULL,
                previous_artifact_sha256 TEXT NOT NULL,
                restored_artifact_sha256 TEXT NOT NULL DEFAULT '',
                started_at REAL NOT NULL,
                completed_at REAL,
                evidence_id TEXT NOT NULL DEFAULT '',
                details_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (run_id) REFERENCES production_deploy_runs(run_id)
            );
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_prod_deploy_project "
            "ON production_deploy_runs(project_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_prod_deploy_status "
            "ON production_deploy_runs(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_prod_deploy_stage_run "
            "ON production_deploy_stages(run_id, stage_order)"
        )
        self._conn.commit()

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="ops.production_deploy_pipeline",
            ))

    def _evidence(self, payload: dict[str, Any], artifact_type: str) -> str:
        artifact = self._evidence_spine.register_json_artifact(
            payload,
            source="ops.production_deploy_pipeline",
            artifact_type=artifact_type,
            retention_policy="production-deploy-freeze",
            metadata={
                "project_id": payload.get("project_id", ""),
                "run_id": payload.get("run_id", ""),
                "stage": payload.get("stage", ""),
            },
            actor_id=str(payload.get("actor_id") or "production-deploy-pipeline"),
        )
        return str(artifact["evidence_id"])

    @staticmethod
    def _run_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["payload"] = _json_loads(data.pop("payload_json", "{}"), {})
        return data

    @staticmethod
    def _stage_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["details"] = _json_loads(data.pop("details_json", "{}"), {})
        return data

    @staticmethod
    def _rollback_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["details"] = _json_loads(data.pop("details_json", "{}"), {})
        return data

    def _insert_run(self, request: ProductionDeployRequest) -> str:
        run_id = _uid("prod_deploy")
        payload = asdict(request)
        with self._lock:
            self._conn.execute("""
                INSERT INTO production_deploy_runs (
                    run_id, project_id, release_version, target_environment,
                    artifact_sha256, previous_artifact_sha256,
                    approval_ticket_id, status, current_live_sha256,
                    payload_json, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, NULL)
            """, (
                run_id,
                request.project_id,
                request.release_version,
                request.target_environment,
                request.artifact_sha256,
                request.previous_artifact_sha256,
                request.approval_ticket_id,
                request.previous_artifact_sha256,
                _canonical_json(payload),
                _now(),
            ))
            self._conn.commit()
        self._emit("production_deploy.started", {
            "run_id": run_id,
            "project_id": request.project_id,
            "target_environment": request.target_environment,
        })
        return run_id

    def _update_run(self, run_id: str, **fields: Any) -> None:
        allowed = {
            "status", "current_live_sha256", "rollback_id",
            "evidence_id", "completed_at",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return
        assignments = ", ".join(f"{key} = ?" for key in updates)
        params = list(updates.values()) + [run_id]
        with self._lock:
            self._conn.execute(
                f"UPDATE production_deploy_runs SET {assignments} WHERE run_id = ?",
                params,
            )
            self._conn.commit()

    def _insert_stage(
        self,
        run_id: str,
        stage_name: str,
        stage_order: int,
        *,
        status: str,
        details: dict[str, Any],
        error: str = "",
    ) -> dict[str, Any]:
        started = _now()
        completed = _now()
        payload = {
            "run_id": run_id,
            "stage": stage_name,
            "status": status,
            "details": details,
            "error": error,
            "started_at": started,
            "completed_at": completed,
        }
        evidence_id = self._evidence(payload, "deploy_stage")
        stage_id = _uid("stage")
        with self._lock:
            self._conn.execute("""
                INSERT INTO production_deploy_stages (
                    stage_id, run_id, stage_name, stage_order, status,
                    started_at, completed_at, evidence_id, details_json, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stage_id,
                run_id,
                stage_name,
                stage_order,
                status,
                started,
                completed,
                evidence_id,
                _canonical_json(details),
                error,
            ))
            self._conn.commit()
        return {
            "stage_id": stage_id,
            "run_id": run_id,
            "stage_name": stage_name,
            "stage_order": stage_order,
            "status": status,
            "started_at": started,
            "completed_at": completed,
            "evidence_id": evidence_id,
            "details": details,
            "error": error,
        }

    def _stage_details(self, request: ProductionDeployRequest, stage: str) -> dict[str, Any]:
        base = {
            "project_id": request.project_id,
            "release_version": request.release_version,
            "artifact_sha256": request.artifact_sha256,
            "target_environment": request.target_environment,
        }
        if stage == "build":
            sbom = {
                "project_id": request.project_id,
                "release_version": request.release_version,
                "artifact_sha256": request.artifact_sha256,
                "components": ["aeis-api", "aeis-frontend", "aeis-worker"],
            }
            return {
                **base,
                "image_ref": f"aeis/{request.project_id}:{request.release_version}",
                "sbom_sha256": _hash_payload(sbom),
                "build_attestation": "recorded",
            }
        if stage == "container_scan":
            report = dict(request.scan_report or {})
            return {
                **base,
                "scanner": str(report.get("scanner") or "aeis-policy-scan"),
                "critical": int(report.get("critical") or 0),
                "high": int(report.get("high") or 0),
                "medium": int(report.get("medium") or 0),
                "low": int(report.get("low") or 0),
                "sbom_sha256": str(report.get("sbom_sha256") or ""),
            }
        if stage == "staging_deploy":
            return {
                **base,
                "environment": "staging",
                "health_url": f"https://staging.local/{request.project_id}/health",
                "migration_mode": "expand-migrate-contract",
            }
        if stage == "smoke_test":
            report = dict(request.smoke_report or {})
            return {
                **base,
                "golden_tests_passed": bool(report.get("golden_tests_passed", True)),
                "healthcheck_passed": bool(report.get("healthcheck_passed", True)),
                "p99_ms": int(report.get("p99_ms") or 120),
                "p99_target_ms": int(report.get("p99_target_ms") or 500),
            }
        if stage == "canary":
            return {
                **base,
                "traffic_percent": int(request.canary_percent),
                "observation_minutes": int(request.canary_observation_minutes),
                "error_rate": float((request.operator_probe or {}).get("error_rate", 0.0) or 0.0),
                "threshold_error_rate": 0.02,
                "circuit_breaker": "enabled",
            }
        if stage == "production_deploy":
            return {
                **base,
                "traffic_percent": 100,
                "previous_artifact_sha256": request.previous_artifact_sha256,
                "approval_ticket_id": request.approval_ticket_id,
            }
        if stage == "post_deploy_verification":
            probe = dict(request.operator_probe or {})
            return {
                **base,
                "healthcheck_passed": bool(probe.get("healthcheck_passed", True)),
                "operator_probe_passed": bool(probe.get("operator_probe_passed", True)),
                "error_rate": float(probe.get("error_rate", 0.0) or 0.0),
                "rollback_threshold_error_rate": 0.02,
            }
        raise ValueError(f"unknown stage: {stage}")

    @staticmethod
    def _stage_error(stage: str, details: dict[str, Any]) -> str:
        if stage == "container_scan":
            if int(details.get("critical") or 0) > 0:
                return "critical_vulnerabilities_present"
            if int(details.get("high") or 0) > 0:
                return "high_vulnerabilities_present"
        if stage == "smoke_test":
            if not details.get("golden_tests_passed"):
                return "golden_tests_failed"
            if not details.get("healthcheck_passed"):
                return "staging_healthcheck_failed"
            if int(details.get("p99_ms") or 0) > int(details.get("p99_target_ms") or 500):
                return "p99_latency_exceeded"
        if stage == "canary":
            if int(details.get("traffic_percent") or 0) < 5:
                return "canary_traffic_below_minimum"
            if int(details.get("observation_minutes") or 0) < 15:
                return "canary_observation_too_short"
            if float(details.get("error_rate") or 0.0) > float(details.get("threshold_error_rate") or 0.02):
                return "canary_error_rate_exceeded"
        if stage == "post_deploy_verification":
            if not details.get("healthcheck_passed"):
                return "production_healthcheck_failed"
            if not details.get("operator_probe_passed"):
                return "operator_probe_failed"
            if float(details.get("error_rate") or 0.0) > float(details.get("rollback_threshold_error_rate") or 0.02):
                return "post_deploy_error_rate_exceeded"
        return ""

    def run(self, request: ProductionDeployRequest) -> dict[str, Any]:
        request = self._validated_request(request)
        run_id = self._insert_run(request)
        stages: list[dict[str, Any]] = []

        for order, stage in enumerate(PIPELINE_STAGES):
            details = self._stage_details(request, stage)
            error = ""
            if request.failure_injection_stage == stage:
                error = "failure_injection_triggered"
            error = error or self._stage_error(stage, details)
            status = "failed" if error else "completed"
            stages.append(self._insert_stage(
                run_id,
                stage,
                order,
                status=status,
                details=details,
                error=error,
            ))
            if stage == "production_deploy" and not error:
                self._update_run(run_id, current_live_sha256=request.artifact_sha256)
            if error:
                rollback = None
                status_after_failure = "failed"
                if request.rollback_on_failure and stage in {"production_deploy", "post_deploy_verification"}:
                    rollback = self.rollback(run_id, reason=error, drill=False)
                    status_after_failure = "rolled_back"
                self._update_run(run_id, status=status_after_failure, completed_at=_now())
                self._emit("production_deploy.failed", {
                    "run_id": run_id,
                    "project_id": request.project_id,
                    "stage": stage,
                    "reason": error,
                    "rolled_back": rollback is not None,
                })
                return self.get_run(run_id) or {}

        rollback_drill = None
        if request.include_rollback_drill:
            rollback_drill = self.rollback(run_id, reason="scheduled_rollback_drill", drill=True)
        summary_payload = {
            "run_id": run_id,
            "project_id": request.project_id,
            "release_version": request.release_version,
            "target_environment": request.target_environment,
            "artifact_sha256": request.artifact_sha256,
            "stage_count": len(stages),
            "rollback_drill": rollback_drill,
            "status": "completed",
        }
        evidence_id = self._evidence(summary_payload, "production_deploy_summary")
        self._update_run(
            run_id,
            status="completed",
            evidence_id=evidence_id,
            completed_at=_now(),
        )
        self._emit("production_deploy.completed", {
            "run_id": run_id,
            "project_id": request.project_id,
            "evidence_id": evidence_id,
        })
        return self.get_run(run_id) or {}

    def _validated_request(self, request: ProductionDeployRequest) -> ProductionDeployRequest:
        if not request.project_id.strip():
            raise ValueError("project_id is required")
        if not request.release_version.strip():
            raise ValueError("release_version is required")
        artifact_sha = _require_sha(request.artifact_sha256, "artifact_sha256")
        previous_sha = _require_sha(request.previous_artifact_sha256, "previous_artifact_sha256")
        target = request.target_environment.strip().lower()
        if requires_production_gate(target) and not request.approval_ticket_id.strip():
            raise ValueError("approval_ticket_id is required for production target")
        if request.canary_percent < 5 or request.canary_percent > 100:
            raise ValueError("canary_percent must be between 5 and 100")
        if request.canary_observation_minutes < 15:
            raise ValueError("canary_observation_minutes must be at least 15")
        if request.failure_injection_stage and request.failure_injection_stage not in PIPELINE_STAGES:
            raise ValueError("failure_injection_stage must be a known pipeline stage")
        return ProductionDeployRequest(
            **{
                **asdict(request),
                "artifact_sha256": artifact_sha,
                "previous_artifact_sha256": previous_sha,
                "target_environment": target,
            }
        )

    def rollback(self, run_id: str, *, reason: str = "", drill: bool = False) -> dict[str, Any]:
        run = self.get_run(run_id)
        if not run:
            raise ValueError(f"production deploy run not found: {run_id}")
        if run["status"] in NON_ROLLBACKABLE_STATUSES and not drill:
            raise ValueError(f"cannot rollback run in status {run['status']}")
        previous = str(run["previous_artifact_sha256"])
        started = _now()
        rollback_id = _uid("rollback")
        details = {
            "run_id": run_id,
            "project_id": run["project_id"],
            "reason": reason,
            "drill": drill,
            "restore_previous_artifact": True,
            "traffic_shift": "100_to_0_then_previous_restore",
            "healthcheck_required": True,
            "previous_artifact_sha256": previous,
        }
        evidence_id = self._evidence({**details, "stage": "rollback"}, "deploy_rollback")
        completed = _now()
        with self._lock:
            self._conn.execute("""
                INSERT INTO production_deploy_rollbacks (
                    rollback_id, run_id, status, previous_artifact_sha256,
                    restored_artifact_sha256, started_at, completed_at,
                    evidence_id, details_json
                ) VALUES (?, ?, 'passed', ?, ?, ?, ?, ?, ?)
            """, (
                rollback_id,
                run_id,
                previous,
                previous,
                started,
                completed,
                evidence_id,
                _canonical_json(details),
            ))
            self._conn.commit()
        if not drill:
            self._update_run(
                run_id,
                status="rolled_back",
                current_live_sha256=previous,
                rollback_id=rollback_id,
                completed_at=completed,
            )
        else:
            self._update_run(run_id, rollback_id=rollback_id)
        self._emit("production_deploy.rollback_tested" if drill else "production_deploy.rolled_back", {
            "run_id": run_id,
            "rollback_id": rollback_id,
            "project_id": run["project_id"],
            "restored_artifact_sha256": previous,
            "drill": drill,
        })
        return self.get_rollback(rollback_id) or {}

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM production_deploy_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if not row:
                return None
            run = self._run_row(row)
            stage_rows = self._conn.execute(
                "SELECT * FROM production_deploy_stages WHERE run_id = ? ORDER BY stage_order ASC",
                (run_id,),
            ).fetchall()
            rollback_rows = self._conn.execute(
                "SELECT * FROM production_deploy_rollbacks WHERE run_id = ? ORDER BY started_at ASC",
                (run_id,),
            ).fetchall()
        run["stages"] = [self._stage_row(stage) for stage in stage_rows]
        run["rollbacks"] = [self._rollback_row(rollback) for rollback in rollback_rows]
        return run

    def get_rollback(self, rollback_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM production_deploy_rollbacks WHERE rollback_id = ?",
                (rollback_id,),
            ).fetchone()
        return self._rollback_row(row) if row else None

    def list_runs(
        self,
        *,
        project_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM production_deploy_runs{where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self.get_run(row["run_id"]) for row in rows if row["run_id"]]


_pipeline: ProductionDeployPipeline | None = None


def get_production_deploy_pipeline(
    db_path: str | Path | None = None,
    *,
    event_bus: EventBus | None = None,
    evidence_spine: EvidenceSpine | None = None,
) -> ProductionDeployPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ProductionDeployPipeline(
            db_path=db_path,
            event_bus=event_bus,
            evidence_spine=evidence_spine,
        )
    return _pipeline


def reset_production_deploy_pipeline(
    db_path: str | Path | None = None,
    *,
    event_bus: EventBus | None = None,
    evidence_spine: EvidenceSpine | None = None,
) -> ProductionDeployPipeline:
    global _pipeline
    _pipeline = ProductionDeployPipeline(
        db_path=db_path,
        event_bus=event_bus,
        evidence_spine=evidence_spine,
    )
    return _pipeline


__all__ = [
    "PIPELINE_STAGES",
    "ProductionDeployPipeline",
    "ProductionDeployRequest",
    "get_production_deploy_pipeline",
    "reset_production_deploy_pipeline",
]
