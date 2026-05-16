"""
SYLION Rebuild -- LPW Checkpoint (Enhanced Last Known Good Position)

Full-system checkpoint system for rollback support.
Captures module states, contract versions, and event replay positions
into a single atomic checkpoint backed by SQLite.

Thread-safe. Singleton pattern. Emits events via EventBus.

Ksiega Reversibility meta-rule:
  LPW = Last Position Working — the last known good state of the system.
  Before every D3+ change, LPW is updated as a checkpoint.
  If anything goes wrong, system can rollback to LPW.
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

log = logging.getLogger("sylion.rebuild.lpw_checkpoint")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CheckpointSnapshot:
    """A single LPW checkpoint capturing full system state."""
    checkpoint_id: str = ""
    label: str = ""
    trigger: str = ""
    snapshot_hash: str = ""
    modules_json: str = "[]"
    contracts_json: str = "[]"
    event_position: float = 0.0
    metadata_json: str = "{}"
    created_at: float = 0.0
    restored_at: float = 0.0
    is_valid: int = 1

    def __post_init__(self):
        if not self.checkpoint_id:
            self.checkpoint_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


# ---------------------------------------------------------------------------
# LPW Checkpoint Manager
# ---------------------------------------------------------------------------

class LPWCheckpoint:
    """Enhanced checkpoint system for Last Known Good Position.

    SQLite-backed, thread-safe, singleton.

    A checkpoint captures:
      - All module states (lifecycle stages, versions)
      - Contract versions for every module
      - Event bus replay position (timestamp)

    Usage:
        cp = LPWCheckpoint(registry=reg, event_bus=bus)
        info = cp.create_checkpoint(label="pre-upgrade", trigger="D3_change")
        # ... do risky operation ...
        if failed:
            cp.restore_checkpoint(info["checkpoint_id"], reg, bus)
    """

    def __init__(self, registry=None, event_bus: EventBus | None = None,
                 db_path: str | Path | None = None):
        self._registry = registry
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS lpw_checkpoints (
                checkpoint_id  TEXT PRIMARY KEY,
                label          TEXT NOT NULL DEFAULT '',
                trigger        TEXT NOT NULL DEFAULT '',
                snapshot_hash  TEXT NOT NULL DEFAULT '',
                modules_json   TEXT NOT NULL DEFAULT '[]',
                contracts_json TEXT NOT NULL DEFAULT '[]',
                event_position REAL NOT NULL DEFAULT 0,
                metadata_json  TEXT NOT NULL DEFAULT '{}',
                created_at     REAL NOT NULL,
                restored_at    REAL NOT NULL DEFAULT 0,
                is_valid       INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lpw_cp_created "
            "ON lpw_checkpoints(created_at DESC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lpw_cp_valid "
            "ON lpw_checkpoints(is_valid)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Snapshot collection
    # ------------------------------------------------------------------

    def _collect_module_states(self) -> list[dict]:
        """Collect current state of all modules from the registry."""
        if self._registry is None:
            return []
        modules = self._registry.list_modules()
        # Store only essential fields for restoration
        result = []
        for m in modules:
            result.append({
                "module_id": m.get("module_id", ""),
                "module_kind": m.get("module_kind", ""),
                "lifecycle": m.get("lifecycle", "draft"),
                "version": m.get("version", "1.0.0"),
                "contract_ver": m.get("contract_ver", "1.0.0"),
                "milestone": m.get("milestone", "M0"),
            })
        return result

    def _collect_contract_versions(self) -> list[dict]:
        """Collect contract versions from the registry."""
        if self._registry is None:
            return []
        modules = self._registry.list_modules()
        return [
            {
                "module_id": m.get("module_id", ""),
                "contract_ver": m.get("contract_ver", "1.0.0"),
            }
            for m in modules
        ]

    def _get_event_position(self) -> float:
        """Get the current event bus replay position (latest timestamp)."""
        if self._event_bus is None:
            return time.time()
        events = self._event_bus.query(limit=1)
        if events:
            return events[0].get("timestamp", time.time())
        return time.time()

    @staticmethod
    def _compute_hash(modules: list[dict], contracts: list[dict],
                      event_pos: float) -> str:
        """Compute SHA-256 hash of the checkpoint data for integrity."""
        payload = json.dumps({
            "modules": modules,
            "contracts": contracts,
            "event_position": event_pos,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Checkpoint CRUD
    # ------------------------------------------------------------------

    def create_checkpoint(self, label: str, trigger: str) -> dict:
        """Create a new LPW checkpoint.

        Captures all module states, contract versions, and event position.
        Returns dict with checkpoint_id, snapshot_hash, modules, contracts.
        """
        modules = self._collect_module_states()
        contracts = self._collect_contract_versions()
        event_pos = self._get_event_position()
        snap_hash = self._compute_hash(modules, contracts, event_pos)

        cp = CheckpointSnapshot(
            label=label,
            trigger=trigger,
            snapshot_hash=snap_hash,
            modules_json=json.dumps(modules),
            contracts_json=json.dumps(contracts),
            event_position=event_pos,
            metadata_json=json.dumps({
                "module_count": len(modules),
                "trigger": trigger,
            }),
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO lpw_checkpoints
                    (checkpoint_id, label, trigger, snapshot_hash,
                     modules_json, contracts_json, event_position,
                     metadata_json, created_at, restored_at, is_valid)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1)
            """, (
                cp.checkpoint_id, cp.label, cp.trigger, cp.snapshot_hash,
                cp.modules_json, cp.contracts_json, cp.event_position,
                cp.metadata_json, cp.created_at,
            ))
            self._conn.commit()

        self._emit("rebuild.lpw_checkpoint.created", {
            "checkpoint_id": cp.checkpoint_id,
            "label": label,
            "trigger": trigger,
            "snapshot_hash": snap_hash[:16],
            "module_count": len(modules),
        })

        log.info("created LPW checkpoint %s (%s, trigger=%s, modules=%d)",
                 cp.checkpoint_id[:12], label, trigger, len(modules))

        return {
            "checkpoint_id": cp.checkpoint_id,
            "label": label,
            "trigger": trigger,
            "snapshot_hash": snap_hash,
            "modules": modules,
            "contracts": contracts,
            "event_position": event_pos,
            "created_at": cp.created_at,
        }

    def restore_checkpoint(self, checkpoint_id: str,
                           registry=None, event_bus=None) -> dict:
        """Restore system to a checkpoint state.

        Reverts module lifecycles and restores contract versions.
        Does NOT delete modules -- only transitions states and updates versions.
        """
        row = self._conn.execute(
            "SELECT * FROM lpw_checkpoints WHERE checkpoint_id = ?",
            (checkpoint_id,),
        ).fetchone()

        if not row:
            log.warning("checkpoint %s not found for restore", checkpoint_id)
            return {"checkpoint_id": checkpoint_id, "error": "checkpoint not found"}

        if not row["is_valid"]:
            return {"checkpoint_id": checkpoint_id, "error": "checkpoint is invalid"}

        modules = json.loads(row["modules_json"])
        contracts = json.loads(row["contracts_json"])
        event_position = row["event_position"]
        restored_count = 0

        target_registry = registry or self._registry
        if target_registry is not None:
            from sylion.core.module_registry import ModuleLifecycleStage

            for mod_snap in modules:
                mid = mod_snap.get("module_id", "")
                current = target_registry.get(mid)
                if current is None:
                    log.warning("module %s not found during restore, skipping", mid)
                    continue

                # Restore lifecycle stage
                target_lifecycle = mod_snap.get("lifecycle", "stable")
                try:
                    current_stage = ModuleLifecycleStage(current.get("lifecycle", "stable"))
                    desired_stage = ModuleLifecycleStage(target_lifecycle)
                    if current_stage != desired_stage:
                        # Use direct SQL update for checkpoint restore to bypass
                        # transition validation -- checkpoint restore is an override
                        with target_registry._lock:
                            target_registry._conn.execute(
                                "UPDATE sylion_modules SET lifecycle=?, last_heartbeat=? "
                                "WHERE module_id=?",
                                (target_lifecycle, time.time(), mid),
                            )
                            target_registry._conn.commit()
                except Exception as exc:
                    log.warning("failed to restore lifecycle for %s: %s", mid, exc)

                # Restore contract version
                for c in contracts:
                    if c.get("module_id") == mid:
                        with target_registry._lock:
                            target_registry._conn.execute(
                                "UPDATE sylion_modules SET contract_ver=? WHERE module_id=?",
                                (c.get("contract_ver", "1.0.0"), mid),
                            )
                            target_registry._conn.commit()
                        break

                restored_count += 1

        # Replay events from the checkpoint position
        target_bus = event_bus or self._event_bus
        if target_bus is not None:
            target_bus.replay(since=event_position)

        # Mark checkpoint as restored
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE lpw_checkpoints SET restored_at=? WHERE checkpoint_id=?",
                (now, checkpoint_id),
            )
            self._conn.commit()

        self._emit("rebuild.lpw_checkpoint.restored", {
            "checkpoint_id": checkpoint_id,
            "restored_count": restored_count,
            "event_position": event_position,
        })

        log.info("restored checkpoint %s (%d modules, event_pos=%.3f)",
                 checkpoint_id[:12], restored_count, event_position)

        return {
            "checkpoint_id": checkpoint_id,
            "restored_count": restored_count,
            "event_position": event_position,
            "restored_at": now,
        }

    def get_latest(self) -> dict | None:
        """Get the most recent valid checkpoint."""
        row = self._conn.execute(
            "SELECT * FROM lpw_checkpoints WHERE is_valid = 1 "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_checkpoint(self, checkpoint_id: str) -> dict | None:
        """Get a specific checkpoint by ID."""
        row = self._conn.execute(
            "SELECT * FROM lpw_checkpoints WHERE checkpoint_id = ?",
            (checkpoint_id,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_checkpoints(self, limit: int = 20) -> list[dict]:
        """List recent checkpoints, newest first."""
        rows = self._conn.execute(
            "SELECT * FROM lpw_checkpoints ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def verify_checkpoint(self, checkpoint_id: str) -> dict:
        """Verify checkpoint integrity by recomputing the hash.

        Returns dict with valid (bool), expected_hash, computed_hash.
        """
        row = self._conn.execute(
            "SELECT * FROM lpw_checkpoints WHERE checkpoint_id = ?",
            (checkpoint_id,),
        ).fetchone()

        if not row:
            return {
                "checkpoint_id": checkpoint_id,
                "valid": False,
                "error": "checkpoint not found",
            }

        stored_hash = row["snapshot_hash"]
        modules = json.loads(row["modules_json"])
        contracts = json.loads(row["contracts_json"])
        event_pos = row["event_position"]
        computed_hash = self._compute_hash(modules, contracts, event_pos)

        valid = (stored_hash == computed_hash) and bool(row["is_valid"])

        self._emit("rebuild.lpw_checkpoint.verified", {
            "checkpoint_id": checkpoint_id,
            "valid": valid,
        })

        return {
            "checkpoint_id": checkpoint_id,
            "valid": valid,
            "expected_hash": stored_hash,
            "computed_hash": computed_hash,
            "hash_match": stored_hash == computed_hash,
            "is_valid_flag": bool(row["is_valid"]),
        }

    def prune_old_checkpoints(self, keep: int = 10) -> int:
        """Remove old checkpoints, keeping only the N most recent valid ones.

        Returns the number of checkpoints removed.
        """
        with self._lock:
            # Find IDs of checkpoints to keep
            rows = self._conn.execute(
                "SELECT checkpoint_id FROM lpw_checkpoints "
                "WHERE is_valid = 1 ORDER BY created_at DESC LIMIT ?",
                (keep,),
            ).fetchall()
            keep_ids = [r["checkpoint_id"] for r in rows]

            if not keep_ids:
                return 0

            placeholders = ",".join("?" * len(keep_ids))
            deleted = self._conn.execute(
                f"DELETE FROM lpw_checkpoints "
                f"WHERE checkpoint_id NOT IN ({placeholders})",
                keep_ids,
            ).rowcount
            self._conn.commit()

        if deleted:
            log.info("pruned %d old checkpoints (kept %d)", deleted, len(keep_ids))
            self._emit("rebuild.lpw_checkpoint.pruned", {
                "removed_count": deleted,
                "kept_count": len(keep_ids),
            })

        return deleted

    # ------------------------------------------------------------------
    # Invalidating checkpoints
    # ------------------------------------------------------------------

    def invalidate_checkpoint(self, checkpoint_id: str) -> bool:
        """Mark a checkpoint as invalid (e.g., corrupted external state)."""
        with self._lock:
            updated = self._conn.execute(
                "UPDATE lpw_checkpoints SET is_valid = 0 WHERE checkpoint_id = ?",
                (checkpoint_id,),
            ).rowcount
            self._conn.commit()
        return bool(updated)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        # Parse JSON fields
        for key in ("modules_json", "contracts_json", "metadata_json"):
            if key in d:
                d[key] = json.loads(d[key])
        return d

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="rebuild.lpw_checkpoint",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: LPWCheckpoint | None = None


def get_lpw_checkpoint(registry=None, event_bus: EventBus | None = None,
                       db_path: str | Path | None = None) -> LPWCheckpoint:
    global _instance
    if _instance is None:
        _instance = LPWCheckpoint(registry=registry, event_bus=event_bus,
                                  db_path=db_path)
    return _instance
