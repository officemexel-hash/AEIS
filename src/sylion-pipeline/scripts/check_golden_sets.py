#!/usr/bin/env python3
"""
SYLION AEIS — Golden Set Runner

For each golden set JSON file in sylion/contracts/golden_sets/, this script:
  1. Imports the specified module and class
  2. Calls the specified method with golden input
  3. Compares the result against the expected output
  4. Reports deviations

Golden set files are JSON with this shape:
{
  "class": "A",
  "module": "core.module_registry",
  "tests": [
    {
      "method": "register",
      "input": {...},
      "expected": {...}
    }
  ]
}

Exit codes:
  0 = all golden tests pass
  1 = one or more deviations detected
"""

from __future__ import annotations

import dataclasses
import enum
import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any, get_type_hints

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Ensure project root is on sys.path so `import sylion.*` works
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CONTRACTS_DIR = PROJECT_ROOT / "sylion" / "contracts"
GOLDEN_SETS_DIR = CONTRACTS_DIR / "golden_sets"


# ---------------------------------------------------------------------------
# Deep subset matching: actual must contain all keys/values from expected
# ---------------------------------------------------------------------------

def _deep_match(actual: Any, expected: Any, path: str = "") -> list[str]:
    """Check that `actual` is a superset of `expected` (recursive)."""
    deviations: list[str] = []

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            deviations.append(f"{path or 'root'}: expected dict, got {type(actual).__name__}")
            return deviations
        for key, exp_val in expected.items():
            sub_path = f"{path}.{key}" if path else key
            if key not in actual:
                deviations.append(f"{sub_path}: missing key (expected {exp_val!r})")
            else:
                deviations.extend(_deep_match(actual[key], exp_val, sub_path))
    elif isinstance(expected, list):
        if not isinstance(actual, list):
            deviations.append(f"{path or 'root'}: expected list, got {type(actual).__name__}")
            return deviations
        if len(actual) != len(expected):
            deviations.append(
                f"{path or 'root'}: list length mismatch (expected {len(expected)}, got {len(actual)})"
            )
        for i, (a_item, e_item) in enumerate(zip(actual, expected)):
            deviations.extend(_deep_match(a_item, e_item, f"{path}[{i}]"))
    else:
        if actual != expected:
            deviations.append(
                f"{path or 'root'}: value mismatch (expected {expected!r}, got {actual!r})"
            )

    return deviations


# ---------------------------------------------------------------------------
# Import helper
# ---------------------------------------------------------------------------

def _import_target(module_fqn: str):
    """Import a module from sylion.<module_fqn>."""
    parts = module_fqn.split(".")
    if len(parts) < 2:
        raise ImportError(f"Module name must have at least 2 parts (package.module), got: {module_fqn}")
    full_import = f"sylion.{module_fqn}"
    return importlib.import_module(full_import)


# ---------------------------------------------------------------------------
# Type coercion helper
# ---------------------------------------------------------------------------

def _coerce_for_dataclass(cls: type, input_dict: dict) -> dict:
    """Coerce values in input_dict so they match the dataclass field types.

    Handles:
      - Enum fields: converts string/value -> Enum member
      - Other fields: passes through as-is
    """
    coerced = dict(input_dict)
    hints = {}
    try:
        hints = get_type_hints(cls)
    except Exception:
        pass

    for field_obj in dataclasses.fields(cls):
        fname = field_obj.name
        if fname not in coerced:
            continue
        ftype = hints.get(fname, field_obj.type)
        # Resolve string annotations
        if isinstance(ftype, str):
            try:
                ftype = eval(ftype, vars(sys.modules[cls.__module__]), {})
            except Exception:
                continue
        # Enum coercion
        if isinstance(ftype, type) and issubclass(ftype, enum.Enum):
            val = coerced[fname]
            if not isinstance(val, ftype):
                try:
                    coerced[fname] = ftype(val)
                except (ValueError, KeyError):
                    pass  # let the dataclass constructor raise the real error
    return coerced


# ---------------------------------------------------------------------------
# Test runner for a single golden set file
# ---------------------------------------------------------------------------

def run_golden_set(gs_path: Path) -> tuple[int, int, list[str]]:
    """Run one golden set file. Returns (passed, failed, details)."""
    with open(gs_path, "r", encoding="utf-8") as f:
        gs_data = json.load(f)

    module_fqn = gs_data.get("module", "")
    tests = gs_data.get("tests", [])
    class_letter = gs_data.get("class", "?")

    passed = 0
    failed = 0
    details: list[str] = []

    if not module_fqn:
        details.append(f"  SKIP: no 'module' field in golden set")
        return 0, 0, details

    # Import the module
    try:
        mod = _import_target(module_fqn)
    except ImportError as e:
        for t in tests:
            method = t.get("method", "?")
            details.append(f"  FAIL [{module_fqn}.{method}]: import error: {e}")
            failed += 1
        return passed, failed, details

    # Run each test case
    for test in tests:
        method_name = test.get("method", "?")
        test_input = test.get("input", {})
        expected = test.get("expected", {})
        setup = test.get("setup", None)

        full_label = f"{module_fqn}::{method_name} (class {class_letter})"

        # Find the callable — could be a class method or module-level function
        target = None

        # Try module-level function first
        if hasattr(mod, method_name):
            target = getattr(mod, method_name)
        else:
            # Try common class names from the module
            # Convention: the module name's second part in CamelCase
            class_candidates = []
            for attr_name in dir(mod):
                obj = getattr(mod, attr_name)
                if isinstance(obj, type):
                    class_candidates.append(obj)

            for cls in class_candidates:
                if hasattr(cls, method_name):
                    target = getattr(cls, method_name)
                    break

        if target is None:
            details.append(f"  FAIL [{full_label}]: method '{method_name}' not found in module")
            failed += 1
            continue

        try:
            # Discover classes in the module for instance construction
            class_candidates = []
            for attr_name in dir(mod):
                obj = getattr(mod, attr_name)
                if isinstance(obj, type):
                    class_candidates.append(obj)

            # If setup is specified, try to construct an instance
            instance = None
            if setup is not None:
                for cls in class_candidates:
                    try:
                        instance = cls(**setup) if isinstance(setup, dict) else cls()
                        break
                    except Exception:
                        continue

            # Resolve method arguments intelligently
            # Handle methods that expect dataclass/typed objects as first positional arg
            args: list[Any] = []
            kwargs: dict[str, Any] = {}

            try:
                sig = inspect.signature(target)
                params = list(sig.parameters.values())
                # Skip 'self' if bound method
                if instance is not None and params and params[0].name == 'self':
                    params = params[1:]

                if params and isinstance(test_input, dict):
                    first_param = params[0]
                    ann = first_param.annotation

                    # Resolve string annotations (from __future__ import annotations)
                    if isinstance(ann, str):
                        try:
                            mod_globals = vars(mod)
                            ann = eval(ann, mod_globals)
                        except Exception:
                            pass

                    # Check if first param expects a dataclass that we can build from input
                    is_dc = False
                    if ann is not inspect.Parameter.empty:
                        try:
                            is_dc = dataclasses.is_dataclass(ann)
                        except TypeError:
                            pass

                    if is_dc and dataclasses.is_dataclass(ann):
                        # Build the dataclass from the input dict (with type coercion)
                        coerced_input = _coerce_for_dataclass(ann, test_input)
                        obj = ann(**coerced_input)
                        args.append(obj)
                        params = params[1:]
                    elif len(params) == 1 and first_param.kind in (
                        inspect.Parameter.VAR_POSITIONAL,
                        inspect.Parameter.VAR_KEYWORD,
                    ):
                        kwargs = test_input
                    else:
                        # Try to match input keys to parameter names
                        for p in params:
                            if p.name in test_input:
                                kwargs[p.name] = test_input[p.name]
                            elif p.default is inspect.Parameter.empty:
                                # Required param not in input — try passing whole dict
                                args.append(test_input)
                                break
                elif isinstance(test_input, dict):
                    kwargs = test_input
                else:
                    args.append(test_input)
            except (ValueError, TypeError):
                # Fallback: pass as kwargs
                if isinstance(test_input, dict):
                    kwargs = test_input
                else:
                    args.append(test_input)

            # Execute the method
            if instance is not None:
                result = target(instance, *args, **kwargs)
            else:
                result = target(*args, **kwargs)

            # Compare result with expected
            if isinstance(result, dict):
                deviations = _deep_match(result, expected)
            elif isinstance(result, bool):
                deviations = [] if result == expected else [
                    f"  value mismatch (expected {expected!r}, got {result!r})"
                ]
            else:
                deviations = _deep_match(result, expected)

            if deviations:
                details.append(f"  FAIL [{full_label}]:")
                for d in deviations:
                    details.append(f"    {d}")
                failed += 1
            else:
                details.append(f"  PASS [{full_label}]")
                passed += 1

        except Exception as exc:
            details.append(f"  FAIL [{full_label}]: execution error: {exc}")
            failed += 1

    return passed, failed, details


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 72)
    print("SYLION AEIS — Golden Set Runner")
    print("=" * 72)

    total_pass = 0
    total_fail = 0

    # Ensure golden_sets directory exists
    if not GOLDEN_SETS_DIR.exists():
        print(f"\nCreating golden sets directory: {GOLDEN_SETS_DIR}")
        GOLDEN_SETS_DIR.mkdir(parents=True, exist_ok=True)

    golden_files = sorted(GOLDEN_SETS_DIR.glob("*.json"))
    if not golden_files:
        print(f"\nWARNING: No golden set files found in {GOLDEN_SETS_DIR}")
        print("  Create JSON files with test definitions (see check_golden_sets.py docstring)")
        print("  Treating empty golden sets as PASS (nothing to validate).")
        print("\nAll golden set checks passed (0/0).")
        print("=" * 72)
        return 0

    print(f"\nFound {len(golden_files)} golden set file(s):")
    for gf in golden_files:
        print(f"  - {gf.name}")

    for gf in golden_files:
        print(f"\n--- {gf.name} ---")
        p, f, details = run_golden_set(gf)
        total_pass += p
        total_fail += f
        for d in details:
            print(d)

    # Summary
    print("\n" + "=" * 72)
    print(f"GOLDEN SET RESULTS: {total_pass} passed, {total_fail} failed")

    if total_fail > 0:
        print("One or more golden set tests FAILED.")
        print("=" * 72)
        return 1
    else:
        print("All golden set tests passed.")
        print("=" * 72)
        return 0


if __name__ == "__main__":
    sys.exit(main())
