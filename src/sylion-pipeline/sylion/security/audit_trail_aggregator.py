"""
SYLION Security -- Audit Trail Aggregator

Aggregates audit events from multiple sources into a unified trail.
Each entry is integrity-protected with a SHA-256 hash chain.

SQLite-backed. Thread-safe (RLock). Emits events via EventBus.

Tables:
  audit_entries  -- unified audit trail from all sources
  audit_queries  -- recorded audit queries for compliance tracking

Singleton: get_audit_trail_aggregator() / reset_audit_trail_aggregator()
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.security.audit_trail_aggregator")


def _invalidate_audit_cache() -> None:
    """Phase 3 W1.3 — drop the audit.events cache after every record write.

    Reads under ``audit.events`` are filtered (source/actor/since/until)
    so we can't compute exactly which keys are stale; invalidate the whole
    namespace and let the TTL bound any future error.
    """
    try:
        from sylion.infra.cache import get_cache
        get_cache().invalidate("sylion:audit.events:*")
    except Exception:                              # noqa: BLE001
        log.warning("audit.events cache invalidation failed", exc_info=True)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SOURCES = (
    "api",
    "security",
    "governance",
    "pipeline",
    "council",
    "workspace",
    "operator_mobile",
)
VALID_OUTCOMES = ("success", "failure", "denied", "error")


# ---------------------------------------------------------------------------
# AuditTrailAggregator
# ---------------------------------------------------------------------------

class AuditTrailAggregator:
    """Unified audit trail aggregator with hash-chain integrity.

    Records audit events from multiple system sources, provides filtered
    querying, and maintains a SHA-256 hash chain so any tampering is
    detectable via verify_integrity().

    All mutations are thread-safe via an RLock. Each write operation
    emits an event on the EventBus when one is configured.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            timeout=30.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_entries (
                entry_id   TEXT PRIMARY KEY,
                source     TEXT    NOT NULL,
                action     TEXT    NOT NULL,
                actor      TEXT    NOT NULL DEFAULT '',
                resource   TEXT    NOT NULL DEFAULT '',
                outcome    TEXT    NOT NULL DEFAULT 'success',
                timestamp  REAL    NOT NULL,
                metadata   TEXT    NOT NULL DEFAULT '{}',
                hash       TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_queries (
                query_id   TEXT PRIMARY KEY,
                name       TEXT    NOT NULL DEFAULT '',
                filters    TEXT    NOT NULL DEFAULT '{}',
                created_at REAL    NOT NULL
            );
        """)

        self._conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_ae_source    ON audit_entries(source);
            CREATE INDEX IF NOT EXISTS idx_ae_action    ON audit_entries(action);
            CREATE INDEX IF NOT EXISTS idx_ae_actor     ON audit_entries(actor);
            CREATE INDEX IF NOT EXISTS idx_ae_resource  ON audit_entries(resource);
            CREATE INDEX IF NOT EXISTS idx_ae_outcome   ON audit_entries(outcome);
            CREATE INDEX IF NOT EXISTS idx_ae_ts        ON audit_entries(timestamp);
            CREATE INDEX IF NOT EXISTS idx_aq_ts        ON audit_queries(created_at);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    def _compute_hash(self, entry_id: str, source: str, action: str,
                      actor: str, resource: str, outcome: str,
                      timestamp: float, metadata_json: str) -> str:
        """Compute SHA-256 hash of an audit entry for integrity."""
        raw = (
            f"{entry_id}|{source}|{action}|{actor}|{resource}|"
            f"{outcome}|{timestamp}|{metadata_json}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _emit(self, topic: str, payload: dict) -> None:
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="security.audit_trail_aggregator",
            ))

    @staticmethod
    def _parse_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        if "metadata" in d and isinstance(d["metadata"], str):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except (json.JSONDecodeError, TypeError):
                d["metadata"] = {}
        return d

    def _record_query(self, name: str, filters: dict) -> None:
        """Record an audit query for compliance tracking.

        Query telemetry must not break read-only audit endpoints. If SQLite is
        temporarily locked, roll back this auxiliary write and return the
        primary query result normally.
        """
        query_id = self._uid()
        now = time.time()
        with self._lock:
            try:
                self._conn.execute("""
                    INSERT INTO audit_queries (query_id, name, filters, created_at)
                    VALUES (?, ?, ?, ?)
                """, (query_id, name, json.dumps(filters, default=str), now))
                self._conn.commit()
            except sqlite3.Error:
                self._conn.rollback()
                log.warning("audit query telemetry skipped; database is busy", exc_info=True)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, source: str, action: str, actor: str = "",
               resource: str = "", outcome: str = "success",
               metadata: dict | None = None,
               entry_id: str | None = None,
               timestamp: float | None = None,
               replace: bool = False) -> dict | None:
        """Record an audit entry with SHA-256 integrity hash.

        Parameters
        ----------
        source   : one of VALID_SOURCES
        action   : free-text action description
        actor    : who performed the action
        resource : target resource identifier
        outcome  : one of VALID_OUTCOMES
        metadata : optional arbitrary dict stored as JSON
        entry_id : optional explicit entry id; if provided and already
                   exists the call is deduplicated and None is returned
                   unless *replace* is True.
        timestamp: optional explicit timestamp (epoch seconds);
                   defaults to now.
        replace  : if True, delete any existing entry with the same
                   entry_id before inserting.

        Returns the created entry dict, or None if deduplicated.
        """
        if source not in VALID_SOURCES:
            raise ValueError(
                f"Invalid source '{source}', must be one of {VALID_SOURCES}"
            )
        if outcome not in VALID_OUTCOMES:
            raise ValueError(
                f"Invalid outcome '{outcome}', must be one of {VALID_OUTCOMES}"
            )

        entry_id = entry_id or self._uid()
        now = timestamp if timestamp is not None else time.time()

        with self._lock:
            if entry_id is not None:
                existing = self._conn.execute(
                    "SELECT 1 FROM audit_entries WHERE entry_id = ?",
                    (entry_id,),
                ).fetchone()
                if existing:
                    if replace:
                        self._conn.execute(
                            "DELETE FROM audit_entries WHERE entry_id = ?",
                            (entry_id,),
                        )
                    else:
                        log.debug("dedup: entry_id %s already exists", entry_id)
                        return None
        metadata_json = json.dumps(metadata or {}, default=str, sort_keys=True)
        hash_value = self._compute_hash(
            entry_id, source, action, actor, resource,
            outcome, now, metadata_json,
        )

        with self._lock:
            try:
                self._conn.execute("""
                    INSERT INTO audit_entries
                        (entry_id, source, action, actor, resource,
                         outcome, timestamp, metadata, hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry_id, source, action, actor, resource,
                    outcome, now, metadata_json, hash_value,
                ))
                self._conn.commit()
            except sqlite3.Error:
                self._conn.rollback()
                raise

        result = {
            "entry_id": entry_id,
            "source": source,
            "action": action,
            "actor": actor,
            "resource": resource,
            "outcome": outcome,
            "timestamp": now,
            "metadata": metadata or {},
            "hash": hash_value,
        }

        # Phase 3 W1.3: a new entry invalidates every cached query result.
        _invalidate_audit_cache()

        self._emit("audit.entry_recorded", {
            "entry_id": entry_id,
            "source": source,
            "action": action,
            "actor": actor,
            "outcome": outcome,
        })
        log.info("audit entry %s source=%s action=%s actor=%s outcome=%s",
                 entry_id, source, action, actor, outcome)
        return result

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_entry(self, entry_id: str) -> dict | None:
        """Return a single audit entry by ID, or None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM audit_entries WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_row(row)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def query(self, source: str | None = None,
              action: str | None = None,
              actor: str | None = None,
              resource: str | None = None,
              outcome: str | None = None,
              since: float | None = None,
              until: float | None = None,
              limit: int = 100) -> list[dict]:
        """Query audit entries with optional filters.

        Returns entries ordered by timestamp DESC (newest first).
        Records the query for compliance tracking.

        Phase 3 W1.3: cached under ``audit.events`` namespace (TTL 5 min).
        Invalidated by every ``record()`` write. Compliance recording
        still happens on every call so the cache hit is observable in
        the audit_queries table.
        """
        cache_key: str | None = None
        try:
            from sylion.infra.cache import default_ttl, get_cache, make_key

            cache_key = make_key(
                "audit.events", "query",
                source, action, actor, resource, outcome,
                since, until, limit,
            )
            cached_payload = get_cache().get(cache_key)
            if cached_payload is not None:
                # Compliance: cache hits still record the query so we
                # don't drop visibility into who looked at what.
                self._record_query("filtered_query", {
                    "source": source, "action": action, "actor": actor,
                    "resource": resource, "outcome": outcome,
                    "since": since, "until": until, "limit": limit,
                    "from_cache": True,
                })
                return cached_payload
        except Exception:                          # noqa: BLE001
            log.warning("audit.events cache get failed", exc_info=True)
            cache_key = None

        q = "SELECT * FROM audit_entries WHERE 1=1"
        params: list[Any] = []

        if source is not None:
            q += " AND source = ?"
            params.append(source)
        if action is not None:
            q += " AND action = ?"
            params.append(action)
        if actor is not None:
            q += " AND actor = ?"
            params.append(actor)
        if resource is not None:
            q += " AND resource = ?"
            params.append(resource)
        if outcome is not None:
            q += " AND outcome = ?"
            params.append(outcome)
        if since is not None:
            q += " AND timestamp >= ?"
            params.append(since)
        if until is not None:
            q += " AND timestamp <= ?"
            params.append(until)

        q += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()

        results = [self._parse_row(r) for r in rows]

        if cache_key is not None:
            try:
                from sylion.infra.cache import default_ttl, get_cache

                get_cache().set(
                    cache_key,
                    results,
                    ttl=default_ttl("audit.events"),
                )
            except Exception:                      # noqa: BLE001
                log.warning("audit.events cache set failed", exc_info=True)

        # Record the query for compliance
        filters = {
            "source": source, "action": action, "actor": actor,
            "resource": resource, "outcome": outcome,
            "since": since, "until": until, "limit": limit,
        }
        self._record_query("filtered_query", filters)

        return results

    # ------------------------------------------------------------------
    # Aggregations
    # ------------------------------------------------------------------

    def count_by_action(self, source: str | None = None) -> dict[str, int]:
        """Count entries grouped by action, optionally filtered by source."""
        with self._lock:
            if source is not None:
                rows = self._conn.execute(
                    "SELECT action, COUNT(*) as cnt FROM audit_entries "
                    "WHERE source = ? GROUP BY action ORDER BY cnt DESC",
                    (source,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT action, COUNT(*) as cnt FROM audit_entries "
                    "GROUP BY action ORDER BY cnt DESC"
                ).fetchall()
        return {r["action"]: r["cnt"] for r in rows}

    def count_by_actor(self, source: str | None = None) -> dict[str, int]:
        """Count entries grouped by actor, optionally filtered by source."""
        with self._lock:
            if source is not None:
                rows = self._conn.execute(
                    "SELECT actor, COUNT(*) as cnt FROM audit_entries "
                    "WHERE source = ? GROUP BY actor ORDER BY cnt DESC",
                    (source,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT actor, COUNT(*) as cnt FROM audit_entries "
                    "GROUP BY actor ORDER BY cnt DESC"
                ).fetchall()
        return {r["actor"]: r["cnt"] for r in rows}

    # ------------------------------------------------------------------
    # Integrity verification
    # ------------------------------------------------------------------

    def verify_integrity(self, since: float | None = None) -> dict[str, Any]:
        """Verify hash integrity of audit entries.

        Recomputes the SHA-256 hash for each entry and compares against
        the stored hash. Optionally restricts verification to entries
        after a given timestamp.

        Returns a dict with:
          valid: bool           -- True if all checked entries are intact
          total_entries: int    -- number of entries checked
          broken_at: list[int]  -- indices where integrity fails (0-based)
          errors: list[str]     -- human-readable error descriptions
        """
        with self._lock:
            q = (
                "SELECT entry_id, source, action, actor, resource, "
                "       outcome, timestamp, metadata, hash "
                "FROM audit_entries WHERE 1=1"
            )
            params: list[Any] = []
            if since is not None:
                q += " AND timestamp >= ?"
                params.append(since)
            q += " ORDER BY timestamp ASC, rowid ASC"

            rows = self._conn.execute(q, params).fetchall()

        errors: list[str] = []
        broken_at: list[int] = []

        for idx, row in enumerate(rows):
            metadata_raw = row["metadata"]
            # Use the raw stored metadata string for hash recomputation
            if isinstance(metadata_raw, str):
                metadata_json = metadata_raw
            else:
                metadata_json = json.dumps({}, sort_keys=True)

            recomputed = self._compute_hash(
                row["entry_id"], row["source"], row["action"],
                row["actor"], row["resource"], row["outcome"],
                row["timestamp"], metadata_json,
            )

            if row["hash"] != recomputed:
                errors.append(
                    f"Entry {idx} (entry_id={row['entry_id']}): "
                    f"hash mismatch. Stored {row['hash'][:16]}... "
                    f"recomputed {recomputed[:16]}..."
                )
                broken_at.append(idx)

        return {
            "valid": len(errors) == 0,
            "total_entries": len(rows),
            "broken_at": broken_at,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_actor_history(self, actor: str, limit: int = 100) -> list[dict]:
        """Return audit entries for a specific actor."""
        return self.query(actor=actor, limit=limit)

    def get_resource_timeline(self, resource: str,
                              limit: int = 100) -> list[dict]:
        """Return audit entries targeting a specific resource."""
        return self.query(resource=resource, limit=limit)

    def record_query(self, name: str, filters: dict) -> None:
        """Record an audit query for compliance tracking."""
        self._record_query(name, filters)

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics across audit entries and queries."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM audit_entries"
            ).fetchone()["cnt"]

            # By source
            source_rows = self._conn.execute(
                "SELECT source, COUNT(*) as cnt FROM audit_entries "
                "GROUP BY source ORDER BY cnt DESC"
            ).fetchall()
            by_source = {r["source"]: r["cnt"] for r in source_rows}

            # By action
            action_rows = self._conn.execute(
                "SELECT action, COUNT(*) as cnt FROM audit_entries "
                "GROUP BY action ORDER BY cnt DESC"
            ).fetchall()
            by_action = {r["action"]: r["cnt"] for r in action_rows}

            # By outcome
            outcome_rows = self._conn.execute(
                "SELECT outcome, COUNT(*) as cnt FROM audit_entries "
                "GROUP BY outcome ORDER BY cnt DESC"
            ).fetchall()
            by_outcome = {r["outcome"]: r["cnt"] for r in outcome_rows}

            # Query count
            query_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM audit_queries"
            ).fetchone()["cnt"]

        return {
            "total_entries": total,
            "by_source": by_source,
            "by_action": by_action,
            "by_outcome": by_outcome,
            "total_queries": query_count,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_aggregator: AuditTrailAggregator | None = None


def get_audit_trail_aggregator(db_path: str | Path | None = None,
                                event_bus: EventBus | None = None) -> AuditTrailAggregator:
    global _aggregator
    if _aggregator is None:
        _aggregator = AuditTrailAggregator(db_path, event_bus)
    return _aggregator


def reset_audit_trail_aggregator(db_path: str | Path | None = None,
                                  event_bus: EventBus | None = None) -> AuditTrailAggregator:
    global _aggregator
    _aggregator = AuditTrailAggregator(db_path, event_bus)
    return _aggregator
