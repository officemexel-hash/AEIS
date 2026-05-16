#!/usr/bin/env python3
"""AEIS Polish localization audit helper.

The scanner is intentionally conservative: it flags user-facing candidates
that still contain common English UI words while allowing product names,
protocol names, and technical identifiers documented in the AEIS i18n policy.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_ROOTS = [
    "src/sylion-frontend/src/app",
    "src/sylion-frontend/src/components",
    "src/sylion-pipeline/sylion/api/execution_start_routes.py",
]

SUSPICIOUS_TERMS = [
    "Refresh",
    "Run acceptance",
    "Project creation",
    "Project Inception",
    "Goal Definition",
    "Scope Definition",
    "Council Configuration",
    "Pending Questions",
    "Running Cost",
    "Timeline",
    "Cost Ledger",
    "No blocking",
    "No audit",
    "No cost",
    "Backend not reachable",
    "Backend offline",
    "Long-horizon",
    "Vault",
    "Sync",
    "Synced",
    "Evidence",
    "Backlink",
    "Final Report",
    "Local release package generated",
    "Project delivered and closed",
    "Customer-facing",
    "Production handed",
    "Customer fully trained",
    "Workspace archived",
    "Skills promotion",
    "Cost reconciliation",
    "Closure email",
    "30-day warranty",
    "Closed project",
    "Create the first",
    "No acceptance snapshot",
    "Approve readiness",
    "Diagnose edge case",
]

TECHNICAL_ALLOWLIST = [
    "AEIS",
    "SYLION",
    "API",
    "Obsidian",
    "Markdown",
    "Human Gate",
    "Source of Truth",
    "Masterplan",
    "LLM",
    "CRM",
    "KSeF",
    "VPS",
    "SDR",
    "SLA",
    "UI",
    "UX",
    "JSON",
    "YAML",
    "SQL",
    "HTTP",
    "OpenAPI",
    "Docker",
    "GitHub",
    "KeyVault",
    "Ollama",
    "LocalAI",
    "OpenAI",
    "Claude",
    "GLM",
]

USER_FACING_HINT_RE = re.compile(
    r"(>\s*[^<]*<|label=|placeholder=|aria-label=|title=|HelpTip|setStatus|<option|_check\(|subject|text=)",
    re.IGNORECASE,
)
COMMENT_OR_CODE_RE = re.compile(
    r"^\s*(//|/\*|\*|import\b|type\b|interface\b|export type\b|className=|data-testid=)",
)
MOJIBAKE_RE = re.compile(r"[ÃÂ]|Ä[^\w]|Ĺ|Ă")


def iter_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        return []
    return [
        path
        for path in root.rglob("*")
        if path.suffix in {".ts", ".tsx", ".py"} and "node_modules" not in path.parts
    ]


def find_terms(line: str) -> list[str]:
    hits: list[str] = []
    for term in SUSPICIOUS_TERMS:
        pattern = r"(?<![A-Za-z0-9_])" + re.escape(term) + r"(?![A-Za-z0-9_])"
        if re.search(pattern, line):
            hits.append(term)
    return hits


def is_technical_allowed(line: str) -> bool:
    stripped = line.strip()
    if COMMENT_OR_CODE_RE.search(stripped):
        return True
    if "data-testid" in stripped or "lucide-react" in stripped:
        return True
    found = find_terms(line)
    if found:
        return False
    return any(token in stripped for token in TECHNICAL_ALLOWLIST)


def scan_file(path: Path, repo: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    for number, line in enumerate(lines, start=1):
        terms = find_terms(line)
        mojibake = bool(MOJIBAKE_RE.search(line))
        if not terms and not mojibake:
            continue
        if is_technical_allowed(line) and not mojibake:
            continue
        findings.append(
            {
                "path": str(path.relative_to(repo)).replace("\\", "/"),
                "line": number,
                "terms": terms,
                "mojibake": mojibake,
                "user_facing_candidate": bool(USER_FACING_HINT_RE.search(line)),
                "text": line.strip()[:260],
            }
        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan AEIS sources for English UI/localization remnants.")
    parser.add_argument("--repo", default=".", help="Repository root")
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument("roots", nargs="*", default=DEFAULT_ROOTS, help="Files or directories to scan")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    files: list[Path] = []
    for item in args.roots:
        files.extend(iter_files((repo / item).resolve()))

    findings: list[dict[str, object]] = []
    for path in sorted(set(files)):
        findings.extend(scan_file(path, repo))

    result = {
        "task": "AEIS P2-008 Polish localization static audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo),
        "roots": args.roots,
        "allowlist": TECHNICAL_ALLOWLIST,
        "scanned_files": len(set(files)),
        "total_findings": len(findings),
        "user_facing_candidates": sum(1 for item in findings if item["user_facing_candidate"]),
        "findings": findings,
    }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        out = (repo / args.output).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
