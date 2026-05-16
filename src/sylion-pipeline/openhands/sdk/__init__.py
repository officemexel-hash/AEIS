"""
openhands.sdk shim — core classes used by SYLION pipeline.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Workaround for litellm >=1.67.4 enterprise module bug
# See: https://github.com/BerriAI/litellm/issues/10349
# Some versions import enterprise.enterprise_hooks which is a paid module.
# We inject a stub module so the import doesn't crash.
import types as _types
import sys as _sys

if "enterprise" not in _sys.modules:
    _enterprise = _types.ModuleType("enterprise")
    _enterprise.__path__ = []  # type: ignore[attr-defined]
    _sys.modules["enterprise"] = _enterprise

    _hooks = _types.ModuleType("enterprise.enterprise_hooks")
    _hooks.__path__ = []  # type: ignore[attr-defined]
    _sys.modules["enterprise.enterprise_hooks"] = _hooks

    # Provide defensive stub classes (Council fix Z3: __getattr__-based to prevent AttributeError)
    # If litellm calls any method on these stubs, they silently return None instead of crashing.
    _session = _types.ModuleType("enterprise.enterprise_hooks.session_handler")

    class _StubSessionHandler:
        """No-op stub for enterprise ChatCompletionSession.
        Uses __getattr__ to absorb any method call (Council fix — Opus+Gemini+Sonnet 3/4).
        TODO: remove when litellm >1.70 fixes enterprise import (BerriAI/litellm#10349).
        """
        def __getattr__(self, name):
            return lambda *a, **kw: None

    _session.ChatCompletionSession = _StubSessionHandler  # type: ignore[attr-defined]
    _session._ENTERPRISE_ResponsesSessionHandler = _StubSessionHandler  # type: ignore[attr-defined]
    _sys.modules["enterprise.enterprise_hooks.session_handler"] = _session

    # Also stub enterprise_callbacks.send_emails.base_email (litellm proxy)
    _callbacks = _types.ModuleType("enterprise.enterprise_callbacks")
    _callbacks.__path__ = []  # type: ignore[attr-defined]
    _sys.modules["enterprise.enterprise_callbacks"] = _callbacks

    _emails = _types.ModuleType("enterprise.enterprise_callbacks.send_emails")
    _emails.__path__ = []  # type: ignore[attr-defined]
    _sys.modules["enterprise.enterprise_callbacks.send_emails"] = _emails

    _base_email = _types.ModuleType("enterprise.enterprise_callbacks.send_emails.base_email")

    class _StubEmailLogger:
        """No-op stub for enterprise BaseEmailLogger."""
        def __getattr__(self, name):
            return lambda *a, **kw: None

    _base_email.BaseEmailLogger = _StubEmailLogger  # type: ignore[attr-defined]
    _sys.modules["enterprise.enterprise_callbacks.send_emails.base_email"] = _base_email

# B-009 v6.2.0: enforce offline-safe defaults BEFORE importing litellm.
# These env vars must be set pre-import because litellm reads them at module load time.
import os as _os  # noqa: E402  (needed before third-party import)
_os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")   # no remote cost_map fetch
_os.environ.setdefault("LITELLM_DO_NOT_TRACK", "True")            # disable telemetry
_os.environ.setdefault("LITELLM_LOG", _os.environ.get("LITELLM_LOG", "ERROR"))
_os.environ.setdefault("LITELLM_TELEMETRY", "False")
_os.environ.setdefault("NO_DOCS", "True")

import litellm

# B-009 v6.2.0: post-import belt-and-suspenders — force offline flags on the
# already-imported module in case env was not honoured or litellm cached a
# different value on first read.
try:
    litellm.telemetry = False
    litellm.suppress_debug_info = True
    if hasattr(litellm, "set_verbose"):
        try:
            litellm.set_verbose = False
        except Exception:
            pass
except Exception as _exc:  # pragma: no cover — defensive
    logging.getLogger("openhands.shim").debug("B-009: litellm flag patch failed: %s", _exc)

log = logging.getLogger("openhands.shim")


# ---------------------------------------------------------------------------
# Tool / Skill / AgentContext — lightweight data containers
# ---------------------------------------------------------------------------

@dataclass
class Tool:
    """Reference to a named tool capability."""
    name: str


@dataclass
class Skill:
    """Agent skill definition — holds system prompt content."""
    name: str
    content: str = ""
    trigger: Optional[str] = None


@dataclass
class AgentContext:
    """Context injected into an Agent — skills + system suffix."""
    skills: list[Skill] = field(default_factory=list)
    system_message_suffix: str = ""


# ---------------------------------------------------------------------------
# Agent — container for LLM + tools + context
# ---------------------------------------------------------------------------

@dataclass
class Agent:
    """Agent definition — combines LLM, tools, and context into a runnable unit."""
    llm: Any = None  # LLM instance
    tools: list[Tool] = field(default_factory=list)
    tool_concurrency_limit: int = 4
    agent_context: Optional[AgentContext] = None

    @property
    def system_prompt(self) -> str:
        """Build full system prompt from skills + suffix."""
        parts = []
        if self.agent_context:
            for skill in self.agent_context.skills:
                if skill.content:
                    parts.append(skill.content)
            if self.agent_context.system_message_suffix:
                parts.append(self.agent_context.system_message_suffix)
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# LLM — wraps litellm.completion
# ---------------------------------------------------------------------------

class LLM:
    """
    LLM wrapper using litellm as backend.

    API-compatible with openhands.sdk.LLM:
      LLM(model=..., api_key=..., base_url=..., usage_id=...)
    """
    def __init__(
        self,
        model: str,
        api_key: Any = None,
        base_url: Optional[str] = None,
        usage_id: Optional[str] = None,
    ):
        self.model = model
        # Handle SecretStr, plain string, or None.
        # FIX PIPELINE-007: str(SecretStr) returns '**********' — MUST call
        # get_secret_value() to retrieve actual secret. Prior code passed the
        # literal string '**********' to litellm causing every LLM call to
        # fail with `authentication_error: invalid x-api-key`, silently
        # masking correct keys stored in DB/env.
        if api_key is None:
            self._api_key = None
        elif hasattr(api_key, 'get_secret_value'):
            self._api_key = api_key.get_secret_value()
        else:
            self._api_key = str(api_key)
        self.base_url = base_url
        self.usage_id = usage_id or model

        # Track cumulative usage
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost = 0.0

    def completion(self, messages: list[dict], **kwargs) -> Any:
        """Call litellm.completion with this LLM's config (synchronous).

        PIPELINE-012 NOTE: Prefer `completion_async()` from async callers so
        that cancellation actually aborts the HTTP call. `completion()` runs
        in a thread via run_in_executor — cancelling the coroutine does NOT
        abort the underlying HTTP request, which keeps burning tokens/$.
        """
        call_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if self._api_key:
            call_kwargs["api_key"] = self._api_key
        if self.base_url:
            call_kwargs["base_url"] = self.base_url
        call_kwargs.update(kwargs)

        response = litellm.completion(**call_kwargs)

        # Track usage
        usage = getattr(response, "usage", None)
        if usage:
            self._total_input_tokens += getattr(usage, "prompt_tokens", 0)
            self._total_output_tokens += getattr(usage, "completion_tokens", 0)
            # litellm can compute cost
            try:
                cost = litellm.completion_cost(response)
                self._total_cost += cost
            except Exception:
                pass

        return response

    async def completion_async(self, messages: list[dict], **kwargs) -> Any:
        """PIPELINE-012 v6.2.0: Async variant using litellm.acompletion.

        When the calling coroutine is cancelled (asyncio.CancelledError),
        litellm.acompletion closes the underlying httpx stream, which ACTUALLY
        aborts the HTTP request and stops token consumption. This is the
        correct path for pipeline stage runners that may be cancelled.

        The sync `completion()` method is kept for backward compatibility but
        must NOT be used from coroutines that can be cancelled.
        """
        import litellm as _litellm  # re-resolve to honour monkeypatches in tests
        call_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if self._api_key:
            call_kwargs["api_key"] = self._api_key
        if self.base_url:
            call_kwargs["base_url"] = self.base_url
        call_kwargs.update(kwargs)

        # acompletion propagates CancelledError to httpx, which closes the stream.
        response = await _litellm.acompletion(**call_kwargs)

        usage = getattr(response, "usage", None)
        if usage:
            self._total_input_tokens += getattr(usage, "prompt_tokens", 0)
            self._total_output_tokens += getattr(usage, "completion_tokens", 0)
            try:
                cost = _litellm.completion_cost(response)
                self._total_cost += cost
            except Exception:
                pass

        return response


# ---------------------------------------------------------------------------
# STAGE1-001 v6.2.0: JSON coercion helper
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_JSON_OBJ_RE = re.compile(r"(\{.*\})", re.DOTALL)


def _coerce_to_json_string(text: str) -> str:
    """Best-effort coercion of a model reply to a JSON object string.

    Order of attempts:
      1. If text is already valid JSON — return as-is.
      2. Strip ```json fences and try again.
      3. Extract first {...} balanced block and try again.
      4. If all fail — return a fallback JSON with the raw text inside.

    STAGE1-001: this is the robustness layer. Even if the provider ignores
    ``response_format``, downstream parsers see valid JSON.
    """
    if not text:
        return '{"requirements": []}'
    stripped = text.strip()
    # 1. Already JSON?
    try:
        json.loads(stripped)
        return stripped
    except Exception:
        pass
    # 2. Strip fences
    m = _JSON_FENCE_RE.search(stripped)
    if m:
        inner = m.group(1).strip()
        try:
            json.loads(inner)
            return inner
        except Exception:
            pass
    # 3. Extract first { ... } greedy
    m = _JSON_OBJ_RE.search(stripped)
    if m:
        candidate = m.group(1)
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass
    # 4. Fallback — wrap raw text so downstream never crashes
    fallback = {"requirements": [], "_raw": stripped[:2000], "_parse_failed": True}
    return json.dumps(fallback)


# ---------------------------------------------------------------------------
# Metrics containers (mimic openhands conversation_stats)
# ---------------------------------------------------------------------------

@dataclass
class CombinedMetrics:
    """Metrics container compatible with conv.conversation_stats.get_combined_metrics()."""
    accumulated_cost: float = 0.0
    accumulated_input_tokens: int = 0
    accumulated_output_tokens: int = 0


class ConversationStats:
    """Tracks conversation metrics."""
    def __init__(self):
        self._cost = 0.0
        self._input_tokens = 0
        self._output_tokens = 0

    def get_combined_metrics(self) -> CombinedMetrics:
        return CombinedMetrics(
            accumulated_cost=self._cost,
            accumulated_input_tokens=self._input_tokens,
            accumulated_output_tokens=self._output_tokens,
        )


# ---------------------------------------------------------------------------
# Event / State (for conv.state.events iteration)
# ---------------------------------------------------------------------------

@dataclass
class LLMMessage:
    """Represents LLM message content in an event."""
    content: Any = ""  # str or list


@dataclass
class ConversationEvent:
    """Single event in conversation history."""
    llm_message: Optional[LLMMessage] = None
    role: str = "assistant"


class ConversationState:
    """Holds conversation event history."""
    def __init__(self):
        self.events: list[ConversationEvent] = []


# ---------------------------------------------------------------------------
# DelegationVisualizer — no-op (only used for terminal output decoration)
# ---------------------------------------------------------------------------

class _DelegationVisualizerStub:
    """No-op visualizer stub — imported via openhands.tools.delegate."""
    def __init__(self, name: str = ""):
        self.name = name


# ---------------------------------------------------------------------------
# Conversation — the core runner
# ---------------------------------------------------------------------------

class Conversation:
    """
    Runs an agent on a task by calling the LLM with the agent's system prompt.

    Compatible with openhands Conversation API:
      conv = Conversation(agent=..., workspace=..., visualizer=...)
      conv.send_message(task)
      conv.run()
      cost = conv.conversation_stats.get_combined_metrics().accumulated_cost
    """
    def __init__(
        self,
        agent: Agent,
        workspace: str = ".",
        visualizer: Any = None,
    ):
        self.agent = agent
        self.workspace = Path(workspace)
        self.visualizer = visualizer
        self.conversation_stats = ConversationStats()
        self.state = ConversationState()
        self._pending_message: Optional[str] = None
        self._messages: list[dict] = []

    def send_message(self, task: str) -> None:
        """Queue a user message for the next run()."""
        self._pending_message = task

    # ------------------------------------------------------------------
    # T-04: file-save helpers
    # ------------------------------------------------------------------

    # Patterns to detect save instructions in task text (PL + EN)
    _SAVE_RESULT_PATTERNS = [
        re.compile(r"Zapisz wynik w:\s*([^\s\n]+)"),
        re.compile(r"Save result to:\s*([^\s\n]+)"),
    ]
    _SIGNAL_FILE_PATTERNS = [
        re.compile(r"Po zako\u0144czeniu utw\u00f3rz:\s*([^\s\n]+)"),
        re.compile(r"On completion create:\s*([^\s\n]+)"),
    ]

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Remove leading/trailing markdown code fences (```json ... ```)."""
        text = text.strip()
        # Remove opening fence (```json, ```python, ``` etc.)
        text = re.sub(r"^```[^\n]*\n", "", text)
        # Remove closing fence
        text = re.sub(r"\n```\s*$", "", text)
        return text.strip()

    def _save_result_file(self, path_str: str, content: str, conv_id: str) -> None:
        """T-04: Save assistant content to a file; handles JSON and raw text."""
        path = Path(path_str)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            log.error("T-04: cannot create directory %s: %s", path.parent, e)
            return

        stripped = self._strip_markdown_fences(content)
        try:
            parsed = json.loads(stripped)
            path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            log.info("T-04: saved JSON result → %s", path)
        except (json.JSONDecodeError, ValueError) as json_err:
            # Save raw text
            raw_path = path.with_suffix(".raw.txt")
            raw_path.write_text(content, encoding="utf-8")
            # Save error sidecar
            err_path = path.with_name(path.name + ".error")
            err_path.write_text(
                json.dumps({"error": str(json_err), "path": str(path)}),
                encoding="utf-8",
            )
            log.warning("T-04: JSON parse failed for %s — saved raw to %s", path, raw_path)

    def _save_signal_file(self, path_str: str, conv_id: str) -> None:
        """T-04: Save a completion signal file with status/timestamp/conversation_id."""
        path = Path(path_str)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            log.error("T-04: cannot create directory for signal %s: %s", path, e)
            return

        payload = {
            "status": "done",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "conversation_id": conv_id,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        log.info("T-04: saved signal file → %s", path)

    def _process_file_instructions(self, task_text: str, assistant_content: str) -> None:
        """T-04: Parse task_text for save/signal patterns and write files."""
        conv_id = getattr(self, "_conversation_id", "unknown")

        for pattern in self._SAVE_RESULT_PATTERNS:
            for match in pattern.finditer(task_text):
                path_str = match.group(1).strip()
                self._save_result_file(path_str, assistant_content, conv_id)

        for pattern in self._SIGNAL_FILE_PATTERNS:
            for match in pattern.finditer(task_text):
                path_str = match.group(1).strip()
                self._save_signal_file(path_str, conv_id)

    # ------------------------------------------------------------------
    # run()
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Execute the conversation: send task to LLM, collect response."""
        if not self.agent or not self.agent.llm:
            log.warning("Conversation.run() called without agent/LLM — skipping")
            return

        llm: LLM = self.agent.llm
        system_prompt = self.agent.system_prompt

        # Capture task text before clearing _pending_message
        task_text = self._pending_message or ""

        # Build messages
        if system_prompt:
            self._messages = [{"role": "system", "content": system_prompt}]
        else:
            self._messages = []

        if self._pending_message:
            self._messages.append({"role": "user", "content": self._pending_message})
            self._pending_message = None

        try:
            response = llm.completion(self._messages)

            # Extract assistant message
            choice = response.choices[0] if response.choices else None
            assistant_content = ""
            if choice and choice.message:
                assistant_content = choice.message.content or ""

            # T-04: parse task for file-save instructions and act on them
            if task_text and assistant_content:
                self._process_file_instructions(task_text, assistant_content)

            # Record event
            event = ConversationEvent(
                llm_message=LLMMessage(content=assistant_content),
                role="assistant",
            )
            self.state.events.append(event)

            # Update stats
            usage = getattr(response, "usage", None)
            if usage:
                self.conversation_stats._input_tokens += getattr(usage, "prompt_tokens", 0)
                self.conversation_stats._output_tokens += getattr(usage, "completion_tokens", 0)
            self.conversation_stats._cost = llm._total_cost

        except Exception as e:
            log.error(f"Conversation.run() failed: {e}")
            # Record error as event so orchestrator can inspect
            event = ConversationEvent(
                llm_message=LLMMessage(content=f"[ERROR] {e}"),
                role="system",
            )
            self.state.events.append(event)

    async def run_async(self) -> None:
        """PIPELINE-012 v6.2.0: Async conversation runner.

        Uses ``LLM.completion_async`` (litellm.acompletion) so that when the
        outer coroutine is cancelled, the HTTP call is actually aborted and
        tokens stop being consumed. Behaviour is otherwise identical to run().
        """
        if not self.agent or not self.agent.llm:
            log.warning("Conversation.run_async() called without agent/LLM — skipping")
            return

        llm: LLM = self.agent.llm
        system_prompt = self.agent.system_prompt
        task_text = self._pending_message or ""

        if system_prompt:
            self._messages = [{"role": "system", "content": system_prompt}]
        else:
            self._messages = []

        if self._pending_message:
            self._messages.append({"role": "user", "content": self._pending_message})
            self._pending_message = None

        # STAGE1-001 v6.2.0: strict JSON mode when agent requests it.
        # Providers that support it: openai, deepseek, anthropic (via tools).
        llm_kwargs: dict[str, Any] = {}
        strict_json = bool(getattr(self.agent, "_strict_json", False))
        if strict_json:
            model_name = (getattr(llm, "model", "") or "").lower()
            # Only pass response_format for providers that support it.
            if any(tag in model_name for tag in (
                "gpt-4", "gpt-3.5", "gpt-5", "deepseek", "qwen", "glm"
            )):
                llm_kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await llm.completion_async(self._messages, **llm_kwargs)

            choice = response.choices[0] if response.choices else None
            assistant_content = ""
            if choice and choice.message:
                assistant_content = choice.message.content or ""

            # STAGE1-001 fallback parser: strip ```json fences, extract first {...}
            if strict_json and assistant_content:
                assistant_content = _coerce_to_json_string(assistant_content)

            if task_text and assistant_content:
                self._process_file_instructions(task_text, assistant_content)

            event = ConversationEvent(
                llm_message=LLMMessage(content=assistant_content),
                role="assistant",
            )
            self.state.events.append(event)

            usage = getattr(response, "usage", None)
            if usage:
                self.conversation_stats._input_tokens += getattr(usage, "prompt_tokens", 0)
                self.conversation_stats._output_tokens += getattr(usage, "completion_tokens", 0)
            self.conversation_stats._cost = llm._total_cost

        except asyncio.CancelledError:
            # PIPELINE-012: propagate cancellation so litellm.acompletion closes HTTP
            log.warning("Conversation.run_async() cancelled — HTTP call aborted")
            raise
        except Exception as e:
            log.error(f"Conversation.run_async() failed: {e}")
            event = ConversationEvent(
                llm_message=LLMMessage(content=f"[ERROR] {e}"),
                role="system",
            )
            self.state.events.append(event)


# ---------------------------------------------------------------------------
# register_agent — no-op (SYLION doesn't use OpenHands agent registry)
# ---------------------------------------------------------------------------

def register_agent(agent_cls=None, **kwargs):
    """No-op agent registration. SYLION uses agents.yaml instead."""
    def decorator(cls):
        return cls
    if agent_cls is not None:
        return agent_cls
    return decorator
