"""
SYLION Anti-Hallucination Layer 5: FactCheckerAgent

An independent LLM-based fact-checker that runs before Stage 6 (Deploy).
Takes the merged findings + proposed patches and asks a separate LLM
to verify that:
  1. Each finding references real code that exists
  2. The proposed fix actually addresses the stated problem
  3. The fix doesn't introduce new issues
  4. The severity rating is justified

This is the highest-confidence anti-hallucination layer because it uses
a full LLM to reason about correctness, not just pattern matching.

Phase: Enhancement (not a blocker for Phase 1, required for Phase 2-3 autonomy)
Estimated effort: ~200 lines, 1 day
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# R3.13: legacy dashboard cost tracker removed; unified monitoring owns budget data.
_COST_TRACKER_AVAILABLE = False
_cost_tracker = None
_compute_cost = None

log = logging.getLogger("fact_checker")

#: Current recommended model ID for the FactChecker.
#: Update this constant when Anthropic releases a newer Sonnet.
#: Override at runtime via the FACT_CHECKER_MODEL_ID environment variable.
DEFAULT_FACT_CHECKER_MODEL_ID: str = os.environ.get(
    "FACT_CHECKER_MODEL_ID", "anthropic/claude-sonnet-4-6"
)


class FactCheckVerdict(str, Enum):
    """Result of LLM-based fact checking for a single finding/patch."""
    CONFIRMED = "CONFIRMED"        # Finding and fix verified by independent LLM
    DISPUTED = "DISPUTED"          # LLM believes finding or fix is incorrect
    HALLUCINATION = "HALLUCINATION" # LLM detected hallucinated content
    INCONCLUSIVE = "INCONCLUSIVE"  # LLM cannot determine correctness
    SKIPPED = "SKIPPED"            # Fact check skipped (budget, timeout, etc.)
    ERROR = "ERROR"                # Internal error during fact checking


@dataclass
class FactCheckItem:
    """A single item to be fact-checked: a finding + optional patch."""
    finding_id: str
    file_path: str
    line_number: int
    title: str
    description: str
    severity: str
    evidence: str = ""
    fix_suggestion: str = ""
    patch_diff: str = ""         # Unified diff if available
    agent_name: str = ""         # Which agent produced this finding


@dataclass
class FactCheckResult:
    """Outcome of fact-checking a single item."""
    finding_id: str
    verdict: FactCheckVerdict = FactCheckVerdict.SKIPPED
    confidence: float = 0.0       # 0.0 - 1.0
    reasoning: str = ""           # LLM's explanation
    issues_found: list[str] = field(default_factory=list)
    suggested_severity: str = ""  # LLM's opinion on correct severity
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    llm_model: str = ""
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning[:2000],
            "issues_found": self.issues_found[:10],
            "suggested_severity": self.suggested_severity,
            "timestamp": self.timestamp,
            "llm_model": self.llm_model,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }


@dataclass
class FactCheckReport:
    """Summary of all fact checks for a pipeline run."""
    total_items: int
    confirmed: int
    disputed: int
    hallucinations: int
    inconclusive: int
    errors: int
    results: list[FactCheckResult]
    llm_model: str
    total_elapsed_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_items": self.total_items,
            "confirmed": self.confirmed,
            "disputed": self.disputed,
            "hallucinations": self.hallucinations,
            "inconclusive": self.inconclusive,
            "errors": self.errors,
            "confirmation_rate": round(
                self.confirmed / self.total_items, 3
            ) if self.total_items > 0 else 0.0,
            "hallucination_rate": round(
                self.hallucinations / self.total_items, 3
            ) if self.total_items > 0 else 0.0,
            "llm_model": self.llm_model,
            "total_elapsed_seconds": round(self.total_elapsed_seconds, 2),
            "results": [r.to_dict() for r in self.results],
        }


# The system prompt for the fact-checker LLM
FACT_CHECK_SYSTEM_PROMPT = """You are an independent fact-checker for a Go security audit pipeline.
Your job is to verify whether audit findings and proposed patches are correct.

## Your Tasks
1. CHECK if the cited file path and line number contain the code described
2. CHECK if the described vulnerability/issue actually exists at that location
3. CHECK if the proposed fix correctly addresses the issue
4. CHECK if the severity rating (CRITICAL/HIGH/MEDIUM/LOW) is justified
5. DETECT hallucinations — cases where the auditor fabricated code, line numbers, or issues

## Response Format (STRICT JSON)
{
  "verdict": "CONFIRMED|DISPUTED|HALLUCINATION|INCONCLUSIVE",
  "confidence": 0.0-1.0,
  "reasoning": "Your detailed explanation",
  "issues_found": ["list of specific problems found"],
  "suggested_severity": "CRITICAL|HIGH|MEDIUM|LOW"
}

## Rules
- Be SKEPTICAL. Assume the auditor may have hallucinated.
- If the file/line doesn't match the evidence, verdict = HALLUCINATION.
- If the issue exists but severity is wrong, verdict = DISPUTED with correct severity.
- If everything checks out, verdict = CONFIRMED.
- Always explain your reasoning.
"""


class FactCheckerAgent:
    """Layer 5 anti-hallucination: independent LLM verification before deploy.

    Uses a separate LLM (different from the auditor) to verify findings
    and patches before they proceed to Stage 6 (Deploy).

    The fact-checker reads the ACTUAL source code and compares it against
    the auditor's claims, catching hallucinated line numbers, fabricated
    code snippets, and incorrect severity ratings.

    Usage:
        fc = FactCheckerAgent(
            workspace=Path("/path/to/sylion"),
            llm_caller=my_llm_function,
            model_id="anthropic/claude-sonnet-4-6",
        )
        items = [FactCheckItem(...), ...]
        report = fc.check_all(items)
        if report.hallucinations > 0:
            # Flag hallucinated findings
    """

    def __init__(
        self,
        workspace: Path,
        *,
        llm_caller: Any = None,  # Callable[[str, str], str] — (system, user) -> response
        model_id: str | None = None,
        max_items_per_run: int = 50,
        context_lines: int = 20,
        log_dir: Path | None = None,
    ):
        """
        Args:
            workspace: Root of the Go source tree.
            llm_caller: Function that calls LLM: (system_prompt, user_prompt) -> response_text.
                        If None, fact-checking is skipped with SKIPPED verdict.
            model_id: LLM model identifier (for logging). If None, reads from
                      env var FACT_CHECKER_MODEL_ID, then falls back to
                      DEFAULT_FACT_CHECKER_MODEL_ID ("anthropic/claude-sonnet-4-6").
            max_items_per_run: Maximum findings to check in one run (budget control).
            context_lines: Lines of source context to provide to LLM.
            log_dir: Directory for fact-check logs.
        """
        self.workspace = workspace.resolve()
        self.llm_caller = llm_caller
        self.model_id = model_id or DEFAULT_FACT_CHECKER_MODEL_ID
        self.max_items_per_run = max_items_per_run
        self.context_lines = context_lines
        self.log_dir = log_dir

        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_all(self, items: list[FactCheckItem]) -> FactCheckReport:
        """Fact-check all items and return a report.

        Args:
            items: List of findings/patches to verify.

        Returns:
            FactCheckReport with per-item results and summary stats.
        """
        t0 = time.monotonic()

        # Enforce budget limit
        check_items = items[:self.max_items_per_run]
        if len(items) > self.max_items_per_run:
            log.warning(
                "FactChecker: truncating %d items to max %d",
                len(items), self.max_items_per_run,
            )

        results = []
        for item in check_items:
            result = self._check_one(item)
            results.append(result)

        # Tally
        confirmed = sum(1 for r in results if r.verdict == FactCheckVerdict.CONFIRMED)
        disputed = sum(1 for r in results if r.verdict == FactCheckVerdict.DISPUTED)
        hallucinations = sum(1 for r in results if r.verdict == FactCheckVerdict.HALLUCINATION)
        inconclusive = sum(1 for r in results if r.verdict == FactCheckVerdict.INCONCLUSIVE)
        errors = sum(1 for r in results if r.verdict in (FactCheckVerdict.ERROR, FactCheckVerdict.SKIPPED))

        report = FactCheckReport(
            total_items=len(check_items),
            confirmed=confirmed,
            disputed=disputed,
            hallucinations=hallucinations,
            inconclusive=inconclusive,
            errors=errors,
            results=results,
            llm_model=self.model_id,
            total_elapsed_seconds=time.monotonic() - t0,
        )

        log.info(
            "FactChecker complete: %d items — %d confirmed, %d disputed, "
            "%d hallucinations, %d inconclusive, %d errors (%.1fs)",
            len(check_items), confirmed, disputed, hallucinations,
            inconclusive, errors, report.total_elapsed_seconds,
        )

        if self.log_dir:
            self._save_report(report)

        return report

    def check_one(self, item: FactCheckItem) -> FactCheckResult:
        """Fact-check a single item. Public wrapper for _check_one."""
        return self._check_one(item)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_one(self, item: FactCheckItem) -> FactCheckResult:
        """Run LLM fact-check on a single finding."""
        t0 = time.monotonic()

        result = FactCheckResult(
            finding_id=item.finding_id,
            llm_model=self.model_id,
        )

        # If no LLM caller, skip
        if self.llm_caller is None:
            result.verdict = FactCheckVerdict.SKIPPED
            result.reasoning = "No LLM caller configured — fact-checking skipped."
            result.elapsed_seconds = time.monotonic() - t0
            return result

        # Read actual source code
        source_context = self._read_source_context(item.file_path, item.line_number)

        # Build user prompt
        user_prompt = self._build_user_prompt(item, source_context)

        try:
            response = self.llm_caller(FACT_CHECK_SYSTEM_PROMPT, user_prompt)
            parsed = self._parse_response(response)

            result.verdict = parsed.get("verdict", FactCheckVerdict.INCONCLUSIVE)
            result.confidence = parsed.get("confidence", 0.0)
            result.reasoning = parsed.get("reasoning", "")
            result.issues_found = parsed.get("issues_found", [])
            result.suggested_severity = parsed.get("suggested_severity", "")

            # v5.9.1 Cluster R: record cost via cost_tracker
            # Estimate token counts: prompt ~1 token/4 chars; response ~1 token/4 chars
            if _COST_TRACKER_AVAILABLE and _cost_tracker is not None:
                try:
                    _in = max(1, (len(FACT_CHECK_SYSTEM_PROMPT) + len(user_prompt)) // 4)
                    _out = max(1, len(response) // 4)
                    provider = "anthropic" if "claude" in self.model_id.lower() else (
                        "openai" if "gpt" in self.model_id.lower() else "unknown"
                    )
                    cost_usd, _ = _compute_cost(self.model_id, _in, _out)
                    elapsed_ms = (time.monotonic() - t0) * 1000
                    _cost_tracker.record_llm_call(
                        provider=provider,
                        model=self.model_id,
                        input_tokens=_in,
                        output_tokens=_out,
                        cost_usd=cost_usd,
                        agent_id="fact_checker",
                        latency_ms=elapsed_ms,
                        success=True,
                    )
                except Exception as _ct_exc:
                    log.debug("cost_tracker record failed (non-fatal): %s", _ct_exc)

        except Exception as e:
            result.verdict = FactCheckVerdict.ERROR
            result.reasoning = f"LLM call failed: {e}"
            log.error("FactChecker error for %s: %s", item.finding_id, e)

            # v5.9.1 Cluster R: record failed call
            if _COST_TRACKER_AVAILABLE and _cost_tracker is not None:
                try:
                    provider = "anthropic" if "claude" in self.model_id.lower() else "unknown"
                    _cost_tracker.record_llm_call(
                        provider=provider, model=self.model_id,
                        input_tokens=0, output_tokens=0, cost_usd=0.0,
                        agent_id="fact_checker",
                        latency_ms=(time.monotonic() - t0) * 1000,
                        success=False, error=str(e),
                    )
                except Exception:
                    pass

        result.elapsed_seconds = time.monotonic() - t0
        return result

    def _read_source_context(self, file_path: str, line_number: int) -> str:
        """Read source code around the cited line."""
        full_path = self.workspace / file_path
        if not full_path.is_file():
            return f"[FILE NOT FOUND: {file_path}]"

        try:
            lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as e:
            return f"[CANNOT READ: {file_path}: {e}]"

        if line_number < 1 or line_number > len(lines):
            return f"[LINE {line_number} OUT OF BOUNDS — file has {len(lines)} lines]"

        start = max(0, line_number - 1 - self.context_lines)
        end = min(len(lines), line_number + self.context_lines)

        numbered = []
        for i in range(start, end):
            marker = " >>>" if i == line_number - 1 else "    "
            numbered.append(f"{i + 1:5d}{marker} {lines[i]}")

        return "\n".join(numbered)

    def _build_user_prompt(self, item: FactCheckItem, source_context: str) -> str:
        """Build the user prompt for the fact-checker LLM."""
        parts = [
            f"## Finding to Verify",
            f"- ID: {item.finding_id}",
            f"- Agent: {item.agent_name}",
            f"- File: {item.file_path}",
            f"- Line: {item.line_number}",
            f"- Severity: {item.severity}",
            f"- Title: {item.title}",
            f"",
            f"### Description",
            item.description,
            f"",
        ]

        if item.evidence:
            parts.extend([
                f"### Evidence (agent-provided code snippet)",
                f"```",
                item.evidence,
                f"```",
                f"",
            ])

        if item.fix_suggestion:
            parts.extend([
                f"### Proposed Fix",
                item.fix_suggestion,
                f"",
            ])

        if item.patch_diff:
            parts.extend([
                f"### Patch (unified diff)",
                f"```diff",
                item.patch_diff[:3000],
                f"```",
                f"",
            ])

        parts.extend([
            f"## ACTUAL Source Code (from repository)",
            f"File: {item.file_path}, centered on line {item.line_number}:",
            f"```go",
            source_context,
            f"```",
            f"",
            f"Now verify: does the finding accurately describe what's in the source code?",
            f"Is the severity justified? Does the proposed fix address the real issue?",
            f"Respond in STRICT JSON format.",
        ])

        return "\n".join(parts)

    def _parse_response(self, response: str) -> dict[str, Any]:
        """Parse LLM response JSON, handling markdown code blocks."""
        # Strip markdown code fences if present
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (code fences)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            import re
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return {"verdict": FactCheckVerdict.ERROR, "reasoning": "Cannot parse LLM response"}
            else:
                return {"verdict": FactCheckVerdict.ERROR, "reasoning": "No JSON in LLM response"}

        # Normalize verdict
        verdict_str = data.get("verdict", "INCONCLUSIVE").upper()
        try:
            data["verdict"] = FactCheckVerdict(verdict_str)
        except ValueError:
            data["verdict"] = FactCheckVerdict.INCONCLUSIVE

        # Clamp confidence
        conf = data.get("confidence", 0.5)
        data["confidence"] = max(0.0, min(1.0, float(conf)))

        return data

    def _save_report(self, report: FactCheckReport) -> None:
        """Save fact-check report to log directory."""
        if not self.log_dir:
            return
        path = self.log_dir / "fact_check_report.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        except OSError as e:
            log.warning("Failed to write fact-check report to %s: %s", path, e)
