from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sylion.api.app import app
import sylion.funding_autopilot.routes as funding_routes
import sylion.funding_autopilot.store as funding_store
from sylion.funding_autopilot.store import reset_funding_store
from sylion.governance.tickets import fetch_by_id, reset_ticket_store, resolve

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_funding_store(tmp_path, monkeypatch):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "funding.sqlite"))
    monkeypatch.setenv("SYLION_FUNDING_RESULTS_ROOT", str(tmp_path / "funding-results"))
    reset_ticket_store()
    reset_funding_store(str(tmp_path / "funding.sqlite"))
    funding_routes.reset_funding_route_service(str(tmp_path / "funding.sqlite"))
    yield
    if funding_store._store is not None:
        funding_store._store.close()
    funding_store._store = None
    funding_routes.reset_funding_route_service(str(tmp_path / "funding.sqlite"))
    reset_ticket_store()


def test_funding_autopilot_empty_state_endpoints():
    profile = client.get("/api/v1/funding/company-profile?company_id=default")
    assert profile.status_code == 200
    assert profile.json()["company_id"] == "default"
    assert profile.json()["legal_name"] == ""

    readiness = client.get("/api/v1/funding/company-profile/readiness?company_id=default")
    assert readiness.status_code == 200
    assert readiness.json()["readiness_score"] < 20
    assert "legal_name" in readiness.json()["missing_fields"]

    documents = client.get("/api/v1/funding/company-profile/documents?company_id=default")
    assert documents.status_code == 200
    assert documents.json()["documents"] == []

    state_aid = client.get("/api/v1/funding/company-profile/state-aid?company_id=default")
    assert state_aid.status_code == 200
    assert state_aid.json()["state_aid_total_eur"] == 0

    sources = client.get("/api/v1/funding/sources")
    assert sources.status_code == 200
    assert sources.json()["sources"] == [
        {
            "source_id": "manual",
            "label": "Import ręczny",
            "scan_mode": "live_manual",
            "programmes": 0,
            "calls": 0,
            "available": True,
        }
    ]

    deadlines = client.get("/api/v1/funding/deadlines?company_id=default")
    assert deadlines.status_code == 200
    assert deadlines.json()["deadlines"] == []

    alerts = client.get("/api/v1/funding/alerts?company_id=default")
    assert alerts.status_code == 200
    kinds = {item["kind"] for item in alerts.json()["alerts"]}
    assert "missing_company_profile_fields" in kinds
    assert "missing_company_documents" in kinds

    report = client.get("/api/v1/funding/reports/executive?company_id=default")
    assert report.status_code == 200
    assert report.json()["company_name"] == ""
    assert report.json()["open_projects"] == 0


def test_funding_calls_scored_route_is_not_shadowed_by_call_id_route():
    programme = client.post(
        "/api/v1/funding/programmes",
        json={
            "source_id": "manual",
            "name": "FENG Route Regression",
            "country": "Poland",
            "institution": "PARP",
            "funding_type": "grant",
        },
    )
    assert programme.status_code == 200

    call = client.post(
        "/api/v1/funding/calls",
        json={
            "programme_id": programme.json()["programme_id"],
            "title": "Route scoring regression call",
            "code": "ROUTE-SCORED-01",
            "country": "Poland",
            "portal_url": "https://feng.parp.gov.pl/component/grants/grants/sciezka-smart",
            "closes_at": 1_900_000_000.0,
            "themes": ["AI", "cybersecurity"],
            "target_beneficiaries": ["SME"],
        },
    )
    assert call.status_code == 200

    scored = client.get("/api/v1/funding/calls/scored?company_id=missing")
    assert scored.status_code == 200
    assert scored.json()["company_id"] == "missing"
    assert any(item["code"] == "ROUTE-SCORED-01" for item in scored.json()["calls"])


def test_funding_programme_creation_fails_closed_when_governance_ticket_fails(monkeypatch):
    def _boom(_programme):
        raise RuntimeError("governance unavailable")

    monkeypatch.setattr(funding_routes, "submit_programme_creation_ticket", _boom)

    response = client.post(
        "/api/v1/funding/programmes",
        json={
            "source_id": "manual",
            "name": "Governance Fail Closed",
            "country": "Poland",
            "institution": "PARP",
            "funding_type": "grant",
        },
    )

    assert response.status_code == 500
    assert "governance ticket" in response.json()["detail"]


def test_funding_submission_gate_blocks_approval_and_submit_when_documents_are_missing():
    profile = client.put(
        "/api/v1/funding/company-profile",
        json={
            "company_id": "default",
            "legal_name": "Razor Systems",
            "tax_id": "1234567890",
            "registration_id": "KRS0001",
            "country": "Poland",
            "legal_form": "sp. z o.o.",
            "sme_status": "SME",
            "employees": 24,
            "annual_revenue": 4200000,
            "technologies": ["AI", "Computer Vision"],
            "products": ["Industrial monitoring platform"],
            "representative_name": "Jan Kowalski",
            "representative_email": "jan@example.com",
        },
    )
    assert profile.status_code == 200

    client.post(
        "/api/v1/funding/company-profile/documents",
        json={
            "company_id": "default",
            "document_type": "financial_statement",
            "filename": "financial_statement.pdf",
            "storage_path": "C:/docs/financial_statement.pdf",
        },
    )

    programme = client.post(
        "/api/v1/funding/programmes",
        json={
            "source_id": "manual",
            "name": "FENG Smart Manufacturing",
            "country": "Poland",
            "institution": "PARP",
            "funding_type": "grant",
            "summary": "Support for digital manufacturing and AI deployment.",
        },
    )
    assert programme.status_code == 200

    programme_id = programme.json()["programme_id"]
    programme_ticket = fetch_by_id(programme.json()["governance_ticket_id"])
    assert programme_ticket is not None
    assert programme_ticket.gate_type == "blocking"
    assert programme_ticket.decision_class == "D2"
    call = client.post(
        "/api/v1/funding/calls",
        json={
            "programme_id": programme_id,
            "title": "AI for Industrial Efficiency",
            "code": "FENG-IND-AI-01",
            "country": "Poland",
            "portal_url": "https://portal.example.test/feng-ai",
            "closes_at": 1_900_000_000.0,
            "min_project_budget": 500000,
            "max_project_budget": 2500000,
            "grant_intensity_pct": 60,
            "trl_min": 4,
            "trl_max": 8,
            "target_beneficiaries": ["sme", "mid-cap"],
            "themes": ["AI", "automation", "energy efficiency"],
            "required_documents": [
                "financial_statement",
                "tax_clearance",
                "social_security_clearance",
                "incorporation_document",
            ],
            "required_partner_types": ["research_institute"],
            "eligible_costs": ["personnel", "equipment", "subcontracting"],
        },
    )
    assert call.status_code == 200
    call_id = call.json()["call_id"]
    call_ticket = fetch_by_id(call.json()["governance_ticket_id"])
    assert call_ticket is not None
    assert call_ticket.gate_type == "blocking"
    assert call_ticket.decision_class == "D2"

    project = client.post(
        "/api/v1/funding/projects",
        json={
            "company_id": "default",
            "title": "AI for Industrial Efficiency",
            "summary": "Industrial AI deployment",
            "objective": "Deploy AI into manufacturing operations",
            "category": "projekt AI",
            "budget_total": 2500000,
            "grant_requested": 1500000,
            "trl": 5,
            "call_id": call_id,
        },
    )
    assert project.status_code == 200
    project_id = project.json()["project"]["project_id"]

    application = client.post(
        "/api/v1/funding/application/create",
        json={"project_id": project_id, "company_id": "default", "call_id": call_id},
    )
    assert application.status_code == 200
    application_id = application.json()["application_id"]
    application_ticket = fetch_by_id(application.json()["governance_ticket_id"])
    assert application_ticket is not None
    assert application_ticket.gate_type == "financial"
    assert application_ticket.decision_class == "D3"

    prepared = client.post(
        "/api/v1/funding/submission/prepare",
        json={"application_id": application_id, "portal_url": "https://portal.example.test/feng-ai"},
    )
    assert prepared.status_code == 200
    session_id = prepared.json()["session_id"]

    empty_receipt = client.get(f"/api/v1/funding/submission/receipt?session_id={session_id}")
    assert empty_receipt.status_code == 200
    assert empty_receipt.json()["receipt"] == {}

    filled = client.post("/api/v1/funding/submission/fill", json={"session_id": session_id})
    assert filled.status_code == 200
    assert filled.json()["status"] == "blocked_missing_documents"

    draft = client.post("/api/v1/funding/submission/save-draft", json={"session_id": session_id})
    assert draft.status_code == 200
    assert draft.json()["status"] == "blocked_missing_documents"

    approval = client.post(
        "/api/v1/funding/submission/request-approval",
        json={"session_id": session_id, "notes": "Try to bypass missing documents"},
    )
    assert approval.status_code == 400
    assert "missing" in approval.json()["detail"].lower()

    submit = client.post(
        "/api/v1/funding/submission/submit",
        json={
            "session_id": session_id,
            "approved_by": "operator@example.com",
            "confirm_legal": True,
            "confirm_budget": True,
            "confirm_documents": True,
            "portal_submission_reference": "PORTAL-REF-001",
        },
    )
    assert submit.status_code == 400
    assert "missing" in submit.json()["detail"].lower()

    for document_type in ["tax_clearance", "social_security_clearance", "incorporation_document"]:
        response = client.post(
            "/api/v1/funding/company-profile/documents",
            json={
                "company_id": "default",
                "document_type": document_type,
                "filename": f"{document_type}.pdf",
                "storage_path": f"C:/docs/{document_type}.pdf",
            },
        )
        assert response.status_code == 200

    application_docs = client.get(f"/api/v1/funding/application/{application_id}/documents")
    assert application_docs.status_code == 200
    assert application_docs.json()["missing_documents"] == []

    review = client.post(
        f"/api/v1/funding/application/{application_id}/review",
        json={"review_modes": ["formal", "financial"]},
    )
    assert review.status_code == 200
    assert review.json()["review"]["readiness"] == "ready"

    refilled = client.post("/api/v1/funding/submission/fill", json={"session_id": session_id})
    assert refilled.status_code == 200
    assert refilled.json()["status"] == "form_mapping_ready"
    assert refilled.json()["validation_json"]["missing_documents"] == []

    redraft = client.post("/api/v1/funding/submission/save-draft", json={"session_id": session_id})
    assert redraft.status_code == 200
    assert redraft.json()["status"] == "draft_saved"

    approval_after_documents = client.post(
        "/api/v1/funding/submission/request-approval",
        json={"session_id": session_id, "notes": "Documents completed after first blocked attempt"},
    )
    assert approval_after_documents.status_code == 200
    assert approval_after_documents.json()["status"] == "pending"
    approval_ticket = fetch_by_id(approval_after_documents.json()["payload_json"]["governance_ticket_id"])
    assert approval_ticket is not None
    assert approval_ticket.gate_type == "financial"
    assert approval_ticket.decision_class == "D4"


def test_funding_autopilot_end_to_end_flow():
    profile = client.put(
        "/api/v1/funding/company-profile",
        json={
            "company_id": "default",
            "legal_name": "Razor Systems",
            "tax_id": "1234567890",
            "registration_id": "KRS0001",
            "country": "Poland",
            "region": "Mazowieckie",
            "city": "Warsaw",
            "legal_form": "sp. z o.o.",
            "sme_status": "SME",
            "employees": 24,
            "annual_revenue": 4200000,
            "ebitda": 650000,
            "technologies": ["AI", "Computer Vision", "IoT"],
            "products": ["Industrial monitoring platform"],
            "services": ["Predictive maintenance"],
            "team_competencies": ["ML engineering", "Embedded systems"],
            "strategic_goals": ["energy efficiency", "automation", "export"],
            "representative_name": "Jan Kowalski",
            "representative_email": "jan@example.com",
            "export_markets": ["Germany", "Poland"],
        },
    )
    assert profile.status_code == 200
    assert profile.json()["legal_name"] == "Razor Systems"

    for document_type in [
        "financial_statement",
        "tax_clearance",
        "social_security_clearance",
        "incorporation_document",
    ]:
        response = client.post(
            "/api/v1/funding/company-profile/documents",
            json={
                "company_id": "default",
                "document_type": document_type,
                "filename": f"{document_type}.pdf",
                "storage_path": f"C:/docs/{document_type}.pdf",
            },
        )
        assert response.status_code == 200

    readiness = client.get("/api/v1/funding/company-profile/readiness?company_id=default")
    assert readiness.status_code == 200
    assert readiness.json()["readiness_score"] >= 80

    programme = client.post(
        "/api/v1/funding/programmes",
        json={
            "source_id": "manual",
            "name": "FENG Smart Manufacturing",
            "country": "Poland",
            "institution": "PARP",
            "funding_type": "grant",
            "summary": "Support for digital manufacturing and AI deployment.",
        },
    )
    assert programme.status_code == 200
    programme_id = programme.json()["programme_id"]
    programme_ticket = fetch_by_id(programme.json()["governance_ticket_id"])
    assert programme_ticket is not None
    assert programme_ticket.gate_type == "blocking"
    assert programme_ticket.decision_class == "D2"

    closes_at = 1_900_000_000.0
    call = client.post(
        "/api/v1/funding/calls",
        json={
            "programme_id": programme_id,
            "title": "AI for Industrial Efficiency",
            "code": "FENG-IND-AI-01",
            "country": "Poland",
            "portal_url": "https://portal.example.test/feng-ai",
            "closes_at": closes_at,
            "min_project_budget": 500000,
            "max_project_budget": 2500000,
            "grant_intensity_pct": 60,
            "trl_min": 4,
            "trl_max": 8,
            "target_beneficiaries": ["sme", "mid-cap"],
            "themes": ["AI", "automation", "energy efficiency"],
            "required_documents": [
                "financial_statement",
                "tax_clearance",
                "social_security_clearance",
                "incorporation_document",
            ],
            "required_partner_types": ["research_institute"],
            "eligible_costs": ["personnel", "equipment", "subcontracting"],
        },
    )
    assert call.status_code == 200
    call_id = call.json()["call_id"]
    call_ticket = fetch_by_id(call.json()["governance_ticket_id"])
    assert call_ticket is not None
    assert call_ticket.gate_type == "blocking"
    assert call_ticket.decision_class == "D2"

    search = client.post(
        "/api/v1/funding/calls/search",
        json={"company_id": "default", "query": "AI automation", "beneficiary_type": "sme"},
    )
    assert search.status_code == 200
    assert search.json()["calls"][0]["call_id"] == call_id

    ideas = client.post("/api/v1/funding/ideas/generate", json={"company_id": "default", "limit": 3})
    assert ideas.status_code == 200
    assert len(ideas.json()["ideas"]) >= 1
    idea_id = ideas.json()["ideas"][0]["idea_id"]

    project = client.post(
        f"/api/v1/funding/ideas/{idea_id}/convert-to-project",
        json={"company_id": "default", "call_id": call_id, "target_trl": 5},
    )
    assert project.status_code == 200
    conversion_payload = project.json()
    assert conversion_payload["status"] == "pending_human_gate"
    conversion_ticket = fetch_by_id(conversion_payload["governance_ticket_id"])
    assert conversion_ticket is not None
    assert conversion_ticket.state == "pending"
    assert conversion_ticket.gate_type == "blocking"
    assert conversion_ticket.decision_class == "D3"
    assert conversion_ticket.payload["project_id"] == ""

    resolve(conversion_payload["governance_ticket_id"], "approved", "test approves funding project conversion", "operator@example.com")
    resolved_ticket = fetch_by_id(conversion_payload["governance_ticket_id"])
    assert resolved_ticket is not None
    projects_after_gate = client.get("/api/v1/funding/projects?company_id=default")
    assert projects_after_gate.status_code == 200
    project_id = projects_after_gate.json()["projects"][0]["project_id"]
    assert project_id.startswith("fund_project_")

    consortium = client.post("/api/v1/funding/consortium/analyze", json={"project_id": project_id})
    assert consortium.status_code == 200
    assert "research_institute" in consortium.json()["required_partner_types"]

    partners = client.post(
        "/api/v1/funding/consortium/partners/search",
        json={
            "project_id": project_id,
            "company_id": "default",
            "candidates": [
                {
                    "name": "Warsaw Tech Lab",
                    "partner_type": "research_institute",
                    "country": "Poland",
                    "expertise": ["AI", "energy efficiency", "embedded systems"],
                    "grant_track_record": 6,
                    "contact_email": "lab@example.com",
                }
            ],
        },
    )
    assert partners.status_code == 200
    partner_id = partners.json()["partners"][0]["partner_id"]

    shortlist = client.post("/api/v1/funding/consortium/partners/shortlist", json={"project_id": project_id, "limit": 3})
    assert shortlist.status_code == 200
    assert shortlist.json()["shortlist"][0]["partner_id"] == partner_id

    outreach = client.post(
        "/api/v1/funding/consortium/outreach/generate",
        json={"project_id": project_id, "partner_ids": [partner_id]},
    )
    assert outreach.status_code == 200
    assert len(outreach.json()["messages"]) == 1

    matching = client.post("/api/v1/funding/matching/run", json={"project_id": project_id, "top_k": 3})
    assert matching.status_code == 200
    assert matching.json()["matches"][0]["call_id"] == call_id

    eligibility = client.post("/api/v1/funding/eligibility/check", json={"project_id": project_id, "call_id": call_id})
    assert eligibility.status_code == 200
    assert eligibility.json()["eligible"] is True

    scoring = client.post("/api/v1/funding/scoring/run", json={"project_id": project_id, "call_id": call_id})
    assert scoring.status_code == 200
    assert scoring.json()["grant_success_probability"] > 0

    application = client.post(
        "/api/v1/funding/application/create",
        json={"project_id": project_id, "company_id": "default", "call_id": call_id},
    )
    assert application.status_code == 200
    application_id = application.json()["application_id"]
    application_ticket = fetch_by_id(application.json()["governance_ticket_id"])
    assert application_ticket is not None
    assert application_ticket.gate_type == "financial"
    assert application_ticket.decision_class == "D3"

    application_docs = client.get(f"/api/v1/funding/application/{application_id}/documents")
    assert application_docs.status_code == 200
    assert application_docs.json()["missing_documents"] == []
    assert sorted(application_docs.json()["available_documents"]) == [
        "financial_statement",
        "incorporation_document",
        "social_security_clearance",
        "tax_clearance",
    ]

    review = client.post(
        f"/api/v1/funding/application/{application_id}/review",
        json={"review_modes": ["formal", "financial", "technical", "market"]},
    )
    assert review.status_code == 200
    assert review.json()["review"]["readiness"] == "ready"

    export = client.post(f"/api/v1/funding/application/{application_id}/export")
    assert export.status_code == 200
    exports = export.json()["exports"]
    assert Path(exports["json"]).is_file()
    assert Path(exports["markdown"]).is_file()
    assert Path(exports["pdf"]).is_file()
    assert Path(exports["xlsx"]).is_file()
    assert Path(exports["zip"]).is_file()

    pdf_download = client.get(f"/api/v1/funding/application/{application_id}/export/pdf")
    assert pdf_download.status_code == 200
    assert pdf_download.headers["content-type"].startswith("application/pdf")
    assert pdf_download.content.startswith(b"%PDF")

    xlsx_download = client.get(f"/api/v1/funding/application/{application_id}/export/xlsx")
    assert xlsx_download.status_code == 200
    assert xlsx_download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert xlsx_download.content.startswith(b"PK")

    unknown_export = client.get(f"/api/v1/funding/application/{application_id}/export/exe")
    assert unknown_export.status_code == 404

    prepared = client.post(
        "/api/v1/funding/submission/prepare",
        json={"application_id": application_id, "portal_url": "https://portal.example.test/feng-ai"},
    )
    assert prepared.status_code == 200
    session_id = prepared.json()["session_id"]

    filled = client.post("/api/v1/funding/submission/fill", json={"session_id": session_id})
    assert filled.status_code == 200
    assert filled.json()["prepared_fields_json"]["project_title"]

    draft = client.post("/api/v1/funding/submission/save-draft", json={"session_id": session_id})
    assert draft.status_code == 200
    assert draft.json()["draft_reference"].startswith("draft-")

    approval = client.post(
        "/api/v1/funding/submission/request-approval",
        json={"session_id": session_id, "notes": "Final legal review complete"},
    )
    assert approval.status_code == 200
    approval_json = approval.json()
    assert approval_json["status"] == "pending"
    governance_ticket_id = approval_json["payload_json"]["governance_ticket_id"]
    governance_ticket = fetch_by_id(governance_ticket_id)
    assert governance_ticket is not None
    assert governance_ticket.decision_class == "D4"
    assert governance_ticket.gate_type == "financial"
    assert governance_ticket.state == "pending"

    blocked_submit = client.post(
        "/api/v1/funding/submission/submit",
        json={
            "session_id": session_id,
            "approved_by": "operator@example.com",
            "confirm_legal": True,
            "confirm_budget": True,
            "confirm_documents": True,
            "portal_submission_reference": "PORTAL-REF-001",
        },
    )
    assert blocked_submit.status_code == 400
    assert "Human Gate approval" in blocked_submit.json()["detail"]

    assert resolve(governance_ticket_id, "approved", reviewer="operator@example.com") is True
    submit = client.post(
        "/api/v1/funding/submission/submit",
        json={
            "session_id": session_id,
            "approved_by": "operator@example.com",
            "confirm_legal": True,
            "confirm_budget": True,
            "confirm_documents": True,
            "portal_submission_reference": "PORTAL-REF-001",
        },
    )
    assert submit.status_code == 200
    assert submit.json()["receipt"]["portal_submission_reference"] == "PORTAL-REF-001"
    assert submit.json()["governance_ticket_id"] == governance_ticket_id

    receipt = client.get(f"/api/v1/funding/submission/receipt?session_id={session_id}")
    assert receipt.status_code == 200
    assert receipt.json()["receipt"]["submitted_by"] == "operator@example.com"

    crm = client.get("/api/v1/funding/crm/applications?company_id=default")
    assert crm.status_code == 200
    assert crm.json()["applications"][0]["status"] == "submitted"

    deadlines = client.get("/api/v1/funding/deadlines?company_id=default")
    assert deadlines.status_code == 200
    assert any(item["type"] == "call_deadline" for item in deadlines.json()["deadlines"])

    alerts = client.get("/api/v1/funding/alerts?company_id=default")
    assert alerts.status_code == 200
    assert isinstance(alerts.json()["alerts"], list)

    report = client.get("/api/v1/funding/reports/executive?company_id=default")
    assert report.status_code == 200
    assert report.json()["company_name"] == "Razor Systems"
