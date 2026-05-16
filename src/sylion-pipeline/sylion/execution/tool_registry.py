"""
SYLION Execution — Tool Registry

Central registry for tool definitions with risk-level authorization,
deprecation lifecycle, and decision-class gating.

Phase 1: SQLite-backed with WAL mode, thread-safe via threading.Lock.
Phase 2: gRPC tool catalog (same interface, config swap).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.execution.tool_registry")


# ---------------------------------------------------------------------------
# Risk levels
# ---------------------------------------------------------------------------

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Authorization matrix: which risk levels are allowed at each decision class.
# Higher D-class = higher autonomy threshold, so high-risk tools need D3+.
_RISK_AUTHORIZATION: dict[RiskLevel, set[str]] = {
    RiskLevel.LOW:      {"D0", "D1", "D2", "D3", "D4", "D5"},
    RiskLevel.MEDIUM:   {"D1", "D2", "D3", "D4", "D5"},
    RiskLevel.HIGH:     {"D2", "D3", "D4", "D5"},
    RiskLevel.CRITICAL: {"D3", "D4", "D5"},
}


# ---------------------------------------------------------------------------
# Tool descriptor
# ---------------------------------------------------------------------------

@dataclass
class ToolDefinition:
    """Registered tool descriptor."""
    tool_id: str
    name: str
    description: str = ""
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"
    category: str = ""
    deprecated: bool = False
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.updated_at:
            self.updated_at = self.created_at


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Central tool definition registry.

    SQLite-backed, thread-safe, singleton via get_tool_registry().
    Emits events to EventBus on tool lifecycle changes.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_tools (
                tool_id            TEXT PRIMARY KEY,
                name               TEXT NOT NULL,
                description        TEXT NOT NULL DEFAULT '',
                parameters_schema  TEXT NOT NULL DEFAULT '{}',
                risk_level         TEXT NOT NULL DEFAULT 'low',
                category           TEXT NOT NULL DEFAULT '',
                deprecated         INTEGER NOT NULL DEFAULT 0,
                created_at         REAL NOT NULL,
                updated_at         REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tools_risk ON sylion_tools(risk_level)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tools_category ON sylion_tools(category)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tools_deprecated ON sylion_tools(deprecated)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # register_tool
    # ------------------------------------------------------------------

    def register_tool(self, tool_id: str, name: str, description: str = "",
                      parameters_schema: dict[str, Any] | None = None,
                      risk_level: str = "low",
                      category: str = "") -> dict:
        """Register a new tool. Returns tool descriptor dict.

        Args:
            tool_id: Unique tool identifier (e.g. "tool.web_search").
            name: Human-readable tool name.
            description: What the tool does.
            parameters_schema: JSON-schema-style parameter definition.
            risk_level: One of low, medium, high, critical.
            category: Optional grouping category.

        Raises:
            ValueError: If risk_level is invalid.
        """
        if parameters_schema is None:
            parameters_schema = {}

        # Validate risk level
        try:
            RiskLevel(risk_level)
        except ValueError:
            raise ValueError(
                f"Invalid risk_level '{risk_level}'. "
                f"Must be one of: {', '.join(r.value for r in RiskLevel)}"
            )

        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO sylion_tools
                (tool_id, name, description, parameters_schema, risk_level,
                 category, deprecated, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (
                tool_id, name, description,
                json.dumps(parameters_schema, default=str),
                risk_level, category, now, now,
            ))
            self._conn.commit()

        self._emit("execution.tool_registry.registered", {
            "tool_id": tool_id, "name": name, "risk_level": risk_level,
            "category": category,
        })

        log.info("registered tool %s (%s) risk=%s", tool_id, name, risk_level)
        return {
            "tool_id": tool_id, "name": name, "risk_level": risk_level,
            "category": category,
        }

    # ------------------------------------------------------------------
    # get_tool
    # ------------------------------------------------------------------

    def get_tool(self, tool_id: str) -> dict | None:
        """Get a single tool definition by ID.

        Returns dict with all fields or None if not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sylion_tools WHERE tool_id = ?", (tool_id,),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["parameters_schema"] = json.loads(result.get("parameters_schema", "{}"))
            result["deprecated"] = bool(result["deprecated"])
            return result

    # ------------------------------------------------------------------
    # list_tools
    # ------------------------------------------------------------------

    def list_tools(self, category: str | None = None,
                   risk_level: str | None = None) -> list[dict]:
        """List tools, optionally filtered by category and/or risk_level.

        Returns list of tool descriptor dicts, excluding deprecated by default.
        """
        q = "SELECT * FROM sylion_tools WHERE 1=1"
        params: list[Any] = []

        if category:
            q += " AND category = ?"
            params.append(category)
        if risk_level:
            q += " AND risk_level = ?"
            params.append(risk_level)

        q += " ORDER BY name"

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["parameters_schema"] = json.loads(d.get("parameters_schema", "{}"))
                d["deprecated"] = bool(d["deprecated"])
                results.append(d)
            return results

    # ------------------------------------------------------------------
    # update_tool
    # ------------------------------------------------------------------

    def update_tool(self, tool_id: str, **kwargs) -> dict:
        """Update tool metadata fields.

        Accepted kwargs: name, description, parameters_schema, risk_level, category.

        Returns updated tool descriptor or {"updated": False, ...} if not found.
        """
        allowed = {"name", "description", "parameters_schema", "risk_level", "category"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}

        if not updates:
            return {"updated": False, "message": "No updatable fields provided"}

        # Validate risk_level if present
        if "risk_level" in updates:
            try:
                RiskLevel(updates["risk_level"])
            except ValueError:
                raise ValueError(
                    f"Invalid risk_level '{updates['risk_level']}'. "
                    f"Must be one of: {', '.join(r.value for r in RiskLevel)}"
                )

        # Serialize parameters_schema if present
        if "parameters_schema" in updates:
            updates["parameters_schema"] = json.dumps(
                updates["parameters_schema"], default=str
            )

        updates["updated_at"] = time.time()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [tool_id]

        with self._lock:
            row = self._conn.execute(
                "SELECT tool_id FROM sylion_tools WHERE tool_id = ?", (tool_id,),
            ).fetchone()
            if not row:
                return {"updated": False, "message": f"Tool {tool_id} not found"}

            self._conn.execute(
                f"UPDATE sylion_tools SET {set_clause} WHERE tool_id = ?",
                values,
            )
            self._conn.commit()

        self._emit("execution.tool_registry.updated", {
            "tool_id": tool_id, "fields": list(kwargs.keys()),
        })

        log.info("updated tool %s: %s", tool_id, list(kwargs.keys()))
        return {"updated": True, "tool_id": tool_id, "fields": list(kwargs.keys())}

    # ------------------------------------------------------------------
    # deprecate_tool
    # ------------------------------------------------------------------

    def deprecate_tool(self, tool_id: str) -> dict:
        """Mark a tool as deprecated.

        Deprecated tools are still queryable via get_tool but excluded
        from authorization checks by default.

        Returns {"deprecated": True, ...} or error dict.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT tool_id, deprecated FROM sylion_tools WHERE tool_id = ?",
                (tool_id,),
            ).fetchone()
            if not row:
                return {"deprecated": False, "message": f"Tool {tool_id} not found"}
            if row["deprecated"]:
                return {"deprecated": False, "message": f"Tool {tool_id} already deprecated"}

            now = time.time()
            self._conn.execute(
                "UPDATE sylion_tools SET deprecated = 1, updated_at = ? WHERE tool_id = ?",
                (now, tool_id),
            )
            self._conn.commit()

        self._emit("execution.tool_registry.deprecated", {
            "tool_id": tool_id,
        })

        log.info("deprecated tool %s", tool_id)
        return {"deprecated": True, "tool_id": tool_id}

    # ------------------------------------------------------------------
    # check_authorization
    # ------------------------------------------------------------------

    def check_authorization(self, tool_id: str, decision_class: str) -> dict:
        """Check if a tool can be used at a given decision class level.

        Args:
            tool_id: The tool to check.
            decision_class: D0-D5 decision class.

        Returns dict with:
            - authorized: bool
            - tool_id, decision_class
            - risk_level of the tool
            - reason (if not authorized)
        """
        tool = self.get_tool(tool_id)
        if tool is None:
            return {
                "authorized": False, "tool_id": tool_id,
                "decision_class": decision_class,
                "reason": f"Tool {tool_id} not found",
            }

        if tool["deprecated"]:
            return {
                "authorized": False, "tool_id": tool_id,
                "decision_class": decision_class,
                "risk_level": tool["risk_level"],
                "reason": f"Tool {tool_id} is deprecated",
            }

        risk = tool["risk_level"]
        try:
            risk_enum = RiskLevel(risk)
        except ValueError:
            return {
                "authorized": False, "tool_id": tool_id,
                "decision_class": decision_class,
                "risk_level": risk,
                "reason": f"Invalid risk_level '{risk}' on tool",
            }

        allowed_classes = _RISK_AUTHORIZATION.get(risk_enum, set())
        if decision_class in allowed_classes:
            return {
                "authorized": True, "tool_id": tool_id,
                "decision_class": decision_class,
                "risk_level": risk,
            }
        else:
            return {
                "authorized": False, "tool_id": tool_id,
                "decision_class": decision_class,
                "risk_level": risk,
                "reason": f"Risk level '{risk}' requires higher decision class "
                          f"(allowed: {', '.join(sorted(allowed_classes))})",
            }

    # ------------------------------------------------------------------
    # get_stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns dict with:
            - total: total registered tools
            - by_category: {category: count, ...}
            - by_risk_level: {risk_level: count, ...}
            - deprecated_count: number of deprecated tools
        """
        with self._lock:
            rows = self._conn.execute("SELECT * FROM sylion_tools").fetchall()

            by_category: dict[str, int] = {}
            by_risk_level: dict[str, int] = {}
            deprecated_count = 0

            for r in rows:
                cat = r["category"] or "uncategorized"
                by_category[cat] = by_category.get(cat, 0) + 1

                rl = r["risk_level"]
                by_risk_level[rl] = by_risk_level.get(rl, 0) + 1

                if r["deprecated"]:
                    deprecated_count += 1

            return {
                "total": len(rows),
                "by_category": by_category,
                "by_risk_level": by_risk_level,
                "deprecated_count": deprecated_count,
            }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="execution.tool_registry",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_registry: ToolRegistry | None = None


def get_tool_registry(db_path: str | Path | None = None,
                      event_bus: EventBus | None = None) -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry(db_path, event_bus)
    return _registry
