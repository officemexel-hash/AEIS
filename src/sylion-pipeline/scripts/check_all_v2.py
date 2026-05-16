#!/usr/bin/env python3
"""
SYLION AEIS -- Master CI Runner (v2)

Orchestrates all contract-validation check scripts in sequence and prints a
unified pass/fail summary.  This is the single entry point for CI pipelines.

Checks executed (in order):
  1. check_manifests      -- manifest schema compliance
  2. check_contracts       -- contract freeze validation
  3. check_golden_sets     -- golden set regression tests
  4. check_imports         -- import dependency boundary enforcement
  5. check_lifecycle_gates -- lifecycle gate compliance

Exit codes:
  0 = all checks pass
  1 = one or more checks fail
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Ensure project root is on sys.path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Check definitions
# ---------------------------------------------------------------------------

CHECKS = [
    {
        "name": "check_manifests",
        "module": "scripts.check_manifests",
        "main_fn": "main",
        "description": "Manifest schema compliance",
    },
    {
        "name": "check_contracts",
        "module": "scripts.check_contracts",
        "main_fn": "main",
        "description": "Contract freeze validation",
    },
    {
        "name": "check_golden_sets",
        "module": "scripts.check_golden_sets",
        "main_fn": "main",
        "description": "Golden set regression tests",
    },
    {
        "name": "check_imports",
        "module": "scripts.check_imports",
        "main_fn": "main",
        "description": "Import dependency boundaries",
    },
    {
        "name": "check_lifecycle_gates",
        "module": "scripts.check_lifecycle_gates",
        "main_fn": "main",
        "description": "Lifecycle gate compliance",
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_check(check: dict) -> int:
    """Import and execute a single check module. Returns its exit code."""
    mod = importlib.import_module(check["module"])
    main_fn = getattr(mod, check["main_fn"])
    return main_fn()


def main() -> int:
    print("=" * 72)
    print("SYLION AEIS -- Master CI Runner (v2)")
    print("=" * 72)
    print(f"Running {len(CHECKS)} check(s)...\n")

    results: list[tuple[str, str, int]] = []  # (name, description, exit_code)

    for i, check in enumerate(CHECKS, 1):
        print(f"\n{'=' * 72}")
        print(f"[{i}/{len(CHECKS)}] {check['name']}: {check['description']}")
        print(f"{'=' * 72}")
        try:
            exit_code = run_check(check)
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            exit_code = 1
        status = "PASS" if exit_code == 0 else "FAIL"
        results.append((check["name"], check["description"], exit_code))
        print(f"\n  >> {check['name']}: {status} (exit={exit_code})")

    # --- Unified summary ---
    print("\n" + "=" * 72)
    print("SYLION AEIS -- CI SUMMARY")
    print("=" * 72)

    all_passed = True
    for name, desc, code in results:
        status = "PASS" if code == 0 else "FAIL"
        if code != 0:
            all_passed = False
        print(f"  {status:4s}  {name:30s}  {desc}")

    print("=" * 72)

    if all_passed:
        print("ALL CHECKS PASSED.")
        return 0
    else:
        print("ONE OR MORE CHECKS FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
