"""Canonical MemoryPlane write/read service.

All new durable memory writes should flow through this service so every
entry carries project scope, provenance and an Evidence Spine link.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.evidence_spine import EvidenceSpine
from sylion.memory.indexer import Indexer

log = logging.getLogger("sylion.memory.plane")


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, sort_keys=True, default=str)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class MemoryEntry:
    entry_id: str = ""
    content: str = ""
    project_id: str = ""
    evidence_id: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    created_by: str = ""
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.entry_id:
            self.entry_id = f"mem_{uuid.uuid4().hex[:16]}"
        if not self.created_at:
            self.created_at = time.time()
        if not self.content_hash and self.content:
            self.content_hash = _content_hash(self.content)


class MemoryPlane:
    """Single write source for project-scoped memory entries."""

    def __init__(
        self,
        *,
        db_path: str | Path | None = None,
        event_bus: EventBus | None = None,
        evidence_spine: EvidenceSpine | None = None,
        indexer: Indexer | None = None,
    ) -> None:
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._evidence_spine = evidence_spine or EvidenceSpine(db_path=db_path)
        self._indexer = indexer or Indexer(event_bus=event_bus, db_path=db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_entries (
                entry_id     TEXT PRIMARY KEY,
                content      TEXT NOT NULL,
                project_id   TEXT NOT NULL DEFAULT '',
                evidence_id  TEXT NOT NULL,
                provenance   TEXT NOT NULL DEFAULT '{}',
                metadata     TEXT NOT NULL DEFAULT '{}',
                content_hash TEXT NOT NULL,
                created_by   TEXT NOT NULL DEFAULT '',
                created_at   REAL NOT NULL
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_entries_project ON memory_entries(project_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_entries_evidence ON memory_entries(evidence_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_entries_created ON memory_entries(created_at)")
        self._conn.commit()

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="memory.plane",
            ))

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["provenance"] = _json_loads(item.get("provenance"), {})
        item["metadata"] = _json_loads(item.get("metadata"), {})
        return item

    @staticmethod
    def _validate_write(content: str, provenance: dict[str, Any]) -> None:
        if not content.strip():
            raise ValueError("memory content is required")
        if not provenance or not str(provenance.get("source") or "").strip():
            raise ValueError("memory provenance.source is required")

    def _ensure_evidence_id(
        self,
        entry: MemoryEntry,
        *,
        retention_policy: str,
    ) -> str:
        if entry.evidence_id:
            return entry.evidence_id

        artifact = self._evidence_spine.register_json_artifact(
            {
                "entry_id": entry.entry_id,
                "project_id": entry.project_id,
                "content_hash": entry.content_hash,
                "provenance": entry.provenance,
                "metadata": entry.metadata,
            },
            source="memory_plane",
            artifact_type="memory_entry",
            retention_policy=retention_policy,
            actor_id=entry.created_by,
        )
        return str(artifact["evidence_id"])

    def write(
        self,
        *,
        content: str,
        provenance: dict[str, Any],
        project_id: str = "",
        evidence_id: str = "",
        created_by: str = "",
        metadata: dict[str, Any] | None = None,
        retention_policy: str = "memory-plane",
    ) -> dict[str, Any]:
        """Write one memory entry, register evidence if needed and index it."""
        self._validate_write(content, provenance)
        entry = MemoryEntry(
            content=content,
            project_id=project_id or "",
            evidence_id=evidence_id or "",
            provenance=provenance,
            metadata=metadata or {},
            created_by=created_by or "",
        )
        entry.evidence_id = self._ensure_evidence_id(entry, retention_policy=retention_policy)

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO memory_entries
                (entry_id, content, project_id, evidence_id, provenance, metadata,
                 content_hash, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    entry.content,
                    entry.project_id,
                    entry.evidence_id,
                    _json_dumps(entry.provenance),
                    _json_dumps(entry.metadata),
                    entry.content_hash,
                    entry.created_by,
                    entry.created_at,
                ),
            )
            self._conn.commit()

        self._indexer.index_section(
            entry.entry_id,
            f"memory:{entry.project_id or 'global'}:{entry.entry_id}",
            entry.content,
            project_id=entry.project_id,
        )
        self._emit("memory.entry_written", {
            "entry_id": entry.entry_id,
            "project_id": entry.project_id,
            "evidence_id": entry.evidence_id,
            "content_hash": entry.content_hash,
        })
        log.info("memory entry %s written for project=%s", entry.entry_id, entry.project_id or "global")
        return self.get(entry.entry_id) or {}

    def get(self, entry_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM memory_entries WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def list_project(self, project_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM memory_entries WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def search(self, query: str, *, limit: int = 10, project_id: str | None = None) -> list[dict[str, Any]]:
        hits = self._indexer.search(query, limit=limit, project_id=project_id)
        results: list[dict[str, Any]] = []
        for hit in hits:
            entry = self.get(str(hit.get("section_id") or ""))
            if not entry:
                continue
            entry["score"] = hit.get("score", 0)
            entry["title"] = hit.get("title", "")
            results.append(entry)
        return results[:limit]

    def stats(self) -> dict[str, Any]:
        total = self._conn.execute("SELECT COUNT(*) AS cnt FROM memory_entries").fetchone()["cnt"]
        project_rows = self._conn.execute(
            "SELECT project_id, COUNT(*) AS cnt FROM memory_entries GROUP BY project_id"
        ).fetchall()
        return {
            "total_entries": total,
            "by_project": {row["project_id"]: row["cnt"] for row in project_rows},
        }


_plane: MemoryPlane | None = None


def get_memory_plane(
    *,
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
    evidence_spine: EvidenceSpine | None = None,
    indexer: Indexer | None = None,
) -> MemoryPlane:
    global _plane
    if _plane is None:
        _plane = MemoryPlane(
            db_path=db_path,
            event_bus=event_bus,
            evidence_spine=evidence_spine,
            indexer=indexer,
        )
    return _plane


def reset_memory_plane() -> None:
    global _plane
    _plane = None


def write(**kwargs: Any) -> dict[str, Any]:
    return get_memory_plane().write(**kwargs)


def search(query: str, *, limit: int = 10, project_id: str | None = None) -> list[dict[str, Any]]:
    return get_memory_plane().search(query, limit=limit, project_id=project_id)
