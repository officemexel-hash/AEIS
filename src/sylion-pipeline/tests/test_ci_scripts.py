#!/usr/bin/env python3
"""
SYLION AEIS -- CI Scripts Test Suite

20+ tests verifying that all CI enforcement scripts work correctly:
  - Import tests for each check module
  - check_manifests: schema validation, format checks, dependency integrity
  - check_lifecycle_gates: stage enum validation, gate rule consistency
  - check_all_v2: orchestrator dispatches all checks

Run:
    python -m pytest tests/test_ci_scripts.py -v --tb=short
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Project root on sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import check modules
from scripts.check_manifests import (
    validate_manifest,
    validate_module_id_format,
    validate_module_kind,
    validate_lifecycle_stage,
    validate_depends_on,
)
from scripts.check_lifecycle_gates import (
    load_gate_rules,
    load_lifecycle_stages,
    load_manifests,
    validate_stage_enum,
    validate_gate_rules_coverage,
    validate_gate_rule_consistency,
    validate_gate_rule_completeness,
)


# ===================================================================
# SAMPLE SCHEMA (subset matching manifest_schema.json)
# ===================================================================

SAMPLE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["module_id", "module_kind", "owner_plan"],
    "properties": {
        "module_id": {
            "type": "string",
            "pattern": "^[a-z]+\\.[a-z_]+$",
        },
        "module_kind": {
            "type": "string",
            "enum": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O"],
        },
        "owner_plan": {"type": "string"},
        "lifecycle_stage": {
            "type": "string",
            "enum": ["draft", "build", "validate", "shadow", "dual", "cutover", "stable", "deprecated"],
        },
        "depends_on": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "additionalProperties": False,
}


def _make_valid_manifest(**overrides) -> dict:
    """Create a minimal valid manifest dict."""
    base = {
        "module_id": "core.test_module",
        "module_kind": "A",
        "owner_plan": "P01",
    }
    base.update(overrides)
    return base


# ===================================================================
# 1. IMPORT TESTS (5 tests)
# ===================================================================

class TestImportCheckModules:
    """Verify all check modules can be imported."""

    def test_import_check_manifests(self):
        import scripts.check_manifests as m
        assert hasattr(m, "main")
        assert hasattr(m, "validate_manifest")

    def test_import_check_contracts(self):
        import scripts.check_contracts as m
        assert hasattr(m, "main")
        assert hasattr(m, "validate_manifest")

    def test_import_check_golden_sets(self):
        import scripts.check_golden_sets as m
        assert hasattr(m, "main")
        assert hasattr(m, "run_golden_set")

    def test_import_check_imports(self):
        import scripts.check_imports as m
        assert hasattr(m, "main")
        assert hasattr(m, "scan_directory")

    def test_import_check_lifecycle_gates(self):
        import scripts.check_lifecycle_gates as m
        assert hasattr(m, "main")
        assert hasattr(m, "load_gate_rules")


# ===================================================================
# 2. CHECK_MANIFESTS: Schema validation tests (6 tests)
# ===================================================================

class TestManifestSchemaValidation:
    """Test check_manifests validation functions."""

    def test_valid_manifest_passes_schema(self):
        manifest = _make_valid_manifest()
        errors = validate_manifest(manifest, SAMPLE_SCHEMA)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_missing_required_field_fails(self):
        manifest = {"module_id": "core.test"}  # missing module_kind, owner_plan
        errors = validate_manifest(manifest, SAMPLE_SCHEMA)
        assert len(errors) >= 2
        error_text = " ".join(errors)
        assert "module_kind" in error_text
        assert "owner_plan" in error_text

    def test_invalid_module_kind_fails(self):
        manifest = _make_valid_manifest(module_kind="Z")
        errors = validate_manifest(manifest, SAMPLE_SCHEMA)
        assert len(errors) > 0
        assert any("module_kind" in e for e in errors)

    def test_extra_properties_rejected(self):
        manifest = _make_valid_manifest(unexpected_field="oops")
        errors = validate_manifest(manifest, SAMPLE_SCHEMA)
        assert any("additional properties" in e for e in errors)

    def test_invalid_module_id_pattern_fails(self):
        manifest = _make_valid_manifest(module_id="INVALID-NAME")
        errors = validate_manifest(manifest, SAMPLE_SCHEMA)
        assert any("module_id" in e and "pattern" in e for e in errors)

    def test_wrong_type_fails(self):
        manifest = _make_valid_manifest(module_kind=42)
        errors = validate_manifest(manifest, SAMPLE_SCHEMA)
        assert any("module_kind" in e and "expected string" in e for e in errors)


# ===================================================================
# 3. CHECK_MANIFESTS: Format/enum checks (5 tests)
# ===================================================================

class TestManifestFormatChecks:
    """Test module_id, module_kind, lifecycle_stage format validators."""

    def test_valid_module_id_format(self):
        assert validate_module_id_format("core.module_registry") == []

    def test_invalid_module_id_format(self):
        errors = validate_module_id_format("Core.Module")
        assert len(errors) == 1
        assert "does not match pattern" in errors[0]

    def test_valid_module_kind(self):
        assert validate_module_kind("A") == []
        assert validate_module_kind("O") == []

    def test_invalid_module_kind(self):
        errors = validate_module_kind("Z")
        assert len(errors) == 1

    def test_valid_lifecycle_stages(self):
        for stage in ["draft", "build", "validate", "shadow", "dual", "cutover", "stable", "deprecated"]:
            assert validate_lifecycle_stage(stage) == []


# ===================================================================
# 4. CHECK_MANIFESTS: Dependency integrity (3 tests)
# ===================================================================

class TestManifestDependencyIntegrity:
    """Test depends_on reference checking."""

    def test_valid_dependency(self):
        manifest = _make_valid_manifest(depends_on=["core.event_bus"])
        all_ids = {"core.test_module", "core.event_bus"}
        errors = validate_depends_on(manifest, all_ids)
        assert errors == []

    def test_missing_dependency(self):
        manifest = _make_valid_manifest(depends_on=["core.nonexistent"])
        all_ids = {"core.test_module"}
        errors = validate_depends_on(manifest, all_ids)
        assert len(errors) == 1
        assert "nonexistent" in errors[0]

    def test_multiple_dependencies_mixed(self):
        manifest = _make_valid_manifest(
            depends_on=["core.event_bus", "core.missing_mod", "core.evidence_spine"]
        )
        all_ids = {"core.test_module", "core.event_bus", "core.evidence_spine"}
        errors = validate_depends_on(manifest, all_ids)
        assert len(errors) == 1
        assert "missing_mod" in errors[0]


# ===================================================================
# 5. CHECK_LIFECYCLE_GATES: Infrastructure tests (4 tests)
# ===================================================================

class TestLifecycleGatesInfrastructure:
    """Test lifecycle gate loading and validation functions."""

    def test_load_gate_rules(self):
        rules = load_gate_rules()
        assert isinstance(rules, dict)
        assert "validate" in rules
        assert "shadow" in rules
        assert "dual" in rules
        assert "cutover" in rules
        assert "stable" in rules
        assert "deprecated" in rules

    def test_load_lifecycle_stages(self):
        stages = load_lifecycle_stages()
        assert "draft" in stages
        assert "stable" in stages
        assert "deprecated" in stages
        assert len(stages) == 8

    def test_validate_stage_enum_valid(self):
        manifests = {"core.test": {"lifecycle_stage": "draft"}}
        errors = validate_stage_enum(manifests, load_lifecycle_stages())
        assert errors == []

    def test_validate_stage_enum_invalid(self):
        manifests = {"core.test": {"lifecycle_stage": "on_fire"}}
        errors = validate_stage_enum(manifests, load_lifecycle_stages())
        assert len(errors) == 1
        assert "on_fire" in errors[0]


# ===================================================================
# 6. CHECK_LIFECYCLE_GATES: Gate rules validation (3 tests)
# ===================================================================

class TestLifecycleGateRules:
    """Test gate rule coverage and consistency."""

    def test_gate_rules_coverage_complete(self):
        rules = load_gate_rules()
        errors = validate_gate_rules_coverage(rules, load_lifecycle_stages())
        assert errors == [], f"Missing gate rules: {errors}"

    def test_gate_rules_consistency(self):
        rules = load_gate_rules()
        errors = validate_gate_rule_consistency(rules, load_lifecycle_stages())
        assert errors == [], f"Inconsistent gate rules: {errors}"

    def test_gate_rules_completeness(self):
        rules = load_gate_rules()
        errors = validate_gate_rule_completeness(rules)
        assert errors == [], f"Empty gate rules: {errors}"


# ===================================================================
# 7. CHECK_ALL_V2: Orchestrator tests (3 tests)
# ===================================================================

class TestCheckAllV2:
    """Test the master CI runner."""

    def test_import_check_all_v2(self):
        import scripts.check_all_v2 as m
        assert hasattr(m, "main")
        assert hasattr(m, "run_check")
        assert hasattr(m, "CHECKS")

    def test_check_list_has_five_entries(self):
        import scripts.check_all_v2 as m
        assert len(m.CHECKS) == 5
        names = [c["name"] for c in m.CHECKS]
        assert "check_manifests" in names
        assert "check_contracts" in names
        assert "check_golden_sets" in names
        assert "check_imports" in names
        assert "check_lifecycle_gates" in names

    def test_run_check_returns_int(self):
        """run_check should return an integer exit code."""
        import scripts.check_all_v2 as m
        # Run check_manifests (it should return 0 or 1, not crash)
        check = m.CHECKS[0]  # check_manifests
        code = m.run_check(check)
        assert isinstance(code, int)
        assert code in (0, 1)


# ===================================================================
# 8. Integration: manifest files on disk (2 tests)
# ===================================================================

class TestManifestFilesOnDisk:
    """Test that actual manifest files on disk are parseable."""

    def test_all_manifest_files_are_valid_json(self):
        manifests_dir = PROJECT_ROOT / "sylion" / "contracts" / "manifests"
        if not manifests_dir.exists():
            pytest.skip("No manifests directory")
        files = list(manifests_dir.glob("*.json"))
        assert len(files) > 0, "No manifest files found"
        for mf in sorted(files):
            with open(mf, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "module_id" in data, f"{mf.name} missing module_id"

    def test_all_manifests_have_valid_module_kind(self):
        manifests_dir = PROJECT_ROOT / "sylion" / "contracts" / "manifests"
        if not manifests_dir.exists():
            pytest.skip("No manifests directory")
        valid_kinds = {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O"}
        for mf in sorted(manifests_dir.glob("*.json")):
            with open(mf, "r", encoding="utf-8") as f:
                data = json.load(f)
            kind = data.get("module_kind", "")
            assert kind in valid_kinds, f"{mf.name} has invalid module_kind: {kind}"
