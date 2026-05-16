from __future__ import annotations

from fastapi.testclient import TestClient

from sylion.api.app import app
import sylion.api.environment_catalog_routes as routes


client = TestClient(app)
BASE = "/api/v1/environment-catalog"


def _fake_scan(deep_scan: bool = False) -> dict:
    scan = {
        "scanned_at": 1777651200.0,
        "deep_scan": deep_scan,
        "os": {
            "platform": "Windows",
            "platform_release": "11",
            "platform_version": "test",
            "architecture": "AMD64",
            "processor": "Ryzen Test",
            "python_version": "3.14",
        },
        "hardware": {
            "cpu_cores": 16,
            "cpu_model": "Ryzen Test",
            "memory": {"total_gb": 64, "available_gb": 24},
            "disks": [{"mount": "C:\\", "total_gb": 2000, "free_gb": 850}],
            "gpu": {"detected": True, "vendor": "nvidia", "devices": [{"name": "RTX Test", "vram_mb": "24576"}]},
            "network": {
                "hostname": "operator-laptop",
                "local_ips": ["192.168.1.42"],
                "network_interfaces_count": 2,
                "ssh_config_exists": True,
                "ssh_host_entries_count": 3,
                "tailscale_installed": True,
                "wireguard_installed": False,
            },
        },
        "software": {
            "docker": {"installed": True, "version": "Docker version 25"},
            "docker_daemon": {"running": True, "version": "25.0.0"},
            "docker_compose": {"installed": True, "version": "Docker Compose v2"},
            "podman": {"installed": False},
            "git": {"installed": True, "version": "git version 2"},
            "node": {"installed": True, "version": "v22"},
            "python": {"installed": True, "version": "3.14"},
        },
        "kubernetes": {
            "kubectl": {"installed": True, "version": "kubectl test"},
            "kube_config_exists": True,
            "active_context": "kind-aeis",
            "local_cluster_hint": True,
        },
        "ports": [
            {"port": 3000, "label": "next-dev", "busy": True, "latency_ms": 1},
            {"port": 8000, "label": "fastapi", "busy": True, "latency_ms": 1},
            {"port": 11434, "label": "ollama", "busy": True, "latency_ms": 1},
        ],
        "cloud_cli_tools": [
            {
                "provider": "aws",
                "command": "aws",
                "label": "AWS CLI",
                "installed": True,
                "path": "C:\\bin\\aws.exe",
                "version": "aws-cli/2",
                "config_present": True,
                "resource_listing_enabled": False,
            },
            {
                "provider": "hetzner",
                "command": "hcloud",
                "label": "Hetzner hcloud",
                "installed": True,
                "path": "C:\\bin\\hcloud.exe",
                "version": "hcloud 1",
                "config_present": True,
                "resource_listing_enabled": False,
            },
            {"provider": "gcp", "command": "gcloud", "label": "Google Cloud CLI", "installed": False},
        ],
        "privacy": {
            "cloud_resource_listing_enabled": False,
            "cloud_resource_listing_requires_explicit_consent": True,
            "ssh_hosts_redacted": True,
            "public_ip_detection_enabled": False,
        },
    }
    routes._set_state("last_local_scan", scan)
    return scan


def test_templates_cover_phase3_part1_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "env.db"))
    response = client.get(f"{BASE}/templates")

    assert response.status_code == 200
    data = response.json()
    assert data["cloud_provider_count"] >= 10
    providers = {item["provider"] for item in data["templates"]}
    assert {"aws", "gcp", "azure", "hetzner", "scaleway", "ionos", "custom_http"} <= providers
    assert len(data["sovereign_profiles"]) == 3
    assert len(data["edge"]["pairing_methods"]) == 5


def test_catalog_auto_scans_and_creates_local_dev(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "env.db"))
    monkeypatch.setattr(routes, "_scan_local_machine", _fake_scan)
    monkeypatch.setattr(routes, "_cloud_connectors", lambda: [])

    response = client.get(BASE)

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["local_dev_configured"] is True
    assert data["summary"]["active_environments"] == 1
    assert data["views"]["type"]["groups"]
    assert data["views"]["purpose"]["groups"]
    assert data["views"]["flat"]["rows"]
    assert data["acceptance"]["accepted"] is True
    local_dev = next(env for env in data["environments"] if env["environment_id"] == "env_local_dev")
    assert local_dev["policies"]["auto_cleanup"] is False
    assert local_dev["purpose"] == "development"


def test_detected_cli_providers_are_added_without_resource_listing(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "env.db"))
    monkeypatch.setattr(routes, "_scan_local_machine", _fake_scan)
    monkeypatch.setattr(routes, "_cloud_connectors", lambda: [])
    client.post(f"{BASE}/scan-local", json={"auto_create_local_dev": True})

    response = client.post(f"{BASE}/providers/detected", json={})

    assert response.status_code == 200
    data = response.json()
    providers = {item["provider"] for item in data["added"]}
    assert {"aws", "hetzner"} <= providers
    assert all(item["credential_status"] == "cli_detected" for item in data["added"])
    assert all(item["metadata"]["resource_listing_enabled"] is False for item in data["added"])


def test_accept_local_dev_marks_operator_acknowledgement(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "env.db"))
    monkeypatch.setattr(routes, "_scan_local_machine", _fake_scan)
    monkeypatch.setattr(routes, "_cloud_connectors", lambda: [])
    client.get(BASE)

    response = client.post(f"{BASE}/local-dev/accept", json={"notes": "accepted in test"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["environment"]["accepted_at"] is not None
    warning_ids = {item["id"] for item in data["acceptance"]["soft_warnings"]}
    assert "local_defaults_acknowledged" not in warning_ids


def test_edge_and_air_gap_workflows_persist_and_evaluate_sovereignty(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "env.db"))
    monkeypatch.setattr(routes, "_scan_local_machine", _fake_scan)
    monkeypatch.setattr(routes, "_cloud_connectors", lambda: [])
    client.get(BASE)

    edge_response = client.post(
        f"{BASE}/edge-devices",
        json={
            "display_name": "rpi-fabryka-1",
            "pairing_method": "ssh",
            "hostname": "192.168.50.10",
            "ssh_username": "pi",
            "device_type": "raspberry_pi_4",
            "location": "Warsaw",
            "owner": "atelier",
            "capabilities": ["linux", "ssh", "docker"],
        },
    )
    assert edge_response.status_code == 201
    assert edge_response.json()["environment"]["type"] == "edge"

    air_gap_response = client.post(
        f"{BASE}/environments",
        json={
            "name": "air-gap-customer-x",
            "environment_type": "air_gapped",
            "provider": "air_gapped",
            "purpose": "air_gapped",
            "tier": "critical",
            "region": "manual",
            "policies": {"auto_cleanup": False, "cleanup_after_days": None},
            "metadata": {"air_gapped": True, "sovereign": True},
        },
    )
    assert air_gap_response.status_code == 201
    env_id = air_gap_response.json()["environment"]["environment_id"]

    allowed = client.post(
        f"{BASE}/sovereignty/evaluate",
        json={"environment_id": env_id, "classification": "tlp_red"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["allowed"] is True

    blocked = client.post(
        f"{BASE}/sovereignty/evaluate",
        json={"environment_id": "env_local_dev", "classification": "tlp_red"},
    )
    assert blocked.status_code == 200
    assert blocked.json()["allowed"] is False


def test_full_phase3_network_cost_cleanup_and_acceptance(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "env.db"))
    monkeypatch.setattr(routes, "_scan_local_machine", _fake_scan)
    monkeypatch.setattr(routes, "_cloud_connectors", lambda: [])
    client.get(BASE)

    network = client.get(f"{BASE}/network")
    assert network.status_code == 200
    assert len(network.json()["topologies"]) == 4
    assert len(network.json()["mesh_providers"]) == 6

    policy_response = client.post(
        f"{BASE}/network/policy",
        json={
            "environment_id": "env_local_dev",
            "network_mode": "mesh",
            "vpn_mode": "tailscale",
            "mesh_provider": "tailscale",
            "firewall_template": "local_only",
            "sensitive": False,
        },
    )
    assert policy_response.status_code == 200
    assert policy_response.json()["policy"]["network_mode"] == "mesh"

    alert_response = client.post(
        f"{BASE}/costs/alerts",
        json={"environment_id": "env_local_dev", "monthly_budget_cap": 25, "thresholds": [50, 80, 100]},
    )
    assert alert_response.status_code == 200
    assert alert_response.json()["costs"]["monitoring"]["enabled"] is True
    assert {level["id"] for level in alert_response.json()["costs"]["levels"]} == {"provider", "environment", "resource"}

    cleanup_response = client.post(
        f"{BASE}/cleanup/policy",
        json={"environment_id": "env_local_dev", "strategy": "auto_after_hours", "cleanup_after_hours": 72, "action": "notify_then_stop"},
    )
    assert cleanup_response.status_code == 200
    assert cleanup_response.json()["policy"]["strategy"] == "auto_after_hours"

    acceptance = client.get(f"{BASE}/acceptance-test?goal=apps_internal")
    assert acceptance.status_code == 200
    data = acceptance.json()
    assert data["accepted"] is True
    assert data["audit_chain"]["phase_3_complete"] is True
    assert data["dod"]["common"]["passed"] == data["dod"]["common"]["required"]


def test_residency_checks_block_non_eu_and_record_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "env.db"))
    monkeypatch.setattr(routes, "_scan_local_machine", _fake_scan)
    monkeypatch.setattr(routes, "_cloud_connectors", lambda: [])
    client.get(BASE)
    create_response = client.post(
        f"{BASE}/environments",
        json={
            "name": "us-prod-test",
            "environment_type": "aws",
            "provider": "aws",
            "purpose": "production",
            "tier": "prod",
            "region": "us-east-1",
            "policies": {"auto_cleanup": False, "backup_strategy": "daily_snapshot"},
        },
    )
    assert create_response.status_code == 201
    env_id = create_response.json()["environment"]["environment_id"]

    blocked = client.post(
        f"{BASE}/residency/check",
        json={"project_id": "workspace-default", "environment_id": env_id, "data_classes": ["PII"], "allowed_regions": ["EU"]},
    )
    assert blocked.status_code == 200
    assert blocked.json()["decision"] == "block"
    assert blocked.json()["allowed"] is False

    override = client.post(
        f"{BASE}/residency/check",
        json={
            "project_id": "workspace-default",
            "environment_id": env_id,
            "data_classes": ["PII"],
            "allowed_regions": ["EU"],
            "override_code": "OVERRIDE_TEST_ONLY",
            "override_reason": "contract test",
        },
    )
    assert override.status_code == 200
    assert override.json()["decision"] == "operator_override_recorded"
    assert override.json()["allowed"] is True

    audit = client.get(f"{BASE}/residency/audit")
    assert audit.status_code == 200
    assert audit.json()["count"] >= 2


def test_edge_case_catalog_contains_phase3_runbooks(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_DB_PATH", str(tmp_path / "env.db"))
    monkeypatch.setattr(routes, "_scan_local_machine", _fake_scan)
    monkeypatch.setattr(routes, "_cloud_connectors", lambda: [])
    client.get(BASE)

    catalog = client.get(f"{BASE}/edge-cases")
    assert catalog.status_code == 200
    data = catalog.json()
    assert data["count"] == 30
    assert {"cloud_provider", "network", "edge_device", "customer_on_prem", "cost", "migration_dr"} <= set(data["categories"])

    diagnosis = client.post(f"{BASE}/edge-cases/diagnose", json={"case_id": "EC-B1", "environment_id": "env_local_dev"})
    assert diagnosis.status_code == 200
    assert diagnosis.json()["requires_human_gate"] is True
    assert "pause deployment" in diagnosis.json()["case"]["recommended_action"]

    inheritance = client.post(
        f"{BASE}/inheritance/resolve",
        json={"project_id": "workspace-default", "purpose": "production", "goal": "cybersecurity"},
    )
    assert inheritance.status_code == 200
    assert inheritance.json()["resolved"]["vpn_mode"] == "wireguard"
    assert inheritance.json()["levels"][-1]["phase"] == 33
