"""No-mock/no-stub source scanner used by Test Center.

The scanner is intentionally narrow: it looks for production UI/API code
that silently substitutes fake data. Canonical demo labs and generated OSDK
types are allowed to mention demo/mock concepts, but they cannot masquerade
as live runtime data.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class NoMockRule:
    rule_id: str
    severity: str
    description: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class NoMockIssue:
    rule_id: str
    severity: str
    path: str
    line: int
    snippet: str
    description: str
    blocking: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class NoMockScanResult:
    status: str
    scanned_files: int
    issue_count: int
    blocking_count: int
    issues: list[NoMockIssue]
    rules: list[dict[str, str]]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["issues"] = [issue.to_dict() for issue in self.issues]
        return data


RULES: tuple[NoMockRule, ...] = (
    NoMockRule(
        "demo_fallback",
        "P2",
        "Kod produkcyjny nie moze spadac do demo fallback.",
        re.compile(r"\b(?:fallback\s+demo|demo\s+fallback|falls?\s+back\s+to\s+demo|fall\s+back\s+to\s+demo)\b", re.I),
    ),
    NoMockRule(
        "mock_banner",
        "P2",
        "MockBanner w powierzchni operatora oznacza nieuczciwy stan danych.",
        re.compile(r"\bMockBanner\b"),
    ),
    NoMockRule(
        "shell_only_surface",
        "P2",
        "Shell-only/view-only bez backendu nie moze udawac gotowej funkcji.",
        re.compile(r"\b(?:shell[- ]only|view[- ]only)\b", re.I),
    ),
    NoMockRule(
        "empty_promise_api",
        "P3",
        "Klient API nie moze udawac sukcesu pustym Promise.resolve({ ...: [] }).",
        re.compile(
            r"Promise\.resolve\(\s*\{\s*(?:models|recommendations|items|data|rows)\s*:\s*\[\s*\]\s*\}\s*\)",
            re.I,
        ),
    ),
    NoMockRule(
        "mock_named_function",
        "P3",
        "Funkcja mock* w runtime UI/API wymaga realnego endpointu albo jawnego test fixture.",
        re.compile(r"\bfunction\s+mock[A-Z]\w*\s*\("),
    ),
)

DEFAULT_TARGETS: tuple[str, ...] = (
    "src/sylion-frontend/src/app/(app)",
    "src/sylion-frontend/src/components",
    "src/sylion-frontend/src/lib",
    "src/sylion-pipeline/sylion/api",
)

SCAN_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx"}
BLOCKING_SEVERITIES = {"P0", "P1", "P2", "P3"}
EXCLUDED_PARTS = {
    ".next",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    "test-results",
}
ALLOWED_PATH_MARKERS = (
    "/src/sylion-frontend/src/app/(app)/demo/",
    "/src/sylion-frontend/src/app/(app)/test-center/page.tsx",
    "/src/sylion-frontend/src/app/(app)/test-center/no-mock-scan/",
    "/src/sylion-frontend/src/lib/osdk-ts/",
    "/src/sylion-pipeline/sylion/api/demo_",
)


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[5]


def _normalize_rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _iter_files(root: Path, targets: Iterable[str]) -> Iterable[Path]:
    for target in targets:
        base = root / target
        if not base.exists():
            continue
        if base.is_file():
            if base.suffix in SCAN_SUFFIXES:
                yield base
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
                continue
            parts = set(path.parts)
            if parts & EXCLUDED_PARTS:
                continue
            yield path


def _is_allowed_path(rel_path: str) -> bool:
    wrapped = f"/{rel_path}"
    return any(marker in wrapped for marker in ALLOWED_PATH_MARKERS)


def _line_issues(rel_path: str, line_no: int, line: str) -> list[NoMockIssue]:
    stripped = line.strip()
    if stripped.startswith(("//", "#", "*")):
        return []
    allowed = _is_allowed_path(rel_path)
    issues: list[NoMockIssue] = []
    for rule in RULES:
        if not rule.pattern.search(line):
            continue
        blocking = (not allowed) and rule.severity in BLOCKING_SEVERITIES
        issues.append(
            NoMockIssue(
                rule_id=rule.rule_id,
                severity=rule.severity if blocking else "P4",
                path=rel_path,
                line=line_no,
                snippet=line.strip()[:240],
                description=rule.description,
                blocking=blocking,
            )
        )
    return issues


def run_no_mock_scan(
    root: Path | None = None,
    targets: Iterable[str] = DEFAULT_TARGETS,
    limit: int = 500,
) -> NoMockScanResult:
    base = (root or repo_root_from_here()).resolve()
    issues: list[NoMockIssue] = []
    scanned = 0
    for path in _iter_files(base, targets):
        scanned += 1
        rel = _normalize_rel(path, base)
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, start=1):
            issues.extend(_line_issues(rel, line_no, line))
            if len(issues) >= limit:
                break
        if len(issues) >= limit:
            break
    blocking = [issue for issue in issues if issue.blocking]
    return NoMockScanResult(
        status="PASS" if not blocking else "FAIL",
        scanned_files=scanned,
        issue_count=len(issues),
        blocking_count=len(blocking),
        issues=issues,
        rules=[
            {
                "rule_id": rule.rule_id,
                "severity": rule.severity,
                "description": rule.description,
            }
            for rule in RULES
        ],
    )


__all__ = ["NoMockIssue", "NoMockScanResult", "run_no_mock_scan"]
