"""
SYLION Surface -- Console UI

Component and layout registry for the SYLION console interface.
Manages UI component definitions, panel layouts, and role-based visibility.

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

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

log = logging.getLogger("sylion.surface.console_ui")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class UIComponent:
    """A registered UI component."""
    component_id: str = ""
    name: str = ""
    panel: str = ""
    component_type: str = "panel"
    config: dict[str, Any] = field(default_factory=dict)
    order_num: int = 0
    active: int = 1

    def __post_init__(self):
        if not self.component_id:
            self.component_id = uuid.uuid4().hex


@dataclass
class UILayout:
    """A saved UI layout configuration."""
    layout_id: str = ""
    name: str = ""
    panels: list[str] = field(default_factory=list)
    role: str = "viewer"
    active: int = 1

    def __post_init__(self):
        if not self.layout_id:
            self.layout_id = uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Console UI
# ---------------------------------------------------------------------------

class ConsoleUI:
    """Component and layout registry for console interface.

    Thread-safe. SQLite-backed. Emits events to EventBus.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS ui_components (
                component_id   TEXT PRIMARY KEY,
                name           TEXT NOT NULL DEFAULT '',
                panel          TEXT NOT NULL DEFAULT '',
                component_type TEXT NOT NULL DEFAULT 'panel',
                config         TEXT NOT NULL DEFAULT '{}',
                order_num      INTEGER NOT NULL DEFAULT 0,
                active         INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS ui_layouts (
                layout_id TEXT PRIMARY KEY,
                name      TEXT NOT NULL DEFAULT '',
                panels    TEXT NOT NULL DEFAULT '[]',
                role      TEXT NOT NULL DEFAULT 'viewer',
                active    INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_uicomp_panel ON ui_components(panel)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_uilay_role ON ui_layouts(role)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Component management
    # ------------------------------------------------------------------

    def register_component(self, name: str, panel: str = "",
                           component_type: str = "panel",
                           config: dict[str, Any] | None = None,
                           order_num: int = 0) -> dict:
        """Register a UI component. Returns component descriptor dict."""
        if config is None:
            config = {}

        comp = UIComponent(
            name=name,
            panel=panel,
            component_type=component_type,
            config=config,
            order_num=order_num,
        )

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO ui_components
                    (component_id, name, panel, component_type, config,
                     order_num, active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (
                comp.component_id, comp.name, comp.panel,
                comp.component_type, json.dumps(config, default=str),
                comp.order_num,
            ))
            self._conn.commit()

        self._emit("surface.console_ui.component_registered", {
            "component_id": comp.component_id,
            "name": name, "component_type": component_type,
        })

        log.info("registered UI component %s (%s)", comp.component_id[:12], name)
        return {"component_id": comp.component_id, "name": name}

    # ------------------------------------------------------------------
    # Layout management
    # ------------------------------------------------------------------

    def create_layout(self, name: str, panels: list[str] | None = None,
                      role: str = "viewer") -> dict:
        """Create a UI layout. Returns layout descriptor dict."""
        if panels is None:
            panels = []

        layout = UILayout(
            name=name,
            panels=panels,
            role=role,
        )

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO ui_layouts
                    (layout_id, name, panels, role, active)
                VALUES (?, ?, ?, ?, 1)
            """, (
                layout.layout_id, layout.name,
                json.dumps(panels), layout.role,
            ))
            self._conn.commit()

        self._emit("surface.console_ui.layout_created", {
            "layout_id": layout.layout_id,
            "name": name, "role": role,
        })

        log.info("created UI layout %s (%s)", layout.layout_id[:12], name)
        return {"layout_id": layout.layout_id, "name": name}

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_layout(self, layout_id: str) -> dict | None:
        """Get a single layout by ID."""
        row = self._conn.execute(
            "SELECT * FROM ui_layouts WHERE layout_id = ?", (layout_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["panels"] = json.loads(result.get("panels", "[]"))
        return result

    def list_components(self, panel: str | None = None,
                        active_only: bool = True,
                        limit: int = 100) -> list[dict]:
        """List UI components, optionally filtered by panel."""
        query = "SELECT * FROM ui_components WHERE 1=1"
        params: list[Any] = []
        if panel:
            query += " AND panel = ?"
            params.append(panel)
        if active_only:
            query += " AND active = 1"
        query += " ORDER BY order_num, name LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["config"] = json.loads(d.get("config", "{}"))
            results.append(d)
        return results

    def list_layouts(self, role: str | None = None,
                     active_only: bool = True,
                     limit: int = 100) -> list[dict]:
        """List UI layouts, optionally filtered by role."""
        query = "SELECT * FROM ui_layouts WHERE 1=1"
        params: list[Any] = []
        if role:
            query += " AND role = ?"
            params.append(role)
        if active_only:
            query += " AND active = 1"
        query += " ORDER BY name LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["panels"] = json.loads(d.get("panels", "[]"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="surface.console_ui",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_ui: ConsoleUI | None = None


def get_console_ui(db_path: str | Path | None = None,
                   event_bus: EventBus | None = None) -> ConsoleUI:
    global _ui
    if _ui is None:
        _ui = ConsoleUI(db_path, event_bus)
    return _ui
