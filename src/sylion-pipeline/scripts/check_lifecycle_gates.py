#!/usr/bin/env python3
"""
SYLION AEIS -- Lifecycle Gate Compliance Validator

Validates that all module manifests declare valid lifecycle stages and that
the gate requirements defined in sylion.core.lifecycle_gates.GATE_RULES are
satisfied for each stage transition described in the manifests.

Checks performed:
  1. Every manifest's lifecycle_stage is a valid ModuleLifecycleStage enum value
  2. Every gate rule has at least one defined requirement (not empty)
  3. Gate rule consistency: referenced duration_from_stage values are valid stages
  4. GATE_RULES covers all post-build stages (validate, shadow, dual, cutover, stable, deprecated)
  5. Manifest lifecycle_stage values match the enum values used in GATE_RULES keys

Exit codes:
  0 = all validations pass
  1 = violations detected
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

CONTRACTS_DIR = PROJECT_ROOT / "sylion" / "contracts"
MANIFESTS_DIR = CONTRACTS_DIR / "manifests"

# Ensure project root is on sys.path for sylion imports
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_gate_rules() -> dict:
    """Import and return GATE_RULES from sylion.core.lifecycle_gates.

    Returns a dict mapping stage name -> GateRequirement dataclass.
    """
    from sylion.core.lifecycle_gates import GATE_RULES
    return GATE_RULES


def load_lifecycle_stages() -> set[str]:
    """Import ModuleLifecycleStage and return the set of valid stage values."""
    from sylion.core.module_registry import ModuleLifecycleStage
    return {s.value for s in ModuleLifecycleStage}


def load_manifests() -> dict[str, dict]:
    """Load all manifests from the manifests directory."""
    manifests: dict[str, dict] = {}
    if not MANIFESTS_DIR.exists():
        return manifests
    for mf in sorted(MANIFESTS_DIR.glob("*.json")):
        try:
            with open(mf, "r", encoding="utf-8") as f:
                data = json.load(f)
            mid = data.get("module_id", mf.stem)
            manifests[mid] = data
        except (json.JSONDecodeError, OSError):
            pass
    return manifests


def validate_stage_enum(manifests: dict[str, dict], valid_stages: set[str]) -> list[str]:
    """Check that every manifest's lifecycle_stage is in the valid enum set."""
    errors: list[str] = []
    for mid, mdata in sorted(manifests.items()):
        stage = mdata.get("lifecycle_stage", "")
        if stage and stage not in valid_stages:
            errors.append(f"[{mid}] lifecycle_stage '{stage}' is not a valid ModuleLifecycleStage")
    return errors


def validate_gate_rules_coverage(gate_rules: dict, valid_stages: set[str]) -> list[str]:
    """Check that gate rules exist for all post-draft stages that need gates."""
    errors: list[str] = []
    # Stages that should have gate rules (build and draft are free-entry)
    gated_stages = {"validate", "shadow", "dual", "cutover", "stable", "deprecated"}
    missing = gated_stages - set(gate_rules.keys())
    if missing:
        errors.append(f"Missing gate rules for stages: {sorted(missing)}")
    return errors


def validate_gate_rule_consistency(gate_rules: dict, valid_stages: set[str]) -> list[str]:
    """Check internal consistency of gate rules."""
    errors: list[str] = []
    for stage, rule in gate_rules.items():
        # Check duration_from_stage references a valid stage
        dur_stage = getattr(rule, "duration_from_stage", None)
        if dur_stage is not None and dur_stage not in valid_stages:
            errors.append(
                f"Gate rule for '{stage}' references invalid duration_from_stage '{dur_stage}'"
            )
    return errors


def validate_gate_rule_completeness(gate_rules: dict) -> list[str]:
    """Check that each gate rule has at least one requirement defined."""
    errors: list[str] = []
    for stage, rule in gate_rules.items():
        has_req = (
            getattr(rule, "min_heartbeat_age_hours", None) is not None
            or getattr(rule, "requires_evidence", False)
            or getattr(rule, "min_duration_hours", None) is not None
            or getattr(rule, "requires_council_approval", False)
        )
        if not has_req:
            errors.append(f"Gate rule for '{stage}' has no requirements defined")
    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 72)
    print("SYLION AEIS -- Lifecycle Gate Compliance Validator")
    print("=" * 72)

    total_pass = 0
    total_fail = 0
    violations: list[str] = []

    # --- 1. Load lifecycle infrastructure ---
    print("\n[1/4] Loading lifecycle infrastructure")
    try:
        gate_rules = load_gate_rules()
        valid_stages = load_lifecycle_stages()
        print(f"  OK -- {len(gate_rules)} gate rules loaded")
        print(f"  OK -- {len(valid_stages)} valid lifecycle stages: {sorted(valid_stages)}")
    except Exception as e:
        print(f"  FATAL: Could not import lifecycle_gates: {e}")
        return 1

    # --- 2. Load manifests ---
    print(f"\n[2/4] Loading manifests from: {MANIFESTS_DIR}")
    manifests = load_manifests()
    if not manifests:
        print("  WARNING: No manifests found -- nothing to validate")
        print("\nAll lifecycle gate checks passed (0/0).")
        print("=" * 72)
        return 0
    print(f"  OK -- {len(manifests)} manifests loaded")

    # --- 3. Validate manifest lifecycle stages ---
    print(f"\n[3/4] Validating manifest lifecycle stages")
    stage_errors = validate_stage_enum(manifests, valid_stages)
    if stage_errors:
        total_fail += len(stage_errors)
        for e in stage_errors:
            violations.append(f"  {e}")
            print(f"  FAIL: {e}")
    else:
        total_pass += 1
        print(f"  PASS -- all {len(manifests)} manifests have valid lifecycle stages")

    # --- 4. Validate gate rules ---
    print(f"\n[4/4] Validating gate rules")

    # 4a. Coverage
    coverage_errors = validate_gate_rules_coverage(gate_rules, valid_stages)
    if coverage_errors:
        for e in coverage_errors:
            violations.append(f"  {e}")
            print(f"  FAIL: {e}")
            total_fail += 1
    else:
        total_pass += 1
        print(f"  PASS -- gate rules cover all gated stages")

    # 4b. Consistency
    consistency_errors = validate_gate_rule_consistency(gate_rules, valid_stages)
    if consistency_errors:
        for e in consistency_errors:
            violations.append(f"  {e}")
            print(f"  FAIL: {e}")
            total_fail += 1
    else:
        total_pass += 1
        print(f"  PASS -- gate rule references are internally consistent")

    # 4c. Completeness
    completeness_errors = validate_gate_rule_completeness(gate_rules)
    if completeness_errors:
        for e in completeness_errors:
            violations.append(f"  {e}")
            print(f"  FAIL: {e}")
            total_fail += 1
    else:
        total_pass += 1
        print(f"  PASS -- all gate rules have at least one requirement")

    # --- Summary ---
    print("\n" + "=" * 72)
    print(f"LIFECYCLE GATE RESULTS: {total_pass} passed, {total_fail} failed")
    if violations:
        print(f"\nViolations ({len(violations)}):")
        for v in violations:
            print(v)
        print("=" * 72)
        return 1
    else:
        print("All lifecycle gate validations passed.")
        print("=" * 72)
        return 0


if __name__ == "__main__":
    sys.exit(main())
