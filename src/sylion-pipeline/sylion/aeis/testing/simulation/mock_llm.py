"""Deterministic mock LLM for W14 simulation sandboxes.

The mock provider implements a small subset of the production
``LLMAdapter`` surface (``complete(prompt, **kwargs)``) but never reaches
out to Anthropic, OpenAI, Ollama, or any other provider. Responses come
from one of two sources:

    1. Explicit fixtures: ``MockLLM(fixtures={prompt: response})``.
    2. Deterministic stub: a SHA256-derived placeholder so the same
       prompt always yields the same response across runs (Python's
       built-in ``hash()`` is randomized by ``PYTHONHASHSEED`` and
       therefore unsuitable here — see ``_stub_response`` below).

A ``recorded_replay`` mode lets a fixture provider feed in a list of
``(prompt, response)`` pairs that get consumed in order; if more
prompts arrive than were recorded, the stub fallback kicks in.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Any, Iterable

log = logging.getLogger("sylion.aeis.testing.simulation.mock_llm")


def _stub_response(prompt: str) -> str:
    """Return a stable SHA256-prefixed placeholder for an unmatched prompt."""
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return f"[STUB:{digest[:8]}]"


class MockLLM:
    """Deterministic LLM stub for sandbox use.

    Parameters
    ----------
    fixtures:
        Mapping of prompt (exact string) -> response. Lookups are exact;
        case and whitespace matter.
    recorded_replay:
        Optional ordered list of ``(prompt, response)`` pairs. When a
        prompt is queried, the next pair whose prompt matches (or the
        next pair when ``ordered_match=False``) is consumed.
    ordered_match:
        If True (default), ``recorded_replay`` is consumed in order
        regardless of the prompt — useful for trace-replay scenarios.
        If False, the first pair whose prompt equals the query is
        consumed.
    """

    def __init__(
        self,
        fixtures: dict[str, str] | None = None,
        recorded_replay: Iterable[tuple[str, str]] | None = None,
        ordered_match: bool = True,
    ) -> None:
        self.fixtures: dict[str, str] = dict(fixtures or {})
        self._replay: list[tuple[str, str]] = list(recorded_replay or [])
        self._ordered = bool(ordered_match)
        self._call_log: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Provider surface
    # ------------------------------------------------------------------

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """Return a response for the given prompt. Never network-calls."""
        with self._lock:
            self._call_log.append({
                "prompt": prompt[:200],
                "kwargs": {k: v for k, v in kwargs.items() if isinstance(v, (str, int, float, bool))},
                "ts": time.time(),
            })

            # 1) Recorded replay first (most specific)
            if self._replay:
                if self._ordered:
                    p, r = self._replay.pop(0)
                    return r
                for i, (p, r) in enumerate(self._replay):
                    if p == prompt:
                        del self._replay[i]
                        return r

            # 2) Static fixtures
            if prompt in self.fixtures:
                return self.fixtures[prompt]

        # 3) Deterministic stub
        return _stub_response(prompt)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    @property
    def call_log(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._call_log)

    def call_count(self) -> int:
        return len(self.call_log)

    def reset(self) -> None:
        with self._lock:
            self._call_log.clear()


__all__ = ["MockLLM", "_stub_response"]
