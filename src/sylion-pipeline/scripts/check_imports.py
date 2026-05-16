#!/usr/bin/env python3
"""
SYLION AEIS — Import Dependency Checker

Scans all .py files under sylion/ (excluding tests/) and checks every import
against the dependency rules defined in .import-linter.yml.

Rules enforced (R2.5 from Ksiega/Masterplan):
  1. Only sylion.core.* may be imported by any other package (kernel layer)
  2. Same-package imports are always allowed
  3. Cross-package imports between non-core packages are FORBIDDEN
  4. sylion.api is a facade — it may import from any package
  5. All cross-package communication must go through EventBus / Contract Registry

Usage:
    python scripts/check_imports.py [--config .import-linter.yml] [--root sylion/]

Exit codes:
    0 — no violations
    1 — violations found
    2 — configuration or runtime error
"""

from __future__ import annotations

import ast
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration — mirrors .import-linter.yml structure
# ---------------------------------------------------------------------------

# All known sylion sub-packages (boundaries)
ALL_PACKAGES = [
    "sylion.core",
    "sylion.governance",
    "sylion.memory",
    "sylion.cognitive",
    "sylion.execution",
    "sylion.security",
    "sylion.efficiency",
    "sylion.aeis",
    "sylion.skills",
    "sylion.surface",
    "sylion.rebuild",
    "sylion.quality",
    "sylion.api",
    "sylion.devices",
    "sylion.sdr",
    "sylion.cellular",
    "sylion.db",
    "sylion.contracts",
]

# Packages that ANY package can import from (kernel)
ALLOWED_IMPORT_TARGET_FOR_ALL = {"sylion.core"}

# Special facade packages: api can import from any domain package
FACADE_PACKAGES = {"sylion.api"}

# Packages that facade packages may import from (all domain + core)
# Set at runtime based on ALL_PACKAGES

# Standard library top-level modules (Python 3.11+)
# This is a subset — we use a heuristic: if it doesn't start with "sylion" it's external
SYLION_PREFIX = "sylion."


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ImportViolation:
    """A single import dependency rule violation."""
    file_path: str
    line_number: int
    import_statement: str
    source_package: str
    target_package: str
    rule_description: str


@dataclass
class ScanResult:
    """Result of scanning all files."""
    total_files: int = 0
    total_imports: int = 0
    violations: list[ImportViolation] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def determine_package(file_path: str, root_dir: str) -> Optional[str]:
    """Determine which sylion sub-package a file belongs to.

    Returns the package name (e.g. 'sylion.governance') or None if the file
    is not inside any known package boundary.
    """
    # Normalize path separators
    rel_path = os.path.relpath(file_path, root_dir).replace(os.sep, "/")

    # rel_path is like "governance/decision_ladder.py" when root_dir is "sylion/"
    # We need to match "governance" against "sylion.governance" -> extract sub-package part
    for pkg in sorted(ALL_PACKAGES, key=len, reverse=True):
        # pkg = "sylion.governance" -> sub = "governance"
        sub = pkg[len(SYLION_PREFIX):]  # strip "sylion." prefix
        if rel_path.startswith(sub + "/") or rel_path.startswith(sub + "\\"):
            return pkg

    return None


def extract_sylion_package(import_module: str) -> Optional[str]:
    """Extract the sylion sub-package from an import string.

    'sylion.governance.decision_ladder' -> 'sylion.governance'
    'sylion.core.event_bus' -> 'sylion.core'
    'os.path' -> None
    """
    if not import_module.startswith(SYLION_PREFIX):
        return None

    parts = import_module.split(".")
    if len(parts) < 2:
        return None

    # sylion.<package>.<module> -> sylion.<package>
    candidate = f"{parts[0]}.{parts[1]}"
    if candidate in ALL_PACKAGES:
        return candidate

    # Handle edge case: direct import of sylion itself
    if import_module == "sylion":
        return None

    return None


def is_stdlib_or_third_party(import_module: str) -> bool:
    """Check if an import is stdlib or third-party (not a sylion internal)."""
    return not import_module.startswith(SYLION_PREFIX)


def check_import(
    source_package: str,
    target_package: str,
    import_module: str,
) -> Optional[str]:
    """Check if importing target_package from source_package is allowed.

    Returns None if allowed, or a human-readable rule description if forbidden.
    """
    # Same-package import: always allowed
    if source_package == target_package:
        return None

    # Core kernel: all packages may import from it
    if target_package in ALLOWED_IMPORT_TARGET_FOR_ALL:
        return None

    # API facade: may import from any package
    if source_package in FACADE_PACKAGES:
        return None

    # If we got here, it's a cross-package import between non-core packages
    return (
        f"Cross-package import forbidden: {source_package} -> {target_package}. "
        f"Use EventBus or Contract Registry for cross-package communication."
    )


# ---------------------------------------------------------------------------
# AST-based import extraction
# ---------------------------------------------------------------------------

def extract_imports_from_file(file_path: str) -> list[tuple[int, str, str]]:
    """Parse a Python file and extract all import statements.

    Returns list of (line_number, import_module, raw_statement) tuples.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"  WARNING: Could not read {file_path}: {e}", file=sys.stderr)
        return []

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as e:
        print(f"  WARNING: Syntax error in {file_path}: {e}", file=sys.stderr)
        return []

    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                raw = f"import {alias.name}"
                imports.append((node.lineno, alias.name, raw))

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                raw = f"from {node.module} import ..."
                imports.append((node.lineno, node.module, raw))
                # Also check individual names (e.g. from sylion.governance import decision_ladder)
                for alias in node.names:
                    full_module = f"{node.module}.{alias.name}"
                    imports.append((node.lineno, full_module, f"from {node.module} import {alias.name}"))

    return imports


# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------

def scan_directory(root_dir: str, exclude_patterns: list[str] | None = None) -> ScanResult:
    """Scan all .py files under root_dir for import violations."""
    result = ScanResult()
    exclude_patterns = exclude_patterns or [
        "/test",
        "/tests/",
        "/__pycache__/",
        "conftest.py",
        "test_",
    ]

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip excluded directories
        rel_dir = os.path.relpath(dirpath, root_dir).replace(os.sep, "/")

        skip = False
        for pattern in exclude_patterns:
            if pattern in rel_dir:
                skip = True
                break
        if skip:
            continue

        # Filter out __pycache__
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]

        for filename in filenames:
            if not filename.endswith(".py"):
                continue

            file_path = os.path.join(dirpath, filename)
            rel_file = os.path.relpath(file_path, root_dir).replace(os.sep, "/")

            # Skip test files
            skip_file = False
            for pattern in exclude_patterns:
                if pattern in filename:
                    skip_file = True
                    break
            if skip_file:
                result.skipped_files.append(rel_file)
                continue

            result.total_files += 1

            # Determine which package this file belongs to
            source_package = determine_package(file_path, root_dir)
            if source_package is None:
                # File is at the sylion/ root level (e.g. __init__.py) — skip
                continue

            # Extract and check imports
            file_imports = extract_imports_from_file(file_path)
            for line_no, import_module, raw_stmt in file_imports:
                # Only check sylion internal imports
                if is_stdlib_or_third_party(import_module):
                    continue

                result.total_imports += 1

                target_package = extract_sylion_package(import_module)
                if target_package is None:
                    # Could not determine target package — skip
                    continue

                violation_msg = check_import(source_package, target_package, import_module)
                if violation_msg is not None:
                    result.violations.append(ImportViolation(
                        file_path=rel_file,
                        line_number=line_no,
                        import_statement=raw_stmt,
                        source_package=source_package,
                        target_package=target_package,
                        rule_description=violation_msg,
                    ))

    return result


def format_violations(violations: list[ImportViolation]) -> str:
    """Format violations for console output."""
    lines = []
    lines.append("=" * 80)
    lines.append("SYLION AEIS — Import Dependency Violations")
    lines.append("=" * 80)
    lines.append("")

    if not violations:
        lines.append("No violations found. All imports comply with R2.5 dependency rules.")
        return "\n".join(lines)

    lines.append(f"Found {len(violations)} violation(s):")
    lines.append("")

    # Group by source package
    by_source: dict[str, list[ImportViolation]] = {}
    for v in violations:
        by_source.setdefault(v.source_package, []).append(v)

    for source_pkg in sorted(by_source.keys()):
        pkg_violations = by_source[source_pkg]
        lines.append(f"--- {source_pkg} ({len(pkg_violations)} violations) ---")

        for v in sorted(pkg_violations, key=lambda x: (x.file_path, x.line_number)):
            lines.append(
                f"  {v.file_path}:{v.line_number}"
                f"  [{v.source_package} -> {v.target_package}]"
                f"  {v.import_statement}"
            )

        lines.append("")

    # Summary
    lines.append("-" * 80)
    lines.append("SUMMARY BY SOURCE -> TARGET:")
    cross_counts: dict[str, int] = {}
    for v in violations:
        key = f"{v.source_package} -> {v.target_package}"
        cross_counts[key] = cross_counts.get(key, 0) + 1

    for edge, count in sorted(cross_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {edge}: {count} import(s)")

    lines.append("")
    lines.append("REMEDIATION: Replace direct imports with EventBus events or")
    lines.append("Contract Registry lookups. See Ksiega R2.5 for patterns.")
    lines.append("=" * 80)

    return "\n".join(lines)


def main() -> int:
    """Main entry point. Returns 0 if no violations, 1 if violations found."""
    # Determine project root (parent of scripts/)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    # Default scan directory
    sylion_dir = project_root / "sylion"

    # Allow override via command-line argument
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("--help", "-h"):
            print(__doc__)
            return 0
        sylion_dir = Path(arg).resolve()

    if not sylion_dir.is_dir():
        print(f"ERROR: Directory not found: {sylion_dir}", file=sys.stderr)
        return 2

    print(f"Scanning: {sylion_dir}")
    print(f"Known packages: {len(ALL_PACKAGES)}")
    print()

    result = scan_directory(str(sylion_dir))

    print(f"Files scanned: {result.total_files}")
    print(f"Sylion imports checked: {result.total_imports}")
    print(f"Files skipped (tests/etc): {len(result.skipped_files)}")
    print()

    output = format_violations(result.violations)
    print(output)

    if result.violations:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
