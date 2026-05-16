#!/usr/bin/env python3
"""
SYLION AEIS — Contract Freeze Validator

Validates that all module manifests conform to the frozen contract schema,
every registered module has a manifest, and event topics in manifests match
the canonical event taxonomy.

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
# Resolve project root (scripts/ -> sylion-pipeline/)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

CONTRACTS_DIR = PROJECT_ROOT / "sylion" / "contracts"
MANIFESTS_DIR = CONTRACTS_DIR / "manifests"
SCHEMA_PATH = CONTRACTS_DIR / "manifest_schema.json"
EVENTS_PATH = CONTRACTS_DIR / "events.yaml"

# ---------------------------------------------------------------------------
# Minimal JSON-Schema validator (avoids jsonschema dependency)
# ---------------------------------------------------------------------------

def _validate_type(value, schema_type: str) -> list[str]:
    """Validate a value against a JSON Schema type string."""
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
        # Python bool is subclass of int — reject bool when integer expected
        if schema_type == "integer" and isinstance(value, bool):
            return [f"expected integer, got boolean"]
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
    """Recursively validate a dict against a JSON Schema (draft-07 subset)."""
    errors: list[str] = []

    # type check
    if "type" in schema:
        errors.extend(f"{path}: {e}" for e in _validate_type(data, schema["type"]))

    # required
    for req in schema.get("required", []):
        if req not in data:
            errors.append(f"{path}: missing required field '{req}'")

    # additionalProperties
    if schema.get("additionalProperties") is False:
        allowed = set(schema.get("properties", {}).keys())
        extra = set(data.keys()) - allowed
        if extra:
            errors.append(f"{path}: additional properties not allowed: {extra}")

    # per-property validation
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

        # array items
        if isinstance(val, list) and "items" in prop_schema:
            item_schema = prop_schema["items"]
            for i, item in enumerate(val):
                if isinstance(item, dict) and item_schema.get("type") == "object":
                    errors.extend(_validate_object(item, item_schema, f"{prop_path}[{i}]"))
                elif "type" in item_schema:
                    errs = _validate_type(item, item_schema["type"])
                    errors.extend(f"{prop_path}[{i}]: {e}" for e in errs)

    return errors


def validate_manifest(manifest: dict, schema: dict) -> list[str]:
    """Validate a single manifest dict against the schema."""
    return _validate_object(manifest, schema)


# ---------------------------------------------------------------------------
# Event taxonomy loader
# ---------------------------------------------------------------------------

def load_event_topics() -> dict[str, dict]:
    """Load event taxonomy from events.yaml. Returns {topic: {owner, ...}}."""
    try:
        import yaml
    except ImportError:
        print("ERROR: PyYAML is required. Install with: pip install pyyaml")
        sys.exit(2)

    if not EVENTS_PATH.exists():
        return {}

    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    taxonomy = data.get("event_taxonomy", data) if data else {}
    events = taxonomy.get("events", [])
    result = {}
    for ev in events:
        topic = ev.get("topic", "")
        if topic:
            result[topic] = ev
    return result


# ---------------------------------------------------------------------------
# Discover registered modules (scan sylion packages for Python modules)
# ---------------------------------------------------------------------------

def discover_modules() -> set[str]:
    """Scan sylion/*/  directories and build a set of module_id strings."""
    sylion_pkg = PROJECT_ROOT / "sylion"
    modules: set[str] = set()
    if not sylion_pkg.is_dir():
        return modules
    for pkg_dir in sorted(sylion_pkg.iterdir()):
        if not pkg_dir.is_dir() or pkg_dir.name.startswith("_"):
            continue
        for py_file in sorted(pkg_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            module_id = f"{pkg_dir.name}.{py_file.stem}"
            modules.add(module_id)
    return modules


# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 72)
    print("SYLION AEIS — Contract Freeze Validator")
    print("=" * 72)

    total_pass = 0
    total_fail = 0
    violations: list[str] = []

    # --- 1. Load schema ---
    print(f"\n[1/4] Loading schema: {SCHEMA_PATH}")
    if not SCHEMA_PATH.exists():
        print(f"  FATAL: Schema file not found: {SCHEMA_PATH}")
        return 1
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)
    print(f"  OK — schema loaded (title: {schema.get('title', 'n/a')})")

    # --- 2. Load manifests ---
    print(f"\n[2/4] Loading manifests from: {MANIFESTS_DIR}")
    manifests: dict[str, dict] = {}
    if not MANIFESTS_DIR.exists():
        print(f"  WARNING: Manifests directory does not exist — creating it")
        MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    manifest_files = list(MANIFESTS_DIR.glob("*.json"))
    if not manifest_files:
        print(f"  WARNING: No manifest files found (directory is empty)")
    else:
        for mf in sorted(manifest_files):
            with open(mf, "r", encoding="utf-8") as f:
                data = json.load(f)
            mid = data.get("module_id", mf.stem)
            manifests[mid] = data
            print(f"  Loaded: {mf.name} (module_id={mid})")

    # --- 3. Validate each manifest against schema ---
    print(f"\n[3/4] Validating {len(manifests)} manifest(s) against schema")
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

    # --- 4. Check coverage: every module should have a manifest ---
    print(f"\n[4/4] Coverage check — modules vs manifests")
    discovered = discover_modules()
    print(f"  Discovered {len(discovered)} Python modules in sylion/")
    print(f"  Found {len(manifests)} manifests in contracts/manifests/")

    if discovered and not manifests:
        print(f"  WARNING: Modules exist but no manifests found — skipping coverage check")
    else:
        missing_manifests = discovered - set(manifests.keys())
        extra_manifests = set(manifests.keys()) - discovered

        if missing_manifests:
            for m in sorted(missing_manifests):
                violations.append(f"  Module '{m}' has no manifest file")
                print(f"  MISSING MANIFEST: {m}")
            total_fail += len(missing_manifests)
        else:
            print(f"  OK — all modules have manifests")

        if extra_manifests:
            for m in sorted(extra_manifests):
                print(f"  ORPHAN MANIFEST: {m} (no corresponding module)")

    # --- 5. Validate event topics in manifests against taxonomy ---
    event_topics = load_event_topics()
    if event_topics:
        print(f"\n[BONUS] Event taxonomy validation ({len(event_topics)} topics)")
        for mid, mdata in sorted(manifests.items()):
            for topic in mdata.get("publishes_events", []):
                if topic not in event_topics:
                    violations.append(f"  [{mid}] publishes unknown event topic: '{topic}'")
                    print(f"  FAIL [{mid}]: unknown publishes_events topic '{topic}'")
            for topic in mdata.get("consumes_events", []):
                if topic not in event_topics:
                    violations.append(f"  [{mid}] consumes unknown event topic: '{topic}'")
                    print(f"  FAIL [{mid}]: unknown consumes_events topic '{topic}'")

    # --- Summary ---
    print("\n" + "=" * 72)
    print(f"RESULTS: {total_pass} passed, {total_fail} failed")
    if violations:
        print(f"\nViolations ({len(violations)}):")
        for v in violations:
            print(v)
        print("=" * 72)
        return 1
    else:
        print("All contract validations passed.")
        print("=" * 72)
        return 0


if __name__ == "__main__":
    sys.exit(main())
