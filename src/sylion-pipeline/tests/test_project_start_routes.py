from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from sylion.api.app import app


client = TestClient(app)
BASE = "/api/v1/project-start"


def _create(monkeypatch, tmp_path: Path, db_name: str = "project_start.db") -> dict:
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / db_name))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))
    response = client.post(
        f"{BASE}/projects/create",
        json={
            "creation_path": "idea",
            "name": "Customer Y CRM",
            "idea_text": "Build Polish CRM with Stripe payments, KSeF invoices, GDPR, PL/EN UI and customer-funded delivery.",
            "customer_context": "Customer Y, 10-50 employees, Polish jurisdiction",
            "deadline": "2026-06",
            "budget_hint_eur": 3000,
            "template_id": "polish_saas_payment",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_project_start_overview_and_template_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "overview.db"))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))

    overview = client.get(BASE)
    templates = client.get(f"{BASE}/templates")

    assert overview.status_code == 200
    assert templates.status_code == 200
    data = overview.json()
    assert data["group"]["id"] == "B"
    assert data["group"]["edge_cases"] == 66
    assert data["group"]["complete"] is False
    assert data["active_project"] is None
    template_ids = {item["id"] for item in templates.json()["templates"]}
    assert {"polish_saas_payment", "internal_crm", "funding_assistant", "mobile_approval_queue", "research_experiment"}.issubset(template_ids)


def test_mobile_approval_queue_stays_internal_without_payment_scope(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "mobile_approval.db"))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))

    response = client.post(
        f"{BASE}/projects/create",
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
            "template_id": "polish_saas_payment",
        },
    )

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["classification"]["project_type"] == "internal_app"
    assert project["classification"]["domain"] == "mobile_approval"
    assert project["resources"]["llm_budget_reserved_usd"] == 400
    assert "payment" not in project["classification"]["detected_signals"]
    assert "ksef" not in project["classification"]["detected_signals"]
    assert "mobile_approval" in project["classification"]["detected_signals"]

    project_id = project["project_id"]
    scope = client.post(f"{BASE}/projects/{project_id}/scope/defaults", json={"operator_id": "operator"}).json()["project"]["scope"]
    council = client.post(f"{BASE}/projects/{project_id}/council/defaults", json={"operator_id": "operator"}).json()["project"]["council"]
    active_surface = f"{scope['in_scope']} {scope['constraints']} {council['roles']} {council['knowledge_bases']}".lower()
    assert "device token" in active_surface
    assert "humangate" in active_surface
    assert "stripe" not in active_surface
    assert "ksef" not in active_surface


def test_multi_domain_project_preserves_all_domains(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "multi_domain.db"))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))

    response = client.post(
        f"{BASE}/projects/create",
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

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["classification"]["project_type"] == "internal_app"
    assert project["classification"]["domain"] == "aeis_multi_domain"
    assert project["classification"]["d_level_label"] == "D5"
    assert project["resources"]["llm_budget_reserved_usd"] == 900
    signals = set(project["classification"]["detected_signals"])
    assert {
        "multi_domain",
        "crm",
        "funding",
        "mobile_approval",
        "automation_runtime",
        "memory",
        "skills",
        "governance",
        "humangate",
        "audit",
    }.issubset(signals)

    project_id = project["project_id"]
    assert client.post(f"{BASE}/projects/{project_id}/goals/defaults", json={"operator_id": "operator"}).status_code == 200
    scope = client.post(f"{BASE}/projects/{project_id}/scope/defaults", json={"operator_id": "operator"}).json()["project"]["scope"]
    council = client.post(f"{BASE}/projects/{project_id}/council/defaults", json={"operator_id": "operator"}).json()["project"]["council"]
    active_surface = f"{scope['in_scope']} {scope['constraints']} {scope['risks']} {council}".lower()
    for expected in ["crm", "funding", "mobile", "automation", "runtime", "memory", "skill", "humangate", "adversarial critic"]:
        assert expected in active_surface
    for forbidden in ["stripe", "ksef", "payment specialist"]:
        assert forbidden not in active_surface
    assert len(council["roles"]) == 14
    assert len(council["knowledge_bases"]) == 9

    approved = client.post(
        f"{BASE}/projects/{project_id}/council/approve-readiness",
        json={"approved": True, "operator_id": "operator", "notes": "Ready for multi-domain council."},
    )
    assert approved.status_code == 200
    assert approved.json()["acceptance"]["accepted"] is True
    assert approved.json()["acceptance"]["hard_blocks"] == []


def test_phase16_create_project_inception_acceptance(monkeypatch, tmp_path):
    data = _create(monkeypatch, tmp_path, "phase16.db")
    project = data["project"]
    acceptance = data["acceptance"]

    assert project["project_id"].startswith("proj_")
    assert project["state"] == "READY_FOR_GOAL_DEFINITION"
    assert project["classification"]["d_level_label"] == "D4"
    assert len(project["templates"]) == 4
    assert project["resources"]["llm_budget_reserved_usd"] > 0
    assert str(project["shell"]["root"]).startswith(str(tmp_path / "projects"))
    assert all(Path(path).exists() for path in project["shell"]["created"])
    assert acceptance["accepted"] is True
    assert acceptance["hard_blocks"] == []
    assert any(entry["event"] == "project_inception" for entry in project["audit_chain"])


def test_simple_local_crm_with_negated_payment_scope_stays_internal(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "simple_crm.db"))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))

    response = client.post(
        f"{BASE}/projects/create",
        json={
            "creation_path": "idea",
            "name": "P1 Mini CRM Local",
            "idea_text": (
                "Stwórz bardzo prosty lokalny CRM dla freelancera: kontakty klientów, "
                "notatki, status leadów, przypomnienia i eksport CSV. Bez płatności, "
                "bez KSeF, bez deployu, bez VPS, bez integracji zewnętrznych."
            ),
            "customer_context": "Freelancer solo, lokalne dane testowe, mały budżet testowy.",
            "deadline": "2026-06",
            "budget_hint_eur": 300,
            "template_id": "polish_saas_payment",
        },
    )

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["classification"]["project_type"] == "internal_app"
    assert project["classification"]["domain"] == "crm"
    assert project["classification"]["d_level_label"] == "D3"
    assert "ksef" not in project["classification"]["detected_signals"]
    assert "payment" not in project["classification"]["detected_signals"]
    assert "external_scope_negated" in project["classification"]["detected_signals"]
    assert "local_crm" in project["classification"]["detected_signals"]
    assert project["resources"]["llm_budget_reserved_usd"] == 200
    assert project["templates"]["deployment"] == "dt_internal_preview"

    project_id = project["project_id"]
    goals = client.post(f"{BASE}/projects/{project_id}/goals/defaults", json={"operator_id": "operator"}).json()["project"]["goals"]
    scope = client.post(f"{BASE}/projects/{project_id}/scope/defaults", json={"operator_id": "operator"}).json()["project"]["scope"]
    council = client.post(f"{BASE}/projects/{project_id}/council/defaults", json={"operator_id": "operator"}).json()["project"]["council"]

    active_surface = " ".join(
        [
            str(scope["in_scope"]),
            str(scope["constraints"]),
            str(council["roles"]),
            str(council["knowledge_bases"]),
        ]
    ).lower()
    assert "stripe" not in active_surface
    assert "ksef" not in active_surface
    assert "payment specialist" not in active_surface
    assert "payments" in " ".join(item["title"].lower() for item in scope["out_of_scope"])

    approved = client.post(
        f"{BASE}/projects/{project_id}/council/approve-readiness",
        json={"approved": True, "operator_id": "operator", "notes": "Ready for local CRM Council."},
    )
    assert approved.status_code == 200
    assert approved.json()["acceptance"]["accepted"] is True
    assert approved.json()["acceptance"]["hard_blocks"] == []


def test_project_start_project_is_visible_in_global_projects_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "global_bridge.db"))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))

    created = client.post(
        f"{BASE}/projects/create",
        json={
            "creation_path": "idea",
            "name": "P1 Mini CRM Global Bridge",
            "idea_text": (
                "Stworz lokalny CRM dla freelancera: kontakty klientow, notatki, status leadow "
                "i eksport CSV. Bez platnosci, bez KSeF, bez deployu, bez VPS."
            ),
            "customer_context": "Freelancer solo, lokalne dane testowe.",
            "deadline": "2026-06",
            "budget_hint_eur": 300,
            "template_id": "polish_saas_payment",
        },
    )
    assert created.status_code == 200
    created_project = created.json()["project"]
    project_id = created_project["project_id"]
    closure_path = Path(created_project["shell"]["root"]) / "reports" / "closure" / "phase41_project_closure.json"
    closure_path.parent.mkdir(parents=True, exist_ok=True)
    closure_path.write_text('{"project_id":"%s","status":"closed"}' % project_id, encoding="utf-8")

    listing = client.get("/api/v1/projects")
    assert listing.status_code == 200
    listed = [item for item in listing.json()["projects"] if item["project_id"] == project_id]
    assert len(listed) == 1
    assert listed[0]["source"] == "project_start_lifecycle"
    assert listed[0]["title"] == "P1 Mini CRM Global Bridge"

    detail = client.get(f"/api/v1/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json()["project_id"] == project_id
    assert detail.json()["source"] == "project_start_lifecycle"

    assert client.get(f"/api/v1/projects/{project_id}/timeline").status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/questions").status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/canon").status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/masterplan").status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/modules").status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/audit").status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/cost").status_code == 200
    artifact = client.get(f"/api/v1/projects/{project_id}/artifact/raw")
    assert artifact.status_code == 200
    assert artifact.json()["project_id"] == project_id


def test_phase17_goal_defaults_and_acceptance(monkeypatch, tmp_path):
    data = _create(monkeypatch, tmp_path, "phase17.db")
    project_id = data["project"]["project_id"]

    response = client.post(f"{BASE}/projects/{project_id}/goals/defaults", json={"operator_id": "operator"})

    assert response.status_code == 200
    payload = response.json()
    project = payload["project"]
    assert project["state"] == "READY_FOR_SCOPE_DEFINITION"
    assert len(project["goals"]["primary_goals"]) == 3
    assert len(project["goals"]["secondary_goals"]) == 5
    assert len(project["goals"]["success_metrics"]) == 5
    assert len(project["goals"]["stakeholders"]) == 5
    assert payload["acceptance"]["accepted"] is True
    assert any(entry["event"] == "goals_defined" for entry in project["audit_chain"])


def test_phase18_scope_defaults_and_acceptance(monkeypatch, tmp_path):
    data = _create(monkeypatch, tmp_path, "phase18.db")
    project_id = data["project"]["project_id"]
    client.post(f"{BASE}/projects/{project_id}/goals/defaults", json={"operator_id": "operator"})

    response = client.post(f"{BASE}/projects/{project_id}/scope/defaults", json={"operator_id": "operator"})

    assert response.status_code == 200
    payload = response.json()
    project = payload["project"]
    assert project["state"] == "READY_FOR_COUNCIL_CONFIG"
    assert len(project["scope"]["in_scope"]) == 28
    assert len(project["scope"]["out_of_scope"]) == 12
    assert set(project["scope"]["constraints"]) == {"technical", "business", "regulatory"}
    assert len(project["scope"]["risks"]) == 9
    assert project["scope"]["budget_reconciliation"]["status"] == "applied"
    assert payload["acceptance"]["accepted"] is True
    assert any(entry["event"] == "scope_defined" for entry in project["audit_chain"])


def test_phase19_council_requires_operator_approval_then_accepts(monkeypatch, tmp_path):
    data = _create(monkeypatch, tmp_path, "phase19.db")
    project_id = data["project"]["project_id"]
    client.post(f"{BASE}/projects/{project_id}/goals/defaults", json={"operator_id": "operator"})
    client.post(f"{BASE}/projects/{project_id}/scope/defaults", json={"operator_id": "operator"})

    prepared = client.post(f"{BASE}/projects/{project_id}/council/defaults", json={"operator_id": "operator"})
    assert prepared.status_code == 200
    before = prepared.json()
    assert len(before["project"]["council"]["roles"]) == 12
    assert len(before["project"]["council"]["knowledge_bases"]) == 8
    assert before["acceptance"]["accepted"] is False
    assert any(item["id"] == "operator_approved" for item in before["acceptance"]["hard_blocks"])

    approved = client.post(
        f"{BASE}/projects/{project_id}/council/approve-readiness",
        json={"approved": True, "operator_id": "operator", "notes": "Ready for Phase 20."},
    )

    assert approved.status_code == 200
    after = approved.json()
    assert after["project"]["state"] == "READY_FOR_COUNCIL_CONVENING"
    assert after["project"]["council"]["operator_approved"] is True
    assert after["acceptance"]["accepted"] is True
    assert any(entry["event"] == "council_configured" for entry in after["project"]["audit_chain"])

    overview = client.get(BASE).json()
    assert overview["group"]["complete"] is True


def test_project_start_edge_cases_and_diagnosis(monkeypatch, tmp_path):
    data = _create(monkeypatch, tmp_path, "edge.db")
    project_id = data["project"]["project_id"]

    edge_cases = client.get(f"{BASE}/projects/{project_id}/edge-cases")
    diagnosis = client.post(
        f"{BASE}/projects/{project_id}/edge-cases/diagnose",
        json={"phase": "19", "case_id": "EC-A1", "context": {"source": "test"}},
    )

    assert edge_cases.status_code == 200
    assert edge_cases.json()["total"] == 66
    assert {phase for phase in edge_cases.json()["phases"]} == {"16", "17", "18", "19"}
    assert diagnosis.status_code == 200
    payload = diagnosis.json()
    assert payload["phase"] == "19"
    assert payload["case"]["id"] == "EC-A1"
    assert payload["requires_operator_review"] is True
    assert payload["action_plan"][-1] == "rerun phase 19 acceptance"
