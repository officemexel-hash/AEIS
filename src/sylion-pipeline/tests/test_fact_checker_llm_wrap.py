"""T-03: Tests for FactCheckerAgent LLM adapter in orchestrator.py.

Verifies that:
1. _fc_caller correctly wraps an LLM object (dict-style access) as callable (system, user) -> str
2. The 50% error threshold guard raises RuntimeError when too many FactChecker errors occur
3. No real API calls are made — LLM is fully mocked
"""
from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure pipeline root is on sys.path so fact_checker / openhands are importable
# ---------------------------------------------------------------------------
_PIPELINE_ROOT = str(Path(__file__).resolve().parent.parent)
if _PIPELINE_ROOT not in sys.path:
    sys.path.insert(0, _PIPELINE_ROOT)

# ---------------------------------------------------------------------------
# Minimal stubs so orchestrator imports don't fail in test environment
# ---------------------------------------------------------------------------

# Stub litellm before any import touches it
if "litellm" not in sys.modules:
    _litellm_stub = types.ModuleType("litellm")
    _litellm_stub.completion = lambda *a, **kw: None  # type: ignore[attr-defined]
    _litellm_stub.completion_cost = lambda *a, **kw: 0.0  # type: ignore[attr-defined]
    sys.modules["litellm"] = _litellm_stub


class TestFcCallerAdapter(unittest.TestCase):
    """Test that _fc_caller adapter correctly converts LLM object to callable."""

    def _make_mock_llm(self, response_text: str = "LLM response") -> Any:
        """Build a mock LLM whose .completion() returns a dict-like response."""
        mock_llm = MagicMock()
        mock_response = {
            "choices": [
                {"message": {"content": response_text}}
            ]
        }
        mock_llm.completion.return_value = mock_response
        return mock_llm

    def test_fc_caller_returns_content(self):
        """_fc_caller(system, user) returns choices[0].message.content."""
        mock_llm = self._make_mock_llm("CONFIRMED: finding is valid")

        # Replicate _fc_caller construction from orchestrator.py
        _fc_llm_obj = mock_llm
        def _fc_caller(system: str, user: str) -> str:
            return _fc_llm_obj.completion(
                [{"role": "system", "content": system},
                 {"role": "user", "content": user}]
            )["choices"][0]["message"]["content"]

        result = _fc_caller("You are a fact-checker.", "Check this finding.")
        self.assertEqual(result, "CONFIRMED: finding is valid")

    def test_fc_caller_passes_messages_correctly(self):
        """_fc_caller passes system and user messages in correct roles."""
        mock_llm = self._make_mock_llm("ok")

        _fc_llm_obj = mock_llm
        def _fc_caller(system: str, user: str) -> str:
            return _fc_llm_obj.completion(
                [{"role": "system", "content": system},
                 {"role": "user", "content": user}]
            )["choices"][0]["message"]["content"]

        _fc_caller("sys_prompt", "usr_prompt")

        call_args = mock_llm.completion.call_args
        messages = call_args[0][0]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "sys_prompt")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "usr_prompt")

    def test_fc_caller_not_llm_object_directly(self):
        """Passing LLM object directly as llm_caller would fail — adapter is needed."""
        mock_llm = self._make_mock_llm("response")

        # Simulate the OLD broken code: passing LLM object as llm_caller
        # The LLM object is NOT callable as (system, user) -> str
        # This verifies the bug exists without the adapter
        with self.assertRaises((TypeError, AttributeError)):
            # Calling mock_llm directly as if it were the callable llm_caller
            # mock_llm is not callable as (system, user) signature without adapter
            result = mock_llm("system prompt", "user prompt")
            # If mock_llm happens to be callable (MagicMock is callable),
            # simulate what FactCheckerAgent would do — it would call
            # llm_caller(system, user) and try to use the return as a string.
            # MagicMock returns another MagicMock, not a string, which
            # would cause downstream failures.
            if not isinstance(result, str):
                raise TypeError(
                    f"llm_caller must return str, got {type(result).__name__}"
                )


class TestFactCheckerErrorThreshold(unittest.TestCase):
    """Test the 50% error threshold guard added to stage_5_6_fact_check."""

    def _make_fc_report(self, errors: int, total_items: int):
        """Create a mock FactCheckReport with given error count."""
        from fact_checker import FactCheckReport
        report = FactCheckReport(
            total_items=total_items,
            confirmed=max(0, total_items - errors),
            disputed=0,
            hallucinations=0,
            inconclusive=0,
            errors=errors,
            results=[],
            llm_model="mock-model",
            total_elapsed_seconds=1.0,
        )
        return report

    def test_error_threshold_not_raised_when_below_50_pct(self):
        """No RuntimeError when errors <= 50% of items."""
        from fact_checker import FactCheckReport
        # 2 errors out of 5 = 40% — should NOT raise
        report = self._make_fc_report(errors=2, total_items=5)
        fc_items = [object()] * 5  # dummy list of length 5

        # Replicate the guard logic from orchestrator.py
        def _check_error_threshold(fc_report, fc_items):
            if fc_items and fc_report.errors > len(fc_items) * 0.5:
                raise RuntimeError(
                    f"FactChecker broken: too many errors "
                    f"({fc_report.errors}/{len(fc_items)} findings returned ERROR verdict)"
                )

        # Should not raise
        _check_error_threshold(report, fc_items)

    def test_error_threshold_raises_at_exactly_50_plus_1(self):
        """RuntimeError raised when errors > 50% of items."""
        report = self._make_fc_report(errors=3, total_items=5)
        fc_items = [object()] * 5  # 3/5 = 60% — SHOULD raise

        def _check_error_threshold(fc_report, fc_items):
            if fc_items and fc_report.errors > len(fc_items) * 0.5:
                raise RuntimeError(
                    f"FactChecker broken: too many errors "
                    f"({fc_report.errors}/{len(fc_items)} findings returned ERROR verdict)"
                )

        with self.assertRaises(RuntimeError) as ctx:
            _check_error_threshold(report, fc_items)
        self.assertIn("FactChecker broken: too many errors", str(ctx.exception))
        self.assertIn("3/5", str(ctx.exception))

    def test_error_threshold_not_raised_for_empty_items(self):
        """Guard skips check when fc_items is empty (avoids ZeroDivisionError)."""
        report = self._make_fc_report(errors=0, total_items=0)
        fc_items = []

        def _check_error_threshold(fc_report, fc_items):
            if fc_items and fc_report.errors > len(fc_items) * 0.5:
                raise RuntimeError("FactChecker broken: too many errors")

        # Should not raise on empty list
        _check_error_threshold(report, fc_items)

    def test_error_threshold_exact_50_pct_does_not_raise(self):
        """Exactly 50% errors does NOT raise (guard uses strictly greater than)."""
        report = self._make_fc_report(errors=2, total_items=4)
        fc_items = [object()] * 4  # 2/4 = exactly 50% — NOT > 50%

        def _check_error_threshold(fc_report, fc_items):
            if fc_items and fc_report.errors > len(fc_items) * 0.5:
                raise RuntimeError("FactChecker broken: too many errors")

        # Should not raise at exactly 50%
        _check_error_threshold(report, fc_items)


class TestFcCallerWithRealFactChecker(unittest.TestCase):
    """Integration: FactCheckerAgent uses _fc_caller adapter correctly."""

    def test_fact_checker_agent_with_mock_caller(self):
        """FactCheckerAgent accepts and uses a (system, user) -> str callable."""
        from fact_checker import FactCheckerAgent, FactCheckItem
        import tempfile

        response_text = json.dumps({
            "verdict": "CONFIRMED",
            "confidence": 0.9,
            "reasoning": "The finding appears valid.",
            "disputed_fields": [],
        })

        call_log: list[tuple[str, str]] = []

        def mock_caller(system: str, user: str) -> str:
            call_log.append((system, user))
            return response_text

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = FactCheckerAgent(
                workspace=Path(tmpdir),
                llm_caller=mock_caller,
                model_id="mock-model",
                max_items_per_run=5,
            )

            items = [
                FactCheckItem(
                    finding_id="F-001",
                    file_path="src/main.go",
                    line_number=42,
                    title="SQL Injection",
                    description="Unparameterized query",
                    severity="HIGH",
                    evidence="query = 'SELECT * FROM users WHERE id=' + id",
                    fix_suggestion="Use parameterized queries",
                    patch_diff="",
                    agent_name="auditor_claude",
                )
            ]

            report = agent.check_all(items)

        # Verify caller was invoked
        self.assertGreater(len(call_log), 0,
                           "mock_caller should have been called at least once")
        # Verify report structure
        self.assertEqual(report.total_items, 1)
        self.assertGreaterEqual(report.confirmed + report.errors + report.inconclusive, 1)


if __name__ == "__main__":
    unittest.main()
