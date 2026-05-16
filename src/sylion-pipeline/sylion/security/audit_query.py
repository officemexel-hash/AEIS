"""
SYLION Security -- Audit Query (DEPRECATED)

DEPRECATED 2026-04-24 — use security.audit_trail_aggregator
This module is a backward-compatible shim that delegates to
AuditTrailAggregator while preserving the original API.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
import warnings
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus
from sylion.security.audit_trail_aggregator import (
    AuditTrailAggregator,
    get_audit_trail_aggregator,
    reset_audit_trail_aggregator,
)

warnings.warn(
    "audit_query is deprecated; use audit_trail_aggregator",
    DeprecationWarning,
    stacklevel=2,
)

log = logging.getLogger("sylion.security.audit_query")

VALID_SOURCES = ("api", "security", "governance", "pipeline", "council", "workspace")


class AuditQuery:
    """Backward-compatible shim over AuditTrailAggregator.

    Preserves the original AuditQuery API while writing all events
    into the canonical audit trail.
    """

    def __init__(self, db_path: str = ":memory:",
                 event_bus: EventBus | None = None):
        self._db_path = db_path
        self._event_bus = event_bus
        # Each shim instance gets its own aggregator for test isolation.
        self._agg = AuditTrailAggregator(db_path=db_path, event_bus=event_bus)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="security.audit_query",
            ))

    @staticmethod
    def _map_entry(entry: dict | None) -> dict | None:
        if entry is None:
            return None
        meta = entry.get("metadata") or {}
        return {
            "event_id": entry["entry_id"],
            "event_type": meta.get("event_type", entry["action"]),
            "actor": entry["actor"],
            "resource": entry["resource"],
            "timestamp": entry["timestamp"],
            "tags_json": meta.get("tags_json", {}),
        }

    # ------------------------------------------------------------------
    # Index events
    # ------------------------------------------------------------------

    def index_event(self, event_id: str, event_type: str, actor: str,
                    resource: str, timestamp: float,
                    tags_json: dict | None = None) -> dict:
        """Index an audit event for fast querying.

        DEPRECATED — delegates to AuditTrailAggregator.record().
        """
        metadata = {
            "event_type": event_type,
            "tags_json": tags_json or {},
            "original_timestamp": timestamp,
        }
        result = self._agg.record(
            source="api",
            action=event_type,
            actor=actor,
            resource=resource,
            outcome="success",
            metadata=metadata,
            entry_id=event_id,
            timestamp=timestamp,
            replace=True,
        )
        mapped = self._map_entry(result)
        self._emit("event_indexed", {
            "event_id": event_id, "event_type": event_type,
        })
        log.debug("event indexed: %s (%s)", event_id[:12], event_type)
        return mapped  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Query events
    # ------------------------------------------------------------------

    def query_events(self, filters_json: dict | None = None) -> list[dict]:
        """Query indexed events with filter criteria.

        DEPRECATED — delegates to AuditTrailAggregator.query().
        """
        filters = filters_json or {}
        query_id = self._uid()
        now = time.time()

        # Map shim filters to aggregator filters
        source = filters.get("source")
        action = filters.get("event_type")
        actor = filters.get("actor")
        resource = filters.get("resource")
        since = filters.get("since")
        until = filters.get("until")
        limit = filters.get("limit", 100)

        results = self._agg.query(
            source=source,
            action=action,
            actor=actor,
            resource=resource,
            since=since,
            until=until,
            limit=limit,
        )

        mapped = [self._map_entry(r) for r in results]

        # Tag filtering (post-query)
        tag_key = filters.get("tag_key")
        if tag_key:
            tag_value = filters.get("tag_value")
            filtered = []
            for r in mapped:
                tags = r.get("tags_json", {})
                if isinstance(tags, dict) and tag_key in tags:
                    if tag_value is None or tags[tag_key] == tag_value:
                        filtered.append(r)
            mapped = filtered

        self._emit("query_executed", {
            "query_id": query_id,
            "result_count": len(mapped),
        })
        return mapped

    def get_event(self, event_id: str) -> dict | None:
        """Get a single indexed event by ID, or None."""
        entry = self._agg.get_entry(event_id)
        return self._map_entry(entry)

    # ------------------------------------------------------------------
    # Actor / resource queries
    # ------------------------------------------------------------------

    def get_actor_history(self, actor: str,
                          limit: int = 100) -> list[dict]:
        """Get event history for a specific actor."""
        results = self._agg.get_actor_history(actor, limit=limit)
        return [self._map_entry(r) for r in results]

    def get_resource_timeline(self, resource: str,
                              limit: int = 100) -> list[dict]:
        """Get event timeline for a specific resource."""
        results = self._agg.get_resource_timeline(resource, limit=limit)
        return [self._map_entry(r) for r in results]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_query_stats(self) -> dict:
        """Get aggregate statistics for the query index."""
        stats = self._agg.get_stats()
        by_action = stats.get("by_action", {})
        by_actor = self._agg.count_by_actor()
        return {
            "total_events": stats.get("total_entries", 0),
            "events_by_type": by_action,
            "top_actors": dict(list(by_actor.items())[:10]),
            "total_queries": stats.get("total_queries", 0),
        }

    # ------------------------------------------------------------------
    # Purge
    # ------------------------------------------------------------------

    def purge_index(self, older_than_seconds: int) -> int:
        """Purge index entries older than the given number of seconds.

        Returns the number of purged entries.
        """
        cutoff = time.time() - older_than_seconds
        with self._lock:
            # We operate directly on the aggregator's underlying DB
            conn = self._agg._conn
            n = conn.execute(
                "DELETE FROM audit_entries WHERE timestamp < ?",
                (cutoff,),
            ).rowcount
            conn.commit()
        if n > 0:
            log.info("purged %d entries older than %ds", n, older_than_seconds)
        return n


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: AuditQuery | None = None


def get_audit_query(db_path: str = ":memory:",
                    event_bus: EventBus | None = None) -> AuditQuery:
    """Get or create the global AuditQuery singleton."""
    global _instance
    if _instance is None:
        _instance = AuditQuery(db_path, event_bus)
    return _instance


def reset_audit_query() -> None:
    """Reset the global singleton (for testing)."""
    global _instance
    _instance = None
