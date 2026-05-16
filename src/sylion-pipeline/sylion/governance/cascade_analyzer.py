"""
SYLION Governance -- Cascade Analyzer

Analyzes cascade effects of changes across modules.  Determines which modules
are affected by a change to a source module, calculates risk levels, and tracks
dependency paths through the contract graph.

Change types:
  api_change          -- public API signature modified
  schema_change       -- data/event schema altered
  config_change       -- configuration shape changed
  dependency_change   -- upstream dependency added/removed/updated
  interface_change    -- inter-module interface contract changed

Risk levels:
  low      -- 0-1 affected modules
  medium   -- 2-3 affected modules
  high     -- 4-5 affected modules, or critical contract types involved
  critical -- 6+ affected modules, or breaking interface changes

Tables:
  cascade_analyses  -- analysis records with risk assessment
  cascade_paths     -- individual dependency paths per analysis

Singleton: get_cascade_analyzer() / reset_cascade_analyzer()
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

log = logging.getLogger("sylion.governance.cascade_analyzer")

VALID_CHANGE_TYPES = (
    "api_change",
    "schema_change",
    "config_change",
    "dependency_change",
    "interface_change",
)

VALID_RISK_LEVELS = ("low", "medium", "high", "critical")

# Contract types that amplify risk when changed
_HIGH_RISK_CONTRACT_TYPES = {"grpc_service", "event_schema"}
_MEDIUM_RISK_CONTRACT_TYPES = {"query_view", "config_schema"}


class CascadeAnalyzer:
    """Analyzes cascade effects of changes across modules.

    Uses ContractRegistry to find modules that depend on the source module
    and calculates risk based on number of affected modules and contract types.
    Thread-safe, SQLite-backed.
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
            CREATE TABLE IF NOT EXISTS cascade_analyses (
                analysis_id         TEXT PRIMARY KEY,
                source_module       TEXT NOT NULL,
                change_type         TEXT NOT NULL,
                change_description  TEXT NOT NULL DEFAULT '',
                affected_modules    TEXT NOT NULL DEFAULT '[]',
                risk_level          TEXT NOT NULL DEFAULT 'low',
                created_at          REAL NOT NULL,
                metadata            TEXT
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cascade_paths (
                path_id       TEXT PRIMARY KEY,
                analysis_id   TEXT NOT NULL,
                from_module   TEXT NOT NULL,
                to_module     TEXT NOT NULL,
                path_type     TEXT NOT NULL DEFAULT 'direct',
                confidence    REAL NOT NULL DEFAULT 1.0,
                FOREIGN KEY (analysis_id) REFERENCES cascade_analyses(analysis_id)
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cascade_analyses_source "
            "ON cascade_analyses(source_module)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cascade_analyses_risk "
            "ON cascade_analyses(risk_level)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cascade_analyses_created "
            "ON cascade_analyses(created_at)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cascade_paths_analysis "
            "ON cascade_paths(analysis_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cascade_paths_from "
            "ON cascade_paths(from_module)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cascade_paths_to "
            "ON cascade_paths(to_module)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="cascade_analyzer",
            ))

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _json_dumps(value: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value, sort_keys=True, default=str)

    @staticmethod
    def _json_loads(raw: str | None, default: Any = None) -> Any:
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    def _contract_registry(self):
        """Lazy import of ContractRegistry singleton."""
        from sylion.core.contract_registry import get_contract_registry
        return get_contract_registry()

    def _find_affected_modules(self, source_module: str) -> list[dict]:
        """Find modules that depend on source_module via contracts.

        Returns a list of dicts:
            [{module: str, contract_name: str, contract_type: str}, ...]
        """
        try:
            registry = self._contract_registry()
            contracts = registry.list_all()
        except Exception:
            contracts = []

        affected: list[dict] = []
        for contract in contracts:
            producer = contract.get("producer_module", "")
            if producer != source_module:
                continue

            consumers_raw = contract.get("consumer_modules", "[]")
            if isinstance(consumers_raw, str):
                consumers_raw = json.loads(consumers_raw)
            consumers = consumers_raw if isinstance(consumers_raw, list) else []

            for consumer in consumers:
                affected.append({
                    "module": consumer,
                    "contract_name": contract.get("name", ""),
                    "contract_type": contract.get("contract_type", ""),
                })

        return affected

    def _calculate_risk(self, affected_count: int,
                        affected_info: list[dict],
                        change_type: str) -> str:
        """Determine risk level based on affected modules and change type.

        Rules:
          - interface_change with any affected modules starts at medium
          - High-risk contract types (grpc_service, event_schema) escalate risk
          - Affected module count thresholds apply
        """
        has_high_risk_contracts = any(
            info.get("contract_type", "") in _HIGH_RISK_CONTRACT_TYPES
            for info in affected_info
        )
        has_medium_risk_contracts = any(
            info.get("contract_type", "") in _MEDIUM_RISK_CONTRACT_TYPES
            for info in affected_info
        )

        # interface_change is inherently high risk
        if change_type == "interface_change":
            if affected_count >= 4:
                return "critical"
            if affected_count >= 2:
                return "high"
            if affected_count >= 1:
                return "medium"
            return "low"

        # High-risk contract types amplify
        if has_high_risk_contracts:
            if affected_count >= 4:
                return "critical"
            if affected_count >= 2:
                return "high"
            if affected_count >= 1:
                return "medium"

        # Medium-risk contract types
        if has_medium_risk_contracts:
            if affected_count >= 5:
                return "critical"
            if affected_count >= 3:
                return "high"
            if affected_count >= 2:
                return "medium"

        # Pure count-based risk
        if affected_count >= 6:
            return "critical"
        if affected_count >= 4:
            return "high"
        if affected_count >= 2:
            return "medium"
        return "low"

    def _calculate_confidence(self, contract_type: str,
                              path_type: str) -> float:
        """Calculate confidence score for a cascade path.

        Direct paths via well-typed contracts have higher confidence.
        """
        base = 1.0

        # Contract type modifiers
        if contract_type in _HIGH_RISK_CONTRACT_TYPES:
            base = 0.95
        elif contract_type in _MEDIUM_RISK_CONTRACT_TYPES:
            base = 0.85
        else:
            base = 0.75

        # Path type modifiers
        if path_type == "transitive":
            base *= 0.8

        return round(base, 2)

    @staticmethod
    def _parse_analysis_row(row: sqlite3.Row) -> dict:
        """Parse an analysis row, decoding JSON fields."""
        d = dict(row)
        for key in ("affected_modules", "metadata"):
            if d.get(key) is not None:
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_change(
        self,
        source_module: str,
        change_type: str,
        change_description: str = "",
    ) -> dict:
        """Analyze cascade effects of a change.

        Parameters
        ----------
        source_module : str
            The module where the change originates.
        change_type : str
            One of VALID_CHANGE_TYPES.
        change_description : str
            Human-readable description of the change.

        Returns
        -------
        dict
            The created analysis record with all fields parsed.

        Raises
        ------
        ValueError
            If change_type is not a valid type.
        """
        if change_type not in VALID_CHANGE_TYPES:
            raise ValueError(
                f"Invalid change_type '{change_type}'. "
                f"Must be one of {VALID_CHANGE_TYPES}"
            )

        analysis_id = self._uid()
        now = time.time()

        # Find affected modules via contract dependencies
        affected_info = self._find_affected_modules(source_module)

        # Deduplicate affected module names
        seen: set[str] = set()
        affected_modules: list[str] = []
        for info in affected_info:
            mod = info["module"]
            if mod not in seen:
                seen.add(mod)
                affected_modules.append(mod)

        # Calculate risk
        risk_level = self._calculate_risk(
            len(affected_modules), affected_info, change_type
        )

        metadata: dict[str, Any] = {
            "contract_count": len(affected_info),
            "unique_affected": len(affected_modules),
        }

        with self._lock:
            self._conn.execute("""
                INSERT INTO cascade_analyses
                (analysis_id, source_module, change_type, change_description,
                 affected_modules, risk_level, created_at, metadata)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                analysis_id, source_module, change_type, change_description,
                json.dumps(affected_modules), risk_level, now,
                self._json_dumps(metadata),
            ))
            self._conn.commit()

            # Create cascade paths for each affected module
            for info in affected_info:
                path_id = self._uid()
                contract_type = info.get("contract_type", "unknown")
                confidence = self._calculate_confidence(contract_type, "direct")

                self._conn.execute("""
                    INSERT INTO cascade_paths
                    (path_id, analysis_id, from_module, to_module,
                     path_type, confidence)
                    VALUES (?,?,?,?,?,?)
                """, (
                    path_id, analysis_id, source_module, info["module"],
                    "direct", confidence,
                ))

            # Also create transitive paths: if an affected module is itself
            # a producer, its consumers are transitively affected.
            for info in affected_info:
                transitive_info = self._find_affected_modules(info["module"])
                for ti in transitive_info:
                    target = ti["module"]
                    if target == source_module or target in seen:
                        continue
                    path_id = self._uid()
                    t_contract_type = ti.get("contract_type", "unknown")
                    t_confidence = self._calculate_confidence(
                        t_contract_type, "transitive"
                    )
                    self._conn.execute("""
                        INSERT INTO cascade_paths
                        (path_id, analysis_id, from_module, to_module,
                         path_type, confidence)
                        VALUES (?,?,?,?,?,?)
                    """, (
                        path_id, analysis_id, info["module"], target,
                        "transitive", t_confidence,
                    ))

            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM cascade_analyses WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()

        result = self._parse_analysis_row(row) if row else {
            "analysis_id": analysis_id
        }

        self._emit("cascade.analyzed", {
            "analysis_id": analysis_id,
            "source_module": source_module,
            "change_type": change_type,
            "risk_level": risk_level,
            "affected_count": len(affected_modules),
        })

        log.info(
            "cascade analysis %s: %s %s on %s affects %d modules [%s]",
            analysis_id, change_type, change_description[:40],
            source_module, len(affected_modules), risk_level,
        )
        return result

    def get_analysis(self, analysis_id: str) -> dict | None:
        """Return a single analysis record by ID, with JSON fields parsed."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cascade_analyses WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_analysis_row(row)

    def list_analyses(
        self,
        source_module: str | None = None,
        risk_level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Filtered listing of cascade analyses, ordered newest-first.

        Parameters
        ----------
        source_module : str, optional
            Filter by source module name.
        risk_level : str, optional
            Filter by risk level (low/medium/high/critical).
        limit : int
            Maximum number of records to return (default 100).

        Returns
        -------
        list[dict]
            List of analysis records with JSON fields parsed.
        """
        with self._lock:
            q = "SELECT * FROM cascade_analyses WHERE 1=1"
            params: list[Any] = []
            if source_module:
                q += " AND source_module = ?"
                params.append(source_module)
            if risk_level:
                q += " AND risk_level = ?"
                params.append(risk_level)
            q += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = self._conn.execute(q, params).fetchall()

        return [self._parse_analysis_row(r) for r in rows]

    def get_cascade_paths(self, analysis_id: str) -> list[dict]:
        """Get all cascade paths for an analysis.

        Parameters
        ----------
        analysis_id : str
            The analysis ID to get paths for.

        Returns
        -------
        list[dict]
            List of path records.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM cascade_paths WHERE analysis_id = ? "
                "ORDER BY path_type, confidence DESC",
                (analysis_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate analysis statistics.

        Returns
        -------
        dict
            {total, by_risk_level, by_change_type, avg_affected}
        """
        with self._lock:
            total_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM cascade_analyses"
            ).fetchone()
            total = total_row["cnt"] if total_row else 0

            risk_rows = self._conn.execute(
                "SELECT risk_level, COUNT(*) as cnt "
                "FROM cascade_analyses GROUP BY risk_level"
            ).fetchall()
            by_risk_level = {r["risk_level"]: r["cnt"] for r in risk_rows}

            type_rows = self._conn.execute(
                "SELECT change_type, COUNT(*) as cnt "
                "FROM cascade_analyses GROUP BY change_type"
            ).fetchall()
            by_change_type = {r["change_type"]: r["cnt"] for r in type_rows}

            path_total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM cascade_paths"
            ).fetchone()
            total_paths = path_total["cnt"] if path_total else 0

            direct_paths = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM cascade_paths "
                "WHERE path_type = 'direct'"
            ).fetchone()
            direct_count = direct_paths["cnt"] if direct_paths else 0

            transitive_paths = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM cascade_paths "
                "WHERE path_type = 'transitive'"
            ).fetchone()
            transitive_count = transitive_paths["cnt"] if transitive_paths else 0

        return {
            "total": total,
            "by_risk_level": by_risk_level,
            "by_change_type": by_change_type,
            "total_paths": total_paths,
            "direct_paths": direct_count,
            "transitive_paths": transitive_count,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_analyzer: CascadeAnalyzer | None = None


def get_cascade_analyzer(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> CascadeAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = CascadeAnalyzer(db_path, event_bus)
    return _analyzer


def reset_cascade_analyzer(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> CascadeAnalyzer:
    global _analyzer
    _analyzer = CascadeAnalyzer(db_path, event_bus)
    return _analyzer
