from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from sylion.api.app import app


client = TestClient(app)
PROJECT_BASE = "/api/v1/project-start"
BASE = "/api/v1/council-to-ksiega"


def _ready_project(monkeypatch, tmp_path: Path, db_name: str = "council_to_ksiega.db") -> str:
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
    return project_id


def _ready_internal_crm_project(monkeypatch, tmp_path: Path, db_name: str = "internal_council.db") -> str:
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
        json={"approved": True, "operator_id": "operator", "notes": "Ready for local CRM Group C."},
    ).status_code == 200
    return project_id


def _ready_funding_project(monkeypatch, tmp_path: Path, db_name: str = "funding_council.db") -> str:
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / db_name))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))
    created = client.post(
        f"{PROJECT_BASE}/projects/create",
        json={
            "creation_path": "idea",
            "name": "P2 Funding NGO",
            "idea_text": (
                "Lokalny asystent funding dla NGO: katalog programow grantowych, scoring, dokumenty, "
                "wniosek i HumanGate przed finalnym zlozeniem. Tylko lokalny rehearsal."
            ),
            "customer_context": "Polska fundacja, lokalny rehearsal, minimalny budzet testowy.",
            "deadline": "2026-06",
            "budget_hint_eur": 300,
            "template_id": "funding_assistant",
        },
    )
    assert created.status_code == 200
    project_id = created.json()["project"]["project_id"]
    assert client.post(f"{PROJECT_BASE}/projects/{project_id}/goals/defaults", json={"operator_id": "operator"}).status_code == 200
    assert client.post(f"{PROJECT_BASE}/projects/{project_id}/scope/defaults", json={"operator_id": "operator"}).status_code == 200
    assert client.post(f"{PROJECT_BASE}/projects/{project_id}/council/defaults", json={"operator_id": "operator"}).status_code == 200
    assert client.post(
        f"{PROJECT_BASE}/projects/{project_id}/council/approve-readiness",
        json={"approved": True, "operator_id": "operator", "notes": "Ready for funding Group C."},
    ).status_code == 200
    return project_id


def test_council_to_ksiega_overview_no_active_project(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "overview.db"))
    monkeypatch.setenv("SYLION_PROJECT_START_ROOT", str(tmp_path / "projects"))

    response = client.get(BASE)

    assert response.status_code == 200
    data = response.json()
    assert data["group"]["id"] == "C"
    assert data["group"]["edge_cases"] == 98
    assert data["group"]["complete"] is False
    assert data["active_project"] is None


def test_phase20_convening_acceptance(monkeypatch, tmp_path):
    project_id = _ready_project(monkeypatch, tmp_path, "phase20.db")

    response = client.post(f"{BASE}/projects/{project_id}/phase20/convene", json={"approved": True, "operator_id": "operator"})

    assert response.status_code == 200
    payload = response.json()
    project = payload["project"]
    assert project["state"] == "READY_FOR_INITIAL_VERDICTS"
    assert len(project["deliberation"]["convening"]["awakened_roles"]) == 12
    assert len(project["deliberation"]["convening"]["key_questions"]) == 20
    assert payload["acceptance"]["accepted"] is True
    assert any(entry["event"] == "council_convened" for entry in project["audit_chain"])


def test_full_group_c_to_locked_ksiega(monkeypatch, tmp_path):
    project_id = _ready_project(monkeypatch, tmp_path, "full_group_c.db")

    phase20 = client.post(f"{BASE}/projects/{project_id}/phase20/convene", json={"approved": True, "operator_id": "operator"})
    assert phase20.status_code == 200
    assert phase20.json()["acceptance"]["accepted"] is True

    phase21 = client.post(f"{BASE}/projects/{project_id}/phase21/initial-verdicts", json={"operator_id": "operator"})
    assert phase21.status_code == 200
    assert phase21.json()["acceptance"]["accepted"] is True
    assert len(phase21.json()["project"]["deliberation"]["initial_verdicts"]["verdicts"]) == 12
    assert len(phase21.json()["project"]["deliberation"]["initial_verdicts"]["aggregation"]["per_question"]) == 20

    phase22 = client.post(f"{BASE}/projects/{project_id}/phase22/deliberate", json={"operator_id": "operator"})
    assert phase22.status_code == 200
    assert phase22.json()["acceptance"]["accepted"] is True
    assert phase22.json()["project"]["deliberation"]["rounds"]["overall_consensus"] >= 0.85
    assert phase22.json()["project"]["deliberation"]["rounds"]["round_budget"]["respected"] is True

    phase23 = client.post(
        f"{BASE}/projects/{project_id}/phase23/consolidate",
        json={"approved": True, "operator_id": "operator", "notes": "Approve Group C finalization."},
    )
    assert phase23.status_code == 200
    assert phase23.json()["acceptance"]["accepted"] is True
    assert len(phase23.json()["project"]["deliberation"]["consolidation"]["decisions"]) == 20

    phase24 = client.post(f"{BASE}/projects/{project_id}/phase24/generate-book", json={"approved": True, "operator_id": "operator"})
    assert phase24.status_code == 200
    assert phase24.json()["acceptance"]["accepted"] is True
    book = phase24.json()["project"]["deliberation"]["council_book"]
    assert Path(book["markdown"]["path"]).exists()
    assert Path(book["pdf"]["path"]).exists()
    assert len(book["sections"]) == 8

    phase25 = client.post(f"{BASE}/projects/{project_id}/phase25/finalize-ksiega", json={"approved": True, "operator_id": "operator"})
    assert phase25.status_code == 200
    payload = phase25.json()
    assert payload["acceptance"]["accepted"] is True
    assert payload["project"]["state"] == "READY_FOR_PLANNING"
    ksiega = payload["project"]["deliberation"]["ksiega"]
    assert Path(ksiega["markdown"]["path"]).exists()
    assert Path(ksiega["pdf"]["path"]).exists()
    assert Path(ksiega["structured_data"]["path"]).exists()
    assert ksiega["locked"] is True
    assert ksiega["notification"]["status"] == "generated_not_sent"
    assert any(entry["event"] == "ksiega_finalized" for entry in payload["project"]["audit_chain"])

    overview = client.get(BASE).json()
    assert overview["group"]["complete"] is True
    assert overview["group"]["edge_cases"] == 98


def test_internal_crm_group_c_uses_small_council_without_external_scope(monkeypatch, tmp_path):
    project_id = _ready_internal_crm_project(monkeypatch, tmp_path, "internal_group_c.db")

    phase20 = client.post(f"{BASE}/projects/{project_id}/phase20/convene", json={"approved": True, "operator_id": "operator"})
    assert phase20.status_code == 200
    assert phase20.json()["acceptance"]["accepted"] is True
    assert len(phase20.json()["project"]["deliberation"]["convening"]["awakened_roles"]) == 9

    phase21 = client.post(f"{BASE}/projects/{project_id}/phase21/initial-verdicts", json={"operator_id": "operator"})
    assert phase21.status_code == 200
    assert phase21.json()["acceptance"]["accepted"] is True
    project = phase21.json()["project"]
    assert len(project["deliberation"]["initial_verdicts"]["verdicts"]) == 9
    questions = " ".join(
        item["title"].lower()
        for item in project["deliberation"]["convening"]["key_questions"]
    )
    assert "ksef" not in questions
    assert "stripe" not in questions
    assert "pci" not in questions

    for endpoint in [
        "phase22/deliberate",
        "phase23/consolidate",
        "phase24/generate-book",
        "phase25/finalize-ksiega",
    ]:
        response = client.post(f"{BASE}/projects/{project_id}/{endpoint}", json={"approved": True, "operator_id": "operator"})
        assert response.status_code == 200
        assert response.json()["acceptance"]["accepted"] is True

    final_project = response.json()["project"]
    assert final_project["state"] == "READY_FOR_PLANNING"
    book_path = Path(final_project["deliberation"]["council_book"]["markdown"]["path"])
    ksiega_path = Path(final_project["deliberation"]["ksiega"]["markdown"]["path"])
    combined = f"{book_path.read_text(encoding='utf-8')} {ksiega_path.read_text(encoding='utf-8')}".lower()
    assert "ksef" not in combined
    assert "stripe" not in combined
    assert "pci" not in combined


def test_funding_group_c_uses_humangate_scope_without_payment_ksef_invoice(monkeypatch, tmp_path):
    project_id = _ready_funding_project(monkeypatch, tmp_path, "funding_group_c.db")

    phase20 = client.post(f"{BASE}/projects/{project_id}/phase20/convene", json={"approved": True, "operator_id": "operator"})
    assert phase20.status_code == 200
    assert phase20.json()["acceptance"]["accepted"] is True
    assert len(phase20.json()["project"]["deliberation"]["convening"]["awakened_roles"]) == 11

    phase21 = client.post(f"{BASE}/projects/{project_id}/phase21/initial-verdicts", json={"operator_id": "operator"})
    assert phase21.status_code == 200
    project = phase21.json()["project"]
    questions = " ".join(item["title"].lower() for item in project["deliberation"]["convening"]["key_questions"])
    assert "humangate" in questions
    for forbidden in ["ksef", "stripe", "payment", "invoice", "pci"]:
        assert forbidden not in questions

    for endpoint in [
        "phase22/deliberate",
        "phase23/consolidate",
        "phase24/generate-book",
        "phase25/finalize-ksiega",
    ]:
        response = client.post(f"{BASE}/projects/{project_id}/{endpoint}", json={"approved": True, "operator_id": "operator"})
        assert response.status_code == 200
        assert response.json()["acceptance"]["accepted"] is True

    final_project = response.json()["project"]
    assert final_project["state"] == "READY_FOR_PLANNING"
    book_path = Path(final_project["deliberation"]["council_book"]["markdown"]["path"])
    ksiega_path = Path(final_project["deliberation"]["ksiega"]["markdown"]["path"])
    combined = f"{book_path.read_text(encoding='utf-8')} {ksiega_path.read_text(encoding='utf-8')}".lower()
    assert "funding" in combined
    assert "humangate" in combined
    for forbidden in ["ksef", "stripe", "payment", "invoice", "pci", "hetzner"]:
        assert forbidden not in combined


def test_edge_cases_and_diagnosis(monkeypatch, tmp_path):
    project_id = _ready_project(monkeypatch, tmp_path, "edge.db")

    edge_cases = client.get(f"{BASE}/projects/{project_id}/edge-cases")
    diagnosis = client.post(
        f"{BASE}/projects/{project_id}/edge-cases/diagnose",
        json={"phase": "25", "case_id": "EC-D2", "context": {"source": "test"}},
    )

    assert edge_cases.status_code == 200
    assert edge_cases.json()["total"] == 98
    assert {phase for phase in edge_cases.json()["phases"]} == {"20", "21", "22", "23", "24", "25"}
    assert diagnosis.status_code == 200
    payload = diagnosis.json()
    assert payload["phase"] == "25"
    assert payload["case"]["id"] == "EC-D2"
    assert payload["requires_operator_review"] is True
    assert payload["action_plan"][-1] == "rerun phase 25 acceptance"
