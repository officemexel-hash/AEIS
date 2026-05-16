"""
SYLION Devices -- Artifact Deployer (M3)

Manages deployment of artifacts (APKs, firmware, configs) to devices.
Supports dry-run validation, deployment, and rollback.
"""

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.devices.artifact_deployer")


class ArtifactDeployer:
    """Deploys artifacts to devices with rollback support."""

    def __init__(self, db_path: str | Path | None = None, event_bus=None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS deployments (
                    deploy_id      TEXT PRIMARY KEY,
                    device_id      TEXT NOT NULL,
                    artifact_hash  TEXT NOT NULL,
                    artifact_type  TEXT NOT NULL DEFAULT 'apk',
                    status         TEXT NOT NULL DEFAULT 'deployed',
                    rollback_hash  TEXT NOT NULL DEFAULT '',
                    deployed_at    REAL NOT NULL
                )
            """)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Deploy
    # ------------------------------------------------------------------

    def deploy(self, device_id: str, artifact_hash: str,
               artifact_type: str = "apk") -> dict:
        """Deploy an artifact to a device.

        Creates a deployment record and emits device.artifact.deployed.
        """
        deploy_id = f"dep-{uuid.uuid4().hex[:12]}"
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO deployments
                (deploy_id, device_id, artifact_hash, artifact_type, status,
                 rollback_hash, deployed_at)
                VALUES (?, ?, ?, ?, 'deployed', '', ?)
            """, (deploy_id, device_id, artifact_hash, artifact_type, now))
            self._conn.commit()

        self._emit("device.artifact.deployed", {
            "deploy_id": deploy_id,
            "device_id": device_id,
            "artifact_hash": artifact_hash,
            "artifact_type": artifact_type,
        })

        log.info("deployed %s to device %s (hash=%s)", deploy_id, device_id, artifact_hash[:12])
        return {
            "deploy_id": deploy_id,
            "device_id": device_id,
            "artifact_hash": artifact_hash,
            "artifact_type": artifact_type,
            "status": "deployed",
            "rollback_hash": "",
            "deployed_at": now,
        }

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def rollback(self, deploy_id: str) -> dict | None:
        """Rollback a deployment by deploy_id.

        Sets status to 'rolled_back' and records the previous artifact hash.
        """
        row = self._conn.execute(
            "SELECT * FROM deployments WHERE deploy_id = ?",
            (deploy_id,),
        ).fetchone()
        if not row:
            return None

        previous_hash = row["artifact_hash"]

        with self._lock:
            self._conn.execute("""
                UPDATE deployments
                SET status = 'rolled_back', rollback_hash = ?
                WHERE deploy_id = ?
            """, (previous_hash, deploy_id))
            self._conn.commit()

        self._emit("device.artifact.rolled_back", {
            "deploy_id": deploy_id,
            "device_id": row["device_id"],
            "rollback_hash": previous_hash,
        })

        log.info("rolled back deployment %s (hash=%s)", deploy_id, previous_hash[:12])
        return self.get(deploy_id)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, deploy_id: str) -> dict | None:
        """Get a single deployment by ID."""
        row = self._conn.execute(
            "SELECT * FROM deployments WHERE deploy_id = ?",
            (deploy_id,),
        ).fetchone()
        if not row:
            return None
        return dict(row)

    def list_deployments(self, device_id: str | None = None,
                         limit: int = 100) -> list[dict]:
        """List deployments, optionally filtered by device_id."""
        query = "SELECT * FROM deployments WHERE 1=1"
        params: list[Any] = []
        if device_id is not None:
            query += " AND device_id = ?"
            params.append(device_id)
        query += " ORDER BY deployed_at DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Dry run
    # ------------------------------------------------------------------

    def dry_run(self, device_id: str, artifact_hash: str) -> dict:
        """Validate a deployment without actually deploying.

        Returns a validation result dict.
        """
        # Simulate validation checks
        valid = len(artifact_hash) >= 8
        warnings = []
        if not valid:
            warnings.append("artifact_hash too short (min 8 chars)")

        return {
            "device_id": device_id,
            "artifact_hash": artifact_hash,
            "valid": valid,
            "warnings": warnings,
            "dry_run": True,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="devices.artifact_deployer",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_var: ArtifactDeployer | None = None


def get_artifact_deployer(db_path=None, event_bus=None):
    global _var
    if _var is None:
        _var = ArtifactDeployer(db_path, event_bus)
    return _var
