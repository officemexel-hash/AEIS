"""
SYLION Governance -- Roles Manager

Manages roles, permissions, and role assignments for SYLION users.
Supports creating roles with permission lists, assigning roles to users,
and checking permissions.

Thread-safe. SQLite-backed. EventBus integration.
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

log = logging.getLogger("sylion.governance.roles")


# ---------------------------------------------------------------------------
# RolesManager
# ---------------------------------------------------------------------------

class RolesManager:
    """Role-based access control manager.

    Manages roles with associated permissions and user assignments.
    Supports checking if a user has a specific permission through
    their role assignments.
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
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    role_id      TEXT PRIMARY KEY,
                    name         TEXT NOT NULL UNIQUE,
                    description  TEXT NOT NULL DEFAULT '',
                    created_at   REAL NOT NULL,
                    updated_at   REAL NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS role_permissions (
                    permission_id TEXT PRIMARY KEY,
                    role_id       TEXT NOT NULL,
                    permission    TEXT NOT NULL,
                    granted_at    REAL NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS role_assignments (
                    assignment_id TEXT PRIMARY KEY,
                    role_id       TEXT NOT NULL,
                    user_id       TEXT NOT NULL,
                    assigned_by   TEXT NOT NULL DEFAULT '',
                    assigned_at   REAL NOT NULL
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_roles_name "
                "ON roles(name)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_permissions_role "
                "ON role_permissions(role_id)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_permissions_perm "
                "ON role_permissions(permission)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_assignments_role "
                "ON role_assignments(role_id)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_assignments_user "
                "ON role_assignments(user_id)"
            )
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_assignments_unique "
                "ON role_assignments(role_id, user_id)"
            )
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_permissions_unique "
                "ON role_permissions(role_id, permission)"
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Role CRUD
    # ------------------------------------------------------------------

    def create_role(self, name: str, description: str = "",
                    permissions_list: list[str] | None = None) -> dict:
        """Create a new role with optional permissions.

        Args:
            name: Role name (must be unique).
            description: Human-readable description.
            permissions_list: List of permission strings.

        Returns:
            Dict with role details.
        """
        if not name or not name.strip():
            raise ValueError("Role name must not be empty.")

        role_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            existing = self._conn.execute(
                "SELECT role_id FROM roles WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                raise ValueError(f"Role with name '{name}' already exists.")

            self._conn.execute("""
                INSERT INTO roles (role_id, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (role_id, name, description, now, now))

            if permissions_list:
                for perm in permissions_list:
                    pid = uuid.uuid4().hex
                    self._conn.execute("""
                        INSERT INTO role_permissions
                        (permission_id, role_id, permission, granted_at)
                        VALUES (?, ?, ?, ?)
                    """, (pid, role_id, perm, now))

            self._conn.commit()

        self._emit("role_created", {
            "role_id": role_id,
            "name": name,
            "permissions": permissions_list or [],
        })

        log.info("created role %s (%s) with %d permissions",
                 role_id, name, len(permissions_list or []))

        return {
            "role_id": role_id,
            "name": name,
            "description": description,
            "permissions": permissions_list or [],
            "created_at": now,
            "updated_at": now,
        }

    def update_role(self, role_id: str, *,
                    name: str | None = None,
                    description: str | None = None) -> dict | None:
        """Update role metadata (not permissions -- use add/remove for that)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM roles WHERE role_id = ?", (role_id,)
            ).fetchone()
            if not row:
                return None

            new_name = name if name is not None else row["name"]
            new_desc = description if description is not None else row["description"]
            now = time.time()

            # Check name uniqueness if changing
            if name is not None and name != row["name"]:
                existing = self._conn.execute(
                    "SELECT role_id FROM roles WHERE name = ? AND role_id != ?",
                    (name, role_id),
                ).fetchone()
                if existing:
                    raise ValueError(f"Role with name '{name}' already exists.")

            self._conn.execute("""
                UPDATE roles SET name = ?, description = ?, updated_at = ?
                WHERE role_id = ?
            """, (new_name, new_desc, now, role_id))
            self._conn.commit()

        perms = self._get_role_permissions(role_id)

        self._emit("role_updated", {
            "role_id": role_id,
            "name": new_name,
        })

        return {
            "role_id": role_id,
            "name": new_name,
            "description": new_desc,
            "permissions": perms,
            "created_at": row["created_at"],
            "updated_at": now,
        }

    def delete_role(self, role_id: str) -> bool:
        """Delete a role and all associated permissions/assignments."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM roles WHERE role_id = ?", (role_id,)
            )
            self._conn.execute(
                "DELETE FROM role_permissions WHERE role_id = ?", (role_id,)
            )
            self._conn.execute(
                "DELETE FROM role_assignments WHERE role_id = ?", (role_id,)
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def get_role(self, role_id: str) -> dict | None:
        """Retrieve a role with its permissions."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM roles WHERE role_id = ?", (role_id,)
            ).fetchone()
            if not row:
                return None

        perms = self._get_role_permissions(role_id)
        d = dict(row)
        d["permissions"] = perms
        return d

    def list_roles(self) -> list[dict]:
        """List all roles with their permissions."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM roles ORDER BY created_at ASC"
            ).fetchall()

        result = []
        for row in rows:
            d = dict(row)
            d["permissions"] = self._get_role_permissions(row["role_id"])
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # Permission management
    # ------------------------------------------------------------------

    def add_permission(self, role_id: str, permission: str) -> bool:
        """Add a permission to a role. Returns True if added."""
        with self._lock:
            row = self._conn.execute(
                "SELECT role_id FROM roles WHERE role_id = ?", (role_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Role '{role_id}' not found.")

            existing = self._conn.execute(
                "SELECT permission_id FROM role_permissions "
                "WHERE role_id = ? AND permission = ?",
                (role_id, permission),
            ).fetchone()
            if existing:
                return False

            pid = uuid.uuid4().hex
            now = time.time()
            self._conn.execute("""
                INSERT INTO role_permissions
                (permission_id, role_id, permission, granted_at)
                VALUES (?, ?, ?, ?)
            """, (pid, role_id, permission, now))
            self._conn.commit()
            return True

    def remove_permission(self, role_id: str, permission: str) -> bool:
        """Remove a permission from a role. Returns True if removed."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM role_permissions "
                "WHERE role_id = ? AND permission = ?",
                (role_id, permission),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def _get_role_permissions(self, role_id: str) -> list[str]:
        """Get all permission strings for a role."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT permission FROM role_permissions WHERE role_id = ?",
                (role_id,),
            ).fetchall()
        return [r["permission"] for r in rows]

    # ------------------------------------------------------------------
    # Assignment management
    # ------------------------------------------------------------------

    def assign_role(self, role_id: str, user_id: str,
                    assigned_by: str = "") -> dict:
        """Assign a role to a user.

        Args:
            role_id: Role to assign.
            user_id: User to assign to.
            assigned_by: ID of the user performing the assignment.

        Returns:
            Dict with assignment details.
        """
        with self._lock:
            role = self._conn.execute(
                "SELECT * FROM roles WHERE role_id = ?", (role_id,)
            ).fetchone()
            if not role:
                raise ValueError(f"Role '{role_id}' not found.")

            existing = self._conn.execute(
                "SELECT assignment_id FROM role_assignments "
                "WHERE role_id = ? AND user_id = ?",
                (role_id, user_id),
            ).fetchone()
            if existing:
                return {
                    "assignment_id": existing["assignment_id"],
                    "role_id": role_id,
                    "user_id": user_id,
                    "assigned_by": assigned_by,
                    "already_assigned": True,
                }

            assignment_id = uuid.uuid4().hex
            now = time.time()
            self._conn.execute("""
                INSERT INTO role_assignments
                (assignment_id, role_id, user_id, assigned_by, assigned_at)
                VALUES (?, ?, ?, ?, ?)
            """, (assignment_id, role_id, user_id, assigned_by, now))
            self._conn.commit()

        self._emit("role_assigned", {
            "assignment_id": assignment_id,
            "role_id": role_id,
            "user_id": user_id,
            "assigned_by": assigned_by,
        })

        log.info("assigned role %s to user %s", role_id, user_id)

        return {
            "assignment_id": assignment_id,
            "role_id": role_id,
            "user_id": user_id,
            "assigned_by": assigned_by,
            "assigned_at": now,
            "already_assigned": False,
        }

    def revoke_assignment(self, assignment_id: str) -> bool:
        """Revoke a role assignment. Returns True if revoked."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM role_assignments WHERE assignment_id = ?",
                (assignment_id,),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def get_user_roles(self, user_id: str) -> list[dict]:
        """Get all roles assigned to a user."""
        with self._lock:
            rows = self._conn.execute("""
                SELECT r.role_id, r.name, r.description, a.assignment_id, a.assigned_at
                FROM roles r
                JOIN role_assignments a ON r.role_id = a.role_id
                WHERE a.user_id = ?
                ORDER BY a.assigned_at ASC
            """, (user_id,)).fetchall()

        result = []
        for row in rows:
            d = dict(row)
            d["permissions"] = self._get_role_permissions(row["role_id"])
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # Permission checking
    # ------------------------------------------------------------------

    def check_permission(self, user_id: str, permission: str) -> bool:
        """Check if a user has a specific permission through any role.

        Args:
            user_id: User to check.
            permission: Permission string to check.

        Returns:
            True if the user has the permission, False otherwise.
        """
        with self._lock:
            result = self._conn.execute("""
                SELECT 1 FROM role_assignments a
                JOIN role_permissions p ON a.role_id = p.role_id
                WHERE a.user_id = ? AND p.permission = ?
                LIMIT 1
            """, (user_id, permission)).fetchone()

        has_permission = result is not None

        self._emit("permission_checked", {
            "user_id": user_id,
            "permission": permission,
            "granted": has_permission,
        })

        return has_permission

    def get_user_permissions(self, user_id: str) -> list[str]:
        """Get all permissions a user has through their roles."""
        with self._lock:
            rows = self._conn.execute("""
                SELECT DISTINCT p.permission
                FROM role_assignments a
                JOIN role_permissions p ON a.role_id = p.role_id
                WHERE a.user_id = ?
                ORDER BY p.permission
            """, (user_id,)).fetchall()
        return [r["permission"] for r in rows]

    # ------------------------------------------------------------------
    # Agent registry (workspace vocabulary)
    # ------------------------------------------------------------------
    # The dashboard surfaces a separate "agents" view distinct from the
    # role-assignment model: each agent has a name, a department, a level
    # and a list of skills. Backed by an `agents` table.

    def _ensure_agents_table(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id    TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    department  TEXT NOT NULL DEFAULT '',
                    level       INTEGER NOT NULL DEFAULT 1,
                    skills_json TEXT NOT NULL DEFAULT '[]',
                    permissions_json TEXT NOT NULL DEFAULT '[]',
                    active      INTEGER NOT NULL DEFAULT 1,
                    created_at  REAL NOT NULL
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agents_department "
                "ON agents(department)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agents_active "
                "ON agents(active)"
            )
            self._conn.commit()

    @staticmethod
    def _row_to_agent_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            d["skills"] = json.loads(d.pop("skills_json", "[]"))
        except (json.JSONDecodeError, TypeError):
            d["skills"] = []
        try:
            d["permissions"] = json.loads(d.pop("permissions_json", "[]"))
        except (json.JSONDecodeError, TypeError):
            d["permissions"] = []
        d["active"] = bool(d.get("active"))
        return d

    def register(self, role) -> dict:
        """Register an agent role. Accepts AgentRole dataclass or dict."""
        self._ensure_agents_table()
        if hasattr(role, "name") and not isinstance(role, dict):
            name = role.name
            dept = getattr(role, "department", "")
            if hasattr(dept, "value"):
                dept = dept.value
            level = getattr(role, "level", 1)
            skills = list(getattr(role, "skills", []) or [])
            agent_id = getattr(role, "agent_id", "") or uuid.uuid4().hex
        elif isinstance(role, dict):
            name = role.get("name", "")
            dept = role.get("department", "")
            level = int(role.get("level", 1))
            skills = list(role.get("skills", []) or [])
            agent_id = role.get("agent_id", "") or uuid.uuid4().hex
        else:
            raise ValueError("register expects AgentRole-like object or dict")

        if not name:
            raise ValueError("agent name must be non-empty")

        with self._lock:
            existing = self._conn.execute(
                "SELECT agent_id FROM agents WHERE name = ? AND active = 1",
                (name,),
            ).fetchone()
            if existing:
                raise ValueError(f"agent with name '{name}' already registered")
            now = time.time()
            self._conn.execute(
                "INSERT INTO agents (agent_id, name, department, level, "
                "skills_json, permissions_json, active, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                (agent_id, name, dept, level,
                 json.dumps(skills, default=str),
                 json.dumps([], default=str), now),
            )
            self._conn.commit()

        self._emit("roles.agent_registered", {
            "agent_id": agent_id, "name": name, "department": dept,
        })
        return self.get(agent_id) or {}

    def list_agents(self, department: str | None = None,
                    active_only: bool = True) -> list[dict]:
        self._ensure_agents_table()
        clauses: list[str] = []
        params: list[Any] = []
        if department is not None:
            clauses.append("department = ?")
            params.append(department)
        if active_only:
            clauses.append("active = 1")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM agents{where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        return [self._row_to_agent_dict(r) for r in rows]

    def get(self, agent_id: str) -> dict | None:
        self._ensure_agents_table()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM agents WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
        return self._row_to_agent_dict(row) if row else None

    def deregister(self, agent_id: str) -> bool:
        self._ensure_agents_table()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE agents SET active = 0 WHERE agent_id = ? AND active = 1",
                (agent_id,),
            )
            self._conn.commit()
        if cur.rowcount > 0:
            self._emit("roles.agent_deregistered", {"agent_id": agent_id})
            return True
        return False

    def grant_permission(self, agent_id: str, permission) -> dict:
        self._ensure_agents_table()
        perm = permission.value if hasattr(permission, "value") else str(permission)
        agent = self.get(agent_id)
        if not agent:
            raise ValueError(f"agent {agent_id} not found")
        perms = list(agent.get("permissions", []))
        if perm not in perms:
            perms.append(perm)
        with self._lock:
            self._conn.execute(
                "UPDATE agents SET permissions_json = ? WHERE agent_id = ?",
                (json.dumps(perms, default=str), agent_id),
            )
            self._conn.commit()
        self._emit("roles.permission_granted", {
            "agent_id": agent_id, "permission": perm,
        })
        return self.get(agent_id) or {}

    def revoke_permission(self, agent_id: str, permission) -> dict:
        self._ensure_agents_table()
        perm = permission.value if hasattr(permission, "value") else str(permission)
        agent = self.get(agent_id)
        if not agent:
            raise ValueError(f"agent {agent_id} not found")
        perms = [p for p in agent.get("permissions", []) if p != perm]
        with self._lock:
            self._conn.execute(
                "UPDATE agents SET permissions_json = ? WHERE agent_id = ?",
                (json.dumps(perms, default=str), agent_id),
            )
            self._conn.commit()
        self._emit("roles.permission_revoked", {
            "agent_id": agent_id, "permission": perm,
        })
        return self.get(agent_id) or {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="governance.roles",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: RolesManager | None = None


def get_roles_manager(db_path: str | Path | None = None,
                      event_bus: EventBus | None = None) -> RolesManager:
    """Return the global RolesManager singleton."""
    global _manager
    if _manager is None:
        _manager = RolesManager(db_path, event_bus)
    return _manager


def reset_roles_manager() -> None:
    """Reset the global singleton (for testing)."""
    global _manager
    _manager = None


# ---------------------------------------------------------------------------
# Workspace dataclasses & enums
# ---------------------------------------------------------------------------
from dataclasses import dataclass, field
from enum import Enum


class Department(str, Enum):
    ENGINEERING = "engineering"
    ARCHITECTURE = "architecture"
    EFFICIENCY = "efficiency"
    SECURITY = "security"
    OPERATIONS = "operations"
    GOVERNANCE = "governance"


@dataclass
class AgentRole:
    """Workspace-vocabulary agent role record.

    Used by ``POST /api/v1/governance/roles`` to register agents with a
    department, level, and skill set. Persisted by RolesManager.register().
    """
    name: str
    department: Department | str = Department.ENGINEERING
    level: int = 1
    skills: list[str] = field(default_factory=list)
    agent_id: str = ""


class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


get_roles_registry = get_roles_manager
reset_roles_registry = reset_roles_manager
