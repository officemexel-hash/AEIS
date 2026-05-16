"""
Tests for funding autopilot contract manifests (K1.4).

Validates that all K-owned funding modules have proper contract manifests
in sylion/contracts/manifests/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

MANIFEST_DIR = Path(__file__).parent.parent.parent / "sylion" / "contracts" / "manifests"

REQUIRED_FIELDS = [
    "module_id",
    "module_kind",
    "owner_plan",
    "implementation_strategy",
    "contract_version",
    "decision_class_entry",
    "security_profile",
    "auth_mode",
    "execution_guard",
    "audit_mode",
    "depends_on",
    "description",
    "version",
    "milestone",
    "lifecycle_stage",
]

FUNDING_MANIFESTS = [
    "funding_autopilot.program_scanner.json",
    "funding_autopilot.browser_automation.json",
    "funding_autopilot.grant_reporter.json",
    "funding_autopilot.governance_bridge.json",
]


@pytest.mark.parametrize("filename", FUNDING_MANIFESTS)
def test_manifest_exists_and_valid(filename: str):
    path = MANIFEST_DIR / filename
    assert path.exists(), f"Manifest {filename} missing"
    data = json.loads(path.read_text(encoding="utf-8"))
    for field in REQUIRED_FIELDS:
        assert field in data, f"{filename} missing field '{field}'"
    assert data["module_id"] == filename.replace(".json", "")
    assert data["decision_class_entry"].startswith("D")
    assert data["lifecycle_stage"] in ("stable", "beta", "alpha", "deprecated")
