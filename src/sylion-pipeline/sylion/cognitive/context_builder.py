"""
SYLION Cognitive -- Context Builder

Assembles context from memory sources for processing. Maintains an
ordered list of prioritized content sources and assembles top-priority
content within a character budget.

No database needed; uses in-memory cache.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.cognitive.context_builder")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ContextSource:
    """A single content source for context assembly."""
    source_id: str = ""
    content: str = ""
    priority: int = 0
    added_at: float = 0.0

    def __post_init__(self):
        if not self.source_id:
            self.source_id = uuid.uuid4().hex
        if not self.added_at:
            self.added_at = time.time()


# ---------------------------------------------------------------------------
# Context Builder
# # ---------------------------------------------------------------------------

class ContextBuilder:
    """Assembles context from memory sources for processing.

    Maintains an ordered list of sources sorted by priority (higher first).
    Assembles top-priority content within a character budget.
    Thread-safe. No database needed; in-memory cache.
    """

    def __init__(self, event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._sources: list[ContextSource] = []

    # ------------------------------------------------------------------
    # Source management
    # ------------------------------------------------------------------

    def add_source(self, source_id: str, content: str, priority: int = 0) -> dict:
        """Add a content source. Returns source summary dict."""
        source = ContextSource(
            source_id=source_id,
            content=content,
            priority=priority,
        )

        with self._lock:
            # Remove existing source with same ID if present
            self._sources = [s for s in self._sources if s.source_id != source_id]
            self._sources.append(source)
            # Sort by priority descending, then by added_at ascending
            self._sources.sort(key=lambda s: (-s.priority, s.added_at))

        self._emit("context.source_added", {
            "source_id": source_id,
            "priority": priority,
            "content_length": len(content),
        })
        log.info("added source %s (priority=%d, len=%d)",
                 source_id[:12], priority, len(content))
        return {
            "source_id": source.source_id,
            "priority": priority,
            "content_length": len(content),
        }

    def clear_sources(self) -> dict:
        """Remove all sources. Returns count of cleared sources."""
        with self._lock:
            count = len(self._sources)
            self._sources.clear()

        self._emit("context.cleared", {"sources_cleared": count})
        log.info("cleared %d sources", count)
        return {"sources_cleared": count}

    # ------------------------------------------------------------------
    # Context assembly
    # ------------------------------------------------------------------

    def build_context(self, query: str, max_chars: int = 4000,
                      sources: list | None = None) -> str:
        """Assemble context string from prioritized sources within budget.

        If `sources` is provided, only those source IDs are used.
        Otherwise all registered sources are used.
        Returns assembled context string.
        """
        with self._lock:
            available = list(self._sources)

        # Filter to specific source IDs if provided
        if sources:
            source_set = set(sources)
            available = [s for s in available if s.source_id in source_set]

        # Assemble within budget
        parts: list[str] = []
        total_chars = 0

        for source in available:
            content = source.content
            remaining = max_chars - total_chars

            if remaining <= 0:
                break

            if len(content) <= remaining:
                parts.append(f"[{source.source_id}]\n{content}")
                total_chars += len(content) + len(source.source_id) + 3
            else:
                # Truncate to fit
                truncated = content[:remaining - len(source.source_id) - 6]
                parts.append(f"[{source.source_id}]\n{truncated}...")
                total_chars = max_chars
                break

        context = "\n\n".join(parts)

        self._emit("context.built", {
            "query": query,
            "sources_used": len(parts),
            "total_chars": len(context),
            "max_chars": max_chars,
        })

        log.info("built context for query '%s...': %d chars from %d sources",
                 query[:40], len(context), len(parts))
        return context

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_context_stats(self) -> dict:
        """Get context builder statistics."""
        with self._lock:
            source_count = len(self._sources)
            total_content = sum(len(s.content) for s in self._sources)
            priorities = [s.priority for s in self._sources]

        return {
            "source_count": source_count,
            "total_content_chars": total_content,
            "min_priority": min(priorities) if priorities else 0,
            "max_priority": max(priorities) if priorities else 0,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cognitive.context_builder",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_builder: ContextBuilder | None = None


def get_context_builder(event_bus: EventBus | None = None) -> ContextBuilder:
    global _builder
    if _builder is None:
        _builder = ContextBuilder(event_bus)
    return _builder
