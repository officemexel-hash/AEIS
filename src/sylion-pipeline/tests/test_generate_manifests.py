"""
Tests for sylion.contracts.generate_manifests

Exercises every public helper and data constant:
  - get_default
  - build_manifest
  - validate_manifest
  - generate_all
  - PACKAGE_KIND / SKIP_PACKAGES / MODULE_META / DEPENDS_ON /
    PUBLISHES_EVENTS / CONSUMES_EVENTS
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sylion.contracts.generate_manifests import (
    CONSUMES_EVENTS,
    DEPENDS_ON,
    MANIFESTS_DIR,
    MODULE_META,
    PACKAGE_KIND,
    PUBLISHES_EVENTS,
    SCHEMA_PATH,
    SKIP_PACKAGES,
    build_manifest,
    generate_all,
    get_default,
    validate_manifest,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def schema() -> dict:
    """Load the manifest JSON schema once for all tests."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# get_default
# ---------------------------------------------------------------------------


class TestGetDefault:
    def test_known_keys_return_expected_values(self):
        known = {
            "implementation_strategy": "greenfield",
            "contract_version": "1.0.0",
            "security_profile": "dev-light",
            "auth_mode": "bootstrap",
            "execution_guard": "off",
            "audit_mode": "basic",
            "milestone": "M0",
            "lifecycle_stage": "draft",
            "version": "1.0.0",
        }
        for key, expected in known.items():
            assert get_default(key, "core.event_bus") == expected, key

    def test_unknown_key_returns_empty_string(self):
        assert get_default("nonexistent_field", "core.event_bus") == ""

    def test_module_id_does_not_affect_defaults(self):
        assert get_default("auth_mode", "security.auth_provider") == "bootstrap"
        assert get_default("auth_mode", "core.module_registry") == "bootstrap"


# ---------------------------------------------------------------------------
# build_manifest
# ---------------------------------------------------------------------------


class TestBuildManifest:
    def test_basic_structure(self):
        m = build_manifest("core.event_bus")
        assert m["module_id"] == "core.event_bus"
        assert m["module_kind"] == "A"
        assert isinstance(m, dict)

    def test_all_required_fields_present(self):
        required = {"module_id", "module_kind", "owner_plan"}
        m = build_manifest("core.event_bus")
        assert required.issubset(m.keys())

    def test_all_schema_fields_present(self):
        schema_fields = {
            "module_id", "module_kind", "owner_plan",
            "implementation_strategy", "contract_version",
            "decision_class_entry", "security_profile",
            "auth_mode", "execution_guard", "audit_mode",
            "depends_on", "publishes_events", "consumes_events",
            "description", "version", "milestone", "lifecycle_stage",
        }
        m = build_manifest("core.event_bus")
        assert schema_fields.issubset(m.keys())

    def test_package_kind_mapping(self):
        m = build_manifest("cognitive.planner")
        assert m["module_kind"] == "B"
        m = build_manifest("execution.tool_runner")
        assert m["module_kind"] == "C"
        m = build_manifest("memory.kanon_access")
        assert m["module_kind"] == "D"

    def test_all_package_kinds(self):
        for pkg, kind in PACKAGE_KIND.items():
            sample_module = next(
                mid for mid in MODULE_META if mid.startswith(pkg + ".")
            )
            m = build_manifest(sample_module)
            assert m["module_kind"] == kind, f"{sample_module} should be kind {kind}"

    def test_security_modules_overrides(self):
        """Security modules (except profiles) get strict auth/guard/audit."""
        for mid in MODULE_META:
            if not mid.startswith("security."):
                continue
            m = build_manifest(mid)
            if mid == "security.profiles":
                assert m["auth_mode"] == "bootstrap"
                assert m["execution_guard"] == "off"
                assert m["audit_mode"] == "basic"
            else:
                assert m["auth_mode"] == "session", mid
                assert m["execution_guard"] == "strict", mid
                assert m["audit_mode"] == "extended", mid

    def test_non_security_modules_get_defaults(self):
        for mid in ["core.event_bus", "cognitive.planner", "devices.device_registry"]:
            m = build_manifest(mid)
            assert m["auth_mode"] == "bootstrap"
            assert m["execution_guard"] == "off"
            assert m["audit_mode"] == "basic"

    def test_depends_on_included(self):
        m = build_manifest("core.bundle_assembler")
        assert set(m["depends_on"]) == {"core.event_bus", "core.module_registry"}

    def test_publishes_events_included(self):
        m = build_manifest("core.module_registry")
        assert "module.registered" in m["publishes_events"]

    def test_consumes_events_included(self):
        m = build_manifest("security.session_broker")
        assert "security.auth.login" in m["consumes_events"]

    def test_depends_on_empty_for_root_modules(self):
        m = build_manifest("core.event_bus")
        assert m["depends_on"] == []
        m = build_manifest("security.profiles")
        assert m["depends_on"] == []

    def test_publishes_events_empty_for_some(self):
        m = build_manifest("core.manifest_loader")
        assert m["publishes_events"] == []

    def test_consumes_events_empty_for_some(self):
        m = build_manifest("core.event_bus")
        assert m["consumes_events"] == []

    def test_meta_fields_populated(self):
        m = build_manifest("core.event_bus")
        assert m["owner_plan"] == "P01"
        assert m["decision_class_entry"] == "D0"
        assert m["description"] != ""

    def test_description_from_meta(self):
        m = build_manifest("security.auth_provider")
        assert "Authentication" in m["description"] or m["description"] != ""

    def test_no_extra_keys_beyond_schema(self):
        schema_fields = {
            "module_id", "module_kind", "owner_plan",
            "implementation_strategy", "contract_version",
            "decision_class_entry", "security_profile",
            "auth_mode", "execution_guard", "audit_mode",
            "depends_on", "publishes_events", "consumes_events",
            "description", "version", "milestone", "lifecycle_stage",
        }
        for mid in MODULE_META:
            m = build_manifest(mid)
            extra = set(m.keys()) - schema_fields
            assert not extra, f"{mid} has extra keys: {extra}"

    def test_module_id_splits_correctly(self):
        m = build_manifest("cellular.evidence_writer")
        assert m["module_id"] == "cellular.evidence_writer"
        assert m["module_kind"] == "O"


# ---------------------------------------------------------------------------
# validate_manifest
# ---------------------------------------------------------------------------


class TestValidateManifest:
    def test_valid_manifest_no_errors(self, schema):
        m = build_manifest("core.event_bus")
        errors = validate_manifest(m, schema)
        assert errors == []

    def test_all_built_manifests_validate(self, schema):
        for mid in MODULE_META:
            m = build_manifest(mid)
            errors = validate_manifest(m, schema)
            assert errors == [], f"{mid}: {errors}"

    def test_missing_required_field(self, schema):
        m = {"module_kind": "A", "owner_plan": "P01"}
        errors = validate_manifest(m, schema)
        assert any("missing required field" in e for e in errors)

    def test_missing_all_required_fields(self, schema):
        m = {}
        errors = validate_manifest(m, schema)
        required = schema.get("required", [])
        assert len(errors) >= len(required)

    def test_unknown_field_reported(self, schema):
        m = build_manifest("core.event_bus")
        m["bogus_field"] = "oops"
        errors = validate_manifest(m, schema)
        assert any("unknown field" in e for e in errors)

    def test_wrong_type_string_field(self, schema):
        m = build_manifest("core.event_bus")
        m["module_id"] = 42
        errors = validate_manifest(m, schema)
        assert any("expected string" in e for e in errors)

    def test_wrong_type_array_field(self, schema):
        m = build_manifest("core.event_bus")
        m["depends_on"] = "not_a_list"
        errors = validate_manifest(m, schema)
        assert any("expected array" in e for e in errors)

    def test_pattern_violation_module_id(self, schema):
        m = build_manifest("core.event_bus")
        m["module_id"] = "INVALID"
        errors = validate_manifest(m, schema)
        assert any("pattern" in e for e in errors)

    def test_enum_violation_module_kind(self, schema):
        m = build_manifest("core.event_bus")
        m["module_kind"] = "Z"
        errors = validate_manifest(m, schema)
        assert any("not in" in e for e in errors)

    def test_enum_violation_decision_class(self, schema):
        m = build_manifest("core.event_bus")
        m["decision_class_entry"] = "D9"
        errors = validate_manifest(m, schema)
        assert any("not in" in e for e in errors)

    def test_enum_violation_lifecycle_stage(self, schema):
        m = build_manifest("core.event_bus")
        m["lifecycle_stage"] = "production"
        errors = validate_manifest(m, schema)
        assert any("not in" in e for e in errors)

    def test_pattern_violation_contract_version(self, schema):
        m = build_manifest("core.event_bus")
        m["contract_version"] = "1.0"
        errors = validate_manifest(m, schema)
        assert any("pattern" in e for e in errors)

    def test_additional_properties_flag(self, schema):
        assert schema.get("additionalProperties") is False


# ---------------------------------------------------------------------------
# generate_all
# ---------------------------------------------------------------------------


class TestGenerateAll:
    def test_returns_tuple_of_three(self):
        result = generate_all()
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_all_modules_generated_successfully(self):
        success, error_count, errors = generate_all()
        assert success == len(MODULE_META), (
            f"Expected {len(MODULE_META)} manifests, got {success}. "
            f"Errors: {errors}"
        )
        assert error_count == 0
        assert errors == []

    def test_manifest_files_written_to_disk(self, tmp_path):
        """Verify files actually exist in the MANIFESTS_DIR after generation."""
        generate_all()
        for mid in MODULE_META:
            path = MANIFESTS_DIR / f"{mid}.json"
            assert path.exists(), f"Missing manifest: {path}"

    def test_written_files_are_valid_json(self):
        generate_all()
        for mid in MODULE_META:
            path = MANIFESTS_DIR / f"{mid}.json"
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, dict)
            assert data["module_id"] == mid

    def test_written_manifests_validate_against_schema(self, schema):
        generate_all()
        for mid in MODULE_META:
            path = MANIFESTS_DIR / f"{mid}.json"
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            errors = validate_manifest(data, schema)
            assert errors == [], f"{mid}: {errors}"


# ---------------------------------------------------------------------------
# Data constant consistency checks
# ---------------------------------------------------------------------------


class TestConstantsConsistency:
    def test_package_kind_covers_all_packages_in_meta(self):
        packages_in_meta = {mid.split(".")[0] for mid in MODULE_META}
        for pkg in packages_in_meta:
            assert pkg in PACKAGE_KIND, f"Package {pkg} not in PACKAGE_KIND"

    def test_all_meta_modules_have_deps(self):
        for mid in MODULE_META:
            assert mid in DEPENDS_ON, f"{mid} not in DEPENDS_ON"

    def test_all_meta_modules_have_publishes(self):
        for mid in MODULE_META:
            assert mid in PUBLISHES_EVENTS, f"{mid} not in PUBLISHES_EVENTS"

    def test_all_meta_modules_have_consumes(self):
        for mid in MODULE_META:
            assert mid in CONSUMES_EVENTS, f"{mid} not in CONSUMES_EVENTS"

    def test_deps_reference_valid_modules(self):
        valid_ids = set(MODULE_META.keys())
        for mid, deps in DEPENDS_ON.items():
            for dep in deps:
                assert dep in valid_ids, f"{mid} depends on unknown module: {dep}"

    def test_skip_packages_excludes_infrastructure(self):
        assert "api" in SKIP_PACKAGES
        assert "db" in SKIP_PACKAGES
        assert "contracts" in SKIP_PACKAGES

    def test_skip_packages_not_in_package_kind(self):
        for pkg in SKIP_PACKAGES:
            assert pkg not in PACKAGE_KIND, (
                f"Skipped package {pkg} should not be in PACKAGE_KIND"
            )

    def test_all_depends_on_are_lists(self):
        for mid, deps in DEPENDS_ON.items():
            assert isinstance(deps, list), f"{mid} deps is not a list"

    def test_all_publishes_are_lists(self):
        for mid, events in PUBLISHES_EVENTS.items():
            assert isinstance(events, list), f"{mid} publishes is not a list"

    def test_all_consumes_are_lists(self):
        for mid, events in CONSUMES_EVENTS.items():
            assert isinstance(events, list), f"{mid} consumes is not a list"

    def test_module_kind_enum_covers_all_kinds(self):
        for mid in MODULE_META:
            pkg = mid.split(".")[0]
            kind = PACKAGE_KIND[pkg]
            assert kind in "ABCDEFGHIJKLMNO", f"Unexpected kind: {kind}"

    def test_manifests_dir_is_path(self):
        assert isinstance(MANIFESTS_DIR, Path)

    def test_schema_path_is_path(self):
        assert isinstance(SCHEMA_PATH, Path)

    def test_schema_path_exists(self):
        assert SCHEMA_PATH.exists()

    def test_meta_count(self):
        assert len(MODULE_META) > 80

    def test_depends_on_same_keys_as_meta(self):
        assert set(DEPENDS_ON.keys()) == set(MODULE_META.keys())

    def test_publishes_same_keys_as_meta(self):
        assert set(PUBLISHES_EVENTS.keys()) == set(MODULE_META.keys())

    def test_consumes_same_keys_as_meta(self):
        assert set(CONSUMES_EVENTS.keys()) == set(MODULE_META.keys())

    def test_no_self_dependencies(self):
        for mid, deps in DEPENDS_ON.items():
            assert mid not in deps, f"{mid} depends on itself"

    def test_event_names_follow_domain_event_action_pattern(self):
        """All events should match domain.event or domain.event.action."""
        import re
        pattern = re.compile(r"^[a-z_]+(\.[a-z_]+){1,2}$")
        for mid, events in PUBLISHES_EVENTS.items():
            for event in events:
                assert pattern.match(event), (
                    f"{mid} publishes event with bad format: {event}"
                )
        for mid, events in CONSUMES_EVENTS.items():
            for event in events:
                assert pattern.match(event), (
                    f"{mid} consumes event with bad format: {event}"
                )
