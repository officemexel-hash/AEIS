"""Operator onboarding production-readiness probe."""

from __future__ import annotations

import shutil
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from sylion.core.evidence_spine import EvidenceSpine, get_evidence_spine


STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
MAX_ONBOARDING_MINUTES = 15.0


@dataclass
class OnboardingProbeStep:
    name: str
    method: str
    path: str
    status_code: int
    ok: bool
    elapsed_ms: float
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class OperatorOnboardingReport:
    report_id: str
    status: str
    operator_id: str
    elapsed_seconds: float
    elapsed_minutes: float
    max_minutes: float
    checked_steps: int
    passed_steps: int
    failed_steps: int
    frontend_contract_status: str
    acceptance_status: str
    has_completed: bool
    workspace_folder_count: int
    secrets_redacted: bool
    evidence_id: str = ""
    steps: list[OnboardingProbeStep] = field(default_factory=list)
    frontend_errors: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    acceptance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [asdict(step) for step in self.steps]
        return data


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[5]


def assess_duration(elapsed_seconds: float, max_minutes: float = MAX_ONBOARDING_MINUTES) -> bool:
    return elapsed_seconds <= max_minutes * 60.0


@contextmanager
def _patched_advisor_audit_dir(audit_dir: Path):
    import sylion.api.advisor_routes as advisor_routes

    audit_dir.mkdir(parents=True, exist_ok=True)
    old_dir = advisor_routes.resolve_audit_chain_dir
    old_path = advisor_routes.resolve_audit_chain_path
    advisor_routes.resolve_audit_chain_dir = lambda default=None: audit_dir
    advisor_routes.resolve_audit_chain_path = lambda filename, default_dir=None: audit_dir / filename
    try:
        yield
    finally:
        advisor_routes.resolve_audit_chain_dir = old_dir
        advisor_routes.resolve_audit_chain_path = old_path


def _json_response(response: Any) -> dict[str, Any]:
    try:
        data = response.json()
    except Exception:
        return {"text": getattr(response, "text", "")}
    return data if isinstance(data, dict) else {"value": data}


class OperatorOnboardingRunner:
    def __init__(
        self,
        *,
        root: str | Path | None = None,
        app: Any | None = None,
        evidence_spine: EvidenceSpine | None = None,
        max_minutes: float = MAX_ONBOARDING_MINUTES,
    ) -> None:
        self.root = (Path(root) if root else repo_root_from_here()).resolve()
        self.app = app
        self.evidence_spine = evidence_spine or get_evidence_spine()
        self.max_minutes = max_minutes

    def run(self, *, record_evidence: bool = True) -> OperatorOnboardingReport:
        app = self.app
        if app is None:
            from sylion.api.app import app as fastapi_app
            app = fastapi_app

        report_id = f"operator_onboarding_{int(time.time() * 1000)}"
        operator_id = f"operator_{report_id}"
        steps: list[OnboardingProbeStep] = []
        errors: list[str] = []
        acceptance: dict[str, Any] = {}
        has_completed = False
        workspace_folder_count = 0
        secrets_redacted = False
        start = time.perf_counter()

        temp_root = Path(tempfile.mkdtemp(prefix="aeis-onboarding-"))
        try:
            audit_dir = temp_root / "audit"
            workspace_path = temp_root / "operator-workspace"
            values = self._operator_values(workspace_path)
            raw_key = str(values["api_keys"][0]["key"])

            with _patched_advisor_audit_dir(audit_dir):
                client = TestClient(app)
                auth_headers = self._operator_auth_headers(operator_id)

                def call(
                    name: str,
                    method: str,
                    path: str,
                    *,
                    json: dict[str, Any] | None = None,
                ) -> dict[str, Any]:
                    request_start = time.perf_counter()
                    response = client.request(
                        method,
                        path,
                        params={"user_id": operator_id},
                        json=json,
                        headers=auth_headers,
                    )
                    elapsed_ms = (time.perf_counter() - request_start) * 1000.0
                    body = _json_response(response)
                    ok = 200 <= response.status_code < 300
                    steps.append(OnboardingProbeStep(
                        name=name,
                        method=method,
                        path=path,
                        status_code=response.status_code,
                        ok=ok,
                        elapsed_ms=elapsed_ms,
                        detail=self._summarize_step(name, body),
                    ))
                    if not ok:
                        errors.append(f"{name}: HTTP {response.status_code} {body}")
                    return body

                call("reset", "DELETE", "/api/v1/advisor/onboarding/state")
                call("system_check", "GET", "/api/v1/advisor/onboarding/phase1/system-check")
                storage = call(
                    "storage_validate",
                    "POST",
                    "/api/v1/advisor/onboarding/phase1/storage/validate",
                    json={"path": str(workspace_path)},
                )
                if storage.get("ok") is not True:
                    errors.append(f"storage_validate: expected ok=true, got {storage}")
                values["workspace_path"] = str(storage.get("path") or workspace_path)
                values["storage_validation"] = storage

                for step, patch in self._step_patches(values):
                    call(
                        f"save_step_{step}",
                        "PUT",
                        f"/api/v1/advisor/onboarding/step/{step}",
                        json={"values": patch},
                    )

                gate = call("model_gate", "GET", "/api/v1/advisor/onboarding/phase1/model-gate")
                if gate.get("passed") is not True:
                    errors.append(f"model_gate: expected passed=true, got {gate}")

                completed = call(
                    "complete_phase1",
                    "POST",
                    "/api/v1/advisor/onboarding/phase1/complete",
                    json={"values": values},
                )
                complete_values = completed.get("values") if isinstance(completed.get("values"), dict) else {}
                completed_keys = complete_values.get("api_keys") if isinstance(complete_values.get("api_keys"), list) else []
                secrets_redacted = bool(
                    completed_keys
                    and isinstance(completed_keys[0], dict)
                    and completed_keys[0].get("key") != raw_key
                    and completed_keys[0].get("key_masked") is True
                )
                if not secrets_redacted:
                    errors.append("complete_phase1: API shortcut secret was not redacted in response")
                workspace = completed.get("workspace_bootstrap") if isinstance(completed.get("workspace_bootstrap"), dict) else {}
                folders = workspace.get("folders") if isinstance(workspace.get("folders"), list) else []
                workspace_folder_count = len(folders)
                if workspace_folder_count < 15:
                    errors.append(f"complete_phase1: expected 15 workspace folders, got {workspace_folder_count}")

                acceptance = call(
                    "acceptance_test",
                    "GET",
                    "/api/v1/advisor/onboarding/phase1/acceptance-test",
                )
                if acceptance.get("accepted") is not True:
                    errors.append(f"acceptance_test: expected accepted=true, got {acceptance}")

                completed_flag = call(
                    "has_completed",
                    "GET",
                    "/api/v1/advisor/onboarding/has_completed",
                )
                has_completed = bool(completed_flag.get("completed"))
                if not has_completed:
                    errors.append("has_completed: expected completed=true")

                state = call("state_after_complete", "GET", "/api/v1/advisor/onboarding/state")
                if not (state.get("phase1_completed_at") or state.get("completed_at")):
                    errors.append("state_after_complete: missing completed_at marker")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

        elapsed_seconds = time.perf_counter() - start
        if not assess_duration(elapsed_seconds, self.max_minutes):
            errors.append(f"duration: exceeded {self.max_minutes} minutes")

        frontend_errors = self.check_frontend_contract()
        if frontend_errors:
            errors.extend(frontend_errors)

        failed_steps = sum(1 for step in steps if not step.ok)
        report = OperatorOnboardingReport(
            report_id=report_id,
            status=STATUS_FAIL if errors or failed_steps else STATUS_PASS,
            operator_id=operator_id,
            elapsed_seconds=round(elapsed_seconds, 3),
            elapsed_minutes=round(elapsed_seconds / 60.0, 3),
            max_minutes=self.max_minutes,
            checked_steps=len(steps),
            passed_steps=sum(1 for step in steps if step.ok),
            failed_steps=failed_steps,
            frontend_contract_status=STATUS_FAIL if frontend_errors else STATUS_PASS,
            acceptance_status=STATUS_PASS if acceptance.get("accepted") is True else STATUS_FAIL,
            has_completed=has_completed,
            workspace_folder_count=workspace_folder_count,
            secrets_redacted=secrets_redacted,
            steps=steps,
            frontend_errors=frontend_errors,
            errors=errors,
            acceptance=acceptance,
        )
        if record_evidence:
            artifact = self.evidence_spine.register_json_artifact(
                report.to_dict(),
                source="testing.operator_onboarding",
                artifact_type="operator_onboarding",
                retention_policy="production-operator-onboarding",
                metadata={
                    "status": report.status,
                    "checked_steps": report.checked_steps,
                    "elapsed_minutes": report.elapsed_minutes,
                },
                actor_id="production-readiness-runner",
            )
            report.evidence_id = str(artifact.get("evidence_id") or "")
        return report

    def check_frontend_contract(self) -> list[str]:
        required = {
            "src/sylion-frontend/src/app/(app)/onboarding/page.tsx": (
                "PHASE1_STEPS",
                'data-testid="onboarding-wizard"',
                "canAdvanceReason",
                "advisorApi.validatePhase1Storage",
                "advisorApi.phase1ModelGate",
                "completePhase1",
                "phase1_acceptance",
            ),
            "src/sylion-frontend/src/lib/hooks/advisor.ts": (
                "advisorApi.completePhase1",
                "Backend jest niedostepny, faza 1 nie zostala zapisana.",
                "writeLocalOnboarding",
                "advisorApi.resetOnboarding",
            ),
            "src/sylion-frontend/src/lib/api/advisor.ts": (
                "/onboarding/phase1/system-check",
                "/onboarding/phase1/storage/validate",
                "/onboarding/phase1/model-gate",
                "/onboarding/phase1/complete",
                "/onboarding/phase1/acceptance-test",
            ),
            "src/sylion-frontend/src/components/onboarding/FirstRunBanner.tsx": (
                "/api/v1/advisor/onboarding/has_completed",
                'data-testid="firstrun-banner"',
                'data-testid="firstrun-banner-cta"',
            ),
        }
        errors: list[str] = []
        for rel, markers in required.items():
            path = self.root / rel
            if not path.is_file():
                errors.append(f"missing frontend onboarding file: {rel}")
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            missing = [marker for marker in markers if marker not in content]
            if missing:
                errors.append(f"{rel} missing marker(s): {missing}")
        return errors

    @staticmethod
    def _operator_auth_headers(operator_id: str) -> dict[str, str]:
        """Mint a real operator token for full-app RBAC middleware probes."""
        try:
            from sylion.governance.roles import get_roles_manager
            from sylion.security.auth_provider import get_auth_provider

            auth = get_auth_provider()
            providers = auth.list_providers(provider_type="local")
            if not providers:
                auth.register_provider("local", provider_type="local", config_json={})
                providers = auth.list_providers(provider_type="local")
            token = auth.authenticate(
                provider_id=providers[0]["provider_id"],
                credentials_json={"user_id": operator_id},
            )["token_id"]

            roles = get_roles_manager()
            existing = [role for role in roles.list_roles() if role["name"] == "operator"]
            role_id = existing[0]["role_id"] if existing else roles.create_role("operator")["role_id"]
            assigned = {role["name"] for role in roles.get_user_roles(operator_id)}
            if "operator" not in assigned:
                roles.assign_role(role_id=role_id, user_id=operator_id, assigned_by="operator-onboarding-runner")
            return {"Authorization": f"Bearer {token}"}
        except Exception:
            return {}

    @staticmethod
    def _operator_values(workspace_path: Path) -> dict[str, Any]:
        return {
            "language": "pl",
            "operator_name": "Production Operator",
            "display_name": "Production Operator",
            "system_name": "production.operator",
            "email_skipped": True,
            "operator_role": "solo",
            "timezone": "Europe/Warsaw",
            "timezone_confirmed": True,
            "workspace_path": str(workspace_path),
            "backup_frequency": "daily",
            "backup_retention_days": 30,
            "security_mode": "low_security",
            "low_security_confirm": "ROZUMIEM",
            "goals": ["internal_apps"],
            "initial_autonomy_preset": "balanced",
            "notification_channel": "in_app",
            "telemetry_consent": False,
            "tutorial_mode": "skip",
            "tutorial_project": "",
            "api_keys": [
                {
                    "id": "phase1-shortcut",
                    "provider": "openai",
                    "key": "sk-phase1-production-readiness-1234567890",
                    "validation_status": "phase1_shortcut",
                }
            ],
            "phase1_api_provider": "openai",
            "demo_mode_accepted": False,
        }

    @staticmethod
    def _step_patches(values: dict[str, Any]) -> tuple[tuple[int, dict[str, Any]], ...]:
        return (
            (1, {"language": values["language"], "timezone": values["timezone"]}),
            (2, {
                "operator_name": values["operator_name"],
                "display_name": values["display_name"],
                "system_name": values["system_name"],
                "email_skipped": values["email_skipped"],
                "operator_role": values["operator_role"],
                "timezone_confirmed": values["timezone_confirmed"],
            }),
            (3, {
                "workspace_path": values["workspace_path"],
                "storage_validation": values["storage_validation"],
                "backup_frequency": values["backup_frequency"],
                "backup_retention_days": values["backup_retention_days"],
            }),
            (4, {
                "security_mode": values["security_mode"],
                "low_security_confirm": values["low_security_confirm"],
            }),
            (5, {
                "goals": values["goals"],
                "initial_autonomy_preset": values["initial_autonomy_preset"],
                "notification_channel": values["notification_channel"],
                "telemetry_consent": values["telemetry_consent"],
            }),
            (6, {
                "tutorial_mode": values["tutorial_mode"],
                "tutorial_project": values["tutorial_project"],
            }),
            (7, {
                "api_keys": values["api_keys"],
                "phase1_api_provider": values["phase1_api_provider"],
                "demo_mode_accepted": values["demo_mode_accepted"],
            }),
        )

    @staticmethod
    def _summarize_step(name: str, body: dict[str, Any]) -> dict[str, Any]:
        if name == "storage_validate":
            return {
                "ok": body.get("ok"),
                "warnings": body.get("warnings", []),
                "errors": body.get("errors", []),
                "path": body.get("path"),
            }
        if name == "model_gate":
            return {
                "passed": body.get("passed"),
                "local_model_count": body.get("local_model_count"),
                "has_api_key": body.get("has_api_key"),
                "demo_mode": body.get("demo_mode"),
            }
        if name == "complete_phase1":
            bootstrap = body.get("workspace_bootstrap") if isinstance(body.get("workspace_bootstrap"), dict) else {}
            acceptance = body.get("phase1_acceptance") if isinstance(body.get("phase1_acceptance"), dict) else {}
            return {
                "phase1_completed_at": bool(body.get("phase1_completed_at")),
                "folder_count": len(bootstrap.get("folders") or []),
                "acceptance": {
                    "accepted": acceptance.get("accepted"),
                    "passed": acceptance.get("passed"),
                    "total": acceptance.get("total"),
                },
            }
        if name == "acceptance_test":
            return {
                "accepted": body.get("accepted"),
                "passed": body.get("passed"),
                "total": body.get("total"),
            }
        if name == "has_completed":
            return {"completed": body.get("completed")}
        if name.startswith("save_step_"):
            return {
                "step": body.get("step"),
                "completed_steps": body.get("completed_steps", []),
            }
        return {key: body.get(key) for key in ("step", "status", "completed") if key in body}


__all__ = [
    "MAX_ONBOARDING_MINUTES",
    "OnboardingProbeStep",
    "OperatorOnboardingReport",
    "OperatorOnboardingRunner",
    "assess_duration",
]
