"""
SYLION Governance — Evidence Spine

Immutable, hash-chained evidence spine for decision snapshots.
Every decision snapshot generates an evidence entry that links to the
previous one, creating a blockchain-like audit trail.

Tables:
  spine_entries -- hash-chained entries, one per decision snapshot event

Singleton: get_governance_spine() / reset_governance_spine()
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

log = logging.getLogger("sylion.governance.evidence_spine")

GENESIS_PREV_HASH = "0" * 64

VALID_ENTRY_TYPES = ("decision", "gate_evaluation", "code_change", "cascade")


class GovernanceSpine:
    """Hash-chained evidence spine for decision snapshots.

    Every append creates a chain entry whose hash covers the previous
    entry hash, the content hash, the decision_id and the timestamp.
    The chain can be verified at any time to detect tampering.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS spine_entries (
                entry_id       TEXT PRIMARY KEY,
                snapshot_id    TEXT,
                decision_id    TEXT NOT NULL,
                entry_type     TEXT NOT NULL,

                prev_hash      TEXT NOT NULL,
                entry_hash     TEXT NOT NULL,
                sequence_num   INTEGER NOT NULL,

                content_hash   TEXT NOT NULL,
                module_states_hash TEXT,
                evidence_pack  TEXT,
                metadata       TEXT,

                verified       INTEGER DEFAULT 0,
                verified_at    REAL,
                tampered       INTEGER DEFAULT 0,

                created_at     REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_spine_decision ON spine_entries(decision_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_spine_type ON spine_entries(entry_type)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_spine_seq ON spine_entries(sequence_num)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_spine_snapshot ON spine_entries(snapshot_id)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="governance.evidence_spine",
            ))

    @staticmethod
    def _compute_entry_hash(prev_hash: str, content_hash: str,
                            decision_id: str, timestamp: float) -> str:
        raw = f"{prev_hash}|{content_hash}|{decision_id}|{timestamp}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _get_last_entry(self) -> dict | None:
        row = self._conn.execute(
            "SELECT entry_hash, sequence_num FROM spine_entries "
            "ORDER BY sequence_num DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _parse_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        for key in ("evidence_pack", "metadata"):
            if d.get(key) is not None:
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_entry(
        self,
        decision_id: str,
        entry_type: str,
        content_hash: str,
        snapshot_id: str | None = None,
        module_states_hash: str | None = None,
        evidence_pack: dict | list | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Append a new entry to the hash chain.

        Returns the created spine entry.
        """
        if entry_type not in VALID_ENTRY_TYPES:
            raise ValueError(
                f"Invalid entry_type '{entry_type}', "
                f"must be one of {VALID_ENTRY_TYPES}"
            )

        entry_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            last = self._get_last_entry()
            prev_hash = last["entry_hash"] if last else GENESIS_PREV_HASH
            seq = (last["sequence_num"] + 1) if last else 1

            entry_hash = self._compute_entry_hash(
                prev_hash, content_hash, decision_id, now
            )

            evidence_json = (
                json.dumps(evidence_pack, sort_keys=True, default=str)
                if evidence_pack is not None else None
            )
            metadata_json = (
                json.dumps(metadata, sort_keys=True, default=str)
                if metadata is not None else None
            )

            self._conn.execute("""
                INSERT INTO spine_entries
                (entry_id, snapshot_id, decision_id, entry_type,
                 prev_hash, entry_hash, sequence_num,
                 content_hash, module_states_hash, evidence_pack, metadata,
                 verified, tampered, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,0,0,?)
            """, (
                entry_id, snapshot_id, decision_id, entry_type,
                prev_hash, entry_hash, seq,
                content_hash, module_states_hash, evidence_json, metadata_json,
                now,
            ))
            self._conn.commit()

        result = {
            "entry_id": entry_id,
            "snapshot_id": snapshot_id,
            "decision_id": decision_id,
            "entry_type": entry_type,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
            "sequence_num": seq,
            "content_hash": content_hash,
            "created_at": now,
        }

        self._emit("governance.spine.appended", {
            "entry_id": entry_id,
            "decision_id": decision_id,
            "sequence_num": seq,
        })
        log.info("spine entry %s (seq=%d, decision=%s, type=%s)",
                 entry_id, seq, decision_id[:12] if decision_id else "?",
                 entry_type)
        return result

    def verify_chain(self) -> dict:
        """Walk the chain from start to end and verify integrity.

        Returns {valid, broken_at, total_entries, tampered_count}.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT entry_id, prev_hash, entry_hash, content_hash, "
                "       decision_id, created_at, tampered "
                "FROM spine_entries ORDER BY sequence_num ASC, rowid ASC"
            ).fetchall()

        total = len(rows)
        if total == 0:
            return {
                "valid": True,
                "broken_at": None,
                "total_entries": 0,
                "tampered_count": 0,
            }

        expected_prev = GENESIS_PREV_HASH
        broken_at = None
        tampered_count = 0

        for i, row in enumerate(rows):
            # Check prev_hash linkage
            if row["prev_hash"] != expected_prev:
                broken_at = row["entry_id"]
                # Mark as tampered
                with self._lock:
                    self._conn.execute(
                        "UPDATE spine_entries SET tampered = 1 WHERE entry_id = ?",
                        (row["entry_id"],)
                    )
                    self._conn.commit()
                tampered_count += 1
                break

            # Recompute entry_hash and compare
            computed = self._compute_entry_hash(
                row["prev_hash"], row["content_hash"],
                row["decision_id"], row["created_at"]
            )
            if computed != row["entry_hash"]:
                broken_at = row["entry_id"]
                with self._lock:
                    self._conn.execute(
                        "UPDATE spine_entries SET tampered = 1 WHERE entry_id = ?",
                        (row["entry_id"],)
                    )
                    self._conn.commit()
                tampered_count += 1
                break

            expected_prev = row["entry_hash"]

        # Count any pre-existing tampered flags
        with self._lock:
            tc = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM spine_entries WHERE tampered = 1"
            ).fetchone()
            pre_existing_tampered = tc["cnt"] if tc else 0

        return {
            "valid": broken_at is None,
            "broken_at": broken_at,
            "total_entries": total,
            "tampered_count": max(tampered_count, pre_existing_tampered),
        }

    def get_spine(self, from_seq: int | None = None,
                  to_seq: int | None = None,
                  entry_type: str | None = None) -> list[dict]:
        """Return a range of spine entries, ordered by sequence."""
        with self._lock:
            q = "SELECT * FROM spine_entries WHERE 1=1"
            params: list[Any] = []
            if from_seq is not None:
                q += " AND sequence_num >= ?"
                params.append(from_seq)
            if to_seq is not None:
                q += " AND sequence_num <= ?"
                params.append(to_seq)
            if entry_type is not None:
                q += " AND entry_type = ?"
                params.append(entry_type)
            q += " ORDER BY sequence_num ASC"
            rows = self._conn.execute(q, params).fetchall()
        return [self._parse_row(r) for r in rows]

    def get_entry(self, entry_id: str) -> dict | None:
        """Return a single spine entry."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM spine_entries WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_row(row)

    def get_entries_for_decision(self, decision_id: str) -> list[dict]:
        """Return all spine entries for a given decision."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM spine_entries WHERE decision_id = ? "
                "ORDER BY sequence_num ASC",
                (decision_id,),
            ).fetchall()
        return [self._parse_row(r) for r in rows]

    def mark_verified(self, entry_id: str) -> dict | None:
        """Mark an entry as verified."""
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT entry_id FROM spine_entries WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
            if not row:
                return None
            self._conn.execute(
                "UPDATE spine_entries SET verified = 1, verified_at = ? "
                "WHERE entry_id = ?",
                (now, entry_id),
            )
            self._conn.commit()
        return {"entry_id": entry_id, "verified": True, "verified_at": now}

    def get_chain_stats(self) -> dict:
        """Return summary statistics of the chain."""
        with self._lock:
            count_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM spine_entries"
            ).fetchone()
            total_entries = count_row["cnt"] if count_row else 0

            if total_entries == 0:
                return {
                    "total_entries": 0,
                    "chain_valid": True,
                    "last_entry_hash": GENESIS_PREV_HASH,
                    "last_sequence": 0,
                }

            last_row = self._conn.execute(
                "SELECT entry_hash, sequence_num FROM spine_entries "
                "ORDER BY sequence_num DESC, rowid DESC LIMIT 1"
            ).fetchone()

        # Run verify to determine chain_valid (outside lock to avoid deadlock)
        verification = self.verify_chain()

        return {
            "total_entries": total_entries,
            "chain_valid": verification["valid"],
            "last_entry_hash": last_row["entry_hash"] if last_row else GENESIS_PREV_HASH,
            "last_sequence": last_row["sequence_num"] if last_row else 0,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_spine: GovernanceSpine | None = None


def get_governance_spine(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> GovernanceSpine:
    global _spine
    if _spine is None:
        _spine = GovernanceSpine(db_path, event_bus)
    return _spine


def reset_governance_spine(db_path: str | Path | None = None,
                           event_bus: EventBus | None = None) -> GovernanceSpine:
    global _spine
    _spine = GovernanceSpine(db_path, event_bus)
    return _spine
