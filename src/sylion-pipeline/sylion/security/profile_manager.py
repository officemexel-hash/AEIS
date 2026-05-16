"""SYLION Security -- Profile Manager

Manages security profiles for hot-swap between dev-light, staging-strict,
and prod-strict modes. Tracks profile assignments per module and maintains
an audited trail of all profile changes.

SQLite-backed. Thread-safe.
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

log = logging.getLogger("sylion.security.profile_manager")

VALID_LEVELS = {"dev-light", "staging-strict", "prod-strict"}


@dataclass
class SecurityProfile:
    profile_id: str = ""
    name: str = ""
    level: str = "dev-light"
    rules: str = ""
    created_at: float = 0.0

    def __post_init__(self):
        if not self.profile_id:
            self.profile_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


class SecurityProfileManager:
    """Manages security profiles and module-to-profile assignments."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        db_path: str | Path | None = None,
    ):
        self._lock = threading.Lock()
        self._bus = event_bus or get_event_bus()
        self._db_path = str(db_path or ":memory:")
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()

    def _init_tables(self):
        cur = self._conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS security_profiles (
                profile_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                level TEXT NOT NULL DEFAULT 'dev-light',
                rules TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS module_profile_assignments (
                module_id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                assigned_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (profile_id) REFERENCES security_profiles(profile_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS profile_audit_trail (
                audit_id TEXT PRIMARY KEY,
                module_id TEXT NOT NULL,
                old_profile_id TEXT,
                new_profile_id TEXT NOT NULL,
                action TEXT NOT NULL DEFAULT 'assign',
                reason TEXT NOT NULL DEFAULT '',
                audited_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def define_profile(self, name: str, level: str, rules: dict | None = None) -> dict:
        if level not in VALID_LEVELS:
            return {"error": f"invalid level: {level}", "valid_levels": list(VALID_LEVELS)}
        profile_id = uuid.uuid4().hex
        now = time.time()
        rules_json = json.dumps(rules or {})
        with self._lock:
            self._conn.execute(
                "INSERT INTO security_profiles (profile_id, name, level, rules, created_at) VALUES (?,?,?,?,?)",
                (profile_id, name, level, rules_json, now),
            )
            self._conn.commit()
        self._emit("security.profile.defined", {"profile_id": profile_id, "name": name, "level": level})
        return {"profile_id": profile_id, "name": name, "level": level, "created_at": now}

    def get_profile(self, profile_name_or_id: str) -> dict | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT profile_id, name, level, rules, created_at FROM security_profiles WHERE profile_id = ? OR name = ?", (profile_name_or_id, profile_name_or_id)).fetchone()
        if not row:
            return None
        return {"profile_id": row[0], "name": row[1], "level": row[2], "rules": row[3], "created_at": row[4]}

    def list_profiles(self, level: str | None = None) -> list[dict]:
        cur = self._conn.cursor()
        if level:
            rows = cur.execute("SELECT profile_id, name, level, created_at FROM security_profiles WHERE level = ?", (level,)).fetchall()
        else:
            rows = cur.execute("SELECT profile_id, name, level, created_at FROM security_profiles").fetchall()
        return [{"profile_id": r[0], "name": r[1], "level": r[2], "created_at": r[3]} for r in rows]

    def assign_profile(self, module_id: str, profile_name_or_id: str) -> dict:
        profile = self.get_profile(profile_name_or_id)
        if profile is None:
            return {"error": "profile not found", "profile": profile_name_or_id}
        now = time.time()
        with self._lock:
            cur = self._conn.cursor()
            prev = cur.execute("SELECT profile_id FROM module_profile_assignments WHERE module_id = ?", (module_id,)).fetchone()
            old_pid = prev[0] if prev else None
            cur.execute(
                "INSERT OR REPLACE INTO module_profile_assignments (module_id, profile_id, assigned_at, updated_at) VALUES (?,?,?,?)",
                (module_id, profile["profile_id"], prev[1] if prev else now, now),
            )
            audit_id = uuid.uuid4().hex
            cur.execute(
                "INSERT INTO profile_audit_trail (audit_id, module_id, old_profile_id, new_profile_id, action, reason, audited_at) VALUES (?,?,?,?,?,?,?)",
                (audit_id, module_id, old_pid, profile["profile_id"], "assign", "", now),
            )
            self._conn.commit()
        self._emit("security.profile.assigned", {"module_id": module_id, "profile": profile["name"]})
        return {"module_id": module_id, "profile_id": profile["profile_id"], "profile_name": profile["name"], "assigned_at": now}

    def get_module_profile(self, module_id: str) -> dict | None:
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT mp.module_id, sp.profile_id, sp.name, sp.level, sp.rules, mp.assigned_at "
            "FROM module_profile_assignments mp JOIN security_profiles sp ON mp.profile_id = sp.profile_id "
            "WHERE mp.module_id = ?",
            (module_id,),
        ).fetchone()
        if not row:
            return None
        return {"module_id": row[0], "profile_id": row[1], "name": row[2], "level": row[3], "rules": row[4], "assigned_at": row[5]}

    def hot_swap_profile(self, module_id: str, new_profile_name_or_id: str) -> dict:
        new_profile = self.get_profile(new_profile_name_or_id)
        if new_profile is None:
            return {"error": "profile not found", "profile": new_profile_name_or_id}
        current = self.get_module_profile(module_id)
        now = time.time()
        with self._lock:
            cur = self._conn.cursor()
            old_pid = current["profile_id"] if current else None
            cur.execute(
                "INSERT OR REPLACE INTO module_profile_assignments (module_id, profile_id, assigned_at, updated_at) VALUES (?,?,?,?)",
                (module_id, new_profile["profile_id"], current["assigned_at"] if current else now, now),
            )
            audit_id = uuid.uuid4().hex
            cur.execute(
                "INSERT INTO profile_audit_trail (audit_id, module_id, old_profile_id, new_profile_id, action, reason, audited_at) VALUES (?,?,?,?,?,?,?)",
                (audit_id, module_id, old_pid, new_profile["profile_id"], "hot_swap", "profile change", now),
            )
            self._conn.commit()
        self._emit("security.profile.hot_swap", {"module_id": module_id, "old": current.get("name") if current else None, "new": new_profile["name"]})
        return {"module_id": module_id, "old_profile": current.get("name") if current else None, "new_profile": new_profile["name"], "swapped_at": now}

    def validate_profile_compliance(self, module_id: str) -> dict:
        assignment = self.get_module_profile(module_id)
        if assignment is None:
            return {"module_id": module_id, "compliant": False, "reason": "no profile assigned"}
        rules = json.loads(assignment.get("rules", "{}")) if isinstance(assignment.get("rules"), str) else {}
        return {
            "module_id": module_id,
            "compliant": True,
            "profile": assignment["name"],
            "level": assignment["level"],
            "rules_count": len(rules),
        }

    def get_audit_trail(self, module_id: str | None = None, limit: int = 100) -> list[dict]:
        cur = self._conn.cursor()
        if module_id:
            rows = cur.execute(
                "SELECT audit_id, module_id, old_profile_id, new_profile_id, action, reason, audited_at FROM profile_audit_trail WHERE module_id = ? ORDER BY audited_at DESC LIMIT ?",
                (module_id, limit),
            ).fetchall()
        else:
            rows = cur.execute(
                "SELECT audit_id, module_id, old_profile_id, new_profile_id, action, reason, audited_at FROM profile_audit_trail ORDER BY audited_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"audit_id": r[0], "module_id": r[1], "old_profile_id": r[2], "new_profile_id": r[3], "action": r[4], "reason": r[5], "audited_at": r[6]} for r in rows]

    def get_stats(self) -> dict:
        cur = self._conn.cursor()
        profiles = cur.execute("SELECT COUNT(*) FROM security_profiles").fetchone()[0]
        assignments = cur.execute("SELECT COUNT(*) FROM module_profile_assignments").fetchone()[0]
        audits = cur.execute("SELECT COUNT(*) FROM profile_audit_trail").fetchone()[0]
        hot_swaps = cur.execute("SELECT COUNT(*) FROM profile_audit_trail WHERE action = 'hot_swap'").fetchone()[0]
        return {"total_profiles": profiles, "total_assignments": assignments, "total_audit_entries": audits, "hot_swaps": hot_swaps}

    def _emit(self, event_type: str, data: dict):
        try:
            self._bus.publish(SylionEvent(event_id=uuid.uuid4().hex, event_type=event_type, source="profile_manager", data=data))
        except Exception:
            pass


_singleton: SecurityProfileManager | None = None


def get_security_profile_manager(**kwargs) -> SecurityProfileManager:
    global _singleton
    if _singleton is None:
        _singleton = SecurityProfileManager(**kwargs)
    return _singleton
