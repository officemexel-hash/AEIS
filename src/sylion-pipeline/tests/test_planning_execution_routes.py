from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from sylion.api.app import app
from sylion.api import execution_start_routes


client = TestClient(app)
PROJECT_BASE = "/api/v1/project-start"
COUNCIL_BASE = "/api/v1/council-to-ksiega"
PLANNING_BASE = "/api/v1/planning"
EXECUTION_BASE = "/api/v1/execution-start"


def _assert_last_w18_route(
    project: dict,
    *,
    owner: str,
    action: str,
    decision_class: str,
    phase: str = "TWO_PHASE",
) -> dict:
    command = project["execution"]["w18_commands"][-1]
    assert "central_router_error" not in command
    assert command["command_route"]["owner"] == owner
    assert command["command_route"]["target_action"] == action
    assert command["command_route"]["phase"] == phase
    assert command["command_route"]["requires_human_gate"] is (phase == "TWO_PHASE")
    assert command["command_intent"]["decision_class"] == decision_class
    assert command["command_execution"]["status"] in {"completed", "pending_human_gate"}
    return command


def _artifact_text(project_id: str, tmp_path: Path, *parts: str) -> str:
    project_dirs = list((tmp_path / "projects").glob(f"*{project_id.replace('proj_', '')}*"))
    assert project_dirs, f"project artifact directory not found for {project_id}"
    return (project_dirs[0].joinpath(*parts)).read_text(encoding="utf-8").lower()


def _generated_artifact_text(project_id: str, tmp_path: Path) -> str:
    project_dirs = list((tmp_path / "projects").glob(f"*{project_id.replace('proj_', '')}*"))
    assert project_dirs, f"project artifact directory not found for {project_id}"
    root = project_dirs[0]
    chunks = []
    for directory in ["planning", "reports", "code", "coordination", "archive"]:
        base = root / directory
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks).lower()


def _ready_for_planning(monkeypatch, tmp_path: Path, db_name: str = "planning_execution.db") -> str:
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / db_name))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))
    created = client.post(
        f"{PROJECT_BASE}/projects/create",
        json={
            "creation_path": "idea",
            "name": "Customer Y CRM",
            "idea_text": "Build Polish CRM with Stripe, KSeF, GDPR, PL/EN and customer-funded delivery.",
            "customer_context": "Customer Y, Polish jurisdiction, 25 seats",
            "deadline": "2026-06",
            "budget_hint_eur": 3000,
            "template_id": "polish_saas_payment",
        },
    )
    assert created.status_code == 200
    project_id = created.json()["project"]["project_id"]
    assert client.post(f"{PROJECT_BASE}/projects/{project_id}/goals/defaults", json={"operator_id": "operator"}).status_code == 200
    assert client.post(f"{PROJECT_BASE}/projects/{project_id}/scope/defaults", json={"operator_id": "operator"}).status_code == 200
    assert client.post(f"{PROJECT_BASE}/projects/{project_id}/council/defaults", json={"operator_id": "operator"}).status_code == 200
    assert client.post(
        f"{PROJECT_BASE}/projects/{project_id}/council/approve-readiness",
        json={"approved": True, "operator_id": "operator", "notes": "Ready for Group C."},
    ).status_code == 200
    assert client.post(f"{COUNCIL_BASE}/projects/{project_id}/phase20/convene", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{COUNCIL_BASE}/projects/{project_id}/phase21/initial-verdicts", json={"operator_id": "operator"}).status_code == 200
    assert client.post(f"{COUNCIL_BASE}/projects/{project_id}/phase22/deliberate", json={"operator_id": "operator"}).status_code == 200
    assert client.post(f"{COUNCIL_BASE}/projects/{project_id}/phase23/consolidate", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{COUNCIL_BASE}/projects/{project_id}/phase24/generate-book", json={"approved": True, "operator_id": "operator"}).status_code == 200
    phase25 = client.post(f"{COUNCIL_BASE}/projects/{project_id}/phase25/finalize-ksiega", json={"approved": True, "operator_id": "operator"})
    assert phase25.status_code == 200
    assert phase25.json()["project"]["state"] == "READY_FOR_PLANNING"
    return project_id


def _ready_internal_for_planning(monkeypatch, tmp_path: Path, db_name: str = "internal_planning.db") -> str:
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / db_name))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))
    created = client.post(
        f"{PROJECT_BASE}/projects/create",
        json={
            "creation_path": "idea",
            "name": "P1 Mini CRM Local",
            "idea_text": (
                "Stworz prosty lokalny CRM dla freelancera: kontakty, notatki, status leadow, "
                "przypomnienia i eksport CSV. Bez platnosci, bez KSeF, bez deployu, bez VPS, "
                "bez integracji zewnetrznych."
            ),
            "customer_context": "Freelancer solo, lokalne dane testowe, maly budzet testowy.",
            "deadline": "2026-06",
            "budget_hint_eur": 300,
            "template_id": "polish_saas_payment",
        },
    )
    assert created.status_code == 200
    project_id = created.json()["project"]["project_id"]
    assert client.post(f"{PROJECT_BASE}/projects/{project_id}/goals/defaults", json={"operator_id": "operator"}).status_code == 200
    assert client.post(f"{PROJECT_BASE}/projects/{project_id}/scope/defaults", json={"operator_id": "operator"}).status_code == 200
    assert client.post(f"{PROJECT_BASE}/projects/{project_id}/council/defaults", json={"operator_id": "operator"}).status_code == 200
    assert client.post(
        f"{PROJECT_BASE}/projects/{project_id}/council/approve-readiness",
        json={"approved": True, "operator_id": "operator", "notes": "Ready for internal planning."},
    ).status_code == 200
    for endpoint in [
        "phase20/convene",
        "phase21/initial-verdicts",
        "phase22/deliberate",
        "phase23/consolidate",
        "phase24/generate-book",
        "phase25/finalize-ksiega",
    ]:
        assert client.post(f"{COUNCIL_BASE}/projects/{project_id}/{endpoint}", json={"approved": True, "operator_id": "operator"}).status_code == 200
    return project_id


def _ready_for_execution(monkeypatch, tmp_path: Path, db_name: str = "execution_ready.db") -> str:
    project_id = _ready_for_planning(monkeypatch, tmp_path, db_name)
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase26/assign-models", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase27/synthesize-skills", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(
        f"{PLANNING_BASE}/projects/{project_id}/phase28/generate-masterplan",
        json={"approved": True, "operator_id": "operator", "profile_id": "profile_2"},
    ).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase29/generate-test-plan", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase30/preflight-cost", json={"approved": True, "operator_id": "operator"}).status_code == 200
    phase31 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase31/dry-run", json={"approved": True, "operator_id": "operator"})
    assert phase31.status_code == 200
    assert phase31.json()["project"]["state"] == "READY_FOR_BUILD"
    return project_id


def _ready_internal_for_execution(monkeypatch, tmp_path: Path, db_name: str = "internal_execution_ready.db") -> str:
    project_id = _ready_internal_for_planning(monkeypatch, tmp_path, db_name)
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase26/assign-models", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase27/synthesize-skills", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(
        f"{PLANNING_BASE}/projects/{project_id}/phase28/generate-masterplan",
        json={"approved": True, "operator_id": "operator", "profile_id": "profile_2"},
    ).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase29/generate-test-plan", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase30/preflight-cost", json={"approved": True, "operator_id": "operator"}).status_code == 200
    phase31 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase31/dry-run", json={"approved": True, "operator_id": "operator"})
    assert phase31.status_code == 200
    assert phase31.json()["project"]["state"] == "READY_FOR_BUILD"
    return project_id


def _ready_funding_for_execution(monkeypatch, tmp_path: Path, db_name: str = "funding_execution_ready.db") -> str:
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / db_name))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))
    created = client.post(
        f"{PROJECT_BASE}/projects/create",
        json={
            "creation_path": "idea",
            "name": "T2 Funding NGO",
            "idea_text": (
                "Lokalny asystent funding dla NGO: wyszukuje granty i nabory, dopasowuje program finansowania, "
                "tworzy wniosek, sprawdza dokumenty i wymaga HumanGate przed finalnym zlozeniem. "
                "Bez zewnetrznego submitu i bez VPS."
            ),
            "customer_context": "Polska fundacja, lokalny rehearsal, minimalny budzet testowy.",
            "deadline": "2026-06",
            "budget_hint_eur": 300,
            "template_id": "research_experiment",
        },
    )
    assert created.status_code == 200
    project = created.json()["project"]
    assert project["classification"]["project_type"] == "internal_app"
    assert project["classification"]["domain"] == "funding"
    project_id = project["project_id"]
    for endpoint in ["goals/defaults", "scope/defaults", "council/defaults"]:
        assert client.post(f"{PROJECT_BASE}/projects/{project_id}/{endpoint}", json={"operator_id": "operator"}).status_code == 200
    assert client.post(
        f"{PROJECT_BASE}/projects/{project_id}/council/approve-readiness",
        json={"approved": True, "operator_id": "operator", "notes": "Ready for funding planning."},
    ).status_code == 200
    for endpoint in [
        "phase20/convene",
        "phase21/initial-verdicts",
        "phase22/deliberate",
        "phase23/consolidate",
        "phase24/generate-book",
        "phase25/finalize-ksiega",
    ]:
        assert client.post(f"{COUNCIL_BASE}/projects/{project_id}/{endpoint}", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase26/assign-models", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase27/synthesize-skills", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(
        f"{PLANNING_BASE}/projects/{project_id}/phase28/generate-masterplan",
        json={"approved": True, "operator_id": "operator", "profile_id": "profile_2"},
    ).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase29/generate-test-plan", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase30/preflight-cost", json={"approved": True, "operator_id": "operator"}).status_code == 200
    phase31 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase31/dry-run", json={"approved": True, "operator_id": "operator"})
    assert phase31.status_code == 200
    assert phase31.json()["project"]["state"] == "READY_FOR_BUILD"
    return project_id


def _ready_mobile_approval_for_execution(monkeypatch, tmp_path: Path, db_name: str = "mobile_approval_execution_ready.db") -> str:
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / db_name))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))
    created = client.post(
        f"{PROJECT_BASE}/projects/create",
        json={
            "creation_path": "idea",
            "name": "P3 Mobile Approval Queue",
            "idea_text": (
                "Lokalna kolejka zatwierdzen dla operatora: desktop i mobile view, pending approved rejected, "
                "HumanGate, lokalne tokeny urzadzen, audit trail decyzji, bez VPS, bez platnosci, bez zewnetrznego submitu."
            ),
            "customer_context": "Operator testuje zatwierdzanie i odrzucanie decyzji z telefonu lokalnie.",
            "deadline": "2026-07",
            "budget_hint_eur": 400,
            "template_id": "research_experiment",
        },
    )
    assert created.status_code == 200
    project = created.json()["project"]
    assert project["classification"]["project_type"] == "internal_app"
    assert project["classification"]["domain"] == "mobile_approval"
    project_id = project["project_id"]
    for endpoint in ["goals/defaults", "scope/defaults", "council/defaults"]:
        assert client.post(f"{PROJECT_BASE}/projects/{project_id}/{endpoint}", json={"operator_id": "operator"}).status_code == 200
    assert client.post(
        f"{PROJECT_BASE}/projects/{project_id}/council/approve-readiness",
        json={"approved": True, "operator_id": "operator", "notes": "Ready for mobile approval planning."},
    ).status_code == 200
    for endpoint in [
        "phase20/convene",
        "phase21/initial-verdicts",
        "phase22/deliberate",
        "phase23/consolidate",
        "phase24/generate-book",
        "phase25/finalize-ksiega",
    ]:
        assert client.post(f"{COUNCIL_BASE}/projects/{project_id}/{endpoint}", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase26/assign-models", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase27/synthesize-skills", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(
        f"{PLANNING_BASE}/projects/{project_id}/phase28/generate-masterplan",
        json={"approved": True, "operator_id": "operator", "profile_id": "profile_2"},
    ).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase29/generate-test-plan", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase30/preflight-cost", json={"approved": True, "operator_id": "operator"}).status_code == 200
    phase31 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase31/dry-run", json={"approved": True, "operator_id": "operator"})
    assert phase31.status_code == 200
    assert phase31.json()["project"]["state"] == "READY_FOR_BUILD"
    return project_id


def _ready_automation_runtime_for_planning(monkeypatch, tmp_path: Path, db_name: str = "automation_runtime_planning.db") -> str:
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / db_name))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))
    created = client.post(
        f"{PROJECT_BASE}/projects/create",
        json={
            "creation_path": "idea",
            "name": "P4 Local Automation Runtime",
            "idea_text": (
                "Lokalny runtime automatyzacji bez VPS i bez zewnetrznego deployu: worker registry, kolejka zadan, "
                "retry policy, max parallel, liczba srodowisk, logi, traces, status reporting i guard planned_vps."
            ),
            "customer_context": "Operator testuje lokalne sterowanie runtime, limity workerow i guardy.",
            "deadline": "2026-07",
            "budget_hint_eur": 1200,
            "template_id": "local_automation_runtime",
        },
    )
    assert created.status_code == 200
    project = created.json()["project"]
    assert project["classification"]["project_type"] == "internal_app"
    assert project["classification"]["domain"] == "automation_runtime"
    project_id = project["project_id"]
    for endpoint in ["goals/defaults", "scope/defaults", "council/defaults"]:
        assert client.post(f"{PROJECT_BASE}/projects/{project_id}/{endpoint}", json={"operator_id": "operator"}).status_code == 200
    assert client.post(
        f"{PROJECT_BASE}/projects/{project_id}/council/approve-readiness",
        json={"approved": True, "operator_id": "operator", "notes": "Ready for automation runtime planning."},
    ).status_code == 200
    for endpoint in [
        "phase20/convene",
        "phase21/initial-verdicts",
        "phase22/deliberate",
        "phase23/consolidate",
        "phase24/generate-book",
        "phase25/finalize-ksiega",
    ]:
        assert client.post(f"{COUNCIL_BASE}/projects/{project_id}/{endpoint}", json={"approved": True, "operator_id": "operator"}).status_code == 200
    return project_id


def _ready_multi_domain_for_planning(monkeypatch, tmp_path: Path, db_name: str = "multi_domain_planning.db") -> str:
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / db_name))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))
    created = client.post(
        f"{PROJECT_BASE}/projects/create",
        json={
            "creation_path": "idea",
            "name": "P5 Complex Multi Domain AEIS",
            "idea_text": (
                "Lokalna multi-domain platforma AEIS laczaca CRM, funding assistant, mobile approvals, "
                "automation runtime, governance, HumanGate, audit, memory reuse, skills, guards i council. "
                "Bez deployu, bez VPS, bez external submit, bez platnosci."
            ),
            "customer_context": "Operator testuje pelny lokalny przeplyw wielodomenowy P1-P4.",
            "deadline": "2026-08",
            "budget_hint_eur": 900,
            "template_id": "research_experiment",
        },
    )
    assert created.status_code == 200
    project = created.json()["project"]
    assert project["classification"]["project_type"] == "internal_app"
    assert project["classification"]["domain"] == "aeis_multi_domain"
    project_id = project["project_id"]
    for endpoint in ["goals/defaults", "scope/defaults", "council/defaults"]:
        assert client.post(f"{PROJECT_BASE}/projects/{project_id}/{endpoint}", json={"operator_id": "operator"}).status_code == 200
    assert client.post(
        f"{PROJECT_BASE}/projects/{project_id}/council/approve-readiness",
        json={"approved": True, "operator_id": "operator", "notes": "Ready for multi-domain planning."},
    ).status_code == 200
    for endpoint in [
        "phase20/convene",
        "phase21/initial-verdicts",
        "phase22/deliberate",
        "phase23/consolidate",
        "phase24/generate-book",
        "phase25/finalize-ksiega",
    ]:
        assert client.post(f"{COUNCIL_BASE}/projects/{project_id}/{endpoint}", json={"approved": True, "operator_id": "operator"}).status_code == 200
    return project_id


def _ready_multi_domain_for_execution(monkeypatch, tmp_path: Path, db_name: str = "multi_domain_execution.db") -> str:
    project_id = _ready_multi_domain_for_planning(monkeypatch, tmp_path, db_name)
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase26/assign-models", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase27/synthesize-skills", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(
        f"{PLANNING_BASE}/projects/{project_id}/phase28/generate-masterplan",
        json={"approved": True, "operator_id": "operator", "profile_id": "profile_2"},
    ).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase29/generate-test-plan", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase30/preflight-cost", json={"approved": True, "operator_id": "operator"}).status_code == 200
    phase31 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase31/dry-run", json={"approved": True, "operator_id": "operator"})
    assert phase31.status_code == 200
    assert phase31.json()["project"]["state"] == "READY_FOR_BUILD"
    return project_id


def test_automation_runtime_planning_acceptance_covers_skills_and_work_units(monkeypatch, tmp_path):
    project_id = _ready_automation_runtime_for_planning(monkeypatch, tmp_path)

    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase26/assign-models", json={"approved": True, "operator_id": "operator"}).status_code == 200
    phase27 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase27/synthesize-skills", json={"approved": True, "operator_id": "operator"})
    assert phase27.status_code == 200
    assert phase27.json()["acceptance"]["accepted"] is True
    synthesis = phase27.json()["project"]["planning"]["skill_synthesis"]
    assert len(synthesis["module_skill_assignments"]) == 5
    assert any(item["result"] == "created_project_skill" for item in synthesis["patterns"])

    phase28 = client.post(
        f"{PLANNING_BASE}/projects/{project_id}/phase28/generate-masterplan",
        json={"approved": True, "operator_id": "operator", "profile_id": "profile_2"},
    )
    assert phase28.status_code == 200
    assert phase28.json()["acceptance"]["accepted"] is True
    masterplan = phase28.json()["project"]["planning"]["masterplan"]
    assert len(masterplan["modules"]) == 5
    assert len(masterplan["work_units"]) >= 41
    plan_text = str(masterplan).lower()
    assert "planned_vps_reset" in plan_text
    assert "external_deploy_block" in plan_text


def test_multi_domain_planning_preserves_domains_and_generated_skills(monkeypatch, tmp_path):
    project_id = _ready_multi_domain_for_planning(monkeypatch, tmp_path)

    phase26 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase26/assign-models", json={"approved": True, "operator_id": "operator"})
    assert phase26.status_code == 200
    assert phase26.json()["acceptance"]["accepted"] is True
    matrix = phase26.json()["project"]["planning"]["model_selection"]["assignment_matrix"]
    assert len(matrix) >= 22
    matrix_text = str(matrix).lower()
    for expected in ["multi_domain_router", "funding_workflow", "mobile_approval", "runtime_queue", "memory_reuse", "external_action_guard"]:
        assert expected in matrix_text

    phase27 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase27/synthesize-skills", json={"approved": True, "operator_id": "operator"})
    assert phase27.status_code == 200
    assert phase27.json()["acceptance"]["accepted"] is True
    synthesis = phase27.json()["project"]["planning"]["skill_synthesis"]
    assert len(synthesis["module_skill_assignments"]) == 7
    synthesis_text = str(synthesis).lower()
    for expected in ["pattern_domain_router", "memory reuse", "external action guard"]:
        assert expected in synthesis_text

    phase28 = client.post(
        f"{PLANNING_BASE}/projects/{project_id}/phase28/generate-masterplan",
        json={"approved": True, "operator_id": "operator", "profile_id": "profile_2"},
    )
    assert phase28.status_code == 200
    assert phase28.json()["acceptance"]["accepted"] is True
    masterplan = phase28.json()["project"]["planning"]["masterplan"]
    assert len(masterplan["modules"]) == 7
    assert len(masterplan["work_units"]) >= 50
    plan_text = str(masterplan).lower()
    for expected in ["crm", "funding", "mobile", "automation", "runtime", "governance", "humangate", "memory", "guard"]:
        assert expected in plan_text
    for forbidden in ["stripe", "ksef", "payment integration"]:
        assert forbidden not in plan_text


def test_automation_runtime_blocks_vps_runtime_configuration(monkeypatch, tmp_path):
    project_id = _ready_automation_runtime_for_planning(monkeypatch, tmp_path, "automation_runtime_vps_guard.db")
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase26/assign-models", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase27/synthesize-skills", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(
        f"{PLANNING_BASE}/projects/{project_id}/phase28/generate-masterplan",
        json={"approved": True, "operator_id": "operator", "profile_id": "profile_2"},
    ).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase29/generate-test-plan", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase30/preflight-cost", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase31/dry-run", json={"approved": True, "operator_id": "operator"}).status_code == 200

    response = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/runtime-configuration",
        json={
            "approved": True,
            "operator_id": "operator",
            "topology": "local + VPS",
            "local_workers": 4,
            "vps_workers": 2,
            "environments": 3,
            "max_parallel_workers": 4,
            "max_monthly_vps_eur": 50,
            "allow_paid_vps": True,
        },
    )

    assert response.status_code == 200
    config = response.json()["runtime_configuration"]
    assert config["topology"] == "local-only"
    assert config["vps_workers"] == 0
    assert config["max_monthly_vps_eur"] == 0
    assert config["allow_paid_vps"] is False
    assert config["blocked_external_runtime_request"] is True
    assert config["provisioning_state"] == "external_runtime_request_blocked_local_only"


def test_multi_domain_execution_generates_local_product_and_blocks_vps(monkeypatch, tmp_path):
    project_id = _ready_multi_domain_for_execution(monkeypatch, tmp_path)

    runtime = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/runtime-configuration",
        json={
            "approved": True,
            "operator_id": "operator",
            "topology": "local + VPS",
            "local_workers": 4,
            "vps_workers": 2,
            "environments": 3,
            "max_parallel_workers": 4,
            "max_monthly_vps_eur": 50,
            "allow_paid_vps": True,
        },
    )
    assert runtime.status_code == 200
    config = runtime.json()["runtime_configuration"]
    assert config["topology"] == "local-only"
    assert config["vps_workers"] == 0
    assert config["max_monthly_vps_eur"] == 0
    assert config["allow_paid_vps"] is False
    assert config["blocked_external_runtime_request"] is True

    for phase, endpoint in [
        ("32", "initialize-build"),
        ("33", "start-execution"),
        ("34", "reconvene-council"),
        ("35", "activate-orchestration"),
    ]:
        response = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase{phase}/{endpoint}", json={"approved": True, "operator_id": "operator"})
        assert response.status_code == 200
        assert response.json()["acceptance"]["accepted"] is True

    phase36 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase36/complete-build", json={"approved": True, "operator_id": "operator"})
    assert phase36.status_code == 200
    assert phase36.json()["acceptance"]["accepted"] is True
    project = phase36.json()["project"]
    completion = project["execution"]["build_completion"]
    assert completion["artifacts_inventory"]["product"] == "aeis_multi_domain"
    assert completion["cost_reconciliation"]["local_only"] is True
    assert completion["cost_reconciliation"]["external_spend_usd"] == 0.0

    root = Path(project["shell"]["root"])
    backend = (root / "code" / "repo" / "backend" / "app.py").read_text(encoding="utf-8").lower()
    frontend = (root / "code" / "repo" / "frontend" / "App.tsx").read_text(encoding="utf-8").lower()
    test_app = (root / "code" / "repo" / "backend" / "test_app.py").read_text(encoding="utf-8").lower()
    generated_text = _generated_artifact_text(project_id, tmp_path)
    for expected in ["aeis multi-domain", "crm", "funding", "mobile_approval", "automation_runtime", "memory", "guards", "human_gate_required"]:
        assert expected in backend
    assert "external_action_blocked" in backend
    assert "external_action_blocked" in test_app
    assert "aeis multi-domain local platform" in frontend
    for forbidden in ["stripe", "ksef", "payment integration"]:
        assert forbidden not in generated_text
    assert "hetzner_provisioned\": true" not in generated_text


def test_planning_overview_no_active_project(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "planning_overview.db"))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))

    response = client.get(PLANNING_BASE)

    assert response.status_code == 200
    data = response.json()
    assert data["group"]["id"] == "D"
    assert data["group"]["edge_cases"] == 98
    assert data["active_project"] is None


def test_profile_6_burst_mode_is_listed_but_not_full_masterplan_selectable(monkeypatch, tmp_path):
    project_id = _ready_for_planning(monkeypatch, tmp_path, "profile_6.db")

    profiles = client.get(f"{PLANNING_BASE}/resource-profiles")
    assert profiles.status_code == 200
    profile_6 = next(item for item in profiles.json()["profiles"] if item["id"] == "profile_6")
    assert profile_6["per_phase_only"] is True
    assert profile_6["workers"] == 60
    assert "35" in profile_6["activation_phases"]
    assert profiles.json()["burst_mode_policy"]["requires_operator_gate"] is True

    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase26/assign-models", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase27/synthesize-skills", json={"approved": True, "operator_id": "operator"}).status_code == 200

    rejected = client.post(
        f"{PLANNING_BASE}/projects/{project_id}/phase28/generate-masterplan",
        json={"approved": True, "operator_id": "operator", "profile_id": "profile_6"},
    )
    assert rejected.status_code == 409
    assert "per-phase only" in rejected.json()["detail"]


def test_internal_crm_planning_has_no_payment_or_external_deploy_scope(monkeypatch, tmp_path):
    project_id = _ready_internal_for_planning(monkeypatch, tmp_path, "internal_planning_scope.db")

    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase26/assign-models", json={"approved": True, "operator_id": "operator"}).status_code == 200
    phase26_text = _artifact_text(project_id, tmp_path, "planning", "phase26_model_assignment.json")
    assert "payment_processing" not in phase26_text
    assert "ksef" not in phase26_text
    assert "stripe" not in phase26_text
    phase27 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase27/synthesize-skills", json={"approved": True, "operator_id": "operator"})
    assert phase27.status_code == 200
    assert phase27.json()["acceptance"]["accepted"] is True
    skill_text = str(phase27.json()["project"]["planning"]["skill_synthesis"]).lower()
    assert "ksef" not in skill_text
    assert "stripe" not in skill_text
    assert "payment" not in skill_text

    phase28 = client.post(
        f"{PLANNING_BASE}/projects/{project_id}/phase28/generate-masterplan",
        json={"approved": True, "operator_id": "operator", "profile_id": "profile_2"},
    )
    assert phase28.status_code == 200
    assert phase28.json()["acceptance"]["accepted"] is True
    masterplan = phase28.json()["project"]["planning"]["masterplan"]
    plan_text = str(masterplan).lower()
    assert "ksef" not in plan_text
    assert "stripe" not in plan_text
    assert "payment" not in plan_text
    assert "layer_2_local_storage" in plan_text

    assert client.post(f"{PLANNING_BASE}/projects/{project_id}/phase29/generate-test-plan", json={"approved": True, "operator_id": "operator"}).status_code == 200
    phase30 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase30/preflight-cost", json={"approved": True, "operator_id": "operator"})
    assert phase30.status_code == 200
    phase30_text = _artifact_text(project_id, tmp_path, "planning", "phase30_preflight_cost.json")
    assert "ksef" not in phase30_text
    assert "stripe" not in phase30_text
    assert "payment" not in phase30_text


def test_internal_crm_execution_stays_local_without_payment_ksef_or_vps(monkeypatch, tmp_path):
    project_id = _ready_internal_for_execution(monkeypatch, tmp_path, "internal_execution_scope.db")

    phase32 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase32/initialize-build", json={"approved": True, "operator_id": "operator"})
    assert phase32.status_code == 200
    assert phase32.json()["acceptance"]["accepted"] is True
    init = phase32.json()["project"]["execution"]["build_initialization"]
    assert all(item["type"] == "local" for item in init["environments"])
    assert all(item["requires_action_time_confirmation"] is False for item in init["environments"])

    phase33 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase33/start-execution", json={"approved": True, "operator_id": "operator"})
    assert phase33.status_code == 200
    assert phase33.json()["acceptance"]["accepted"] is True
    sequential = phase33.json()["project"]["execution"]["sequential_execution"]
    execution_text = str(sequential).lower()
    assert "ksef" not in execution_text
    assert "stripe" not in execution_text
    assert "payment integration" not in execution_text
    assert "quality and deploy" not in execution_text
    assert "operator api" in execution_text
    assert "local data contracts" in execution_text
    assert sequential["cost_so_far_usd"] == 0.0
    assert sequential["real_execution_evidence"]["external_actions"] is False
    assert sequential["real_execution_evidence"]["vps_used"] is False

    assert client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase34/reconvene-council", json={"approved": True, "operator_id": "operator"}).status_code == 200
    assert client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase35/activate-orchestration", json={"approved": True, "operator_id": "operator"}).status_code == 200
    phase36 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase36/complete-build", json={"approved": True, "operator_id": "operator"})
    assert phase36.status_code == 200
    assert phase36.json()["acceptance"]["accepted"] is True
    completion = phase36.json()["project"]["execution"]["build_completion"]
    completion_text = str(completion).lower()
    assert "ksef" not in completion_text
    assert "stripe" not in completion_text
    assert "payment integration" not in completion_text
    assert completion["cost_reconciliation"]["local_only"] is True
    assert completion["cost_reconciliation"]["external_spend_usd"] == 0.0

    phase37 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase37/run-quality-gates", json={"approved": True, "operator_id": "operator"})
    assert phase37.status_code == 200
    quality = phase37.json()["project"]["execution"]["quality_gates"]
    assert "invoice" not in str(quality["auto_fix_iterations"]).lower()
    assert "payment" not in str(quality["auto_fix_iterations"]).lower()
    assert quality["costs"]["total_usd"] == 0.0
    assert quality["fixer_runtime_policy"]["source"] == "orchestration_config"
    assert len(quality["auto_fix_iterations"]) <= quality["fixer_runtime_policy"]["max_nogo_iterations"]

    edge_cases = client.get(f"{EXECUTION_BASE}/projects/{project_id}/edge-cases")
    assert edge_cases.status_code == 200
    edge_text = str(edge_cases.json()).lower()
    assert "stripe" not in edge_text
    assert "ksef" not in edge_text
    assert "production vm" not in edge_text
    assert "paid cloud action attempted" in edge_text

    phase38 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase38/complete-acceptance",
        json={"approved": True, "operator_id": "operator", "customer_representative": "Operator lokalny", "signoff_text": "Akceptuje lokalny rehearsal."},
    )
    assert phase38.status_code == 200
    acceptance_text = str(phase38.json()["project"]["execution"]["acceptance_testing"]).lower()
    assert "invoice" not in acceptance_text
    assert "payment" not in acceptance_text

    phase39 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase39/authorize-predeploy",
        json={"approved": True, "operator_id": "operator", "domain": "local-release.local", "authorization_option": "local_rehearsal"},
    )
    assert phase39.status_code == 200
    predeploy_text = str(phase39.json()["project"]["execution"]["predeploy"]).lower()
    assert "ksef" not in predeploy_text
    assert "stripe" not in predeploy_text
    assert "payment" not in predeploy_text

    phase40 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase40/execute-production-deploy",
        json={"approved": True, "operator_id": "operator", "domain": "local-release.local", "strategy": "local_rehearsal"},
    )
    assert phase40.status_code == 200
    deploy = phase40.json()["project"]["execution"]["production_deploy"]
    deploy_text = str(deploy).lower()
    assert "ksef" not in deploy_text
    assert "stripe" not in deploy_text
    assert "payment" not in deploy_text
    assert deploy["observation_24h"]["documents_processed"] == 0
    assert deploy["observation_24h"]["financial_events"] == 0

    phase41 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase41/close-project",
        json={"approved": True, "operator_id": "operator", "closed_date": "2026-06-27", "warranty_start": "2026-06-27", "warranty_end": "2026-07-27"},
    )
    assert phase41.status_code == 200
    closure = phase41.json()["project"]["execution"]["project_closure"]
    closure_text = str(closure).lower()
    assert "ksef" not in closure_text
    assert "stripe" not in closure_text
    assert "payment" not in closure_text
    assert "invoice" not in closure_text
    assert "final_invoice" not in closure
    assert closure["final_settlement"]["generated"] is True
    assert closure["final_settlement"]["external_submission"] is False
    assert closure["closure_email"]["subject"] == "Lokalny pakiet wydania wygenerowany"
    operator_report_text = Path(closure["artifacts"]["operator_report"]["path"]).read_text(encoding="utf-8")
    assert "Raport końcowy operatora" in operator_report_text
    assert "Local release package generated" not in str(closure)
    assert "Operator Final Report" not in operator_report_text

    generated_text = _generated_artifact_text(project_id, tmp_path)
    for forbidden in ["ksef", "stripe", "payment", "invoice", "hetzner"]:
        assert forbidden not in generated_text


def test_orchestration_config_controls_phase26_models_and_phase32_workers(monkeypatch, tmp_path):
    from sylion.aeis.advisor.orchestration_config import service as svc_mod

    svc_mod._STORE.clear()
    svc_mod._SERVICE = None
    try:
        project_id = _ready_internal_for_planning(monkeypatch, tmp_path, "orchestration_config_controls.db")
        service = svc_mod.get_orchestration_service()
        routing = service.get_llm_routing()
        cells = [cell.__dict__ for cell in routing.cells]
        for cell in cells:
            if cell["recommendation_type"] == "architecture" and cell["risk_level"] == "medium":
                cell["model_id"] = "gpt-4o-mini"
                cell["is_default"] = False
        service.update_llm_routing(cells, preset="operator-test")

        dispatch = service.get_dispatch_config()
        dispatch_payload = dispatch.__dict__
        dispatch_payload["parallelism_mode"] = "capped"
        dispatch_payload["max_simultaneous"] = 1
        dispatch_payload["stage_allocation_rules"] = [rule.__dict__ for rule in dispatch.stage_allocation_rules]
        service.update_dispatch_config(dispatch_payload)

        phase26 = client.post(
            f"{PLANNING_BASE}/projects/{project_id}/phase26/assign-models",
            json={"approved": True, "operator_id": "operator"},
        )
        assert phase26.status_code == 200
        matrix = phase26.json()["project"]["planning"]["model_selection"]["assignment_matrix"]
        backend_row = next(row for row in matrix if row["task_type"] == "backend_code")
        assert backend_row["primary_model"] == "gpt-4o-mini"
        assert backend_row["model_source"] == "orchestration_config.llm_judge_routing"

        for phase, endpoint in [
            ("27", "synthesize-skills"),
            ("28", "generate-masterplan"),
            ("29", "generate-test-plan"),
            ("30", "preflight-cost"),
            ("31", "dry-run"),
        ]:
            assert client.post(
                f"{PLANNING_BASE}/projects/{project_id}/phase{phase}/{endpoint}",
                json={"approved": True, "operator_id": "operator"},
            ).status_code == 200

        phase32 = client.post(
            f"{EXECUTION_BASE}/projects/{project_id}/phase32/initialize-build",
            json={"approved": True, "operator_id": "operator"},
        )
        assert phase32.status_code == 200
        profile = phase32.json()["project"]["execution"]["build_initialization"]["profile"]
        assert profile["requested_workers"] >= 2
        assert profile["workers"] == 1
        assert profile["orchestration_dispatch"]["applied"] is True
    finally:
        svc_mod._STORE.clear()
        svc_mod._SERVICE = None


def test_funding_project_generates_funding_assistant_product_not_crm(monkeypatch, tmp_path):
    project_id = _ready_funding_for_execution(monkeypatch, tmp_path, "funding_execution_scope.db")

    for phase, endpoint in [
        ("32", "initialize-build"),
        ("33", "start-execution"),
        ("34", "reconvene-council"),
        ("35", "activate-orchestration"),
    ]:
        response = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase{phase}/{endpoint}", json={"approved": True, "operator_id": "operator"})
        assert response.status_code == 200

    phase36 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase36/complete-build", json={"approved": True, "operator_id": "operator"})
    assert phase36.status_code == 200
    project = phase36.json()["project"]
    completion = project["execution"]["build_completion"]
    assert completion["artifacts_inventory"]["product"] == "funding_assistant"

    root = Path(project["shell"]["root"])
    backend = (root / "code" / "repo" / "backend" / "app.py").read_text(encoding="utf-8").lower()
    frontend = (root / "code" / "repo" / "frontend" / "App.tsx").read_text(encoding="utf-8").lower()
    test_app = (root / "code" / "repo" / "backend" / "test_app.py").read_text(encoding="utf-8").lower()

    assert "aeis local funding assistant" in backend
    assert "from datetime import date" in backend
    assert "human_gate_required" in backend
    assert "external_submit" in backend
    assert "deadline_expired" in backend
    assert "missing_source" in backend
    assert "legal_confirmation_required" in backend
    assert "budget_confirmation_required" in backend
    assert "document_confirmation_required" in backend
    assert "submitted_locally" in test_app
    assert "deadline_expired" in test_app
    assert "legal_confirmation_required" in test_app
    assert "lokalny asystent funding ngo" in frontend
    assert "local crm" not in backend
    assert "contact" not in backend


def test_mobile_approval_project_generates_device_bound_queue_product(monkeypatch, tmp_path):
    project_id = _ready_mobile_approval_for_execution(monkeypatch, tmp_path, "mobile_approval_execution_scope.db")

    for phase, endpoint in [
        ("32", "initialize-build"),
        ("33", "start-execution"),
        ("34", "reconvene-council"),
        ("35", "activate-orchestration"),
    ]:
        response = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase{phase}/{endpoint}", json={"approved": True, "operator_id": "operator"})
        assert response.status_code == 200

    phase36 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase36/complete-build", json={"approved": True, "operator_id": "operator"})
    assert phase36.status_code == 200
    project = phase36.json()["project"]
    completion = project["execution"]["build_completion"]
    assert completion["artifacts_inventory"]["product"] == "mobile_approval_queue"

    root = Path(project["shell"]["root"])
    backend = (root / "code" / "repo" / "backend" / "app.py").read_text(encoding="utf-8").lower()
    frontend = (root / "code" / "repo" / "frontend" / "App.tsx").read_text(encoding="utf-8").lower()
    test_app = (root / "code" / "repo" / "backend" / "test_app.py").read_text(encoding="utf-8").lower()
    forbidden = " ".join(
        path.read_text(encoding="utf-8", errors="replace").lower()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".json", ".md", ".py", ".tsx", ".yml", ".sql"}
    )

    assert "local mobile approval queue" in backend
    assert "blocked_invalid_device" in backend
    assert "approved" in test_app
    assert "rejected" in test_app
    assert "lokalna kolejka zatwierdzen" in frontend
    assert "stripe" not in forbidden
    assert "ksef" not in forbidden
    assert "payment" not in forbidden


def test_windows_runtime_uses_persistent_process_group_backend(monkeypatch):
    monkeypatch.setattr(execution_start_routes.platform, "system", lambda: "Windows")
    monkeypatch.setattr(execution_start_routes.platform, "release", lambda: "11")
    monkeypatch.setattr(execution_start_routes.platform, "machine", lambda: "AMD64")

    def fake_which(command: str) -> str | None:
        return {
            "git": "C:/Program Files/Git/cmd/git.exe",
            "docker": "C:/Program Files/Docker/Docker/resources/bin/docker.exe",
            "powershell": "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            "powershell.exe": "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        }.get(command)

    monkeypatch.setattr(execution_start_routes.shutil, "which", fake_which)
    monkeypatch.setattr(
        execution_start_routes,
        "_docker_runtime_status",
        lambda cli: {"available": True, "state": "daemon_ready", "evidence": "test-daemon"},
    )

    snapshot = execution_start_routes._runtime_capability_snapshot()

    assert snapshot["session_backend"]["id"] == "windows_process_group"
    assert snapshot["features"]["persistent_worker_sessions"] is True
    assert snapshot["features"]["burst_mode_profile_6"] is True
    assert snapshot["runtime_ready"] is True


def test_windows_process_alive_uses_tasklist(monkeypatch):
    monkeypatch.setattr(execution_start_routes.platform, "system", lambda: "Windows")
    monkeypatch.setattr(execution_start_routes.shutil, "which", lambda command: "tasklist.exe" if command == "tasklist" else None)

    monkeypatch.setattr(
        execution_start_routes.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='"powershell.exe","1234","Console","1","10 K"', stderr=""),
    )
    assert execution_start_routes._process_is_alive(1234) is True

    monkeypatch.setattr(
        execution_start_routes.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="INFO: No tasks are running which match the specified criteria.", stderr=""),
    )
    assert execution_start_routes._process_is_alive(1234) is False


def test_live_spawn_status_marks_dead_pid_stopped(monkeypatch):
    project = {
        "execution": {
            "live_worker_sessions": {
                "active": True,
                "sessions": [{"pid": 1234, "state": "running", "log_path": ""}],
            }
        }
    }
    monkeypatch.setattr(execution_start_routes, "_process_is_alive", lambda pid: False)

    status = execution_start_routes._live_spawn_status(project)

    assert status["running"] == 0
    assert status["active"] is False
    assert status["sessions"][0]["state"] == "stopped"


def test_windows_worker_slug_removes_path_invalid_characters():
    slug = execution_start_routes._safe_worker_slug("project_abc::local::1/agent:critic*?")

    assert slug == "project_abc-local-1-agent-critic"
    assert not any(char in slug for char in '<>:"/\\|?*')


def test_execution_start_bridges_project_mode_dashboard_project(monkeypatch, tmp_path):
    import sylion.project_mode.store as project_mode_store

    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "project_mode_bridge.sqlite"))
    monkeypatch.setenv("SYLION_PROJECT_RESULTS_ROOT", str(tmp_path / "project-results"))
    monkeypatch.setattr(project_mode_store, "_store", None)

    created = client.post(
        "/api/v1/projects",
        json={
            "name": "Dashboard bridge project",
            "idea_raw": (
                "Build local-first operator dashboard with API, Quality Gates, adversarial critic, "
                "three local environments and no VPS before Human Gate."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert created.status_code == 200
    project_id = created.json()["project"]["project_id"]

    store = project_mode_store.get_project_mode_store()
    project = store.get_project(project_id)
    assert project is not None
    project["status"] = "completed"
    project["phase"] = "broadcast"
    project["approvals"] = {"book": True, "operating_model": True}
    project["build_authorized_at"] = 1777740000.0
    store.upsert_project(project)

    runtime_config = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/runtime-configuration",
        json={
            "approved": True,
            "operator_id": "operator",
            "topology": "local-first",
            "local_workers": 3,
            "vps_workers": 0,
            "environments": 3,
            "max_parallel_workers": 3,
            "max_monthly_vps_eur": 0,
            "allow_paid_vps": False,
            "apply_to_next_build": True,
        },
    )
    assert runtime_config.status_code == 200
    assert runtime_config.json()["runtime_configuration"]["provisioning_state"] == "local_plan_ready"

    capabilities = client.get(f"{EXECUTION_BASE}/runtime-capabilities")
    assert capabilities.status_code == 200
    payload = capabilities.json()
    assert payload["active_project_id"] == project_id
    assert payload["runtime_configuration"]["configured"] is True
    assert payload["runtime_configuration"]["local_workers"] == 3
    assert payload["runtime_configuration"]["vps_workers"] == 0

    live_status = client.get(f"{EXECUTION_BASE}/projects/{project_id}/phase32/live-spawn-workers")
    assert live_status.status_code == 200
    assert live_status.json()["live_spawn"]["total"] == 0

    project_detail = client.get(f"{EXECUTION_BASE}/projects/{project_id}")
    assert project_detail.status_code == 200
    execution = project_detail.json()["project"]["execution"]
    assert len(execution["build_initialization"]["modern_worker_spawning"]["sessions"]) == 3
    assert execution["build_initialization"]["environments"][2]["label"] == "qa-lab"

    phase32 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase32/initialize-build", json={"approved": True, "operator_id": "operator"})
    assert phase32.status_code == 200
    payload32 = phase32.json()
    assert payload32["acceptance"]["accepted"] is True
    phase32_command = payload32["project"]["execution"]["w18_commands"][-1]
    assert phase32_command["command_route"]["owner"] == "execution_start.phase32"
    assert phase32_command["command_route"]["target_action"] == "initialize_build"
    assert phase32_command["command_execution"]["governance_ticket_id"]
    env_ids = [item["id"] for item in payload32["project"]["execution"]["build_initialization"]["environments"]]
    assert "qa-lab" in env_ids
    assert "prod_ready" not in env_ids

    phase33 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase33/start-execution", json={"approved": True, "operator_id": "operator"})
    assert phase33.status_code == 200
    assert phase33.json()["acceptance"]["accepted"] is True
    phase33_command = phase33.json()["project"]["execution"]["w18_commands"][-1]
    assert phase33_command["command_route"]["owner"] == "execution_start.phase33"
    assert phase33_command["command_route"]["target_action"] == "start_sequential_execution"
    assert phase33_command["command_execution"]["governance_ticket_id"]
    sequential = phase33.json()["project"]["execution"]["sequential_execution"]
    assert sequential["cost_so_far_usd"] == 0
    evidence = sequential["real_execution_evidence"]
    assert evidence["status"] == "live_verified_local"
    assert evidence["workers_completed"] == 3
    assert evidence["artifacts_written"] >= 15
    worker_run = sequential["worker_runs"][0]
    first_worker = worker_run["workers"][0]
    assert Path(first_worker["artifacts"]["code"]["path"]).exists()
    assert Path(first_worker["artifacts"]["diff"]["path"]).exists()
    assert Path(first_worker["artifacts"]["log"]["path"]).exists()
    assert Path(first_worker["artifacts"]["test_result"]["path"]).exists()

    phase34 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase34/reconvene-council", json={"approved": True, "operator_id": "operator"})
    assert phase34.status_code == 200
    council = phase34.json()["project"]["execution"]["mid_build_council"]
    assert council["weighted_vote"]["quorum"]["met"] is True
    assert council["weighted_vote"]["adversarial_critic"]["present"] is True
    assert council["governance_veto"]["enabled"] is True
    assert phase34.json()["project"]["execution"]["model_effectiveness"]["adversarial_critic_tracked"] is True
    assert client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase35/activate-orchestration", json={"approved": True, "operator_id": "operator"}).status_code == 200
    phase36 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase36/complete-build", json={"approved": True, "operator_id": "operator"})
    assert phase36.status_code == 200
    completion = phase36.json()["project"]["execution"]["build_completion"]
    assert completion["cost_reconciliation"]["build_actual_usd"] == 0.0
    assert completion["worker_run_evidence"]["status"] == "completed"
    truth_map = completion["audit_truth_map"]
    assert "LIVE_VERIFIED" in truth_map["classification_vocab"]
    assert truth_map["coverage"]["modules_total"] >= 1
    assert truth_map["status_counts"]["BROKEN"] == 0

    truth_response = client.get(f"{EXECUTION_BASE}/projects/{project_id}/audit-truth-map")
    assert truth_response.status_code == 200
    assert truth_response.json()["truth_map"]["coverage"]["modules_total"] == truth_map["coverage"]["modules_total"]

    phase37 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase37/run-quality-gates", json={"approved": True, "operator_id": "operator"})
    assert phase37.status_code == 200
    quality = phase37.json()["project"]["execution"]["quality_gates"]
    assert "Hetzner" not in quality["performance"]["environment"]
    assert quality["performance"]["environment"] == "local dev, staging, qa-lab"
    assert quality["costs"]["total_usd"] == 0.0
    assert quality["fixer_runtime_policy"]["source"] == "orchestration_config"

    assert client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase38/complete-acceptance",
        json={"approved": True, "operator_id": "operator", "customer_representative": "Operator lokalny", "signoff_text": "Akceptuje lokalny rehearsal."},
    ).status_code == 200
    phase39 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase39/authorize-predeploy",
        json={"approved": True, "operator_id": "operator", "domain": "local-release.local", "authorization_option": "local_rehearsal"},
    )
    assert phase39.status_code == 200
    predeploy = phase39.json()["project"]["execution"]["predeploy"]
    assert predeploy["production_environment"]["provider"] == "local-workspace"
    assert predeploy["production_environment"]["region"] == "qa-lab"
    assert predeploy["production_environment"]["target_environments"] == "dev, staging, qa-lab"
    assert predeploy["production_environment"]["estimated_monthly_eur"] == 0.0
    assert "no_external_submit" in predeploy["authorization"]["scope"]

    phase40 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase40/execute-production-deploy",
        json={"approved": True, "operator_id": "operator", "domain": "local-release.local", "strategy": "local_rehearsal"},
    )
    assert phase40.status_code == 200
    deploy = phase40.json()["project"]["execution"]["production_deploy"]
    assert deploy["external_effects"]["dashboard_executed_external_calls"] is False
    assert deploy["external_effects"]["mode"] == "local_release_rehearsal_no_external_calls"
    assert deploy["production_switch"]["financial_gateway"] == "not_configured_out_of_scope"
    assert deploy["observation_24h"]["documents_processed"] == 0
    assert deploy["observation_24h"]["financial_events"] == 0
    assert deploy["cost_usd"] == 0.0

    phase41 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase41/close-project",
        json={"approved": True, "operator_id": "operator", "closed_date": "2026-06-27", "warranty_start": "2026-06-27", "warranty_end": "2026-07-27"},
    )
    assert phase41.status_code == 200
    assert phase41.json()["acceptance"]["accepted"] is True
    closure = phase41.json()["project"]["execution"]["project_closure"]
    assert closure["reports"]["delivery_mode"] == "local_artifact_only"
    assert closure["closure_email"]["sent"] is False
    assert closure["closure_email"]["subject"] == "Lokalny pakiet wydania wygenerowany"
    assert "final_invoice" not in closure
    assert closure["final_settlement"]["generated"] is True
    assert closure["final_settlement"]["external_submission"] is False


def test_execution_start_uses_canonical_local_environment_count_without_runtime_form(monkeypatch, tmp_path):
    import sylion.project_mode.store as project_mode_store

    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "project_mode_canon_envs.sqlite"))
    monkeypatch.setenv("SYLION_PROJECT_RESULTS_ROOT", str(tmp_path / "project-results"))
    monkeypatch.setattr(project_mode_store, "_store", None)

    created = client.post(
        "/api/v1/projects",
        json={
            "name": "ServiceOps four local envs",
            "idea_raw": (
                "ServiceOps Control Tower local-first with 4 lokalne środowiska "
                "dev/staging/qa-lab/release-lab, zero VPS, zero Hetznera, "
                "zero produkcji, zero external upload and zero external submit."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert created.status_code == 200
    project_id = created.json()["project"]["project_id"]

    store = project_mode_store.get_project_mode_store()
    project = store.get_project(project_id)
    assert project is not None
    assert project["canon_snapshot"]["runtime_constraints"]["local_environment_count"] == 4
    project["status"] = "completed"
    project["phase"] = "broadcast"
    project["approvals"] = {"book": True, "operating_model": True}
    project["build_authorized_at"] = 1777740000.0
    store.upsert_project(project)

    phase32 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase32/initialize-build",
        json={"approved": True, "operator_id": "operator", "notes": "Local-only human dashboard run."},
    )
    assert phase32.status_code == 200
    environments = phase32.json()["project"]["execution"]["build_initialization"]["environments"]
    assert [item["id"] for item in environments] == ["dev", "staging", "qa-lab", "release-lab"]
    assert all(item["type"] == "local" for item in environments)
    assert all(item["requires_action_time_confirmation"] is False for item in environments)

    for phase, endpoint in [
        ("33", "phase33/start-execution"),
        ("34", "phase34/reconvene-council"),
        ("35", "phase35/activate-orchestration"),
        ("36", "phase36/complete-build"),
    ]:
        response = client.post(
            f"{EXECUTION_BASE}/projects/{project_id}/{endpoint}",
            json={"approved": True, "operator_id": "operator", "notes": f"phase {phase} local-only"},
        )
        assert response.status_code == 200

    phase37 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase37/run-quality-gates",
        json={"approved": True, "operator_id": "operator", "notes": "quality local-only"},
    )
    assert phase37.status_code == 200
    quality = phase37.json()["project"]["execution"]["quality_gates"]
    assert quality["performance"]["environment"] == "local dev, staging, qa-lab, release-lab"
    assert quality["summary"]["reruns"] == len(quality["auto_fix_iterations"])

    phase38 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase38/complete-acceptance",
        json={"approved": True, "operator_id": "operator", "customer_representative": "Operator lokalny", "signoff_text": "Akceptuje lokalny rehearsal."},
    )
    assert phase38.status_code == 200
    signoff_path = Path(phase38.json()["project"]["execution"]["acceptance_testing"]["artifacts"]["signoff_form"]["path"])
    assert "dev, staging, qa-lab, release-lab" in signoff_path.read_text(encoding="utf-8")

    phase39 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase39/authorize-predeploy",
        json={"approved": True, "operator_id": "operator", "domain": "local-release.local", "authorization_option": "local_rehearsal"},
    )
    assert phase39.status_code == 200
    predeploy = phase39.json()["project"]["execution"]["predeploy"]
    assert predeploy["production_environment"]["region"] == "release-lab"
    assert predeploy["production_environment"]["target_environments"] == "dev, staging, qa-lab, release-lab"


def test_execution_dispatch_controls_pause_resume_cancel_with_w18_owner(monkeypatch, tmp_path):
    project_id = _ready_internal_for_execution(monkeypatch, tmp_path, "dispatch_controls.db")
    phase32 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase32/initialize-build", json={"approved": True, "operator_id": "operator"})
    assert phase32.status_code == 200
    phase33 = client.post(f"{EXECUTION_BASE}/projects/{project_id}/phase33/start-execution", json={"approved": True, "operator_id": "operator"})
    assert phase33.status_code == 200
    started = phase33.json()
    assert started["dispatch_control"]["state"] == "running"
    assert started["dispatch_control"]["controls_available"]["pause"] is True
    assert started["dispatch_control"]["command_owner_rules"]["active_route_owner"] == "execution_start.dispatch_control"

    status = client.get(f"{EXECUTION_BASE}/projects/{project_id}/phase33/dispatch-control")
    assert status.status_code == 200
    assert status.json()["dispatch_control"]["state"] == "running"

    pause = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase33/pause-dispatch",
        json={"approved": True, "operator_id": "operator", "reason": "audit pause"},
    )
    assert pause.status_code == 200
    pause_payload = pause.json()
    assert pause_payload["dispatch_control"]["state"] == "paused"
    assert pause_payload["dispatch_control"]["controls_available"]["resume"] is True
    assert pause_payload["project"]["execution"]["sequential_execution"]["status"] == "paused"
    _assert_last_w18_route(
        pause_payload["project"],
        owner="execution_start.dispatch_control",
        action="pause_dispatch",
        decision_class="D3",
    )

    resume = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase33/resume-dispatch",
        json={"approved": True, "operator_id": "operator", "reason": "audit resume"},
    )
    assert resume.status_code == 200
    resume_payload = resume.json()
    assert resume_payload["dispatch_control"]["state"] == "running"
    assert resume_payload["project"]["execution"]["sequential_execution"]["status"] == "long_running"
    _assert_last_w18_route(
        resume_payload["project"],
        owner="execution_start.dispatch_control",
        action="resume_dispatch",
        decision_class="D3",
    )

    cancel = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase33/cancel-dispatch",
        json={"approved": True, "operator_id": "operator", "reason": "audit cancel"},
    )
    assert cancel.status_code == 200
    cancel_payload = cancel.json()
    control = cancel_payload["dispatch_control"]
    assert control["state"] == "cancelled"
    assert control["controls_available"]["pause"] is False
    assert control["controls_available"]["cancel"] is False
    assert cancel_payload["project"]["execution"]["sequential_execution"]["status"] == "cancelled"
    assert Path(control["artifacts"]["structured_data"]["path"]).exists()
    events = [item["event"] for item in control["events"]]
    assert "dispatch_paused" in events
    assert "dispatch_resumed" in events
    assert "dispatch_cancelled" in events
    _assert_last_w18_route(
        cancel_payload["project"],
        owner="execution_start.dispatch_control",
        action="cancel_dispatch",
        decision_class="D4",
    )


def test_execution_start_uses_explicit_environment_labels_without_numeric_count(monkeypatch, tmp_path):
    import sylion.project_mode.store as project_mode_store

    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "project_mode_explicit_envs.sqlite"))
    monkeypatch.setenv("SYLION_PROJECT_RESULTS_ROOT", str(tmp_path / "project-results"))
    monkeypatch.setattr(project_mode_store, "_store", None)

    created = client.post(
        "/api/v1/projects",
        json={
            "name": "ServiceOps six explicit local envs",
            "idea_raw": (
                "ServiceOps Control Tower local-first, bez Hetznera, bez tworzenia VPS, bez produkcji, "
                "bez external submit. Wymagane wielosrodowiskowe wykonanie lokalne: "
                "dev/staging/qa-lab/security/review/release-lab."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert created.status_code == 200
    project_id = created.json()["project"]["project_id"]

    store = project_mode_store.get_project_mode_store()
    project = store.get_project(project_id)
    assert project is not None
    assert project["canon_snapshot"]["runtime_constraints"]["local_environment_count"] == 6
    project["status"] = "completed"
    project["phase"] = "broadcast"
    project["approvals"] = {"book": True, "operating_model": True}
    project["build_authorized_at"] = 1777740000.0
    store.upsert_project(project)

    phase32 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase32/initialize-build",
        json={"approved": True, "operator_id": "operator", "notes": "Local-only human dashboard run."},
    )
    assert phase32.status_code == 200
    environments = phase32.json()["project"]["execution"]["build_initialization"]["environments"]
    assert [item["id"] for item in environments] == [
        "dev",
        "staging",
        "qa-lab",
        "security",
        "review",
        "release-lab",
    ]
    assert all(item["type"] == "local" for item in environments)
    assert all(item["requires_action_time_confirmation"] is False for item in environments)

    for endpoint in [
        "phase33/start-execution",
        "phase34/reconvene-council",
        "phase35/activate-orchestration",
        "phase36/complete-build",
    ]:
        accepted = client.post(f"{EXECUTION_BASE}/projects/{project_id}/{endpoint}", json={"approved": True, "operator_id": "operator"})
        assert accepted.status_code == 200

    phase37 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase37/run-quality-gates",
        json={"approved": True, "operator_id": "operator", "notes": "Run full local quality gates."},
    )
    assert phase37.status_code == 200
    quality = phase37.json()["project"]["execution"]["quality_gates"]
    assert quality["performance"]["environment"] == "local dev, staging, qa-lab, security, review, release-lab"
    assert quality["fixer_runtime_policy"]["applied_iterations"] == len(quality["auto_fix_iterations"])


def test_full_group_d_planning_to_ready_for_build(monkeypatch, tmp_path):
    project_id = _ready_for_planning(monkeypatch, tmp_path, "group_d.db")

    phase26 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase26/assign-models", json={"approved": True, "operator_id": "operator"})
    assert phase26.status_code == 200
    assert phase26.json()["acceptance"]["accepted"] is True
    assert len(phase26.json()["project"]["planning"]["model_selection"]["assignment_matrix"]) >= 18

    phase27 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase27/synthesize-skills", json={"approved": True, "operator_id": "operator"})
    assert phase27.status_code == 200
    assert phase27.json()["acceptance"]["accepted"] is True
    assert len(phase27.json()["project"]["planning"]["skill_synthesis"]["patterns"]) == 8

    phase28 = client.post(
        f"{PLANNING_BASE}/projects/{project_id}/phase28/generate-masterplan",
        json={"approved": True, "operator_id": "operator", "profile_id": "profile_2"},
    )
    assert phase28.status_code == 200
    assert phase28.json()["acceptance"]["accepted"] is True
    masterplan = phase28.json()["project"]["planning"]["masterplan"]
    assert len(masterplan["layers"]) == 8
    assert len(masterplan["work_units"]) >= 47
    assert Path(masterplan["artifacts"]["markdown"]["path"]).exists()

    phase29 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase29/generate-test-plan", json={"approved": True, "operator_id": "operator"})
    assert phase29.status_code == 200
    assert phase29.json()["acceptance"]["accepted"] is True
    assert phase29.json()["project"]["planning"]["test_plan"]["covered_acceptance_criteria"] == 150
    assert len(phase29.json()["project"]["planning"]["test_plan"]["human_like_scenarios"]) == 32

    phase30 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase30/preflight-cost", json={"approved": True, "operator_id": "operator"})
    assert phase30.status_code == 200
    assert phase30.json()["acceptance"]["accepted"] is True
    assert phase30.json()["project"]["planning"]["preflight_cost"]["operator_decision"]["decision"] == "GO"

    phase31 = client.post(f"{PLANNING_BASE}/projects/{project_id}/phase31/dry-run", json={"approved": True, "operator_id": "operator"})
    assert phase31.status_code == 200
    payload = phase31.json()
    assert payload["acceptance"]["accepted"] is True
    assert payload["project"]["state"] == "READY_FOR_BUILD"
    assert payload["project"]["planning"]["dry_run"]["confidence"] >= 0.85

    overview = client.get(PLANNING_BASE).json()
    assert overview["group"]["complete"] is True
    assert overview["group"]["edge_cases"] == 98


def test_execution_testing_deploy_closure_to_closed(monkeypatch, tmp_path):
    project_id = _ready_for_execution(monkeypatch, tmp_path, "group_e.db")

    runtime_config = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/runtime-configuration",
        json={
            "approved": True,
            "operator_id": "operator",
            "topology": "local-plus-vps",
            "local_workers": 3,
            "vps_workers": 2,
            "environments": 4,
            "max_parallel_workers": 5,
            "max_monthly_vps_eur": 40,
            "allow_paid_vps": False,
            "apply_to_next_build": True,
        },
    )
    assert runtime_config.status_code == 200
    runtime_payload = runtime_config.json()["runtime_configuration"]
    assert runtime_payload["provisioning_state"] == "planned_locked"
    assert runtime_payload["external_cost"] is False
    assert runtime_payload["requires_action_time_confirmation_before_cost"] is True
    assert runtime_config.json()["w18_recent"][-1]["command"].startswith("/runtime ustaw")

    phase32 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase32/initialize-build",
        json={"approved": True, "operator_id": "operator", "notes": "Start build."},
    )
    assert phase32.status_code == 200
    assert phase32.json()["acceptance"]["accepted"] is True
    project = phase32.json()["project"]
    assert project["state"] == "BUILDING"
    assert len(project["execution"]["build_initialization"]["workers"]) == 5
    assert len(project["execution"]["build_initialization"]["environments"]) == 4
    assert project["execution"]["build_initialization"]["runtime_configuration"]["vps_workers"] == 2
    assert len(project["execution"]["build_initialization"]["repository"]["branches"]) == 10
    modern_spawning = project["execution"]["build_initialization"]["modern_worker_spawning"]
    assert "A1" in modern_spawning["architecture"]
    assert "A2 git worktrees" in modern_spawning["architecture"]
    assert "A3 docker sandboxing" in modern_spawning["architecture"]
    assert modern_spawning["session_backend"]["id"] in {"tmux", "windows_process_group", "missing_session_backend", "wsl_tmux_candidate"}
    assert len(modern_spawning["sessions"]) == 5
    assert all("backend" in item for item in modern_spawning["sessions"])
    assert len(modern_spawning["worktrees"]) == 5
    assert len(modern_spawning["containers"]) == 5
    assert modern_spawning["operator_decision_required_for_live_spawn"] is True

    runtime_caps = client.get(f"{EXECUTION_BASE}/runtime-capabilities")
    assert runtime_caps.status_code == 200
    assert any(item["id"] == "A1" for item in runtime_caps.json()["checklist"])

    ready_caps = {
        "host": {"system": "Windows", "release": "11", "machine": "AMD64"},
        "commands": {},
        "session_backend": {
            "id": "windows_process_group",
            "label": "Windows detached process groups",
            "available": True,
            "attach_supported": False,
            "path": "powershell",
        },
        "docker_runtime": {"available": True, "state": "daemon_ready", "evidence": "test-daemon"},
        "features": {
            "persistent_worker_sessions": True,
            "tmux_persistent_sessions": False,
            "windows_persistent_processes": True,
            "git_worktrees": True,
            "docker_sandboxing": True,
            "network_whitelist": True,
            "burst_mode_profile_6": True,
        },
        "missing": [],
        "runtime_ready": True,
        "critical_if_live_spawn": False,
        "recommendation": "ready_for_operator_gate",
    }
    alive_pids = {4242, 4243}

    class FakeProc:
        def __init__(self, pid: int):
            self.pid = pid

    spawn_index = {"value": 0}

    def fake_spawn(script_path, workdir, log_path, powershell_path):
        pid = 4242 + spawn_index["value"]
        spawn_index["value"] += 1
        Path(log_path).write_text(f"started worker pid={pid}\nheartbeat worker pid={pid}\n", encoding="utf-8")
        return FakeProc(pid)

    def fake_run(*args, **kwargs):
        alive_pids.clear()
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(execution_start_routes, "_runtime_capability_snapshot", lambda: ready_caps)
    monkeypatch.setattr(execution_start_routes, "_spawn_windows_worker", fake_spawn)
    monkeypatch.setattr(execution_start_routes, "_process_is_alive", lambda pid: int(pid) in alive_pids)
    monkeypatch.setattr(execution_start_routes.subprocess, "run", fake_run)

    live_spawn = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase32/live-spawn-workers",
        json={"approved": True, "operator_id": "operator", "workers_limit": 2, "duration_seconds": 15, "mode": "smoke"},
    )
    assert live_spawn.status_code == 200
    live = live_spawn.json()["live_spawn"]
    assert live["backend"] == "windows_process_group"
    assert live["running"] == 2
    assert live["safety"]["external_cost"] is False
    assert all(Path(item["pid_path"]).exists() for item in live["sessions"])
    assert all(Path(item["log_path"]).exists() for item in live["sessions"])
    assert live_spawn.json()["project"]["execution"]["w18_commands"][-1]["command"].startswith("/workers smoke start")
    live_command = live_spawn.json()["project"]["execution"]["w18_commands"][-1]
    assert live_command["command_route"]["target_action"] == "live_spawn_workers"
    assert live_command["command_execution"]["governance_ticket_id"]

    status = client.get(f"{EXECUTION_BASE}/projects/{project_id}/phase32/live-spawn-workers")
    assert status.status_code == 200
    assert status.json()["live_spawn"]["running"] == 2

    stopped = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase32/stop-live-workers",
        json={"approved": True, "operator_id": "operator", "notes": "Stop smoke sessions."},
    )
    assert stopped.status_code == 200
    assert stopped.json()["live_spawn"]["running"] == 0
    assert stopped.json()["project"]["execution"]["w18_commands"][-1]["command"] == "/workers smoke stop"
    stop_command = stopped.json()["project"]["execution"]["w18_commands"][-1]
    assert stop_command["command_route"]["target_action"] == "stop_live_workers"
    assert stop_command["command_route"]["phase"] == "IMMEDIATE"

    phase33 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase33/start-execution",
        json={"approved": True, "operator_id": "operator", "notes": "Monitor execution."},
    )
    assert phase33.status_code == 200
    payload = phase33.json()
    assert payload["acceptance"]["accepted"] is True
    progress = payload["project"]["execution"]["sequential_execution"]
    assert progress["total_progress_percent"] == 22
    assert progress["build_phases"][0]["status"] == "complete"
    assert progress["build_phases"][1]["status"] == "in_progress"
    assert progress["guards"]["cost"]["status"] == "pass"
    phase33_command = payload["project"]["execution"]["w18_commands"][-1]
    assert phase33_command["command_route"]["target_action"] == "start_sequential_execution"
    assert phase33_command["result"]["workers_completed"] >= 1

    dispatch = client.get("/api/v1/orchestration/dispatch-config").json()
    dispatch["parallelism_mode"] = "capped"
    dispatch["max_simultaneous"] = 2
    assert client.put("/api/v1/orchestration/dispatch-config", json=dispatch).status_code == 200
    assert client.put(
        "/api/v1/orchestration/auditor-cadence",
        json={
            "tick_frequency_seconds": 60,
            "enabled_dimensions": ["code_quality", "funding_deadlines"],
            "phase_boundary_cron": "*/5 * * * *",
        },
    ).status_code == 200
    assert client.put(
        "/api/v1/orchestration/inter-model-conversation",
        json={"enabled": True, "max_turns": 2},
    ).status_code == 200

    phase34 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase34/reconvene-council",
        json={
            "approved": True,
            "operator_id": "operator",
            "trigger": "customer_scope_change",
            "issue_title": "Customer asks to add subscription billing during build",
        },
    )
    assert phase34.status_code == 200
    assert phase34.json()["acceptance"]["accepted"] is True
    council = phase34.json()["project"]["execution"]["mid_build_council"]
    assert len(council["invited_roles"]) >= 8
    assert "Adversarial Critic" in council["invited_roles"]
    assert council["adversarial_critic_policy"]["status"] == "hard_required"
    assert council["weighted_vote"]["quorum"]["met"] is True
    assert council["weighted_vote"]["quorum"]["source"] == "orchestration_config"
    assert council["weighted_vote"]["adversarial_critic"]["signed"] is True
    assert council["governance_veto"]["enabled"] is True
    assert council["rounds"][0]["consensus"] >= 0.85
    assert council["build_integration"]["workers_reactivated"] is True
    _assert_last_w18_route(
        phase34.json()["project"],
        owner="execution_start.phase34",
        action="reconvene_mid_build_council",
        decision_class="D4",
    )

    phase35 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase35/activate-orchestration",
        json={"approved": True, "operator_id": "operator", "notes": "Activate orchestration."},
    )
    assert phase35.status_code == 200
    assert phase35.json()["acceptance"]["accepted"] is True
    orchestration = phase35.json()["project"]["execution"]["build_orchestration"]
    assert orchestration["active"] is True
    meta_runtime = orchestration["meta_orchestration_runtime"]
    assert meta_runtime["enabled"] is True
    assert meta_runtime["dispatch"]["parallelism_mode"] == "capped"
    assert orchestration["profile"]["requested_workers"] >= 2
    assert orchestration["profile"]["workers"] == 2
    assert orchestration["build_critic"]["cadence"]["commit_review_minutes"] == 1
    assert meta_runtime["team_formation"]["matched_rules"] >= 1
    assert meta_runtime["inter_model_conversation"]["turns"] == 2
    assert orchestration["lifetime_stats"]["tasks_orchestrated"] == 47
    assert orchestration["lifetime_stats"]["tasks_completed"] == 31
    assert orchestration["coherence_guard"]["tier3_cross_worker"]["failed"] == 0
    assert orchestration["build_critic"]["enabled"] is True
    assert orchestration["build_critic"]["role"] == "adversarial_critic"
    assert orchestration["build_critic"]["hard_required"] is True
    assert orchestration["build_critic"]["authority"]["can_escalate_to_human_gate"] is True
    assert orchestration["prompt_splitting"]["enabled"] is True
    assert "CRITIC" in orchestration["prompt_splitting"]["angles"]
    _assert_last_w18_route(
        phase35.json()["project"],
        owner="execution_start.phase35",
        action="activate_orchestration",
        decision_class="D3",
    )

    phase36 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase36/complete-build",
        json={"approved": True, "operator_id": "operator", "notes": "Complete build."},
    )
    assert phase36.status_code == 200
    payload36 = phase36.json()
    assert payload36["acceptance"]["accepted"] is True
    assert payload36["project"]["state"] == "BUILD_COMPLETE"
    completion = payload36["project"]["execution"]["build_completion"]
    assert completion["artifacts_inventory"]["total_files"] == 153
    assert completion["cost_reconciliation"]["build_actual_usd"] == 142.30
    assert completion["worker_decommissioning"]["decommissioned"] == 5
    assert Path(completion["artifacts"]["summary_report"]["path"]).exists()
    inventory_paths = {
        Path(item["path"]).name: Path(item["path"])
        for item in completion["artifacts_inventory"]["files"]
    }
    backend_app = inventory_paths["app.py"]
    frontend_app = inventory_paths["App.tsx"]
    assert "FastAPI(title=\"AEIS Local CRM\")" in backend_app.read_text(encoding="utf-8")
    assert "Generated by Phase 36 build completion inventory" not in backend_app.read_text(encoding="utf-8")
    assert "Lokalny CRM freelancera" in frontend_app.read_text(encoding="utf-8")
    _assert_last_w18_route(
        payload36["project"],
        owner="execution_start.phase36",
        action="complete_build",
        decision_class="D3",
    )

    phase37 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase37/run-quality-gates",
        json={"approved": True, "operator_id": "operator", "notes": "Accept quality verdict."},
    )
    assert phase37.status_code == 200
    payload37 = phase37.json()
    assert payload37["acceptance"]["accepted"] is True
    assert payload37["project"]["state"] == "READY_FOR_ACCEPTANCE_TESTING"
    quality = payload37["project"]["execution"]["quality_gates"]
    assert quality["summary"]["functional_passed_effective"] == 308
    assert quality["summary"]["waived"] == 1
    assert quality["summary"]["quality_guard_verdict"] == "PASS"
    assert quality["summary"]["reruns"] == len(quality["auto_fix_iterations"])
    assert quality["performance"]["p95_api_latency_ms"] == 280
    _assert_last_w18_route(
        payload37["project"],
        owner="execution_start.phase37",
        action="run_quality_gates",
        decision_class="D3",
    )

    phase38 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase38/complete-acceptance",
        json={
            "approved": True,
            "operator_id": "operator",
            "notes": "Customer accepted staging.",
            "customer_representative": "Anna Kowalska, CTO",
            "review_window_days": 5,
            "signoff_text": "Akceptuje wdrozenie produkcyjne",
        },
    )
    assert phase38.status_code == 200
    payload38 = phase38.json()
    assert payload38["acceptance"]["accepted"] is True
    assert payload38["project"]["state"] == "READY_FOR_PREDEPLOY"
    customer = payload38["project"]["execution"]["acceptance_testing"]
    assert customer["feedback"]["total"] == 14
    assert customer["resolution"]["all_feedback_addressed"] is True
    assert customer["signoff"]["received"] is True
    _assert_last_w18_route(
        payload38["project"],
        owner="execution_start.phase38",
        action="complete_acceptance_testing",
        decision_class="D4",
    )

    phase39 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase39/authorize-predeploy",
        json={
            "approved": True,
            "operator_id": "operator",
            "notes": "Authorize production deploy.",
            "domain": "crm.customer-y.pl",
            "deploy_day": "2026-06-25",
            "authorization_option": "authorize_phase_40",
        },
    )
    assert phase39.status_code == 200
    payload39 = phase39.json()
    assert payload39["acceptance"]["accepted"] is True
    assert payload39["project"]["state"] == "READY_FOR_PRODUCTION_DEPLOY"
    predeploy = payload39["project"]["execution"]["predeploy"]
    assert predeploy["production_environment"]["region"] == "hel1"
    assert predeploy["deploy_plan"]["rollback_test"]["rollback_minutes"] == 4
    assert predeploy["authorization"]["approved"] is True
    assert predeploy["dns"]["domain"] == "crm.customer-y.pl"
    phase39_command = _assert_last_w18_route(
        payload39["project"],
        owner="execution_start.phase39",
        action="authorize_predeploy",
        decision_class="D4",
    )
    assert phase39_command["command_execution"]["governance_ticket_id"]

    phase40 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase40/execute-production-deploy",
        json={
            "approved": True,
            "operator_id": "operator",
            "notes": "Deploy to production.",
            "domain": "crm.customer-y.pl",
            "deploy_day": "2026-06-25",
            "strategy": "canary",
        },
    )
    assert phase40.status_code == 200
    payload40 = phase40.json()
    assert payload40["acceptance"]["accepted"] is True
    assert payload40["project"]["state"] == "DEPLOYED"
    deploy = payload40["project"]["execution"]["production_deploy"]
    assert len(deploy["canary_stages"]) == 4
    assert deploy["observation_24h"]["critical_errors"] == 0
    assert deploy["observation_24h"]["uptime_percent"] == 100
    assert deploy["customer_postdeploy"]["handoff_completed"] is True
    phase40_command = _assert_last_w18_route(
        payload40["project"],
        owner="execution_start.phase40",
        action="execute_production_deploy",
        decision_class="D5",
    )
    assert phase40_command["command_execution"]["governance_ticket_id"]

    phase41 = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/phase41/close-project",
        json={
            "approved": True,
            "operator_id": "operator",
            "notes": "Close delivered project.",
            "closed_date": "2026-06-27",
            "warranty_start": "2026-06-27",
            "warranty_end": "2026-07-27",
            "final_invoice_number": "INV-2026-06-001",
        },
    )
    assert phase41.status_code == 200
    payload41 = phase41.json()
    assert payload41["acceptance"]["accepted"] is True
    assert payload41["project"]["state"] == "CLOSED"
    closure = payload41["project"]["execution"]["project_closure"]
    assert closure["calibration"]["skills_promoted"] == 4
    assert closure["cost_reconciliation"]["final_actual_usd"] == 358.50
    assert closure["cost_reconciliation"]["operator_profit_usd"] == 126.50
    assert closure["final_invoice"]["ksef_submitted"] is True
    assert closure["closure_email"]["subject"] == "Customer Y CRM - projekt zakończony"
    assert closure["warranty"]["days"] == 30
    _assert_last_w18_route(
        payload41["project"],
        owner="execution_start.phase41",
        action="close_project",
        decision_class="D4",
    )
    assert Path(closure["artifacts"]["operator_report"]["path"]).exists()
    operator_report_text = Path(closure["artifacts"]["operator_report"]["path"]).read_text(encoding="utf-8")
    assert "Projekt został dostarczony i zamknięty." in operator_report_text
    assert "Operator Final Report" not in operator_report_text

    overview = client.get(EXECUTION_BASE).json()
    assert overview["group"]["edge_cases"] == 164
    assert overview["group"]["complete"] is True


def test_execution_edge_cases_and_diagnosis(monkeypatch, tmp_path):
    project_id = _ready_for_execution(monkeypatch, tmp_path, "execution_edge.db")

    edge_cases = client.get(f"{EXECUTION_BASE}/projects/{project_id}/edge-cases")
    diagnosis = client.post(
        f"{EXECUTION_BASE}/projects/{project_id}/edge-cases/diagnose",
        json={"phase": "33", "case_id": "EC-B1", "context": {"source": "test"}},
    )

    assert edge_cases.status_code == 200
    assert edge_cases.json()["total"] == 164
    assert diagnosis.status_code == 200
    payload = diagnosis.json()
    assert payload["phase"] == "33"
    assert payload["case"]["id"] == "EC-B1"
    assert payload["action_plan"][-1] == "rerun phase 33 acceptance"


def test_mid_build_council_caps_impossible_runtime_quorum(monkeypatch):
    import sylion.aeis.advisor.orchestration_config.service as orchestration_service

    class FakeOrchestrationService:
        def get_council_rules(self):
            return SimpleNamespace(quorum_min=99, quorum_type="majority", critic_gate_threshold=0.6)

    monkeypatch.setattr(orchestration_service, "get_orchestration_service", lambda: FakeOrchestrationService())
    vote = execution_start_routes._weighted_council_vote(
        {},
        execution_start_routes.MidBuildCouncilRequest(approved=True, operator_id="operator"),
    )
    assert vote["quorum"]["configured_required_roles"] == 99
    assert vote["quorum"]["required_roles"] == len(vote["roles"])
    assert vote["quorum"]["capped_to_available_roles"] is True
    assert vote["quorum"]["met"] is True
