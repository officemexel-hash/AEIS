"""
SYLION Anti-Hallucination Layer 3: ClaimProvenance

Verifies that agent claims about code (file paths, line numbers, function names,
variable names) actually exist in the source. Uses keyword matching in the
vicinity of cited lines to detect hallucinated findings.

When an auditor says "line 42 of pkg/auth/handler.go has an unsafe XFF read",
this layer opens the file, reads lines around 42, and checks whether the cited
keywords (XFF, X-Forwarded-For, handler, etc.) actually appear there.

Phase: Enhancement (not a blocker for Phase 1, required for Phase 2-3 autonomy)
Estimated effort: ~150 lines, 1 day
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger("claim_provenance")


class ProvenanceVerdict(str, Enum):
    """Result of provenance check for a single claim."""
    VERIFIED = "VERIFIED"          # Keywords found near cited line
    WEAK = "WEAK"                  # File exists but keywords not found near line
    FILE_MISSING = "FILE_MISSING"  # Referenced file does not exist
    LINE_OOB = "LINE_OOB"         # Line number out of bounds
    NO_EVIDENCE = "NO_EVIDENCE"    # No keywords provided to check
    ERROR = "ERROR"                # Internal error


@dataclass
class ProvenanceClaim:
    """A single claim made by an agent about source code."""
    finding_id: str
    agent_name: str
    file_path: str             # Path relative to workspace (e.g. "pkg/auth/handler.go")
    line_number: int           # Cited line number
    keywords: list[str]        # Keywords that should appear near the line
    title: str = ""            # Short description of the finding
    evidence_snippet: str = "" # Agent-provided code snippet


@dataclass
class ProvenanceResult:
    """Outcome of provenance verification for one claim."""
    finding_id: str
    verdict: ProvenanceVerdict = ProvenanceVerdict.NO_EVIDENCE
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    actual_lines: str = ""     # What actually exists at the cited location
    match_ratio: float = 0.0   # Fraction of keywords matched (0.0 - 1.0)
    context_window: int = 0    # How many lines around cited line were checked
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "verdict": self.verdict.value,
            "matched_keywords": self.matched_keywords,
            "missing_keywords": self.missing_keywords,
            "actual_lines": self.actual_lines[:1000],
            "match_ratio": round(self.match_ratio, 3),
            "context_window": self.context_window,
            "error_message": self.error_message,
        }


class ClaimProvenance:
    """Layer 3 anti-hallucination: verify agent claims reference real code.

    For each finding that cites a file path + line number, this layer:
      1. Checks the file exists in the workspace
      2. Reads lines around the cited line (configurable window)
      3. Searches for keywords from the finding's evidence/title
      4. Returns a verdict: VERIFIED, WEAK, FILE_MISSING, LINE_OOB

    Usage:
        cp = ClaimProvenance(workspace=Path("/path/to/sylion"))
        claim = ProvenanceClaim(
            finding_id="FIND-042",
            agent_name="auditor_claude",
            file_path="pkg/auth/handler.go",
            line_number=42,
            keywords=["X-Forwarded-For", "XFF", "RemoteAddr"],
        )
        result = cp.verify_claim(claim)
        if result.verdict == ProvenanceVerdict.WEAK:
            # Agent may be hallucinating this finding
    """

    def __init__(
        self,
        workspace: Path,
        *,
        context_window: int = 10,
        min_match_ratio: float = 0.3,
        case_sensitive: bool = False,
        log_dir: Path | None = None,
    ):
        """
        Args:
            workspace: Root of the Go source tree.
            context_window: Number of lines above+below the cited line to search.
            min_match_ratio: Minimum fraction of keywords that must match for VERIFIED.
            case_sensitive: Whether keyword matching is case-sensitive.
            log_dir: Directory to write provenance logs.
        """
        self.workspace = workspace.resolve()
        self.context_window = context_window
        self.min_match_ratio = min_match_ratio
        self.case_sensitive = case_sensitive
        self.log_dir = log_dir

        # Counters
        self._total_checks = 0
        self._verified = 0
        self._weak = 0
        self._missing = 0
        self._results: list[ProvenanceResult] = []

        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_claim(self, claim: ProvenanceClaim) -> ProvenanceResult:
        """Verify a single provenance claim.

        Args:
            claim: The claim to verify.

        Returns:
            ProvenanceResult with verdict and details.
        """
        self._total_checks += 1

        result = ProvenanceResult(
            finding_id=claim.finding_id,
            context_window=self.context_window,
        )

        # No keywords to check
        if not claim.keywords:
            result.verdict = ProvenanceVerdict.NO_EVIDENCE
            self._save_result(result)
            return result

        # Check file exists
        file_path = self.workspace / claim.file_path
        if not file_path.is_file():
            result.verdict = ProvenanceVerdict.FILE_MISSING
            result.missing_keywords = list(claim.keywords)
            result.error_message = f"File not found: {claim.file_path}"
            self._missing += 1
            log.warning(
                "ClaimProvenance FILE_MISSING: %s references non-existent %s",
                claim.finding_id, claim.file_path,
            )
            self._save_result(result)
            return result

        # Read file
        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as e:
            result.verdict = ProvenanceVerdict.ERROR
            result.error_message = f"Cannot read {claim.file_path}: {e}"
            self._save_result(result)
            return result

        # Check line in bounds
        if claim.line_number < 1 or claim.line_number > len(lines):
            result.verdict = ProvenanceVerdict.LINE_OOB
            result.error_message = (
                f"Line {claim.line_number} out of bounds "
                f"(file has {len(lines)} lines)"
            )
            self._missing += 1
            log.warning(
                "ClaimProvenance LINE_OOB: %s cites line %d but %s has %d lines",
                claim.finding_id, claim.line_number, claim.file_path, len(lines),
            )
            self._save_result(result)
            return result

        # Extract context window
        start = max(0, claim.line_number - 1 - self.context_window)
        end = min(len(lines), claim.line_number + self.context_window)
        context_lines = lines[start:end]
        context_text = "\n".join(context_lines)
        result.actual_lines = context_text

        # Match keywords
        matched = []
        missing = []
        for kw in claim.keywords:
            if self._keyword_in_text(kw, context_text):
                matched.append(kw)
            else:
                missing.append(kw)

        result.matched_keywords = matched
        result.missing_keywords = missing
        result.match_ratio = len(matched) / len(claim.keywords) if claim.keywords else 0.0

        # Determine verdict
        if result.match_ratio >= self.min_match_ratio:
            result.verdict = ProvenanceVerdict.VERIFIED
            self._verified += 1
            log.debug(
                "ClaimProvenance VERIFIED: %s (%.0f%% keywords matched)",
                claim.finding_id, result.match_ratio * 100,
            )
        else:
            result.verdict = ProvenanceVerdict.WEAK
            self._weak += 1
            log.warning(
                "ClaimProvenance WEAK: %s — only %.0f%% keywords matched "
                "(found: %s, missing: %s)",
                claim.finding_id, result.match_ratio * 100,
                matched, missing,
            )

        self._save_result(result)
        return result

    def verify_batch(self, claims: list[ProvenanceClaim]) -> list[ProvenanceResult]:
        """Verify multiple claims and return all results."""
        return [self.verify_claim(c) for c in claims]

    def extract_claims_from_findings(
        self,
        findings: list[dict[str, Any]],
        agent_name: str,
    ) -> list[ProvenanceClaim]:
        """Convert raw JSON findings into ProvenanceClaim objects.

        Expected finding format (from auditor agents):
            {
                "id": "FIND-042",
                "file": "pkg/auth/handler.go",
                "line": 42,
                "title": "Unsafe XFF read",
                "evidence": "req.Header.Get(\"X-Forwarded-For\")",
                ...
            }

        Args:
            findings: List of finding dicts from auditor output.
            agent_name: Name of the agent that produced these findings.

        Returns:
            List of ProvenanceClaim objects ready for verification.
        """
        claims = []
        for f in findings:
            finding_id = f.get("id", f.get("finding_id", "UNKNOWN"))
            file_path = f.get("file", "")
            line_num = f.get("line", 0)
            title = f.get("title", "")
            evidence = f.get("evidence", "")

            if not file_path or not line_num:
                continue

            # Extract keywords from title + evidence
            keywords = self._extract_keywords(title, evidence)

            claims.append(ProvenanceClaim(
                finding_id=finding_id,
                agent_name=agent_name,
                file_path=file_path,
                line_number=int(line_num),
                keywords=keywords,
                title=title,
                evidence_snippet=evidence,
            ))

        return claims

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        return {
            "total_checks": self._total_checks,
            "verified": self._verified,
            "weak": self._weak,
            "file_missing": self._missing,
            "verification_rate": (
                self._verified / self._total_checks
                if self._total_checks > 0
                else 0.0
            ),
        }

    def export_report(self) -> dict[str, Any]:
        """Export full provenance report."""
        return {
            "stats": self.get_stats(),
            "results": [r.to_dict() for r in self._results],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _keyword_in_text(self, keyword: str, text: str) -> bool:
        """Check if a keyword appears in the text (respecting case_sensitive setting)."""
        if self.case_sensitive:
            return keyword in text
        return keyword.lower() in text.lower()

    def _extract_keywords(self, title: str, evidence: str) -> list[str]:
        """Extract meaningful keywords from finding title + evidence.

        Filters out Go language noise (func, return, if, etc.) and keeps
        identifiers, function names, package names, and security-relevant terms.
        """
        combined = f"{title} {evidence}"

        # Extract Go identifiers (CamelCase, snake_case, pkg.Func)
        identifiers = re.findall(r'[A-Z][a-zA-Z0-9]+|[a-z_][a-zA-Z0-9_.]+', combined)

        # Also extract quoted strings (often exact code references)
        quoted = re.findall(r'"([^"]+)"', combined)
        quoted += re.findall(r"'([^']+)'", combined)

        # Filter noise words
        noise = {
            "func", "return", "if", "else", "for", "range", "var", "const",
            "type", "struct", "interface", "package", "import", "nil", "err",
            "error", "string", "int", "bool", "byte", "true", "false",
            "the", "and", "or", "not", "is", "in", "to", "of", "a", "an",
        }

        keywords = []
        seen = set()
        for token in identifiers + quoted:
            token_clean = token.strip()
            if (
                len(token_clean) >= 3
                and token_clean.lower() not in noise
                and token_clean not in seen
            ):
                keywords.append(token_clean)
                seen.add(token_clean)

        return keywords[:15]  # Cap at 15 keywords per claim

    def _save_result(self, result: ProvenanceResult) -> None:
        """Persist result to internal list and optionally to disk."""
        self._results.append(result)
        if self.log_dir:
            safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', result.finding_id)
            log_file = self.log_dir / f"provenance_{safe_id}.json"
            try:
                with open(log_file, "w", encoding="utf-8") as f:
                    json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            except OSError as e:
                log.warning("Failed to write provenance log to %s: %s", log_file, e)
