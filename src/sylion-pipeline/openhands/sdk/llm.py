"""
openhands.sdk.llm shim — content_to_str helper.
"""
from typing import Any


def content_to_str(content: Any) -> list[str]:
    """
    Normalize LLM message content to a list of strings.

    OpenHands messages can have content as:
      - str: plain text
      - list[dict]: multimodal content blocks [{"type": "text", "text": "..."}]
      - list[str]: already string list
      - None: empty

    Returns list of strings (always).
    """
    if content is None:
        return []

    if isinstance(content, str):
        return [content]

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                # Extract text from content blocks
                text = item.get("text", "")
                if text:
                    parts.append(text)
            else:
                parts.append(str(item))
        return parts

    return [str(content)]
