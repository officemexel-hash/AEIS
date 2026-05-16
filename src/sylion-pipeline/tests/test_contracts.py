"""
Comprehensive tests for SYLION AEIS Contract Registry and Manifest system.

Covers:
  - ContractRegistry: publish, versioning, breaking-change detection, listing
  - ManifestLoader: dict validation, required fields, module_kind validation
  - ManifestSchema: JSON Schema validation against manifest_schema.json
"""
import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# jsonschema — graceful import for schema tests
# ---------------------------------------------------------------------------
try:
    import jsonschema as _js
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from sylion.core.contract_registry import (
    Contract,
    ContractRegistry,
    ContractType,
)
from sylion.core.manifest_loader import ManifestLoader
from sylion.core.module_registry import ModuleKind

# Path to the canonical manifest schema shipped with the package
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sylion" / "contracts" / "manifest_schema.json"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def cr():
    """Fresh ContractRegistry (in-memory, no event bus)."""
    return ContractRegistry()


@pytest.fixture
def cr_with_bus(bus):
    """ContractRegistry wired to the shared EventBus fixture."""
    return ContractRegistry(event_bus=bus)


@pytest.fixture
def schema_json():
    """Load and return the manifest JSON schema as a dict."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _make_contract(**overrides) -> Contract:
    """Helper to build a Contract with sensible defaults."""
    defaults = dict(
        name="test.contract",
        contract_type=ContractType.GRPC_SERVICE,
        version="1.0.0",
        schema_def='{"type": "object"}',
        producer_module="core.test",
        consumer_modules=["core.consumer"],
        description="Test contract",
    )
    defaults.update(overrides)
    return Contract(**defaults)


# ============================================================================
# TestContractRegistry
# ============================================================================

class TestContractRegistry:
    """Tests for ContractRegistry CRUD and versioning logic."""

    def test_publish_contract(self, cr):
        """Publishing a new contract stores it and returns metadata."""
        c = _make_contract()
        result = cr.publish(c)

        assert result["name"] == "test.contract"
        assert result["version"] == "1.0.0"
        assert result["breaking"] is False
        assert result["contract_id"] == c.contract_id

        stored = cr.get("test.contract")
        assert stored is not None
        assert stored["name"] == "test.contract"
        assert stored["version"] == "1.0.0"
        assert stored["is_latest"] == 1

    def test_publish_new_version(self, cr):
        """Publishing a second version of the same contract succeeds."""
        cr.publish(_make_contract(version="1.0.0"))
        result = cr.publish(_make_contract(name="test.contract", version="1.1.0"))

        assert result["version"] == "1.1.0"
        assert result["breaking"] is False

        # Old version should no longer be latest
        latest = cr.get("test.contract")
        assert latest["version"] == "1.1.0"

    def test_detect_breaking_change(self, cr):
        """Major version bump is flagged as a breaking change."""
        cr.publish(_make_contract(version="1.0.0"))
        result = cr.publish(_make_contract(name="test.contract", version="2.0.0"))

        assert result["breaking"] is True

    def test_compatible_minor_version(self, cr):
        """Minor/patch version bumps are NOT breaking."""
        cr.publish(_make_contract(version="1.0.0"))
        result = cr.publish(_make_contract(name="test.contract", version="1.2.3"))

        assert result["breaking"] is False

    def test_get_latest_version(self, cr):
        """get(name) with no version returns the latest published version."""
        cr.publish(_make_contract(version="1.0.0"))
        cr.publish(_make_contract(name="test.contract", version="1.1.0"))
        cr.publish(_make_contract(name="test.contract", version="2.0.0"))

        latest = cr.get("test.contract")
        assert latest is not None
        assert latest["version"] == "2.0.0"

    def test_get_specific_version(self, cr):
        """get(name, version) returns the exact historical version."""
        cr.publish(_make_contract(version="1.0.0"))
        cr.publish(_make_contract(name="test.contract", version="2.0.0"))

        v1 = cr.get("test.contract", version="1.0.0")
        assert v1 is not None
        assert v1["version"] == "1.0.0"

        v2 = cr.get("test.contract", version="2.0.0")
        assert v2 is not None
        assert v2["version"] == "2.0.0"

        missing = cr.get("test.contract", version="9.9.9")
        assert missing is None

    def test_list_versions(self, cr):
        """list_versions returns all published versions of a contract."""
        cr.publish(_make_contract(version="1.0.0"))
        cr.publish(_make_contract(name="test.contract", version="1.1.0"))
        cr.publish(_make_contract(name="test.contract", version="2.0.0"))

        versions = cr.list_versions("test.contract")
        assert len(versions) == 3
        version_strings = {v["version"] for v in versions}
        assert version_strings == {"1.0.0", "1.1.0", "2.0.0"}

    def test_list_all_contracts(self, cr):
        """list_all returns only the latest version of each contract."""
        cr.publish(_make_contract(name="alpha"))
        cr.publish(_make_contract(name="beta"))
        cr.publish(_make_contract(name="alpha", version="2.0.0"))

        all_latest = cr.list_all()
        names = {c["name"] for c in all_latest}
        assert names == {"alpha", "beta"}
        # alpha should show v2 (latest), not v1
        alpha = next(c for c in all_latest if c["name"] == "alpha")
        assert alpha["version"] == "2.0.0"

    def test_list_by_type(self, cr):
        """list_all(contract_type=...) filters by contract type."""
        cr.publish(_make_contract(
            name="grpc.one", contract_type=ContractType.GRPC_SERVICE,
        ))
        cr.publish(_make_contract(
            name="event.one", contract_type=ContractType.EVENT_SCHEMA,
        ))
        cr.publish(_make_contract(
            name="grpc.two", contract_type=ContractType.GRPC_SERVICE,
        ))

        grpc_only = cr.list_all(contract_type="grpc_service")
        assert len(grpc_only) == 2
        assert all(c["contract_type"] == "grpc_service" for c in grpc_only)

        event_only = cr.list_all(contract_type="event_schema")
        assert len(event_only) == 1
        assert event_only[0]["name"] == "event.one"

        # Unknown type returns empty
        assert cr.list_all(contract_type="nonexistent") == []

    def test_publish_emits_event(self, cr_with_bus, bus):
        """Publishing a contract emits a 'contract.published' event on the bus."""
        c = _make_contract()
        cr_with_bus.publish(c)

        events = bus.query(topic="contract.published")
        assert len(events) >= 1

        payload = json.loads(events[0]["payload"])
        assert payload["name"] == "test.contract"
        assert payload["version"] == "1.0.0"
        assert payload["breaking"] is False

    def test_check_compatibility_new_contract(self, cr):
        """check_compatibility on a name with no existing version returns compatible."""
        result = cr.check_compatibility("brand.new", "1.0.0")
        assert result["compatible"] is True
        assert result["breaking"] is False
        assert result["message"] == "no existing version"

    def test_check_compatibility_breaking(self, cr):
        """check_compatibility detects major version mismatch as breaking."""
        cr.publish(_make_contract(version="1.0.0"))
        result = cr.check_compatibility("test.contract", "2.0.0")
        assert result["compatible"] is False
        assert result["breaking"] is True
        assert result["old_version"] == "1.0.0"
        assert result["new_version"] == "2.0.0"

    def test_check_compatibility_minor(self, cr):
        """check_compatibility says compatible for minor bumps."""
        cr.publish(_make_contract(version="1.0.0"))
        result = cr.check_compatibility("test.contract", "1.5.0")
        assert result["compatible"] is True
        assert result["breaking"] is False

    def test_get_nonexistent_contract(self, cr):
        """get for an unknown name returns None."""
        assert cr.get("no.such.contract") is None


# ============================================================================
# TestManifestLoader
# ============================================================================

class TestManifestLoader:
    """Tests for ManifestLoader dict validation."""

    def test_load_valid_manifest_dict(self):
        """A minimal valid manifest dict passes validation."""
        ml = ManifestLoader()
        result = ml.load_dict({
            "module_id": "core.test",
            "module_kind": "A",
            "owner_plan": "P01",
        })
        assert result["module_id"] == "core.test"
        assert result["module_kind"] == "A"

    def test_load_invalid_missing_required_field(self):
        """Missing a required field raises ValueError."""
        ml = ManifestLoader()
        with pytest.raises(ValueError, match="missing required field"):
            ml.load_dict({
                "module_id": "core.test",
                # module_kind missing
                "owner_plan": "P01",
            })

    def test_load_invalid_module_kind(self):
        """An unrecognized module_kind raises ValueError."""
        ml = ManifestLoader()
        with pytest.raises(ValueError, match="invalid module_kind"):
            ml.load_dict({
                "module_id": "core.test",
                "module_kind": "Z",
                "owner_plan": "P01",
            })

    def test_load_valid_manifest_with_all_fields(self):
        """A manifest dict with many optional fields validates successfully."""
        ml = ManifestLoader()
        manifest = {
            "module_id": "cognitive.planner",
            "module_kind": "B",
            "owner_plan": "P03",
            "implementation_strategy": "greenfield",
            "contract_version": "1.0.0",
            "decision_class_entry": "D3",
            "security_profile": "dev-light",
            "auth_mode": "bootstrap",
            "execution_guard": "off",
            "audit_mode": "basic",
            "depends_on": ["core.module_registry"],
            "description": "Cognitive planner module",
            "version": "1.0.0",
            "milestone": "M1",
            "lifecycle_stage": "draft",
        }
        result = ml.load_dict(manifest)
        assert result["module_id"] == "cognitive.planner"
        assert result["module_kind"] == "B"
        assert result["depends_on"] == ["core.module_registry"]

    def test_manifest_module_id_pattern(self):
        """module_id is accepted regardless of pattern (loader checks required, not regex)."""
        ml = ManifestLoader()
        # The ManifestLoader only checks for required fields and valid kind.
        # Pattern validation is the schema's job (see TestManifestSchema).
        result = ml.load_dict({
            "module_id": "any_id_works",
            "module_kind": "A",
            "owner_plan": "P01",
        })
        assert result["module_id"] == "any_id_works"

    def test_load_non_dict_raises(self):
        """Passing a non-dict raises ValueError."""
        ml = ManifestLoader()
        with pytest.raises(ValueError, match="manifest must be a dict"):
            ml.load_dict("not a dict")

    def test_load_missing_all_required(self):
        """Empty dict raises ValueError for all three missing fields."""
        ml = ManifestLoader()
        with pytest.raises(ValueError, match="missing required field"):
            ml.load_dict({})

    def test_all_valid_module_kinds(self):
        """Every ModuleKind enum value passes validation."""
        ml = ManifestLoader()
        for kind in ModuleKind:
            result = ml.load_dict({
                "module_id": f"test.{kind.value}",
                "module_kind": kind.value,
                "owner_plan": "P01",
            })
            assert result["module_kind"] == kind.value


# ============================================================================
# TestManifestSchema
# ============================================================================

class TestManifestSchema:
    """Tests that validate manifests against the canonical manifest_schema.json.

    Uses the jsonschema library. Tests are skipped gracefully if it is not installed.
    """

    @pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_schema_validates_good_manifest(self, schema_json):
        """A minimal valid manifest passes schema validation."""
        import jsonschema
        manifest = {
            "module_id": "core.test",
            "module_kind": "A",
            "owner_plan": "P01",
        }
        # Should not raise
        jsonschema.validate(instance=manifest, schema=schema_json)

    @pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_schema_rejects_bad_kind(self, schema_json):
        """An invalid module_kind fails schema validation."""
        import jsonschema
        manifest = {
            "module_id": "core.test",
            "module_kind": "Z",
            "owner_plan": "P01",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=manifest, schema=schema_json)

    @pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_schema_rejects_missing_fields(self, schema_json):
        """Manifests missing required fields fail schema validation."""
        import jsonschema
        # Missing module_id
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                instance={"module_kind": "A", "owner_plan": "P01"},
                schema=schema_json,
            )

        # Missing module_kind
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                instance={"module_id": "core.test", "owner_plan": "P01"},
                schema=schema_json,
            )

        # Missing owner_plan
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                instance={"module_id": "core.test", "module_kind": "A"},
                schema=schema_json,
            )

        # Missing all
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance={}, schema=schema_json)

    @pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_schema_accepts_full_manifest(self, schema_json):
        """A fully populated manifest passes schema validation."""
        import jsonschema
        manifest = {
            "module_id": "cognitive.planner",
            "module_kind": "B",
            "owner_plan": "P03",
            "implementation_strategy": "greenfield",
            "contract_version": "1.0.0",
            "decision_class_entry": "D3",
            "security_profile": "dev-light",
            "auth_mode": "bootstrap",
            "execution_guard": "off",
            "audit_mode": "basic",
            "depends_on": ["core.module_registry"],
            "publishes_events": ["cognitive.plan.created"],
            "consumes_events": ["module.registered"],
            "description": "Cognitive planner module",
            "version": "1.0.0",
            "milestone": "M1",
            "lifecycle_stage": "draft",
        }
        # Should not raise
        jsonschema.validate(instance=manifest, schema=schema_json)

    @pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_schema_rejects_bad_module_id_pattern(self, schema_json):
        """module_id must match ^[a-z]+\\.[a-z_]+$ -- no uppercase, no digits."""
        import jsonschema
        bad = {
            "module_id": "CORE.TEST",
            "module_kind": "A",
            "owner_plan": "P01",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=bad, schema=schema_json)

    @pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_schema_rejects_additional_properties(self, schema_json):
        """Schema has additionalProperties=false, so extra fields are rejected."""
        import jsonschema
        manifest = {
            "module_id": "core.test",
            "module_kind": "A",
            "owner_plan": "P01",
            "unknown_field": "oops",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=manifest, schema=schema_json)

    @pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_schema_rejects_bad_milestone(self, schema_json):
        """milestone must be one of M0-M5."""
        import jsonschema
        manifest = {
            "module_id": "core.test",
            "module_kind": "A",
            "owner_plan": "P01",
            "milestone": "M99",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=manifest, schema=schema_json)

    @pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_schema_rejects_bad_security_profile(self, schema_json):
        """security_profile must be one of the allowed enum values."""
        import jsonschema
        manifest = {
            "module_id": "core.test",
            "module_kind": "A",
            "owner_plan": "P01",
            "security_profile": "ultra-secure",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=manifest, schema=schema_json)
