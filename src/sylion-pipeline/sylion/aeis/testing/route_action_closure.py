"""Route-action closure checks for production readiness.

The runner verifies that priority operator surfaces do not stop at a
rendered route. Every listed action must have a backend route, a frontend
call path, and the shared client contract for empty responses and errors.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.evidence_spine import EvidenceSpine, get_evidence_spine


STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"


@dataclass(frozen=True)
class RouteActionSpec:
    action_id: str
    surface: str
    frontend_route: str
    method: str
    api_path: str
    surface_paths: tuple[str, ...]
    action_paths: tuple[str, ...]
    required_markers: tuple[str, ...]
    notes: str = ""


@dataclass
class RouteActionResult:
    action_id: str
    surface: str
    frontend_route: str
    method: str
    api_path: str
    status: str
    backend_route_found: bool = False
    frontend_surface_found: bool = False
    frontend_action_found: bool = False
    required_markers_found: list[str] = field(default_factory=list)
    missing_markers: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResponseContractVerdict:
    status: str
    category: str
    ok: bool
    retryable: bool = False
    message: str = ""


@dataclass
class RouteActionClosureReport:
    report_id: str
    status: str
    generated_at: float
    checked_actions: int
    passed_actions: int
    failed_actions: int
    helper_contract_status: str
    response_contract_status: str
    evidence_id: str = ""
    results: list[RouteActionResult] = field(default_factory=list)
    helper_errors: list[str] = field(default_factory=list)
    response_contract: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["results"] = [asdict(item) for item in self.results]
        return data


DEFAULT_ROUTE_ACTION_SPECS: tuple[RouteActionSpec, ...] = (
    RouteActionSpec(
        action_id="advisor.card.action",
        surface="/advisor",
        frontend_route="/advisor",
        method="POST",
        api_path="/api/v1/advisor/cards/{card_id}/actions",
        surface_paths=("src/sylion-frontend/src/app/(app)/advisor/page.tsx",),
        action_paths=(
            "src/sylion-frontend/src/components/v2/widgets/AdvisorCardFeed.tsx",
            "src/sylion-frontend/src/lib/api/advisor.ts",
        ),
        required_markers=("/api/v1/advisor/cards/", "/actions", 'method: "POST"', "catch (err)"),
        notes="Accept/reject/modify card actions must persist through backend advisor routes.",
    ),
    RouteActionSpec(
        action_id="planning.phase28.masterplan",
        surface="/planning",
        frontend_route="/planning",
        method="POST",
        api_path="/api/v1/planning/projects/{project_id}/phase28/generate-masterplan",
        surface_paths=("src/sylion-frontend/src/app/(app)/planning/page.tsx",),
        action_paths=(
            "src/sylion-frontend/src/components/planning/PlanningDashboard.tsx",
            "src/sylion-frontend/src/lib/api/client.ts",
        ),
        required_markers=("generateMasterplan", "generateMasterplanPhase28", "/phase28/generate-masterplan", 'method: "POST"', "catch (err)"),
    ),
    RouteActionSpec(
        action_id="source_of_truth.freeze_canon",
        surface="/source-of-truth",
        frontend_route="/source-of-truth",
        method="POST",
        api_path="/api/v1/projects/{project_id}/canon/freeze",
        surface_paths=("src/sylion-frontend/src/app/(app)/source-of-truth/page.tsx",),
        action_paths=(
            "src/sylion-frontend/src/app/(app)/projects/[projectId]/page.tsx",
            "src/sylion-frontend/src/lib/api/client.ts",
        ),
        required_markers=("handleFreezeCanon", "freezeProjectCanon", "/canon/freeze", 'method: "POST"', "catch (err)"),
        notes="The canonical action lives on the project detail route; the source-of-truth page is the navigation surface.",
    ),
    RouteActionSpec(
        action_id="masterplan.freeze",
        surface="/masterplan",
        frontend_route="/masterplan",
        method="POST",
        api_path="/api/v1/projects/{project_id}/masterplan/freeze",
        surface_paths=("src/sylion-frontend/src/app/(app)/masterplan/page.tsx",),
        action_paths=(
            "src/sylion-frontend/src/app/(app)/projects/[projectId]/page.tsx",
            "src/sylion-frontend/src/lib/api/client.ts",
        ),
        required_markers=("handleFreezeMasterplan", "freezeProjectMasterplan", "/masterplan/freeze", 'method: "POST"', "catch (err)"),
        notes="The canonical action lives on the project detail route; the masterplan page is the navigation surface.",
    ),
    RouteActionSpec(
        action_id="ontology.reload",
        surface="/ontology",
        frontend_route="/ontology",
        method="POST",
        api_path="/api/v1/ontology/reload",
        surface_paths=("src/sylion-frontend/src/app/(app)/ontology/page.tsx",),
        action_paths=(
            "src/sylion-frontend/src/app/(app)/ontology/page.tsx",
            "src/sylion-frontend/src/lib/api/client.ts",
        ),
        required_markers=("reloadOntology", "/api/v1/ontology/reload", 'method: "POST"', "catch (err)"),
    ),
    RouteActionSpec(
        action_id="contracts.list.active",
        surface="/contracts",
        frontend_route="/contracts",
        method="GET",
        api_path="/api/v1/contracts",
        surface_paths=("src/sylion-frontend/src/app/(app)/contracts/page.tsx",),
        action_paths=(
            "src/sylion-frontend/src/lib/api/hooks.ts",
            "src/sylion-frontend/src/lib/api/client.ts",
        ),
        required_markers=("useContractsList", "listContractsActive", "/api/v1/contracts?active_only="),
        notes="Contracts is read-mostly today; the live list must still hit the backend API through the proxy.",
    ),
    RouteActionSpec(
        action_id="contracts.register",
        surface="/contracts",
        frontend_route="/contracts",
        method="POST",
        api_path="/api/v1/contracts",
        surface_paths=("src/sylion-frontend/src/app/(app)/contracts/page.tsx",),
        action_paths=("src/sylion-frontend/src/lib/api/client.ts",),
        required_markers=("registerContract", "/api/v1/contracts", 'method: "POST"'),
        notes="Client mutation path is frozen even before the contracts page exposes a create form.",
    ),
    RouteActionSpec(
        action_id="templates_setup.defaults.apply",
        surface="/templates-setup",
        frontend_route="/templates-setup",
        method="POST",
        api_path="/api/v1/templates-setup/{phase_id}/defaults/apply",
        surface_paths=("src/sylion-frontend/src/app/(app)/templates-setup/page.tsx",),
        action_paths=(
            "src/sylion-frontend/src/components/templates/TemplatesSetupDashboard.tsx",
            "src/sylion-frontend/src/lib/api/client.ts",
        ),
        required_markers=("applyDefaults", "applyTemplatesSetupDefaults", "/defaults/apply", 'method: "POST"', "catch (err)"),
    ),
    RouteActionSpec(
        action_id="environments.create",
        surface="/environments",
        frontend_route="/environments",
        method="POST",
        api_path="/api/v1/environment-catalog/environments",
        surface_paths=("src/sylion-frontend/src/app/(app)/environments/page.tsx",),
        action_paths=(
            "src/sylion-frontend/src/app/(app)/environments/page.tsx",
            "src/sylion-frontend/src/lib/api/client.ts",
        ),
        required_markers=("createEnvironmentCatalogEntry", "/api/v1/environment-catalog/environments", 'method: "POST"', "catch"),
    ),
)


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[5]


def _normalize_path(path: str) -> str:
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return path


def _route_signature(path: str) -> str:
    return re.sub(r"\{[^}/]+\}", "{}", _normalize_path(path))


def classify_action_response(
    status_code: int,
    body: str | bytes | None = "",
    *,
    network_error: str = "",
    timeout: bool = False,
) -> ResponseContractVerdict:
    if timeout:
        return ResponseContractVerdict(
            status=STATUS_FAIL,
            category="timeout",
            ok=False,
            retryable=True,
            message="Frontend must surface timeout as an action error.",
        )
    if network_error:
        return ResponseContractVerdict(
            status=STATUS_FAIL,
            category="transport_error",
            ok=False,
            retryable=True,
            message=network_error,
        )
    if status_code == 204:
        return ResponseContractVerdict(
            status=STATUS_PASS,
            category="no_content_success",
            ok=True,
            message="204/empty body is a valid success and must not call response.json().",
        )
    if 200 <= status_code < 300:
        text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body or "")
        return ResponseContractVerdict(
            status=STATUS_PASS,
            category="json_or_text_success" if text.strip() else "empty_success",
            ok=True,
        )
    if status_code in {401, 403}:
        return ResponseContractVerdict(
            status=STATUS_FAIL,
            category="authorization_error",
            ok=False,
            retryable=False,
            message=f"API {status_code}",
        )
    if status_code >= 500:
        return ResponseContractVerdict(
            status=STATUS_FAIL,
            category="server_error",
            ok=False,
            retryable=True,
            message=f"API {status_code}",
        )
    return ResponseContractVerdict(
        status=STATUS_FAIL,
        category="client_error",
        ok=False,
        retryable=False,
        message=f"API {status_code}",
    )


class RouteActionClosureRunner:
    def __init__(
        self,
        *,
        root: str | Path | None = None,
        app: Any | None = None,
        specs: tuple[RouteActionSpec, ...] = DEFAULT_ROUTE_ACTION_SPECS,
        evidence_spine: EvidenceSpine | None = None,
    ) -> None:
        self.root = (Path(root) if root else repo_root_from_here()).resolve()
        self.app = app
        self.specs = specs
        self.evidence_spine = evidence_spine or get_evidence_spine()

    def run(self, *, record_evidence: bool = True) -> RouteActionClosureReport:
        routes = self._collect_routes()
        results = [self._check_spec(spec, routes) for spec in self.specs]
        helper_errors = self._check_frontend_helper_contract()
        response_contract = self._check_response_contract()
        failed = [
            item for item in results
            if item.status != STATUS_PASS
        ]
        if helper_errors:
            failed.append(RouteActionResult(
                action_id="frontend.helper_contract",
                surface="shared_client",
                frontend_route="shared_client",
                method="N/A",
                api_path="N/A",
                status=STATUS_FAIL,
                errors=helper_errors,
            ))
        if response_contract["status"] != STATUS_PASS:
            failed.append(RouteActionResult(
                action_id="frontend.response_contract",
                surface="shared_client",
                frontend_route="shared_client",
                method="N/A",
                api_path="N/A",
                status=STATUS_FAIL,
                errors=response_contract.get("errors", []),
            ))

        report = RouteActionClosureReport(
            report_id=f"route_action_{int(time.time() * 1000)}",
            status=STATUS_FAIL if failed else STATUS_PASS,
            generated_at=time.time(),
            checked_actions=len(results),
            passed_actions=sum(1 for item in results if item.status == STATUS_PASS),
            failed_actions=sum(1 for item in results if item.status != STATUS_PASS),
            helper_contract_status=STATUS_FAIL if helper_errors else STATUS_PASS,
            response_contract_status=response_contract["status"],
            results=results,
            helper_errors=helper_errors,
            response_contract=response_contract,
        )
        if record_evidence:
            artifact = self.evidence_spine.register_json_artifact(
                report.to_dict(),
                source="testing.route_action_closure",
                artifact_type="route_action_closure",
                retention_policy="production-route-action-closure",
                metadata={
                    "status": report.status,
                    "checked_actions": report.checked_actions,
                    "failed_actions": report.failed_actions,
                },
                actor_id="production-readiness-runner",
            )
            report.evidence_id = str(artifact.get("evidence_id") or "")
        return report

    def _collect_routes(self) -> set[tuple[str, str]]:
        app = self.app
        if app is None:
            from sylion.api.app import app as fastapi_app
            app = fastapi_app

        routes: set[tuple[str, str]] = set()
        for route in getattr(app, "routes", []):
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", None) or []
            if not path or not methods:
                continue
            signature = _route_signature(path)
            for method in methods:
                method = str(method).upper()
                if method in {"HEAD", "OPTIONS"}:
                    continue
                routes.add((method, signature))
        return routes

    def _check_spec(
        self,
        spec: RouteActionSpec,
        routes: set[tuple[str, str]],
    ) -> RouteActionResult:
        result = RouteActionResult(
            action_id=spec.action_id,
            surface=spec.surface,
            frontend_route=spec.frontend_route,
            method=spec.method,
            api_path=spec.api_path,
            status=STATUS_PASS,
        )
        result.backend_route_found = (spec.method.upper(), _route_signature(spec.api_path)) in routes
        if not result.backend_route_found:
            result.errors.append(f"missing backend route: {spec.method.upper()} {spec.api_path}")

        surface_files = [self.root / rel for rel in spec.surface_paths]
        action_files = [self.root / rel for rel in spec.action_paths]
        result.frontend_surface_found = all(path.is_file() for path in surface_files)
        if not result.frontend_surface_found:
            missing = [str(path.relative_to(self.root)) for path in surface_files if not path.is_file()]
            result.errors.append(f"missing frontend surface file(s): {missing}")

        existing_action_files = [path for path in action_files if path.is_file()]
        result.frontend_action_found = bool(existing_action_files)
        if not result.frontend_action_found:
            missing = [str(path.relative_to(self.root)) for path in action_files]
            result.errors.append(f"missing frontend action file(s): {missing}")
        content = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in existing_action_files)
        for marker in spec.required_markers:
            if marker in content:
                result.required_markers_found.append(marker)
            else:
                result.missing_markers.append(marker)
        if result.missing_markers:
            result.errors.append(f"missing frontend marker(s): {result.missing_markers}")

        if result.errors:
            result.status = STATUS_FAIL
        return result

    def _check_frontend_helper_contract(self) -> list[str]:
        helper_paths = (
            self.root / "src/sylion-frontend/src/lib/api/client.ts",
            self.root / "src/sylion-frontend/src/lib/api/advisor.ts",
        )
        errors: list[str] = []
        for path in helper_paths:
            if not path.is_file():
                errors.append(f"missing frontend helper: {path.relative_to(self.root)}")
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            if "if (!text.trim()) return undefined as T;" not in content:
                errors.append(f"{path.relative_to(self.root)} does not handle 204/empty body safely")
            if "throw new Error(" not in content or "res.status" not in content:
                errors.append(f"{path.relative_to(self.root)} does not surface non-2xx status")
        return errors

    def _check_response_contract(self) -> dict[str, Any]:
        samples = {
            "no_content_204": classify_action_response(204, ""),
            "forbidden_403": classify_action_response(403, '{"detail":"forbidden"}'),
            "server_500": classify_action_response(500, "boom"),
            "network_error": classify_action_response(0, "", network_error="ECONNRESET"),
            "timeout": classify_action_response(0, "", timeout=True),
        }
        expected = {
            "no_content_204": ("no_content_success", True),
            "forbidden_403": ("authorization_error", False),
            "server_500": ("server_error", False),
            "network_error": ("transport_error", False),
            "timeout": ("timeout", False),
        }
        errors: list[str] = []
        payload: dict[str, Any] = {}
        for key, verdict in samples.items():
            payload[key] = asdict(verdict)
            expected_category, expected_ok = expected[key]
            if verdict.category != expected_category or verdict.ok is not expected_ok:
                errors.append(f"{key}: expected ({expected_category}, {expected_ok}), got ({verdict.category}, {verdict.ok})")
        return {
            "status": STATUS_FAIL if errors else STATUS_PASS,
            "cases": payload,
            "errors": errors,
        }


__all__ = [
    "DEFAULT_ROUTE_ACTION_SPECS",
    "ResponseContractVerdict",
    "RouteActionClosureReport",
    "RouteActionClosureRunner",
    "RouteActionResult",
    "RouteActionSpec",
    "classify_action_response",
]
