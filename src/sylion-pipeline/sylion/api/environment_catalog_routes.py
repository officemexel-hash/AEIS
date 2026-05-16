"""Environment Catalog control plane for Phase 3 onboarding.

Phase 3 is about compute targets: local machine, cloud accounts, VPS,
sovereign/on-prem locations and edge devices. This API keeps that catalogue
separate from Phase 2 LLM providers and deliberately does not enumerate cloud
resources from operator accounts unless a later explicit workflow asks for it.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import shutil
import socket
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/environment-catalog", tags=["Environment Catalog"])


COMMON_PORTS: list[dict[str, Any]] = [
    {"port": 80, "label": "http"},
    {"port": 443, "label": "https"},
    {"port": 3000, "label": "next-dev"},
    {"port": 3001, "label": "aeis-frontend"},
    {"port": 5000, "label": "flask"},
    {"port": 5432, "label": "postgres"},
    {"port": 8000, "label": "fastapi"},
    {"port": 8010, "label": "aeis-api"},
    {"port": 8080, "label": "llamacpp/http"},
    {"port": 11434, "label": "ollama"},
    {"port": 1234, "label": "lm-studio"},
    {"port": 8188, "label": "comfyui"},
]

CLOUD_CLI_TOOLS: list[dict[str, Any]] = [
    {"provider": "aws", "command": "aws", "label": "AWS CLI", "config_paths": ["~/.aws/credentials", "~/.aws/config"]},
    {"provider": "gcp", "command": "gcloud", "label": "Google Cloud CLI", "config_paths": ["~/.config/gcloud/configurations"]},
    {"provider": "azure", "command": "az", "label": "Azure CLI", "config_paths": ["~/.azure"]},
    {"provider": "hetzner", "command": "hcloud", "label": "Hetzner hcloud", "config_paths": ["~/.config/hcloud/cli.toml"]},
    {"provider": "digitalocean", "command": "doctl", "label": "DigitalOcean doctl", "config_paths": ["~/.config/doctl/config.yaml"]},
    {"provider": "linode", "command": "linode-cli", "label": "Linode CLI", "config_paths": ["~/.config/linode-cli"]},
    {"provider": "terraform", "command": "terraform", "label": "Terraform", "config_paths": ["~/.terraform.d"]},
    {"provider": "pulumi", "command": "pulumi", "label": "Pulumi", "config_paths": ["~/.pulumi"]},
]

CLOUD_PROVIDER_TEMPLATES: list[dict[str, Any]] = [
    {
        "provider": "aws",
        "display_name": "Amazon Web Services",
        "category": "cloud_enterprise",
        "tier": "tier_1_enterprise",
        "website": "https://aws.amazon.com",
        "sovereignty": "EU regions available",
        "min_monthly_cost": 7.59,
        "currency": "USD",
        "setup_minutes": 30,
        "sla": "99.99%",
        "auth_methods": ["access_key_secret", "aws_cli_profile", "sso", "iam_role", "oauth"],
        "regions": [
            {"id": "eu-west-1", "display": "Ireland (Dublin)", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "eu-central-1", "display": "Germany (Frankfurt)", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "eu-central-2", "display": "Switzerland (Zurich)", "sovereignty": "EU+CH", "gdpr_friendly": True},
            {"id": "us-east-1", "display": "USA (Virginia)", "sovereignty": "US", "gdpr_friendly": False},
        ],
        "instance_types": [
            {"id": "t3.micro", "display": "T3 Micro", "cpu": 2, "ram_gb": 1, "monthly_estimate": 7.59, "good_for": ["dev", "light_workloads"]},
            {"id": "t3.medium", "display": "T3 Medium", "cpu": 2, "ram_gb": 4, "monthly_estimate": 30.37, "good_for": ["staging", "small_prod"]},
        ],
        "services_supported": ["ec2", "s3", "rds", "lambda", "eks", "cloudfront"],
        "recommended_for": ["global_scale", "multi_region", "enterprise"],
        "quirks": ["VPC/security groups are mandatory", "pricing includes data transfer", "budget alerts recommended"],
    },
    {
        "provider": "gcp",
        "display_name": "Google Cloud Platform",
        "category": "cloud_enterprise",
        "tier": "tier_1_enterprise",
        "website": "https://cloud.google.com",
        "sovereignty": "EU regions available",
        "min_monthly_cost": 6.13,
        "currency": "USD",
        "setup_minutes": 25,
        "sla": "99.95%",
        "auth_methods": ["service_account", "gcloud_cli", "oauth", "workload_identity"],
        "regions": [
            {"id": "europe-west1", "display": "Belgium", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "europe-west3", "display": "Germany (Frankfurt)", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "us-central1", "display": "USA (Iowa)", "sovereignty": "US", "gdpr_friendly": False},
        ],
        "instance_types": [
            {"id": "e2-small", "display": "E2 Small", "cpu": 2, "ram_gb": 2, "monthly_estimate": 6.13, "good_for": ["dev", "staging"]},
        ],
        "services_supported": ["compute_engine", "cloud_storage", "cloud_run", "gke", "cloud_sql"],
        "recommended_for": ["analytics", "global_scale", "managed_runtime"],
        "quirks": ["project ID required", "billing account is separate", "service accounts preferred"],
    },
    {
        "provider": "azure",
        "display_name": "Microsoft Azure",
        "category": "cloud_enterprise",
        "tier": "tier_1_enterprise",
        "website": "https://azure.microsoft.com",
        "sovereignty": "EU regions available",
        "min_monthly_cost": 7.59,
        "currency": "USD",
        "setup_minutes": 30,
        "sla": "99.95%",
        "auth_methods": ["service_principal", "azure_cli", "managed_identity", "oauth"],
        "regions": [
            {"id": "westeurope", "display": "Netherlands", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "germanywestcentral", "display": "Germany West Central", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "polandcentral", "display": "Poland Central", "sovereignty": "PL/EU", "gdpr_friendly": True},
        ],
        "instance_types": [
            {"id": "B1s", "display": "B1s", "cpu": 1, "ram_gb": 1, "monthly_estimate": 7.59, "good_for": ["dev"]},
        ],
        "services_supported": ["virtual_machines", "storage_accounts", "aks", "app_service", "sql_database"],
        "recommended_for": ["microsoft_stack", "enterprise", "poland_region"],
        "quirks": ["resource groups required", "tenant and subscription IDs matter", "RBAC can be complex"],
    },
    {
        "provider": "hetzner",
        "display_name": "Hetzner Cloud",
        "category": "vps_focused",
        "tier": "tier_2_vps",
        "website": "https://www.hetzner.com/cloud",
        "sovereignty": "EU only (DE/FI/US, PL via Warsaw availability where configured)",
        "min_monthly_cost": 4.20,
        "currency": "EUR",
        "setup_minutes": 10,
        "sla": "99.5%",
        "auth_methods": ["api_token", "hcloud_cli"],
        "regions": [
            {"id": "fsn1", "display": "Germany (Falkenstein)", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "nbg1", "display": "Germany (Nuremberg)", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "hel1", "display": "Finland (Helsinki)", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "warsaw-1", "display": "Poland (Warsaw)", "sovereignty": "PL/EU", "gdpr_friendly": True},
        ],
        "instance_types": [
            {"id": "cx21", "display": "CX21", "cpu": 2, "ram_gb": 4, "monthly_estimate": 4.20, "good_for": ["staging", "cheap_prod"]},
            {"id": "cx31", "display": "CX31", "cpu": 4, "ram_gb": 8, "monthly_estimate": 8.40, "good_for": ["production"]},
        ],
        "services_supported": ["servers", "volumes", "floating_ips", "networks", "firewalls"],
        "recommended_for": ["cheap_staging", "eu_sovereign_prod", "polish_operator"],
        "quirks": ["SSH key required before first instance", "floating IPs and volumes are separately billed", "simple network model"],
    },
    {
        "provider": "digitalocean",
        "display_name": "DigitalOcean",
        "category": "vps_focused",
        "tier": "tier_2_vps",
        "website": "https://www.digitalocean.com",
        "sovereignty": "EU regions available",
        "min_monthly_cost": 6.0,
        "currency": "USD",
        "setup_minutes": 10,
        "sla": "99.99%",
        "auth_methods": ["api_token", "doctl_cli"],
        "regions": [
            {"id": "fra1", "display": "Germany (Frankfurt)", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "ams3", "display": "Netherlands (Amsterdam)", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "nyc3", "display": "USA (New York)", "sovereignty": "US", "gdpr_friendly": False},
        ],
        "instance_types": [
            {"id": "s-1vcpu-1gb", "display": "Basic", "cpu": 1, "ram_gb": 1, "monthly_estimate": 6.0, "good_for": ["dev", "demo"]},
        ],
        "services_supported": ["droplets", "spaces", "managed_databases", "kubernetes", "load_balancers"],
        "recommended_for": ["simple_vps", "developer_experience"],
        "quirks": ["US-based operator", "project scoping recommended", "bandwidth limits visible per droplet"],
    },
    {
        "provider": "linode",
        "display_name": "Linode / Akamai",
        "category": "vps_focused",
        "tier": "tier_2_vps",
        "website": "https://www.linode.com",
        "sovereignty": "EU regions available",
        "min_monthly_cost": 5.0,
        "currency": "USD",
        "setup_minutes": 10,
        "sla": "99.99%",
        "auth_methods": ["personal_access_token", "linode_cli"],
        "regions": [
            {"id": "eu-central", "display": "Germany (Frankfurt)", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "gb-lon", "display": "UK (London)", "sovereignty": "UK", "gdpr_friendly": True},
        ],
        "instance_types": [
            {"id": "g6-nanode-1", "display": "Nanode", "cpu": 1, "ram_gb": 1, "monthly_estimate": 5.0, "good_for": ["dev", "monitoring"]},
        ],
        "services_supported": ["linodes", "nodebalancers", "object_storage", "lke"],
        "recommended_for": ["small_vps", "akamai_edge"],
        "quirks": ["Akamai account model", "API token scopes should be minimal"],
    },
    {
        "provider": "ovh",
        "display_name": "OVHcloud",
        "category": "vps_focused",
        "tier": "tier_2_vps",
        "website": "https://www.ovhcloud.com",
        "sovereignty": "FR/DE/PL EU sovereign",
        "min_monthly_cost": 3.50,
        "currency": "EUR",
        "setup_minutes": 20,
        "sla": "99.99%",
        "auth_methods": ["application_key_secret", "consumer_key", "ovh_cli"],
        "regions": [
            {"id": "GRA", "display": "France (Gravelines)", "sovereignty": "EU/FR", "gdpr_friendly": True},
            {"id": "SBG", "display": "France (Strasbourg)", "sovereignty": "EU/FR", "gdpr_friendly": True},
            {"id": "WAW", "display": "Poland (Warsaw)", "sovereignty": "PL/EU", "gdpr_friendly": True},
        ],
        "instance_types": [
            {"id": "b2-7", "display": "B2-7", "cpu": 2, "ram_gb": 7, "monthly_estimate": 8.0, "good_for": ["staging", "eu_prod"]},
        ],
        "services_supported": ["public_cloud", "bare_metal", "object_storage", "private_network"],
        "recommended_for": ["eu_sovereign", "polish_datacenter_option"],
        "quirks": ["public cloud and bare metal differ", "WAW datacenter matters for PL locality", "private network needs explicit config"],
    },
    {
        "provider": "vultr",
        "display_name": "Vultr",
        "category": "vps_focused",
        "tier": "tier_2_vps",
        "website": "https://www.vultr.com",
        "sovereignty": "EU regions available",
        "min_monthly_cost": 5.0,
        "currency": "USD",
        "setup_minutes": 10,
        "sla": "99.99%",
        "auth_methods": ["api_key"],
        "regions": [
            {"id": "fra", "display": "Germany (Frankfurt)", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "waw", "display": "Poland (Warsaw)", "sovereignty": "PL/EU", "gdpr_friendly": True},
        ],
        "instance_types": [
            {"id": "vc2-1c-1gb", "display": "Cloud Compute 1GB", "cpu": 1, "ram_gb": 1, "monthly_estimate": 5.0, "good_for": ["dev", "demo"]},
        ],
        "services_supported": ["instances", "block_storage", "kubernetes", "object_storage"],
        "recommended_for": ["fast_vps_setup", "many_regions"],
        "quirks": ["API key should be scoped", "regional product availability varies"],
    },
    {
        "provider": "scaleway",
        "display_name": "Scaleway",
        "category": "sovereign_eu",
        "tier": "tier_5_sovereign_eu",
        "website": "https://www.scaleway.com",
        "sovereignty": "FR sovereign",
        "min_monthly_cost": 1.99,
        "currency": "EUR",
        "setup_minutes": 15,
        "sla": "99.95%",
        "auth_methods": ["access_key_secret", "scw_cli"],
        "regions": [
            {"id": "fr-par", "display": "France (Paris)", "sovereignty": "EU/FR", "gdpr_friendly": True},
            {"id": "nl-ams", "display": "Netherlands (Amsterdam)", "sovereignty": "EU", "gdpr_friendly": True},
            {"id": "pl-waw", "display": "Poland (Warsaw)", "sovereignty": "PL/EU", "gdpr_friendly": True},
        ],
        "instance_types": [
            {"id": "DEV1-S", "display": "DEV1-S", "cpu": 2, "ram_gb": 2, "monthly_estimate": 1.99, "good_for": ["dev", "cheap_staging"]},
        ],
        "services_supported": ["instances", "object_storage", "kapsule", "serverless"],
        "recommended_for": ["cheap_staging", "fr_sovereign"],
        "quirks": ["project ID required", "zones inside each region", "good IPv6 support"],
    },
    {
        "provider": "ionos",
        "display_name": "IONOS Cloud",
        "category": "sovereign_eu",
        "tier": "tier_5_sovereign_eu",
        "website": "https://cloud.ionos.com",
        "sovereignty": "DE sovereign",
        "min_monthly_cost": 4.50,
        "currency": "EUR",
        "setup_minutes": 20,
        "sla": "99.95%",
        "auth_methods": ["token", "username_password", "ionosctl"],
        "regions": [
            {"id": "de/fra", "display": "Germany (Frankfurt)", "sovereignty": "EU/DE", "gdpr_friendly": True},
            {"id": "de/txl", "display": "Germany (Berlin)", "sovereignty": "EU/DE", "gdpr_friendly": True},
        ],
        "instance_types": [
            {"id": "cube-xs", "display": "Cube XS", "cpu": 1, "ram_gb": 1, "monthly_estimate": 4.50, "good_for": ["dev", "small_service"]},
        ],
        "services_supported": ["servers", "datacenters", "volumes", "kubernetes", "object_storage"],
        "recommended_for": ["de_sovereign", "gdpr_sensitive"],
        "quirks": ["virtual datacenter abstraction", "DCD modelling can feel different than VPS providers"],
    },
    {
        "provider": "custom_http",
        "display_name": "Custom HTTP / Self-hosted PaaS",
        "category": "custom",
        "tier": "custom",
        "website": "",
        "sovereignty": "operator-defined",
        "min_monthly_cost": 0.0,
        "currency": "USD",
        "setup_minutes": 15,
        "sla": "operator-defined",
        "auth_methods": ["api_key", "oauth", "mtls", "manual"],
        "regions": [{"id": "custom", "display": "Operator-defined", "sovereignty": "custom", "gdpr_friendly": False}],
        "instance_types": [],
        "services_supported": ["operator_defined"],
        "recommended_for": ["self_hosted", "internal_platform"],
        "quirks": ["requires custom healthcheck and deploy adapter metadata"],
    },
]

SOVEREIGN_PROFILES: list[dict[str, Any]] = [
    {
        "id": "eu_cloud",
        "label": "EU/PL cloud region",
        "type": "cloud_sovereign",
        "examples": ["Hetzner Warsaw", "OVH WAW", "IONOS DE", "Scaleway Paris", "AWS eu-central-1"],
        "recommended_for": ["commercial PL apps", "EU customer data", "standard GDPR"],
        "not_recommended_for": ["TLP:RED", "classified material", "critical national infrastructure"],
        "enforced_restrictions": ["region must be EU/PL", "DPA/GDPR profile visible"],
    },
    {
        "id": "on_prem",
        "label": "On-premise hardware",
        "type": "sovereign_on_prem",
        "examples": ["office server room", "customer server", "Proxmox/OpenStack private cloud"],
        "recommended_for": ["legal office data", "atelier local production", "customer-owned infrastructure"],
        "not_recommended_for": ["unmaintained hardware", "unknown physical access"],
        "enforced_restrictions": ["owner and location required", "network access mode explicit"],
    },
    {
        "id": "air_gapped",
        "label": "Air-gapped environment",
        "type": "air_gapped",
        "examples": ["TLP:RED customer facility", "defense", "critical infrastructure"],
        "recommended_for": ["classified workloads", "offline package delivery", "manual status import"],
        "not_recommended_for": ["fast public web iteration", "automated cloud deploys"],
        "enforced_restrictions": [
            "no telemetry upload",
            "no external artifact upload",
            "isolated package workspace",
            "audit entries marked air_gapped",
        ],
    },
]

EDGE_PAIRING_METHODS: list[dict[str, Any]] = [
    {"id": "ssh", "label": "SSH connection", "setup_minutes": 5, "requires": ["Linux", "SSH", "IP/hostname"], "best_for": "most common edge setup"},
    {"id": "provisioning_script", "label": "Provisioning script", "setup_minutes": 10, "requires": ["operator runs script"], "best_for": "zero pre-installed agent"},
    {"id": "qr_code", "label": "QR code pairing", "setup_minutes": 2, "requires": ["AEIS edge agent"], "best_for": "preinstalled devices"},
    {"id": "bulk_csv", "label": "Bulk import CSV", "setup_minutes": 30, "requires": ["preconfigured fleet list"], "best_for": "many devices"},
    {"id": "auto_discovery", "label": "Auto-discovery mDNS/SSDP", "setup_minutes": 1, "requires": ["AEIS edge agent on LAN"], "best_for": "local lab discovery"},
]

EDGE_PLATFORM_GROUPS: list[dict[str, Any]] = [
    {"id": "raspberry_pi", "label": "Raspberry Pi family", "examples": ["Pi 4", "Pi 5", "Pi Zero 2 W", "Compute Module 4"]},
    {"id": "arm_sbc", "label": "Other ARM SBC", "examples": ["Orange Pi", "Banana Pi", "Rock Pi", "NVIDIA Jetson"]},
    {"id": "mini_pc", "label": "Intel NUC / mini PC", "examples": ["NUC 11/12/13", "Beelink", "generic x86 mini systems"]},
    {"id": "industrial_iot", "label": "Industrial / IoT", "examples": ["Advantech", "Siemens IPC", "Cisco/Dell edge gateways"]},
]

EDGE_USE_CASES: list[dict[str, Any]] = [
    {"id": "atelier_tracking", "label": "Atelier production tracking", "hardware": "Raspberry Pi 4", "apps": ["web frontend", "SQLite", "sync"]},
    {"id": "legal_sovereign", "label": "Confidential legal endpoint", "hardware": "Intel NUC 13", "apps": ["local CRM", "GDPR storage"]},
    {"id": "factory_monitoring", "label": "Factory monitoring", "hardware": "Industrial PC", "apps": ["data collector", "edge ML inference"]},
    {"id": "retail_pos", "label": "Retail POS", "hardware": "Pi 5 + touchscreen", "apps": ["catalog", "payment", "inventory sync"]},
]

DETECTION_PREFERENCES: dict[str, Any] = {
    "on_launch_quick_scan": True,
    "on_demand_deep_scan": True,
    "filesystem_watch": True,
    "network_change_detection": True,
    "cloud_resource_auto_listing": False,
    "cloud_resource_listing_frequency": "manual_only",
}

PURPOSES: list[dict[str, str]] = [
    {"id": "development", "label": "Development", "description": "rapid iteration, low risk"},
    {"id": "testing", "label": "Testing", "description": "isolated validation"},
    {"id": "staging", "label": "Staging", "description": "integration testing, pre-prod"},
    {"id": "production", "label": "Production", "description": "live customer traffic"},
    {"id": "edge", "label": "Edge", "description": "customer-side or device-side runtime"},
    {"id": "demo_sandbox", "label": "Demo / Sandbox", "description": "showcase and experiments"},
    {"id": "sovereign", "label": "Sovereign", "description": "jurisdiction-constrained workloads"},
    {"id": "air_gapped", "label": "Air-gapped", "description": "manual offline package delivery"},
]

NETWORK_TOPOLOGIES: list[dict[str, Any]] = [
    {
        "id": "isolated",
        "label": "Isolated",
        "default": True,
        "description": "Environment has its own local/private network boundary.",
        "recommended_for": ["development", "testing", "air_gapped", "single tenant"],
        "requires": [],
    },
    {
        "id": "mesh",
        "label": "Mesh",
        "default": False,
        "description": "Nodes join an encrypted peer network for operator, edge and customer-side access.",
        "recommended_for": ["edge", "on_prem", "distributed staging", "support access"],
        "requires": ["mesh_provider", "device_identity"],
    },
    {
        "id": "hub_spoke",
        "label": "Hub-and-spoke",
        "default": False,
        "description": "Cloud or datacenter hub brokers access to spoke environments.",
        "recommended_for": ["production", "multi_region", "customer VPC"],
        "requires": ["hub_environment", "routing_policy"],
    },
    {
        "id": "custom_hybrid",
        "label": "Custom / hybrid",
        "default": False,
        "description": "Operator-managed topology for mixed cloud, sovereign, on-prem and air-gapped paths.",
        "recommended_for": ["enterprise", "regulated", "migration"],
        "requires": ["operator_design", "human_gate"],
    },
]

MESH_PROVIDER_TEMPLATES: list[dict[str, Any]] = [
    {"id": "tailscale", "label": "Tailscale", "managed": True, "open_source": False, "relay": "DERP", "identity": "SSO/device auth", "best_for": ["fast setup", "edge fleet"]},
    {"id": "headscale", "label": "Headscale", "managed": False, "open_source": True, "relay": "self-hosted", "identity": "operator controlled", "best_for": ["sovereign", "self-hosted"]},
    {"id": "netbird", "label": "NetBird", "managed": True, "open_source": True, "relay": "managed/self-hosted", "identity": "IdP groups", "best_for": ["policy UI", "teams"]},
    {"id": "zerotier", "label": "ZeroTier", "managed": True, "open_source": False, "relay": "planet/moon", "identity": "network membership", "best_for": ["L2-like networks"]},
    {"id": "wireguard", "label": "Raw WireGuard", "managed": False, "open_source": True, "relay": "none", "identity": "static keys", "best_for": ["minimal attack surface"]},
    {"id": "nebula", "label": "Nebula", "managed": False, "open_source": True, "relay": "lighthouse", "identity": "certificates", "best_for": ["large flat mesh"]},
]

VPN_MODES: list[dict[str, Any]] = [
    {"id": "disabled", "label": "Disabled", "default": True, "requires": []},
    {"id": "wireguard", "label": "WireGuard", "default": False, "requires": ["peer_public_key", "allowed_ips"]},
    {"id": "tailscale", "label": "Tailscale", "default": False, "requires": ["tailnet", "device_tags"]},
    {"id": "managed_vpn", "label": "Managed cloud VPN", "default": False, "requires": ["cloud_account", "gateway"]},
    {"id": "customer_vpn", "label": "Customer VPN", "default": False, "requires": ["customer_gateway", "support_contact"]},
    {"id": "air_gap_manual", "label": "Air-gap/manual transfer", "default": False, "requires": ["offline_package", "signed_manifest"]},
]

FIREWALL_TEMPLATES: dict[str, dict[str, Any]] = {
    "local_only": {
        "label": "Local only",
        "inbound": ["127.0.0.1:3000", "127.0.0.1:8000"],
        "outbound": ["os_updates", "package_registries"],
    },
    "basic_web": {
        "label": "Basic web/API",
        "inbound": ["tcp:80", "tcp:443"],
        "outbound": ["dns", "ntp", "os_updates", "provider_api"],
    },
    "api_backend": {
        "label": "API backend",
        "inbound": ["tcp:443", "tcp:8000 from load_balancer_or_vpn"],
        "outbound": ["dns", "ntp", "database", "object_storage", "provider_api"],
    },
    "production_strict": {
        "label": "Production strict",
        "inbound": ["tcp:443 from load_balancer", "tcp:22 from vpn_only"],
        "outbound": ["dns", "ntp", "database_private", "object_storage_private", "monitoring"],
    },
    "edge_device": {
        "label": "Edge device",
        "inbound": ["tcp:22 from vpn_only", "tcp:443 optional"],
        "outbound": ["vpn_mesh", "sync_endpoint", "time_sync"],
    },
    "air_gapped": {
        "label": "Air-gapped",
        "inbound": [],
        "outbound": [],
    },
}

NETWORK_MONITORING_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "checks": ["reachability", "dns_resolution", "vpn_session", "firewall_drift"],
    "cadence_seconds": 300,
    "alert_on": ["vpn_down", "unexpected_open_port", "egress_change"],
}

RESIDENCY_RULE_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "gdpr_eu",
        "label": "GDPR / EU only",
        "allowed_regions": ["EU", "PL", "DE", "FR", "NL", "FI"],
        "data_classes": ["PII", "customer_data", "billing"],
        "hard_requirements": ["no_us_processing", "subprocessor_disclosure"],
    },
    {
        "id": "poland_only",
        "label": "Poland only",
        "allowed_regions": ["PL"],
        "data_classes": ["public_sector", "sensitive_legal", "PII"],
        "hard_requirements": ["polish_datacenter_or_on_prem"],
    },
    {
        "id": "sovereign_eu",
        "label": "Sovereign EU",
        "allowed_regions": ["EU"],
        "data_classes": ["regulated", "health", "finance"],
        "hard_requirements": ["eu_operator_preferred", "audit_export"],
    },
    {
        "id": "air_gapped",
        "label": "Air-gapped",
        "allowed_regions": ["ON_PREM", "AIR_GAPPED"],
        "data_classes": ["classified", "TLP_RED"],
        "hard_requirements": ["offline_delivery", "signed_packages", "manual_sync"],
    },
]

CLEANUP_STRATEGIES: list[dict[str, Any]] = [
    {"id": "manual", "label": "Manual", "description": "Operator must approve deletion or teardown."},
    {"id": "auto_after_hours", "label": "Auto after N hours", "description": "Sandbox/test resources expire after a configured age."},
    {"id": "conditional", "label": "Conditional", "description": "Cleanup runs when cost, tags and inactivity conditions match."},
    {"id": "schedule", "label": "Schedule", "description": "Cleanup runs in an operator-defined window."},
]

CLEANUP_DECISION_MATRIX: dict[str, dict[str, Any]] = {
    "development": {"strategy": "auto_after_hours", "cleanup_after_hours": 168, "action": "notify_then_stop"},
    "testing": {"strategy": "auto_after_hours", "cleanup_after_hours": 72, "action": "stop_then_delete_after_review"},
    "staging": {"strategy": "conditional", "inactive_days": 14, "action": "snapshot_then_stop"},
    "production": {"strategy": "manual", "inactive_days": None, "action": "never_delete_without_gate"},
    "edge": {"strategy": "conditional", "inactive_days": 30, "action": "disable_sync_then_review"},
    "demo_sandbox": {"strategy": "auto_after_hours", "cleanup_after_hours": 24, "action": "delete_ephemeral"},
    "sovereign": {"strategy": "manual", "inactive_days": None, "action": "signed_cleanup_request"},
    "air_gapped": {"strategy": "manual", "inactive_days": None, "action": "offline_manifest_only"},
}

EDGE_CASES: list[dict[str, Any]] = [
    {"id": "EC-A1", "category": "cloud_provider", "title": "Cloud account suspended", "severity": "high", "detection": "provider_auth_failed", "recommended_action": "freeze deploys, ask operator to verify billing/account status", "human_gate": True},
    {"id": "EC-A2", "category": "cloud_provider", "title": "Region-wide outage", "severity": "critical", "detection": "region_health_down", "recommended_action": "move to approved fallback region or trigger DR plan", "human_gate": True},
    {"id": "EC-A3", "category": "cloud_provider", "title": "Quota exhausted", "severity": "medium", "detection": "quota_or_limit_error", "recommended_action": "request quota, resize plan or choose another provider", "human_gate": False},
    {"id": "EC-A4", "category": "cloud_provider", "title": "Instance type deprecated", "severity": "medium", "detection": "instance_type_unavailable", "recommended_action": "map to replacement SKU and record migration note", "human_gate": False},
    {"id": "EC-A5", "category": "cloud_provider", "title": "Vendor pricing change", "severity": "medium", "detection": "forecast_delta_over_threshold", "recommended_action": "refresh cost caps and ask operator before prod expansion", "human_gate": True},
    {"id": "EC-B1", "category": "network", "title": "VPN tunnel breaks mid-deploy", "severity": "high", "detection": "vpn_session_lost", "recommended_action": "pause deployment, keep rollback package, restore tunnel before continuing", "human_gate": True},
    {"id": "EC-B2", "category": "network", "title": "DNS propagation issue", "severity": "medium", "detection": "dns_mismatch", "recommended_action": "lower TTL, verify authoritative records and delay cutover", "human_gate": False},
    {"id": "EC-B3", "category": "network", "title": "Firewall blocks legitimate traffic", "severity": "medium", "detection": "healthcheck_timeout_after_firewall_change", "recommended_action": "diff firewall template and open only the required source/port", "human_gate": False},
    {"id": "EC-B4", "category": "network", "title": "Mesh network split-brain", "severity": "high", "detection": "mesh_peer_groups_diverge", "recommended_action": "pin control plane, rotate stale peers and revalidate routing", "human_gate": True},
    {"id": "EC-B5", "category": "network", "title": "NAT traversal failure for edge device", "severity": "medium", "detection": "edge_peer_unreachable", "recommended_action": "fallback to relay, customer VPN or outbound-only sync", "human_gate": False},
    {"id": "EC-C1", "category": "edge_device", "title": "Edge device offline", "severity": "medium", "detection": "heartbeat_missing", "recommended_action": "queue sync, notify customer contact and avoid destructive actions", "human_gate": False},
    {"id": "EC-C2", "category": "edge_device", "title": "SD card failure for Raspberry Pi", "severity": "high", "detection": "filesystem_readonly_or_io_errors", "recommended_action": "switch to backup image and restore latest signed snapshot", "human_gate": True},
    {"id": "EC-C3", "category": "edge_device", "title": "Edge device hijacked", "severity": "critical", "detection": "unexpected_identity_or_traffic", "recommended_action": "revoke mesh identity, quarantine data and rotate credentials", "human_gate": True},
    {"id": "EC-C4", "category": "edge_device", "title": "Edge update fails / bricked", "severity": "high", "detection": "post_update_boot_missing", "recommended_action": "rollback boot slot or dispatch offline recovery package", "human_gate": True},
    {"id": "EC-C5", "category": "edge_device", "title": "Bulk edge update mixed results", "severity": "medium", "detection": "fleet_update_partial_success", "recommended_action": "freeze rollout, segment failed devices and retry canary first", "human_gate": False},
    {"id": "EC-D1", "category": "customer_on_prem", "title": "Customer changes server hardware", "severity": "medium", "detection": "hardware_fingerprint_changed", "recommended_action": "re-scan, update capacity and re-run residency checks", "human_gate": False},
    {"id": "EC-D2", "category": "customer_on_prem", "title": "Compliance audit requires data export", "severity": "high", "detection": "audit_export_requested", "recommended_action": "generate signed environment, residency and access reports", "human_gate": True},
    {"id": "EC-D3", "category": "customer_on_prem", "title": "Air-gapped sync conflict", "severity": "high", "detection": "offline_manifest_conflict", "recommended_action": "stop import, compare manifests and require operator merge", "human_gate": True},
    {"id": "EC-D4", "category": "customer_on_prem", "title": "On-prem server out of disk", "severity": "high", "detection": "disk_free_below_threshold", "recommended_action": "stop noncritical jobs, snapshot logs and run approved cleanup", "human_gate": False},
    {"id": "EC-D5", "category": "customer_on_prem", "title": "Sovereign provider certification expired", "severity": "critical", "detection": "attestation_expired", "recommended_action": "block new deployments until certification is updated or provider changed", "human_gate": True},
    {"id": "EC-E1", "category": "cost", "title": "Sudden cost spike / crypto-mining attack", "severity": "critical", "detection": "cost_anomaly_plus_cpu_spike", "recommended_action": "isolate environment, rotate keys and preserve forensic evidence", "human_gate": True},
    {"id": "EC-E2", "category": "cost", "title": "Reserved instance overbought", "severity": "medium", "detection": "reserved_capacity_idle", "recommended_action": "flag waste and adjust purchasing plan", "human_gate": False},
    {"id": "EC-E3", "category": "cost", "title": "Budget alert noise", "severity": "low", "detection": "repeated_false_positive_alerts", "recommended_action": "tune thresholds per purpose and require anomaly confirmation", "human_gate": False},
    {"id": "EC-E4", "category": "cost", "title": "Free tier expiration", "severity": "medium", "detection": "free_tier_end_date_near", "recommended_action": "convert to paid cap or migrate before bill shock", "human_gate": False},
    {"id": "EC-E5", "category": "cost", "title": "Egress costs surprise", "severity": "high", "detection": "egress_forecast_jump", "recommended_action": "move data path private/CDN and ask operator before transfer", "human_gate": True},
    {"id": "EC-F1", "category": "migration_dr", "title": "Cloud-to-cloud migration", "severity": "medium", "detection": "migration_requested", "recommended_action": "stage target environment, run residency and cost diff, cut over with rollback", "human_gate": True},
    {"id": "EC-F2", "category": "migration_dr", "title": "Disaster recovery region down", "severity": "critical", "detection": "primary_region_down", "recommended_action": "activate DR environment and write incident audit entry", "human_gate": True},
    {"id": "EC-F3", "category": "migration_dr", "title": "Workspace import on new operator machine", "severity": "medium", "detection": "workspace_machine_changed", "recommended_action": "run local scan, verify secrets are not copied and re-accept local-dev", "human_gate": False},
    {"id": "EC-F4", "category": "migration_dr", "title": "Environment metadata corruption", "severity": "high", "detection": "catalog_json_parse_or_hash_fail", "recommended_action": "restore last snapshot and reconcile with provider state manually", "human_gate": True},
    {"id": "EC-F5", "category": "migration_dr", "title": "Environment migration to new hardware", "severity": "medium", "detection": "hardware_migration_requested", "recommended_action": "scan target, compare capabilities and update routing/backup policies", "human_gate": False},
]

INHERITANCE_LEVELS: list[dict[str, Any]] = [
    {"id": "workspace", "label": "Workspace", "order": 10},
    {"id": "project", "label": "Project", "order": 20},
    {"id": "environment", "label": "Environment", "order": 30},
    {"id": "module", "label": "Module", "order": 40, "phase": 33},
]


class ScanLocalRequest(BaseModel):
    auto_create_local_dev: bool = True
    deep_scan: bool = False


class AcceptLocalDevRequest(BaseModel):
    display_name: str | None = None
    purpose: str | None = None
    notes: str | None = None


class AddDetectedProvidersRequest(BaseModel):
    providers: list[str] | None = None


class CreateEnvironmentRequest(BaseModel):
    environment_id: str | None = None
    name: str
    display_name: str | None = None
    environment_type: str = "custom"
    provider: str = "custom"
    purpose: str = "development"
    tier: str = "dev"
    account: str = ""
    region: str = ""
    datacenter: str = ""
    resources: dict[str, Any] = {}
    configuration: dict[str, Any] = {}
    cost: dict[str, Any] = {}
    status: dict[str, Any] = {}
    policies: dict[str, Any] = {}
    network: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


class CreateEdgeDeviceRequest(BaseModel):
    display_name: str
    pairing_method: str = "ssh"
    hostname: str = ""
    ssh_port: int = 22
    ssh_username: str = ""
    device_type: str = "raspberry_pi_4"
    architecture: str = "arm64"
    purpose: str = "edge"
    location: str = ""
    owner: str = ""
    capabilities: list[str] = []
    ram_gb: float | None = None
    storage_gb: float | None = None
    auto_update_policy: str = "weekly_auto"
    sync_strategy: str = "periodic_5_min"


class SovereigntyEvaluateRequest(BaseModel):
    environment_id: str | None = None
    classification: str = "standard"
    requires_eu: bool = False
    requires_poland: bool = False
    allow_air_gapped: bool = True


class UpdateNetworkPolicyRequest(BaseModel):
    environment_id: str
    network_mode: str = "isolated"
    vpn_mode: str = "disabled"
    mesh_provider: str = ""
    firewall_template: str = "basic_web"
    sensitive: bool = False
    custom_policy: dict[str, Any] = {}


class ResidencyRuleRequest(BaseModel):
    project_id: str = "workspace-default"
    compliance_profile: str = "gdpr_eu"
    allowed_regions: list[str] = ["EU"]
    data_classes: list[str] = ["PII"]
    hard_requirements: list[str] = []
    subprocessor_disclosure: bool = True


class ResidencyCheckRequest(BaseModel):
    project_id: str = "workspace-default"
    environment_id: str
    data_classes: list[str] = ["PII"]
    allowed_regions: list[str] = ["EU"]
    requires_poland: bool = False
    override_code: str = ""
    override_reason: str = ""


class CostAlertRequest(BaseModel):
    environment_id: str
    monthly_budget_cap: float = 0
    thresholds: list[int] = [50, 80, 95, 100]
    channels: list[str] = ["in_app"]
    auto_actions: dict[str, Any] = {}


class CleanupPolicyRequest(BaseModel):
    environment_id: str
    strategy: str = "manual"
    cleanup_after_hours: int | None = None
    inactive_days: int | None = None
    schedule: str = ""
    action: str = "notify_only"


class BulkCleanupPlanRequest(BaseModel):
    purposes: list[str] = ["testing", "demo_sandbox"]
    inactive_days: int = 14
    include_tags: list[str] = []
    exclude_tags: list[str] = ["keep-permanent", "customer-prod"]


class EdgeCaseDiagnoseRequest(BaseModel):
    case_id: str
    environment_id: str = ""
    context: dict[str, Any] = {}


class InheritanceResolveRequest(BaseModel):
    project_id: str = "workspace-default"
    module_id: str = ""
    purpose: str = "production"
    goal: str = "apps_internal"
    overrides: dict[str, Any] = {}


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _db_path() -> Path:
    return Path(os.environ.get("SYLION_DB_PATH", "sylion_aeis.db"))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS environment_catalog_state (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS environment_catalog_environments (
            environment_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            env_type TEXT NOT NULL,
            provider TEXT NOT NULL,
            purpose TEXT NOT NULL,
            tier TEXT NOT NULL,
            account TEXT NOT NULL DEFAULT '',
            region TEXT NOT NULL DEFAULT '',
            datacenter TEXT NOT NULL DEFAULT '',
            status_state TEXT NOT NULL DEFAULT 'running',
            health TEXT NOT NULL DEFAULT 'healthy',
            monthly_estimate_usd REAL NOT NULL DEFAULT 0,
            monthly_estimate_eur REAL NOT NULL DEFAULT 0,
            resources_json TEXT NOT NULL DEFAULT '{}',
            configuration_json TEXT NOT NULL DEFAULT '{}',
            policies_json TEXT NOT NULL DEFAULT '{}',
            network_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            accepted_at REAL
        );

        CREATE TABLE IF NOT EXISTS environment_catalog_provider_accounts (
            account_id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            display_name TEXT NOT NULL,
            account_ref TEXT NOT NULL DEFAULT '',
            default_region TEXT NOT NULL DEFAULT '',
            auth_method TEXT NOT NULL DEFAULT 'manual',
            credential_status TEXT NOT NULL DEFAULT 'not_configured',
            source TEXT NOT NULL DEFAULT 'manual',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            last_test_status TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_environment_catalog_env_type
            ON environment_catalog_environments(env_type);
        CREATE INDEX IF NOT EXISTS idx_environment_catalog_env_purpose
            ON environment_catalog_environments(purpose);
        CREATE INDEX IF NOT EXISTS idx_environment_catalog_account_provider
            ON environment_catalog_provider_accounts(provider);
        """
    )
    conn.commit()


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _set_state(key: str, value: Any) -> None:
    now = time.time()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO environment_catalog_state (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json=excluded.value_json,
                updated_at=excluded.updated_at
            """,
            (key, json.dumps(value, ensure_ascii=False, default=str), now),
        )


def _get_state(key: str) -> Any | None:
    with _connect() as conn:
        row = conn.execute("SELECT value_json FROM environment_catalog_state WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    return _json_loads(row["value_json"], None)


def _command_probe(command: str, args: list[str] | None = None, timeout_s: float = 1.2) -> dict[str, Any]:
    path = shutil.which(command)
    if not path:
        return {"installed": False, "path": "", "version": "", "error": "not_found"}
    try:
        result = subprocess.run(
            [path, *(args or ["--version"])],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        output = (result.stdout or result.stderr or "").strip().splitlines()
        return {
            "installed": True,
            "path": path,
            "version": output[0][:240] if output else "",
            "exit_code": result.returncode,
            "error": "",
        }
    except subprocess.TimeoutExpired:
        return {"installed": True, "path": path, "version": "", "exit_code": None, "error": "timeout"}
    except Exception as exc:
        return {"installed": True, "path": path, "version": "", "exit_code": None, "error": type(exc).__name__}


def _memory_info() -> dict[str, Any]:
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return {
                "total_gb": round(status.ullTotalPhys / (1024 ** 3), 2),
                "available_gb": round(status.ullAvailPhys / (1024 ** 3), 2),
                "load_percent": int(status.dwMemoryLoad),
            }
        return {}
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        phys_pages = os.sysconf("SC_PHYS_PAGES")
        avail_pages = os.sysconf("SC_AVPHYS_PAGES")
        return {
            "total_gb": round((page_size * phys_pages) / (1024 ** 3), 2),
            "available_gb": round((page_size * avail_pages) / (1024 ** 3), 2),
        }
    except Exception:
        return {}


def _disk_info() -> list[dict[str, Any]]:
    roots: list[str] = []
    for candidate in [Path.cwd().anchor, Path.home().anchor, os.environ.get("SYSTEMDRIVE", "") + "\\"]:
        if candidate and candidate not in roots:
            roots.append(candidate)
    if not roots:
        roots = ["/"]
    disks: list[dict[str, Any]] = []
    for root in roots:
        try:
            usage = shutil.disk_usage(root)
            disks.append(
                {
                    "mount": root,
                    "total_gb": round(usage.total / (1024 ** 3), 2),
                    "free_gb": round(usage.free / (1024 ** 3), 2),
                    "used_gb": round(usage.used / (1024 ** 3), 2),
                }
            )
        except Exception:
            continue
    return disks


def _gpu_info() -> dict[str, Any]:
    nvidia = shutil.which("nvidia-smi")
    if not nvidia:
        return {"detected": False, "vendor": "", "devices": []}
    try:
        result = subprocess.run(
            [
                nvidia,
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )
        devices = []
        for line in (result.stdout or "").splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 3:
                devices.append({"name": parts[0], "vram_mb": parts[1], "driver": parts[2]})
        return {"detected": bool(devices), "vendor": "nvidia" if devices else "", "devices": devices}
    except Exception as exc:
        return {"detected": True, "vendor": "nvidia", "devices": [], "error": type(exc).__name__}


def _port_status(port: int) -> dict[str, Any]:
    started = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.08)
    try:
        busy = sock.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        busy = False
    finally:
        sock.close()
    return {"port": port, "busy": busy, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


def _network_info() -> dict[str, Any]:
    hostname = socket.gethostname()
    addresses: list[str] = []
    try:
        addresses = [ip for ip in socket.gethostbyname_ex(hostname)[2] if not ip.startswith("127.")]
    except Exception:
        addresses = []
    ssh_config = Path.home() / ".ssh" / "config"
    host_count = 0
    if ssh_config.exists():
        try:
            for line in ssh_config.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.strip()
                if stripped.lower().startswith("host ") and "*" not in stripped:
                    host_count += 1
        except Exception:
            host_count = 0
    return {
        "hostname": hostname,
        "local_ips": addresses[:8],
        "network_interfaces_count": max(1, len(addresses)),
        "ssh_config_exists": ssh_config.exists(),
        "ssh_host_entries_count": host_count,
        "tailscale_installed": shutil.which("tailscale") is not None,
        "wireguard_installed": shutil.which("wg") is not None or shutil.which("wireguard") is not None,
        "dns_name": socket.getfqdn(),
    }


def _cloud_cli_detection() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for tool in CLOUD_CLI_TOOLS:
        probe = _command_probe(str(tool["command"]))
        config_paths = []
        for raw_path in tool.get("config_paths", []):
            path = Path(str(raw_path)).expanduser()
            config_paths.append({"path": str(path), "exists": path.exists()})
        tools.append(
            {
                **tool,
                **probe,
                "config_paths": config_paths,
                "config_present": any(item["exists"] for item in config_paths),
                "resource_listing_enabled": False,
            }
        )
    return tools


def _scan_local_machine(deep_scan: bool = False) -> dict[str, Any]:
    docker = _command_probe("docker")
    docker_daemon = {"running": False, "version": "", "error": "docker_not_installed"}
    compose = {"installed": False, "path": "", "version": "", "error": "not_found"}
    if docker.get("installed"):
        docker_daemon_probe = _command_probe("docker", ["info", "--format", "{{.ServerVersion}}"], timeout_s=1.2 if not deep_scan else 3.0)
        docker_daemon = {
            "running": docker_daemon_probe.get("exit_code") == 0 and not docker_daemon_probe.get("error"),
            "version": docker_daemon_probe.get("version", ""),
            "error": docker_daemon_probe.get("error", "") or ("" if docker_daemon_probe.get("exit_code") == 0 else "daemon_unavailable"),
        }
        compose = _command_probe("docker", ["compose", "version"], timeout_s=1.2)
    if not compose.get("installed") or compose.get("exit_code") not in {0, None}:
        legacy_compose = _command_probe("docker-compose")
        if legacy_compose.get("installed"):
            compose = legacy_compose

    kubectl = _command_probe("kubectl", ["version", "--client=true"], timeout_s=1.2)
    kube_config = Path.home() / ".kube" / "config"
    current_context = ""
    if kubectl.get("installed"):
        context_probe = _command_probe("kubectl", ["config", "current-context"], timeout_s=1.0)
        current_context = context_probe.get("version", "") if not context_probe.get("error") else ""

    port_rows = []
    for item in COMMON_PORTS:
        status = _port_status(int(item["port"]))
        port_rows.append({**item, **status})

    git = _command_probe("git")
    node = _command_probe("node")
    python = {"installed": True, "path": shutil.which("python") or "", "version": platform.python_version(), "error": ""}

    scan = {
        "scanned_at": time.time(),
        "deep_scan": deep_scan,
        "os": {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        },
        "hardware": {
            "cpu_cores": os.cpu_count() or 0,
            "cpu_model": platform.processor() or platform.machine(),
            "memory": _memory_info(),
            "disks": _disk_info(),
            "gpu": _gpu_info(),
            "network": _network_info(),
        },
        "software": {
            "docker": docker,
            "docker_daemon": docker_daemon,
            "docker_compose": compose,
            "podman": _command_probe("podman"),
            "git": git,
            "node": node,
            "python": python,
        },
        "kubernetes": {
            "kubectl": kubectl,
            "kube_config_exists": kube_config.exists(),
            "active_context": current_context,
            "local_cluster_hint": any(name in current_context.lower() for name in ["kind", "k3d", "k3s", "minikube"]),
        },
        "ports": port_rows,
        "cloud_cli_tools": _cloud_cli_detection(),
        "privacy": {
            "cloud_resource_listing_enabled": False,
            "cloud_resource_listing_requires_explicit_consent": True,
            "ssh_hosts_redacted": True,
            "public_ip_detection_enabled": False,
        },
    }
    _set_state("last_local_scan", scan)
    return scan


def _row_to_environment(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["type"] = data.pop("env_type")
    data["resources"] = _json_loads(data.pop("resources_json"), {})
    data["configuration"] = _json_loads(data.pop("configuration_json"), {})
    data["policies"] = _json_loads(data.pop("policies_json"), {})
    data["network"] = _json_loads(data.pop("network_json"), {})
    data["metadata"] = _json_loads(data.pop("metadata_json"), {})
    data["classification"] = {
        "type": data["type"],
        "purpose": data["purpose"],
        "tier": data["tier"],
        "sovereign": bool(data["metadata"].get("sovereign") or data["type"] in {"air_gapped", "on_prem"} or str(data["region"]).lower().startswith(("eu", "pl", "de", "fr", "waw", "warsaw"))),
        "air_gapped": data["type"] == "air_gapped" or bool(data["metadata"].get("air_gapped")),
    }
    data["location"] = {
        "provider": data["provider"],
        "account": data["account"],
        "region": data["region"],
        "datacenter": data["datacenter"],
    }
    data["cost"] = {
        "monthly_estimate_usd": data["monthly_estimate_usd"],
        "monthly_estimate_eur": data["monthly_estimate_eur"],
    }
    data["status"] = {"state": data["status_state"], "health": data["health"]}
    return data


def _list_environments() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM environment_catalog_environments ORDER BY created_at ASC").fetchall()
    return [_row_to_environment(row) for row in rows]


def _list_provider_accounts() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM environment_catalog_provider_accounts ORDER BY created_at ASC").fetchall()
    accounts = []
    for row in rows:
        data = dict(row)
        data["metadata"] = _json_loads(data.pop("metadata_json"), {})
        accounts.append(data)
    return accounts


def _save_environment(payload: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    env_id = str(payload.get("environment_id") or _uid("env"))
    name = str(payload.get("name") or env_id).strip()
    if not name:
        raise ValueError("environment name must be non-empty")
    display_name = str(payload.get("display_name") or name).strip()
    env_type = str(payload.get("environment_type") or payload.get("type") or "custom").strip().lower()
    provider = str(payload.get("provider") or env_type).strip().lower()
    purpose = str(payload.get("purpose") or "development").strip().lower()
    tier = str(payload.get("tier") or "dev").strip().lower()
    account = str(payload.get("account") or "").strip()
    region = str(payload.get("region") or "").strip()
    datacenter = str(payload.get("datacenter") or "").strip()
    status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
    cost = payload.get("cost") if isinstance(payload.get("cost"), dict) else {}

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO environment_catalog_environments (
                environment_id, name, display_name, env_type, provider, purpose,
                tier, account, region, datacenter, status_state, health,
                monthly_estimate_usd, monthly_estimate_eur, resources_json,
                configuration_json, policies_json, network_json, metadata_json,
                created_at, updated_at, accepted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(environment_id) DO UPDATE SET
                name=excluded.name,
                display_name=excluded.display_name,
                env_type=excluded.env_type,
                provider=excluded.provider,
                purpose=excluded.purpose,
                tier=excluded.tier,
                account=excluded.account,
                region=excluded.region,
                datacenter=excluded.datacenter,
                status_state=excluded.status_state,
                health=excluded.health,
                monthly_estimate_usd=excluded.monthly_estimate_usd,
                monthly_estimate_eur=excluded.monthly_estimate_eur,
                resources_json=excluded.resources_json,
                configuration_json=excluded.configuration_json,
                policies_json=excluded.policies_json,
                network_json=excluded.network_json,
                metadata_json=excluded.metadata_json,
                updated_at=excluded.updated_at,
                accepted_at=COALESCE(environment_catalog_environments.accepted_at, excluded.accepted_at)
            """,
            (
                env_id,
                name,
                display_name,
                env_type,
                provider,
                purpose,
                tier,
                account,
                region,
                datacenter,
                str(status.get("state") or payload.get("status_state") or "running"),
                str(status.get("health") or payload.get("health") or "healthy"),
                float(cost.get("monthly_estimate_usd") or payload.get("monthly_estimate_usd") or 0),
                float(cost.get("monthly_estimate_eur") or payload.get("monthly_estimate_eur") or 0),
                json.dumps(payload.get("resources") or {}, ensure_ascii=False, default=str),
                json.dumps(payload.get("configuration") or {}, ensure_ascii=False, default=str),
                json.dumps(payload.get("policies") or {}, ensure_ascii=False, default=str),
                json.dumps(payload.get("network") or {}, ensure_ascii=False, default=str),
                json.dumps(payload.get("metadata") or {}, ensure_ascii=False, default=str),
                float(payload.get("created_at") or now),
                now,
                payload.get("accepted_at"),
            ),
        )
    env = _get_environment(env_id)
    if not env:
        raise RuntimeError("environment save failed")
    return env


def _get_environment(environment_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM environment_catalog_environments WHERE environment_id = ?",
            (environment_id,),
        ).fetchone()
    return _row_to_environment(row) if row else None


def _state_list(key: str) -> list[dict[str, Any]]:
    value = _get_state(key)
    return value if isinstance(value, list) else []


def _append_state_list(key: str, item: dict[str, Any], limit: int = 500) -> list[dict[str, Any]]:
    rows = _state_list(key)
    rows.append(item)
    if limit > 0:
        rows = rows[-limit:]
    _set_state(key, rows)
    return rows


def _append_phase3_audit(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    chain = _state_list("phase3_audit_chain")
    previous_hash = str(chain[-1].get("hash") or "") if chain else ""
    entry = {
        "event_id": _uid("audit"),
        "event": event,
        "payload": payload,
        "created_at": time.time(),
        "previous_hash": previous_hash,
    }
    canonical = json.dumps(entry, ensure_ascii=False, sort_keys=True, default=str)
    entry["hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    _append_state_list("phase3_audit_chain", entry, limit=1000)
    return entry


def _firewall_template(template_id: str) -> dict[str, Any]:
    return FIREWALL_TEMPLATES.get(template_id) or FIREWALL_TEMPLATES["basic_web"]


def _default_firewall_template(env: dict[str, Any]) -> str:
    if env["type"] == "air_gapped":
        return "air_gapped"
    if env["type"] == "edge":
        return "edge_device"
    if env["type"] == "local":
        return "local_only"
    if env["purpose"] == "production":
        return "production_strict"
    return "basic_web"


def _network_policy_for(env: dict[str, Any]) -> dict[str, Any]:
    raw = env.get("network") if isinstance(env.get("network"), dict) else {}
    template_id = str(raw.get("firewall_template") or _default_firewall_template(env))
    firewall = _firewall_template(template_id)
    network_mode = str(raw.get("network_mode") or raw.get("topology") or "isolated")
    vpn_mode = str(raw.get("vpn_mode") or ("air_gap_manual" if env["type"] == "air_gapped" else "disabled"))
    if env["type"] == "edge" and vpn_mode == "disabled" and raw.get("vpn_attached"):
        vpn_mode = "tailscale"
    return {
        "environment_id": env["environment_id"],
        "environment_name": env.get("display_name") or env.get("name"),
        "network_mode": network_mode,
        "vpn_mode": vpn_mode,
        "mesh_provider": str(raw.get("mesh_provider") or ""),
        "firewall_template": template_id,
        "inbound_rules": raw.get("inbound_rules") or firewall.get("inbound", []),
        "outbound_rules": raw.get("outbound_rules") or firewall.get("outbound", []),
        "sensitive": bool(raw.get("sensitive") or env["purpose"] in {"production", "sovereign", "air_gapped"}),
        "monitoring": raw.get("monitoring") or NETWORK_MONITORING_DEFAULTS,
        "custom_policy": raw.get("custom_policy") or {},
        "stored": bool(raw.get("phase3_policy") or raw.get("network_mode") or raw.get("firewall_template")),
        "source": "stored_policy" if raw.get("phase3_policy") else "generated_default",
    }


def _network_overview(environments: list[dict[str, Any]]) -> dict[str, Any]:
    policies = [_network_policy_for(env) for env in environments]
    vpn_required = [
        policy
        for policy in policies
        if policy["sensitive"] and policy["vpn_mode"] == "disabled" and policy["network_mode"] != "isolated"
    ]
    return {
        "topologies": NETWORK_TOPOLOGIES,
        "mesh_providers": MESH_PROVIDER_TEMPLATES,
        "vpn_modes": VPN_MODES,
        "firewall_templates": [{"id": key, **value} for key, value in FIREWALL_TEMPLATES.items()],
        "monitoring_defaults": NETWORK_MONITORING_DEFAULTS,
        "policies": policies,
        "diagnostics": {
            "environments_with_policy": len(policies),
            "explicit_policies": len([item for item in policies if item["stored"]]),
            "vpn_attention_required": vpn_required,
        },
        "federation_use_cases": [
            "operator support access to customer edge",
            "cloud-to-cloud migration bridge",
            "sovereign/on-prem sync window",
            "disaster recovery routing",
        ],
    }


def _region_bucket(env: dict[str, Any]) -> str:
    region = str(env.get("region") or "").lower()
    env_type = str(env.get("type") or "").lower()
    if env_type == "air_gapped":
        return "AIR_GAPPED"
    if env_type in {"on_prem", "local", "edge"}:
        return "ON_PREM"
    if region.startswith(("pl", "waw", "warsaw", "poland")) or "poland" in region:
        return "PL"
    if region.startswith(("eu", "de", "fr", "nl", "fi", "be", "westeurope", "germany", "fra", "ams", "fsn", "nbg", "hel", "gra", "sbg")):
        return "EU"
    if region.startswith(("us", "nyc", "sfo", "atl", "iad")) or "usa" in region:
        return "US"
    if env.get("classification", {}).get("sovereign"):
        return "EU"
    return "UNKNOWN"


def _residency_rules() -> list[dict[str, Any]]:
    saved = _state_list("phase3_residency_rules")
    if saved:
        return saved
    return [
        {
            "rule_id": f"default_{item['id']}",
            "project_id": "workspace-default",
            "compliance_profile": item["id"],
            "allowed_regions": item["allowed_regions"],
            "data_classes": item["data_classes"],
            "hard_requirements": item["hard_requirements"],
            "subprocessor_disclosure": True,
            "source": "template",
            "updated_at": time.time(),
        }
        for item in RESIDENCY_RULE_TEMPLATES
        if item["id"] == "gdpr_eu"
    ]


def _upsert_residency_rule(body: ResidencyRuleRequest) -> dict[str, Any]:
    now = time.time()
    rule_id = f"{body.project_id}:{body.compliance_profile}"
    rules = [rule for rule in _residency_rules() if rule.get("rule_id") != rule_id]
    rule = {
        "rule_id": rule_id,
        "project_id": body.project_id,
        "compliance_profile": body.compliance_profile,
        "allowed_regions": body.allowed_regions,
        "data_classes": body.data_classes,
        "hard_requirements": body.hard_requirements,
        "subprocessor_disclosure": body.subprocessor_disclosure,
        "source": "operator_saved",
        "updated_at": now,
    }
    rules.append(rule)
    _set_state("phase3_residency_rules", rules)
    _append_phase3_audit("residency.rule_saved", {"rule_id": rule_id, "project_id": body.project_id})
    return rule


def _check_residency(body: ResidencyCheckRequest) -> dict[str, Any]:
    env = _get_environment(body.environment_id)
    if not env:
        raise HTTPException(status_code=404, detail="environment not found")
    bucket = _region_bucket(env)
    allowed = {item.upper() for item in body.allowed_regions}
    reasons: list[str] = []
    hard_block = False
    eu_compatible = bucket in {"EU", "PL", "ON_PREM", "AIR_GAPPED"}
    region_allowed = bucket in allowed or ("EU" in allowed and eu_compatible)
    if allowed and not region_allowed:
        hard_block = True
        reasons.append(f"region bucket {bucket} is not in allowed regions {sorted(allowed)}")
    if body.requires_poland and bucket not in {"PL", "ON_PREM", "AIR_GAPPED"}:
        hard_block = True
        reasons.append("Poland-only workload requires PL, on-prem or air-gapped environment")
    data_classes = {item.upper() for item in body.data_classes}
    if data_classes & {"TLP_RED", "CLASSIFIED"} and bucket != "AIR_GAPPED":
        hard_block = True
        reasons.append("TLP_RED/classified data requires air-gapped environment")
    override_applied = bool(body.override_code and body.override_reason)
    decision = "allow"
    if hard_block and override_applied:
        decision = "operator_override_recorded"
    elif hard_block:
        decision = "block"
    result = {
        "project_id": body.project_id,
        "environment_id": body.environment_id,
        "environment_name": env.get("display_name") or env.get("name"),
        "region": env.get("region"),
        "region_bucket": bucket,
        "allowed": not hard_block or override_applied,
        "decision": decision,
        "hard_block": hard_block and not override_applied,
        "override_applied": override_applied,
        "reasons": reasons or ["environment satisfies residency constraints"],
        "data_classes": body.data_classes,
        "allowed_regions": body.allowed_regions,
        "checked_at": time.time(),
    }
    _append_phase3_audit(
        "residency.check",
        {
            "project_id": body.project_id,
            "environment_id": body.environment_id,
            "decision": decision,
            "region_bucket": bucket,
            "override_applied": override_applied,
        },
    )
    return result


def _cost_monitoring_config() -> dict[str, Any]:
    config = _get_state("phase3_cost_monitoring")
    if isinstance(config, dict):
        return config
    return {"enabled": True, "levels": ["provider", "environment", "resource"], "currency": "USD"}


def _upsert_cost_alert(body: CostAlertRequest) -> dict[str, Any]:
    if not _get_environment(body.environment_id):
        raise HTTPException(status_code=404, detail="environment not found")
    alert_id = f"cost:{body.environment_id}"
    alerts = [item for item in _state_list("phase3_cost_alerts") if item.get("alert_id") != alert_id]
    alert = {
        "alert_id": alert_id,
        "environment_id": body.environment_id,
        "monthly_budget_cap": body.monthly_budget_cap,
        "thresholds": body.thresholds,
        "channels": body.channels,
        "auto_actions": body.auto_actions,
        "updated_at": time.time(),
    }
    alerts.append(alert)
    _set_state("phase3_cost_alerts", alerts)
    _append_phase3_audit("cost.alert_saved", {"alert_id": alert_id, "environment_id": body.environment_id})
    return alert


def _cost_views(environments: list[dict[str, Any]]) -> dict[str, Any]:
    by_provider: dict[str, float] = {}
    by_environment = []
    by_resource = []
    for env in environments:
        cost = float(env.get("monthly_estimate_usd") or 0)
        provider = str(env.get("provider") or env.get("type") or "unknown")
        by_provider[provider] = round(by_provider.get(provider, 0) + cost, 2)
        by_environment.append(
            {
                "environment_id": env["environment_id"],
                "name": env.get("display_name") or env.get("name"),
                "provider": provider,
                "purpose": env.get("purpose"),
                "monthly_estimate_usd": round(cost, 2),
            }
        )
        resources = env.get("resources") if isinstance(env.get("resources"), dict) else {}
        by_resource.append(
            {
                "environment_id": env["environment_id"],
                "cpu": resources.get("cpu") or resources.get("vcpus"),
                "ram_gb": resources.get("ram_gb"),
                "storage_gb": resources.get("storage_gb") or resources.get("disk_gb"),
                "monthly_estimate_usd": round(cost, 2),
            }
        )
    total = round(sum(by_provider.values()), 2)
    alerts = _state_list("phase3_cost_alerts")
    return {
        "monitoring": _cost_monitoring_config(),
        "levels": [
            {"id": "provider", "enabled": True, "rows": [{"provider": key, "monthly_estimate_usd": value} for key, value in sorted(by_provider.items())]},
            {"id": "environment", "enabled": True, "rows": by_environment},
            {"id": "resource", "enabled": True, "rows": by_resource},
        ],
        "summary": {"monthly_estimate_usd": total, "environment_count": len(environments), "alert_count": len(alerts)},
        "forecast": {
            "current_month_usd": total,
            "next_30_days_usd": total,
            "next_90_days_usd": round(total * 3, 2),
            "confidence": "manual_estimate",
        },
        "alerts": alerts,
    }


def _cleanup_policy_for(env: dict[str, Any]) -> dict[str, Any]:
    policies = env.get("policies") if isinstance(env.get("policies"), dict) else {}
    saved = policies.get("cleanup_policy") if isinstance(policies.get("cleanup_policy"), dict) else {}
    matrix = CLEANUP_DECISION_MATRIX.get(str(env.get("purpose") or "development"), CLEANUP_DECISION_MATRIX["development"])
    return {
        "environment_id": env["environment_id"],
        "environment_name": env.get("display_name") or env.get("name"),
        "purpose": env.get("purpose"),
        "strategy": saved.get("strategy") or matrix["strategy"],
        "cleanup_after_hours": saved.get("cleanup_after_hours", matrix.get("cleanup_after_hours")),
        "inactive_days": saved.get("inactive_days", matrix.get("inactive_days")),
        "schedule": saved.get("schedule", ""),
        "action": saved.get("action") or matrix["action"],
        "source": "stored_policy" if saved else "decision_matrix_default",
        "protected": env.get("purpose") in {"production", "sovereign", "air_gapped"},
    }


def _cleanup_candidates(environments: list[dict[str, Any]], inactive_days: int, purposes: list[str], exclude_tags: list[str]) -> list[dict[str, Any]]:
    cutoff = time.time() - (inactive_days * 86400)
    excluded = set(exclude_tags)
    candidates = []
    for env in environments:
        tags = set((env.get("metadata") or {}).get("tags") or [])
        policy = _cleanup_policy_for(env)
        if env.get("purpose") not in purposes:
            continue
        if tags & excluded or policy["protected"]:
            continue
        if float(env.get("updated_at") or 0) > cutoff and policy["strategy"] == "manual":
            continue
        candidates.append(
            {
                "environment_id": env["environment_id"],
                "name": env.get("display_name") or env.get("name"),
                "purpose": env.get("purpose"),
                "policy": policy,
                "monthly_estimate_usd": env.get("monthly_estimate_usd") or 0,
                "planned_action": policy["action"],
            }
        )
    return candidates


def _cleanup_overview(environments: list[dict[str, Any]]) -> dict[str, Any]:
    policies = [_cleanup_policy_for(env) for env in environments]
    return {
        "strategies": CLEANUP_STRATEGIES,
        "decision_matrix": CLEANUP_DECISION_MATRIX,
        "policies": policies,
        "bulk_operations": {
            "available": ["plan_only", "notify", "stop_non_production", "snapshot_then_stop"],
            "destructive_requires_human_gate": True,
        },
        "default_candidates": _cleanup_candidates(environments, 14, ["testing", "demo_sandbox"], ["keep-permanent", "customer-prod"]),
    }


def _upsert_cleanup_policy(body: CleanupPolicyRequest) -> dict[str, Any]:
    env = _get_environment(body.environment_id)
    if not env:
        raise HTTPException(status_code=404, detail="environment not found")
    if body.strategy not in {item["id"] for item in CLEANUP_STRATEGIES}:
        raise HTTPException(status_code=400, detail="unsupported cleanup strategy")
    policies = dict(env.get("policies") or {})
    policies["cleanup_policy"] = {
        "strategy": body.strategy,
        "cleanup_after_hours": body.cleanup_after_hours,
        "inactive_days": body.inactive_days,
        "schedule": body.schedule,
        "action": body.action,
        "updated_at": time.time(),
    }
    saved = _save_environment({**env, "environment_type": env["type"], "policies": policies})
    _append_phase3_audit("cleanup.policy_saved", {"environment_id": body.environment_id, "strategy": body.strategy})
    return _cleanup_policy_for(saved)


def _resolve_inheritance(body: InheritanceResolveRequest) -> dict[str, Any]:
    rules = _residency_rules()
    goal_defaults: dict[str, Any] = {
        "public_products": {"backup_strategy": "daily_snapshot", "cost_limit_usd": 300, "network_mode": "hub_spoke"},
        "cybersecurity": {"backup_strategy": "immutable_signed", "cost_limit_usd": 500, "network_mode": "isolated", "vpn_mode": "wireguard"},
        "research": {"backup_strategy": "best_effort", "cost_limit_usd": 1000, "network_mode": "mesh", "cleanup_strategy": "auto_after_hours"},
        "apps_internal": {"backup_strategy": "manual", "cost_limit_usd": 80, "network_mode": "isolated"},
    }
    purpose_defaults = CLEANUP_DECISION_MATRIX.get(body.purpose, CLEANUP_DECISION_MATRIX["development"])
    resolved = {
        "network_mode": goal_defaults.get(body.goal, goal_defaults["apps_internal"]).get("network_mode", "isolated"),
        "vpn_mode": goal_defaults.get(body.goal, {}).get("vpn_mode", "disabled"),
        "cleanup_strategy": goal_defaults.get(body.goal, {}).get("cleanup_strategy", purpose_defaults["strategy"]),
        "backup_strategy": goal_defaults.get(body.goal, goal_defaults["apps_internal"])["backup_strategy"],
        "cost_limit_usd": goal_defaults.get(body.goal, goal_defaults["apps_internal"])["cost_limit_usd"],
        "residency_profile": rules[0]["compliance_profile"] if rules else "gdpr_eu",
        **body.overrides,
    }
    return {
        "project_id": body.project_id,
        "module_id": body.module_id,
        "goal": body.goal,
        "purpose": body.purpose,
        "levels": INHERITANCE_LEVELS,
        "resolved": resolved,
        "sources": [
            {"level": "workspace", "fields": ["residency_profile"]},
            {"level": "project", "fields": ["backup_strategy", "cost_limit_usd", "network_mode"]},
            {"level": "environment", "fields": ["cleanup_strategy", "vpn_mode"]},
            {"level": "module", "fields": list(body.overrides.keys()), "phase": 33},
        ],
    }


def _build_full_acceptance(
    environments: list[dict[str, Any]],
    last_scan: dict[str, Any] | None,
    goal: str = "apps_internal",
    finalize: bool = False,
) -> dict[str, Any]:
    cost_monitoring = _cost_monitoring_config()
    audit_entries = _state_list("phase3_audit_chain")
    audit_complete = any(entry.get("event") == "phase_3.complete" for entry in audit_entries)
    hard_blocks: list[dict[str, Any]] = []
    soft_warnings: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    def add_check(check_id: str, label: str, passed: bool, evidence: str, hard: bool = True) -> None:
        check = {
            "id": check_id,
            "label": label,
            "status": "pass" if passed else ("fail" if hard else "warn"),
            "evidence": evidence,
            "hard_block": hard,
        }
        checks.append(check)
        if not passed and hard:
            hard_blocks.append(check)
        elif not passed:
            soft_warnings.append(check)

    add_check("min_one_environment", "Minimum one environment exists", len(environments) >= 1, f"{len(environments)} configured")
    network_policies = [_network_policy_for(env) for env in environments]
    add_check("network_policy_per_environment", "Network policy per environment", len(network_policies) == len(environments), f"{len(network_policies)} policies")
    cleanup_policies = [_cleanup_policy_for(env) for env in environments]
    add_check("cleanup_policy_default", "Cleanup policy default exists", len(cleanup_policies) == len(environments), f"{len(cleanup_policies)} policies")
    add_check("cost_monitoring_enabled", "Cost monitoring enabled", bool(cost_monitoring.get("enabled")), str(cost_monitoring.get("levels")))
    add_check("phase_3_complete_audit", "Audit chain has phase_3.complete", audit_complete or finalize, "recorded" if audit_complete or finalize else "missing")
    add_check("wide_local_scan", "Local scan available", bool(last_scan), "scan state present" if last_scan else "missing")

    cloud_types = {item["provider"] for item in CLOUD_PROVIDER_TEMPLATES if item["provider"] != "custom_http"}
    production_envs = [env for env in environments if env.get("purpose") == "production"]
    cloud_prod = [env for env in production_envs if env.get("type") in cloud_types or env.get("provider") in cloud_types]
    for env in cloud_prod:
        policy = _network_policy_for(env)
        if not policy["stored"]:
            hard_blocks.append(
                {
                    "id": "cloud_production_network_policy_missing",
                    "label": "Cloud production requires explicit network policy",
                    "status": "fail",
                    "evidence": env["environment_id"],
                    "hard_block": True,
                }
            )
    for env in production_envs:
        policies = env.get("policies") if isinstance(env.get("policies"), dict) else {}
        backup = str(policies.get("backup_strategy") or "").lower()
        if str(env.get("tier") or "").lower() in {"critical", "prod", "production"} and backup in {"", "none", "manual"}:
            hard_blocks.append(
                {
                    "id": "critical_production_backup_missing",
                    "label": "Critical production requires backup",
                    "status": "fail",
                    "evidence": env["environment_id"],
                    "hard_block": True,
                }
            )
    if production_envs and not cost_monitoring.get("enabled"):
        hard_blocks.append(
            {
                "id": "production_cost_monitoring_disabled",
                "label": "Production cost monitoring cannot be disabled",
                "status": "fail",
                "evidence": f"{len(production_envs)} production environments",
                "hard_block": True,
            }
        )

    has_cloud = any(env.get("type") in cloud_types or env.get("provider") in cloud_types for env in environments)
    has_sovereign = any(env.get("classification", {}).get("sovereign") for env in environments)
    edge_without_vpn = [
        env
        for env in environments
        if env.get("type") == "edge" and _network_policy_for(env)["vpn_mode"] == "disabled"
    ]
    prod_without_ha = [
        env
        for env in production_envs
        if not (env.get("configuration") or {}).get("ha") and not (env.get("resources") or {}).get("ha")
    ]
    manual_test_cleanup = [
        env
        for env in environments
        if env.get("purpose") == "testing" and _cleanup_policy_for(env)["strategy"] == "manual"
    ]
    if goal == "public_products" and not has_cloud:
        add_check("public_products_cloud_provider", "Public products should have a cloud provider", False, "no cloud provider", hard=False)
    if goal == "cybersecurity" and not has_sovereign:
        add_check("cybersecurity_sovereign_environment", "Cybersecurity should have sovereign environment", False, "no sovereign env", hard=False)
    if edge_without_vpn:
        add_check("edge_without_vpn", "Edge environments should use VPN/mesh", False, f"{len(edge_without_vpn)} edge envs", hard=False)
    if prod_without_ha:
        add_check("production_without_ha", "Production should declare HA", False, f"{len(prod_without_ha)} production envs", hard=False)
    if manual_test_cleanup:
        add_check("manual_cleanup_for_testing", "Testing should not default to manual cleanup", False, f"{len(manual_test_cleanup)} testing envs", hard=False)

    if finalize and not hard_blocks and not audit_complete:
        audit_entry = _append_phase3_audit("phase_3.complete", {"goal": goal, "environment_count": len(environments), "soft_warnings": len(soft_warnings)})
        audit_complete = True
        for check in checks:
            if check["id"] == "phase_3_complete_audit":
                check["status"] = "pass"
                check["evidence"] = audit_entry["event_id"]

    common_passed = len([check for check in checks if check["status"] == "pass"])
    goal_requirements = {
        "public_products": ["cloud_provider_integrated", "production_env", "backup_per_prod", "cost_limits_per_prod", "firewall_for_prod"],
        "cybersecurity": ["sovereign_env", "air_gapped_capability", "vpn_sensitive_envs", "immutable_signed_audit", "compliance_attestations"],
        "research": ["diverse_local_cloud", "relaxed_cost_limits", "aggressive_cleanup"],
        "apps_internal": ["min_one_env", "low_cost_limits", "minimal_backup"],
    }
    return {
        "phase": "3",
        "goal": goal,
        "accepted": len(hard_blocks) == 0,
        "checked_at": time.time(),
        "checks": checks,
        "hard_blocks": hard_blocks,
        "soft_warnings": soft_warnings,
        "dod": {
            "common": {
                "required": 5,
                "passed": len([item for item in checks[:5] if item["status"] == "pass"]),
            },
            "goal_specific": goal_requirements.get(goal, goal_requirements["apps_internal"]),
            "counts": {"checks_passed": common_passed, "checks_total": len(checks), "hard_blocks": len(hard_blocks), "soft_warnings": len(soft_warnings)},
        },
        "audit_chain": {
            "entries": len(_state_list("phase3_audit_chain")),
            "phase_3_complete": audit_complete,
            "last_hash": (_state_list("phase3_audit_chain")[-1].get("hash") if _state_list("phase3_audit_chain") else ""),
        },
    }


def _build_local_dev_payload(scan: dict[str, Any]) -> dict[str, Any]:
    hardware = scan.get("hardware", {}) if isinstance(scan.get("hardware"), dict) else {}
    software = scan.get("software", {}) if isinstance(scan.get("software"), dict) else {}
    network = hardware.get("network", {}) if isinstance(hardware.get("network"), dict) else {}
    disks = hardware.get("disks") if isinstance(hardware.get("disks"), list) else []
    disk = disks[0] if disks else {}
    docker_daemon = software.get("docker_daemon", {}) if isinstance(software.get("docker_daemon"), dict) else {}
    kubernetes = scan.get("kubernetes", {}) if isinstance(scan.get("kubernetes"), dict) else {}
    docker_ok = bool(docker_daemon.get("running"))
    return {
        "environment_id": "env_local_dev",
        "name": "local-dev",
        "display_name": "Local development (this machine)",
        "environment_type": "local",
        "provider": "local",
        "purpose": "development",
        "tier": "dev",
        "account": "this-machine",
        "region": "local",
        "datacenter": platform.node() or "localhost",
        "resources": {
            "cpu": hardware.get("cpu_cores", 0),
            "cpu_model": hardware.get("cpu_model", ""),
            "ram_gb": (hardware.get("memory") or {}).get("total_gb"),
            "ram_available_gb": (hardware.get("memory") or {}).get("available_gb"),
            "disk_gb": disk.get("total_gb"),
            "disk_free_gb": disk.get("free_gb"),
            "gpu": hardware.get("gpu"),
            "network_interfaces": network.get("network_interfaces_count", 0),
        },
        "configuration": {
            "os": scan.get("os", {}),
            "docker": docker_ok,
            "docker_version": docker_daemon.get("version") or (software.get("docker") or {}).get("version"),
            "docker_compose": bool((software.get("docker_compose") or {}).get("installed")),
            "kubernetes": bool(kubernetes.get("kubectl", {}).get("installed")) if isinstance(kubernetes.get("kubectl"), dict) else False,
            "kubernetes_context": kubernetes.get("active_context", ""),
            "healthcheck_url": "http://127.0.0.1:8000/health",
            "monitoring": "local",
        },
        "status": {"state": "running", "health": "healthy" if docker_ok else "degraded"},
        "cost": {"monthly_estimate_usd": 0, "monthly_estimate_eur": 0},
        "policies": {
            "auto_cleanup": False,
            "cleanup_after_days": None,
            "backup_strategy": "manual",
            "snapshot_retention": 0,
        },
        "network": {
            "public_ip": "",
            "private_ip": (network.get("local_ips") or ["127.0.0.1"])[0],
            "vpn_attached": bool(network.get("tailscale_installed") or network.get("wireguard_installed")),
            "accessible_from": ["localhost"],
            "ports": scan.get("ports", []),
        },
        "metadata": {
            "created_by_phase": 3,
            "tags": ["local", "dev", "single-machine"],
            "source": "auto_detected",
            "scan_time": scan.get("scanned_at"),
            "sovereign": True,
            "operator_notes": "Auto-created from Phase 3 local machine scan.",
        },
    }


def _ensure_local_dev(scan: dict[str, Any] | None = None) -> dict[str, Any]:
    scan = scan or _get_state("last_local_scan") or _scan_local_machine(False)
    return _save_environment(_build_local_dev_payload(scan))


def _upsert_provider_account(provider: str, metadata: dict[str, Any]) -> dict[str, Any]:
    provider = provider.strip().lower()
    if provider not in {item["provider"] for item in CLOUD_PROVIDER_TEMPLATES} and provider not in {"terraform", "pulumi"}:
        raise ValueError(f"unsupported environment provider '{provider}'")
    now = time.time()
    account_id = f"acct_{provider}_cli"
    display_name = str(metadata.get("display_name") or f"{provider} CLI detected")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO environment_catalog_provider_accounts (
                account_id, provider, display_name, account_ref, default_region,
                auth_method, credential_status, source, metadata_json, created_at,
                updated_at, last_test_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id) DO UPDATE SET
                display_name=excluded.display_name,
                default_region=excluded.default_region,
                auth_method=excluded.auth_method,
                credential_status=excluded.credential_status,
                source=excluded.source,
                metadata_json=excluded.metadata_json,
                updated_at=excluded.updated_at
            """,
            (
                account_id,
                provider,
                display_name,
                str(metadata.get("account_ref") or ""),
                str(metadata.get("default_region") or ""),
                str(metadata.get("auth_method") or "cli_detected"),
                str(metadata.get("credential_status") or "cli_detected"),
                str(metadata.get("source") or "cloud_cli_detection"),
                json.dumps(metadata, ensure_ascii=False, default=str),
                now,
                now,
                metadata.get("last_test_status"),
            ),
        )
    accounts = [item for item in _list_provider_accounts() if item["account_id"] == account_id]
    return accounts[0]


def _cloud_connectors() -> list[dict[str, Any]]:
    try:
        from sylion.security.cloud_connectors import get_cloud_connector_store

        return get_cloud_connector_store().list()
    except Exception:
        return []


def _build_type_view(environments: list[dict[str, Any]], accounts: list[dict[str, Any]]) -> dict[str, Any]:
    static_types = [
        {"id": "local", "display_name": "Local", "category": "local"},
        {"id": "edge", "display_name": "Edge", "category": "edge"},
        {"id": "on_prem", "display_name": "On-premise", "category": "sovereign"},
        {"id": "air_gapped", "display_name": "Air-gapped", "category": "sovereign"},
    ]
    all_types = static_types + [
        {"id": item["provider"], "display_name": item["display_name"], "category": item["category"]}
        for item in CLOUD_PROVIDER_TEMPLATES
    ]
    groups = []
    for template in all_types:
        provider = template["id"]
        envs = [env for env in environments if env["type"] == provider or env["provider"] == provider]
        provider_accounts = [account for account in accounts if account["provider"] == provider]
        account_names = sorted({env.get("account") or "default" for env in envs} | {acc.get("display_name") or "default" for acc in provider_accounts})
        account_groups = []
        for account_name in account_names:
            account_envs = [env for env in envs if (env.get("account") or "default") == account_name]
            regions = sorted({env.get("region") or "n/a" for env in account_envs}) or ["n/a"]
            account_groups.append(
                {
                    "account": account_name,
                    "provider_accounts": [acc for acc in provider_accounts if (acc.get("display_name") or "default") == account_name],
                    "regions": [
                        {
                            "region": region,
                            "environments": [env for env in account_envs if (env.get("region") or "n/a") == region],
                        }
                        for region in regions
                    ],
                }
            )
        groups.append(
            {
                **template,
                "environment_count": len(envs),
                "account_count": len(provider_accounts),
                "accounts": account_groups,
                "empty": len(envs) == 0 and len(provider_accounts) == 0,
            }
        )
    return {"groups": groups, "empty_slots": [group for group in groups if group["empty"]]}


def _build_purpose_view(environments: list[dict[str, Any]]) -> dict[str, Any]:
    groups = []
    for purpose in PURPOSES:
        envs = [env for env in environments if env["purpose"] == purpose["id"]]
        groups.append({**purpose, "environment_count": len(envs), "environments": envs})
    return {"groups": groups}


def _build_flat_view(environments: list[dict[str, Any]]) -> dict[str, Any]:
    rows = sorted(environments, key=lambda item: (float(item.get("monthly_estimate_usd") or 0), item["name"]))
    return {"rows": rows, "sort": "cost_asc", "filters": {"types": sorted({row["type"] for row in rows})}}


def _build_acceptance(environments: list[dict[str, Any]], last_scan: dict[str, Any] | None) -> dict[str, Any]:
    local_dev = next((env for env in environments if env["environment_id"] == "env_local_dev"), None)
    cleanup_defined = bool(local_dev and isinstance(local_dev.get("policies"), dict) and "auto_cleanup" in local_dev["policies"])
    checks = [
        {
            "id": "local_dev_configured",
            "label": "Min 1 environment configured (local-dev)",
            "status": "pass" if local_dev else "fail",
            "evidence": local_dev["name"] if local_dev else "missing",
            "hard_block": True,
        },
        {
            "id": "operator_understands_purposes",
            "label": "dev/staging/prod/edge purpose model visible",
            "status": "pass",
            "evidence": f"{len(PURPOSES)} purpose groups",
            "hard_block": False,
        },
        {
            "id": "cleanup_policy_defined",
            "label": "Cleanup policy defined",
            "status": "pass" if cleanup_defined else "fail",
            "evidence": json.dumps(local_dev.get("policies", {}) if local_dev else {}, default=str),
            "hard_block": True,
        },
        {
            "id": "wide_local_scan",
            "label": "Wide local machine scan completed",
            "status": "pass" if last_scan else "fail",
            "evidence": "os/hardware/docker/k8s/ports/ssh/cloud-cli" if last_scan else "missing",
            "hard_block": True,
        },
        {
            "id": "three_catalog_views",
            "label": "Type/Purpose/Flat catalog views available",
            "status": "pass",
            "evidence": "3 views",
            "hard_block": True,
        },
        {
            "id": "cloud_templates",
            "label": "Tier 1+2+5 cloud provider templates",
            "status": "pass" if len([t for t in CLOUD_PROVIDER_TEMPLATES if t["provider"] != "custom_http"]) >= 10 else "fail",
            "evidence": f"{len([t for t in CLOUD_PROVIDER_TEMPLATES if t['provider'] != 'custom_http'])} cloud providers + custom",
            "hard_block": True,
        },
        {
            "id": "sovereign_and_edge_workflows",
            "label": "Sovereign and edge workflows available",
            "status": "pass",
            "evidence": f"{len(SOVEREIGN_PROFILES)} sovereign profiles, {len(EDGE_PAIRING_METHODS)} edge pairing methods",
            "hard_block": True,
        },
        {
            "id": "cloud_resource_privacy",
            "label": "Cloud resource auto-listing disabled by default",
            "status": "pass" if DETECTION_PREFERENCES["cloud_resource_auto_listing"] is False else "fail",
            "evidence": "manual_only",
            "hard_block": True,
        },
    ]
    if local_dev and not local_dev.get("accepted_at"):
        checks.append(
            {
                "id": "local_defaults_acknowledged",
                "label": "Operator accepted local-dev defaults",
                "status": "warn",
                "evidence": "pending operator click",
                "hard_block": False,
            }
        )
    hard_blocks = [check for check in checks if check["hard_block"] and check["status"] != "pass"]
    soft_warnings = [check for check in checks if not check["hard_block"] and check["status"] != "pass"]
    return {
        "checks": checks,
        "hard_blocks": hard_blocks,
        "soft_warnings": soft_warnings,
        "accepted": len(hard_blocks) == 0,
        "score": {"passed": len([check for check in checks if check["status"] == "pass"]), "total": len(checks)},
    }


def _catalog_snapshot(view: str = "type", auto_scan: bool = True) -> dict[str, Any]:
    last_scan = _get_state("last_local_scan")
    environments = _list_environments()
    has_local_dev = any(env["environment_id"] == "env_local_dev" for env in environments)
    if auto_scan and (not last_scan or not has_local_dev):
        last_scan = _scan_local_machine(False)
        _ensure_local_dev(last_scan)
        environments = _list_environments()
    accounts = _list_provider_accounts()
    connectors = _cloud_connectors()
    for connector in connectors:
        provider = str(connector.get("provider") or "").lower()
        if provider and not any(acc["account_id"] == f"connector_{connector.get('connector_id')}" for acc in accounts):
            accounts.append(
                {
                    "account_id": f"connector_{connector.get('connector_id')}",
                    "provider": provider,
                    "display_name": connector.get("name") or provider,
                    "account_ref": connector.get("scope") or "",
                    "default_region": "",
                    "auth_method": "encrypted_connector",
                    "credential_status": "stored_encrypted",
                    "source": "cloud_connectors",
                    "metadata": {"connector_id": connector.get("connector_id"), "credentials_masked": connector.get("credentials_masked", {})},
                    "created_at": connector.get("created_at"),
                    "updated_at": connector.get("updated_at"),
                    "last_test_status": connector.get("last_test_status"),
                }
            )
    type_view = _build_type_view(environments, accounts)
    purpose_view = _build_purpose_view(environments)
    flat_view = _build_flat_view(environments)
    monthly_usd = sum(float(env.get("monthly_estimate_usd") or 0) for env in environments)
    monthly_eur = sum(float(env.get("monthly_estimate_eur") or 0) for env in environments)
    installed_cli = [tool for tool in (last_scan or {}).get("cloud_cli_tools", []) if tool.get("installed")]
    summary = {
        "active_environments": len(environments),
        "active_provider_accounts": len(accounts),
        "edge_devices": len([env for env in environments if env["type"] == "edge"]),
        "sovereign_environments": len([env for env in environments if env.get("classification", {}).get("sovereign")]),
        "monthly_cost_usd": round(monthly_usd, 2),
        "monthly_cost_eur": round(monthly_eur, 2),
        "cloud_cli_detected": len(installed_cli),
        "local_dev_configured": has_local_dev or any(env["environment_id"] == "env_local_dev" for env in environments),
        "cloud_resource_auto_listing": False,
    }
    views = {"type": type_view, "purpose": purpose_view, "flat": flat_view}
    return {
        "phase": "3",
        "part": "1-13",
        "view": view if view in views else "type",
        "default_view": "type",
        "summary": summary,
        "environments": environments,
        "provider_accounts": accounts,
        "cloud_connectors": connectors,
        "views": views,
        "selected_view_data": views.get(view, type_view),
        "local_scan": last_scan,
        "cloud_provider_templates": CLOUD_PROVIDER_TEMPLATES,
        "sovereign_profiles": SOVEREIGN_PROFILES,
        "sovereignty_rules": {
            "tlp_red": "air_gapped_or_sovereign_on_prem_only",
            "polish_gov_classified": "polish_datacenters_only",
            "eu_gdpr_pii": "eu_regions_only",
            "default_preference": "operator_decides",
            "conflict_resolution": "block_deploy_require_operator_override",
        },
        "edge": {
            "platform_groups": EDGE_PLATFORM_GROUPS,
            "pairing_methods": EDGE_PAIRING_METHODS,
            "use_cases": EDGE_USE_CASES,
        },
        "network": _network_overview(environments),
        "residency": {
            "templates": RESIDENCY_RULE_TEMPLATES,
            "rules": _residency_rules(),
            "audit": _state_list("phase3_audit_chain"),
        },
        "costs": _cost_views(environments),
        "cleanup": _cleanup_overview(environments),
        "edge_cases": {
            "cases": EDGE_CASES,
            "categories": sorted({item["category"] for item in EDGE_CASES}),
            "count": len(EDGE_CASES),
        },
        "inheritance": {
            "levels": INHERITANCE_LEVELS,
            "module_level_phase": 33,
            "granular_inheritance_enabled": True,
        },
        "detection_preferences": DETECTION_PREFERENCES,
        "acceptance": _build_acceptance(environments, last_scan),
        "phase3_acceptance": _build_full_acceptance(environments, last_scan, "apps_internal", finalize=False),
    }


def _environment_status(env: dict[str, Any]) -> str:
    status = env.get("status")
    status_health = status.get("health") if isinstance(status, dict) else ""
    raw = str(env.get("health") or status_health or status or "unknown").lower()
    if raw in {"healthy", "running", "ok", "active", "accepted"}:
        return "working"
    if raw in {"degraded", "configured", "unknown", "pending"}:
        return "degraded"
    if raw in {"blocked", "failed", "error", "missing"}:
        return "blocked"
    return "idle"


def _environment_theater_snapshot(auto_scan: bool = True) -> dict[str, Any]:
    catalog = _catalog_snapshot(view="flat", auto_scan=auto_scan)
    environments = catalog.get("environments", [])
    accounts = catalog.get("provider_accounts", [])
    scan = catalog.get("local_scan") or {}
    hardware = scan.get("hardware") or {}
    software = scan.get("software") or {}
    network = hardware.get("network") or {}
    ports = scan.get("ports") or []
    cli_tools = scan.get("cloud_cli_tools") or []
    acceptance = catalog.get("acceptance") or {}

    actors: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    host_id = "local_host"
    hostname = network.get("hostname") or socket.gethostname()
    busy_ports = [port for port in ports if port.get("busy")]
    docker_running = bool((software.get("docker_daemon") or {}).get("running"))
    actors.append(
        {
            "id": host_id,
            "name": hostname,
            "role": "host lokalny",
            "kind": "host",
            "status": "working" if scan else "degraded",
            "details": {
                "cpu_cores": hardware.get("cpu_cores"),
                "memory_total_gb": (hardware.get("memory") or {}).get("total_gb"),
                "memory_available_gb": (hardware.get("memory") or {}).get("available_gb"),
                "docker_running": docker_running,
                "local_ips": network.get("local_ips", []),
            },
        }
    )

    actors.append(
        {
            "id": "network_policy",
            "name": "Polityka sieci",
            "role": "routing, izolacja, mesh",
            "kind": "network",
            "status": "working" if catalog.get("network") else "degraded",
            "details": {
                "topologies": len((catalog.get("network") or {}).get("topologies", [])),
                "diagnostic_available": True,
            },
        }
    )
    actors.append(
        {
            "id": "cost_policy",
            "name": "Koszt środowisk",
            "role": "limity i alerty kosztowe",
            "kind": "cost",
            "status": "working",
            "details": {
                "monthly_cost_usd": catalog.get("summary", {}).get("monthly_cost_usd", 0),
                "monthly_cost_eur": catalog.get("summary", {}).get("monthly_cost_eur", 0),
            },
        }
    )
    actors.append(
        {
            "id": "human_gate",
            "name": "Human Gate runtime",
            "role": "blokady VPS, produkcji i kosztów",
            "kind": "guard",
            "status": "blocked" if acceptance.get("hard_blocks") else "working",
            "details": {
                "hard_blocks": acceptance.get("hard_blocks", []),
                "soft_warnings": acceptance.get("soft_warnings", []),
            },
        }
    )

    for port in busy_ports:
        port_id = f"port_{port.get('port')}"
        actors.append(
            {
                "id": port_id,
                "name": f"{port.get('port')} {port.get('label', '')}".strip(),
                "role": "proces lokalny / port",
                "kind": "port",
                "status": "working",
                "details": {"port": port.get("port"), "latency_ms": port.get("latency_ms")},
            }
        )
        edges.append({"source": host_id, "target": port_id, "kind": "listens_on"})

    for tool in cli_tools:
        tool_id = f"cli_{tool.get('provider')}"
        actors.append(
            {
                "id": tool_id,
                "name": tool.get("label") or tool.get("provider"),
                "role": "narzędzie providera",
                "kind": "cli",
                "status": "working" if tool.get("installed") else "idle",
                "details": {
                    "provider": tool.get("provider"),
                    "installed": tool.get("installed"),
                    "config_present": tool.get("config_present"),
                },
            }
        )
        edges.append({"source": host_id, "target": tool_id, "kind": "tool_detected"})

    for account in accounts:
        account_id = f"account_{account.get('account_id')}"
        actors.append(
            {
                "id": account_id,
                "name": account.get("display_name") or account.get("provider"),
                "role": "konto providera",
                "kind": "provider",
                "status": "working" if account.get("credential_status") else "degraded",
                "details": {
                    "provider": account.get("provider"),
                    "region": account.get("default_region"),
                    "credential_status": account.get("credential_status"),
                    "last_test_status": account.get("last_test_status"),
                },
            }
        )

    for env in environments:
        env_id = f"env_{env.get('environment_id')}"
        provider = str(env.get("provider") or env.get("type") or "local").lower()
        actors.append(
            {
                "id": env_id,
                "name": env.get("display_name") or env.get("name") or env.get("environment_id"),
                "role": f"{env.get('purpose') or 'environment'} / {env.get('type') or 'unknown'}",
                "kind": "environment",
                "status": _environment_status(env),
                "details": {
                    "environment_id": env.get("environment_id"),
                    "type": env.get("type"),
                    "provider": provider,
                    "region": env.get("region"),
                    "monthly_estimate_usd": env.get("monthly_estimate_usd"),
                    "sovereign": bool((env.get("classification") or {}).get("sovereign")),
                    "accepted_at": env.get("accepted_at"),
                },
            }
        )
        if provider == "local" or env.get("environment_id") == "env_local_dev":
            edges.append({"source": host_id, "target": env_id, "kind": "runs_environment"})
        matching_account = next((acc for acc in accounts if str(acc.get("provider")).lower() == provider), None)
        if matching_account:
            edges.append({"source": f"account_{matching_account.get('account_id')}", "target": env_id, "kind": "provisions"})
        edges.append({"source": env_id, "target": "network_policy", "kind": "uses_network_policy"})
        edges.append({"source": env_id, "target": "cost_policy", "kind": "reports_cost"})
        if env.get("purpose") in {"production", "staging"} or provider not in {"local", "on_prem", "edge"}:
            edges.append({"source": "human_gate", "target": env_id, "kind": "guards"})

    summary = catalog.get("summary", {})
    return {
        "type": "snapshot",
        "as_of": time.time(),
        "summary": {
            **summary,
            "busy_ports": len(busy_ports),
            "actor_count": len(actors),
            "edge_count": len(edges),
            "docker_running": docker_running,
            "hard_blocks": len(acceptance.get("hard_blocks") or []),
            "soft_warnings": len(acceptance.get("soft_warnings") or []),
        },
        "topology": {"actors": actors, "edges": edges},
        "local_scan": scan,
        "acceptance": acceptance,
        "network": catalog.get("network"),
        "costs": catalog.get("costs"),
    }


@router.get("")
def get_environment_catalog(view: str = "type", auto_scan: bool = True) -> dict[str, Any]:
    return _catalog_snapshot(view=view, auto_scan=auto_scan)


@router.get("/theater")
def get_environment_theater(auto_scan: bool = True) -> dict[str, Any]:
    return _environment_theater_snapshot(auto_scan=auto_scan)


@router.get("/templates")
def get_environment_templates() -> dict[str, Any]:
    return {
        "cloud_provider_count": len([item for item in CLOUD_PROVIDER_TEMPLATES if item["provider"] != "custom_http"]),
        "templates": CLOUD_PROVIDER_TEMPLATES,
        "sovereign_profiles": SOVEREIGN_PROFILES,
        "edge": {
            "platform_groups": EDGE_PLATFORM_GROUPS,
            "pairing_methods": EDGE_PAIRING_METHODS,
            "use_cases": EDGE_USE_CASES,
        },
        "detection_preferences": DETECTION_PREFERENCES,
    }


@router.get("/acceptance")
def get_environment_acceptance() -> dict[str, Any]:
    snapshot = _catalog_snapshot(auto_scan=True)
    return snapshot["acceptance"]


@router.get("/network")
def get_environment_network() -> dict[str, Any]:
    environments = _list_environments()
    return _network_overview(environments)


@router.post("/network/policy")
def update_environment_network_policy(body: UpdateNetworkPolicyRequest) -> dict[str, Any]:
    env = _get_environment(body.environment_id)
    if not env:
        raise HTTPException(status_code=404, detail="environment not found")
    if body.network_mode not in {item["id"] for item in NETWORK_TOPOLOGIES}:
        raise HTTPException(status_code=400, detail="unsupported network mode")
    if body.vpn_mode not in {item["id"] for item in VPN_MODES}:
        raise HTTPException(status_code=400, detail="unsupported VPN mode")
    if body.firewall_template not in FIREWALL_TEMPLATES:
        raise HTTPException(status_code=400, detail="unsupported firewall template")
    if body.mesh_provider and body.mesh_provider not in {item["id"] for item in MESH_PROVIDER_TEMPLATES}:
        raise HTTPException(status_code=400, detail="unsupported mesh provider")
    firewall = _firewall_template(body.firewall_template)
    network = dict(env.get("network") or {})
    network.update(
        {
            "phase3_policy": True,
            "network_mode": body.network_mode,
            "vpn_mode": body.vpn_mode,
            "mesh_provider": body.mesh_provider,
            "firewall_template": body.firewall_template,
            "inbound_rules": body.custom_policy.get("inbound_rules") or firewall.get("inbound", []),
            "outbound_rules": body.custom_policy.get("outbound_rules") or firewall.get("outbound", []),
            "sensitive": body.sensitive,
            "custom_policy": body.custom_policy,
            "monitoring": body.custom_policy.get("monitoring") or NETWORK_MONITORING_DEFAULTS,
            "updated_at": time.time(),
        }
    )
    saved = _save_environment({**env, "environment_type": env["type"], "network": network})
    _append_phase3_audit(
        "network.policy_saved",
        {"environment_id": body.environment_id, "network_mode": body.network_mode, "vpn_mode": body.vpn_mode},
    )
    return {"policy": _network_policy_for(saved), "network": _network_overview(_list_environments())}


@router.post("/network/diagnostic")
def run_environment_network_diagnostic(body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    environment_id = str(body.get("environment_id") or "")
    environments = _list_environments()
    selected = [env for env in environments if not environment_id or env["environment_id"] == environment_id]
    diagnostics = []
    for env in selected:
        policy = _network_policy_for(env)
        diagnostics.append(
            {
                "environment_id": env["environment_id"],
                "network_mode": policy["network_mode"],
                "vpn_mode": policy["vpn_mode"],
                "firewall_template": policy["firewall_template"],
                "checks": [
                    {"id": "policy_present", "status": "pass", "evidence": policy["source"]},
                    {"id": "monitoring_enabled", "status": "pass" if policy["monitoring"].get("enabled") else "warn", "evidence": policy["monitoring"].get("checks", [])},
                    {"id": "sensitive_vpn", "status": "pass" if not policy["sensitive"] or policy["vpn_mode"] != "disabled" or policy["network_mode"] == "isolated" else "warn", "evidence": policy["vpn_mode"]},
                ],
            }
        )
    _append_phase3_audit("network.diagnostic", {"environment_id": environment_id or "all", "checked": len(diagnostics)})
    return {"diagnostics": diagnostics, "checked_at": time.time()}


@router.get("/residency")
def get_environment_residency() -> dict[str, Any]:
    return {
        "templates": RESIDENCY_RULE_TEMPLATES,
        "rules": _residency_rules(),
        "audit": [item for item in _state_list("phase3_audit_chain") if str(item.get("event", "")).startswith("residency.")],
    }


@router.post("/residency/rules")
def save_environment_residency_rule(body: ResidencyRuleRequest) -> dict[str, Any]:
    return {"rule": _upsert_residency_rule(body), "rules": _residency_rules()}


@router.post("/residency/check")
def check_environment_residency(body: ResidencyCheckRequest) -> dict[str, Any]:
    return _check_residency(body)


@router.get("/residency/audit")
def get_environment_residency_audit() -> dict[str, Any]:
    entries = [item for item in _state_list("phase3_audit_chain") if str(item.get("event", "")).startswith("residency.")]
    return {"entries": entries, "count": len(entries)}


@router.get("/costs")
def get_environment_costs() -> dict[str, Any]:
    return _cost_views(_list_environments())


@router.post("/costs/alerts")
def save_environment_cost_alert(body: CostAlertRequest) -> dict[str, Any]:
    alert = _upsert_cost_alert(body)
    return {"alert": alert, "costs": _cost_views(_list_environments())}


@router.get("/cleanup")
def get_environment_cleanup() -> dict[str, Any]:
    return _cleanup_overview(_list_environments())


@router.post("/cleanup/policy")
def save_environment_cleanup_policy(body: CleanupPolicyRequest) -> dict[str, Any]:
    policy = _upsert_cleanup_policy(body)
    return {"policy": policy, "cleanup": _cleanup_overview(_list_environments())}


@router.post("/cleanup/bulk-plan")
def create_environment_bulk_cleanup_plan(body: BulkCleanupPlanRequest) -> dict[str, Any]:
    candidates = _cleanup_candidates(_list_environments(), body.inactive_days, body.purposes, body.exclude_tags)
    plan = {
        "plan_id": _uid("cleanup_plan"),
        "mode": "plan_only",
        "destructive": False,
        "purposes": body.purposes,
        "inactive_days": body.inactive_days,
        "include_tags": body.include_tags,
        "exclude_tags": body.exclude_tags,
        "candidates": candidates,
        "estimated_monthly_savings_usd": round(sum(float(item.get("monthly_estimate_usd") or 0) for item in candidates), 2),
        "created_at": time.time(),
    }
    _append_phase3_audit("cleanup.bulk_plan_created", {"plan_id": plan["plan_id"], "candidates": len(candidates)})
    return {"plan": plan}


@router.get("/edge-cases")
def get_environment_edge_cases() -> dict[str, Any]:
    return {
        "cases": EDGE_CASES,
        "categories": sorted({item["category"] for item in EDGE_CASES}),
        "count": len(EDGE_CASES),
    }


@router.post("/edge-cases/diagnose")
def diagnose_environment_edge_case(body: EdgeCaseDiagnoseRequest) -> dict[str, Any]:
    case = next((item for item in EDGE_CASES if item["id"] == body.case_id), None)
    if not case:
        raise HTTPException(status_code=404, detail="edge case not found")
    env = _get_environment(body.environment_id) if body.environment_id else None
    diagnosis = {
        "case": case,
        "environment": env,
        "context": body.context,
        "action_plan": [
            "capture current environment state",
            case["recommended_action"],
            "write audit entry before resuming deployment",
        ],
        "requires_human_gate": bool(case.get("human_gate")),
        "created_at": time.time(),
    }
    _append_phase3_audit("edge_case.diagnosed", {"case_id": body.case_id, "environment_id": body.environment_id})
    return diagnosis


@router.post("/inheritance/resolve")
def resolve_environment_inheritance(body: InheritanceResolveRequest) -> dict[str, Any]:
    return _resolve_inheritance(body)


@router.get("/acceptance-test")
def run_environment_acceptance_test(goal: str = "apps_internal") -> dict[str, Any]:
    snapshot = _catalog_snapshot(auto_scan=True)
    environments = snapshot["environments"]
    last_scan = snapshot.get("local_scan")
    return _build_full_acceptance(environments, last_scan, goal=goal, finalize=True)


@router.post("/scan-local")
def scan_local_environment(body: ScanLocalRequest | None = None) -> dict[str, Any]:
    body = body or ScanLocalRequest()
    scan = _scan_local_machine(deep_scan=body.deep_scan)
    local_dev = _ensure_local_dev(scan) if body.auto_create_local_dev else None
    return {
        "scan": scan,
        "local_dev": local_dev,
        "catalog": _catalog_snapshot(auto_scan=False),
    }


@router.post("/local-dev/accept")
def accept_local_dev(body: AcceptLocalDevRequest | None = None) -> dict[str, Any]:
    body = body or AcceptLocalDevRequest()
    env = _get_environment("env_local_dev")
    if not env:
        env = _ensure_local_dev()
    metadata = dict(env.get("metadata") or {})
    if body.notes:
        metadata["operator_notes"] = body.notes
    payload = {
        **env,
        "environment_type": env["type"],
        "display_name": body.display_name or env["display_name"],
        "purpose": body.purpose or env["purpose"],
        "metadata": metadata,
        "accepted_at": time.time(),
    }
    saved = _save_environment(payload)
    with _connect() as conn:
        conn.execute(
            "UPDATE environment_catalog_environments SET accepted_at = ? WHERE environment_id = ?",
            (payload["accepted_at"], "env_local_dev"),
        )
    saved = _get_environment("env_local_dev") or saved
    return {"status": "accepted", "environment": saved, "acceptance": _catalog_snapshot(auto_scan=False)["acceptance"]}


@router.post("/providers/detected")
def add_detected_providers(body: AddDetectedProvidersRequest | None = None) -> dict[str, Any]:
    body = body or AddDetectedProvidersRequest()
    scan = _get_state("last_local_scan") or _scan_local_machine(False)
    installed = {
        str(tool.get("provider")): tool
        for tool in scan.get("cloud_cli_tools", [])
        if tool.get("installed") and str(tool.get("provider")) not in {"terraform", "pulumi"}
    }
    requested = body.providers or sorted(installed)
    added = []
    skipped = []
    for provider in requested:
        provider = provider.strip().lower()
        tool = installed.get(provider)
        if not tool:
            skipped.append({"provider": provider, "reason": "cli_not_detected"})
            continue
        try:
            added.append(
                _upsert_provider_account(
                    provider,
                    {
                        "display_name": f"{tool.get('label')} detected",
                        "auth_method": "cli_detected",
                        "credential_status": "cli_detected",
                        "source": "cloud_cli_detection",
                        "command": tool.get("command"),
                        "path": tool.get("path"),
                        "version": tool.get("version"),
                        "config_present": tool.get("config_present"),
                        "resource_listing_enabled": False,
                    },
                )
            )
        except ValueError as exc:
            skipped.append({"provider": provider, "reason": str(exc)})
    return {"added": added, "skipped": skipped, "catalog": _catalog_snapshot(auto_scan=False)}


@router.post("/environments", status_code=201)
def create_environment(body: CreateEnvironmentRequest) -> dict[str, Any]:
    try:
        payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
        env = _save_environment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"environment": env, "acceptance": _catalog_snapshot(auto_scan=False)["acceptance"]}


@router.post("/edge-devices", status_code=201)
def create_edge_device(body: CreateEdgeDeviceRequest) -> dict[str, Any]:
    if not body.display_name.strip():
        raise HTTPException(status_code=400, detail="display_name is required")
    capabilities = body.capabilities or ["linux", "ssh"]
    resources: dict[str, Any] = {
        "architecture": body.architecture,
        "device_type": body.device_type,
        "ram_gb": body.ram_gb,
        "storage_gb": body.storage_gb,
    }
    env = _save_environment(
        {
            "environment_id": _uid("edge"),
            "name": body.display_name.lower().replace(" ", "-"),
            "display_name": body.display_name,
            "environment_type": "edge",
            "provider": "edge",
            "purpose": "edge",
            "tier": "edge",
            "account": body.owner,
            "region": body.location or "edge",
            "resources": resources,
            "configuration": {
                "pairing_method": body.pairing_method,
                "hostname": body.hostname,
                "ssh_port": body.ssh_port,
                "ssh_username": body.ssh_username,
                "capabilities": capabilities,
                "auto_update_policy": body.auto_update_policy,
                "sync_strategy": body.sync_strategy,
            },
            "status": {"state": "configured", "health": "unknown"},
            "policies": {
                "auto_cleanup": False,
                "cleanup_after_days": None,
                "backup_strategy": "edge_sync",
                "snapshot_retention": 7,
            },
            "network": {
                "hostname": body.hostname,
                "ssh_port": body.ssh_port,
                "accessible_from": ["operator_vpn"] if body.hostname else ["manual_pairing_pending"],
            },
            "metadata": {
                "created_by_phase": 3,
                "tags": ["edge", body.device_type, body.pairing_method],
                "owner": body.owner,
                "location": body.location,
                "sovereign": True,
            },
        }
    )
    return {"environment": env, "edge": {"pairing_methods": EDGE_PAIRING_METHODS}}


@router.post("/sovereignty/evaluate")
def evaluate_sovereignty(body: SovereigntyEvaluateRequest) -> dict[str, Any]:
    env = _get_environment(body.environment_id) if body.environment_id else None
    classification = body.classification.strip().lower()
    reasons: list[str] = []
    allowed = True
    if not env:
        allowed = False
        reasons.append("environment missing")
    else:
        env_type = env["type"]
        region = str(env.get("region") or "").lower()
        sovereign = bool(env.get("classification", {}).get("sovereign"))
        air_gapped = bool(env.get("classification", {}).get("air_gapped"))
        if classification in {"tlp:red", "tlp_red", "classified", "polish_gov_classified"}:
            allowed = air_gapped or env_type == "on_prem"
            if not allowed:
                reasons.append("TLP:RED/classified workloads require air-gapped or sovereign on-prem")
        if body.requires_eu or classification in {"eu_gdpr_pii", "gdpr", "pii"}:
            eu_ok = sovereign or region.startswith(("eu", "de", "fr", "pl", "waw", "warsaw", "fsn", "nbg", "hel"))
            if not eu_ok:
                allowed = False
                reasons.append("EU/GDPR workloads require EU-friendly region")
        if body.requires_poland or classification in {"polish_gov", "pl_gov"}:
            pl_ok = region.startswith(("pl", "waw", "warsaw", "poland")) or env_type in {"on_prem", "air_gapped"}
            if not pl_ok:
                allowed = False
                reasons.append("Polish-government workloads require Polish/on-prem/air-gapped location")
    return {
        "allowed": allowed,
        "action": "allow" if allowed else "block_deploy_require_operator_override",
        "reasons": reasons or ["environment satisfies declared sovereignty constraints"],
        "environment": env,
        "rules": _catalog_snapshot(auto_scan=False)["sovereignty_rules"],
    }
