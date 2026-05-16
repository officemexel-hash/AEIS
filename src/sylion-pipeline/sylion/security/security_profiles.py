"""
SYLION Security -- Security Profiles Manager

Security profiles define named security levels with associated rules.
SQLite-backed storage with thread-safe access.

Tables:
  security_profiles -- named profiles with security levels
  profile_rules     -- rules bound to a profile

Thread-safe via threading.RLock(). Singleton via get_security_profiles() /
reset_security_profiles().  Emits events via EventBus.
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

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.security.security_profiles")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_LEVELS: tuple[str, ...] = ("low", "medium", "high", "critical")
VALID_RULE_TYPES: tuple[str, ...] = ("allow", "deny", "require", "transform")


# ---------------------------------------------------------------------------
# SecurityProfilesManager
# ---------------------------------------------------------------------------


class SecurityProfilesManager:
    """Security profiles and their associated rules.

    SQLite-backed with RLock for thread safety.  Profiles have a name,
    security level, description, and a set of rules.  Rules define allow/deny
    constraints, requirements, or transformations within a profile.
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
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS security_profiles (
                profile_id   TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                level        TEXT NOT NULL DEFAULT 'medium',
                description  TEXT NOT NULL DEFAULT '',
                rules_json   TEXT NOT NULL DEFAULT '[]',
                created_at   REAL NOT NULL DEFAULT 0.0,
                updated_at   REAL NOT NULL DEFAULT 0.0,
                is_active    INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS profile_rules (
                rule_id      TEXT PRIMARY KEY,
                profile_id   TEXT NOT NULL,
                rule_name    TEXT NOT NULL,
                rule_type    TEXT NOT NULL DEFAULT 'allow',
                config_json  TEXT NOT NULL DEFAULT '{}',
                created_at   REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sp_profiles_name ON security_profiles(name)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sp_profiles_level ON security_profiles(level)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sp_profiles_active ON security_profiles(is_active)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sp_rules_profile ON profile_rules(profile_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sp_rules_type ON profile_rules(rule_type)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return dict(row)

    def _parse_json(self, raw: str) -> Any:
        try:
            return json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="security.security_profiles",
            ))

    # ------------------------------------------------------------------
    # Profile CRUD
    # ------------------------------------------------------------------

    def create_profile(self, name: str, level: str = "medium",
                       description: str = "",
                       rules_json: Any = None) -> dict:
        """Create a new security profile. Returns profile dict.

        Raises ValueError if level is invalid.
        """
        if level not in VALID_LEVELS:
            raise ValueError(
                f"Invalid level '{level}'. Must be one of {VALID_LEVELS}"
            )

        profile_id = uuid.uuid4().hex
        now = time.time()
        rules_str = json.dumps(rules_json or [], default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO security_profiles
                    (profile_id, name, level, description, rules_json,
                     created_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (profile_id, name, level, description, rules_str, now, now))
            self._conn.commit()

        self._emit("profile_created", {
            "profile_id": profile_id,
            "name": name,
            "level": level,
        })
        log.info("created security profile %s (level=%s)", name, level)
        return {
            "profile_id": profile_id,
            "name": name,
            "level": level,
            "description": description,
            "rules_json": rules_json or [],
            "created_at": now,
            "updated_at": now,
            "is_active": 1,
        }

    def update_profile(self, profile_id: str, name: str | None = None,
                       level: str | None = None,
                       description: str | None = None,
                       rules_json: Any = None) -> dict | None:
        """Update profile fields. Returns updated profile dict or None."""
        if level is not None and level not in VALID_LEVELS:
            raise ValueError(
                f"Invalid level '{level}'. Must be one of {VALID_LEVELS}"
            )

        sets: list[str] = []
        params: list[Any] = []

        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if level is not None:
            sets.append("level = ?")
            params.append(level)
        if description is not None:
            sets.append("description = ?")
            params.append(description)
        if rules_json is not None:
            sets.append("rules_json = ?")
            params.append(json.dumps(rules_json, default=str))

        if not sets:
            return self.get_profile(profile_id)

        sets.append("updated_at = ?")
        params.append(time.time())
        params.append(profile_id)

        with self._lock:
            n = self._conn.execute(
                f"UPDATE security_profiles SET {', '.join(sets)} WHERE profile_id = ?",
                params,
            ).rowcount
            self._conn.commit()

        if not n:
            return None

        self._emit("profile_updated", {"profile_id": profile_id})
        log.info("updated security profile %s", profile_id[:12])
        return self.get_profile(profile_id)

    def delete_profile(self, profile_id: str) -> bool:
        """Soft-delete a profile (set is_active=0). Returns True if deleted."""
        with self._lock:
            n = self._conn.execute(
                "UPDATE security_profiles SET is_active = 0, updated_at = ? "
                "WHERE profile_id = ? AND is_active = 1",
                (time.time(), profile_id),
            ).rowcount
            self._conn.commit()

        if n:
            log.info("deleted security profile %s", profile_id[:12])
        return bool(n)

    def get_profile(self, profile_id: str):
        """Retrieve a profile by profile_id or hardened name.

        Stored DB profiles are returned as dict for back-compat. Hardened
        defaults (dev-light/standard/prod-strict) match by name and return
        a SimpleNamespace with .name/.level/.rules so that
        /api/v1/security/hardened-profiles/{name} can dot-access them.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM security_profiles WHERE profile_id = ? OR "
                "(name = ? AND is_active = 1) LIMIT 1",
                (profile_id, profile_id),
            ).fetchone()
        if row:
            d = self._row_to_dict(row)
            d["rules_json"] = self._parse_json(d.get("rules_json", "[]"))
            return d
        # Fall back to hardened defaults (only when called by name)
        if profile_id in self._HARDENED_DEFAULTS:
            level, rules = self._HARDENED_DEFAULTS[profile_id]
            return self._profile_view(profile_id, level, rules)
        return None

    def list_profiles(self, level: str | None = None) -> list[dict]:
        """List profiles, optionally filtered by level."""
        conditions: list[str] = []
        params: list[Any] = []

        if level is not None:
            conditions.append("level = ?")
            params.append(level)

        where = "WHERE is_active = 1"
        if conditions:
            where += " AND " + " AND ".join(conditions)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM security_profiles {where} ORDER BY created_at",
                params,
            ).fetchall()
        results = []
        for r in rows:
            d = self._row_to_dict(r)
            d["rules_json"] = self._parse_json(d.get("rules_json", "[]"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Hardened-profile selector (active by name)
    # ------------------------------------------------------------------

    def _ensure_active_state_table(self):
        """Ensure the singleton-row active-profile-name table exists."""
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS active_profile_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    profile_name TEXT NOT NULL DEFAULT 'standard',
                    updated_at REAL NOT NULL DEFAULT 0.0
                )
            """)
            self._conn.commit()

    @staticmethod
    def _profile_view(name: str, level: str = "medium",
                      rules: list | None = None):
        """Return a SimpleNamespace view -- routes access .name/.level/.rules."""
        from types import SimpleNamespace
        return SimpleNamespace(name=name, level=level, rules=list(rules or []))

    _HARDENED_DEFAULTS = {
        "dev-light":   ("low",      [{"rule": "allow_all", "scope": "*"}]),
        "standard":    ("medium",   [{"rule": "audit_required", "scope": "*"}]),
        "prod-strict": ("critical", [{"rule": "deny_unverified", "scope": "*"},
                                     {"rule": "encrypt_at_rest", "scope": "*"}]),
    }

    def get_active_profile(self):
        """Return the currently active hardened profile (SimpleNamespace).

        Used by GET /api/v1/security/hardened-profiles/active. The
        attribute-style API (.name/.level/.rules) is what the route emits.
        Looks up the recorded active name in active_profile_state, falling
        back to 'standard' if no row is present.
        """
        self._ensure_active_state_table()
        with self._lock:
            row = self._conn.execute(
                "SELECT profile_name FROM active_profile_state WHERE id = 1"
            ).fetchone()
        name = row["profile_name"] if row else "standard"
        # Prefer a stored profile matching the name; otherwise use the
        # hardened default. This keeps the API stable even on a fresh DB.
        with self._lock:
            db_row = self._conn.execute(
                "SELECT * FROM security_profiles WHERE name = ? AND is_active = 1 "
                "ORDER BY created_at LIMIT 1",
                (name,),
            ).fetchone()
        if db_row:
            d = self._row_to_dict(db_row)
            rules = self._parse_json(d.get("rules_json", "[]"))
            return self._profile_view(d["name"], d.get("level", "medium"),
                                      rules if isinstance(rules, list) else [])
        level, rules = self._HARDENED_DEFAULTS.get(
            name, self._HARDENED_DEFAULTS["standard"]
        )
        return self._profile_view(name, level, rules)

    def set_active_profile(self, name: str) -> dict:
        """Set the active hardened profile by name. Used by route POST.

        Accepts any of the 3 hardened defaults or a stored profile name.
        Returns {success, message, name}.
        """
        if not name or not isinstance(name, str):
            return {"success": False, "message": "name is required",
                    "name": name}
        # Allow either a known hardened default or any stored profile.
        if name not in self._HARDENED_DEFAULTS:
            with self._lock:
                row = self._conn.execute(
                    "SELECT profile_id FROM security_profiles "
                    "WHERE name = ? AND is_active = 1 LIMIT 1",
                    (name,),
                ).fetchone()
            if not row:
                return {"success": False,
                        "message": f"Profile '{name}' is not a known hardened "
                                   f"profile and is not stored",
                        "name": name}
        self._ensure_active_state_table()
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO active_profile_state (id, profile_name, updated_at) "
                "VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET profile_name = excluded.profile_name, "
                "updated_at = excluded.updated_at",
                (name, now),
            )
            self._conn.commit()
        self._emit("profile.active_changed",
                   {"name": name, "updated_at": now})
        return {"success": True,
                "message": f"Active profile set to '{name}'",
                "name": name}

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------

    def add_rule(self, profile_id: str, rule_name: str,
                 rule_type: str = "allow",
                 config_json: Any = None) -> dict:
        """Add a rule to a profile. Returns rule dict.

        Raises ValueError if profile does not exist or rule_type is invalid.
        """
        profile = self.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"Profile '{profile_id}' does not exist")
        if rule_type not in VALID_RULE_TYPES:
            raise ValueError(
                f"Invalid rule_type '{rule_type}'. Must be one of {VALID_RULE_TYPES}"
            )

        rule_id = uuid.uuid4().hex
        now = time.time()
        config_str = json.dumps(config_json or {}, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO profile_rules
                    (rule_id, profile_id, rule_name, rule_type, config_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (rule_id, profile_id, rule_name, rule_type, config_str, now))
            self._conn.commit()

        log.info("added rule %s to profile %s", rule_name, profile_id[:12])
        return {
            "rule_id": rule_id,
            "profile_id": profile_id,
            "rule_name": rule_name,
            "rule_type": rule_type,
            "config_json": config_json or {},
            "created_at": now,
        }

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule. Returns True if removed."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM profile_rules WHERE rule_id = ?",
                (rule_id,),
            ).rowcount
            self._conn.commit()

        if n:
            log.info("removed rule %s", rule_id[:12])
        return bool(n)

    def get_rules(self, profile_id: str) -> list[dict]:
        """List all rules for a profile."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM profile_rules WHERE profile_id = ? ORDER BY created_at",
                (profile_id,),
            ).fetchall()
        results = []
        for r in rows:
            d = self._row_to_dict(r)
            d["config_json"] = self._parse_json(d.get("config_json", "{}"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_profile(self, profile_id: str,
                         context_json: Any = None) -> dict:
        """Evaluate a profile against a context. Returns evaluation result.

        Checks each rule against the provided context and returns pass/fail
        with details on any violations.
        """
        profile = self.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"Profile '{profile_id}' does not exist")

        context = context_json or {}
        rules = self.get_rules(profile_id)
        now = time.time()

        violations: list[dict] = []
        passed = 0

        for rule in rules:
            rule_type = rule["rule_type"]
            config = rule["config_json"]

            if rule_type == "deny":
                denied_keys = config.get("keys", [])
                for key in denied_keys:
                    if key in context:
                        violations.append({
                            "rule_id": rule["rule_id"],
                            "rule_name": rule["rule_name"],
                            "reason": f"Denied key '{key}' present in context",
                        })
                    else:
                        passed += 1
            elif rule_type == "require":
                required_keys = config.get("keys", [])
                for key in required_keys:
                    if key not in context:
                        violations.append({
                            "rule_id": rule["rule_id"],
                            "rule_name": rule["rule_name"],
                            "reason": f"Required key '{key}' missing from context",
                        })
                    else:
                        passed += 1
            else:
                passed += 1

        result = {
            "profile_id": profile_id,
            "profile_name": profile["name"],
            "level": profile["level"],
            "evaluated_at": now,
            "total_rules": len(rules),
            "passed": passed,
            "violations": violations,
            "compliant": len(violations) == 0,
        }

        self._emit("profile_evaluated", {
            "profile_id": profile_id,
            "compliant": result["compliant"],
            "violation_count": len(violations),
        })
        return result

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_profile_stats(self) -> dict:
        """Return aggregate statistics about profiles and rules."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM security_profiles"
            ).fetchone()[0]
            active = self._conn.execute(
                "SELECT COUNT(*) FROM security_profiles WHERE is_active = 1"
            ).fetchone()[0]
            total_rules = self._conn.execute(
                "SELECT COUNT(*) FROM profile_rules"
            ).fetchone()[0]

            level_rows = self._conn.execute(
                "SELECT level, COUNT(*) as cnt FROM security_profiles "
                "WHERE is_active = 1 GROUP BY level"
            ).fetchall()
            by_level = {r["level"]: r["cnt"] for r in level_rows}

        return {
            "total_profiles": total,
            "active_profiles": active,
            "total_rules": total_rules,
            "by_level": by_level,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: SecurityProfilesManager | None = None


def get_security_profiles(db_path: str | Path | None = None,
                          event_bus: EventBus | None = None) -> SecurityProfilesManager:
    """Get or create the global SecurityProfilesManager singleton."""
    global _manager
    if _manager is None:
        _manager = SecurityProfilesManager(db_path, event_bus)
    return _manager


def reset_security_profiles(db_path: str | Path | None = None,
                            event_bus: EventBus | None = None) -> SecurityProfilesManager:
    """Reset the global SecurityProfilesManager singleton (for testing)."""
    global _manager
    _manager = SecurityProfilesManager(db_path, event_bus)
    return _manager


# Alias kept for ``sylion.api.security_routes`` which imports
# ``get_security_profile_manager`` (singular) and re-exports it as
# ``get_hardened_profile_manager``. Without this name being importable
# the /api/v1/security/hardened-profiles routes 501-out.
def get_security_profile_manager(db_path: str | Path | None = None,
                                 event_bus: EventBus | None = None) -> SecurityProfilesManager:
    return get_security_profiles(db_path, event_bus)
