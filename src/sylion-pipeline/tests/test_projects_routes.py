from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from sylion.api.app import app
import sylion.api.ai_workspace_routes as _routes
import sylion.api.idea_routes as _idea_routes_api
import sylion.api.pipeline_routes as _pipeline_routes
import sylion.api.projects_routes as _project_routes_api
import sylion.project_mode.store as _project_store
import sylion.skills.registry as _skills_registry

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_project_mode(tmp_path, monkeypatch):
    from sylion.cognitive.chat_engine import ChatEngine
    from sylion.governance.council_hybrid import CouncilHybrid
    from sylion.governance.council_hybrid import reset_council_hybrid
    from sylion.governance.ticket import reset_ticket_store
    from sylion.security.key_vault import KeyVault
    from sylion.cognitive.prompt_templates import PromptTemplateManager
    from sylion.memory.book_generator import BookGenerator
    from sylion.governance.human_gate import HumanGate
    from sylion.cognitive.idea_vault import IdeaVault
    from sylion.governance.audit_chain import reset_audit_chain
    from sylion.security.audit_trail_aggregator import reset_audit_trail_aggregator
    from sylion.aeis.advisor.engine import _db as advisor_engine_db
    from sylion.aeis.advisor.engine.llm_judge import client as judge_client_module
    from sylion.aeis.advisor.engine.llm_judge.client import JudgeResponse
    from sylion.aeis.advisor.engine.rule_engine.loader import invalidate_cache
    from sylion.aeis.advisor.engine.service import reset_engine_service

    class StubLLM:
        def call_messages(self, model_id, messages, max_tokens=1000):
            return {
                "call_id": "stub-call-001",
                "text": "AEIS_STUB_REPLY",
                "tokens": 7,
                "cost": 0.0,
                "latency_ms": 1,
            }

    class StubJudgeClient:
        def call(self, model_id, prompt, max_tokens=2048, temperature=0.3, timeout_s=30.0):
            return JudgeResponse(
                text=(
                    '{"rationale":"Test judge rationale is deliberately long enough to satisfy the runtime '
                    'validator while still being deterministic. It confirms that the project event is visible, '
                    'auditable, and should create a real advisor card for the operator workflow.",'
                    '"recommendation":"review this lifecycle event",'
                    '"expected_benefit":"keeps project visible to operator",'
                    '"expected_downside":"test fixture only; no external action is executed",'
                    '"quality_impact":"structured card creation remains covered by a non-empty rationale"}'
                ),
                model_id=model_id,
                prompt_tokens=12,
                response_tokens=12,
                latency_ms=1,
                provider_id="test",
                cost_usd=0.0,
                was_stub=True,
            )

    class FakePipelineController:
        def submit_idea(self, idea, context=None):
            return {"run_id": "run_fake_001", "status": "pending", "idea": idea, "context": context or {}}

        def execute_run(self, run_id):
            return {"run_id": run_id, "status": "complete", "steps": []}

    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "project_mode.sqlite"))
    monkeypatch.setenv("SYLION_PROJECT_RESULTS_ROOT", str(tmp_path / "project-results"))
    monkeypatch.setattr(advisor_engine_db, "_use_sqlite_store", lambda: True)
    monkeypatch.setattr(advisor_engine_db, "_sqlite_db_path", lambda: str(tmp_path / "advisor_engine.sqlite"))
    if advisor_engine_db._sqlite_conn is not None:
        advisor_engine_db._sqlite_conn.close()
    advisor_engine_db._sqlite_conn = None
    reset_engine_service()
    invalidate_cache()
    judge_client_module._client = StubJudgeClient()
    reset_audit_trail_aggregator(db_path=tmp_path / "audit_trail.sqlite")
    reset_audit_chain(db_path=tmp_path / "governance_chain.sqlite")
    reset_ticket_store(db_path=tmp_path / "governance_tickets.sqlite")
    reset_council_hybrid(db_path=tmp_path / "hybrid_council.sqlite")
    if _routes._workspace_state_conn is not None:
        _routes._workspace_state_conn.close()
    _routes._workspace_state_conn = None
    _routes._workspace_state_loaded = False
    if _routes._project_store is not None:
        _routes._project_store.close()
    _routes._project_store = None
    if _project_store._store is not None:
        _project_store._store.close()
    _project_store._store = None
    _skills_registry._registry = None

    _routes._chat_engine = ChatEngine()
    _routes._council = CouncilHybrid()
    _routes._vault = KeyVault()
    _routes._prompts = PromptTemplateManager()
    _routes._books = BookGenerator()
    _routes._llm = StubLLM()
    _routes._hg = HumanGate()
    _routes._idea_vault = IdeaVault()
    _idea_routes_api._idea_vault = IdeaVault(db_path=tmp_path / "ideas.sqlite")
    _routes._idea_attachments = None
    _routes._workspace_notifications.clear()
    _routes._project_kickoffs.clear()
    _routes._hg_workflows.clear()
    _routes._project_launch_futures.clear()
    _pipeline_routes._controller = FakePipelineController()

    yield

    _project_routes_api.wait_for_project_kickoffs(timeout_s=10.0)
    if _routes._workspace_state_conn is not None:
        _routes._workspace_state_conn.close()
    _routes._workspace_state_conn = None
    _routes._workspace_state_loaded = False
    if _routes._project_store is not None:
        _routes._project_store.close()
    _routes._project_store = None
    if _project_store._store is not None:
        _project_store._store.close()
    _project_store._store = None
    _skills_registry._registry = None
    _routes._chat_engine = None
    _routes._council = None
    _routes._vault = None
    _routes._prompts = None
    _routes._books = None
    _routes._llm = None
    _routes._hg = None
    _routes._idea_vault = None
    _idea_routes_api._idea_vault = None
    _routes._idea_attachments = None
    _routes._workspace_notifications.clear()
    _routes._project_kickoffs.clear()
    _routes._hg_workflows.clear()
    _routes._project_launch_futures.clear()
    _pipeline_routes._controller = None
    if advisor_engine_db._sqlite_conn is not None:
        advisor_engine_db._sqlite_conn.close()
    advisor_engine_db._sqlite_conn = None
    reset_engine_service()
    invalidate_cache()
    judge_client_module._client = None


def _create_project() -> dict:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"Chat Project {uuid4().hex[:6]}",
            "idea_raw": "zbuduj prosty komunikator z rejestracją, logowaniem, pokojami i wiadomościami",
            "constraints": "offline-first",
            "preferred_stack": ["Next.js", "FastAPI", "SQLite"],
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    return response.json()


def _approve_freeze(project_id: str, target: str) -> dict:
    freeze = client.post(f"/api/v1/projects/{project_id}/{target}/freeze")
    assert freeze.status_code == 200
    payload = freeze.json()
    ticket_id = payload.get("pending_governance_ticket_id")
    if ticket_id:
        resolved = client.post(
            f"/api/v1/governance/tickets/{ticket_id}/resolve",
            json={
                "decision": "approved",
                "reason": f"test approves {target} freeze",
                "reviewer": "operator@example.com",
            },
        )
        assert resolved.status_code == 200
        freeze = client.post(f"/api/v1/projects/{project_id}/{target}/freeze")
        assert freeze.status_code == 200
        payload = freeze.json()
    return payload


def test_project_routes_create_and_list():
    created = _create_project()
    project_id = created["project"]["project_id"]

    listing = client.get("/api/v1/projects")
    assert listing.status_code == 200
    projects = listing.json()["projects"]
    assert any(item["project_id"] == project_id for item in projects)

    detail = client.get(f"/api/v1/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json()["project_id"] == project_id


def test_idea_promotion_preserves_source_idea_id():
    created = client.post(
        "/api/v1/ideas",
        json={
            "title": "Generator opisow marketplace",
            "description": (
                "Aplikacja analizuje zdjecia produktu, generuje opisy PL EN DE, "
                "waliduje EAN i eksportuje CSV do Allegro oraz Amazon."
            ),
            "author": "operator",
            "tags": ["ecommerce", "marketplace"],
        },
    )
    assert created.status_code == 201
    idea_id = created.json()["idea_id"]

    promoted = client.post(
        f"/api/v1/ideas/{idea_id}/promote-to-project",
        json={
            "project_name": "Projekt z promowanej idei",
            "constraints": "traceability required",
            "preferred_stack": ["HTML", "FastAPI", "SQLite"],
            "owner_id": "workspace-default",
        },
    )
    assert promoted.status_code == 200
    project = promoted.json()["project"]
    project_id = project["project_id"]
    assert project["source_idea_id"] == idea_id

    detail = client.get(f"/api/v1/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json()["source_idea_id"] == idea_id


def test_idea_promotion_respects_zero_vps_runtime_questions():
    created = client.post(
        "/api/v1/ideas",
        json={
            "title": "ServiceOps zero VPS",
            "description": (
                "Zbuduj system zarzadzania projektami i operacjami: portfolio projektow, backlog, Kanban, "
                "roadmap, sprinty, capacity planning i audit trail. Runtime local-first, trzy srodowiska lokalne "
                "dev/staging/test-lab, zero VPS, zero Hetzner, zero produkcji i zero uploadow."
            ),
            "author": "operator",
            "tags": ["operacje", "local-first"],
        },
    )
    assert created.status_code == 201

    promoted = client.post(
        f"/api/v1/ideas/{created.json()['idea_id']}/promote-to-project",
        json={
            "project_name": "ServiceOps zero VPS",
            "owner_id": "workspace-default",
        },
    )
    assert promoted.status_code == 200
    project = promoted.json()["project"]
    runtime_question = next(question for question in project["questions"] if question["key"] == "runtime_policy")
    runtime_choice_text = " ".join(
        f"{choice['label']} {choice['rationale']} {choice['consequences']}"
        for choice in runtime_question["choices"]
    )

    assert project["canon_snapshot"]["runtime_constraints"]["vps_blocked_until_human_gate"] is True
    assert "Pozwala zaplanowac VPS" not in runtime_choice_text
    assert "Hybrid later" not in runtime_choice_text
    assert "Tylko Change Proposal" in runtime_choice_text


def test_idea_promotion_blocks_pending_humangate():
    created = client.post(
        "/api/v1/ideas",
        json={
            "title": "Portal HR D4",
            "description": "Portal HR z PII, GDPR, DSR, DPIA i dokumentami kadrowymi.",
            "author": "operator",
            "tags": ["hr", "pii_high", "gdpr"],
        },
    )
    assert created.status_code == 201
    idea_id = created.json()["idea_id"]

    gated = client.put(
        f"/api/v1/ideas/{idea_id}",
        json={"status": "awaiting_approval", "author": "operator"},
    )
    assert gated.status_code == 200
    assert gated.json()["human_gate_required"] == 1
    assert gated.json()["human_gate_decision"] == ""

    promoted = client.post(
        f"/api/v1/ideas/{idea_id}/promote-to-project",
        json={"project_name": "Portal HR bez HG"},
    )

    assert promoted.status_code == 409
    assert "HumanGate" in promoted.json()["detail"]


def test_simple_crm_idea_promotion_stays_small_application():
    created = client.post(
        "/api/v1/ideas",
        json={
            "title": "Mini CRM local",
            "description": (
                "Create a simple local CRM for a small service company: customer list, "
                "contact status, notes, search filter, no external integrations, local-only artifact, "
                "cheap_slow resource profile, minimal council and workers, full Human Gate before promotion."
            ),
            "author": "operator",
            "tags": ["crm", "local"],
        },
    )
    assert created.status_code == 201
    idea_id = created.json()["idea_id"]

    promoted = client.post(
        f"/api/v1/ideas/{idea_id}/promote-to-project",
        json={
            "project_name": "Mini CRM local",
            "constraints": "local-only",
            "preferred_stack": ["HTML", "FastAPI", "SQLite"],
            "owner_id": "workspace-default",
        },
    )
    assert promoted.status_code == 200
    project = promoted.json()["project"]

    assert project["project_kind"] == "application"
    assert project["worker_plan"]["modules"] == [
        "application_core",
        "interface_layer",
        "integration_validation",
    ]
    assert "project_management_system" not in project["canonical_book"]
    assert "gantt_roadmap" not in project["masterplan"]
    assert "tenant_workspace" not in project["worker_plan"]["modules"]


def test_hr_idea_promotion_uses_employee_portal_blueprint():
    created = client.post(
        "/api/v1/ideas",
        json={
            "title": "Portal HR z dokumentami",
            "description": (
                "Portal pracowniczy HR z logowaniem SSO LDAP, dokumentami kadrowymi, "
                "wnioskami urlopowymi, GDPR DSR, DPIA, DPO, PII high, session timeout, "
                "rate limit i password policy."
            ),
            "author": "operator",
            "tags": ["hr", "pii_high", "gdpr"],
        },
    )
    assert created.status_code == 201
    idea_id = created.json()["idea_id"]

    promoted = client.post(
        f"/api/v1/ideas/{idea_id}/promote-to-project",
        json={
            "project_name": "Portal HR D4",
            "constraints": "D4 HumanGate and DPIA required",
            "preferred_stack": ["HTML", "FastAPI", "SQLite"],
            "owner_id": "workspace-default",
        },
    )
    assert promoted.status_code == 200
    project = promoted.json()["project"]

    assert project["source_idea_id"] == idea_id
    assert project["project_kind"] == "employee_portal"
    assert project["worker_plan"]["modules"] == [
        "auth_users",
        "role_assignment",
        "document_workflow",
        "leave_request_workflow",
        "gdpr_dsr",
        "security_session_policy",
        "audit_evidence_pack",
        "integration_validation",
    ]
    roles = {member["role"] for member in project["council_plan"]["members"]}
    assert {"security_sentinel", "compliance_officer", "red_team"} <= roles
    assert project["governance_policy"]["decision_class"] == "D4"
    assert project["governance_policy"]["dpia_required"] is True


def test_operator_mobile_idea_promotion_uses_offline_firmware_blueprint():
    created = client.post(
        "/api/v1/ideas",
        json={
            "title": "Mobilny asystent serwisowy offline",
            "description": (
                "Aplikacja mobilna dla technikow serwisowych. Ma dzialac offline, obslugiwac checklisty, "
                "zalaczniki firmware .ino i .bin, zdjecia dowodowe z redakcja PII, sync queue, "
                "device binding i HumanGate przed firmware upload oraz zewnetrznym sync."
            ),
            "author": "operator",
            "tags": ["mobile", "offline", "firmware", "serwis"],
        },
    )
    assert created.status_code == 201
    idea_id = created.json()["idea_id"]

    promoted = client.post(
        f"/api/v1/ideas/{idea_id}/promote-to-project",
        json={
            "project_name": "Mobilny serwis D4",
            "constraints": "D4 HumanGate for firmware, photo PII and external sync",
            "preferred_stack": ["HTML", "JavaScript", "SQLite"],
            "owner_id": "workspace-default",
        },
    )
    assert promoted.status_code == 200
    project = promoted.json()["project"]

    assert project["source_idea_id"] == idea_id
    assert project["project_kind"] == "operator_mobile"
    assert project["worker_plan"]["modules"] == [
        "mobile_shell",
        "offline_checklists",
        "firmware_attachment_guard",
        "photo_evidence_redaction",
        "sync_queue",
        "device_binding",
        "secure_approval",
        "audit_evidence_pack",
        "integration_validation",
    ]
    roles = {member["role"] for member in project["council_plan"]["members"]}
    assert {"security_sentinel", "mobile_specialist", "red_team"} <= roles
    assert project["governance_policy"]["decision_class"] == "D4"
    assert project["governance_policy"]["offline_mode"] is True
    assert "firmware_upload" in project["governance_policy"]["human_gate_required_for"]
    assert "photo_evidence_redaction" in project["canonical_book"]

    skills = client.get(f"/api/v1/projects/{project['project_id']}/skills")
    assert skills.status_code == 200
    skill_payload = skills.json()
    assert {
        "aeis.offline-checklist-builder",
        "aeis.firmware-attachment-guard",
        "aeis.photo-evidence-redactor",
        "aeis.sync-queue-governance",
    } <= set(skill_payload["skill_ids"])
    assert any(item["reused_skill_id"] == "aeis.firmware-attachment-guard" for item in skill_payload["reuse_log"])


def test_project_management_system_uses_portfolio_release_blueprint():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Rozbudowany system projektowy",
            "idea_raw": (
                "System projektowy dla software house: portfolio projektow, Kanban, Gantt, backlog, sprinty, "
                "resource capacity, risk register, budzet projektu, RBAC audit, integracje API, release gate, "
                "canary i deploy na Hetzner VPS."
            ),
            "constraints": "D4 HumanGate dla produkcji, RBAC, integracji API i budzetu",
            "preferred_stack": ["HTML", "JavaScript", "FastAPI", "SQLite"],
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]

    assert project["project_kind"] == "project_management_system"
    assert project["worker_plan"]["modules"] == [
        "tenant_workspace",
        "portfolio_dashboard",
        "kanban_backlog",
        "gantt_roadmap",
        "resource_capacity",
        "risk_register",
        "budget_tracking",
        "notification_center",
        "api_integrations",
        "rbac_audit",
        "release_governance",
        "integration_validation",
    ]
    assert project["governance_policy"]["decision_class"] == "D4"
    assert "production_deploy" in project["governance_policy"]["human_gate_required_for"]
    assert "rollback_delete_cloud_resource" in project["governance_policy"]["human_gate_required_for"]

    skills = client.get(f"/api/v1/projects/{project['project_id']}/skills")
    assert skills.status_code == 200
    skill_ids = set(skills.json()["skill_ids"])
    assert {
        "aeis.project-management-workflow",
        "aeis.kanban-gantt-builder",
        "aeis.budget-risk-control",
        "aeis.rbac-audit-governance",
        "aeis.release-deploy-governance",
    } <= skill_ids


def test_project_management_system_respects_local_first_vps_block():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "LocalOps Control Center local runtime",
            "idea_raw": (
                "Zbuduj lokalny system SaaS dla zespolu serwisowego: panel operatora, API zgloszen, "
                "harmonogramy, raporty SLA, faktury testowe, modul klientow i audit trail. Rada modeli "
                "ma miec planner, architect, adversarial critic, security sentinel, cost sentinel i verifier. "
                "Runtime ma byc local-first z trzema lokalnymi srodowiskami: dev, staging i test-lab. "
                "VPS, Hetzner, produkcja, wysylki, uploady i akcje zewnetrzne sa zabronione bez Human Gate. Wymagane: Source of Truth, "
                "Masterplan, Quality Gates, test jak czlowiek i zapis do memory."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]

    assert project["project_kind"] == "project_management_system"
    runtime_constraints = project["canon_snapshot"]["runtime_constraints"]
    assert runtime_constraints["vps_blocked_until_human_gate"] is True
    assert runtime_constraints["local_environment_count"] == 3
    assert runtime_constraints["production_blocked_until_human_gate"] is True
    assert runtime_constraints["external_blocked_until_human_gate"] is True
    assert project["canon_snapshot"]["production_vps_scope"] == "blocked_future_human_gate"
    assert "utworz Hetzner VPS" not in project["masterplan"]
    assert "Hetzner deploy" not in project["masterplan"]
    assert "- vps_capacity_policy" not in project["masterplan"]
    runtime_question = next(question for question in project["questions"] if question["key"] == "runtime_policy")
    runtime_choice_text = " ".join(
        f"{choice['label']} {choice['rationale']} {choice['consequences']}"
        for choice in runtime_question["choices"]
    )
    assert "Pozwala zaplanowac VPS" not in runtime_choice_text
    assert "Hybrid later" not in runtime_choice_text
    assert "Tylko Change Proposal" in runtime_choice_text
    assert "future Change Proposal" in project["masterplan"]
    assert "VPS, produkcja i akcje zewnetrzne pozostaja zablokowane" in project["canonical_book"]


def test_project_management_system_respects_zero_vps_hetzner_wording():
    from sylion.project_mode.engine import _project_management_artifact

    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Zero external runtime wording",
            "idea_raw": (
                "Zbuduj ServiceOps Control Tower jako system zarzadzania projektami i operacjami: "
                "portfolio projektow, backlog, Kanban, roadmap, sprinty, capacity planning i audit trail. "
                "Wymagania: runtime local-first, "
                "trzy srodowiska lokalne dev/staging/test-lab, zero VPS, zero Hetzner, zero produkcji, "
                "zero wysylek zewnetrznych i zero uploadow. Human Gate dla SoT, Masterplanu, kosztow i finalu."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    runtime_constraints = project["canon_snapshot"]["runtime_constraints"]

    assert project["project_kind"] == "project_management_system"
    assert runtime_constraints["vps_blocked_until_human_gate"] is True
    assert runtime_constraints["production_blocked_until_human_gate"] is True
    assert runtime_constraints["external_blocked_until_human_gate"] is True
    assert runtime_constraints["local_environment_count"] == 3
    assert project["canon_snapshot"]["production_vps_scope"] == "blocked_future_human_gate"
    assert "utworz Hetzner VPS" not in project["masterplan"]
    assert "Hetzner deploy" not in project["masterplan"]
    assert "- vps_capacity_policy" not in project["masterplan"]
    artifact = _project_management_artifact(project)
    assert "Hetzner-ready" not in artifact
    assert "bez Hetznera i VPS" in artifact


def test_project_management_system_does_not_treat_decision_variants_as_bioinformatics():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "ServiceOps variants are governance variants",
            "idea_raw": (
                "Projekt testowy do audytu jak czlowiek: zbuduj lokalny cockpit ServiceOps z API, UI, "
                "audit trail, Human Gate, Council z twarda rola Adversarial Critic, pamiecia, skills, "
                "testami human-like i czterema srodowiskami lokalnymi: dev, staging, qa-lab, release-lab. "
                "Wymagania: local-first, zero VPS, zero Hetznera, zero produkcji, zero external upload, "
                "zero kosztu. Sprawdz skalowanie workerow lokalnych, wybor wariantow A/B/C/D/E, "
                "Source of Truth, Masterplan, wykonanie, testy i closure bez dzialan zewnetrznych."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]

    assert project["project_kind"] == "project_management_system"
    assert project["canon_snapshot"]["domain_profile"]["primary_domain"] == "project_operations"
    assert project["canon_snapshot"]["runtime_constraints"]["local_environment_count"] == 4
    assert project["canon_snapshot"]["runtime_constraints"]["external_blocked_until_human_gate"] is True
    assert "dev, staging, qa-lab, release-lab" in project["canonical_book"]
    assert "clinical_safety_guard" not in project["worker_plan"]["modules"]
    assert "sample_pseudonymization" not in project["worker_plan"]["modules"]


def test_project_management_system_infers_environment_count_from_explicit_labels():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "ServiceOps explicit six local environments",
            "idea_raw": (
                "Zbuduj zlozony projekt testowy AEIS: centrum operacyjne ServiceOps dla incidentow, "
                "kosztow i decyzji Human Gate. Tryb local-first, bez Hetznera, bez tworzenia VPS, "
                "bez produkcji i bez external submit. Wymagane wielosrodowiskowe wykonanie lokalne: "
                "dev/staging/qa-lab/security/review/release-lab. Rada modeli ma miec planner, "
                "architect, executor, verifier, governance, cost_sentinel, security_sentinel oraz "
                "twardego adversarial critic."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]

    runtime_constraints = project["canon_snapshot"]["runtime_constraints"]
    assert project["project_kind"] == "project_management_system"
    assert runtime_constraints["local_environment_count"] == 6
    assert runtime_constraints["vps_blocked_until_human_gate"] is True
    assert runtime_constraints["production_blocked_until_human_gate"] is True
    assert runtime_constraints["external_blocked_until_human_gate"] is True
    assert "dev, staging, qa-lab, security, review, release-lab" in project["canonical_book"]


def test_project_creation_applies_onboarding_meta_orchestration():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Meta orchestration audit project",
            "idea_raw": "Prosty kalkulator kosztow LLM dla zespolu z polskim raportem audytu",
            "constraints": "operator selected auto mode and seven council members in onboarding",
            "preferred_stack": ["Next.js", "FastAPI", "SQLite"],
            "owner_id": "workspace-default",
            "project_kind": "internal_tool",
            "project_domain": "software",
            "onboarding_config": {
                "configured_providers": ["openai", "anthropic", "perplexity", "zai", "google", "moonshot"],
                "installed_local_models": [
                    "bielik-11b-v2.3-instruct:Q4_K_M",
                    "pllum-12b-instruct:Q4_K_M",
                ],
                "autonomy_level": "auto",
                "council_size": 7,
                "llm_judge_routing": {
                    "low": "bielik-11b-v2.3-instruct:Q4_K_M",
                    "medium": "pllum-12b-instruct:Q4_K_M",
                    "high": "claude-sonnet-4-6",
                    "critical": "gpt-5+claude-sonnet-4-6",
                },
                "quality_speed_cost": {"quality": 0.6, "speed": 0.2, "cost": 0.2},
                "cost_ceilings": {"low": 0.1, "medium": 0.4, "high": 1.5, "critical": 5.0},
                "trusted_providers": ["perplexity"],
                "auto_trusted_providers": ["openai", "anthropic", "ollama"],
                "blocked_providers": ["deepseek"],
                "funding_advisor_enabled": True,
                "funding_model_profile": {
                    "research_provider": "perplexity",
                    "polish_specialists": ["bielik", "pllum"],
                    "require_polish_specialist": True,
                },
            },
        },
    )

    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]
    governance = project["governance_policy"]
    execution = project["execution_plan"]
    council_plan = project["council_plan"]

    assert project["project_kind"] == "internal_tool"
    assert project["canon_snapshot"]["project_domain"] == "software"
    assert project["custom_inputs"][0]["payload"]["first_idea_project_kind"] == "internal_tool"
    assert project["custom_inputs"][0]["payload"]["first_idea_project_domain"] == "software"
    assert project["autonomy_level"] == "auto"
    assert governance["autonomy_mode"] == "auto"
    assert governance["llm_judge_routing"]["low"] == "bielik-11b-v2.3-instruct:Q4_K_M"
    assert governance["provider_policy"]["blocked"] == ["deepseek"]
    assert governance["quality_speed_cost"] == {"quality": 0.6, "speed": 0.2, "cost": 0.2}
    assert execution["hard_limit_usd"] == 5.0
    assert execution["soft_warn_usd"] == 4.0
    assert project["cost_cap_usd"] == 5.0
    assert council_plan["operator_configured"] is True
    assert council_plan["active_size"] == 7
    assert len(council_plan["members"]) == 7
    assert len(project["council_members"]) == 7
    assert any(member["model_id"] == "bielik-11b-v2.3-instruct:Q4_K_M" for member in project["council_members"])
    assert any(member["model_id"] == "pllum-12b-instruct:Q4_K_M" for member in project["council_members"])
    assert not any(member["provider"] == "deepseek" for member in project["council_members"])
    assert project["custom_inputs"][0]["input_id"] == "advisor_onboarding_meta_orchestration"
    assert "api_keys" not in project["custom_inputs"][0]["payload"]

    autonomy = client.get(f"/api/v1/projects/{project_id}/autonomy")
    assert autonomy.status_code == 200
    assert autonomy.json()["raw_level"] == "auto"
    assert autonomy.json()["level"] == "L4"

    council = client.get(f"/api/v1/projects/{project_id}/council")
    assert council.status_code == 200
    assert council.json()["plan"]["active_size"] == 7
    assert len(council.json()["members"]) == 7


def test_project_creation_emits_advisor_lifecycle_cards_for_attachment_analysis():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Funding PII audit",
            "idea_raw": "Projekt fundingowy z dotacjami FENG/Horizon i dokumentami HR PII/GDPR",
            "constraints": "human-gate required",
            "preferred_stack": ["FastAPI", "SQLite"],
            "attachments": [
                {
                    "attachment_id": "att-pii-001",
                    "filename": "pii-redactor.md",
                    "file_type": "text/markdown",
                    "file_size": 512,
                    "analysis": [
                        {
                            "attachment_id": "att-pii-001",
                            "decision_class": "D4",
                            "human_gate_required": True,
                            "tags": ["gdpr", "pii_scope", "funding"],
                            "suggested_skills": ["pii_redactor", "gdpr_dsr", "funding_research"],
                            "missing_info": ["DPIA owner", "retention policy"],
                            "risks": ["personal-data processing"],
                        }
                    ],
                }
            ],
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]
    assert project["kickoff"]["cards_created"] >= 4

    cards = client.get(
        f"/api/v1/advisor/cards?operator_id=00000000-0000-0000-0000-000000000001&project_id={project_id}"
    )
    assert cards.status_code == 200
    topics = {
        card["header"].get("emitting_event_topic")
        for card in cards.json()["cards"]
    }
    assert "aeis.idea.intake.completed" in topics
    assert "aeis.council.formation_requested" in topics
    assert "aeis.system.skill_selection_requested" in topics
    assert "aeis.human_gate.ticket_pending" in topics

    lifecycle = client.get(f"/api/v1/advisor/projects/{project_id}/lifecycle")
    assert lifecycle.status_code == 200
    by_topic = {phase["hook_event_type"]: phase for phase in lifecycle.json()["phases"]}
    assert by_topic["aeis.idea.intake.completed"]["status"] == "in_progress"
    assert by_topic["aeis.council.formation_requested"]["status"] == "in_progress"
    assert by_topic["aeis.system.skill_selection_requested"]["status"] == "in_progress"
    assert by_topic["aeis.human_gate.ticket_pending"]["status"] == "in_progress"

    from sylion.aeis.advisor.engine import _db as advisor_engine_db

    conn = advisor_engine_db._get_sqlite_conn()
    conn.execute(
        "DELETE FROM advisor_engine_recommendations "
        "WHERE project_id = ? AND body_jsonb NOT LIKE ?",
        (project_id, "%aeis.idea.intake.completed%"),
    )
    conn.commit()
    retry = client.post(f"/api/v1/projects/{project_id}/kickoff")
    assert retry.status_code == 200
    retry_payload = retry.json()["kickoff"]
    assert retry_payload["skipped"] is False
    assert "aeis.idea.intake.completed" in retry_payload["skipped_existing_topics"]
    assert "aeis.system.skill_selection_requested" in retry_payload["emitted_topics"]
    assert "aeis.human_gate.ticket_pending" in retry_payload["emitted_topics"]


def test_project_questions_answer_and_freeze():
    created = _create_project()
    project_id = created["project"]["project_id"]

    pending = client.get(f"/api/v1/projects/{project_id}/questions?status=pending")
    assert pending.status_code == 200
    first_question = pending.json()["questions"][0]
    first_choice = first_question["choices"][0]

    answered = client.post(
        f"/api/v1/projects/{project_id}/questions/{first_question['question_id']}/answer",
        json={"choice_id": first_choice["choice_id"], "source": "human"},
    )
    assert answered.status_code == 200
    updated_project = answered.json()["project"]
    assert any(item["question_id"] == first_question["question_id"] and item["status"] == "answered" for item in updated_project["questions"])
    assert any(
        item["question_id"] == first_question["question_id"]
        and item["key"] == first_question["key"]
        for item in updated_project["decisions"]
    )
    assert updated_project["canon_snapshot"]["direction_locked"] is True

    canon = _approve_freeze(project_id, "canon")
    assert canon["approvals"]["book"] is True

    masterplan = _approve_freeze(project_id, "masterplan")
    assert masterplan["approvals"]["operating_model"] is True


def test_full_scope_and_hybrid_decisions_rebuild_ecommerce_planning():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Generator opisow marketplace",
            "idea_raw": (
                "Aplikacja analizuje zdjecia produktu i brief, generuje opisy PL EN DE, "
                "waliduje EAN, eksportuje CSV do Allegro i Amazon oraz wymaga HumanGate."
            ),
            "constraints": "test meta-orchestration effects",
            "preferred_stack": ["FastAPI", "HTML", "CSV"],
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]
    assert project["project_kind"] == "ecommerce_generator"

    pending = client.get(f"/api/v1/projects/{project_id}/questions?status=pending")
    assert pending.status_code == 200
    direction = next(item for item in pending.json()["questions"] if item["key"] == "direction_approval")
    runtime = next(item for item in pending.json()["questions"] if item["key"] == "runtime_policy")

    first = client.post(
        f"/api/v1/projects/{project_id}/questions/{direction['question_id']}/answer",
        json={"choice_id": "direction_full_scope", "source": "human-dashboard"},
    )
    assert first.status_code == 200
    project_after_direction = first.json()["project"]
    assert project_after_direction["project_kind"] == "ecommerce_generator"
    assert "marketplace_export" in project_after_direction["canonical_book"]
    assert "Allegro" in project_after_direction["canonical_book"]
    assert len(project_after_direction["worker_plan"]["modules"]) >= 6

    second = client.post(
        f"/api/v1/projects/{project_id}/questions/{runtime['question_id']}/answer",
        json={"choice_id": "runtime_hybrid_later", "source": "human-dashboard"},
    )
    assert second.status_code == 200
    project_after_runtime = second.json()["project"]
    assert project_after_runtime["status"] == "definition_complete"
    assert project_after_runtime["execution_plan"]["provisioning_mode"] == "hybrid-later"
    assert project_after_runtime["governance_policy"]["planned_runtime_expansion"] == "requires_future_approval"
    assert "hybrid-later" in project_after_runtime["masterplan"]
    assert "runtime_expansion_requires_human_gate: True" in project_after_runtime["masterplan"]
    assert any(module["name"] == "marketplace_export" for module in project_after_runtime["modules"])


def test_marketplace_saas_with_funding_scan_stays_marketplace_platform():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Meridian Commerce audit",
            "idea_raw": (
                "Platforma SaaS marketplace white-label dla wielu tenantow i vendorow. "
                "Wymagania: multi-tenant auth/RBAC, katalog produktow, koszyk, payment sandbox, "
                "tax, shipping, admin console, funding scan, HumanGate D5, canary deploy i rollback na Hetzner."
            ),
            "constraints": "funding scan jest funkcja wspierajaca, nie glownym typem projektu",
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]
    assert project["project_kind"] == "marketplace_platform"
    assert project["governance_policy"]["decision_class"] == "D5"
    assert "payment_provider_choice" in project["governance_policy"]["human_gate_required_for"]
    assert "funding_scan" in project["worker_plan"]["modules"]
    assert "funding_intake" not in project["worker_plan"]["modules"]

    pending = client.get(f"/api/v1/projects/{project_id}/questions?status=pending")
    assert pending.status_code == 200
    direction = next(item for item in pending.json()["questions"] if item["key"] == "direction_approval")
    runtime = next(item for item in pending.json()["questions"] if item["key"] == "runtime_policy")

    first = client.post(
        f"/api/v1/projects/{project_id}/questions/{direction['question_id']}/answer",
        json={"choice_id": "direction_full_scope", "source": "human-dashboard"},
    )
    assert first.status_code == 200
    project_after_direction = first.json()["project"]
    assert project_after_direction["project_kind"] == "marketplace_platform"
    assert "Typ projektu: marketplace_platform" in project_after_direction["canonical_book"]
    assert "funding-only" in project_after_direction["canonical_book"]
    assert "tenant_identity" in project_after_direction["worker_plan"]["modules"]
    assert "payment_sandbox" in project_after_direction["worker_plan"]["modules"]
    assert "funding_intake" not in project_after_direction["worker_plan"]["modules"]

    second = client.post(
        f"/api/v1/projects/{project_id}/questions/{runtime['question_id']}/answer",
        json={"choice_id": "runtime_hybrid_later", "source": "human-dashboard"},
    )
    assert second.status_code == 200
    project_after_runtime = second.json()["project"]
    assert project_after_runtime["project_kind"] == "marketplace_platform"
    assert project_after_runtime["execution_plan"]["provisioning_mode"] == "hybrid-later"
    assert any(module["name"] == "payment_sandbox" for module in project_after_runtime["modules"])
    assert any(module["name"] == "funding_scan" for module in project_after_runtime["modules"])


def test_multi_domain_saas_keeps_primary_kind_and_adds_supporting_overlays():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "AeroLab Nexus multi-domain regression",
            "idea_raw": (
                "Zbuduj zlozony system SaaS AEIS dla laboratorium automatyzacji: dashboard operatora, API, "
                "moduly klientow, projektow, faktur, raportow i harmonogramow. System ma miec Rade Modeli "
                "z rolami planner, architect, adversarial critic, security, cost sentinel, funding specialist "
                "i verifier. Dodaj Funding Autopilot jako modul wspierajacy, mobile approvals z device binding, "
                "runtime local-first, pozniejszy Hetzner VPS tylko przez Human Gate, Source of Truth i Masterplan."
            ),
            "constraints": "funding, mobile i runtime sa domenami wspierajacymi, nie glownym typem projektu",
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]
    assert project["project_kind"] == "project_management_system"
    profile = project["canon_snapshot"]["domain_profile"]
    assert profile["primary_kind"] == "project_management_system"
    assert profile["funding_is_supporting"] is True
    assert {"project_operations", "funding", "operator_mobile", "runtime", "governance"} <= set(profile["domains"])
    assert "funding_intake" not in project["worker_plan"]["modules"]
    assert {"funding_scan", "mobile_approval_bridge", "runtime_environment_matrix", "cross_domain_orchestration"} <= set(project["worker_plan"]["modules"])
    assert {"funding_submission", "mobile_approval_token", "runtime_expansion"} <= set(project["governance_policy"]["human_gate_required_for"])
    roles = {member["role"]: member for member in project["council_plan"]["members"]}
    assert roles["adversarial_critic"]["required_signature"] is True
    assert "challenge" in roles["adversarial_critic"]["responsibility"]
    assert "funding_specialist" in roles
    assert project["council_plan"]["quorum_policy"]["adversarial_critic_required"] is True
    assert "Profil wielodomenowy AEIS" in project["canonical_book"]
    assert "Funding scan nie przejmuje projektu" in project["masterplan"]

    pending = client.get(f"/api/v1/projects/{project_id}/questions?status=pending")
    assert pending.status_code == 200
    direction = next(item for item in pending.json()["questions"] if item["key"] == "direction_approval")
    runtime = next(item for item in pending.json()["questions"] if item["key"] == "runtime_policy")

    first = client.post(
        f"/api/v1/projects/{project_id}/questions/{direction['question_id']}/answer",
        json={"choice_id": "direction_full_scope", "source": "human-dashboard"},
    )
    assert first.status_code == 200
    project_after_direction = first.json()["project"]
    assert project_after_direction["project_kind"] == "project_management_system"
    assert "funding_intake" not in project_after_direction["worker_plan"]["modules"]
    assert "adversarial_critic" in {member["role"] for member in project_after_direction["council_plan"]["members"]}

    second = client.post(
        f"/api/v1/projects/{project_id}/questions/{runtime['question_id']}/answer",
        json={"choice_id": "runtime_hybrid_later", "source": "human-dashboard"},
    )
    assert second.status_code == 200
    project_after_runtime = second.json()["project"]
    assert project_after_runtime["project_kind"] == "project_management_system"
    assert project_after_runtime["execution_plan"]["provisioning_mode"] == "hybrid-later"
    assert any(module["name"] == "mobile_approval_bridge" for module in project_after_runtime["modules"])
    assert any(module["name"] == "runtime_environment_matrix" for module in project_after_runtime["modules"])


def test_bioinformatics_workflow_with_funding_scan_stays_bioinformatics_d5():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Aurora Genome Privacy audit",
            "idea_raw": (
                "D5 bioinformatics workflow dla plikow FASTQ i VCF, QC pipeline, pseudonimizacja probek, "
                "research-only variant scoring, no clinical use, PESEL/PII guard, local-only Bielik i PLLuM, "
                "funding scan Horizon Europe, EIC Pathfinder, FENG SMART i Digital Europe."
            ),
            "constraints": "funding scan jest funkcja wspierajaca, nie glownym typem projektu",
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]
    assert project["project_kind"] == "bioinformatics_workflow"
    assert project["governance_policy"]["decision_class"] == "D5"
    assert project["governance_policy"]["clinical_use_allowed"] is False
    assert "patient_data_import" in project["governance_policy"]["human_gate_required_for"]
    assert "funding_scan" in project["worker_plan"]["modules"]
    assert "funding_intake" not in project["worker_plan"]["modules"]
    assert any(member["role"] == "clinical_safety_reviewer" for member in project["council_plan"]["members"])
    assert any(member["role"] == "privacy_sentinel" for member in project["council_plan"]["members"])

    pending = client.get(f"/api/v1/projects/{project_id}/questions?status=pending")
    assert pending.status_code == 200
    direction = next(item for item in pending.json()["questions"] if item["key"] == "direction_approval")
    runtime = next(item for item in pending.json()["questions"] if item["key"] == "runtime_policy")

    first = client.post(
        f"/api/v1/projects/{project_id}/questions/{direction['question_id']}/answer",
        json={"choice_id": "direction_full_scope", "source": "human-dashboard"},
    )
    assert first.status_code == 200
    project_after_direction = first.json()["project"]
    assert project_after_direction["project_kind"] == "bioinformatics_workflow"
    assert "Typ projektu: bioinformatics_workflow" in project_after_direction["canonical_book"]
    assert "funding-only" in project_after_direction["canonical_book"]
    assert "clinical_safety_guard" in project_after_direction["worker_plan"]["modules"]
    assert "local_model_documentation" in project_after_direction["worker_plan"]["modules"]
    assert "funding_intake" not in project_after_direction["worker_plan"]["modules"]

    second = client.post(
        f"/api/v1/projects/{project_id}/questions/{runtime['question_id']}/answer",
        json={"choice_id": "runtime_local_only", "source": "human-dashboard"},
    )
    assert second.status_code == 200
    project_after_runtime = second.json()["project"]
    assert project_after_runtime["project_kind"] == "bioinformatics_workflow"
    assert project_after_runtime["execution_plan"]["deployment_mode"] == "local_docker"
    assert project_after_runtime["execution_plan"]["provisioning_mode"] == "local-first"
    assert any(module["name"] == "sample_pseudonymization" for module in project_after_runtime["modules"])
    assert any(module["name"] == "funding_scan" for module in project_after_runtime["modules"])

    suggested = client.post(f"/api/v1/projects/{project_id}/council/suggest")
    assert suggested.status_code == 200
    suggested_project = suggested.json()["project"]
    assert suggested_project["council_plan"]["enabled"] is True
    assert suggested_project["council_plan"]["active_size"] >= 8
    assert any(member["role"] == "clinical_safety_reviewer" for member in suggested_project["council_plan"]["members"])


def test_mental_health_safety_uses_d5_safety_roles_and_modules():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Vanguard Mind safety audit",
            "idea_raw": (
                "VANGUARD-MIND safety-first mental wellbeing assistant po polsku. "
                "Wykrywa kryzys, samobojcze mysli, autoagresje, blokuje diagnozy, "
                "plan terapii i porady medyczne, korzysta lokalnie z Bielik i PLLuM, "
                "a external LLM i public release wymagaja HumanGate D5."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]
    assert project["project_kind"] == "mental_health_safety"
    assert project["governance_policy"]["decision_class"] == "D5"
    assert project["governance_policy"]["medical_advice_allowed"] is False
    assert "medical_or_therapy_claim" in project["governance_policy"]["human_gate_required_for"]
    assert "crisis_classifier" in project["worker_plan"]["modules"]
    assert "no_medical_advice_guard" in project["worker_plan"]["modules"]
    assert "bioinformatics_guard" not in project["worker_plan"]["modules"]
    assert any(member["role"] == "safety_clinician_reviewer" for member in project["council_plan"]["members"])
    assert any(member["role"] == "privacy_sentinel" for member in project["council_plan"]["members"])

    pending = client.get(f"/api/v1/projects/{project_id}/questions?status=pending")
    assert pending.status_code == 200
    direction = next(item for item in pending.json()["questions"] if item["key"] == "direction_approval")
    runtime = next(item for item in pending.json()["questions"] if item["key"] == "runtime_policy")

    first = client.post(
        f"/api/v1/projects/{project_id}/questions/{direction['question_id']}/answer",
        json={"choice_id": "direction_full_scope", "source": "human-dashboard"},
    )
    assert first.status_code == 200
    project_after_direction = first.json()["project"]
    assert "Typ projektu: mental_health_safety" in project_after_direction["canonical_book"]
    assert "no_medical_advice_guard" in project_after_direction["worker_plan"]["modules"]

    second = client.post(
        f"/api/v1/projects/{project_id}/questions/{runtime['question_id']}/answer",
        json={"choice_id": "runtime_local_only", "source": "human-dashboard"},
    )
    assert second.status_code == 200
    project_after_runtime = second.json()["project"]
    assert project_after_runtime["execution_plan"]["deployment_mode"] == "local_docker"
    assert any(module["name"] == "source_backed_resources" for module in project_after_runtime["modules"])


def test_d5_round_meta_tickets_keep_project_decision_class_and_priority():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"Aurora D5 Gates {uuid4().hex[:6]}",
            "idea_raw": (
                "Bioinformatics workflow D5 FASTQ VCF PESEL guard, clinical_safety_guard, "
                "research-only no clinical use, funding scan Horizon Europe i local-only PLLuM Bielik."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]
    assert project["project_kind"] == "bioinformatics_workflow"
    assert project["governance_policy"]["decision_class"] == "D5"

    canon = client.post(f"/api/v1/projects/{project_id}/canon/freeze")
    assert canon.status_code == 200
    canon_ticket_id = canon.json()["ticket_id"]
    canon_ticket = client.get(f"/api/v1/governance/tickets/{canon_ticket_id}")
    assert canon_ticket.status_code == 200
    assert canon_ticket.json()["decision_class"] == "D5"
    assert canon_ticket.json()["priority"] == "P0"
    assert canon_ticket.json()["payload"]["decision_class"] == "D5"
    resolved = client.post(
        f"/api/v1/governance/tickets/{canon_ticket_id}/resolve",
        json={"decision": "approved", "reason": "test approves D5 canon", "reviewer": "operator@example.com"},
    )
    assert resolved.status_code == 200

    masterplan = client.post(f"/api/v1/projects/{project_id}/masterplan/freeze")
    assert masterplan.status_code == 200
    masterplan_ticket_id = masterplan.json()["ticket_id"]
    masterplan_ticket = client.get(f"/api/v1/governance/tickets/{masterplan_ticket_id}")
    assert masterplan_ticket.status_code == 200
    assert masterplan_ticket.json()["decision_class"] == "D5"
    assert masterplan_ticket.json()["priority"] == "P0"
    assert masterplan_ticket.json()["payload"]["decision_class"] == "D5"
    resolved = client.post(
        f"/api/v1/governance/tickets/{masterplan_ticket_id}/resolve",
        json={"decision": "approved", "reason": "test approves D5 masterplan", "reviewer": "operator@example.com"},
    )
    assert resolved.status_code == 200

    build = client.post(
        f"/api/v1/projects/{project_id}/build/authorize",
        json={"cost_cap_usd": 1.75, "autonomy_level": "L0", "external_actions_policy": {"mode": "local_only"}},
    )
    assert build.status_code == 200
    build_ticket = client.get(f"/api/v1/governance/tickets/{build.json()['ticket_id']}")
    assert build_ticket.status_code == 200
    assert build_ticket.json()["decision_class"] == "D5"
    assert build_ticket.json()["priority"] == "P0"
    assert build_ticket.json()["payload"]["decision_class"] == "D5"


def test_project_and_human_gate_events_mirror_to_unified_audit_trail():
    created = _create_project()
    project_id = created["project"]["project_id"]

    canon = _approve_freeze(project_id, "canon")
    assert canon["approvals"]["book"] is True

    events_response = client.get("/api/v1/audit/events?limit=200")
    assert events_response.status_code == 200
    audit_events = events_response.json()["events"]
    actions = {event["action"] for event in audit_events}
    assert "project.created" in actions
    assert "project.canon.freeze.requested" in actions
    assert "project.canon.frozen" in actions
    assert "governance.ticket.submitted" in actions
    assert "governance.ticket.resolved" in actions

    project_event = next(
        event for event in audit_events
        if event["action"] == "project.canon.frozen"
    )
    assert project_event["source"] == "workspace"
    assert project_event["resource"] == f"project:{project_id}"
    assert project_event["metadata"]["audit_chain_entry"]

    summary = client.get("/api/v1/audit/summary")
    assert summary.status_code == 200
    assert summary.json()["total_entries"] >= 5


def test_project_audit_cost_and_brain():
    created = _create_project()
    project_id = created["project"]["project_id"]

    audit = client.post(f"/api/v1/projects/{project_id}/audit/run", json={"scope": "masterplan", "parallel": True})
    assert audit.status_code == 200
    assert len(audit.json()["results"]) >= 5

    cost = client.get(f"/api/v1/projects/{project_id}/cost")
    assert cost.status_code == 200
    assert "running_total" in cost.json()

    brain_stats = client.get("/api/v1/brain/memory/stats")
    assert brain_stats.status_code == 200
    assert brain_stats.json()["entries"] >= 1

    search = client.post("/api/v1/brain/search", json={"query": "komunikator", "top_k": 5})
    assert search.status_code == 200
    assert isinstance(search.json()["items"], list)


def test_project_council_suggests_ranked_weighted_members_and_reconciles():
    created = _create_project()
    project_id = created["project"]["project_id"]

    suggested = client.post(f"/api/v1/projects/{project_id}/council/suggest")
    assert suggested.status_code == 200
    plan = suggested.json()["plan"]
    assert plan["active_size"] == len(plan["members"])
    assert plan["quorum_policy"]["type"] == "weighted_majority_with_adversarial_critic_signature"
    assert plan["quorum_policy"]["adversarial_critic_required"] is True
    assert plan["suggestion_stage"] == "provisional"
    assert plan["requires_model_probe"] is True
    assert "no_project_model_probe" in plan["confidence_basis"]
    assert suggested.json()["requires_model_probe"] is True
    assert {member["role"] for member in plan["members"]} >= {"planner", "architect", "critic", "adversarial_critic", "verifier", "governance"}
    assert all(member["rank"] for member in plan["members"])
    assert all(member["voting_weight"] > 0 for member in plan["members"])
    assert any(member["role"] == "critic" and member["required_signature"] for member in plan["members"])
    assert any(member["role"] == "adversarial_critic" and member["required_signature"] for member in plan["members"])

    reconciled = client.post(f"/api/v1/council/{project_id}/reconcile")
    assert reconciled.status_code == 200
    state = reconciled.json()
    assert state["enabled"] is True
    assert state["active_size"] == plan["active_size"]
    assert len(state["members"]) == plan["active_size"]
    assert all(member["voting_weight"] > 0 for member in state["members"])
    assert any(member["member_role"] == "critic" and member["config"]["required_signature"] for member in state["members"])
    assert any(member["member_role"] == "adversarial_critic" and member["config"]["required_signature"] for member in state["members"])
    assert "planner_council" in state["decision_hierarchy"]


def _patch_real_council_call(monkeypatch):
    import sylion.api.council_routes as council_routes

    def fake_analysis(**kwargs):
        member = kwargs["member"]
        role = council_routes._canonical_role(member.member_role)
        model_id = member.model_id or member.member_id or role
        return {
            "model_id": model_id,
            "role": role,
            "verdict": "approve",
            "confidence": 0.91,
            "analysis_text": f"source=real_llm provider=test model={model_id} reasoning=test-approved",
            "rationale": "test-approved",
            "source": "real_llm",
            "llm": {
                "ok": True,
                "provider": "test",
                "model": model_id,
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "estimated_cost_usd": 0.0,
            },
            "sentinel_blocks": [],
        }

    monkeypatch.setattr(council_routes, "_run_member_llm_analysis", fake_analysis)


def test_project_council_deliberates_low_risk_change_without_human_gate(monkeypatch):
    _patch_real_council_call(monkeypatch)
    created = _create_project()
    project_id = created["project"]["project_id"]

    suggested = client.post(f"/api/v1/projects/{project_id}/council/suggest")
    assert suggested.status_code == 200
    reconciled = client.post(f"/api/v1/council/{project_id}/reconcile")
    assert reconciled.status_code == 200

    deliberation = client.post(
        f"/api/v1/council/{project_id}/deliberate",
        json={
            "title": "Local copy tweak",
            "description": "Adjust local draft copy without changing canon, architecture, cost or runtime.",
            "change_type": "local_refactor",
            "risk_level": "low",
        },
    )

    assert deliberation.status_code == 200
    payload = deliberation.json()
    assert payload["status"] == "auto_approved"
    assert payload["human_gate_ticket_id"] == ""
    assert payload["decision_class"] == "D1"
    assert payload["gate_type"] == "non_blocking"
    assert payload["consensus"]["verdict"] == "approve"
    assert payload["consensus"]["critic_signed"] is True

    tickets = client.get(f"/api/v1/governance/tickets/pending?origin=council&project_id={project_id}")
    assert tickets.status_code == 200
    assert tickets.json()["count"] == 0


def test_project_council_uses_orchestration_council_quorum(monkeypatch):
    from sylion.aeis.advisor.orchestration_config import service as svc_mod

    _patch_real_council_call(monkeypatch)
    svc_mod._STORE.clear()
    svc_mod._SERVICE = None
    try:
        orchestration = svc_mod.get_orchestration_service()
        rules = orchestration.get_council_rules()
        payload = rules.__dict__
        payload["rank_weights"] = [item.__dict__ for item in rules.rank_weights]
        payload["sentinel_requirements"] = [item.__dict__ for item in rules.sentinel_requirements]
        payload["quorum_min"] = 99
        orchestration.update_council_rules(payload)

        created = _create_project()
        project_id = created["project"]["project_id"]
        assert client.post(f"/api/v1/projects/{project_id}/council/suggest").status_code == 200
        assert client.post(f"/api/v1/council/{project_id}/reconcile").status_code == 200

        deliberation = client.post(
            f"/api/v1/council/{project_id}/deliberate",
            json={
                "title": "Local copy tweak with strict runtime quorum",
                "description": "Low-risk change should still respect orchestration quorum.",
                "change_type": "local_refactor",
                "risk_level": "low",
            },
        )
        assert deliberation.status_code == 200
        payload = deliberation.json()
        assert payload["quorum_policy"]["source"] == "orchestration_config"
        assert payload["quorum_policy"]["quorum_min"] == 99
        assert payload["quorum_met"] is False
        assert payload["status"] == "requires_human_gate"
        assert payload["human_gate_ticket_id"]
    finally:
        svc_mod._STORE.clear()
        svc_mod._SERVICE = None


def test_project_council_escalates_production_change_to_human_gate(monkeypatch):
    _patch_real_council_call(monkeypatch)
    created = _create_project()
    project_id = created["project"]["project_id"]

    assert client.post(f"/api/v1/projects/{project_id}/council/suggest").status_code == 200
    assert client.post(f"/api/v1/council/{project_id}/reconcile").status_code == 200

    deliberation = client.post(
        f"/api/v1/council/{project_id}/deliberate",
        json={
            "title": "Deploy production without extra review",
            "description": "Move the generated project to production immediately.",
            "change_type": "production_deploy",
            "risk_level": "high",
            "production_deploy": True,
        },
    )

    assert deliberation.status_code == 200
    payload = deliberation.json()
    assert payload["status"] == "requires_human_gate"
    assert payload["decision_class"] == "D5"
    assert payload["gate_type"] == "production"
    assert payload["human_gate_ticket_id"]
    assert "production_deploy" in payload["risk_flags"]
    assert payload["consensus"]["critic_signed"] is True

    ticket = client.get(f"/api/v1/governance/tickets/{payload['human_gate_ticket_id']}")
    assert ticket.status_code == 200
    ticket_payload = ticket.json()
    assert ticket_payload["origin"] == "council"
    assert ticket_payload["project_id"] == project_id
    assert ticket_payload["decision_class"] == "D5"
    assert ticket_payload["gate_type"] == "production"
    assert ticket_payload["payload"]["council_session_id"] == payload["session"]["session_id"]

    events = client.get(f"/api/v1/projects/{project_id}/events").json()["events"]
    assert any(event["event_type"] == "project.council.deliberation.requires_human_gate" for event in events)


def test_project_auto_binds_default_skills_to_modules_and_registry():
    created = _create_project()
    project_id = created["project"]["project_id"]

    skills = client.get(f"/api/v1/projects/{project_id}/skills")
    assert skills.status_code == 200
    payload = skills.json()
    assert "aeis.intent-classifier" in payload["skill_ids"]
    assert "aeis.auth-flow-builder" in payload["skill_ids"]
    assert "aeis.realtime-messaging-builder" in payload["skill_ids"]
    assert all(module["bindings"] for module in payload["modules"])
    assert all(any(binding["source"] == "default" for binding in module["bindings"]) for module in payload["modules"])

    registry = client.get("/api/v1/skills/skills")
    assert registry.status_code == 200
    registered = {skill["skill_id"]: skill for skill in registry.json()["skills"]}
    assert registered["aeis.intent-classifier"]["lifecycle"] == "PUBLISHED"
    assert registered["aeis.human-gate-policy"]["lifecycle"] == "PUBLISHED"
    assert payload["reuse_log"], "W18 skill matching must show cold-start manifest bindings, not only memory reuse"
    assert any(item["reused_skill_id"] == "aeis.auth-flow-builder" for item in payload["reuse_log"])
    assert any("matched project_kind" in item["adaptation_notes"] for item in payload["reuse_log"])


def test_similar_project_reuses_skill_bindings_from_memory():
    first = _create_project()["project"]

    second_response = client.post(
        "/api/v1/projects",
        json={
            "name": f"Chat Followup {uuid4().hex[:6]}",
            "idea_raw": "zbuduj drugi podobny komunikator z logowaniem, pokojami i wiadomościami",
            "constraints": "reuse patterns from previous local chat project",
            "owner_id": "workspace-default",
        },
    )
    assert second_response.status_code == 200
    second = second_response.json()["project"]

    skills = client.get(f"/api/v1/projects/{second['project_id']}/skills")
    assert skills.status_code == 200
    payload = skills.json()
    similar = payload["memory_policy"]["similar_projects"]
    assert any(item["project_id"] == first["project_id"] for item in similar)
    assert payload["memory_policy"]["reused_skill_ids"]
    assert payload["reuse_log"]
    assert any(item["reused_skill_id"] == "aeis.auth-flow-builder" for item in payload["reuse_log"])


def test_project_launch_executes_real_build_and_writes_artifacts():
    created = _create_project()
    project_id = created["project"]["project_id"]

    for question in client.get(f"/api/v1/projects/{project_id}/questions?status=pending").json()["questions"]:
        choice_id = question["choices"][0]["choice_id"]
        answered = client.post(
            f"/api/v1/projects/{project_id}/questions/{question['question_id']}/answer",
            json={"choice_id": choice_id, "source": "human"},
        )
        assert answered.status_code == 200

    _approve_freeze(project_id, "canon")
    _approve_freeze(project_id, "masterplan")

    launch = client.post(
        f"/api/v1/projects/{project_id}/launch",
        json={"auto_execute": True, "wait_for_completion": True},
    )
    assert launch.status_code == 200
    payload = launch.json()
    execution = payload["execution"]
    artifact_path = Path(execution["artifact_path"])
    assert artifact_path.is_file()
    assert execution["validation"]["success"] is True
    assert len(execution["module_outputs"]) >= 1
    for item in execution["module_outputs"]:
        assert Path(item["artifact_path"]).is_file()

    detail = client.get(f"/api/v1/projects/{project_id}").json()
    assert detail["status"] == "completed"
    assert detail["launch"]["artifact_path"] == str(artifact_path)
    assert Path(detail["launch"]["deployment"]["docker_compose"]).is_file()

    brain_stats = client.get("/api/v1/brain/memory/stats").json()
    assert brain_stats["entries"] >= 3


def test_internal_tool_launch_generates_real_llm_cost_calculator():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"LLM Cost Project {uuid4().hex[:6]}",
            "idea_raw": (
                "Prosty kalkulator kosztow LLM dla zespolu. Ma liczyc input tokeny, output tokeny, "
                "provider, model, uruchomienia dziennie, budzet miesieczny, progi 80/100, CSV export "
                "i lokalny audit bez PII. W gotowym produkcie nie wolno uzywac mockow, stubow ani fallbackow."
            ),
            "constraints": "brak produkcyjnego deployu bez HumanGate",
            "preferred_stack": ["HTML", "JavaScript"],
            "owner_id": "workspace-default",
            "project_kind": "internal_tool",
            "project_domain": "software",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]

    for question in client.get(f"/api/v1/projects/{project_id}/questions?status=pending").json()["questions"]:
        choice_id = question["choices"][0]["choice_id"]
        answered = client.post(
            f"/api/v1/projects/{project_id}/questions/{question['question_id']}/answer",
            json={"choice_id": choice_id, "source": "human"},
        )
        assert answered.status_code == 200

    _approve_freeze(project_id, "canon")
    _approve_freeze(project_id, "masterplan")

    launch = client.post(
        f"/api/v1/projects/{project_id}/launch",
        json={"auto_execute": True, "wait_for_completion": True},
    )
    assert launch.status_code == 200
    execution = launch.json()["execution"]
    artifact_path = Path(execution["artifact_path"])
    artifact_text = artifact_path.read_text(encoding="utf-8").lower()

    assert execution["artifact_format"] == "html"
    assert execution["validation"]["success"] is True
    assert execution["validation"]["stages"]["integration_tests"]["success"] is True
    assert "calculatellmcost" in artifact_text
    assert 'data-testid="input-tokens-input"' in artifact_text
    assert 'data-testid="output-tokens-input"' in artifact_text
    assert 'data-testid="csv-download"' in artifact_text
    assert "warn_80" in artifact_text
    assert "over_100" in artifact_text
    assert "document.getelementbyid('inputtokens').value = '10000';" in artifact_text
    assert "document.getelementbyid('monthlybudget').value = '1.50';" in artifact_text
    assert "no_pii" in artifact_text
    assert "aeis application product" not in artifact_text
    assert "nowe zadanie operatora" not in artifact_text
    assert "def add(" not in artifact_text
    assert "stub" not in artifact_text
    assert "mock" not in artifact_text
    assert "fallback" not in artifact_text
    assert all(result["status"] == "pass" for result in execution["audit"]["results"])


def test_ecommerce_launch_generates_domain_artifact_and_passes_audit():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"Ecommerce Project {uuid4().hex[:6]}",
            "idea_raw": (
                "Generator opisow e-commerce z obrazow i briefu produktu. Ma generowac opisy PL EN DE, "
                "walidowac EAN, blokowac eksport CSV przez HumanGate i przygotowac eksport Allegro oraz Amazon."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]
    assert project["project_kind"] == "ecommerce_generator"

    for question in client.get(f"/api/v1/projects/{project_id}/questions?status=pending").json()["questions"]:
        if question["key"] == "direction_approval":
            choice_id = "direction_full_scope"
        elif question["key"] == "runtime_policy":
            choice_id = "runtime_hybrid_later"
        else:
            choice_id = question["choices"][0]["choice_id"]
        answered = client.post(
            f"/api/v1/projects/{project_id}/questions/{question['question_id']}/answer",
            json={"choice_id": choice_id, "source": "human"},
        )
        assert answered.status_code == 200

    _approve_freeze(project_id, "canon")
    _approve_freeze(project_id, "masterplan")

    launch = client.post(
        f"/api/v1/projects/{project_id}/launch",
        json={"auto_execute": True, "wait_for_completion": True},
    )
    assert launch.status_code == 200
    execution = launch.json()["execution"]
    artifact_path = Path(execution["artifact_path"])
    artifact_text = artifact_path.read_text(encoding="utf-8").lower()

    assert execution["artifact_format"] == "html"
    assert execution["validation"]["success"] is True
    assert execution["validation"]["stages"]["integration_tests"]["success"] is True
    assert "generateproductdescriptions" in artifact_text
    assert "validateean" in artifact_text
    assert "humangate" in artifact_text
    assert "allegro" in artifact_text
    assert "amazon" in artifact_text
    assert "buildcsv" in artifact_text
    assert "evidence_pack" in artifact_text
    assert "aeis application product" not in artifact_text
    assert "nowe zadanie operatora" not in artifact_text
    assert "def add(" not in artifact_text
    assert "stub" not in artifact_text
    assert "mock" not in artifact_text
    assert all(result["status"] == "pass" for result in execution["audit"]["results"])


def test_marketplace_platform_launch_generates_d5_artifact_and_passes_audit():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"Marketplace Platform {uuid4().hex[:6]}",
            "idea_raw": (
                "Marketplace SaaS white-label dla wielu tenantow i vendorow z katalogiem, koszykiem, "
                "payment sandbox, tax, shipping, admin console, funding scan, release governance, "
                "canary, rollback i HumanGate D5 dla Hetzner deploy."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]
    assert project["project_kind"] == "marketplace_platform"
    assert project["governance_policy"]["decision_class"] == "D5"

    for question in client.get(f"/api/v1/projects/{project_id}/questions?status=pending").json()["questions"]:
        if question["key"] == "direction_approval":
            choice_id = "direction_full_scope"
        elif question["key"] == "runtime_policy":
            choice_id = "runtime_hybrid_later"
        else:
            choice_id = question["choices"][0]["choice_id"]
        answered = client.post(
            f"/api/v1/projects/{project_id}/questions/{question['question_id']}/answer",
            json={"choice_id": choice_id, "source": "human"},
        )
        assert answered.status_code == 200

    _approve_freeze(project_id, "canon")
    _approve_freeze(project_id, "masterplan")

    launch = client.post(
        f"/api/v1/projects/{project_id}/launch",
        json={"auto_execute": True, "wait_for_completion": True},
    )
    assert launch.status_code == 200
    execution = launch.json()["execution"]
    artifact_path = Path(execution["artifact_path"])
    artifact_text = artifact_path.read_text(encoding="utf-8").lower()

    assert execution["artifact_format"] == "html"
    assert execution["validation"]["success"] is True
    assert execution["validation"]["stages"]["integration_tests"]["success"] is True
    assert "tenant_identity" in artifact_text
    assert "vendor_onboarding" in artifact_text
    assert "product_catalog" in artifact_text
    assert "cart_checkout" in artifact_text
    assert "payment_sandbox" in artifact_text
    assert "tax_shipping" in artifact_text
    assert "admin_console" in artifact_text
    assert "funding_scan" in artifact_text
    assert "release_governance" in artifact_text
    assert "promotecanary" in artifact_text
    assert "state.release=false; state.canary=0" in artifact_text
    assert "wymaga ponownego humangate" in artifact_text
    assert "state.rolledback=false; state.canary" in artifact_text
    assert "rollback" in artifact_text
    assert "humangate" in artifact_text
    assert "evidence_pack" in artifact_text
    assert "funding-only" in artifact_text
    assert "aeis application product" not in artifact_text
    assert "nowe zadanie operatora" not in artifact_text
    assert "def add(" not in artifact_text
    assert "mock" not in artifact_text
    assert "stub" not in artifact_text
    assert all(result["status"] == "pass" for result in execution["audit"]["results"])


def test_bioinformatics_workflow_launch_generates_d5_artifact_and_passes_audit():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"Aurora Genome {uuid4().hex[:6]}",
            "idea_raw": (
                "Workflow bioinformatyczny D5 do lokalnej analizy FASTQ/VCF, QC pipeline, "
                "pseudonimizacja probek, PESEL guard, research-only variant scoring, no clinical use, "
                "Bielik i PLLuM lokalnie, funding scan Horizon Europe EIC FENG SMART Digital Europe."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]

    assert project["project_kind"] == "bioinformatics_workflow"
    assert project["governance_policy"]["decision_class"] == "D5"

    for question in client.get(f"/api/v1/projects/{project_id}/questions?status=pending").json()["questions"]:
        if question["key"] == "direction_approval":
            choice_id = "direction_full_scope"
        elif question["key"] == "runtime_policy":
            choice_id = "runtime_local_only"
        else:
            choice_id = question["choices"][0]["choice_id"]
        answered = client.post(
            f"/api/v1/projects/{project_id}/questions/{question['question_id']}/answer",
            json={"choice_id": choice_id, "source": "human"},
        )
        assert answered.status_code == 200

    _approve_freeze(project_id, "canon")
    _approve_freeze(project_id, "masterplan")

    launch = client.post(
        f"/api/v1/projects/{project_id}/launch",
        json={"auto_execute": True, "wait_for_completion": True},
    )
    assert launch.status_code == 200
    execution = launch.json()["execution"]
    artifact_path = Path(execution["artifact_path"])
    artifact_text = artifact_path.read_text(encoding="utf-8").lower()

    assert execution["artifact_format"] == "html"
    assert execution["validation"]["success"] is True
    assert execution["validation"]["stages"]["integration_tests"]["success"] is True
    assert "synthetic_data_intake" in artifact_text
    assert "format_validation" in artifact_text
    assert "qc_pipeline" in artifact_text
    assert "sample_pseudonymization" in artifact_text
    assert "variant_research_scoring" in artifact_text
    assert "clinical_safety_guard" in artifact_text
    assert "funding_scan" in artifact_text
    assert "local_model_documentation" in artifact_text
    assert "research-only" in artifact_text
    assert "no clinical use" in artifact_text
    assert "pesel" in artifact_text
    assert "humangate" in artifact_text
    assert "report_export" in artifact_text
    assert "funding-only" in artifact_text
    assert "aeis application product" not in artifact_text
    assert "nowe zadanie operatora" not in artifact_text
    assert "def add(" not in artifact_text
    assert "mock" not in artifact_text
    assert "stub" not in artifact_text
    assert all(result["status"] == "pass" for result in execution["audit"]["results"])


def test_mental_health_safety_launch_generates_d5_artifact_and_passes_audit():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"Vanguard Mind {uuid4().hex[:6]}",
            "idea_raw": (
                "Safety-first mental wellbeing assistant D5 po polsku: wellbeing intake, "
                "crisis classifier, no medical advice guard, emergency handoff, PII minimization, "
                "Bielik i PLLuM local-only, source-backed resources i release safety gate."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]

    assert project["project_kind"] == "mental_health_safety"
    assert project["governance_policy"]["decision_class"] == "D5"

    for question in client.get(f"/api/v1/projects/{project_id}/questions?status=pending").json()["questions"]:
        if question["key"] == "direction_approval":
            choice_id = "direction_full_scope"
        elif question["key"] == "runtime_policy":
            choice_id = "runtime_local_only"
        else:
            choice_id = question["choices"][0]["choice_id"]
        answered = client.post(
            f"/api/v1/projects/{project_id}/questions/{question['question_id']}/answer",
            json={"choice_id": choice_id, "source": "human"},
        )
        assert answered.status_code == 200

    _approve_freeze(project_id, "canon")
    _approve_freeze(project_id, "masterplan")

    launch = client.post(
        f"/api/v1/projects/{project_id}/launch",
        json={"auto_execute": True, "wait_for_completion": True},
    )
    assert launch.status_code == 200
    execution = launch.json()["execution"]
    artifact_text = Path(execution["artifact_path"]).read_text(encoding="utf-8").lower()

    assert execution["artifact_format"] == "html"
    assert execution["validation"]["success"] is True
    assert "wellbeing_intake" in artifact_text
    assert "crisis_classifier" in artifact_text
    assert "no_medical_advice_guard" in artifact_text
    assert "safe_response_generator" in artifact_text
    assert "emergency_handoff" in artifact_text
    assert "pii_minimization" in artifact_text
    assert "source_backed_resources" in artifact_text
    assert "release_safety_gate" in artifact_text
    assert "humangate" in artifact_text
    assert "bioinformatics_workflow" not in artifact_text
    assert "mock" not in artifact_text
    assert "stub" not in artifact_text
    assert all(result["status"] == "pass" for result in execution["audit"]["results"])


def test_employee_portal_launch_generates_hr_artifact_and_passes_audit():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"HR Portal Project {uuid4().hex[:6]}",
            "idea_raw": (
                "Portal pracowniczy HR z logowaniem SSO LDAP, dokumentami kadrowymi, "
                "wnioskami urlopowymi, GDPR DSR, DPIA, DPO, PII high, session timeout, "
                "rate limit i password policy."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]

    assert project["project_kind"] == "employee_portal"
    assert project["worker_plan"]["modules"] == [
        "auth_users",
        "role_assignment",
        "document_workflow",
        "leave_request_workflow",
        "gdpr_dsr",
        "security_session_policy",
        "audit_evidence_pack",
        "integration_validation",
    ]
    assert project["governance_policy"]["decision_class"] == "D4"

    skills = client.get(f"/api/v1/projects/{project_id}/skills")
    assert skills.status_code == 200
    skill_ids = set(skills.json()["skill_ids"])
    assert {
        "aeis.hr-document-workflow",
        "aeis.gdpr-dsr-governance",
        "aeis.security-session-policy",
    } <= skill_ids

    for question in client.get(f"/api/v1/projects/{project_id}/questions?status=pending").json()["questions"]:
        if question["key"] == "direction_approval":
            choice_id = "direction_full_scope"
        elif question["key"] == "runtime_policy":
            choice_id = "runtime_local_only"
        else:
            choice_id = question["choices"][0]["choice_id"]
        answered = client.post(
            f"/api/v1/projects/{project_id}/questions/{question['question_id']}/answer",
            json={"choice_id": choice_id, "source": "human"},
        )
        assert answered.status_code == 200

    planned = client.get(f"/api/v1/projects/{project_id}").json()
    assert planned["execution_plan"]["vps_workers"] == 0
    assert all(module["host_target"] == "local" for module in planned["modules"])
    assert {worker["worker_type"] for worker in planned["worker_pool"]} == {"docker"}

    _approve_freeze(project_id, "canon")
    _approve_freeze(project_id, "masterplan")

    launch = client.post(
        f"/api/v1/projects/{project_id}/launch",
        json={"auto_execute": True, "wait_for_completion": True},
    )
    assert launch.status_code == 200
    execution = launch.json()["execution"]
    artifact_path = Path(execution["artifact_path"])
    artifact_text = artifact_path.read_text(encoding="utf-8").lower()

    assert execution["artifact_format"] == "html"
    assert execution["validation"]["success"] is True
    assert execution["validation"]["stages"]["integration_tests"]["success"] is True
    assert "auth_users" in artifact_text
    assert "role_assignment" in artifact_text
    assert "document_workflow" in artifact_text
    assert "leave_request_workflow" in artifact_text
    assert "gdpr_dsr" in artifact_text
    assert "security_session_policy" in artifact_text
    assert "audit_evidence_pack" in artifact_text
    assert "dpia_required" in artifact_text
    assert "session_timeout_30_min" in artifact_text
    assert "rate_limit_5_15min" in artifact_text
    assert "password_policy_14_mfa_lockout" in artifact_text
    assert "humangate" in artifact_text
    assert "dpo" in artifact_text
    assert "aeis application product" not in artifact_text
    assert "nowe zadanie operatora" not in artifact_text
    assert "def add(" not in artifact_text
    assert "stub" not in artifact_text
    assert "mock" not in artifact_text
    assert all(result["status"] == "pass" for result in execution["audit"]["results"])


def test_operator_mobile_launch_generates_offline_firmware_artifact_and_passes_audit():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"Mobile Service Project {uuid4().hex[:6]}",
            "idea_raw": (
                "Mobilny asystent serwisowy dla technikow. Ma dzialac offline, prowadzic checklisty, "
                "przyjmowac firmware .ino .bin .hex, redagowac zdjecia dowodowe z mozliwym PII, "
                "kolejkowac sync queue, wymagac device binding i HumanGate przed firmware oraz sync."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]

    assert project["project_kind"] == "operator_mobile"
    assert project["worker_plan"]["modules"] == [
        "mobile_shell",
        "offline_checklists",
        "firmware_attachment_guard",
        "photo_evidence_redaction",
        "sync_queue",
        "device_binding",
        "secure_approval",
        "audit_evidence_pack",
        "integration_validation",
    ]
    assert project["governance_policy"]["decision_class"] == "D4"

    skills = client.get(f"/api/v1/projects/{project_id}/skills")
    assert skills.status_code == 200
    skill_ids = set(skills.json()["skill_ids"])
    assert {
        "aeis.offline-checklist-builder",
        "aeis.firmware-attachment-guard",
        "aeis.photo-evidence-redactor",
        "aeis.sync-queue-governance",
        "aeis.mobile-approval-security",
    } <= skill_ids

    for question in client.get(f"/api/v1/projects/{project_id}/questions?status=pending").json()["questions"]:
        if question["key"] == "direction_approval":
            choice_id = "direction_full_scope"
        elif question["key"] == "runtime_policy":
            choice_id = "runtime_local_only"
        else:
            choice_id = question["choices"][0]["choice_id"]
        answered = client.post(
            f"/api/v1/projects/{project_id}/questions/{question['question_id']}/answer",
            json={"choice_id": choice_id, "source": "human"},
        )
        assert answered.status_code == 200

    _approve_freeze(project_id, "canon")
    _approve_freeze(project_id, "masterplan")

    launch = client.post(
        f"/api/v1/projects/{project_id}/launch",
        json={"auto_execute": True, "wait_for_completion": True},
    )
    assert launch.status_code == 200
    execution = launch.json()["execution"]
    artifact_path = Path(execution["artifact_path"])
    artifact_text = artifact_path.read_text(encoding="utf-8").lower()

    assert execution["artifact_format"] == "html"
    assert execution["validation"]["success"] is True
    assert execution["validation"]["stages"]["integration_tests"]["success"] is True
    assert "mobile_shell" in artifact_text
    assert "offline_checklists" in artifact_text
    assert "firmware_attachment_guard" in artifact_text
    assert "validatefirmwareattachment" in artifact_text
    assert "photo_evidence_redaction" in artifact_text
    assert "redactphotoevidence" in artifact_text
    assert "sync_queue" in artifact_text
    assert "syncqueue" in artifact_text
    assert "device_binding" in artifact_text
    assert "binddevice" in artifact_text
    assert "secure_approval" in artifact_text
    assert "approvefirmwaregate" in artifact_text
    assert "audit_evidence_pack" in artifact_text
    assert "humangate" in artifact_text
    assert "\n    addchecklistitem();\n" not in artifact_text
    assert "missing firmware attachment" in artifact_text
    assert "missing photo evidence" in artifact_text
    assert "firmwarename_manual" not in artifact_text
    assert "firmwarename" in artifact_text
    assert "firmwarecontentmanual" in artifact_text
    assert "photonamemanual" in artifact_text
    assert "photocontentmanual" in artifact_text
    assert "firmware-serwisowy.ino" not in artifact_text
    assert "tabliczka-z-lokalizacja.jpg" not in artifact_text
    assert "aeis application product" not in artifact_text
    assert "nowe zadanie operatora" not in artifact_text
    assert "def add(" not in artifact_text
    assert "stub" not in artifact_text
    assert "mock" not in artifact_text
    assert all(result["status"] == "pass" for result in execution["audit"]["results"])


def test_project_management_launch_generates_release_governance_artifact_and_passes_audit():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"Project Management Project {uuid4().hex[:6]}",
            "idea_raw": (
                "Rozbudowany system projektowy z portfolio projektow, Kanban, Gantt, backlogiem, sprintami, "
                "resource capacity, risk register, budzetem projektu, RBAC audit, integracjami API, release gate, "
                "canary i deployem na Hetzner VPS."
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]

    assert project["project_kind"] == "project_management_system"

    for question in client.get(f"/api/v1/projects/{project_id}/questions?status=pending").json()["questions"]:
        choice_id = "direction_full_scope" if question["key"] == "direction_approval" else question["choices"][0]["choice_id"]
        answered = client.post(
            f"/api/v1/projects/{project_id}/questions/{question['question_id']}/answer",
            json={"choice_id": choice_id, "source": "human"},
        )
        assert answered.status_code == 200

    _approve_freeze(project_id, "canon")
    _approve_freeze(project_id, "masterplan")

    launch = client.post(
        f"/api/v1/projects/{project_id}/launch",
        json={"auto_execute": True, "wait_for_completion": True},
    )
    assert launch.status_code == 200
    execution = launch.json()["execution"]
    artifact_path = Path(execution["artifact_path"])
    artifact_text = artifact_path.read_text(encoding="utf-8").lower()

    assert execution["artifact_format"] == "html"
    assert execution["validation"]["success"] is True
    assert execution["validation"]["stages"]["integration_tests"]["success"] is True
    assert "tenant_workspace" in artifact_text
    assert "kanban_backlog" in artifact_text
    assert "gantt_roadmap" in artifact_text
    assert "risk_register" in artifact_text
    assert "budget_tracking" in artifact_text
    assert "rbac_audit" in artifact_text
    assert "release_governance" in artifact_text
    assert "promotecanary" in artifact_text
    assert "state.release=false; state.canary=0" in artifact_text
    assert "wymaga ponownego humangate" in artifact_text
    assert "state.rolledback=false; state.canary" in artifact_text
    assert "rollback" in artifact_text
    assert "humangate" in artifact_text
    assert "mock" not in artifact_text
    assert "stub" not in artifact_text
    assert all(result["status"] == "pass" for result in execution["audit"]["results"])


def test_project_management_classifier_wins_over_gdpr_and_funding_tokens():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"Sentinel Grid {uuid4().hex[:6]}",
            "idea_raw": (
                "Polski system projektowy dla R&D/software house: portfel projektow, Kanban, Gantt, backlog, "
                "RBAC audit, compliance GDPR/NIS2, funding FENG SMART Horizon EIC, budzet projektu, "
                "release gate, canary i Hetzner deploy z HumanGate."
            ),
            "owner_id": "workspace-default",
        },
    )

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["project_kind"] == "project_management_system"
    assert "tenant_workspace" in project["worker_plan"]["modules"]
    assert "funding_intake" not in project["worker_plan"]["modules"]
    assert "auth_users" not in project["worker_plan"]["modules"]


def test_hetzner_provision_blocks_without_financial_confirmation():
    response = client.post(
        "/api/v1/deploy/hetzner/provision",
        json={
            "project_id": "project_missing",
            "connector_id": "connector_missing",
            "confirm_financial_action": False,
        },
    )

    assert response.status_code == 409
    assert "financial" in response.json()["detail"].lower()


def test_hetzner_provision_blocks_deprecated_server_type_before_cloud_call():
    response = client.post(
        "/api/v1/deploy/hetzner/provision",
        json={
            "project_id": "project_missing",
            "connector_id": "connector_missing",
            "server_type": "cx22",
            "confirm_financial_action": True,
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "deprecated" in detail
    assert "cx23" in detail


def test_hetzner_provision_blocks_scale_above_operator_limit_before_cloud_call():
    response = client.post(
        "/api/v1/deploy/hetzner/provision",
        json={
            "project_id": "project_missing",
            "connector_id": "connector_missing",
            "environment_count": 4,
            "vps_per_environment": 3,
            "confirm_financial_action": True,
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"].lower()
    assert "10 vps" in detail
    assert "environment_count" in detail


def test_design_tool_launch_uses_design_kind_and_canvas_artifact():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"Planner Project {uuid4().hex[:6]}",
            "idea_raw": "zbuduj prosty program do projektowania pokoju 2D z przesuwaniem mebli",
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    created = response.json()
    project = created["project"]
    project_id = project["project_id"]

    assert project["project_kind"] == "design_tool"
    assert project["worker_plan"]["modules"] == ["canvas_kernel", "layout_state", "furniture_tools", "integration_validation"]

    for question in client.get(f"/api/v1/projects/{project_id}/questions?status=pending").json()["questions"]:
        choice_id = question["choices"][0]["choice_id"]
        answered = client.post(
            f"/api/v1/projects/{project_id}/questions/{question['question_id']}/answer",
            json={"choice_id": choice_id, "source": "human"},
        )
        assert answered.status_code == 200

    _approve_freeze(project_id, "canon")
    _approve_freeze(project_id, "masterplan")

    launch = client.post(
        f"/api/v1/projects/{project_id}/launch",
        json={"auto_execute": True, "wait_for_completion": True},
    )
    assert launch.status_code == 200
    payload = launch.json()
    execution = payload["execution"]
    artifact_path = Path(execution["artifact_path"])
    assert artifact_path.is_file()
    assert execution["validation"]["success"] is True
    assert "<canvas" in artifact_path.read_text(encoding="utf-8").lower()

    detail = client.get(f"/api/v1/projects/{project_id}").json()
    assert detail["status"] == "completed"
    assert detail["project_kind"] == "design_tool"


def test_funding_launch_generates_domain_artifact_not_calculator_fallback():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"Funding Project {uuid4().hex[:6]}",
            "idea_raw": (
                "System grantowy FENG SMART Horizon Europe EIC dla kryptografii "
                "postkwantowej z Perplexity, Bielik, PLLuM i HumanGate przed scoringiem"
            ),
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    project = response.json()["project"]
    project_id = project["project_id"]
    assert project["project_kind"] == "funding"
    assert "source_verification" in project["worker_plan"]["modules"]
    assert "deadline_guard" in project["worker_plan"]["modules"]
    assert "polish_model_context_review" in project["worker_plan"]["modules"]
    assert project["governance_policy"]["decision_class"] == "D4"
    assert project["governance_policy"]["source_truth_policy"] == "official_sources_required"

    for question in client.get(f"/api/v1/projects/{project_id}/questions?status=pending").json()["questions"]:
        choice_id = question["choices"][0]["choice_id"]
        answered = client.post(
            f"/api/v1/projects/{project_id}/questions/{question['question_id']}/answer",
            json={"choice_id": choice_id, "source": "human"},
        )
        assert answered.status_code == 200

    _approve_freeze(project_id, "canon")
    _approve_freeze(project_id, "masterplan")

    launch = client.post(
        f"/api/v1/projects/{project_id}/launch",
        json={"auto_execute": True, "wait_for_completion": True},
    )
    assert launch.status_code == 200
    execution = launch.json()["execution"]
    artifact_path = Path(execution["artifact_path"])
    artifact_text = artifact_path.read_text(encoding="utf-8").lower()

    assert execution["artifact_format"] == "html"
    assert execution["validation"]["success"] is True
    assert "feng" in artifact_text
    assert "horizon" in artifact_text
    assert "perplexity" in artifact_text
    assert "google" in artifact_text
    assert "bielik" in artifact_text
    assert "pllum" in artifact_text
    assert "source_verification" in artifact_text
    assert "deadline_guard" in artifact_text
    assert "funding_submission" in artifact_text
    assert "humangate" in artifact_text
    assert "def add(" not in artifact_text
    assert "def sub(" not in artifact_text
    assert "alert(" not in artifact_text
    assert all(result["status"] == "pass" for result in execution["audit"]["results"])

    raw = client.get(f"/api/v1/projects/{project_id}/artifact/raw")
    assert raw.status_code == 200
    assert raw.headers["content-type"].startswith("text/html")
    assert "content-disposition" not in raw.headers
    assert "source_verification" in raw.text
    assert "deadline_guard" in raw.text
