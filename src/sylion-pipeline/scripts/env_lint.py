#!/usr/bin/env python3
"""
env_lint.py — Sylion Pipeline environment variable drift linter.

Usage:
    python scripts/env_lint.py [--env-example PATH] [--source-dirs DIR...] [--json]

Exit codes:
    0  No drift detected
    1  Drift detected (missing_in_example or unused_in_code count > 0)
    2  Internal error (file not found, parse failure)

Reports:
    - missing_in_example : variables used in code but absent from .env.example
    - unused_in_code     : variables in .env.example not referenced in scanned sources
    - deprecated         : variables commented-out in .env.example (informational)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------
DEFAULT_ENV_EXAMPLE = ".env.example"
DEFAULT_SOURCE_DIRS = ["sylion", "."]
DEFAULT_SOURCE_FILES = [
    "sylion/server.py",
    "sylion/api/router.py",
    "orchestrator.py",
    "config.py",
    "dashboard_server.py",
]

# Pattern matches:  os.getenv("VAR") / os.environ.get("VAR") / os.environ["VAR"]
ENV_ACCESS_RE = re.compile(
    r'os\.(?:environ\.get|getenv)\(\s*["\']([A-Z][A-Z0-9_]+)["\']'
    r'|os\.environ\[\s*["\']([A-Z][A-Z0-9_]+)["\']\s*\]'
)

# Matches a non-commented key=value line in .env.example
ENV_EXAMPLE_KEY_RE = re.compile(r'^([A-Z][A-Z0-9_]+)\s*=')

# Matches a commented-out key in .env.example: "# KEY=..."
ENV_DEPRECATED_RE = re.compile(r'^#\s*([A-Z][A-Z0-9_]+)\s*=')

# API key variables (always "required" conceptually — flag if missing in code scan scope)
API_KEY_VARS = {
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY",
    "DEEPSEEK_API_KEY", "PERPLEXITY_API_KEY", "OPENHANDS_API_KEY", "OLLAMA_API_KEY",
}

# Variables set at runtime / by orchestrator — not expected to be in example
RUNTIME_SET_VARS = {"SYLION_PHANTOM_PATH"}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_env_example(path: Path) -> tuple[set[str], set[str]]:
    """
    Returns (active_vars, deprecated_vars).
    active_vars   — non-commented KEY= lines
    deprecated_vars — commented-out KEY= lines (# KEY=...)
    """
    active: set[str] = set()
    deprecated: set[str] = set()

    if not path.exists():
        print(f"ERROR: .env.example not found at {path}", file=sys.stderr)
        sys.exit(2)

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        m = ENV_EXAMPLE_KEY_RE.match(line)
        if m:
            active.add(m.group(1))
            continue
        m2 = ENV_DEPRECATED_RE.match(line)
        if m2:
            deprecated.add(m2.group(1))

    return active, deprecated


def parse_source_files(source_files: list[Path]) -> dict[str, list[str]]:
    """
    Returns dict: variable_name -> list of file paths where it is referenced.
    """
    found: dict[str, list[str]] = {}

    for fpath in source_files:
        if not fpath.exists():
            print(f"WARNING: source file not found, skipping: {fpath}", file=sys.stderr)
            continue
        content = fpath.read_text(encoding="utf-8", errors="replace")
        for m in ENV_ACCESS_RE.finditer(content):
            name = m.group(1) or m.group(2)
            if name:
                found.setdefault(name, []).append(str(fpath))

    return found


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def build_report(
    example_active: set[str],
    example_deprecated: set[str],
    code_vars: dict[str, list[str]],
) -> dict:
    code_var_names = set(code_vars.keys())

    # Exclude vars that are runtime-set (not read via getenv)
    code_readable = code_var_names - RUNTIME_SET_VARS

    missing_in_example = sorted(code_readable - example_active - example_deprecated)
    unused_in_code = sorted(
        (example_active - code_var_names - API_KEY_VARS)
    )
    deprecated = sorted(example_deprecated)

    return {
        "summary": {
            "total_in_example": len(example_active),
            "total_in_code": len(code_var_names),
            "missing_in_example": len(missing_in_example),
            "unused_in_code": len(unused_in_code),
            "deprecated": len(deprecated),
        },
        "missing_in_example": missing_in_example,
        "unused_in_code": unused_in_code,
        "deprecated": deprecated,
        "all_code_vars": {k: list(set(v)) for k, v in sorted(code_vars.items())},
        "all_example_vars": sorted(example_active),
    }


def print_report(report: dict, use_json: bool) -> None:
    if use_json:
        print(json.dumps(report, indent=2))
        return

    s = report["summary"]
    width = 70
    print("=" * width)
    print("  SYLION env_lint.py — Environment Variable Drift Report")
    print("=" * width)
    print(f"  Variables in .env.example : {s['total_in_example']}")
    print(f"  Variables in code         : {s['total_in_code']}")
    print(f"  Missing in .env.example   : {s['missing_in_example']}  {'<-- DRIFT!' if s['missing_in_example'] else 'OK'}")
    print(f"  Unused in code            : {s['unused_in_code']}  {'<-- WARNING' if s['unused_in_code'] else 'OK'}")
    print(f"  Deprecated (commented)    : {s['deprecated']}")
    print("=" * width)

    if report["missing_in_example"]:
        print("\n[MISSING IN .env.example]")
        for v in report["missing_in_example"]:
            files = report["all_code_vars"].get(v, [])
            print(f"  {v:50s}  ({', '.join(files)})")

    if report["unused_in_code"]:
        print("\n[UNUSED IN CODE — consider removing from .env.example]")
        for v in report["unused_in_code"]:
            print(f"  {v}")

    if report["deprecated"]:
        print("\n[DEPRECATED — commented out in .env.example]")
        for v in report["deprecated"]:
            print(f"  # {v}")

    print()
    if s["missing_in_example"] > 0:
        print("RESULT: FAIL — drift detected. Update .env.example.")
    elif s["unused_in_code"] > 0:
        print("RESULT: WARN — unused vars in .env.example (no code references found).")
    else:
        print("RESULT: PASS — no drift detected.")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lint .env.example against actual env-var usage in source code.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--env-example",
        default=DEFAULT_ENV_EXAMPLE,
        help=f"Path to .env.example (default: {DEFAULT_ENV_EXAMPLE})",
    )
    parser.add_argument(
        "--source-files",
        nargs="+",
        default=DEFAULT_SOURCE_FILES,
        help="Python source files to scan (default: the 5 standard Sylion files)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output report as JSON",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        default=False,
        help="Always exit 0 (informational mode)",
    )

    args = parser.parse_args()

    env_example_path = Path(args.env_example)
    source_files = [Path(f) for f in args.source_files]

    example_active, example_deprecated = parse_env_example(env_example_path)
    code_vars = parse_source_files(source_files)

    report = build_report(example_active, example_deprecated, code_vars)
    print_report(report, use_json=args.json)

    if args.no_fail:
        sys.exit(0)

    drift = report["summary"]["missing_in_example"]
    sys.exit(1 if drift > 0 else 0)


if __name__ == "__main__":
    main()
