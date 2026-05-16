from fastapi.testclient import TestClient

from sylion.api.app import app
import sylion.api.ai_workspace_routes as _routes
import sylion.api.gates_routes as gates_routes
import sylion.api.idea_routes as idea_routes
from sylion.cognitive.chat_engine import reset_chat_engine
from sylion.cognitive.idea_attachments import IdeaAttachments
from sylion.cognitive.idea_vault import IdeaVault, reset_idea_vault
from sylion.governance.human_gate import reset_human_gate


client = TestClient(app)


def test_attachment_analysis_detects_pii_and_humangate(tmp_path):
    store = IdeaAttachments(db_path=tmp_path / "ideas.db")
    attachment = store.add_attachment(
        idea_id="draft-1",
        filename="pii.md",
        file_type="text/markdown",
        content_bytes=(
            b"PII redactor for HR documents. GDPR scope, employee emails, "
            b"external LLM policy not decided."
        ),
    )

    analysis = store.analyze_attachment(attachment["attachment_id"])

    assert analysis["decision_class"] == "D4"
    assert analysis["human_gate_required"] is True
    assert "pii_redactor" in analysis["suggested_skills"]
    assert "gdpr" in analysis["tags"]


def test_attachment_analysis_extracts_svg_context(tmp_path):
    store = IdeaAttachments(db_path=tmp_path / "ideas.db")
    attachment = store.add_attachment(
        idea_id="draft-2",
        filename="grant-map.svg",
        file_type="image/svg+xml",
        content_bytes=b"<svg><text>Horizon grant deadline source required quantum crypto TRL</text></svg>",
    )

    analysis = store.analyze_attachment(attachment["attachment_id"])

    assert analysis["detected_kind"] == "svg_diagram"
    assert "funding_research" in analysis["suggested_skills"]
    assert "deep_tech" in analysis["tags"]
    assert analysis["human_gate_required"] is True


def test_attachment_analysis_routes_mental_health_svg_to_safety_skills(tmp_path):
    store = IdeaAttachments(db_path=tmp_path / "ideas.db")
    attachment = store.add_attachment(
        idea_id="draft-mental",
        filename="vanguard-mind.svg",
        file_type="image/svg+xml",
        content_bytes=(
            b"<svg><text>mental wellbeing assistant safety classifier kryzys "
            b"autoagresja no medical advice emergency hand-off D5</text></svg>"
        ),
    )

    analysis = store.analyze_attachment(attachment["attachment_id"])

    assert analysis["detected_kind"] == "svg_diagram"
    assert analysis["decision_class"] == "D5"
    assert analysis["human_gate_required"] is True
    assert "mental_health" in analysis["tags"]
    assert "mental_health_safety_classifier" in analysis["suggested_skills"]
    assert "crisis_response_guard" in analysis["suggested_skills"]
    assert "no_medical_advice_guard" in analysis["suggested_skills"]
    assert "bioinformatics_guard" not in analysis["suggested_skills"]


def test_attachment_analysis_treats_ino_as_firmware_source(tmp_path):
    store = IdeaAttachments(db_path=tmp_path / "ideas.db")
    attachment = store.add_attachment(
        idea_id="draft-fw-source",
        filename="service_guard.ino",
        file_type="application/octet-stream",
        content_bytes=b"const char* DEVICE_ID = \"pump-1\"; void setup(){} void loop(){}",
    )

    analysis = store.analyze_attachment(attachment["attachment_id"])

    assert analysis["detected_kind"] == "source_code"
    assert analysis["decision_class"] == "D4"
    assert analysis["human_gate_required"] is True
    assert "firmware" in analysis["tags"]
    assert "firmware_attachment_guard" in analysis["suggested_skills"]
    assert "secure_approval" in analysis["suggested_skills"]
    assert not any("text-only extractor" in risk for risk in analysis["risks"])


def test_attachment_analysis_treats_bin_as_firmware_binary_with_hash(tmp_path):
    store = IdeaAttachments(db_path=tmp_path / "ideas.db")
    attachment = store.add_attachment(
        idea_id="draft-fw-bin",
        filename="service_guard.bin",
        file_type="application/octet-stream",
        content_bytes=b"\x01AEIS-FIRMWARE\x02",
    )

    analysis = store.analyze_attachment(attachment["attachment_id"])

    assert analysis["detected_kind"] == "firmware_binary"
    assert analysis["decision_class"] == "D4"
    assert analysis["human_gate_required"] is True
    assert "firmware" in analysis["tags"]
    assert "firmware_attachment_guard" in analysis["suggested_skills"]
    assert "device_binding" in analysis["suggested_skills"]
    assert "sha256=" in analysis["extracted_text_preview"]
    assert any("Firmware sha256 proof" in risk for risk in analysis["risks"])
    assert not any("text-only extractor" in risk for risk in analysis["risks"])


def test_reassign_attachments_moves_metadata_and_analysis(tmp_path):
    store = IdeaAttachments(db_path=tmp_path / "ideas.db")
    attachment = store.add_attachment(
        idea_id="draft-before-create",
        filename="password-policy.md",
        file_type="text/markdown",
        content_bytes=b"GDPR PII password policy session timeout human gate",
    )
    analysis = store.analyze_attachment(attachment["attachment_id"])

    moved = store.reassign_attachments([attachment["attachment_id"]], "idea-final")

    assert moved[0]["idea_id"] == "idea-final"
    assert store.list_attachments("draft-before-create") == []
    final_analyses = store.list_attachment_analysis("idea-final")
    assert final_analyses[0]["analysis_id"] == analysis["analysis_id"]
    assert final_analyses[0]["decision_class"] == "D4"


def test_reanalysis_replaces_visible_attachment_result(tmp_path):
    store = IdeaAttachments(db_path=tmp_path / "ideas.db")
    attachment = store.add_attachment(
        idea_id="draft-reanalysis",
        filename="service_guard.bin",
        file_type="application/octet-stream",
        content_bytes=b"\x01AEIS-FIRMWARE\x02",
    )

    first = store.analyze_attachment(attachment["attachment_id"])
    second = store.analyze_attachment(attachment["attachment_id"])
    visible = store.list_attachment_analysis("draft-reanalysis")

    assert first["analysis_id"] != second["analysis_id"]
    assert len(visible) == 1
    assert visible[0]["analysis_id"] == second["analysis_id"]
    assert visible[0]["detected_kind"] == "firmware_binary"
    assert visible[0]["decision_class"] == "D4"


def test_local_import_endpoint_uses_attachment_store(tmp_path):
    _routes._idea_attachments = IdeaAttachments(db_path=tmp_path / "attachments.db")
    source = tmp_path / "local-idea.md"
    source.write_text("Horizon grant idea with quantum crypto funding scope", encoding="utf-8")

    response = client.post(
        "/api/v1/workspace/ideas/import-local",
        json={"file_path": str(source), "idea_id": "draft-local"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["idea_id"] == "draft-local"
    assert body["filename"] == "local-idea.md"
    assert body["source"] == "local_path_import"

    analyses = client.post("/api/v1/workspace/ideas/draft-local/attachments/analyze")
    assert analyses.status_code == 200
    assert analyses.json()["analyses"][0]["human_gate_required"] is True


def test_create_idea_with_d4_attachment_requests_humangate(tmp_path):
    from sylion.governance.tickets import reset_ticket_store

    old_attachment_store = _routes._idea_attachments
    old_idea_vault = idea_routes._idea_vault
    try:
        _routes._idea_attachments = IdeaAttachments(db_path=tmp_path / "attachments.db")
        idea_routes._idea_vault = IdeaVault(db_path=tmp_path / "ideas.db")
        reset_human_gate(db_path=tmp_path / "human_gate.db")
        reset_ticket_store(db_path=tmp_path / "tickets.db")

        attachment = _routes._idea_attachments.add_attachment(
            idea_id="draft-hg",
            filename="employee-portal.md",
            file_type="text/markdown",
            content_bytes=(
                b"Portal pracowniczy: GDPR, PII, employee email, external LLM, "
                b"DPIA, retention, human gate and production approval required."
            ),
        )
        analysis = _routes._idea_attachments.analyze_attachment(attachment["attachment_id"])
        assert analysis["decision_class"] == "D4"

        response = client.post(
            "/api/v1/ideas",
            json={
                "title": "Portal pracowniczy z D4 attachment",
                "description": "Pomysl utworzony z zalacznikiem D4.",
                "author": "audit-operator",
                "tags": ["gdpr", "employee_portal"],
                "attachments": [{"attachment_id": attachment["attachment_id"]}],
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "awaiting_approval"
        assert body["human_gate_required"] == 1
        assert body["human_gate_request_id"]
        assert body["attachment_analysis"][0]["decision_class"] == "D4"
        assert body["attachment_analysis"][0]["human_gate_required"] is True
        ticket = client.get(f"/api/v1/governance/tickets/{body['human_gate_request_id']}")
        assert ticket.status_code == 200
        assert ticket.json()["decision_class"] == "D4"
        assert ticket.json()["priority"] == "P1"
    finally:
        _routes._idea_attachments = old_attachment_store
        idea_routes._idea_vault = old_idea_vault
        reset_ticket_store()


def test_create_idea_with_d5_genomic_attachment_mirrors_d5_ticket(tmp_path):
    from sylion.governance.tickets import reset_ticket_store

    old_attachment_store = _routes._idea_attachments
    old_idea_vault = idea_routes._idea_vault
    try:
        _routes._idea_attachments = IdeaAttachments(db_path=tmp_path / "attachments.db")
        idea_routes._idea_vault = IdeaVault(db_path=tmp_path / "ideas.db")
        reset_human_gate(db_path=tmp_path / "human_gate.db")
        reset_ticket_store(db_path=tmp_path / "tickets.db")

        attachment = _routes._idea_attachments.add_attachment(
            idea_id="draft-d5",
            filename="aurora-genome.txt",
            file_type="text/plain",
            content_bytes=(
                b"D5 genomic research workflow, syntetyczne dane FASTQ/VCF, "
                b"zakaz decyzji klinicznych, pacjent data guard, HumanGate export."
            ),
        )
        analysis = _routes._idea_attachments.analyze_attachment(attachment["attachment_id"])
        assert analysis["decision_class"] == "D5"

        response = client.post(
            "/api/v1/ideas",
            json={
                "title": "AURORA-GENOME D5",
                "description": "Pomysl z zalacznikiem D5 powinien miec bilet D5/P0.",
                "author": "audit-operator",
                "tags": ["genomika"],
                "attachments": [{"attachment_id": attachment["attachment_id"]}],
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "awaiting_approval"
        assert body["human_gate_request_id"]
        ticket = client.get(f"/api/v1/governance/tickets/{body['human_gate_request_id']}")
        assert ticket.status_code == 200
        data = ticket.json()
        assert data["decision_class"] == "D5"
        assert data["priority"] == "P0"
        assert data["payload"]["context"]["decision_class"] == "D5"
    finally:
        _routes._idea_attachments = old_attachment_store
        idea_routes._idea_vault = old_idea_vault
        reset_ticket_store()


def test_humangate_review_syncs_linked_idea_status(tmp_path):
    old_attachment_store = _routes._idea_attachments
    old_idea_vault = idea_routes._idea_vault
    old_human_gate = gates_routes._human_gate
    try:
        _routes._idea_attachments = IdeaAttachments(db_path=tmp_path / "attachments.db")
        vault = reset_idea_vault(tmp_path / "ideas.db")
        idea_routes._idea_vault = vault
        gates_routes._human_gate = reset_human_gate(db_path=tmp_path / "human_gate.db")

        attachment = _routes._idea_attachments.add_attachment(
            idea_id="draft-sync",
            filename="employee-portal.md",
            file_type="text/markdown",
            content_bytes=b"GDPR PII DPIA external LLM employee portal human gate.",
        )
        _routes._idea_attachments.analyze_attachment(attachment["attachment_id"])

        created = client.post(
            "/api/v1/ideas",
            json={
                "title": "Idea HG sync",
                "description": "Sprawdzenie synchronizacji HumanGate z IdeaVault.",
                "author": "audit-operator",
                "tags": ["gdpr"],
                "attachments": [{"attachment_id": attachment["attachment_id"]}],
            },
        )
        assert created.status_code == 201
        created_body = created.json()
        assert created_body["status"] == "awaiting_approval"

        review = client.post(
            "/api/v1/gates/human/reviews",
            json={
                "request_id": created_body["human_gate_request_id"],
                "reviewer": "operator-dashboard",
                "decision": "needs_info",
                "rationale": "Potrzebne doprecyzowanie retencji.",
            },
        )

        assert review.status_code == 201
        idea = vault.get_idea(created_body["idea_id"])
        assert idea["status"] == "clarification"
        assert idea["human_gate_required"] == 1
        assert idea["human_gate_decision"] == "needs_info"
        assert idea["human_gate_decided_by"] == "operator-dashboard"
    finally:
        _routes._idea_attachments = old_attachment_store
        idea_routes._idea_vault = old_idea_vault
        gates_routes._human_gate = old_human_gate


def test_unified_humangate_ticket_resolve_syncs_linked_idea_status(tmp_path):
    from sylion.governance.tickets import reset_ticket_store

    old_idea_vault = idea_routes._idea_vault
    old_human_gate = gates_routes._human_gate
    try:
        vault = reset_idea_vault(tmp_path / "ideas.db")
        idea_routes._idea_vault = vault
        gate = reset_human_gate(db_path=tmp_path / "human_gate.db")
        gates_routes._human_gate = gate
        reset_ticket_store(db_path=tmp_path / "tickets.db")

        idea = vault.create_idea(
            title="Unified HG sync",
            description="D4 marketplace publication must be approved in the main HumanGate queue.",
            author="audit-operator",
            tags=["human-gate", "marketplace"],
        )
        gated = vault.request_approval(
            idea["idea_id"],
            requested_by="audit-operator",
            priority="attachment_d4",
        )
        request_id = gated["human_gate_request_id"]

        ticket = client.get(f"/api/v1/governance/tickets/{request_id}")
        assert ticket.status_code == 200
        assert ticket.json()["payload"]["legacy_gate_id"] == f"idea:{idea['idea_id']}"

        resolved = client.post(
            f"/api/v1/governance/tickets/{request_id}/resolve",
            json={
                "reviewer": "operator-console",
                "decision": "approved",
                "reason": "Operator zatwierdza z glownej kolejki HumanGate.",
            },
        )

        assert resolved.status_code == 200
        assert resolved.json()["state"] == "approved"
        synced = vault.get_idea(idea["idea_id"])
        assert synced["status"] == "accepted"
        assert synced["human_gate_required"] == 0
        assert synced["human_gate_decision"] == "approved"
        assert synced["human_gate_decided_by"] == "operator-console"
        assert gate.get_request(request_id)["status"] == "approved"
    finally:
        idea_routes._idea_vault = old_idea_vault
        gates_routes._human_gate = old_human_gate
        reset_ticket_store()


def test_manual_approval_transition_reopens_humangate_after_needs_info(tmp_path):
    old_idea_vault = idea_routes._idea_vault
    old_human_gate = gates_routes._human_gate
    try:
        vault = reset_idea_vault(tmp_path / "ideas.db")
        idea_routes._idea_vault = vault
        gates_routes._human_gate = reset_human_gate(db_path=tmp_path / "human_gate.db")

        idea = vault.create_idea(
            title="Idea wymagajaca ponownego HG",
            description="D4 marketplace export with external API publication.",
            author="audit-operator",
            tags=["human-gate"],
        )
        gated = vault.request_approval(
            idea["idea_id"],
            requested_by="audit-operator",
            priority="attachment_d4",
        )
        first_request_id = gated["human_gate_request_id"]

        review = client.post(
            "/api/v1/gates/human/reviews",
            json={
                "request_id": first_request_id,
                "reviewer": "operator-dashboard",
                "decision": "needs_info",
                "rationale": "Brakuje polityki publikacji zewnetrznej.",
            },
        )
        assert review.status_code == 201
        assert vault.get_idea(idea["idea_id"])["status"] == "clarification"

        answer = client.post(
            f"/api/v1/ideas/{idea['idea_id']}/clarification-response",
            json={
                "response": "Publikacja do API zewnetrznego zawsze wymaga osobnego HumanGate.",
                "responder": "operator",
            },
        )
        assert answer.status_code == 200

        council = client.put(
            f"/api/v1/ideas/{idea['idea_id']}",
            json={"status": "council_review", "author": "operator"},
        )
        assert council.status_code == 200
        assert council.json()["status"] == "council_review"

        reopened = client.put(
            f"/api/v1/ideas/{idea['idea_id']}",
            json={"status": "awaiting_approval", "author": "operator"},
        )
        assert reopened.status_code == 200
        body = reopened.json()
        assert body["status"] == "awaiting_approval"
        assert body["human_gate_required"] == 1
        assert body["human_gate_request_id"]
        assert body["human_gate_request_id"] != first_request_id
        assert body["human_gate_decision"] == ""
        assert body["human_gate_decided_by"] == ""
        assert body["human_gate_decided_at"] is None

        pending = client.get("/api/v1/gates/human/requests?status=pending")
        assert pending.status_code == 200
        pending_ids = {item["request_id"] for item in pending.json()["requests"]}
        assert body["human_gate_request_id"] in pending_ids
    finally:
        idea_routes._idea_vault = old_idea_vault
        gates_routes._human_gate = old_human_gate


def test_idea_discussion_runs_real_runner_and_writes_assistant_messages(tmp_path, monkeypatch):
    old_idea_vault = idea_routes._idea_vault
    try:
        vault = IdeaVault(db_path=tmp_path / "ideas.db")
        idea_routes._idea_vault = vault
        reset_chat_engine(db_path=tmp_path / "chat.db")
        idea = vault.create_idea(
            title="Generator opisow e-commerce",
            description="Opisuje produkty z obrazow i eksportuje do marketplace.",
            author="audit-operator",
            tags=["ecommerce"],
        )

        def fake_discussion(**kwargs):
            model_id = kwargs["model_id"]
            return {
                "ok": True,
                "model_id": model_id,
                "provider": "test-provider",
                "model": model_id,
                "latency_ms": 12,
                "prompt_tokens": 100,
                "completion_tokens": 40,
                "estimated_cost_usd": 0.001,
                "fallback_used": False,
                "content": f"verdict: approve\nmodel: {model_id}\nskills_needed: image_analysis, marketplace_export",
            }

        monkeypatch.setattr(_routes, "_run_idea_model_discussion", fake_discussion)

        response = client.post(
            f"/api/v1/ideas/{idea['idea_id']}/discuss",
            json={
                "prompt": "Sprawdz ryzyka i umiejetnosci.",
                "model_ids": ["gpt-4o-mini", "claude-haiku-4-5"],
                "rounds": 1,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert len(body["responses"]) == 2

        messages = client.get(f"/api/v1/workspace/sessions/{body['session_id']}/messages")
        assert messages.status_code == 200
        rows = messages.json()["messages"]
        assistant_rows = [row for row in rows if row["role"] == "assistant"]
        assert len(assistant_rows) == 2
        assert {row["model_id"] for row in assistant_rows} == {"gpt-4o-mini", "claude-haiku-4-5"}
        assert all(row["metadata"]["source"] == "idea_discussion" for row in assistant_rows)
    finally:
        idea_routes._idea_vault = old_idea_vault
        reset_chat_engine()


def test_idea_discussion_list_is_scoped_to_idea_id(tmp_path, monkeypatch):
    old_idea_vault = idea_routes._idea_vault
    try:
        vault = IdeaVault(db_path=tmp_path / "ideas.db")
        idea_routes._idea_vault = vault
        reset_chat_engine(db_path=tmp_path / "chat.db")
        first = vault.create_idea(
            title="Pierwsza idea",
            description="Opis pierwszej idei.",
            author="audit-operator",
        )
        second = vault.create_idea(
            title="Druga idea",
            description="Opis drugiej idei.",
            author="audit-operator",
        )

        def fake_discussion(**kwargs):
            return {
                "ok": True,
                "model_id": kwargs["model_id"],
                "provider": "test-provider",
                "content": f"Analiza dla {kwargs['title']}",
            }

        monkeypatch.setattr(_routes, "_run_idea_model_discussion", fake_discussion)

        first_discussion = client.post(
            f"/api/v1/ideas/{first['idea_id']}/discuss",
            json={"model_ids": ["model-a"], "rounds": 1},
        )
        second_discussion = client.post(
            f"/api/v1/ideas/{second['idea_id']}/discuss",
            json={"model_ids": ["model-b"], "rounds": 1},
        )
        assert first_discussion.status_code == 200
        assert second_discussion.status_code == 200

        first_sessions = client.get(f"/api/v1/ideas/{first['idea_id']}/discussion")
        second_sessions = client.get(f"/api/v1/ideas/{second['idea_id']}/discussion")

        assert first_sessions.status_code == 200
        assert second_sessions.status_code == 200
        assert [
            item["session_id"] for item in first_sessions.json()["sessions"]
        ] == [first_discussion.json()["session_id"]]
        assert [
            item["session_id"] for item in second_sessions.json()["sessions"]
        ] == [second_discussion.json()["session_id"]]
    finally:
        idea_routes._idea_vault = old_idea_vault
        reset_chat_engine()
