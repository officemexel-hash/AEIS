"""
SYLION Infra -- Topology Templates

Generates Terraform HCL and Ansible playbooks for AEIS distributed topologies:
  - 5_server (minimal)
  - 8_server (recommended)
  - 10_server (full)

All templates are provider-agnostic stubs (Hetzner/DigitalOcean/AWS ready).
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path
from typing import Any


def _server_block(name: str, role: str, components: list[str], min_vcpus: int, min_ram_gb: int) -> dict[str, Any]:
    return {
        "name": name,
        "role": role,
        "components": components,
        "min_vcpus": min_vcpus,
        "min_ram_gb": min_ram_gb,
    }


def _resolve_repo_url() -> str:
    """Resolve the deployment repository source without hard-coded placeholders."""
    for key in ("SYLION_DEPLOY_REPO_URL", "SYLION_REPO_URL", "SYLION_GIT_REPO_URL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value

    repo_root = Path(__file__).resolve().parents[4]
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"],
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


TOPOLOGIES: dict[str, list[dict[str, Any]]] = {
    "5_server": [
        _server_block("sylion-cp", "control_plane", ["canon", "planning", "coordination", "governance"], 2, 4),
        _server_block("sylion-wa", "worker_a", ["core", "registry", "contracts"], 2, 4),
        _server_block("sylion-wb", "worker_b", ["cognitive", "memory"], 2, 4),
        _server_block("sylion-wc", "worker_c", ["execution", "skills", "connectors"], 2, 4),
        _server_block("sylion-wd", "worker_d_integration", ["security", "monitoring", "ui", "integration_tests"], 2, 4),
    ],
    "8_server": [
        _server_block("sylion-canon", "canon_planning", ["canon_manager", "decomposition_engine"], 2, 4),
        _server_block("sylion-coord", "coordination_governance", ["assignment_orchestrator", "governance_engine"], 2, 4),
        _server_block("sylion-data", "data_backbone", ["postgres", "nats", "minio", "vault"], 2, 8),
        _server_block("sylion-wa", "worker_a", ["core", "contracts", "registry"], 2, 4),
        _server_block("sylion-wb", "worker_b", ["cognitive", "memory"], 2, 4),
        _server_block("sylion-wc", "worker_c", ["execution", "skills", "connectors"], 2, 4),
        _server_block("sylion-wd", "worker_d", ["security", "monitoring", "audit"], 2, 4),
        _server_block("sylion-int", "integration_dashboard", ["integration_orchestrator", "dashboard_pro"], 2, 4),
    ],
    "10_server": [
        _server_block("sylion-canon", "canon_layer", ["canon_manager"], 2, 4),
        _server_block("sylion-plan", "planning_layer", ["decomposition_engine"], 2, 4),
        _server_block("sylion-coord", "coordination_layer", ["assignment_orchestrator"], 2, 4),
        _server_block("sylion-gov", "governance_layer", ["governance_engine"], 2, 4),
        _server_block("sylion-data", "data_backbone", ["postgres", "nats", "minio", "vault"], 2, 8),
        _server_block("sylion-wa", "worker_a", ["core", "contracts"], 2, 4),
        _server_block("sylion-wb", "worker_b", ["cognitive", "memory", "self_model"], 2, 4),
        _server_block("sylion-wc", "worker_c", ["execution", "connectors", "skills"], 2, 4),
        _server_block("sylion-wd", "worker_d", ["security", "observability", "audit"], 2, 4),
        _server_block("sylion-we", "worker_e", ["dashboard", "ui", "operator_console"], 2, 4),
    ],
}


def generate_terraform(variant: str, output_dir: Path) -> Path:
    """Generate Terraform main.tf for the given topology variant."""
    servers = TOPOLOGIES.get(variant, TOPOLOGIES["8_server"])
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    resources: list[str] = []
    for srv in servers:
        name = srv["name"]
        resources.append(textwrap.dedent(f"""
            resource "hcloud_server" "{name}" {{
              name        = "{name}"
              server_type = "cx21"  # 2 vCPU, 4 GB RAM (adjust as needed)
              image       = "ubuntu-22.04"
              location    = "nbg1"
              labels = {{
                role = "{srv['role']}"
                topology = "{variant}"
              }}
            }}
        """))

    content = textwrap.dedent(f"""\
        # SYLION AEIS -- {variant} Topology
        # Generated automatically. Adjust provider and server_type to your infrastructure.

        terraform {{
          required_providers {{
            hcloud = {{
              source  = "hetznercloud/hcloud"
              version = "~> 1.45"
            }}
          }}
        }}

        variable "hcloud_token" {{
          description = "Hetzner Cloud API token"
          sensitive   = true
        }}

        provider "hcloud" {{
          token = var.hcloud_token
        }}

        {''.join(resources)}

        output "server_ips" {{
          value = {{{
        {chr(10).join([f'            {s["name"]} = hcloud_server.{s["name"]}.ipv4_address' for s in servers])}
          }}}
        }}
    """)

    tf_path = output_dir / "main.tf"
    tf_path.write_text(content, encoding="utf-8")
    return tf_path


def generate_ansible(variant: str, output_dir: Path) -> tuple[Path, Path]:
    """Generate Ansible inventory.ini and playbook.yml."""
    servers = TOPOLOGIES.get(variant, TOPOLOGIES["8_server"])
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    repo_url = _resolve_repo_url()

    # Inventory
    inventory_lines = [
        f"[{variant}]",
        "# Resolve these hostnames in DNS or replace ansible_host values after provisioning.",
    ]
    for srv in servers:
        inventory_lines.append(
            f"{srv['name']} ansible_host={srv['name']} ansible_user=root role={srv['role']}"
        )

    inventory_lines += [
        "",
        f"[{variant}:vars]",
        "ansible_python_interpreter=/usr/bin/python3",
        f"topology_variant={variant}",
    ]
    inv_path = output_dir / "inventory.ini"
    inv_path.write_text("\n".join(inventory_lines), encoding="utf-8")

    # Playbook
    playbook = textwrap.dedent(f"""\
        ---
        - name: Deploy SYLION AEIS {variant} topology
          hosts: {variant}
          become: yes
          vars:
            sylion_version: "3.5.0"
            sylion_repo: "{repo_url or "{{{{ lookup('env', 'SYLION_DEPLOY_REPO_URL') | default('', true) }}}}"}"
            sylion_dir: "/opt/sylion"
          tasks:
            - name: Require a deployment repository source
              assert:
                that:
                  - sylion_repo | length > 0
                fail_msg: >-
                  Set SYLION_DEPLOY_REPO_URL or configure git remote.origin.url
                  before running this topology playbook.

            - name: Update apt cache
              apt:
                update_cache: yes
              when: ansible_os_family == 'Debian'

            - name: Install dependencies
              apt:
                name:
                  - git
                  - python3
                  - python3-venv
                  - python3-pip
                  - postgresql-client
                state: present
              when: ansible_os_family == 'Debian'

            - name: Clone SYLION repo
              git:
                repo: "{{{{ sylion_repo }}}}"
                dest: "{{{{ sylion_dir }}}}"
                version: "{{{{ sylion_version }}}}"
                force: yes

            - name: Install Python dependencies
              pip:
                requirements: "{{{{ sylion_dir }}}}/requirements.txt"
                virtualenv: "{{{{ sylion_dir }}}}/.venv"
                virtualenv_command: python3 -m venv

            - name: Run install script
              shell: |
                cd {{{{ sylion_dir }}}} && .venv\\/bin\\/python scripts\\/install.sh
              args:
                creates: "{{{{ sylion_dir }}}}\\/.env.generated"

            - name: Start backend service
              shell: |
                cd {{{{ sylion_dir }}}} && .venv\\/bin\\/uvicorn sylion.api.app:app --host 0.0.0.0 --port 8000 &
              async: 10
              poll: 0
    """)
    pb_path = output_dir / "playbook.yml"
    pb_path.write_text(playbook, encoding="utf-8")
    return inv_path, pb_path


def generate_all(variant: str, output_dir: str | Path) -> dict[str, Path]:
    """Generate both Terraform and Ansible files."""
    output_dir = Path(output_dir) / variant
    output_dir.mkdir(parents=True, exist_ok=True)
    tf = generate_terraform(variant, output_dir / "terraform")
    inv, pb = generate_ansible(variant, output_dir / "ansible")
    return {
        "terraform": tf,
        "inventory": inv,
        "playbook": pb,
    }
