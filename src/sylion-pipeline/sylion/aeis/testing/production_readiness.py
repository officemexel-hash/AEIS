"""Production readiness runner for AEIS repair-loop governance."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_WARN = "WARN"

REPAIR_PROTOCOL = {
    "command": "AEIS_PRODUCTION_REPAIR_LOOP",
    "rules": [
        "stop_on_first_error",
        "record_blocker_with_evidence",
        "repair_before_next_item",
        "run_PASS1",
        "run_PASS2_same_scope",
        "write_freeze_note_and_evidence_pack",
        "advance_only_after_FROZEN_2X",
    ],
    "ready_rule": "PROD_READY is forbidden while any P0/P1 blocker is FAIL or any required FROZEN_2X evidence is missing.",
}


@dataclass(frozen=True)
class ReadinessRequirement:
    requirement_id: str
    title: str
    priority: str
    evidence_path: str = ""
    kind: str = "freeze_file"
    description: str = ""


@dataclass
class ReadinessResult:
    requirement_id: str
    title: str
    priority: str
    status: str
    evidence: str = ""
    message: str = ""
    next_action: str = ""


@dataclass
class ProductionReadinessReport:
    report_id: str
    project_id: str = ""
    status: str = "BLOCKED"
    can_mark_production_ready: bool = False
    p0_blockers: list[str] = field(default_factory=list)
    p1_blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    results: list[ReadinessResult] = field(default_factory=list)
    repair_protocol: dict[str, Any] = field(default_factory=lambda: dict(REPAIR_PROTOCOL))
    next_blocker: dict[str, Any] | None = None
    generated_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["results"] = [asdict(item) for item in self.results]
        return data


DEFAULT_REQUIREMENTS: tuple[ReadinessRequirement, ...] = (
    ReadinessRequirement("PROD-P0-001", "PostgreSQL required", "P0", "docs/aeis_repair_v2/production_roadmap/PROD_R1_DB_POLICY_PASS12.md"),
    ReadinessRequirement("PROD-P0-002", "Backup and restore drill", "P0", "docs/aeis_repair_v2/production_roadmap/PROD_R1_BACKUP_DR_PRIMITIVES_PASS12.md"),
    ReadinessRequirement("PROD-P0-003", "Vault secret lifecycle", "P0", "docs/aeis_repair_v2/production_roadmap/PROD_R1_SECRET_LIFECYCLE_PASS12.md"),
    ReadinessRequirement("PROD-P0-004", "Backend RBAC enforcement", "P0", "docs/aeis_repair_v2/production_roadmap/PROD_R1_RBAC_AUTH_CONTRACT_PASS12.md"),
    ReadinessRequirement("PROD-P0-005", "Unified Human Gate", "P0", "docs/aeis_repair_v2/production_roadmap/PROD_R2_HUMAN_GATE_RESOLUTION_POLICY_PASS12.md"),
    ReadinessRequirement("PROD-P0-006", "Funding submission gate", "P0", "docs/aeis_repair_v2/production_roadmap/PROD_R2_FUNDING_SUBMISSION_PREVIEW_GATE_PASS12.md"),
    ReadinessRequirement("PROD-P0-007", "Production deploy pipeline", "P0", "docs/aeis_repair_v2/production_roadmap/PROD_R6_PRODUCTION_DEPLOY_PIPELINE_PASS12.md"),
    ReadinessRequirement("PROD-P1-001", "MemoryPlane canonical write", "P1", "docs/aeis_repair_v2/production_roadmap/PROD_R3_MEMORY_PLANE_CANONICAL_WRITE_PASS12.md"),
    ReadinessRequirement("PROD-P1-002", "Evidence Spine artifact registry", "P1", "docs/aeis_repair_v2/production_roadmap/PROD_R3_EVIDENCE_SPINE_ARTIFACT_REGISTRY_PASS12.md"),
    ReadinessRequirement("PROD-P1-003", "Skills integration layer", "P1", "docs/aeis_repair_v2/production_roadmap/PROD_R4_SKILL_INTEGRATION_LAYER_PASS12.md"),
    ReadinessRequirement("PROD-P1-004", "ModelControlPlane", "P1", "docs/aeis_repair_v2/production_roadmap/PROD_R4_MODEL_CONTROL_PLANE_PASS12.md"),
    ReadinessRequirement("PROD-P1-005", "Security headers", "P1", "docs/aeis_repair_v2/production_roadmap/PROD_R1_SECURE_HEADERS_PASS12.md"),
    ReadinessRequirement("PROD-P1-006", "Rate limiting", "P1", "docs/aeis_repair_v2/production_roadmap/PROD_R1_RATE_LIMIT_REDIS_ROLE_PASS12.md"),
    ReadinessRequirement("PROD-P1-007", "Worker fleet lifecycle", "P1", "docs/aeis_repair_v2/production_roadmap/PROD_R6_WORKER_FLEET_LIFECYCLE_PASS12.md"),
    ReadinessRequirement("PROD-P1-008", "Load test 10x peak", "P1", "docs/aeis_repair_v2/production_roadmap/PROD_R7_LOAD_TEST_10X_PASS12.md"),
    ReadinessRequirement("PROD-P2-001", "Mobile identity and audit", "P2", "docs/aeis_repair_v2/production_roadmap/PROD_R2_MOBILE_DEVICE_AUDIT_PASS12.md"),
    ReadinessRequirement("PROD-P2-002", "Autoscaler simulation", "P2", "docs/aeis_repair_v2/production_roadmap/PROD_R6_AUTOSCALER_SIMULATION_PASS12.md"),
    ReadinessRequirement("PROD-P2-003", "Global terminal policy", "P2", "docs/aeis_repair_v2/production_roadmap/PROD_R6_GLOBAL_TERMINAL_POLICY_PASS12.md"),
    ReadinessRequirement("PROD-P2-004", "Route-action closure", "P2", "docs/aeis_repair_v2/production_roadmap/PROD_R7_ROUTE_ACTION_CLOSURE_PASS12.md"),
    ReadinessRequirement("PROD-P2-005", "Operator onboarding", "P2", "docs/aeis_repair_v2/production_roadmap/PROD_R8_OPERATOR_ONBOARDING_PASS12.md"),
)


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[5]


class ProductionReadinessRunner:
    """Evaluates hard production-readiness evidence and records commands."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        db_path: str | Path | None = None,
        event_bus: EventBus | None = None,
        requirements: tuple[ReadinessRequirement, ...] = DEFAULT_REQUIREMENTS,
    ) -> None:
        self.root = (root or repo_root_from_here()).resolve()
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._requirements = requirements
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS production_readiness_runs (
                report_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                can_mark_production_ready INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS production_readiness_commands (
                command_id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL,
                project_id TEXT NOT NULL DEFAULT '',
                actor TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="aeis.testing.production_readiness",
            ))

    def _freeze_file_result(self, requirement: ReadinessRequirement) -> ReadinessResult:
        path = self.root / requirement.evidence_path
        if path.exists():
            return ReadinessResult(
                requirement_id=requirement.requirement_id,
                title=requirement.title,
                priority=requirement.priority,
                status=STATUS_PASS,
                evidence=requirement.evidence_path,
                message="FROZEN_2X evidence found.",
            )
        return ReadinessResult(
            requirement_id=requirement.requirement_id,
            title=requirement.title,
            priority=requirement.priority,
            status=STATUS_FAIL,
            evidence=requirement.evidence_path,
            message="Missing FROZEN_2X production evidence.",
            next_action="Fix implementation, run PASS1 and PASS2, then write freeze note and evidence pack.",
        )

    def _no_mock_result(self) -> ReadinessResult:
        try:
            from sylion.aeis.testing.no_mock_scan import run_no_mock_scan

            scan = run_no_mock_scan(root=self.root, limit=200)
        except Exception as exc:  # noqa: BLE001
            return ReadinessResult(
                requirement_id="PROD-P1-009",
                title="No mock-as-live scan",
                priority="P1",
                status=STATUS_FAIL,
                message=f"No-mock scan failed closed: {exc}",
                next_action="Fix scanner/runtime error, then rerun PASS1/PASS2.",
            )
        if scan.blocking_count:
            return ReadinessResult(
                requirement_id="PROD-P1-009",
                title="No mock-as-live scan",
                priority="P1",
                status=STATUS_FAIL,
                message=f"{scan.blocking_count} blocking mock/demo-as-live issue(s).",
                next_action="Remove fake-success fallback or wire the backend action, then rerun scanner twice.",
            )
        return ReadinessResult(
            requirement_id="PROD-P1-009",
            title="No mock-as-live scan",
            priority="P1",
            status=STATUS_PASS,
            message=f"PASS: scanned {scan.scanned_files} files.",
        )

    def evaluate(self, *, project_id: str = "") -> ProductionReadinessReport:
        results = [self._freeze_file_result(requirement) for requirement in self._requirements]
        results.append(self._no_mock_result())
        p0_blockers = [
            item.requirement_id for item in results
            if item.priority == "P0" and item.status == STATUS_FAIL
        ]
        p1_blockers = [
            item.requirement_id for item in results
            if item.priority == "P1" and item.status == STATUS_FAIL
        ]
        warnings = [
            item.requirement_id for item in results
            if item.priority not in {"P0", "P1"} and item.status == STATUS_FAIL
        ]
        can_ready = not p0_blockers and not p1_blockers and not warnings
        failed = [item for item in results if item.status == STATUS_FAIL]
        next_blocker = None
        if failed:
            priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
            blocker = sorted(failed, key=lambda item: priority_order.get(item.priority, 99))[0]
            next_blocker = asdict(blocker)
        report = ProductionReadinessReport(
            report_id=f"prod_ready_{uuid.uuid4().hex}",
            project_id=project_id,
            status="PROD_READY" if can_ready else "BLOCKED",
            can_mark_production_ready=can_ready,
            p0_blockers=p0_blockers,
            p1_blockers=p1_blockers,
            warnings=warnings,
            results=results,
            next_blocker=next_blocker,
            generated_at=time.time(),
        )
        self._record_report(report)
        return report

    def _record_report(self, report: ProductionReadinessReport) -> None:
        payload = report.to_dict()
        self._conn.execute("""
            INSERT INTO production_readiness_runs
                (report_id, project_id, status, can_mark_production_ready, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            report.report_id,
            report.project_id,
            report.status,
            1 if report.can_mark_production_ready else 0,
            json.dumps(payload, sort_keys=True),
            report.generated_at,
        ))
        self._conn.commit()
        self._emit("production_readiness.evaluated", {
            "report_id": report.report_id,
            "project_id": report.project_id,
            "status": report.status,
            "p0_blockers": report.p0_blockers,
            "p1_blockers": report.p1_blockers,
        })

    def command(self, *, project_id: str = "", actor: str = "operator-dashboard", action: str = "start") -> dict[str, Any]:
        report = self.evaluate(project_id=project_id)
        command_id = f"prod_cmd_{uuid.uuid4().hex}"
        payload = {
            "command_id": command_id,
            "action": action,
            "actor": actor,
            "report_id": report.report_id,
            "status": report.status,
            "allowed_to_continue": report.can_mark_production_ready,
            "repair_protocol": report.repair_protocol,
            "next_blocker": report.next_blocker,
        }
        self._conn.execute("""
            INSERT INTO production_readiness_commands
                (command_id, report_id, project_id, actor, action, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            command_id,
            report.report_id,
            project_id,
            actor,
            action,
            json.dumps(payload, sort_keys=True),
            time.time(),
        ))
        self._conn.commit()
        self._emit("production_readiness.command_recorded", payload)
        return {**payload, "report": report.to_dict()}

    def latest_report(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT payload_json FROM production_readiness_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return json.loads(row["payload_json"]) if row else None


_runner: ProductionReadinessRunner | None = None


def get_production_readiness_runner(
    *,
    root: Path | None = None,
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ProductionReadinessRunner:
    global _runner
    if _runner is None:
        _runner = ProductionReadinessRunner(root=root, db_path=db_path, event_bus=event_bus)
    return _runner


def reset_production_readiness_runner(
    *,
    root: Path | None = None,
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ProductionReadinessRunner | None:
    global _runner
    _runner = None
    if root is not None or db_path is not None or event_bus is not None:
        _runner = ProductionReadinessRunner(root=root, db_path=db_path, event_bus=event_bus)
    return _runner


__all__ = [
    "DEFAULT_REQUIREMENTS",
    "ProductionReadinessRunner",
    "REPAIR_PROTOCOL",
    "get_production_readiness_runner",
    "reset_production_readiness_runner",
]
