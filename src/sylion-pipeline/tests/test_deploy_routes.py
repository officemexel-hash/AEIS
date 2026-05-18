from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from sylion.api.app import app
from sylion.execution.deployment_orchestrator import reset_deployment_orchestrator
from sylion.core.bundle_assembler import reset_bundle_assembler
from sylion.governance.tickets import (
    GovernanceTicket,
    clear_post_resolve_hooks,
    fetch_by_id,
    reset_ticket_store,
    resolve,
    submit,
)
import sylion.api.ai_workspace_routes as _routes
import sylion.api.bundle_routes as _bundle_routes
import sylion.api.deploy_routes as _deploy_routes
import sylion.api.pipeline_routes as _pipeline_routes
import sylion.project_mode.store as _project_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_deploy_surface(tmp_path, monkeypatch):
    from sylion.cognitive.chat_engine import ChatEngine
    from sylion.governance.council_hybrid import CouncilHybrid
    from sylion.security.key_vault import KeyVault
    from sylion.cognitive.prompt_templates import PromptTemplateManager
    from sylion.memory.book_generator import BookGenerator
    from sylion.governance.human_gate import HumanGate
    from sylion.cognitive.idea_vault import IdeaVault

    class StubLLM:
        def call_messages(self, model_id, messages, max_tokens=1000):
            return {
                "call_id": "stub-call-001",
                "text": "AEIS_STUB_REPLY",
                "tokens": 7,
                "cost": 0.0,
                "latency_ms": 1,
            }

    class FakePipelineController:
        def submit_idea(self, idea, context=None):
            return {"run_id": "run_fake_001", "status": "pending", "idea": idea, "context": context or {}}

        def execute_run(self, run_id):
            return {"run_id": run_id, "status": "complete", "steps": []}

    def clear_if_present(name: str) -> None:
        value = getattr(_routes, name, None)
        if hasattr(value, "clear"):
            value.clear()

    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "project_mode.sqlite"))
    monkeypatch.setenv("SYLION_PROJECT_RESULTS_ROOT", str(tmp_path / "project-results"))
    reset_ticket_store()
    clear_post_resolve_hooks()
    import sylion.project_mode.round_meta_hooks as _round_meta_hooks

    _round_meta_hooks._REGISTERED = False
    _round_meta_hooks.register_round_meta_hook()
    reset_bundle_assembler()
    _bundle_routes._bundle_assembler = None
    workspace_conn = getattr(_routes, "_workspace_state_conn", None)
    if workspace_conn is not None:
        workspace_conn.close()
    if hasattr(_routes, "_workspace_state_conn"):
        _routes._workspace_state_conn = None
    if hasattr(_routes, "_workspace_state_loaded"):
        _routes._workspace_state_loaded = False
    project_store = getattr(_routes, "_project_store", None)
    if project_store is not None:
        project_store.close()
    if hasattr(_routes, "_project_store"):
        _routes._project_store = None
    if _project_store._store is not None:
        _project_store._store.close()
    _project_store._store = None

    _routes._chat_engine = ChatEngine()
    _routes._council = CouncilHybrid()
    _routes._vault = KeyVault()
    _routes._prompts = PromptTemplateManager()
    _routes._books = BookGenerator()
    _routes._llm = StubLLM()
    _routes._hg = HumanGate()
    _routes._idea_vault = IdeaVault()
    _routes._idea_attachments = None
    clear_if_present("_workspace_notifications")
    clear_if_present("_project_kickoffs")
    clear_if_present("_hg_workflows")
    clear_if_present("_project_launch_futures")
    _pipeline_routes._controller = FakePipelineController()
    reset_deployment_orchestrator(str(tmp_path / "deployments.sqlite"))

    yield

    workspace_conn = getattr(_routes, "_workspace_state_conn", None)
    if workspace_conn is not None:
        workspace_conn.close()
    if hasattr(_routes, "_workspace_state_conn"):
        _routes._workspace_state_conn = None
    if hasattr(_routes, "_workspace_state_loaded"):
        _routes._workspace_state_loaded = False
    project_store = getattr(_routes, "_project_store", None)
    if project_store is not None:
        project_store.close()
    if hasattr(_routes, "_project_store"):
        _routes._project_store = None
    if _project_store._store is not None:
        _project_store._store.close()
    _project_store._store = None
    _routes._chat_engine = None
    _routes._council = None
    _routes._vault = None
    _routes._prompts = None
    _routes._books = None
    _routes._llm = None
    _routes._hg = None
    _routes._idea_vault = None
    _routes._idea_attachments = None
    clear_if_present("_workspace_notifications")
    clear_if_present("_project_kickoffs")
    clear_if_present("_hg_workflows")
    clear_if_present("_project_launch_futures")
    _pipeline_routes._controller = None
    reset_deployment_orchestrator()
    reset_bundle_assembler()
    _bundle_routes._bundle_assembler = None
    clear_post_resolve_hooks()
    _round_meta_hooks._REGISTERED = False
    reset_ticket_store()


def _create_project() -> str:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"Deploy Project {uuid4().hex[:6]}",
            "idea_raw": "zbuduj prosty komunikator z rejestracja, logowaniem, pokojami i wiadomosciami",
            "constraints": "offline-first",
            "preferred_stack": ["Next.js", "FastAPI", "SQLite"],
            "owner_id": "workspace-default",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    return payload.get("project", payload)["project_id"]


def _answer_all_questions(project_id: str) -> None:
    pending = client.get(f"/api/v1/projects/{project_id}/questions?status=pending")
    assert pending.status_code == 200
    for question in pending.json()["questions"]:
        choice_id = question["choices"][0]["choice_id"]
        answered = client.post(
            f"/api/v1/projects/{project_id}/questions/{question['question_id']}/answer",
            json={"choice_id": choice_id, "source": "human"},
        )
        assert answered.status_code == 200


def _launch_project(project_id: str) -> dict:
    _answer_all_questions(project_id)
    for target in ("canon", "masterplan"):
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

    response = client.post(
        f"/api/v1/projects/{project_id}/launch",
        json={"auto_execute": True, "wait_for_completion": True},
    )
    assert response.status_code == 200
    return response.json()


def test_deploy_summary_reports_unlaunched_projects_as_pending():
    project_id = _create_project()

    response = client.get("/api/v1/deploy/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"]["ready_projects"] == 0
    pending = next(item for item in payload["pending_projects"] if item["project_id"] == project_id)
    assert pending["reason"] == "Project has not been launched into the pipeline yet."
    assert pending["recommended_action"].startswith("Launch the project")


def test_deploy_summary_returns_real_artifact_and_bundle_after_launch():
    project_id = _create_project()
    launch = _launch_project(project_id)

    response = client.get("/api/v1/deploy/summary")

    assert response.status_code == 200
    payload = response.json()
    ready = next(item for item in payload["ready_projects"] if item["project_id"] == project_id)
    artifact_path = Path(launch["execution"]["artifact_path"]).resolve()

    assert ready["reason"] == ""
    assert ready["artifact"]["exists"] is True
    assert ready["artifact"]["path"] == str(artifact_path)
    assert ready["artifact"]["sha256"] == launch["execution"]["artifact_sha256"]
    assert ready["validation"]["success"] is True
    assert ready["bundle"]["status"] == "ready"
    assert all(item["exists"] for item in ready["bundle"]["files"])
    assert ready["module_output_count"] >= 1


def test_deploy_summary_exposes_active_deployment_queue():
    response = client.post(
        "/api/v1/deployments",
        params={
            "module_id": "core.operator_panel",
            "from_stage": "draft",
            "to_stage": "build",
            "strategy": "canary",
        },
    )
    assert response.status_code == 201

    summary = client.get("/api/v1/deploy/summary")

    assert summary.status_code == 200
    payload = summary.json()
    active = next(item for item in payload["active_deployments"] if item["module_id"] == "core.operator_panel")
    assert active["status"] == "pending"
    assert active["strategy"] == "canary"
    assert active["step_summary"]["current_step"] == "prepare"


def test_production_deployment_creation_requires_human_gate():
    blocked = client.post(
        "/api/v1/deployments",
        params={
            "module_id": "core.operator_panel",
            "from_stage": "cutover",
            "to_stage": "stable",
            "strategy": "canary",
        },
    )

    assert blocked.status_code == 423
    detail = blocked.json()["detail"]
    assert detail["requires_human_gate"] is True
    ticket_id = detail["governance_ticket_id"]
    ticket = fetch_by_id(ticket_id)
    assert ticket is not None
    assert ticket.gate_type == "production"
    assert ticket.state == "pending"

    assert resolve(
        ticket_id,
        "approved",
        reason="operator approved production deployment gate",
        reviewer="operator@example.com",
    ) is True
    allowed = client.post(
        "/api/v1/deployments",
        params={
            "module_id": "core.operator_panel",
            "from_stage": "cutover",
            "to_stage": "stable",
            "strategy": "canary",
            "approval_ticket_id": ticket_id,
        },
    )

    assert allowed.status_code == 201
    payload = allowed.json()
    assert payload["to_stage"] == "stable"
    assert payload["metadata"]["governance_ticket_id"] == ticket_id


def test_d3_plus_ticket_resolution_requires_reason():
    ticket_id = submit(GovernanceTicket(
        origin="workspace",
        decision_class="D4",
        gate_type="production",
        priority="P0",
        title="Production approval needs reason",
        summary="D3+ governance tickets must not be resolved without rationale.",
        payload={
            "action": "deployment.create",
            "target": "stable",
            "module_id": "core.operator_panel",
            "requires_human_gate": True,
        },
        requested_by="test",
    ))

    response = client.post(
        f"/api/v1/governance/tickets/{ticket_id}/resolve",
        json={"decision": "approved", "reviewer": "operator@example.com"},
    )

    assert response.status_code == 422
    assert "reason is required" in response.json()["detail"]
    assert fetch_by_id(ticket_id).state == "pending"


def test_production_deployment_rejects_approved_ticket_for_other_module():
    ticket_id = submit(GovernanceTicket(
        origin="workspace",
        decision_class="D4",
        gate_type="production",
        priority="P0",
        title="Wrong module production approval",
        summary="Ticket is intentionally scoped to another module.",
        payload={
            "action": "deployment.create",
            "target": "stable",
            "to_stage": "stable",
            "module_id": "core.other_panel",
            "requires_human_gate": True,
        },
        requested_by="test",
    ))
    assert resolve(
        ticket_id,
        "approved",
        reason="approve wrong module ticket for negative test",
        reviewer="operator@example.com",
    ) is True

    response = client.post(
        "/api/v1/deployments",
        params={
            "module_id": "core.operator_panel",
            "from_stage": "cutover",
            "to_stage": "stable",
            "strategy": "canary",
            "approval_ticket_id": ticket_id,
        },
    )

    assert response.status_code == 423
    detail = response.json()["detail"]
    assert detail["requires_human_gate"] is True
    assert detail["ticket_validation_reason"] == "module_id_mismatch"


def test_production_bundle_deploy_requires_human_gate():
    created = client.post(
        "/api/v1/bundles",
        json={"name": "prod-bundle", "description": "production deploy gate test"},
    )
    assert created.status_code == 201
    bundle_id = created.json()["bundle_id"]

    blocked = client.post(
        "/api/v1/bundles/deploy",
        json={"bundle_id": bundle_id, "target_env": "production"},
    )
    assert blocked.status_code == 423
    detail = blocked.json()["detail"]
    assert detail["requires_human_gate"] is True
    ticket_id = detail["governance_ticket_id"]

    assert resolve(
        ticket_id,
        "approved",
        reason="operator approved production bundle deployment gate",
        reviewer="operator@example.com",
    ) is True
    allowed = client.post(
        "/api/v1/bundles/deploy",
        json={
            "bundle_id": bundle_id,
            "target_env": "production",
            "approval_ticket_id": ticket_id,
        },
    )
    assert allowed.status_code == 202
    assert allowed.json()["status"] == "deploying"


def test_generated_topology_files_do_not_emit_placeholder_hosts_or_repo():
    response = client.post("/api/v1/deploy/topologies/8_server")

    assert response.status_code == 200
    payload = response.json()
    inventory = payload["files"]["ansible_inventory_ini"]
    playbook = payload["files"]["ansible_playbook_yml"]

    assert "ansible_host=TODO" not in inventory
    assert "github.com/USER/sylion.git" not in playbook
    assert "Set SYLION_DEPLOY_REPO_URL or configure git remote.origin.url" in playbook


def test_hetzner_health_returns_public_probe_evidence(monkeypatch):
    _deploy_routes._record_hetzner_deployment(
        {
            "deployment_id": "hcloud_probe_001",
            "project_id": "project_probe",
            "connector_id": "connector_probe",
            "provider_server_id": "123",
            "server_name": "aeis-probe",
            "server_type": "cx23",
            "location": "fsn1",
            "image": "ubuntu-24.04",
            "status": "created",
            "public_ipv4": "203.0.113.10",
            "health_url": "",
            "artifact_sha256": "abc123",
            "raw": {},
        }
    )
    public_probe = {
        "ok": True,
        "url": "http://203.0.113.10/healthz",
        "status_code": 200,
        "body_excerpt": "aeis-deploy-ok project_id=project_probe",
        "error": "",
        "expected_marker": "project_id=project_probe",
        "checked_at": 1_776_000_000.0,
    }
    monkeypatch.setattr(
        _deploy_routes,
        "_wait_for_http_health",
        lambda ipv4, project_id, timeout_s=30: (True, public_probe["url"], public_probe),
    )

    response = client.post("/api/v1/deploy/hetzner/hcloud_probe_001/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["health_url"] == "http://203.0.113.10/healthz"
    assert payload["public_probe"]["status_code"] == 200
    assert payload["public_probe"]["body_excerpt"] == "aeis-deploy-ok project_id=project_probe"
    assert payload["deployment"]["raw"]["health_probe"]["ok"] is True
