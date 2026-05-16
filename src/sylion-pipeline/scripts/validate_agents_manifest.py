#!/usr/bin/env python3
"""
SYLION Manifest Validator — Single Source of Truth enforcement.

Validates that agents.yaml is the authoritative manifest:
  1. Agent count consistency across agents.yaml, README.md, definitions.py
  2. No duplicate agent IDs
  3. Required §9.5 metadata fields present for all enabled agents
  4. Stage assignments are valid
  5. requirements.json is marked as derived artifact (if present)

Usage:
  python scripts/validate_agents_manifest.py              # validate
  python scripts/validate_agents_manifest.py --strict      # treat warnings as errors
  python scripts/validate_agents_manifest.py --fix-counts  # auto-fix counts in README/definitions
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Paths (relative to project root)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_YAML = PROJECT_ROOT / "agents.yaml"
README_MD = PROJECT_ROOT / "README.md"
AGENTS_README_MD = PROJECT_ROOT / "agents" / "README.md"
DEFINITIONS_PY = PROJECT_ROOT / "agents" / "definitions.py"
REQUIREMENTS_JSON = PROJECT_ROOT / "requirements.json"

# ---------------------------------------------------------------------------
# §9.5 required metadata fields for enabled agents
# ---------------------------------------------------------------------------
# Fields that every enabled agent MUST have populated (non-default):
REQUIRED_METADATA = {
    "security_impact",       # critical / high / medium / low
    "requires_human_gate",   # bool
}

# Fields that should be present (warnings if missing, not errors):
RECOMMENDED_METADATA = {
    "tier_scope",            # SYLION tiers: G1, G2, etc.
    "allowed_actions",       # whitelisted Safe Runner scenarios
    "forbidden_actions",     # explicitly blocked actions
    "produces_artifacts",    # expected output files
    "acceptance_tests",      # criteria for success
}

VALID_SECURITY_IMPACTS = {"critical", "high", "medium", "low"}
VALID_STAGES = {0, 1, 2, 3, 4, 5, 6, 6.5, 7, 7.5, 8, 8.5, 9}


def load_agents_yaml() -> tuple[dict, list[str]]:
    """Load agents.yaml, return (raw_data, agent_names).

    Handles both dict-of-dicts (canonical) and list-of-dicts formats.
    P2-B fix: normalize list format to dict for consistent downstream processing.
    """
    if not AGENTS_YAML.exists():
        return {}, []
    with open(AGENTS_YAML, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    agents = raw.get("agents", {})

    # Normalize: if agents is a list, convert to dict keyed by 'id' or 'name'
    if isinstance(agents, list):
        agents_dict = {}
        for item in agents:
            if isinstance(item, dict):
                key = item.get("id") or item.get("name") or f"agent_{len(agents_dict)}"
                agents_dict[key] = item
        raw["agents"] = agents_dict
        agents = agents_dict

    return raw, list(agents.keys())


def extract_readme_count(text: str) -> int | None:
    """Extract agent count from README.md header/table."""
    # Match patterns like "42 agentów", "34 agentów", "## 42 agentów"
    m = re.search(r"(\d+)\s+agent[óo]w", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def extract_definitions_count(text: str) -> int | None:
    """Extract agent count from definitions.py docstring/header."""
    # Match patterns like "Definicje 27 agentów", "27 agents"
    m = re.search(r"(\d+)\s+agent[óo]w", text, re.IGNORECASE)
    if not m:
        m = re.search(r"(\d+)\s+agents", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

def check_no_duplicate_ids(agent_names: list[str]) -> list[str]:
    """Check for duplicate agent IDs."""
    errors = []
    seen = set()
    for name in agent_names:
        if name in seen:
            errors.append(f"ERROR: Duplicate agent ID: '{name}'")
        seen.add(name)
    return errors


def check_count_consistency(agent_names: list[str]) -> list[str]:
    """Check that agent count is consistent across files."""
    issues = []
    actual_count = len(agent_names)

    # README.md
    if README_MD.exists():
        readme_text = README_MD.read_text(encoding="utf-8")
        readme_count = extract_readme_count(readme_text)
        if readme_count is not None and readme_count != actual_count:
            issues.append(
                f"ERROR: README.md says {readme_count} agentów, "
                f"agents.yaml has {actual_count}"
            )
    else:
        issues.append("WARN: README.md not found")

    # definitions.py
    if DEFINITIONS_PY.exists():
        defs_text = DEFINITIONS_PY.read_text(encoding="utf-8")
        defs_count = extract_definitions_count(defs_text)
        if defs_count is not None and defs_count != actual_count:
            issues.append(
                f"ERROR: definitions.py says {defs_count} agentów, "
                f"agents.yaml has {actual_count}"
            )
    else:
        issues.append("WARN: agents/definitions.py not found")

    # agents/README.md
    if AGENTS_README_MD.exists():
        agents_readme_text = AGENTS_README_MD.read_text(encoding="utf-8")
        agents_readme_count = extract_readme_count(agents_readme_text)
        if agents_readme_count is not None and agents_readme_count != actual_count:
            issues.append(
                f"ERROR: agents/README.md says {agents_readme_count} agentów, "
                f"agents.yaml has {actual_count}"
            )
        # Check for canonical source annotation
        if "agents.yaml" not in agents_readme_text:
            issues.append(
                "WARN: agents/README.md does not reference agents.yaml as canonical source"
            )
    else:
        issues.append("WARN: agents/README.md not found")

    return issues


def check_metadata_completeness(raw: dict) -> list[str]:
    """Check §9.5 metadata completeness for all enabled agents."""
    issues = []
    agents = raw.get("agents", {})

    for name, cfg in agents.items():
        if not cfg.get("enabled", True):
            continue

        # Required fields
        si = cfg.get("security_impact")
        if not si:
            issues.append(
                f"ERROR: {name} — missing required metadata: security_impact"
            )
        elif si not in VALID_SECURITY_IMPACTS:
            issues.append(
                f"ERROR: {name} — invalid security_impact='{si}' "
                f"(allowed: {VALID_SECURITY_IMPACTS})"
            )

        # requires_human_gate must be explicitly set (not relying on default)
        if "requires_human_gate" not in cfg:
            issues.append(
                f"WARN: {name} — requires_human_gate not explicitly set "
                f"(defaulting to True)"
            )

        # Recommended fields
        for field_name in RECOMMENDED_METADATA:
            val = cfg.get(field_name)
            if val is None or val == []:
                issues.append(
                    f"WARN: {name} — recommended metadata '{field_name}' is empty"
                )

        # Cross-checks
        if cfg.get("produces_artifacts") and not cfg.get("acceptance_tests"):
            issues.append(
                f"WARN: {name} — produces artifacts but no acceptance_tests"
            )

        allowed = set(cfg.get("allowed_actions", []))
        forbidden = set(cfg.get("forbidden_actions", []))
        overlap = allowed & forbidden
        if overlap:
            issues.append(
                f"ERROR: {name} — overlapping allowed/forbidden actions: {overlap}"
            )

    return issues


def check_valid_stages(raw: dict) -> list[str]:
    """Check that all agent stages are valid."""
    issues = []
    agents = raw.get("agents", {})
    for name, cfg in agents.items():
        stage = cfg.get("stage", 0)
        if stage not in VALID_STAGES:
            issues.append(
                f"ERROR: {name} — invalid stage={stage} "
                f"(valid: {sorted(VALID_STAGES)})"
            )
    return issues


def check_derived_artifacts() -> list[str]:
    """Check that requirements.json is marked as derived artifact."""
    issues = []
    if REQUIREMENTS_JSON.exists():
        try:
            import json
            data = json.loads(REQUIREMENTS_JSON.read_text(encoding="utf-8"))
            meta = data.get("_meta", {})
            if not meta.get("derived"):
                issues.append(
                    "WARN: requirements.json exists but not marked as derived "
                    "artifact (_meta.derived should be true)"
                )
        except (json.JSONDecodeError, AttributeError):
            issues.append("WARN: requirements.json exists but is not valid JSON")
    return issues


def check_coordinator_count(raw: dict) -> list[str]:
    """Check that coordinator prompt doesn't contain stale agent count."""
    issues = []
    agents = raw.get("agents", {})
    actual_count = len(agents)

    # Check definitions.py for hardcoded counts in create_coordinator
    if DEFINITIONS_PY.exists():
        defs_text = DEFINITIONS_PY.read_text(encoding="utf-8")
        # Find "Zarządzasz X agentami" patterns
        for m in re.finditer(r"[Zz]arządzasz\s+(\d+)\s+agent", defs_text):
            stated = int(m.group(1))
            if stated != actual_count:
                issues.append(
                    f"ERROR: definitions.py create_coordinator says "
                    f"'Zarządzasz {stated} agentami' but actual count is "
                    f"{actual_count}"
                )
    return issues


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def validate(strict: bool = False) -> int:
    """Run all validations. Returns exit code (0 = OK, 1 = errors found)."""
    raw, agent_names = load_agents_yaml()

    if not agent_names:
        print("FATAL: agents.yaml is empty or missing")
        return 1

    print(f"📋 agents.yaml: {len(agent_names)} agents found")
    print(f"   IDs: {', '.join(agent_names[:10])}{'...' if len(agent_names) > 10 else ''}")
    print()

    all_issues: list[str] = []

    checks = [
        ("Duplicate IDs", check_no_duplicate_ids(agent_names)),
        ("Count consistency", check_count_consistency(agent_names)),
        ("§9.5 Metadata", check_metadata_completeness(raw)),
        ("Valid stages", check_valid_stages(raw)),
        ("Derived artifacts", check_derived_artifacts()),
        ("Coordinator count", check_coordinator_count(raw)),
    ]

    for check_name, issues in checks:
        if issues:
            print(f"{'❌' if any(i.startswith('ERROR') for i in issues) else '⚠️ '} {check_name}:")
            for issue in issues:
                print(f"    {issue}")
            print()
        else:
            print(f"✅ {check_name}: OK")

        all_issues.extend(issues)

    # Summary
    errors = [i for i in all_issues if i.startswith("ERROR")]
    warnings = [i for i in all_issues if i.startswith("WARN")]

    print()
    print(f"{'='*60}")
    print(f"  Errors:   {len(errors)}")
    print(f"  Warnings: {len(warnings)}")
    print(f"{'='*60}")

    if errors:
        print("\n❌ VALIDATION FAILED — fix errors before proceeding")
        return 1
    elif strict and warnings:
        print("\n⚠️  VALIDATION FAILED (--strict) — fix warnings")
        return 1
    elif warnings:
        print("\n⚠️  VALIDATION PASSED with warnings")
        return 0
    else:
        print("\n✅ VALIDATION PASSED — all checks OK")
        return 0


def fix_counts():
    """Auto-fix agent counts in README.md and definitions.py."""
    raw, agent_names = load_agents_yaml()
    actual_count = len(agent_names)

    if README_MD.exists():
        text = README_MD.read_text(encoding="utf-8")
        new_text = re.sub(
            r"(\d+)\s+agentów",
            f"{actual_count} agentów",
            text
        )
        if new_text != text:
            README_MD.write_text(new_text, encoding="utf-8")
            print(f"✅ README.md: updated agent count to {actual_count}")
        else:
            print(f"ℹ️  README.md: no changes needed")

    if DEFINITIONS_PY.exists():
        text = DEFINITIONS_PY.read_text(encoding="utf-8")
        new_text = re.sub(
            r"(Definicje\s+)\d+(\s+agentów)",
            rf"\g<1>{actual_count}\g<2>",
            text,
        )
        # Also fix "Zarządzasz N agentami"
        new_text = re.sub(
            r"([Zz]arządzasz\s+)\d+(\s+agent)",
            rf"\g<1>{actual_count}\g<2>",
            new_text,
        )
        if new_text != text:
            DEFINITIONS_PY.write_text(new_text, encoding="utf-8")
            print(f"✅ definitions.py: updated agent count to {actual_count}")
        else:
            print(f"ℹ️  definitions.py: no changes needed")

    # agents/README.md
    if AGENTS_README_MD.exists():
        text = AGENTS_README_MD.read_text(encoding="utf-8")
        new_text = re.sub(
            r"(\d+)\s+[Aa]gent[óo]w",
            f"{actual_count} Agentów",
            text
        )
        if new_text != text:
            AGENTS_README_MD.write_text(new_text, encoding="utf-8")
            print(f"✅ agents/README.md: updated agent count to {actual_count}")
        else:
            print(f"ℹ️  agents/README.md: no changes needed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SYLION Manifest Validator — Single Source of Truth enforcement"
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Treat warnings as errors"
    )
    parser.add_argument(
        "--fix-counts", action="store_true",
        help="Auto-fix agent counts in README.md and definitions.py"
    )
    args = parser.parse_args()

    if args.fix_counts:
        fix_counts()
        sys.exit(0)

    sys.exit(validate(strict=args.strict))
