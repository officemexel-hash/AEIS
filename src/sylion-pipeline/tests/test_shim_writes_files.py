"""T-04: Tests for Conversation.run() file-save functionality (openhands/sdk/__init__.py).

Verifies that:
1. Polish pattern "Zapisz wynik w: <path>" triggers JSON save
2. English pattern "Save result to: <path>" triggers JSON save
3. Polish pattern "Po zakończeniu utwórz: <path>" triggers signal file
4. English pattern "On completion create: <path>" triggers signal file
5. Markdown fences are stripped before JSON parse
6. Non-JSON content → .raw.txt + .json.error sidecar
7. Parent directories are created automatically
8. No real LLM calls — fully mocked
"""
from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure pipeline root is on sys.path so openhands/ is importable
# ---------------------------------------------------------------------------
_PIPELINE_ROOT = str(Path(__file__).resolve().parent.parent)
if _PIPELINE_ROOT not in sys.path:
    sys.path.insert(0, _PIPELINE_ROOT)

# ---------------------------------------------------------------------------
# Stub litellm so sdk __init__ imports cleanly
# ---------------------------------------------------------------------------
if "litellm" not in sys.modules:
    _litellm_stub = types.ModuleType("litellm")
    _litellm_stub.completion = lambda *a, **kw: None  # type: ignore[attr-defined]
    _litellm_stub.completion_cost = lambda *a, **kw: 0.0  # type: ignore[attr-defined]
    sys.modules["litellm"] = _litellm_stub


def _make_mock_response(content: str):
    """Build a mock litellm response with the given content string."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = None
    return mock_response


def _make_conversation(task_text: str, llm_response_content: str):
    """Create a Conversation with a mocked LLM returning the given content."""
    from openhands.sdk import Agent, Conversation, LLM, AgentContext, Skill

    mock_llm = MagicMock(spec=LLM)
    mock_llm._total_cost = 0.0
    mock_llm.completion.return_value = _make_mock_response(llm_response_content)

    agent = Agent(llm=mock_llm)
    conv = Conversation(agent=agent, workspace=".")
    conv.send_message(task_text)
    return conv, mock_llm


class TestShimSaveResultJSON(unittest.TestCase):
    """Tests for JSON result-file saving (Zapisz wynik w / Save result to)."""

    def test_polish_save_result_creates_json_file(self):
        """Polish pattern writes valid JSON to the specified path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "results" / "output.json"
            task = f"Analyze code. Zapisz wynik w: {out_path}"
            llm_content = json.dumps({"findings": [{"id": "F-001", "severity": "HIGH"}]})

            conv, _ = _make_conversation(task, llm_content)
            conv.run()

            self.assertTrue(out_path.exists(), f"Expected {out_path} to be created")
            data = json.loads(out_path.read_text())
            self.assertIn("findings", data)
            self.assertEqual(data["findings"][0]["id"], "F-001")

    def test_english_save_result_creates_json_file(self):
        """English pattern writes valid JSON to the specified path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "output.json"
            task = f"Analyze code. Save result to: {out_path}"
            llm_content = json.dumps({"status": "ok", "score": 42})

            conv, _ = _make_conversation(task, llm_content)
            conv.run()

            self.assertTrue(out_path.exists())
            data = json.loads(out_path.read_text())
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["score"], 42)

    def test_markdown_fences_stripped_before_json_parse(self):
        """Markdown code fences are stripped before attempting json.loads."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "output.json"
            task = f"Run audit. Zapisz wynik w: {out_path}"
            llm_content = '```json\n{"result": "clean", "issues": 0}\n```'

            conv, _ = _make_conversation(task, llm_content)
            conv.run()

            self.assertTrue(out_path.exists())
            data = json.loads(out_path.read_text())
            self.assertEqual(data["result"], "clean")
            self.assertEqual(data["issues"], 0)

    def test_non_json_content_creates_raw_txt_and_error_sidecar(self):
        """Non-JSON LLM content creates .raw.txt and .json.error sidecar files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "output.json"
            task = f"Run analysis. Zapisz wynik w: {out_path}"
            llm_content = "This is plain text, not JSON at all."

            conv, _ = _make_conversation(task, llm_content)
            conv.run()

            # JSON file should NOT exist
            self.assertFalse(out_path.exists(),
                             "JSON file should not be created for non-JSON content")
            # Raw text file should exist
            raw_path = out_path.with_suffix(".raw.txt")
            self.assertTrue(raw_path.exists(), f"Expected {raw_path} to exist")
            self.assertEqual(raw_path.read_text(), llm_content)
            # Error sidecar should exist
            err_path = out_path.with_name(out_path.name + ".error")
            self.assertTrue(err_path.exists(), f"Expected {err_path} to exist")
            err_data = json.loads(err_path.read_text())
            self.assertIn("error", err_data)

    def test_parent_directory_created_automatically(self):
        """Parent directory is created even if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "deep" / "nested" / "dir" / "output.json"
            task = f"Run. Save result to: {out_path}"
            llm_content = json.dumps({"ok": True})

            conv, _ = _make_conversation(task, llm_content)
            conv.run()

            self.assertTrue(out_path.parent.exists())
            self.assertTrue(out_path.exists())


class TestShimSignalFile(unittest.TestCase):
    """Tests for signal file creation (Po zakończeniu utwórz / On completion create)."""

    def test_polish_signal_file_created(self):
        """Polish pattern creates signal file with correct JSON payload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            signal_path = Path(tmpdir) / "signals" / "done.json"
            task = f"Do work. Po zakończeniu utwórz: {signal_path}"
            llm_content = json.dumps({"result": "done"})

            conv, _ = _make_conversation(task, llm_content)
            conv.run()

            self.assertTrue(signal_path.exists(), f"Expected {signal_path} to exist")
            data = json.loads(signal_path.read_text())
            self.assertEqual(data["status"], "done")
            self.assertIn("timestamp", data)
            self.assertIn("conversation_id", data)

    def test_english_signal_file_created(self):
        """English pattern creates signal file with correct JSON payload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            signal_path = Path(tmpdir) / "done_signal.json"
            task = f"Process data. On completion create: {signal_path}"
            llm_content = json.dumps({"result": "processed"})

            conv, _ = _make_conversation(task, llm_content)
            conv.run()

            self.assertTrue(signal_path.exists())
            data = json.loads(signal_path.read_text())
            self.assertEqual(data["status"], "done")

    def test_signal_file_parent_dir_created(self):
        """Signal file parent directory is created automatically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            signal_path = Path(tmpdir) / "a" / "b" / "c" / "signal.json"
            task = f"Done. On completion create: {signal_path}"
            llm_content = "{}"

            conv, _ = _make_conversation(task, llm_content)
            conv.run()

            self.assertTrue(signal_path.parent.exists())
            self.assertTrue(signal_path.exists())

    def test_signal_and_result_both_written(self):
        """Both save-result and signal patterns can appear in the same task."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result_path = Path(tmpdir) / "result.json"
            signal_path = Path(tmpdir) / "signal.json"
            task = (
                f"Run. Save result to: {result_path} "
                f"On completion create: {signal_path}"
            )
            llm_content = json.dumps({"data": [1, 2, 3]})

            conv, _ = _make_conversation(task, llm_content)
            conv.run()

            self.assertTrue(result_path.exists(), "Result file should exist")
            self.assertTrue(signal_path.exists(), "Signal file should exist")
            result_data = json.loads(result_path.read_text())
            self.assertEqual(result_data["data"], [1, 2, 3])
            signal_data = json.loads(signal_path.read_text())
            self.assertEqual(signal_data["status"], "done")


class TestShimNoSaveWhenNoPattern(unittest.TestCase):
    """Verify that Conversation.run() does NOT create files when no patterns present."""

    def test_no_files_created_without_pattern(self):
        """If task has no save/signal patterns, no files are created."""
        from openhands.sdk import Agent, Conversation, LLM

        mock_llm = MagicMock(spec=LLM)
        mock_llm._total_cost = 0.0
        mock_llm.completion.return_value = _make_mock_response(
            json.dumps({"result": "clean"})
        )

        agent = Agent(llm=mock_llm)
        conv = Conversation(agent=agent, workspace=".")

        with tempfile.TemporaryDirectory() as tmpdir:
            task = "Run audit and report back what you find."
            conv.send_message(task)
            # Patch _save_result_file to detect unexpected calls
            original_save = conv._save_result_file
            save_calls: list = []
            conv._save_result_file = lambda *a, **kw: save_calls.append(a)  # type: ignore
            conv.run()
            self.assertEqual(len(save_calls), 0,
                             "No _save_result_file calls expected without pattern")


class TestStripMarkdownFences(unittest.TestCase):
    """Unit tests for _strip_markdown_fences helper."""

    def setUp(self):
        from openhands.sdk import Conversation, Agent
        self.conv = Conversation.__new__(Conversation)

    def test_strips_json_fence(self):
        text = '```json\n{"key": "value"}\n```'
        result = self.conv._strip_markdown_fences(text)
        self.assertEqual(result, '{"key": "value"}')

    def test_strips_plain_fence(self):
        text = '```\n{"key": "value"}\n```'
        result = self.conv._strip_markdown_fences(text)
        self.assertEqual(result, '{"key": "value"}')

    def test_no_fence_unchanged(self):
        text = '{"key": "value"}'
        result = self.conv._strip_markdown_fences(text)
        self.assertEqual(result, '{"key": "value"}')

    def test_strips_python_fence(self):
        text = '```python\nprint("hello")\n```'
        result = self.conv._strip_markdown_fences(text)
        self.assertEqual(result, 'print("hello")')


if __name__ == "__main__":
    unittest.main()
