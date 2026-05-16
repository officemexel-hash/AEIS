"""Focused tests for the AEIS decomposition engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from sylion.aeis.decomposition_engine import (
    UnsupportedPromptError,
    decompose_and_build,
    decompose_prompt,
)
from sylion.cognitive.llm_adapter import LLMCallUnavailableError


class UnavailableLLM:
    def _get_provider(self):
        return "stub"

    def _get_api_key(self, provider: str):
        return ""


class StubPlannerLLM:
    def _get_provider(self):
        return "openai"

    def _get_api_key(self, provider: str):
        return "sk-test"

    def call_messages(self, model_id, messages, max_tokens=1600):
        return {
            "text": """
            {
              "tasks": [
                {
                  "name": "document",
                  "kind": "html_fragment",
                  "signature": "",
                  "body": "<!DOCTYPE html><html><head><style>{{STYLE}}</style></head><body><canvas id='room'></canvas><script>{{SCRIPT}}</script></body></html>",
                  "docstring": "HTML shell"
                },
                {
                  "name": "styles",
                  "kind": "css_fragment",
                  "signature": "",
                  "body": "body { font-family: sans-serif; } canvas { border: 1px solid #333; }",
                  "docstring": "CSS"
                },
                {
                  "name": "logic",
                  "kind": "js_fragment",
                  "signature": "",
                  "body": "const canvas = document.getElementById('room'); const ctx = canvas.getContext('2d');",
                  "docstring": "JS"
                }
              ]
            }
            """,
        }


class FailingPlannerLLM:
    def _get_provider(self):
        return "openai"

    def _get_api_key(self, provider: str):
        return "sk-test"

    def call_messages(self, model_id, messages, max_tokens=1600):
        raise LLMCallUnavailableError("provider failed")


def test_polish_chat_prompt_does_not_fall_back_to_calculator():
    tasks = decompose_prompt("zbuduj prosty komunikator z logowaniem, pokojami i wiadomosciami")
    names = [task.name for task in tasks]
    assert "register_user" in names
    assert "send_message" in names
    assert "add" not in names
    assert any(task.kind == "html_fragment" for task in tasks)


def test_general_prompt_without_live_provider_raises_unsupported():
    with pytest.raises(UnsupportedPromptError):
        decompose_prompt("zbuduj aplikacje do zarzadzania fakturami dla malej firmy", llm_adapter=UnavailableLLM())


def test_stub_llm_decomposes_room_planner_into_html_tasks():
    tasks = decompose_prompt(
        "zbuduj prosty program do projektowania pokoju 2D z przesuwaniem mebli",
        llm_adapter=StubPlannerLLM(),
    )
    kinds = {task.kind for task in tasks}
    names = {task.name for task in tasks}
    assert {"html_fragment", "css_fragment", "js_fragment"}.issubset(kinds)
    assert {"document", "styles", "logic"}.issubset(names)


def test_general_prompt_with_failing_live_provider_raises_unsupported():
    with pytest.raises(UnsupportedPromptError, match="provider failed"):
        decompose_prompt(
            "zbuduj prosty program do projektowania pokoju 2D z przesuwaniem mebli",
            llm_adapter=FailingPlannerLLM(),
        )


def test_decompose_and_build_writes_html_artifact_for_room_planner(tmp_path: Path):
    result = decompose_and_build(
        prompt="zbuduj prosty program do projektowania pokoju 2D z przesuwaniem mebli",
        workers=["host_a"],
        artifact_dir=tmp_path,
        llm_adapter=StubPlannerLLM(),
    )
    assert result.artifact_format == "html"
    assert result.artifact_path is not None
    assert result.artifact_path.endswith(".html")
    assert "canvas" in result.artifact.lower()
