"""
SYLION Cognitive -- Prompt Template Manager

CRUD + versioning for reusable prompt templates with {variable} placeholders.
Supports categories, team/project scoping, import/export, search, and stats.

Thread-safe. SQLite-backed. Emits events on mutations.

Tables:
  prompt_templates          -- current template versions
  prompt_template_versions  -- version history snapshots

Singleton: get_prompt_template_manager() / reset_prompt_template_manager()
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.cognitive.prompt_templates")


class PromptTemplateManager:
    """Prompt template CRUD with variable extraction, versioning, and search.

    Every template stores ``{variable}`` placeholders extracted automatically
    from the *content* field.  On update the version counter is bumped and
    the previous row is archived to ``prompt_template_versions``.
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
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS prompt_templates (
                template_id   TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                description   TEXT NOT NULL DEFAULT '',
                content       TEXT NOT NULL,
                variables     TEXT NOT NULL DEFAULT '[]',
                category      TEXT NOT NULL DEFAULT '',
                team_id       TEXT NOT NULL DEFAULT '',
                project_id    TEXT NOT NULL DEFAULT '',
                version       INTEGER NOT NULL DEFAULT 1,
                is_active     INTEGER NOT NULL DEFAULT 1,
                created_by    TEXT NOT NULL DEFAULT '',
                created_at    REAL NOT NULL,
                updated_at    REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS prompt_template_versions (
                version_id    TEXT PRIMARY KEY,
                template_id   TEXT NOT NULL,
                name          TEXT NOT NULL,
                description   TEXT NOT NULL DEFAULT '',
                content       TEXT NOT NULL,
                variables     TEXT NOT NULL DEFAULT '[]',
                category      TEXT NOT NULL DEFAULT '',
                team_id       TEXT NOT NULL DEFAULT '',
                project_id    TEXT NOT NULL DEFAULT '',
                version       INTEGER NOT NULL,
                created_by    TEXT NOT NULL DEFAULT '',
                created_at    REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_pt_category
                ON prompt_templates(category);
            CREATE INDEX IF NOT EXISTS idx_pt_team_project
                ON prompt_templates(team_id, project_id);
            CREATE INDEX IF NOT EXISTS idx_pt_active
                ON prompt_templates(is_active);
            CREATE INDEX IF NOT EXISTS idx_ptv_template
                ON prompt_template_versions(template_id);
        """)
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
                source_module="cognitive.prompt_templates",
            ))

    @staticmethod
    def _extract_variables(content: str) -> list[str]:
        """Extract sorted unique ``{variable}`` placeholders from *content*."""
        return sorted(set(re.findall(r"\{(\w+)\}", content)))

    @staticmethod
    def _parse_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        for key in ("variables",):
            if d.get(key) is not None:
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    def _archive_version(self, template_id: str):
        """Copy current template row into the versions archive table."""
        row = self._conn.execute(
            "SELECT * FROM prompt_templates WHERE template_id = ?",
            (template_id,),
        ).fetchone()
        if row is None:
            return
        d = dict(row)
        version_id = self._uid()
        self._conn.execute(
            "INSERT INTO prompt_template_versions "
            "(version_id, template_id, name, description, content, variables, "
            " category, team_id, project_id, version, created_by, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                version_id, d["template_id"], d["name"], d["description"],
                d["content"], d["variables"], d["category"], d["team_id"],
                d["project_id"], d["version"], d["created_by"], d["created_at"],
            ),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_template(
        self,
        name: str,
        content: str,
        description: str | None = None,
        category: str | None = None,
        team_id: str | None = None,
        project_id: str | None = None,
        created_by: str | None = None,
    ) -> dict:
        """Create a new prompt template.

        Auto-extracts ``{variable}`` placeholders from *content* and stores
        them as a JSON array in the ``variables`` column.
        """
        template_id = self._uid()
        now = time.time()
        variables = self._extract_variables(content)

        with self._lock:
            self._conn.execute(
                "INSERT INTO prompt_templates "
                "(template_id, name, description, content, variables, category, "
                " team_id, project_id, version, is_active, created_by, "
                " created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?, 1,1,?,?,?)",
                (
                    template_id, name, description or "", content,
                    json.dumps(variables), category or "",
                    team_id or "", project_id or "",
                    created_by or "",
                    now, now,
                ),
            )
            self._conn.commit()

        result = {
            "template_id": template_id,
            "name": name,
            "description": description or "",
            "content": content,
            "variables": variables,
            "category": category or "",
            "team_id": team_id or "",
            "project_id": project_id or "",
            "version": 1,
            "is_active": 1,
            "created_by": created_by or "",
            "created_at": now,
            "updated_at": now,
        }

        self._emit("template.created", {"template_id": template_id, "name": name})
        log.info("created template %s (id=%s)", name, template_id)
        return result

    def update_template(self, template_id: str, **kwargs) -> dict | None:
        """Update mutable fields on a template.  Bumps version.

        Accepted kwargs: name, description, content, category, team_id,
        project_id, created_by.

        If *content* is supplied the variables are re-extracted.
        Returns ``None`` if the template does not exist.
        """
        allowed = {
            "name", "description", "content", "category",
            "team_id", "project_id", "created_by",
        }
        updates: dict[str, Any] = {}
        for key, value in kwargs.items():
            if key in allowed:
                updates[key] = value

        if not updates:
            return self.get_template(template_id)

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                "SELECT * FROM prompt_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()
            if row is None:
                self._conn.rollback()
                return None

            # Archive the current version before modifying
            self._archive_version(template_id)

            # Re-extract variables if content changed
            if "content" in updates:
                updates["variables"] = json.dumps(
                    self._extract_variables(updates["content"])
                )

            now = time.time()
            updates["updated_at"] = now

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [template_id]
            self._conn.execute(
                f"UPDATE prompt_templates SET version = version + 1, "
                f"{set_clause} WHERE template_id = ?",
                values,
            )
            self._conn.commit()

            updated_row = self._conn.execute(
                "SELECT * FROM prompt_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()

        result = self._parse_row(updated_row)
        self._emit("template.updated", {
            "template_id": template_id,
            "version": result["version"],
        })
        log.info("updated template %s to version %d", template_id, result["version"])
        return result

    def get_template(self, template_id: str) -> dict | None:
        """Return a single template by ID (includes inactive)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM prompt_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_row(row)

    def list_templates(
        self,
        category: str | None = None,
        team_id: str | None = None,
        project_id: str | None = None,
        is_active: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List templates with optional filters and pagination."""
        clauses: list[str] = []
        params: list[Any] = []
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if team_id is not None:
            clauses.append("team_id = ?")
            params.append(team_id)
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if is_active is not None:
            clauses.append("is_active = ?")
            params.append(is_active)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            f"SELECT * FROM prompt_templates{where} "
            f"ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._parse_row(r) for r in rows]

    def resolve_template(self, template_id: str, variables: dict) -> str:
        """Substitute ``{var}`` placeholders with the supplied values.

        Raises ``ValueError`` if the template does not exist or a required
        variable is missing from the *variables* dict.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT content, variables FROM prompt_templates "
                "WHERE template_id = ? AND is_active = 1",
                (template_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Template '{template_id}' not found or inactive")

        content: str = row["content"]
        required: list[str] = json.loads(row["variables"])

        missing = [v for v in required if v not in variables]
        if missing:
            raise ValueError(
                f"Missing required variable(s): {', '.join(missing)}"
            )

        for key, value in variables.items():
            content = content.replace("{" + key + "}", str(value))

        self._emit("template.resolved", {
            "template_id": template_id,
        })
        return content

    def delete_template(self, template_id: str) -> bool:
        """Soft-delete a template (set ``is_active = 0``).

        Returns ``True`` if the template was found and deactivated.
        """
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT template_id FROM prompt_templates "
                "WHERE template_id = ? AND is_active = 1",
                (template_id,),
            ).fetchone()
            if row is None:
                return False
            self._conn.execute(
                "UPDATE prompt_templates SET is_active = 0, updated_at = ? "
                "WHERE template_id = ?",
                (now, template_id),
            )
            self._conn.commit()

        self._emit("template.deleted", {"template_id": template_id})
        log.info("soft-deleted template %s", template_id)
        return True

    def duplicate_template(
        self, template_id: str, new_name: str | None = None
    ) -> dict | None:
        """Clone a template.  Version resets to 1 on the copy."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM prompt_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()
            if row is None:
                return None

            d = dict(row)
            new_id = self._uid()
            now = time.time()
            name = new_name or (d["name"] + " (copy)")
            self._conn.execute(
                "INSERT INTO prompt_templates "
                "(template_id, name, description, content, variables, category, "
                " team_id, project_id, version, is_active, created_by, "
                " created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?, 1,1,?,?,?)",
                (
                    new_id, name, d["description"], d["content"],
                    d["variables"], d["category"],
                    d["team_id"], d["project_id"],
                    d["created_by"],
                    now, now,
                ),
            )
            self._conn.commit()

        result = self.get_template(new_id)
        self._emit("template.created", {"template_id": new_id, "name": name})
        log.info("duplicated template %s -> %s", template_id, new_id)
        return result

    def get_template_versions(self, template_id: str) -> list[dict]:
        """Return version history for a template, oldest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM prompt_template_versions "
                "WHERE template_id = ? ORDER BY version ASC",
                (template_id,),
            ).fetchall()
        return [self._parse_row(r) for r in rows]

    def search_templates(self, query: str) -> list[dict]:
        """Search templates by name, description, or content (case-insensitive)."""
        pattern = f"%{query}%"
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM prompt_templates "
                "WHERE (name LIKE ? OR description LIKE ? OR content LIKE ?) "
                "AND is_active = 1 ORDER BY updated_at DESC",
                (pattern, pattern, pattern),
            ).fetchall()
        return [self._parse_row(r) for r in rows]

    def get_categories(self) -> list[str]:
        """Return distinct non-empty categories."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT category FROM prompt_templates "
                "WHERE category != '' AND is_active = 1 ORDER BY category"
            ).fetchall()
        return [r["category"] for r in rows]

    def get_template_stats(self) -> dict:
        """Return summary statistics."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM prompt_templates"
            ).fetchone()["cnt"]

            active = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM prompt_templates WHERE is_active = 1"
            ).fetchone()["cnt"]

            cat_rows = self._conn.execute(
                "SELECT category, COUNT(*) as cnt FROM prompt_templates "
                "WHERE is_active = 1 GROUP BY category"
            ).fetchall()
            by_category = {r["category"]: r["cnt"] for r in cat_rows}

            team_rows = self._conn.execute(
                "SELECT team_id, COUNT(*) as cnt FROM prompt_templates "
                "WHERE is_active = 1 GROUP BY team_id"
            ).fetchall()
            by_team = {r["team_id"]: r["cnt"] for r in team_rows}

        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "by_category": by_category,
            "by_team": by_team,
        }

    def export_template(self, template_id: str) -> str:
        """Export a template as a JSON string."""
        tpl = self.get_template(template_id)
        if tpl is None:
            raise ValueError(f"Template '{template_id}' not found")
        return json.dumps(tpl, indent=2, sort_keys=True, default=str)

    def import_template(self, json_str: str, overwrite: bool = False) -> dict:
        """Import a template from a JSON string.

        If *overwrite* is ``True`` and a template with the same
        ``template_id`` already exists, it will be updated.  Otherwise a
        new ID is generated.
        """
        data = json.loads(json_str)

        # Validate required fields
        if "name" not in data or "content" not in data:
            raise ValueError("Import JSON must contain at least 'name' and 'content'")

        existing_id = data.get("template_id")

        if overwrite and existing_id:
            existing = self.get_template(existing_id)
            if existing is not None:
                kwargs: dict[str, Any] = {
                    "name": data["name"],
                    "content": data["content"],
                }
                for field in ("description", "category", "team_id", "project_id",
                              "created_by"):
                    if field in data:
                        kwargs[field] = data[field]
                result = self.update_template(existing_id, **kwargs)
                if result is not None:
                    return result

        # Create new (generate fresh ID)
        return self.create_template(
            name=data["name"],
            content=data["content"],
            description=data.get("description"),
            category=data.get("category"),
            team_id=data.get("team_id"),
            project_id=data.get("project_id"),
            created_by=data.get("created_by"),
        )


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: PromptTemplateManager | None = None


def get_prompt_template_manager(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> PromptTemplateManager:
    global _manager
    if _manager is None:
        _manager = PromptTemplateManager(db_path, event_bus)
    return _manager


def reset_prompt_template_manager(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> PromptTemplateManager:
    global _manager
    _manager = PromptTemplateManager(db_path, event_bus)
    return _manager
