"""
SYLION API -- Deploy routes (Phase 4/5)

Endpoints for topology template generation and deployment helpers.
"""

import base64
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sylion.api.deploy_service import build_deploy_summary
from sylion.infra.topology_templates import generate_all, TOPOLOGIES
from sylion.project_mode import get_project_mode_store

router = APIRouter(prefix="/api/v1")

DEPRECATED_HETZNER_SERVER_TYPES = {
    "cx22": "cx23",
    "cx32": "cx33",
    "cx42": "cx43",
    "cx52": "cx53",
}


class HetznerProvisionRequest(BaseModel):
    project_id: str
    connector_id: str
    server_name: str = ""
    server_type: str = "cx23"
    location: str = "fsn1"
    image: str = "ubuntu-24.04"
    environment_count: int = Field(default=1, ge=1, le=10)
    vps_per_environment: int = Field(default=1, ge=1, le=10)
    confirm_financial_action: bool = False
    wait_for_health: bool = True


class HetznerDeleteRequest(BaseModel):
    confirm_delete: bool = False


def _deploy_db_path() -> Path:
    return Path(os.environ.get("SYLION_DB_PATH", "sylion_aeis.db"))


def _deploy_conn() -> sqlite3.Connection:
    path = _deploy_db_path()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hetzner_project_deployments (
            deployment_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            connector_id TEXT NOT NULL,
            provider_server_id TEXT NOT NULL DEFAULT '',
            server_name TEXT NOT NULL,
            server_type TEXT NOT NULL,
            location TEXT NOT NULL,
            image TEXT NOT NULL,
            status TEXT NOT NULL,
            public_ipv4 TEXT NOT NULL DEFAULT '',
            health_url TEXT NOT NULL DEFAULT '',
            artifact_sha256 TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            raw_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    try:
        data["raw"] = json.loads(data.pop("raw_json") or "{}")
    except Exception:
        data["raw"] = {}
    return data


def _record_hetzner_deployment(payload: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    payload.setdefault("created_at", now)
    payload["updated_at"] = now
    payload.setdefault("raw", {})
    raw_json = json.dumps(payload.pop("raw"), ensure_ascii=False, default=str)
    with _deploy_conn() as conn:
        conn.execute(
            """
            INSERT INTO hetzner_project_deployments (
                deployment_id, project_id, connector_id, provider_server_id,
                server_name, server_type, location, image, status, public_ipv4,
                health_url, artifact_sha256, created_at, updated_at, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(deployment_id) DO UPDATE SET
                provider_server_id=excluded.provider_server_id,
                status=excluded.status,
                public_ipv4=excluded.public_ipv4,
                health_url=excluded.health_url,
                updated_at=excluded.updated_at,
                raw_json=excluded.raw_json
            """,
            (
                payload["deployment_id"],
                payload["project_id"],
                payload["connector_id"],
                payload.get("provider_server_id", ""),
                payload["server_name"],
                payload["server_type"],
                payload["location"],
                payload["image"],
                payload["status"],
                payload.get("public_ipv4", ""),
                payload.get("health_url", ""),
                payload.get("artifact_sha256", ""),
                payload["created_at"],
                payload["updated_at"],
                raw_json,
            ),
        )
    return {**payload, "raw": json.loads(raw_json)}


def _list_hetzner_deployments(project_id: str | None = None) -> list[dict[str, Any]]:
    with _deploy_conn() as conn:
        if project_id:
            rows = conn.execute(
                "SELECT * FROM hetzner_project_deployments WHERE project_id = ? ORDER BY updated_at DESC",
                (project_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM hetzner_project_deployments ORDER BY updated_at DESC").fetchall()
    return [_row_to_dict(row) for row in rows]


def _get_hetzner_deployment(deployment_id: str) -> dict[str, Any]:
    with _deploy_conn() as conn:
        row = conn.execute(
            "SELECT * FROM hetzner_project_deployments WHERE deployment_id = ?",
            (deployment_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Hetzner deployment {deployment_id} not found")
    return _row_to_dict(row)


def _hetzner_token(connector_id: str) -> tuple[str, dict[str, Any]]:
    from sylion.security.cloud_connectors import get_cloud_connector_store

    store = get_cloud_connector_store()
    record = store.get(connector_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Connector {connector_id} not found")
    if str(record.get("provider") or "").lower() != "hetzner":
        raise HTTPException(status_code=400, detail="Selected connector is not a Hetzner connector")
    credentials = store.get_decrypted_credentials(connector_id) or {}
    token = str(credentials.get("token") or credentials.get("api_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Hetzner connector has no API token")
    return token, record


def _load_deployable_artifact(project_id: str) -> tuple[dict[str, Any], str, str]:
    project = get_project_mode_store().get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    launch = project.get("launch") if isinstance(project.get("launch"), dict) else {}
    artifact_path = Path(str(launch.get("artifact_path") or ""))
    if not artifact_path.is_file():
        raise HTTPException(status_code=400, detail="Project has no recorded artifact file")
    validation = launch.get("validation") if isinstance(launch.get("validation"), dict) else {}
    if not bool(validation.get("success")):
        raise HTTPException(status_code=400, detail="Project validation has not passed")
    content = artifact_path.read_text(encoding="utf-8")
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return project, content, sha


def _cloud_init_for_artifact(project_id: str, content: str) -> str:
    artifact_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    health = f"aeis-deploy-ok project_id={project_id}"
    health_b64 = base64.b64encode(health.encode("utf-8")).decode("ascii")
    return "\n".join(
        [
            "#cloud-config",
            "package_update: true",
            "packages:",
            "  - nginx",
            "write_files:",
            "  - path: /var/www/html/index.html",
            "    encoding: b64",
            f"    content: {artifact_b64}",
            "  - path: /var/www/html/healthz",
            "    encoding: b64",
            f"    content: {health_b64}",
            "runcmd:",
            "  - systemctl enable --now nginx",
            "  - systemctl restart nginx",
        ]
    )


def _hcloud_request(method: str, path: str, token: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    import httpx

    with httpx.Client(timeout=30.0) as client:
        response = client.request(
            method,
            f"https://api.hetzner.cloud/v1{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Hetzner API HTTP {response.status_code}: {response.text[:200]}")
    return response.json() if response.content else {}


def _validate_hetzner_server_type(server_type: str) -> str:
    normalized = str(server_type or "").strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Hetzner server_type is required")
    replacement = DEPRECATED_HETZNER_SERVER_TYPES.get(normalized)
    if replacement:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Hetzner server_type {normalized} is deprecated for new orders. "
                f"Use {replacement} or another currently orderable type."
            ),
        )
    return normalized


def _validate_hetzner_scale(body: HetznerProvisionRequest) -> tuple[int, int, int]:
    environment_count = int(body.environment_count or 1)
    vps_per_environment = int(body.vps_per_environment or 1)
    total_servers = environment_count * vps_per_environment
    if total_servers > 10:
        raise HTTPException(
            status_code=409,
            detail=(
                "Hetzner scale is capped at 10 VPS per provisioning request. "
                "Lower environment_count or vps_per_environment, or split the deployment into batches."
            ),
        )
    return environment_count, vps_per_environment, total_servers


def _safe_hcloud_name(raw: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in raw.strip().lower())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return (cleaned or "aeis-deploy")[:63]


def _scaled_server_name(base: str, environment_index: int, server_index: int, total_servers: int) -> str:
    if total_servers <= 1:
        return _safe_hcloud_name(base)
    suffix = f"e{environment_index:02d}-vps{server_index:02d}"
    head = _safe_hcloud_name(base)[: max(1, 63 - len(suffix) - 1)]
    return _safe_hcloud_name(f"{head}-{suffix}")


def _server_ipv4(server: dict[str, Any]) -> str:
    public_net = server.get("public_net") if isinstance(server.get("public_net"), dict) else {}
    ipv4 = public_net.get("ipv4") if isinstance(public_net.get("ipv4"), dict) else {}
    return str(ipv4.get("ip") or "")


def _wait_for_server_running(server_id: int, token: str, timeout_s: int = 180) -> tuple[dict[str, Any], str]:
    deadline = time.time() + timeout_s
    last_server: dict[str, Any] = {}
    while time.time() < deadline:
        body = _hcloud_request("GET", f"/servers/{server_id}", token)
        last_server = body.get("server") or {}
        ip = _server_ipv4(last_server)
        if last_server.get("status") == "running" and ip:
            return last_server, ip
        time.sleep(5)
    return last_server, _server_ipv4(last_server)


def _probe_http_health(ipv4: str, project_id: str) -> dict[str, Any]:
    import httpx

    checked_at = time.time()
    marker = f"project_id={project_id}"
    if not ipv4:
        return {
            "ok": False,
            "url": "",
            "status_code": None,
            "body_excerpt": "",
            "error": "missing_public_ipv4",
            "expected_marker": marker,
            "checked_at": checked_at,
        }
    url = f"http://{ipv4}/healthz"
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(url)
        body_excerpt = response.text[:500]
        ok = response.status_code == 200 and marker in response.text
        error = ""
        if response.status_code != 200:
            error = f"unexpected_http_status:{response.status_code}"
        elif marker not in response.text:
            error = "expected_project_marker_missing"
        return {
            "ok": ok,
            "url": url,
            "status_code": response.status_code,
            "body_excerpt": body_excerpt,
            "error": error,
            "expected_marker": marker,
            "checked_at": checked_at,
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "status_code": None,
            "body_excerpt": "",
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            "expected_marker": marker,
            "checked_at": checked_at,
        }


def _wait_for_http_health(ipv4: str, project_id: str, timeout_s: int = 180) -> tuple[bool, str, dict[str, Any]]:
    if not ipv4:
        probe = _probe_http_health(ipv4, project_id)
        return False, "", probe
    url = f"http://{ipv4}/healthz"
    deadline = time.time() + timeout_s
    last_probe: dict[str, Any] = {"ok": False, "url": url, "status_code": None, "body_excerpt": "", "error": "not_checked"}
    while time.time() < deadline:
        last_probe = _probe_http_health(ipv4, project_id)
        if bool(last_probe.get("ok")):
            return True, url, last_probe
        time.sleep(8)
    return False, url, last_probe


@router.get("/deploy/summary")
def get_deploy_summary():
    """Return real deployable project artifacts and active deployment queue."""
    return build_deploy_summary()


@router.get("/deploy/topologies")
def list_topologies():
    """List available topology variants."""
    return {
        "variants": [
            {
                "variant": variant,
                "server_count": len(servers),
                "servers": [
                    {"name": s["name"], "role": s["role"], "components": s["components"]}
                    for s in servers
                ],
            }
            for variant, servers in TOPOLOGIES.items()
        ]
    }


@router.post("/deploy/topologies/{variant}")
def generate_topology_files(variant: str):
    """Generate Terraform and Ansible files for a topology variant.

    Returns file contents inline (suitable for download or review).
    """
    if variant not in TOPOLOGIES:
        raise HTTPException(status_code=404, detail=f"Unknown topology variant: {variant}")

    with TemporaryDirectory() as tmpdir:
        result = generate_all(variant, tmpdir)
        return {
            "variant": variant,
            "files": {
                "terraform_main_tf": Path(result["terraform"]).read_text(),
                "ansible_inventory_ini": Path(result["inventory"]).read_text(),
                "ansible_playbook_yml": Path(result["playbook"]).read_text(),
            },
        }


@router.get("/deploy/hetzner/deployments")
def list_hetzner_deployments(project_id: str | None = None):
    """List real Hetzner deployment attempts tracked by AEIS."""
    return {"deployments": _list_hetzner_deployments(project_id=project_id)}


@router.post("/deploy/hetzner/provision", status_code=201)
def provision_hetzner_project(body: HetznerProvisionRequest):
    """Create a Hetzner Cloud VPS and publish the generated artifact via nginx.

    This is intentionally not a template generator. It performs the external
    financial action only when the dashboard sends `confirm_financial_action`.
    """
    if not body.confirm_financial_action:
        raise HTTPException(
            status_code=409,
            detail="Creating a Hetzner VPS is a financial external action and requires explicit operator confirmation.",
        )
    server_type = _validate_hetzner_server_type(body.server_type)
    environment_count, vps_per_environment, total_servers = _validate_hetzner_scale(body)
    token, _record = _hetzner_token(body.connector_id)
    project, artifact_content, artifact_sha = _load_deployable_artifact(body.project_id)
    safe_project = _safe_hcloud_name(body.project_id)[:32]
    timestamp = int(time.time())
    base_server_name = body.server_name or f"aeis-{safe_project}-{timestamp}"
    deployment_group_id = f"hcloud_{body.project_id}_{timestamp}"
    deployments: list[dict[str, Any]] = []
    created_server_ids: list[int] = []

    try:
        for environment_index in range(1, environment_count + 1):
            environment_name = f"env-{environment_index:02d}"
            for server_index in range(1, vps_per_environment + 1):
                deployment_id = f"{deployment_group_id}_e{environment_index:02d}_v{server_index:02d}"
                server_name = _scaled_server_name(base_server_name, environment_index, server_index, total_servers)
                create_payload = {
                    "name": server_name,
                    "server_type": server_type,
                    "image": body.image,
                    "location": body.location,
                    "start_after_create": True,
                    "user_data": _cloud_init_for_artifact(body.project_id, artifact_content),
                    "labels": {
                        "aeis_project_id": body.project_id[:63],
                        "aeis_deployment_id": deployment_id[:63],
                        "aeis_deployment_group": deployment_group_id[:63],
                        "aeis_environment": environment_name[:63],
                        "aeis_server_index": str(server_index),
                        "aeis_audit": "true",
                    },
                }
                created = _hcloud_request("POST", "/servers", token, payload=create_payload)
                server = created.get("server") or {}
                server_id = int(server.get("id") or 0)
                if server_id <= 0:
                    raise HTTPException(status_code=502, detail="Hetzner API did not return a server id")
                created_server_ids.append(server_id)
                deployment = _record_hetzner_deployment(
                    {
                        "deployment_id": deployment_id,
                        "project_id": body.project_id,
                        "connector_id": body.connector_id,
                        "provider_server_id": str(server_id),
                        "server_name": server_name,
                        "server_type": server_type,
                        "location": body.location,
                        "image": body.image,
                        "status": "created",
                        "artifact_sha256": artifact_sha,
                        "raw": {
                            "project_title": project.get("title", ""),
                            "hetzner_action_id": (created.get("action") or {}).get("id"),
                            "server_status": server.get("status"),
                            "deployment_group_id": deployment_group_id,
                            "environment_name": environment_name,
                            "environment_index": environment_index,
                            "server_index": server_index,
                            "environment_count": environment_count,
                            "vps_per_environment": vps_per_environment,
                            "total_servers": total_servers,
                        },
                    }
                )
                ipv4 = _server_ipv4(server)
                if body.wait_for_health:
                    running_server, ipv4 = _wait_for_server_running(server_id, token)
                    health_ok, health_url, health_probe = _wait_for_http_health(ipv4, body.project_id)
                    deployment = _record_hetzner_deployment(
                        {
                            **deployment,
                            "status": "healthy" if health_ok else "health_timeout",
                            "public_ipv4": ipv4,
                            "health_url": health_url,
                            "raw": {
                                **(deployment.get("raw") or {}),
                                "server_status": running_server.get("status"),
                                "health_ok": health_ok,
                                "health_probe": health_probe,
                                "public_ipv4": ipv4,
                                "artifact_sha256": artifact_sha,
                            },
                        }
                    )
                deployments.append(deployment)
    except Exception:
        for server_id in created_server_ids:
            try:
                _hcloud_request("DELETE", f"/servers/{server_id}", token)
            except Exception:
                pass
        raise

    primary = deployments[0] if deployments else {}
    return {
        "deployment": primary,
        "deployments": deployments,
        "deployment_group": {
            "deployment_group_id": deployment_group_id,
            "environment_count": environment_count,
            "vps_per_environment": vps_per_environment,
            "total_servers": total_servers,
        },
        "public_probe": (primary.get("raw") or {}).get("health_probe") if primary else None,
    }


@router.post("/deploy/hetzner/{deployment_id}/health")
def check_hetzner_deployment_health(deployment_id: str):
    deployment = _get_hetzner_deployment(deployment_id)
    ok, health_url, health_probe = _wait_for_http_health(
        str(deployment.get("public_ipv4") or ""),
        str(deployment.get("project_id") or ""),
        timeout_s=30,
    )
    deployment = _record_hetzner_deployment(
        {
            **deployment,
            "status": "healthy" if ok else "health_failed",
            "health_url": health_url,
            "raw": {**(deployment.get("raw") or {}), "health_ok": ok, "health_probe": health_probe},
        }
    )
    return {"ok": ok, "health_url": health_url, "public_probe": health_probe, "deployment": deployment}


@router.post("/deploy/hetzner/{deployment_id}/delete")
def delete_hetzner_deployment(deployment_id: str, body: HetznerDeleteRequest):
    """Delete the tracked Hetzner server. Cloud deletion is also gated."""
    if not body.confirm_delete:
        raise HTTPException(
            status_code=409,
            detail="Deleting a Hetzner VPS is irreversible for that cloud resource and requires explicit operator confirmation.",
        )
    deployment = _get_hetzner_deployment(deployment_id)
    token, _record = _hetzner_token(str(deployment.get("connector_id") or ""))
    server_id = str(deployment.get("provider_server_id") or "").strip()
    if not server_id:
        raise HTTPException(status_code=400, detail="Deployment has no Hetzner server id")
    _hcloud_request("DELETE", f"/servers/{server_id}", token)
    deployment = _record_hetzner_deployment(
        {
            **deployment,
            "status": "delete_requested",
            "raw": {**(deployment.get("raw") or {}), "delete_requested_at": time.time()},
        }
    )
    return {"deleted": True, "deployment": deployment}
