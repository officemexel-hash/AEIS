"""
SYLION Efficiency -- Config Drift Detector

Tracks configuration drift between expected baselines and actual runtime
config values.  Detects non-compliant modules, records drift events with
timestamps, and supports remediation (update baseline or flag for fix).

SQLite-backed with WAL mode.  Thread-safe via threading.Lock.  Singleton
via get_config_drift_detector().  Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.efficiency.config_drift")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ConfigBaseline:
    """Expected configuration value for a module key."""
    module_id: str = ""
    config_key: str = ""
    config_value: str = ""
    set_at: float = 0.0

    def __post_init__(self):
        if not self.set_at:
            self.set_at = time.time()


@dataclass
class DriftEvent:
    """Recorded configuration drift occurrence."""
    drift_id: str = ""
    module_id: str = ""
    config_key: str = ""
    expected_value: str = ""
    actual_value: str = ""
    detected_at: float = 0.0
    remediated: int = 0

    def __post_init__(self):
        if not self.drift_id:
            self.drift_id = uuid.uuid4().hex
        if not self.detected_at:
            self.detected_at = time.time()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ComplianceError(Exception):
    """Raised when a module is non-compliant with its config baseline."""


# ---------------------------------------------------------------------------
# Config Drift Detector
# ---------------------------------------------------------------------------

class ConfigDriftDetector:
    """Configuration drift detection and compliance enforcement.

    Thread-safe.  SQLite-backed.  Emits events on drift / remediation.
    """

    def __init__(self, event_bus: EventBus | None = None,
                 db_path: str | Path | None = None):
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
            CREATE TABLE IF NOT EXISTS sylion_config_baselines (
                module_id    TEXT    NOT NULL,
                config_key   TEXT    NOT NULL,
                config_value TEXT    NOT NULL DEFAULT '',
                set_at       REAL    NOT NULL DEFAULT 0.0,
                PRIMARY KEY (module_id, config_key)
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_config_drift_events (
                drift_id       TEXT PRIMARY KEY,
                module_id      TEXT    NOT NULL DEFAULT '',
                config_key     TEXT    NOT NULL DEFAULT '',
                expected_value TEXT    NOT NULL DEFAULT '',
                actual_value   TEXT    NOT NULL DEFAULT '',
                detected_at    REAL    NOT NULL DEFAULT 0.0,
                remediated     INTEGER NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cde_module "
            "ON sylion_config_drift_events(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cde_ts "
            "ON sylion_config_drift_events(detected_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cde_remediated "
            "ON sylion_config_drift_events(remediated)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Baseline management
    # ------------------------------------------------------------------

    def set_baseline(self, module_id: str, config_key: str,
                     config_value: Any) -> dict:
        """Set expected config value for *module_id* / *config_key*.

        The value is serialised to a string (JSON for containers,
        ``str()`` for scalars).  Emits
        ``efficiency.config_drift.baseline_set``.
        """
        value_str = self._serialise(config_value)
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO sylion_config_baselines
                    (module_id, config_key, config_value, set_at)
                VALUES (?, ?, ?, ?)
            """, (module_id, config_key, value_str, now))
            self._conn.commit()

        result = {
            "module_id": module_id,
            "config_key": config_key,
            "config_value": value_str,
            "set_at": now,
        }

        self._emit("efficiency.config_drift.baseline_set", result)
        log.info("baseline set: %s/%s=%s", module_id, config_key, value_str)
        return result

    def get_baseline(self, module_id: str, config_key: str) -> str | None:
        """Return the baseline value for a key, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT config_value FROM sylion_config_baselines "
                "WHERE module_id = ? AND config_key = ?",
                (module_id, config_key),
            ).fetchone()
            return row["config_value"] if row else None

    def get_baselines_for_module(self, module_id: str) -> dict[str, str]:
        """Return all baseline key-value pairs for *module_id*."""
        with self._lock:
            return self._get_baselines_internal(module_id)

    def remove_baseline(self, module_id: str, config_key: str) -> bool:
        """Remove a single baseline entry. Returns True if deleted."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM sylion_config_baselines "
                "WHERE module_id = ? AND config_key = ?",
                (module_id, config_key),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def remove_baselines_for_module(self, module_id: str) -> int:
        """Remove all baselines for *module_id*. Returns count deleted."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM sylion_config_baselines WHERE module_id = ?",
                (module_id,),
            )
            self._conn.commit()
            return cur.rowcount

    # ------------------------------------------------------------------
    # Drift detection
    # ------------------------------------------------------------------

    def check_drift(self, module_id: str,
                    current_configs: dict[str, Any]) -> dict:
        """Compare *current_configs* against stored baselines.

        Returns ``{drifts: [...], compliant: bool}``.  Each drift entry
        contains ``config_key``, ``expected``, ``actual``.
        Drift events are automatically recorded.

        Emits ``efficiency.config_drift.drift_detected`` when drifts are
        found, or ``efficiency.config_drift.compliance_ok`` when clean.
        """
        with self._lock:
            baselines = self._get_baselines_internal(module_id)
            drifts: list[dict[str, str]] = []

            for key, expected_raw in baselines.items():
                if key not in current_configs:
                    actual_raw = None
                else:
                    actual_raw = current_configs[key]

                expected_str = expected_raw
                actual_str = self._serialise(actual_raw)

                if expected_str != actual_str:
                    drifts.append({
                        "config_key": key,
                        "expected": expected_str,
                        "actual": actual_str,
                    })

            # Record each drift (inside lock to avoid races)
            for d in drifts:
                self._insert_drift_row(
                    module_id, d["config_key"], d["expected"], d["actual"],
                )

        compliant = len(drifts) == 0
        result = {
            "drifts": drifts,
            "compliant": compliant,
            "module_id": module_id,
        }

        if compliant:
            self._emit("efficiency.config_drift.compliance_ok", {
                "module_id": module_id,
            })
        else:
            self._emit("efficiency.config_drift.drift_detected", {
                "module_id": module_id,
                "drift_count": len(drifts),
            })
            log.warning("drift detected for %s: %d keys drifted",
                        module_id, len(drifts))

        return result

    def record_drift(self, module_id: str, key: str,
                     expected: Any, actual: Any) -> dict:
        """Manually record a drift event.

        Emits ``efficiency.config_drift.drift_recorded``.
        """
        expected_str = self._serialise(expected)
        actual_str = self._serialise(actual)
        with self._lock:
            result = self._insert_drift_row(
                module_id, key, expected_str, actual_str,
            )
        self._emit("efficiency.config_drift.drift_recorded", result)
        log.info("drift recorded: %s/%s expected=%s actual=%s",
                 module_id, key, expected_str, actual_str)
        return result

    def _get_baselines_internal(self, module_id: str) -> dict[str, str]:
        """Internal: read baselines (caller holds lock if needed)."""
        rows = self._conn.execute(
            "SELECT config_key, config_value FROM sylion_config_baselines "
            "WHERE module_id = ?",
            (module_id,),
        ).fetchall()
        return {r["config_key"]: r["config_value"] for r in rows}

    def _insert_drift_row(self, module_id: str, key: str,
                          expected_str: str, actual_str: str) -> dict:
        """Internal: persist a drift event row (caller holds lock)."""
        drift = DriftEvent(
            module_id=module_id,
            config_key=key,
            expected_value=expected_str,
            actual_value=actual_str,
        )

        self._conn.execute("""
            INSERT INTO sylion_config_drift_events
                (drift_id, module_id, config_key,
                 expected_value, actual_value, detected_at, remediated)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (
            drift.drift_id, drift.module_id, drift.config_key,
            drift.expected_value, drift.actual_value, drift.detected_at,
        ))
        self._conn.commit()

        return {
            "drift_id": drift.drift_id,
            "module_id": module_id,
            "config_key": key,
            "expected": expected_str,
            "actual": actual_str,
            "detected_at": drift.detected_at,
        }

    # ------------------------------------------------------------------
    # Drift history & queries
    # ------------------------------------------------------------------

    def get_drift_history(self, module_id: str, limit: int = 20) -> list[dict]:
        """Return recent drift events for *module_id*."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sylion_config_drift_events "
                "WHERE module_id = ? ORDER BY detected_at DESC LIMIT ?",
                (module_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_drifts(self) -> list[dict]:
        """Return current drifts across all modules.

        Returns the most recent drift per (module_id, config_key) that
        has not been remediated.
        """
        with self._lock:
            rows = self._conn.execute("""
                SELECT d.* FROM sylion_config_drift_events d
                INNER JOIN (
                    SELECT module_id, config_key, MAX(detected_at) AS max_ts
                    FROM sylion_config_drift_events
                    WHERE remediated = 0
                    GROUP BY module_id, config_key
                ) latest
                ON d.module_id = latest.module_id
                AND d.config_key = latest.config_key
                AND d.detected_at = latest.max_ts
                WHERE d.remediated = 0
                ORDER BY d.module_id, d.config_key
            """).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Remediation
    # ------------------------------------------------------------------

    def remediate_drift(self, drift_id: str, new_value: Any) -> dict:
        """Remediate a drift event by *drift_id*.

        *new_value* updates the baseline to match the current (accepted)
        configuration.  The drift event is marked as remediated.

        Emits ``efficiency.config_drift.drift_remediated``.
        """
        new_value_str = self._serialise(new_value)

        # Fetch drift to get module_id and config_key
        row = self._conn.execute(
            "SELECT * FROM sylion_config_drift_events WHERE drift_id = ?",
            (drift_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"Drift event {drift_id} not found")

        module_id = row["module_id"]
        config_key = row["config_key"]

        with self._lock:
            # Update baseline
            now = time.time()
            self._conn.execute("""
                INSERT OR REPLACE INTO sylion_config_baselines
                    (module_id, config_key, config_value, set_at)
                VALUES (?, ?, ?, ?)
            """, (module_id, config_key, new_value_str, now))

            # Mark drift as remediated
            self._conn.execute(
                "UPDATE sylion_config_drift_events "
                "SET remediated = 1 WHERE drift_id = ?",
                (drift_id,),
            )
            self._conn.commit()

        result = {
            "drift_id": drift_id,
            "module_id": module_id,
            "config_key": config_key,
            "new_baseline": new_value_str,
            "remediated": True,
        }

        self._emit("efficiency.config_drift.drift_remediated", result)
        log.info("drift remediated: %s/%s -> %s",
                 module_id, config_key, new_value_str)
        return result

    # ------------------------------------------------------------------
    # Compliance enforcement
    # ------------------------------------------------------------------

    def enforce_compliance(self, module_id: str,
                           configs: dict[str, Any]) -> dict:
        """Check compliance and raise :class:`ComplianceError` if drifted.

        Returns the check result on success.
        """
        result = self.check_drift(module_id, configs)
        if not result["compliant"]:
            drift_keys = [d["config_key"] for d in result["drifts"]]
            raise ComplianceError(
                f"Module '{module_id}' is non-compliant. "
                f"Drifted keys: {drift_keys}"
            )
        return result

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate statistics across all modules.

        Returns total_baselines, total_drifts, compliance_rate (overall),
        and per-module breakdown.
        """
        with self._lock:
            # Total baselines
            bl_row = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM sylion_config_baselines"
            ).fetchone()
            total_baselines = bl_row["cnt"]

            # Total unremediated drifts
            dr_row = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM sylion_config_drift_events "
                "WHERE remediated = 0"
            ).fetchone()
            total_drifts = dr_row["cnt"]

            # Per-module stats
            modules_rows = self._conn.execute(
                "SELECT DISTINCT module_id FROM sylion_config_baselines "
                "ORDER BY module_id"
            ).fetchall()

            by_module: dict[str, dict[str, Any]] = {}
            for mrow in modules_rows:
                mid = mrow["module_id"]
                bl_count = self._conn.execute(
                    "SELECT COUNT(*) AS cnt FROM sylion_config_baselines "
                    "WHERE module_id = ?", (mid,)
                ).fetchone()["cnt"]

                drift_count = self._conn.execute(
                    "SELECT COUNT(*) AS cnt FROM sylion_config_drift_events "
                    "WHERE module_id = ? AND remediated = 0", (mid,)
                ).fetchone()["cnt"]

                # Latest drifts per key for this module
                active_drifts = self._conn.execute("""
                    SELECT d.* FROM sylion_config_drift_events d
                    INNER JOIN (
                        SELECT config_key, MAX(detected_at) AS max_ts
                        FROM sylion_config_drift_events
                        WHERE module_id = ? AND remediated = 0
                        GROUP BY config_key
                    ) latest ON d.config_key = latest.config_key
                              AND d.detected_at = latest.max_ts
                    WHERE d.module_id = ? AND d.remediated = 0
                """, (mid, mid)).fetchall()

                compliant_keys = bl_count - len(active_drifts)
                compliance_rate = (compliant_keys / bl_count * 100.0) if bl_count > 0 else 100.0

                by_module[mid] = {
                    "baselines": bl_count,
                    "active_drifts": len(active_drifts),
                    "compliance_rate": round(compliance_rate, 2),
                }

            overall_rate = 100.0
            if total_baselines > 0:
                compliant_total = total_baselines - total_drifts
                # Clamp to zero
                compliant_total = max(compliant_total, 0)
                overall_rate = round(compliant_total / total_baselines * 100.0, 2)

            return {
                "total_baselines": total_baselines,
                "total_drifts": total_drifts,
                "compliance_rate": overall_rate,
                "by_module": by_module,
            }

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialise(value: Any) -> str:
        """Normalise a config value to a comparable string."""
        if value is None:
            return "__NULL__"
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list, tuple, set)):
            return json.dumps(value, sort_keys=True, default=str)
        return str(value)

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="efficiency.config_drift",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_detector: ConfigDriftDetector | None = None


def get_config_drift_detector(event_bus: EventBus | None = None,
                              db_path: str | Path | None = None
                              ) -> ConfigDriftDetector:
    global _detector
    if _detector is None:
        _detector = ConfigDriftDetector(event_bus, db_path)
    return _detector
