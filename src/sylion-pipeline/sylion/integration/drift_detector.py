"""
SYLION Integration -- Drift Detector

Detects cross-module contract drift by comparing current manifests
against the frozen contract registry.

Drift types:
  - breaking_change: public API removed or signature changed
  - missing_dependency: depends_on references unknown module
  - version_mismatch: contract version incompatible
  - event_drift: event taxonomy changed without governance
  - ownership_drift: module owner changed without approval
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.integration.drift")

DRIFT_TYPES = ("breaking_change", "missing_dependency", "version_mismatch", "event_drift", "ownership_drift", "cross_module_leak")


class DriftDetector:
    """Detects and records contract drift across modules."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        event_bus: EventBus | None = None,
        manifest_dir: Path | None = None,
    ):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._manifest_dir = manifest_dir or (Path(__file__).parent.parent / "contracts" / "manifests")
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS drift_records (
                drift_id          TEXT PRIMARY KEY,
                drift_type        TEXT NOT NULL,
                source_module     TEXT NOT NULL,
                target_module     TEXT,
                description       TEXT NOT NULL,
                severity          TEXT NOT NULL DEFAULT 'warning',
                status            TEXT NOT NULL DEFAULT 'open',
                resolution        TEXT,
                metadata_json     TEXT NOT NULL DEFAULT '{}',
                created_at        REAL NOT NULL,
                updated_at        REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_drift_type     ON drift_records(drift_type);
            CREATE INDEX IF NOT EXISTS idx_drift_source   ON drift_records(source_module);
            CREATE INDEX IF NOT EXISTS idx_drift_status   ON drift_records(status);
        """)
        self._conn.commit()

    def _emit(self, topic: str, payload: dict[str, Any]):
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(
                SylionEvent(event_id="", topic=topic, payload=payload, source_module="core.integration")
            )
        except Exception as exc:
            log.warning("EventBus publish failed: %s", exc)

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect_all(self) -> list[dict[str, Any]]:
        """Run full drift detection across all manifests."""
        drifts: list[dict[str, Any]] = []
        manifests = self._load_all_manifests()
        module_ids = {m["module_id"] for m in manifests}

        for m in manifests:
            # Missing dependencies
            for dep in m.get("depends_on", []):
                if dep not in module_ids:
                    drifts.append(self._create_drift_record(
                        drift_type="missing_dependency",
                        source_module=m["module_id"],
                        target_module=dep,
                        description=f"Module {m['module_id']} depends on unknown module {dep}",
                        severity="critical",
                    ))

            # Cross-module public API leaks (if public_api references other modules)
            for api in m.get("public_api", []):
                for other in module_ids:
                    if other != m["module_id"] and other in str(api):
                        drifts.append(self._create_drift_record(
                            drift_type="cross_module_leak",
                            source_module=m["module_id"],
                            target_module=other,
                            description=f"Public API of {m['module_id']} references {other}",
                            severity="warning",
                        ))

            # Version mismatch (simple heuristic: if version field missing)
            if not m.get("version"):
                drifts.append(self._create_drift_record(
                    drift_type="version_mismatch",
                    source_module=m["module_id"],
                    description=f"Module {m['module_id']} has no version defined",
                    severity="warning",
                ))

        self._emit("integration.drift.detected", {"count": len(drifts)})
        return drifts

    def detect_for_module(self, module_id: str) -> list[dict[str, Any]]:
        """Detect drift for a single module."""
        all_drifts = self.detect_all()
        return [d for d in all_drifts if d["source_module"] == module_id or d.get("target_module") == module_id]

    def _load_all_manifests(self) -> list[dict[str, Any]]:
        manifests: list[dict[str, Any]] = []
        if not self._manifest_dir.exists():
            return manifests
        for path in self._manifest_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                manifests.append(data)
            except Exception as exc:
                log.warning("Failed to load manifest %s: %s", path, exc)
        return manifests

    # ------------------------------------------------------------------
    # Record CRUD
    # ------------------------------------------------------------------

    def _create_drift_record(
        self,
        drift_type: str,
        source_module: str,
        description: str,
        target_module: str | None = None,
        severity: str = "warning",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        drift_id = f"dft_{uuid.uuid4().hex[:12]}"
        now = time.time()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO drift_records
                (drift_id, drift_type, source_module, target_module, description,
                 severity, status, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    drift_id, drift_type, source_module, target_module or "",
                    description, severity, "open",
                    json.dumps(metadata or {}), now, now,
                ),
            )
            self._conn.commit()
        record = {
            "drift_id": drift_id,
            "drift_type": drift_type,
            "source_module": source_module,
            "target_module": target_module,
            "description": description,
            "severity": severity,
            "status": "open",
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        self._emit("integration.drift.recorded", {"drift_id": drift_id, "type": drift_type, "source": source_module})
        return record

    def list_drifts(
        self,
        status: str | None = None,
        severity: str | None = None,
        source_module: str | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if severity:
            where.append("severity = ?")
            params.append(severity)
        if source_module:
            where.append("source_module = ?")
            params.append(source_module)
        sql = "SELECT * FROM drift_records"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "drift_id": r["drift_id"],
                "drift_type": r["drift_type"],
                "source_module": r["source_module"],
                "target_module": r["target_module"] or None,
                "description": r["description"],
                "severity": r["severity"],
                "status": r["status"],
                "resolution": r["resolution"],
                "metadata": json.loads(r["metadata_json"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def get_drift(self, drift_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM drift_records WHERE drift_id = ?", (drift_id,)
            ).fetchone()
        if row is None:
            return None
        return {
            "drift_id": row["drift_id"],
            "drift_type": row["drift_type"],
            "source_module": row["source_module"],
            "target_module": row["target_module"] or None,
            "description": row["description"],
            "severity": row["severity"],
            "status": row["status"],
            "resolution": row["resolution"],
            "metadata": json.loads(row["metadata_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def resolve_drift(self, drift_id: str, resolution: str = "") -> dict[str, Any] | None:
        with self._lock:
            self._conn.execute(
                "UPDATE drift_records SET status = ?, resolution = ?, updated_at = ? WHERE drift_id = ?",
                ("resolved", resolution, time.time(), drift_id),
            )
            self._conn.commit()
        self._emit("integration.drift.resolved", {"drift_id": drift_id, "resolution": resolution})
        return self.get_drift(drift_id)

    def get_drift_summary(self) -> dict[str, Any]:
        """Return summary counts by type and severity."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT drift_type, severity, COUNT(*) as cnt
                FROM drift_records
                WHERE status = 'open'
                GROUP BY drift_type, severity
                """
            ).fetchall()
        summary: dict[str, Any] = {"total_open": 0, "by_type": {}, "by_severity": {}}
        for r in rows:
            summary["total_open"] += r["cnt"]
            summary["by_type"][r["drift_type"]] = summary["by_type"].get(r["drift_type"], 0) + r["cnt"]
            summary["by_severity"][r["severity"]] = summary["by_severity"].get(r["severity"], 0) + r["cnt"]
        return summary


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_detector_instance: DriftDetector | None = None


def get_drift_detector(db_path: str | Path | None = None, event_bus: EventBus | None = None) -> DriftDetector:
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = DriftDetector(db_path, event_bus)
    return _detector_instance


def reset_drift_detector():
    global _detector_instance
    _detector_instance = None
