"""
SYLION Core — Evidence Spine

Immutable, append-only audit log with hash chain.
Every D2+ decision leaves a permanent, tamper-evident trace.

Chain: SHA-256(prev_hash | event_id | canonical_json(payload) | timestamp)
Genesis: prev_hash = "0" * 64
Signing: Ed25519 planned (SHA-256 for now).

gRPC planned: AppendEvidence, QueryEvidence, ReplayToCheckpoint
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

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.core.evidence_spine")

GENESIS_PREV_HASH = "0" * 64


@dataclass
class EvidenceEntry:
    entry_id: str = ""
    source_plan: str = ""
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""
    hash: str = ""
    timestamp: float = 0.0
    actor_id: str = ""
    signature: str = ""

    def __post_init__(self):
        if not self.entry_id:
            self.entry_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class EvidenceArtifact:
    evidence_id: str = ""
    source: str = ""
    artifact_type: str = ""
    uri: str = ""
    checksum: str = ""
    retention_policy: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)
    size_bytes: int = 0
    actor_id: str = ""
    created_at: float = 0.0

    def __post_init__(self):
        if not self.evidence_id:
            self.evidence_id = f"ev_{uuid.uuid4().hex[:16]}"
        if not self.created_at:
            self.created_at = time.time()


def _compute_chain_hash(entry_id: str, payload_json: str, prev_hash: str, timestamp: float) -> str:
    raw = f"{prev_hash}|{entry_id}|{payload_json}|{timestamp}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}", size


class EvidenceSpine:
    """Immutable hash-chain audit log.

    Thread-safe. SQLite-backed. Emits events to EventBus.
    """

    def __init__(self, db_path: str | Path | None = None, event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path) if db_path else ":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_spine (
                entry_id    TEXT PRIMARY KEY,
                source_plan TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                payload     TEXT NOT NULL DEFAULT '{}',
                prev_hash   TEXT NOT NULL,
                hash        TEXT NOT NULL,
                timestamp   REAL NOT NULL,
                actor_id    TEXT NOT NULL DEFAULT '',
                signature   TEXT NOT NULL DEFAULT ''
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_plan ON evidence_spine(source_plan)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence_spine(event_type)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_ts ON evidence_spine(timestamp)")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_artifacts (
                evidence_id      TEXT PRIMARY KEY,
                source           TEXT NOT NULL,
                artifact_type    TEXT NOT NULL,
                uri              TEXT NOT NULL DEFAULT '',
                checksum         TEXT NOT NULL,
                retention_policy TEXT NOT NULL DEFAULT 'default',
                metadata         TEXT NOT NULL DEFAULT '{}',
                size_bytes       INTEGER NOT NULL DEFAULT 0,
                actor_id         TEXT NOT NULL DEFAULT '',
                chain_entry_id   TEXT NOT NULL,
                chain_hash       TEXT NOT NULL,
                created_at       REAL NOT NULL
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_artifact_source ON evidence_artifacts(source)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_artifact_type ON evidence_artifacts(artifact_type)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_artifact_created ON evidence_artifacts(created_at)")
        self._conn.commit()

    def _get_last_hash(self) -> str:
        row = self._conn.execute(
            "SELECT hash FROM evidence_spine ORDER BY timestamp DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return row["hash"] if row else GENESIS_PREV_HASH

    def append(self, entry: EvidenceEntry) -> dict:
        payload_json = _canonical_json(entry.payload)

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            prev_hash = self._get_last_hash()
            chain_hash = _compute_chain_hash(entry.entry_id, payload_json, prev_hash, entry.timestamp)

            self._conn.execute("""
                INSERT INTO evidence_spine
                (entry_id, source_plan, event_type, payload, prev_hash, hash, timestamp, actor_id, signature)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (entry.entry_id, entry.source_plan, entry.event_type, payload_json,
                  prev_hash, chain_hash, entry.timestamp, entry.actor_id, entry.signature))
            self._conn.commit()

        entry.prev_hash = prev_hash
        entry.hash = chain_hash

        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic="evidence.appended",
                payload={"entry_id": entry.entry_id, "hash": chain_hash},
                source_module="core.evidence_spine",
            ))

        log.info("evidence appended: %s (plan=%s, type=%s)", entry.entry_id[:12], entry.source_plan, entry.event_type)
        return {"entry_id": entry.entry_id, "hash": chain_hash, "prev_hash": prev_hash}

    @staticmethod
    def _artifact_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        artifact = dict(row)
        try:
            artifact["metadata"] = json.loads(artifact.get("metadata") or "{}")
        except (TypeError, json.JSONDecodeError):
            artifact["metadata"] = {}
        return artifact

    def register_artifact(self, artifact: EvidenceArtifact) -> dict[str, Any]:
        if not artifact.source.strip():
            raise ValueError("artifact source is required")
        if not artifact.artifact_type.strip():
            raise ValueError("artifact_type is required")
        if not artifact.retention_policy.strip():
            raise ValueError("retention_policy is required")
        if not artifact.checksum.strip():
            raise ValueError("artifact checksum is required")
        if self.get_artifact(artifact.evidence_id) is not None:
            raise ValueError(f"evidence artifact already exists: {artifact.evidence_id}")

        chain_entry = EvidenceEntry(
            source_plan=artifact.source,
            event_type="evidence.artifact.registered",
            payload={
                "evidence_id": artifact.evidence_id,
                "source": artifact.source,
                "artifact_type": artifact.artifact_type,
                "uri": artifact.uri,
                "checksum": artifact.checksum,
                "retention_policy": artifact.retention_policy,
                "metadata": artifact.metadata,
                "size_bytes": artifact.size_bytes,
            },
            actor_id=artifact.actor_id,
            timestamp=artifact.created_at,
        )
        chain_result = self.append(chain_entry)

        metadata_json = _canonical_json(artifact.metadata)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO evidence_artifacts
                (evidence_id, source, artifact_type, uri, checksum, retention_policy,
                 metadata, size_bytes, actor_id, chain_entry_id, chain_hash, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    artifact.evidence_id,
                    artifact.source,
                    artifact.artifact_type,
                    artifact.uri,
                    artifact.checksum,
                    artifact.retention_policy,
                    metadata_json,
                    int(artifact.size_bytes or 0),
                    artifact.actor_id,
                    chain_result["entry_id"],
                    chain_result["hash"],
                    artifact.created_at,
                ),
            )
            self._conn.commit()

        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic="evidence.artifact.registered",
                payload={"evidence_id": artifact.evidence_id, "checksum": artifact.checksum},
                source_module="core.evidence_spine",
            ))

        return self.get_artifact(artifact.evidence_id) or {}

    def register_json_artifact(
        self,
        payload: dict[str, Any],
        *,
        source: str,
        artifact_type: str = "api_response",
        retention_policy: str = "default",
        metadata: dict[str, Any] | None = None,
        evidence_id: str = "",
        actor_id: str = "",
    ) -> dict[str, Any]:
        payload_json = _canonical_json(payload)
        checksum = _sha256_bytes(payload_json.encode("utf-8"))
        return self.register_artifact(EvidenceArtifact(
            evidence_id=evidence_id,
            source=source,
            artifact_type=artifact_type,
            uri=f"inline:{checksum}",
            checksum=checksum,
            retention_policy=retention_policy,
            metadata={**(metadata or {}), "content_type": "application/json"},
            size_bytes=len(payload_json.encode("utf-8")),
            actor_id=actor_id,
        ))

    def register_file_artifact(
        self,
        path: str | Path,
        *,
        source: str,
        artifact_type: str,
        retention_policy: str = "default",
        metadata: dict[str, Any] | None = None,
        evidence_id: str = "",
        actor_id: str = "",
    ) -> dict[str, Any]:
        artifact_path = Path(path).resolve()
        if not artifact_path.is_file():
            raise ValueError(f"artifact file does not exist: {artifact_path}")
        checksum, size_bytes = _sha256_file(artifact_path)
        return self.register_artifact(EvidenceArtifact(
            evidence_id=evidence_id,
            source=source,
            artifact_type=artifact_type,
            uri=str(artifact_path),
            checksum=checksum,
            retention_policy=retention_policy,
            metadata=metadata or {},
            size_bytes=size_bytes,
            actor_id=actor_id,
        ))

    def get_artifact(self, evidence_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM evidence_artifacts WHERE evidence_id = ?",
            (evidence_id,),
        ).fetchone()
        return self._artifact_row_to_dict(row) if row else None

    def list_artifacts(
        self,
        *,
        source: str | None = None,
        artifact_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        q = "SELECT * FROM evidence_artifacts WHERE 1=1"
        params: list[Any] = []
        if source:
            q += " AND source = ?"
            params.append(source)
        if artifact_type:
            q += " AND artifact_type = ?"
            params.append(artifact_type)
        q += " ORDER BY created_at ASC LIMIT ?"
        params.append(limit)
        return [self._artifact_row_to_dict(r) for r in self._conn.execute(q, params).fetchall()]

    def verify_artifact(self, evidence_id: str) -> dict[str, Any]:
        artifact = self.get_artifact(evidence_id)
        if artifact is None:
            return {"evidence_id": evidence_id, "valid": False, "reason": "not_found"}

        uri = str(artifact.get("uri") or "")
        if not uri or uri.startswith("inline:"):
            return {
                "evidence_id": evidence_id,
                "valid": True,
                "reason": "checksum_recorded",
                "checksum": artifact["checksum"],
            }

        path = Path(uri)
        if not path.is_file():
            return {"evidence_id": evidence_id, "valid": False, "reason": "file_missing", "checksum": artifact["checksum"]}

        current_checksum, size_bytes = _sha256_file(path)
        return {
            "evidence_id": evidence_id,
            "valid": current_checksum == artifact["checksum"],
            "reason": "ok" if current_checksum == artifact["checksum"] else "checksum_mismatch",
            "checksum": artifact["checksum"],
            "current_checksum": current_checksum,
            "size_bytes": size_bytes,
        }

    def query(self, source_plan: str | None = None, event_type: str | None = None,
              since: float | None = None, limit: int = 100) -> list[dict]:
        q = "SELECT * FROM evidence_spine WHERE 1=1"
        params: list[Any] = []
        if source_plan: q += " AND source_plan = ?"; params.append(source_plan)
        if event_type:  q += " AND event_type = ?";  params.append(event_type)
        if since:       q += " AND timestamp >= ?";  params.append(since)
        q += " ORDER BY timestamp ASC LIMIT ?"; params.append(limit)
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def verify_chain(self) -> tuple[bool, str]:
        rows = self._conn.execute(
            "SELECT entry_id, payload, prev_hash, hash, timestamp FROM evidence_spine ORDER BY timestamp ASC, rowid ASC"
        ).fetchall()

        if not rows:
            return True, "empty spine — valid"

        expected_prev = GENESIS_PREV_HASH
        for i, row in enumerate(rows):
            if row["prev_hash"] != expected_prev:
                return False, f"chain break at entry {row['entry_id'][:12]} (index {i}): expected prev={expected_prev[:12]}, got {row['prev_hash'][:12]}"

            computed = _compute_chain_hash(row["entry_id"], row["payload"], row["prev_hash"], row["timestamp"])
            if computed != row["hash"]:
                return False, f"hash mismatch at entry {row['entry_id'][:12]} (index {i})"

            expected_prev = row["hash"]

        return True, f"chain valid ({len(rows)} entries)"

    def replay(self, since: float | None = None) -> list[dict]:
        """Replay evidence entries since timestamp."""
        return self.query(since=since, limit=100000)


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_spine: EvidenceSpine | None = None

def get_evidence_spine(db_path: str | Path | None = None,
                       event_bus: EventBus | None = None) -> EvidenceSpine:
    global _spine
    if _spine is None:
        _spine = EvidenceSpine(db_path, event_bus)
    return _spine
