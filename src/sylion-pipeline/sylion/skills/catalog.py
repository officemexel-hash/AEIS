"""
SYLION Skills -- Standard Skills Catalog

Manages a browsable catalog of skills organized by category, domain, and tags.
Provides search, filtering, and recommendation capabilities.

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

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.skills.catalog")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

VALID_CATEGORIES = (
    "kernel", "contract", "scaffold", "test", "governance",
    "efficiency", "ui", "skill", "aeis", "infra", "custom",
)


SEED_SKILL_MANIFESTS: tuple[dict[str, Any], ...] = (
    {
        "skill_id": "seed.echo",
        "name": "seed.echo",
        "version": "1.0.0",
        "description": "Echo the provided text back to the caller.",
        "category": "skill",
        "domain": "seed",
        "tags": ["seed", "demo", "text"],
        "author": "B-ADAPT",
        "compatibility": "runtime-v1",
        "owner_role": "operator",
        "entry_point": "sylion.skills.catalog:seed_echo_handler",
        "inputs": [{"name": "text", "type": "string", "required": True}],
        "outputs": [{"name": "output", "type": "string"}],
        "steps": [
            "Read the text payload.",
            "Return the exact same text as output.",
        ],
        "safety_rules": [
            "No filesystem writes.",
            "No network calls.",
        ],
    },
    {
        "skill_id": "seed.tokenize",
        "name": "seed.tokenize",
        "version": "1.0.0",
        "description": "Split text into whitespace-delimited tokens.",
        "category": "skill",
        "domain": "seed",
        "tags": ["seed", "demo", "nlp"],
        "author": "B-ADAPT",
        "compatibility": "runtime-v1",
        "owner_role": "operator",
        "entry_point": "sylion.skills.catalog:seed_tokenize_handler",
        "inputs": [{"name": "text", "type": "string", "required": True}],
        "outputs": [{"name": "tokens", "type": "array"}],
        "steps": [
            "Read the text payload.",
            "Split the text on whitespace boundaries.",
        ],
        "safety_rules": [
            "No filesystem writes.",
            "No network calls.",
        ],
    },
    {
        "skill_id": "seed.summarize",
        "name": "seed.summarize",
        "version": "1.0.0",
        "description": "Produce a compact summary from the first sentence or first 12 words.",
        "category": "skill",
        "domain": "seed",
        "tags": ["seed", "demo", "summary"],
        "author": "B-ADAPT",
        "compatibility": "runtime-v1",
        "owner_role": "operator",
        "entry_point": "sylion.skills.catalog:seed_summarize_handler",
        "inputs": [{"name": "text", "type": "string", "required": True}],
        "outputs": [{"name": "summary", "type": "string"}],
        "steps": [
            "Read the text payload.",
            "Extract the first sentence when present.",
            "Fallback to the first 12 words when there is no sentence boundary.",
        ],
        "safety_rules": [
            "No filesystem writes.",
            "No network calls.",
        ],
    },
)


def get_seed_skill_manifests() -> list[dict[str, Any]]:
    """Return deep-copied seed skill manifest definitions."""

    return json.loads(json.dumps(SEED_SKILL_MANIFESTS))


def seed_catalog_entries() -> list[dict[str, Any]]:
    """Return catalog-facing metadata for the built-in seed skills."""

    entries = []
    for manifest in get_seed_skill_manifests():
        entries.append({
            "skill_id": manifest["skill_id"],
            "name": manifest["name"],
            "category": manifest.get("category", "skill"),
            "domain": manifest.get("domain", ""),
            "description": manifest.get("description", ""),
            "tags": manifest.get("tags", []),
            "author": manifest.get("author", ""),
            "compatibility": manifest.get("compatibility", ""),
        })
    return entries


def seed_echo_handler(inputs: dict[str, Any]) -> str:
    """Return the text payload unchanged."""

    return str(inputs.get("text", ""))


def seed_tokenize_handler(inputs: dict[str, Any]) -> list[str]:
    """Split text into whitespace-delimited tokens."""

    text = str(inputs.get("text", "")).strip()
    return text.split() if text else []


def seed_summarize_handler(inputs: dict[str, Any]) -> str:
    """Return a compact summary from the first sentence or first 12 words."""

    text = str(inputs.get("text", "")).strip()
    if not text:
        return ""
    sentence = text.split(".", 1)[0].strip()
    if sentence:
        return sentence
    words = text.split()
    if len(words) <= 12:
        return text
    return " ".join(words[:12]) + "..."


@dataclass
class CatalogEntry:
    """A skill catalog entry."""
    entry_id: str = ""
    skill_id: str = ""
    name: str = ""
    category: str = "custom"
    domain: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    compatibility: str = ""
    rating: float = 0.0
    usage_count: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.entry_id:
            self.entry_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()
        if not self.updated_at:
            self.updated_at = self.created_at


# ---------------------------------------------------------------------------
# Skills Catalog
# ---------------------------------------------------------------------------

class SkillsCatalog:
    """Standard skills catalog with category browsing and search.

    Thread-safe. SQLite-backed. Emits events on mutations.
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
            CREATE TABLE IF NOT EXISTS catalog_entries (
                entry_id      TEXT PRIMARY KEY,
                skill_id      TEXT    NOT NULL,
                name          TEXT    NOT NULL,
                category      TEXT    NOT NULL DEFAULT 'custom',
                domain        TEXT    NOT NULL DEFAULT '',
                tags          TEXT    NOT NULL DEFAULT '[]',
                description   TEXT    NOT NULL DEFAULT '',
                version       TEXT    NOT NULL DEFAULT '1.0.0',
                author        TEXT    NOT NULL DEFAULT '',
                compatibility TEXT    NOT NULL DEFAULT '',
                rating        REAL    NOT NULL DEFAULT 0,
                usage_count   INTEGER NOT NULL DEFAULT 0,
                created_at    REAL    NOT NULL,
                updated_at    REAL    NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_catalog_category ON catalog_entries(category)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_catalog_domain ON catalog_entries(domain)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_catalog_skill ON catalog_entries(skill_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_catalog_name ON catalog_entries(name)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Add / Update
    # ------------------------------------------------------------------

    def add(self, skill_id: str, name: str, category: str = "custom",
            domain: str = "", description: str = "", tags: list[str] | None = None,
            author: str = "", compatibility: str = "") -> dict:
        """Add a skill to the catalog.

        Emits ``skill.catalog.added``.
        """
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category: {category}. Must be one of {VALID_CATEGORIES}")

        if tags is None:
            tags = []

        entry = CatalogEntry(
            skill_id=skill_id,
            name=name,
            category=category,
            domain=domain,
            tags=tags,
            description=description,
            author=author,
            compatibility=compatibility,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO catalog_entries
                    (entry_id, skill_id, name, category, domain, tags,
                     description, version, author, compatibility,
                     rating, usage_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.entry_id, entry.skill_id, entry.name,
                entry.category, entry.domain, json.dumps(tags),
                entry.description, entry.version, entry.author,
                entry.compatibility, entry.rating, entry.usage_count,
                entry.created_at, entry.updated_at,
            ))
            self._conn.commit()

        self._emit("skill.catalog.added", {
            "entry_id": entry.entry_id,
            "skill_id": skill_id,
            "name": name,
            "category": category,
        })

        log.info("added skill %s to catalog: %s [%s]", skill_id, name, category)
        return {
            "entry_id": entry.entry_id,
            "skill_id": skill_id,
            "name": name,
            "category": category,
        }

    def update(self, entry_id: str, **kwargs) -> dict:
        """Update catalog entry fields.

        Emits ``skill.catalog.updated``.
        """
        row = self._conn.execute(
            "SELECT * FROM catalog_entries WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Entry {entry_id} not found")

        allowed = {"name", "category", "domain", "description", "tags",
                    "version", "author", "compatibility", "rating"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}

        if not updates:
            return {"entry_id": entry_id, "updated": False}

        if "tags" in updates and isinstance(updates["tags"], list):
            updates["tags"] = json.dumps(updates["tags"])

        if "category" in updates and updates["category"] not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category: {updates['category']}")

        updates["updated_at"] = time.time()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [entry_id]

        with self._lock:
            self._conn.execute(
                f"UPDATE catalog_entries SET {set_clause} WHERE entry_id = ?",
                values,
            )
            self._conn.commit()

        self._emit("skill.catalog.updated", {
            "entry_id": entry_id,
            "fields": list(kwargs.keys()),
        })

        return {"entry_id": entry_id, "updated": True, "fields": list(kwargs.keys())}

    def remove(self, entry_id: str) -> dict:
        """Remove a catalog entry.

        Emits ``skill.catalog.removed``.
        """
        row = self._conn.execute(
            "SELECT skill_id FROM catalog_entries WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Entry {entry_id} not found")

        with self._lock:
            self._conn.execute(
                "DELETE FROM catalog_entries WHERE entry_id = ?",
                (entry_id,),
            )
            self._conn.commit()

        self._emit("skill.catalog.removed", {
            "entry_id": entry_id,
            "skill_id": row["skill_id"],
        })

        return {"entry_id": entry_id, "removed": True}

    # ------------------------------------------------------------------
    # Browsing
    # ------------------------------------------------------------------

    def browse(self, category: str | None = None,
               domain: str | None = None,
               tag: str | None = None,
               limit: int = 100) -> list[dict]:
        """Browse catalog entries with optional filters."""
        q = "SELECT * FROM catalog_entries WHERE 1=1"
        params: list[Any] = []

        if category:
            q += " AND category = ?"
            params.append(category)
        if domain:
            q += " AND domain = ?"
            params.append(domain)
        if tag:
            q += " AND tags LIKE ?"
            params.append(f'%"{tag}"%')

        q += " ORDER BY usage_count DESC, rating DESC, created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(q, params).fetchall()
        return self._rows_to_dicts(rows)

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Search catalog by name, description, or tags."""
        pattern = f"%{query}%"
        rows = self._conn.execute("""
            SELECT * FROM catalog_entries
            WHERE name LIKE ? OR description LIKE ? OR tags LIKE ?
            ORDER BY rating DESC, usage_count DESC
            LIMIT ?
        """, (pattern, pattern, pattern, limit)).fetchall()
        return self._rows_to_dicts(rows)

    def get(self, entry_id: str) -> dict | None:
        """Return a single catalog entry."""
        row = self._conn.execute(
            "SELECT * FROM catalog_entries WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def get_by_skill(self, skill_id: str) -> dict | None:
        """Return catalog entry by skill_id."""
        row = self._conn.execute(
            "SELECT * FROM catalog_entries WHERE skill_id = ?",
            (skill_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def track_usage(self, entry_id: str) -> dict:
        """Increment usage count for a catalog entry."""
        with self._lock:
            self._conn.execute(
                "UPDATE catalog_entries SET usage_count = usage_count + 1, updated_at = ? WHERE entry_id = ?",
                (time.time(), entry_id),
            )
            self._conn.commit()
        return {"entry_id": entry_id, "tracked": True}

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def recommend(self, domain: str | None = None,
                  category: str | None = None,
                  limit: int = 10) -> list[dict]:
        """Recommend top-rated skills, optionally filtered."""
        q = "SELECT * FROM catalog_entries WHERE 1=1"
        params: list[Any] = []
        if domain:
            q += " AND domain = ?"
            params.append(domain)
        if category:
            q += " AND category = ?"
            params.append(category)
        q += " ORDER BY rating DESC, usage_count DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(q, params).fetchall()
        return self._rows_to_dicts(rows)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate catalog statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM catalog_entries"
        ).fetchone()["cnt"]

        by_cat_rows = self._conn.execute(
            "SELECT category, COUNT(*) as cnt FROM catalog_entries GROUP BY category"
        ).fetchall()
        by_category = {r["category"]: r["cnt"] for r in by_cat_rows}

        by_domain_rows = self._conn.execute(
            "SELECT domain, COUNT(*) as cnt FROM catalog_entries GROUP BY domain"
        ).fetchall()
        by_domain = {r["domain"]: r["cnt"] for r in by_domain_rows}

        top_rated = self._rows_to_dicts(
            self._conn.execute(
                "SELECT * FROM catalog_entries ORDER BY rating DESC LIMIT 5"
            ).fetchall()
        )

        return {
            "total_entries": total,
            "by_category": by_category,
            "by_domain": by_domain,
            "top_rated": top_rated,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _row_to_dict(self, row) -> dict:
        d = dict(row)
        d["tags"] = json.loads(d.get("tags", "[]"))
        return d

    def _rows_to_dicts(self, rows) -> list[dict]:
        return [self._row_to_dict(r) for r in rows]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="skills.catalog",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_catalog: SkillsCatalog | None = None


def get_skills_catalog(db_path: str | Path | None = None,
                       event_bus: EventBus | None = None) -> SkillsCatalog:
    global _catalog
    if _catalog is None:
        _catalog = SkillsCatalog(db_path, event_bus)
    return _catalog
