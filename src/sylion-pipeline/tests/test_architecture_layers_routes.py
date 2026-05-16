from __future__ import annotations

from fastapi.testclient import TestClient

from sylion.api.app import app


client = TestClient(app)
BASE = "/api/v1/architecture-layers"


def test_architecture_layers_expose_canonical_w1_w19_map():
    response = client.get(BASE)
    assert response.status_code == 200
    data = response.json()

    assert data["summary"]["layer_count"] == 19
    assert data["summary"]["phase_count"] == 41
    assert data["layers"][0]["id"] == "W1"
    assert data["layers"][0]["canonical_name"] == "Canon / System Constitution"
    assert data["layers"][-1]["id"] == "W19"

    groups = {group["id"]: group["range"] for group in data["groups"]}
    assert groups["foundation"] == "W1-W9"
    assert groups["operator_console"] == "W18"


def test_w18_is_global_operator_console_layer():
    response = client.get(f"{BASE}/W18")
    assert response.status_code == 200
    layer = response.json()["layer"]

    assert layer["id"] == "W18"
    assert layer["phase_span"] == "1-41"
    assert len(layer["phase_touchpoints"]) == 41
    assert "Kliknięcie w UI powinno generować komendę w W18." in layer["hard_rules"]


def test_working_model_includes_defaults_entities_and_audit_order():
    response = client.get(BASE)
    assert response.status_code == 200
    model = response.json()["working_model"]

    defaults = {item["id"]: item["value"] for item in model["default_policies"]}
    assert defaults["runtime"] == "local-first"
    assert defaults["autonomy"] == "medium"
    assert "approval powyżej ok. 25 EUR" in defaults["cost_single_action"]

    entity_ids = {item["id"] for item in model["entities"]}
    assert {"Project", "SourceOfTruth", "Masterplan", "HumanGateTicket", "MemorySnapshot"} <= entity_ids
    assert model["runtime_truth_order"] == ["kod", "runtime", "API", "UI", "testy", "dokumentacja"]
    assert model["advisor_layer"]["id"] == "W13"
    assert len(model["implementation_planes"]) == 19


def test_phase_overlay_keeps_w18_context_and_execution_closure():
    response = client.get(BASE)
    assert response.status_code == 200
    overlay = response.json()["phase_overlay"]

    assert "W18" in overlay["1"]
    assert "W1" in overlay["1"]
    assert "W18" in overlay["41"]
    assert "W19" in overlay["41"]
    assert "W14" in overlay["39"]
    assert "W17" in overlay["40"]


def test_numeric_layer_lookup_returns_ontology_layer():
    response = client.get(f"{BASE}/15")
    assert response.status_code == 200
    layer = response.json()["layer"]

    assert layer["id"] == "W15"
    assert "Ontology definiuje Project" in layer["runtime_assertion"]
    assert any(surface["href"] == "/ontology" for surface in layer["surfaces"])


def test_document_alignment_exposes_advisor_and_patches():
    response = client.get(BASE)
    assert response.status_code == 200
    data = response.json()

    advisor = data["advisor_layer"]
    assert advisor["id"] == "W13"
    assert "Subscription Advisor" in advisor["specialized_advisors"]
    assert len(advisor["lifecycle_hooks"]) == 16

    patch_ids = {patch["id"] for patch in data["phase_patches"]}
    assert {
        "phase_5_d0_d5",
        "phase_7_subscription_waterfall",
        "phase_20_25_council_hybrid",
        "phase_30_subscription_advisor",
        "customer_y_cost",
    } <= patch_ids

    planes = {plane["id"]: plane["label"] for plane in data["implementation_planes"]}
    assert planes["W13"] == "Advisor Layer"
    assert planes["W18"] == "Operator Terminal Plane"
