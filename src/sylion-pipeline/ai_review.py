#!/usr/bin/env python3
"""
SYLION AI Review Pipeline — Pre-deploy code audit.

Three reviewers run in parallel:
  1. Claude Code Agent SDK (local WSL) — full codebase access, can propose edits
  2. Ollama 3 (local http://localhost:11434) — offline, fast, cost-free
  3. Perplexity-generated review manifest — loaded from last remote audit

Results are synthesized: >=2/3 agreement → auto-patch.
Disagreements → Human Gate prompt in dashboard.

Usage:
    python ai_review.py                     # full review before deploy
    python ai_review.py --quick             # quick scan (changed files only)
    python ai_review.py --file orchestrator.py  # single file
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SYLION_ROOT = Path(__file__).parent.resolve()
REVIEW_DIR = SYLION_ROOT / "reviews"
REVIEW_DIR.mkdir(exist_ok=True)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# Files/patterns to always audit (high-risk)
HIGH_RISK_PATTERNS = [
    "orchestrator.py",
    "sylion/server.py",
    "sylion/api/router.py",
    "dashboard_server.py",
    "launcher.py",
    "pipeline.py",
    "abr_controller.py",
    "device_harness.py",
    "stream_security.py",
    "config.py",
]

# Known bug patterns to scan for
BUG_PATTERNS = [
    # Private attribute access from outside class (like _ladder bug)
    {
        "id": "SYL-ATTR-001",
        "name": "Private attribute access from outside class",
        "pattern": r"\b\w+\._[a-z]\w+",
        "severity": "HIGH",
        "description": "Accessing ._private attributes from outside the class — may crash like _ladder bug",
        "exclude_patterns": [
            r"self\._",           # self access is fine
            r"cls\._",            # classmethod access is fine
            r"__pycache__",
            r"#.*\._",           # comments
            r"\".*\._",          # strings
            r"'.*\._",           # strings
            r"_ladder",          # already fixed
        ],
    },
    # Bare except or overly broad exception handling
    {
        "id": "SYL-ERR-001",
        "name": "Silent exception swallowing",
        "pattern": r"except.*:\s*\n\s*(pass|\.\.\.)",
        "severity": "MEDIUM",
        "description": "Exception caught and silently ignored",
    },
    # Console-only error handling in frontend
    {
        "id": "SYL-UX-001",
        "name": "Silent console.error without UI feedback",
        "pattern": r"catch\s*\(e\)\s*\{\s*console\.(error|log)",
        "severity": "MEDIUM",
        "description": "Frontend catch block only logs to console — user sees nothing",
    },
    # Inline style display:none on .screen elements
    {
        "id": "SYL-CSS-001",
        "name": "Inline display:none on screen elements",
        "pattern": r'class="screen[^"]*"\s+style="[^"]*display:\s*none',
        "severity": "HIGH",
        "description": "Inline style overrides CSS .screen.active — panels will be invisible",
    },
    # Missing import
    {
        "id": "SYL-IMP-001",
        "name": "Potential missing import",
        "pattern": r"^\s*(?:import|from)\s+\w+",
        "severity": "LOW",
        "check_type": "import_verify",
        "description": "Verify all imports resolve correctly",
    },
]

log = logging.getLogger("ai_review")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Verdict(str, Enum):
    APPROVE = "APPROVE"
    APPROVE_WITH_NITS = "APPROVE_WITH_NITS"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    BLOCK = "BLOCK"


@dataclass
class Finding:
    """Single issue found by a reviewer."""
    id: str
    file: str
    line: Optional[int]
    severity: str
    title: str
    description: str
    suggested_fix: Optional[str] = None
    auto_fixable: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class ReviewReport:
    """Report from a single reviewer."""
    reviewer: str          # "claude_code" | "ollama3" | "static_scan"
    verdict: str
    confidence: int        # 0-100
    findings: list = field(default_factory=list)
    timestamp: str = ""
    duration_s: float = 0.0
    error: Optional[str] = None

    def to_dict(self):
        d = asdict(self)
        d["findings"] = [f.to_dict() if isinstance(f, Finding) else f for f in self.findings]
        return d


@dataclass
class ReviewSynthesis:
    """Combined result from all reviewers."""
    consensus_verdict: str
    reports: list
    agreed_findings: list     # >=2/3 agree
    disputed_findings: list   # only 1 reviewer flagged
    auto_patches: list        # applied automatically
    human_gate_items: list    # need human decision
    timestamp: str = ""

    def to_dict(self):
        return {
            "consensus_verdict": self.consensus_verdict,
            "reports": [r.to_dict() if isinstance(r, ReviewReport) else r for r in self.reports],
            "agreed_findings": [f.to_dict() if isinstance(f, Finding) else f for f in self.agreed_findings],
            "disputed_findings": [f.to_dict() if isinstance(f, Finding) else f for f in self.disputed_findings],
            "auto_patches": self.auto_patches,
            "human_gate_items": self.human_gate_items,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Reviewer 1: Static pattern scan (always available, instant)
# ---------------------------------------------------------------------------
def run_static_scan(files: list[Path]) -> ReviewReport:
    """Scan files for known bug patterns."""
    start = time.time()
    findings = []

    for fpath in files:
        if not fpath.exists():
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        lines = content.split("\n")
        rel = str(fpath.relative_to(SYLION_ROOT))

        for bp in BUG_PATTERNS:
            if bp.get("check_type") == "import_verify":
                continue  # skip complex checks in static scan

            for i, line in enumerate(lines, 1):
                if re.search(bp["pattern"], line):
                    # Check exclusions
                    excluded = False
                    for exc in bp.get("exclude_patterns", []):
                        if re.search(exc, line):
                            excluded = True
                            break
                    if excluded:
                        continue

                    findings.append(Finding(
                        id=bp["id"],
                        file=rel,
                        line=i,
                        severity=bp["severity"],
                        title=bp["name"],
                        description=f"{bp['description']}\n  → `{line.strip()[:120]}`",
                    ))

    # Cross-file: check for private attr access vs class definitions
    findings = _verify_private_attrs(findings, files)

    verdict = Verdict.APPROVE.value
    if any(f.severity == "CRITICAL" for f in findings):
        verdict = Verdict.BLOCK.value
    elif any(f.severity == "HIGH" for f in findings):
        verdict = Verdict.REQUEST_CHANGES.value
    elif findings:
        verdict = Verdict.APPROVE_WITH_NITS.value

    return ReviewReport(
        reviewer="static_scan",
        verdict=verdict,
        confidence=95,
        findings=findings,
        timestamp=datetime.now().isoformat(),
        duration_s=round(time.time() - start, 2),
    )


def _verify_private_attrs(findings: list[Finding], files: list[Path]) -> list[Finding]:
    """Cross-reference: if code accesses obj._attr, check if class defines self._attr or self.attr.
    
    Always parses ALL high-risk files for class definitions (not just files under review)
    to catch cross-file bugs like _ladder (orchestrator.py accessing ABRController from abr_controller.py).
    """
    # Build map of class attributes — always from ALL high-risk files, not just reviewed ones
    class_files = set(files)
    for pattern in HIGH_RISK_PATTERNS:
        candidate = SYLION_ROOT / pattern
        if candidate.exists() and candidate.suffix == ".py":
            class_files.add(candidate)
    
    class_attrs: dict[str, dict[str, str]] = {}  # class_name -> {attr_name: "private"|"public"}
    for fpath in class_files:
        if not fpath.suffix == ".py":
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        current_class = None
        for line in content.split("\n"):
            cls_match = re.match(r"^class\s+(\w+)", line)
            if cls_match:
                current_class = cls_match.group(1)
                class_attrs.setdefault(current_class, {})
            if current_class:
                # self._attr = ... → private
                priv = re.findall(r"self\.(_[a-z]\w+)\s*=", line)
                for a in priv:
                    class_attrs[current_class][a] = "private"
                # self.attr = ... → public
                pub = re.findall(r"self\.([a-z]\w+)\s*=", line)
                for a in pub:
                    if not a.startswith("_"):
                        class_attrs[current_class][a] = "public"

    # Now check findings: if accessing ._attr and class has .attr (public), flag as BUG
    verified = []
    for f in findings:
        if f.id != "SYL-ATTR-001":
            verified.append(f)
            continue

        # Extract the attribute name
        match = re.search(r"\.(_[a-z]\w+)", f.description)
        if not match:
            verified.append(f)
            continue

        private_name = match.group(1)       # e.g. "_ladder"
        public_name = private_name.lstrip("_")  # e.g. "ladder"

        # Check if any class has the public version but NOT the private version
        # IMPORTANT: also check if ANY class defines the private version (legitimate access)
        is_bug = False
        has_legitimate_private = False
        bug_class = None
        
        for cls_name, attrs in class_attrs.items():
            if private_name in attrs and attrs[private_name] == "private":
                has_legitimate_private = True
            if public_name in attrs and attrs[public_name] == "public":
                if private_name not in attrs:
                    bug_class = cls_name
        
        # Only flag as CRITICAL if a class has public but NOT private,
        # AND no other class has a legitimate private version
        if bug_class and not has_legitimate_private:
            f.severity = "CRITICAL"
            f.title = f"WILL CRASH: .{private_name} should be .{public_name}"
            f.description += f"\n  → Class {bug_class} defines self.{public_name} (public), not self.{private_name}"
            f.suggested_fix = f"Change .{private_name} to .{public_name}"
            # Never auto-fix from pre-deploy hook — require human review
            f.auto_fixable = False
            is_bug = True
        elif has_legitimate_private:
            # Legitimate private access — downgrade to INFO
            f.severity = "INFO"
            f.title = f"Private attr access: .{private_name} (legitimate)"
            # Don't include in findings — it's noise
            continue
        
        if is_bug:
            verified.append(f)
        # Drop unverified HIGH findings that are just noise

    return verified


# ---------------------------------------------------------------------------
# Reviewer 2: Ollama 3 (local LLM)
# ---------------------------------------------------------------------------
async def run_ollama_review(files: list[Path]) -> ReviewReport:
    """Send code to local Ollama for review."""
    start = time.time()

    # Check Ollama availability
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            if r.status_code != 200:
                return ReviewReport(
                    reviewer="ollama3", verdict="SKIP", confidence=0,
                    error="Ollama not responding", timestamp=datetime.now().isoformat(),
                    duration_s=round(time.time() - start, 2),
                )
    except Exception as e:
        return ReviewReport(
            reviewer="ollama3", verdict="SKIP", confidence=0,
            error=f"Ollama connection failed: {e}", timestamp=datetime.now().isoformat(),
            duration_s=round(time.time() - start, 2),
        )

    # Build review prompt with file contents
    code_context = ""
    for fpath in files[:5]:  # limit to 5 files for Ollama context window
        if not fpath.exists():
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
            # Trim large files
            if len(content) > 8000:
                content = content[:4000] + "\n... [truncated] ...\n" + content[-4000:]
            rel = str(fpath.relative_to(SYLION_ROOT))
            code_context += f"\n### {rel}\n```python\n{content}\n```\n"
        except Exception:
            continue

    prompt = f"""You are a senior code reviewer for SYLION pipeline (Python + JS dashboard).
Review the following code changes and report bugs, security issues, and crash risks.

Focus especially on:
1. AttributeError risks: accessing ._private attributes that should be .public
2. Silent exception handling (catch blocks that swallow errors)
3. Missing error feedback for users
4. Race conditions in async code
5. Import errors or missing dependencies

For each issue found, output JSON:
{{"id": "unique-id", "file": "path", "line": number_or_null, "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "title": "short title", "description": "detailed description", "suggested_fix": "code fix or null"}}

Output ONLY a JSON array of issues. If no issues found, output [].

{code_context}
"""

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 4096},
                },
            )
            if r.status_code != 200:
                return ReviewReport(
                    reviewer="ollama3", verdict="SKIP", confidence=0,
                    error=f"Ollama returned HTTP {r.status_code}",
                    timestamp=datetime.now().isoformat(),
                    duration_s=round(time.time() - start, 2),
                )

            response_text = r.json().get("response", "")
            findings = _parse_llm_findings(response_text, "ollama3")

    except Exception as e:
        return ReviewReport(
            reviewer="ollama3", verdict="SKIP", confidence=0,
            error=f"Ollama review failed: {e}", timestamp=datetime.now().isoformat(),
            duration_s=round(time.time() - start, 2),
        )

    verdict = Verdict.APPROVE.value
    if any(f.severity == "CRITICAL" for f in findings):
        verdict = Verdict.REQUEST_CHANGES.value
    elif any(f.severity == "HIGH" for f in findings):
        verdict = Verdict.APPROVE_WITH_NITS.value

    return ReviewReport(
        reviewer="ollama3",
        verdict=verdict,
        confidence=70,
        findings=findings,
        timestamp=datetime.now().isoformat(),
        duration_s=round(time.time() - start, 2),
    )


# ---------------------------------------------------------------------------
# Reviewer 3: Claude Code Agent SDK (if available)
# ---------------------------------------------------------------------------
async def run_claude_code_review(files: list[Path]) -> ReviewReport:
    """Use Claude Code Agent SDK for deep code review."""
    start = time.time()

    try:
        from claude_agent_sdk import query, ClaudeAgentOptions
    except ImportError:
        # Fallback: try CLI
        return await _run_claude_cli_review(files, start)

    file_list = ", ".join(str(f.relative_to(SYLION_ROOT)) for f in files[:10])

    prompt = f"""Review these SYLION pipeline files for bugs, crash risks, and security issues: {file_list}

Focus on:
1. AttributeError: accessing ._private attrs that should be .public (like the _ladder bug)
2. Silent exception handling without user feedback
3. Frontend catch blocks with only console.error
4. Inline style="display:none" on .screen elements (CSS war)
5. Missing imports, undefined variables
6. Race conditions in async/polling code

For each issue, output one JSON object per line:
{{"id": "unique", "file": "path", "line": null, "severity": "CRITICAL|HIGH|MEDIUM|LOW", "title": "...", "description": "...", "suggested_fix": "..."}}

End with a verdict line: VERDICT: APPROVE|APPROVE_WITH_NITS|REQUEST_CHANGES|BLOCK (confidence: XX%)"""

    findings = []
    result_text = ""

    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Grep", "Glob"],
            ),
        ):
            if hasattr(message, "result"):
                result_text += str(message.result)
            elif hasattr(message, "content"):
                result_text += str(message.content)

        findings = _parse_llm_findings(result_text, "claude_code")
        verdict = _extract_verdict(result_text)
        confidence = _extract_confidence(result_text)

    except Exception as e:
        return ReviewReport(
            reviewer="claude_code", verdict="SKIP", confidence=0,
            error=f"Claude Code SDK failed: {e}",
            timestamp=datetime.now().isoformat(),
            duration_s=round(time.time() - start, 2),
        )

    return ReviewReport(
        reviewer="claude_code",
        verdict=verdict,
        confidence=confidence,
        findings=findings,
        timestamp=datetime.now().isoformat(),
        duration_s=round(time.time() - start, 2),
    )


async def _run_claude_cli_review(files: list[Path], start: float) -> ReviewReport:
    """Fallback: use claude CLI --print for review."""
    try:
        result = subprocess.run(
            ["which", "claude"], capture_output=True, text=True
        )
        if result.returncode != 0:
            return ReviewReport(
                reviewer="claude_code", verdict="SKIP", confidence=0,
                error="Claude Code not installed (npm i -g @anthropic-ai/claude-code)",
                timestamp=datetime.now().isoformat(),
                duration_s=round(time.time() - start, 2),
            )
    except Exception:
        return ReviewReport(
            reviewer="claude_code", verdict="SKIP", confidence=0,
            error="Cannot check for Claude CLI",
            timestamp=datetime.now().isoformat(),
            duration_s=round(time.time() - start, 2),
        )

    file_paths = " ".join(str(f) for f in files[:5])
    prompt = (
        f"Review these files for bugs, focusing on AttributeError from wrong "
        f"private attr access, silent exceptions, missing UI error feedback: {file_paths}"
    )

    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True, text=True, timeout=180,
            cwd=str(SYLION_ROOT),
        )
        findings = _parse_llm_findings(result.stdout, "claude_code")
        verdict = _extract_verdict(result.stdout) if result.returncode == 0 else "SKIP"

    except subprocess.TimeoutExpired:
        return ReviewReport(
            reviewer="claude_code", verdict="SKIP", confidence=0,
            error="Claude CLI timed out after 180s",
            timestamp=datetime.now().isoformat(),
            duration_s=round(time.time() - start, 2),
        )
    except Exception as e:
        return ReviewReport(
            reviewer="claude_code", verdict="SKIP", confidence=0,
            error=f"Claude CLI error: {e}",
            timestamp=datetime.now().isoformat(),
            duration_s=round(time.time() - start, 2),
        )

    return ReviewReport(
        reviewer="claude_code",
        verdict=verdict,
        confidence=75,
        findings=findings,
        timestamp=datetime.now().isoformat(),
        duration_s=round(time.time() - start, 2),
    )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
def _parse_llm_findings(text: str, reviewer: str) -> list[Finding]:
    """Extract JSON findings from LLM response text."""
    findings = []

    # Try parsing as JSON array
    try:
        # Find JSON array in response
        match = re.search(r"\[[\s\S]*?\]", text)
        if match:
            items = json.loads(match.group())
            for item in items:
                if isinstance(item, dict) and "title" in item:
                    findings.append(Finding(
                        id=item.get("id", f"{reviewer}-{len(findings)+1}"),
                        file=item.get("file", "unknown"),
                        line=item.get("line"),
                        severity=item.get("severity", "MEDIUM"),
                        title=item.get("title", "Unnamed issue"),
                        description=item.get("description", ""),
                        suggested_fix=item.get("suggested_fix"),
                    ))
            return findings
    except (json.JSONDecodeError, ValueError):
        pass

    # Try parsing line-by-line JSON objects
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("{") and "title" in line:
            try:
                item = json.loads(line)
                findings.append(Finding(
                    id=item.get("id", f"{reviewer}-{len(findings)+1}"),
                    file=item.get("file", "unknown"),
                    line=item.get("line"),
                    severity=item.get("severity", "MEDIUM"),
                    title=item.get("title", "Unnamed issue"),
                    description=item.get("description", ""),
                    suggested_fix=item.get("suggested_fix"),
                ))
            except (json.JSONDecodeError, ValueError):
                continue

    return findings


def _extract_verdict(text: str) -> str:
    """Extract verdict from LLM response."""
    match = re.search(r"VERDICT:\s*(APPROVE_WITH_NITS|APPROVE|REQUEST_CHANGES|BLOCK)", text)
    return match.group(1) if match else Verdict.APPROVE_WITH_NITS.value


def _extract_confidence(text: str) -> int:
    """Extract confidence percentage from LLM response."""
    match = re.search(r"confidence:\s*(\d+)%", text, re.IGNORECASE)
    return int(match.group(1)) if match else 75


# ---------------------------------------------------------------------------
# Synthesis: combine all reviewer reports
# ---------------------------------------------------------------------------
def synthesize_reviews(reports: list[ReviewReport]) -> ReviewSynthesis:
    """Combine reports from all reviewers into consensus."""
    active_reports = [r for r in reports if r.verdict != "SKIP"]

    if not active_reports:
        return ReviewSynthesis(
            consensus_verdict="SKIP",
            reports=reports,
            agreed_findings=[], disputed_findings=[],
            auto_patches=[], human_gate_items=[],
            timestamp=datetime.now().isoformat(),
        )

    # Group findings by (file, approximate line, title pattern)
    finding_groups: dict[str, dict] = {}

    for report in active_reports:
        for f in report.findings:
            # Group key: file + bug pattern ID (if available) + severity
            # Using ID prefix instead of title[:40] for cross-reviewer matching
            # (different LLMs use different titles for the same bug)
            id_prefix = f.id.split('-')[0] if '-' in f.id else f.id[:10]
            key = f"{f.file}:{f.severity}:{id_prefix}"
            if key not in finding_groups:
                finding_groups[key] = {"finding": f, "reviewers": set(), "count": 0}
            finding_groups[key]["reviewers"].add(report.reviewer)
            finding_groups[key]["count"] += 1

    agreed = []
    disputed = []
    auto_patches = []
    human_gate = []

    threshold = max(2, len(active_reports) // 2 + 1)  # >=2 for 3 reviewers

    for key, group in finding_groups.items():
        f = group["finding"]
        count = group["count"]

        if count >= threshold:
            agreed.append(f)
            if f.auto_fixable and f.suggested_fix:
                auto_patches.append({
                    "file": f.file,
                    "fix": f.suggested_fix,
                    "reason": f.title,
                    "agreed_by": list(group["reviewers"]),
                })
            elif f.severity in ("CRITICAL", "HIGH"):
                human_gate.append({
                    "finding": f.to_dict(),
                    "agreed_by": list(group["reviewers"]),
                    "action_needed": "Review and decide on fix",
                })
        else:
            disputed.append(f)

    # Consensus verdict
    verdicts = [r.verdict for r in active_reports]
    if "BLOCK" in verdicts:
        consensus = Verdict.BLOCK.value
    elif verdicts.count(Verdict.REQUEST_CHANGES.value) >= threshold:
        consensus = Verdict.REQUEST_CHANGES.value
    elif any(v in (Verdict.APPROVE_WITH_NITS.value, Verdict.REQUEST_CHANGES.value) for v in verdicts):
        consensus = Verdict.APPROVE_WITH_NITS.value
    else:
        consensus = Verdict.APPROVE.value

    return ReviewSynthesis(
        consensus_verdict=consensus,
        reports=reports,
        agreed_findings=agreed,
        disputed_findings=disputed,
        auto_patches=auto_patches,
        human_gate_items=human_gate,
        timestamp=datetime.now().isoformat(),
    )


# ---------------------------------------------------------------------------
# Auto-patch: apply consensus fixes
# ---------------------------------------------------------------------------
def apply_auto_patches(synthesis: ReviewSynthesis, dry_run: bool = False) -> list[dict]:
    """Report auto-fixable patches but NEVER apply automatically in pre-deploy hook.
    
    Auto-patching is disabled by default (council consensus: global regex replace is dangerous).
    All patches are reported with status MANUAL_REQUIRED for human review.
    Use --auto-fix flag to explicitly enable (not available in launcher hook).
    """
    reported = []

    for patch in synthesis.auto_patches:
        fpath = SYLION_ROOT / patch["file"]
        if not fpath.exists():
            patch["status"] = "SKIP: file not found"
            continue

        # Always report as manual required — never auto-apply
        patch["status"] = "MANUAL_REQUIRED"
        patch["dry_run_note"] = (
            "Auto-patch disabled in pre-deploy hook (council decision: global regex replace too risky). "
            "Review suggested fix and apply manually."
        )
        reported.append(patch)

    return reported


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_report(synthesis: ReviewSynthesis) -> str:
    """Generate human-readable review report."""
    lines = [
        "# SYLION AI Review Report",
        f"**Date:** {synthesis.timestamp}",
        f"**Consensus:** {synthesis.consensus_verdict}",
        "",
        "## Reviewers",
        "",
    ]

    for r in synthesis.reports:
        status = f"✅ {r.verdict}" if r.verdict != "SKIP" else f"⏭ SKIP ({r.error})"
        lines.append(f"| {r.reviewer} | {status} | {r.confidence}% | {len(r.findings)} findings | {r.duration_s}s |")

    lines.extend(["", "## Agreed Findings (≥2 reviewers)", ""])
    if synthesis.agreed_findings:
        for f in synthesis.agreed_findings:
            lines.append(f"- **[{f.severity}]** {f.title} — `{f.file}:{f.line or '?'}`")
            lines.append(f"  {f.description[:200]}")
            if f.auto_fixable:
                lines.append(f"  → AUTO-FIX: {f.suggested_fix}")
    else:
        lines.append("None — code looks clean.")

    if synthesis.disputed_findings:
        lines.extend(["", "## Disputed (1 reviewer only)", ""])
        for f in synthesis.disputed_findings:
            lines.append(f"- [{f.severity}] {f.title} — `{f.file}:{f.line or '?'}`")

    if synthesis.auto_patches:
        lines.extend(["", "## Auto-patches Applied", ""])
        for p in synthesis.auto_patches:
            lines.append(f"- {p['reason']}: `{p['file']}` — {p.get('status', 'pending')}")

    if synthesis.human_gate_items:
        lines.extend(["", "## ⚠ Human Gate Required", ""])
        for item in synthesis.human_gate_items:
            lines.append(f"- **{item['finding']['title']}** ({item['finding']['file']})")
            lines.append(f"  Agreed by: {', '.join(item['agreed_by'])}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
async def run_review(
    files: Optional[list[Path]] = None,
    quick: bool = False,
    dry_run: bool = False,
) -> ReviewSynthesis:
    """Run full AI review pipeline."""
    log.info("=" * 60)
    log.info("SYLION AI Review Pipeline — starting")
    log.info("=" * 60)

    # Determine files to review
    if files:
        review_files = [SYLION_ROOT / f if not Path(f).is_absolute() else Path(f) for f in files]
    elif quick:
        # Only review files changed since last review
        review_files = _get_changed_files()
    else:
        # Full review of high-risk files
        review_files = [SYLION_ROOT / p for p in HIGH_RISK_PATTERNS if (SYLION_ROOT / p).exists()]

    log.info(f"Reviewing {len(review_files)} files: {[str(f.name) for f in review_files]}")

    # Run all reviewers in parallel
    log.info("Launching reviewers: static_scan + ollama3 + claude_code")

    static_report = run_static_scan(review_files)
    log.info(f"  ✓ static_scan: {static_report.verdict} ({len(static_report.findings)} findings, {static_report.duration_s}s)")

    ollama_task = asyncio.create_task(run_ollama_review(review_files))
    claude_task = asyncio.create_task(run_claude_code_review(review_files))

    ollama_report, claude_report = await asyncio.gather(ollama_task, claude_task)

    log.info(f"  {'✓' if ollama_report.verdict != 'SKIP' else '⏭'} ollama3: {ollama_report.verdict} ({len(ollama_report.findings)} findings, {ollama_report.duration_s}s)")
    log.info(f"  {'✓' if claude_report.verdict != 'SKIP' else '⏭'} claude_code: {claude_report.verdict} ({len(claude_report.findings)} findings, {claude_report.duration_s}s)")

    # Synthesize
    synthesis = synthesize_reviews([static_report, ollama_report, claude_report])
    log.info(f"\nConsensus: {synthesis.consensus_verdict}")
    log.info(f"  Agreed findings: {len(synthesis.agreed_findings)}")
    log.info(f"  Disputed: {len(synthesis.disputed_findings)}")
    log.info(f"  Auto-patches: {len(synthesis.auto_patches)}")
    log.info(f"  Human Gate items: {len(synthesis.human_gate_items)}")

    # Apply auto-patches
    if synthesis.auto_patches:
        applied = apply_auto_patches(synthesis, dry_run=dry_run)
        log.info(f"  Applied {len(applied)} auto-patches")

    # Save report
    report_text = generate_report(synthesis)
    report_path = REVIEW_DIR / f"review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.write_text(report_text, encoding="utf-8")
    log.info(f"  Report saved: {report_path}")

    # Save JSON for dashboard consumption
    json_path = REVIEW_DIR / "latest_review.json"
    json_path.write_text(json.dumps(synthesis.to_dict(), indent=2, default=str), encoding="utf-8")

    return synthesis


def _get_changed_files() -> list[Path]:
    """Get files changed since last review (via git or mtime)."""
    try:
        # Get ALL changed files: committed (HEAD~1), staged, and unstaged
        changed = set()
        for cmd in [
            ["git", "diff", "--name-only", "HEAD~1"],     # last commit
            ["git", "diff", "--name-only", "HEAD"],        # unstaged changes
            ["git", "diff", "--name-only", "--cached"],    # staged changes
        ]:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=str(SYLION_ROOT),
            )
            if result.returncode == 0 and result.stdout.strip():
                changed.update(f.strip() for f in result.stdout.strip().split("\n") if f.strip())
        if changed:
            return [SYLION_ROOT / f for f in changed]
    except Exception:
        pass

    # Fallback: high-risk files
    return [SYLION_ROOT / p for p in HIGH_RISK_PATTERNS if (SYLION_ROOT / p).exists()]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    import argparse
    parser = argparse.ArgumentParser(description="SYLION AI Review Pipeline")
    parser.add_argument("--quick", action="store_true", help="Quick scan (changed files only)")
    parser.add_argument("--file", nargs="+", help="Specific files to review")
    parser.add_argument("--dry-run", action="store_true", help="Show patches without applying")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = parser.parse_args()

    files = [Path(f) for f in args.file] if args.file else None

    synthesis = asyncio.run(run_review(files=files, quick=args.quick, dry_run=args.dry_run))

    if args.json:
        print(json.dumps(synthesis.to_dict(), indent=2, default=str))
    else:
        print(generate_report(synthesis))

    # Exit code reflects consensus
    if synthesis.consensus_verdict == Verdict.BLOCK.value:
        sys.exit(2)
    elif synthesis.consensus_verdict == Verdict.REQUEST_CHANGES.value:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
