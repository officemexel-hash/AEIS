#!/usr/bin/env python3
"""
SYLION AEIS -- Manifest Schema Validator

Validates all module manifests in sylion/contracts/manifests/ against the
canonical manifest_schema.json.  Performs:

  1. Schema structural validation (required fields, types, enums, patterns)
  2. module_id format check  (^[a-z]+\\.[a-z_]+$)
  3. module_kind enum check  (A-O)
  4. lifecycle_stage enum check  (draft .. deprecated)
  5. depends_on reference integrity (referenced module_id must have a manifest)

Exit codes:
  0 = all validations pass
  1 = violations detected
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

CONTRACTS_DIR = PROJECT_ROOT / "sylion" / "contracts"
MANIFESTS_DIR = CONTRACTS_DIR / "manifests"
SCHEMA_PATH = CONTRACTS_DIR / "manifest_schema.json"

# Allowed enum values (from manifest_schema.json)
VALID_MODULE_KINDS = {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O"}
VALID_LIFECYCLE_STAGES = {"draft", "build", "validate", "shadow", "dual", "cutover", "stable", "deprecated"}

MODULE_ID_PATTERN = re.compile(r"^[a-z]+\.[a-z_]+$")

# ---------------------------------------------------------------------------
# Minimal JSON-Schema validator (subset of draft-07)
# ---------------------------------------------------------------------------

def _validate_type(value, schema_type: str) -> list[str]:
    type_map = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    expected = type_map.get(schema_type)
    if expected is None:
        return []
    if not isinstance(value, expected):
        if schema_type == "integer" and isinstance(value, bool):
            return ["expected integer, got boolean"]
        return [f"expected {schema_type}, got {type(value).__name__}"]
    return []


def _validate_enum(value, enum_values: list) -> list[str]:
    if value not in enum_values:
        return [f"value '{value}' not in {enum_values}"]
    return []


def _validate_pattern(value: str, pattern: str) -> list[str]:
    if not re.fullmatch(pattern, value):
        return [f"value '{value}' does not match pattern '{pattern}'"]
    return []


def _validate_object(data: dict, schema: dict, path: str = "") -> list[str]:
    errors: list[str] = []

    if "type" in schema:
        errors.extend(f"{path}: {e}" for e in _validate_type(data, schema["type"]))

    for req in schema.get("required", []):
        if req not in data:
            errors.append(f"{path}: missing required field '{req}'")

    if schema.get("additionalProperties") is False:
        allowed = set(schema.get("properties", {}).keys())
        extra = set(data.keys()) - allowed
        if extra:
            errors.append(f"{path}: additional properties not allowed: {extra}")

    for key, prop_schema in schema.get("properties", {}).items():
        if key not in data:
            continue
        val = data[key]
        prop_path = f"{path}.{key}" if path else key

        if "type" in prop_schema:
            errs = _validate_type(val, prop_schema["type"])
            errors.extend(f"{prop_path}: {e}" for e in errs)

        if "enum" in prop_schema:
            errs = _validate_enum(val, prop_schema["enum"])
            errors.extend(f"{prop_path}: {e}" for e in errs)

        if "pattern" in prop_schema and isinstance(val, str):
            errs = _validate_pattern(val, prop_schema["pattern"])
            errors.extend(f"{prop_path}: {e}" for e in errs)

        if isinstance(val, list) and "items" in prop_schema:
            item_schema = prop_schema["items"]
            for i, item in enumerate(val):
                if isinstance(item, dict) and item_schema.get("type") == "object":
                    errors.extend(_validate_object(item, item_schema, f"{prop_path}[{i}]"))
                elif "type" in item_schema:
                    errs = _validate_type(item, item_schema["type"])
                    errors.extend(f"{prop_path}[{i}]: {e}" for e in errs)

    return errors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_manifest(manifest: dict, schema: dict) -> list[str]:
    """Validate a single manifest dict against the full schema. Returns errors."""
    return _validate_object(manifest, schema)


def validate_module_id_format(module_id: str) -> list[str]:
    """Check module_id matches the canonical pattern."""
    if not MODULE_ID_PATTERN.fullmatch(module_id):
        return [f"module_id '{module_id}' does not match pattern ^[a-z]+\\.[a-z_]+$"]
    return []


def validate_module_kind(kind: str) -> list[str]:
    """Check module_kind is a valid enum value."""
    if kind not in VALID_MODULE_KINDS:
        return [f"module_kind '{kind}' not in valid set {sorted(VALID_MODULE_KINDS)}"]
    return []


def validate_lifecycle_stage(stage: str) -> list[str]:
    """Check lifecycle_stage is a valid enum value."""
    if stage not in VALID_LIFECYCLE_STAGES:
        return [f"lifecycle_stage '{stage}' not in valid set {sorted(VALID_LIFECYCLE_STAGES)}"]
    return []


def validate_depends_on(manifest: dict, all_module_ids: set[str]) -> list[str]:
    """Check that every depends_on entry references an existing module_id."""
    errors: list[str] = []
    mid = manifest.get("module_id", "?")
    for dep in manifest.get("depends_on", []):
        if dep not in all_module_ids:
            errors.append(f"[{mid}] depends_on '{dep}' has no matching manifest")
    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 72)
    print("SYLION AEIS -- Manifest Schema Validator")
    print("=" * 72)

    total_pass = 0
    total_fail = 0
    violations: list[str] = []

    # --- 1. Load schema ---
    print(f"\n[1/5] Loading schema: {SCHEMA_PATH}")
    if not SCHEMA_PATH.exists():
        print(f"  FATAL: Schema file not found: {SCHEMA_PATH}")
        return 1
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)
    print(f"  OK -- schema loaded (title: {schema.get('title', 'n/a')})")

    # --- 2. Load manifests ---
    print(f"\n[2/5] Loading manifests from: {MANIFESTS_DIR}")
    manifests: dict[str, dict] = {}
    if not MANIFESTS_DIR.exists():
        print(f"  WARNING: Manifests directory does not exist -- creating it")
        MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    manifest_files = list(MANIFESTS_DIR.glob("*.json"))
    if not manifest_files:
        print(f"  WARNING: No manifest files found (directory is empty)")
    else:
        for mf in sorted(manifest_files):
            try:
                with open(mf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                mid = data.get("module_id", mf.stem)
                manifests[mid] = data
                print(f"  Loaded: {mf.name} (module_id={mid})")
            except (json.JSONDecodeError, OSError) as e:
                violations.append(f"  [{mf.name}] parse error: {e}")
                total_fail += 1
                print(f"  FAIL [{mf.name}]: parse error: {e}")

    all_module_ids = set(manifests.keys())

    # --- 3. Schema validation ---
    print(f"\n[3/5] Schema validation ({len(manifests)} manifest(s))")
    for mid, mdata in sorted(manifests.items()):
        errs = validate_manifest(mdata, schema)
        if errs:
            total_fail += 1
            for e in errs:
                violations.append(f"  [{mid}] {e}")
                print(f"  FAIL [{mid}]: {e}")
        else:
            total_pass += 1
            print(f"  PASS [{mid}]")

    # --- 4. Enum / format checks ---
    print(f"\n[4/5] Enum and format checks")
    for mid, mdata in sorted(manifests.items()):
        errs = []
        errs.extend(validate_module_id_format(mdata.get("module_id", "")))
        errs.extend(validate_module_kind(mdata.get("module_kind", "")))
        stage = mdata.get("lifecycle_stage")
        if stage is not None:
            errs.extend(validate_lifecycle_stage(stage))
        if errs:
            total_fail += 1
            for e in errs:
                violations.append(f"  [{mid}] {e}")
                print(f"  FAIL [{mid}]: {e}")
        else:
            print(f"  PASS [{mid}]")

    # --- 5. Dependency reference integrity ---
    print(f"\n[5/5] Dependency reference integrity")
    dep_issues = 0
    for mid, mdata in sorted(manifests.items()):
        errs = validate_depends_on(mdata, all_module_ids)
        if errs:
            dep_issues += len(errs)
            for e in errs:
                violations.append(f"  {e}")
                print(f"  FAIL: {e}")
    if dep_issues == 0:
        print(f"  OK -- all depends_on references resolve")
    else:
        total_fail += dep_issues

    # --- Summary ---
    print("\n" + "=" * 72)
    print(f"MANIFEST RESULTS: {total_pass} passed, {total_fail} failed")
    if violations:
        print(f"\nViolations ({len(violations)}):")
        for v in violations:
            print(v)
        print("=" * 72)
        return 1
    else:
        print("All manifest validations passed.")
        print("=" * 72)
        return 0


if __name__ == "__main__":
    sys.exit(main())
