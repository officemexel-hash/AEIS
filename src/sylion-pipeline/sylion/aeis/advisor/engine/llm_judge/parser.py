"""Robust JSON-from-LLM parser.

LLMs occasionally wrap JSON in code fences, prefix with explanation, or emit
trailing commentary. This parser strips the noise and falls back to balanced-
brace extraction, then to safe defaults.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def parse_json_response(text: str, default: Any = None) -> Any:
    if not text:
        return default if default is not None else {}

    candidates = [text]

    fence = _FENCE_RE.search(text)
    if fence:
        candidates.insert(0, fence.group(1).strip())

    span = _balanced_json_span(text)
    if span:
        candidates.insert(0, span)

    for c in candidates:
        try:
            return json.loads(c)
        except (json.JSONDecodeError, TypeError):
            continue
    return default if default is not None else {}


def _balanced_json_span(text: str) -> str | None:
    """Find the largest balanced {...} span (or [...] span if dominant)."""
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start < 0:
            continue
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None
