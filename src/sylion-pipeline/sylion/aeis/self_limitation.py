"""
SYLION AEIS -- Self-Limitation Engine (Rate Limiting)

Enforces rate-limit policies on system actions by scope.
Tracks action events, violations, and explicit throttle cooldowns.

SQLite-backed with WAL mode. Thread-safe via threading.Lock.
Singleton via get_self_limitation_engine(). Emits events via EventBus.

Tables:
  sylion_rate_policies — registered rate-limit policies
  sylion_rate_events   — action events and violation records
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.aeis.self_limitation")


# ---------------------------------------------------------------------------
# Self-Limitation Engine
# ---------------------------------------------------------------------------

class SelfLimitationEngine:
    """Rate-limit policy engine for self-limitation.

    Thread-safe. SQLite-backed. Emits events on check, violation, and throttle.
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
            self._conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_rate_policies (
                policy_id      TEXT PRIMARY KEY,
                scope          TEXT    NOT NULL,
                max_calls      INTEGER NOT NULL DEFAULT 1,
                window_seconds REAL    NOT NULL DEFAULT 60.0,
                action         TEXT    NOT NULL DEFAULT 'throttle',
                created_at     REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_rate_events (
                event_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                scope          TEXT    NOT NULL,
                identifier     TEXT    NOT NULL,
                action         TEXT    NOT NULL DEFAULT '',
                result         TEXT    NOT NULL DEFAULT '',
                is_violation   INTEGER NOT NULL DEFAULT 0,
                details        TEXT    NOT NULL DEFAULT '{}',
                timestamp      REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_named_policies (
                policy_id    TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                description  TEXT NOT NULL DEFAULT '',
                category     TEXT NOT NULL DEFAULT 'safety',
                threshold    REAL NOT NULL DEFAULT 0.0,
                unit         TEXT NOT NULL DEFAULT '',
                enabled      INTEGER NOT NULL DEFAULT 1,
                created_at   REAL NOT NULL,
                updated_at   REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_named_violations (
                violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id    TEXT NOT NULL,
                value        REAL NOT NULL DEFAULT 0.0,
                severity     TEXT NOT NULL DEFAULT 'warning',
                details      TEXT NOT NULL DEFAULT '{}',
                recorded_at  REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_named_pol_cat "
            "ON sylion_named_policies(category)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_named_viol_pol "
            "ON sylion_named_violations(policy_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_named_viol_ts "
            "ON sylion_named_violations(recorded_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rate_policy_scope "
            "ON sylion_rate_policies(scope)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rate_event_scope_id "
            "ON sylion_rate_events(scope, identifier)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rate_event_ts "
            "ON sylion_rate_events(timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rate_event_violation "
            "ON sylion_rate_events(is_violation)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Register policy
    # ------------------------------------------------------------------

    def register_policy(self, policy_id: str, scope_or_name: str,
                        max_calls: int | None = None,
                        window_seconds: float | None = None,
                        action: str = "throttle",
                        *,
                        description: str | None = None,
                        category: str | None = None,
                        threshold: float | None = None,
                        unit: str | None = None) -> dict:
        """Register a policy. Polymorphic by kwargs:

        - Rate-limit style: register_policy(policy_id, scope,
          max_calls, window_seconds, action) — existing 8-test behavior.
        - Named-policy style: register_policy(policy_id, name,
          description=..., category=..., threshold=..., unit=...) —
          used by /api/v1/aeis/limitations/policies.

        The two are stored in separate tables and queried by separate
        helpers (list_rate_policies vs list_policies).
        """
        is_named = any(x is not None for x in
                       (description, category, threshold, unit))
        if is_named:
            return self._register_named_policy(
                policy_id, scope_or_name,
                description=description or "",
                category=category or "safety",
                threshold=threshold if threshold is not None else 0.0,
                unit=unit or "",
            )
        if max_calls is None or window_seconds is None:
            raise ValueError(
                "rate-style register_policy requires max_calls and "
                "window_seconds (or pass description/category/threshold/unit "
                "for named-policy style)"
            )
        return self._register_rate_policy(
            policy_id, scope_or_name, int(max_calls),
            float(window_seconds), action,
        )

    def _register_rate_policy(self, policy_id: str, scope: str,
                              max_calls: int, window_seconds: float,
                              action: str) -> dict:
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO sylion_rate_policies
                    (policy_id, scope, max_calls, window_seconds, action, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (policy_id, scope, max_calls, window_seconds, action, now))
            self._conn.commit()

        self._emit("aeis.self_limitation.policy_registered", {
            "policy_id": policy_id,
            "scope": scope,
            "max_calls": max_calls,
            "window_seconds": window_seconds,
            "action": action,
        })
        log.info("registered rate policy %s: scope=%s max=%d/%.0fs action=%s",
                 policy_id, scope, max_calls, window_seconds, action)
        return {
            "policy_id": policy_id,
            "scope": scope,
            "max_calls": max_calls,
            "window_seconds": window_seconds,
            "action": action,
        }

    # ------------------------------------------------------------------
    # Check rate
    # ------------------------------------------------------------------

    def check_rate(self, scope: str, identifier: str) -> dict:
        """Check if an action is within rate limits for a scope/identifier.

        Returns:
            Dict with allowed (bool), remaining (int), reset_at (float).
            If no policy exists for the scope, always allows.
        """
        with self._lock:
            now = time.time()

            row = self._conn.execute(
                "SELECT * FROM sylion_rate_policies WHERE scope = ?",
                (scope,),
            ).fetchone()

            if not row:
                return {"allowed": True, "remaining": -1, "reset_at": 0.0}

            max_calls = row["max_calls"]
            window_seconds = row["window_seconds"]
            action_on_violation = row["action"]
            cutoff = now - window_seconds

            # Count real action events in window (exclude throttle_cooldown)
            count_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sylion_rate_events "
                "WHERE scope = ? AND identifier = ? AND timestamp > ? "
                "AND action != 'throttle_cooldown'",
                (scope, identifier, cutoff),
            ).fetchone()
            current_count = count_row["cnt"] if count_row else 0

            remaining = max(0, max_calls - current_count)
            reset_at = now + window_seconds

            # Check for explicit throttle cooldown (any recent cooldown event)
            throttle_row = self._conn.execute(
                "SELECT details FROM sylion_rate_events "
                "WHERE scope = ? AND identifier = ? AND action = 'throttle_cooldown' "
                "ORDER BY timestamp DESC LIMIT 1",
                (scope, identifier),
            ).fetchone()

            if throttle_row:
                details = json.loads(throttle_row["details"])
                cooldown_until = details.get("cooldown_until", 0.0)
                if now < cooldown_until:
                    return {
                        "allowed": False,
                        "remaining": 0,
                        "reset_at": cooldown_until,
                    }

            if current_count >= max_calls:
                self._emit("aeis.self_limitation.rate_violation", {
                    "scope": scope,
                    "identifier": identifier,
                    "current_count": current_count,
                    "max_calls": max_calls,
                    "action": action_on_violation,
                })
                return {"allowed": False, "remaining": 0, "reset_at": reset_at}

            return {"allowed": True, "remaining": remaining, "reset_at": reset_at}

    # ------------------------------------------------------------------
    # Record action
    # ------------------------------------------------------------------

    def record_action(self, scope: str, identifier: str,
                      action: str = "", result: str = "") -> dict:
        """Record an action for rate tracking.

        Automatically flags as violation if the action exceeds a policy.

        Args:
            scope: Domain scope.
            identifier: Entity identifier within scope.
            action: Description of the action taken.
            result: Result of the action (e.g. "success", "blocked").

        Returns:
            Dict with event_id, is_violation, and metadata.
        """
        with self._lock:
            now = time.time()
            is_violation = 0

            # Check if this action creates a violation
            policy_row = self._conn.execute(
                "SELECT * FROM sylion_rate_policies WHERE scope = ?",
                (scope,),
            ).fetchone()

            if policy_row:
                cutoff = now - policy_row["window_seconds"]
                count_row = self._conn.execute(
                    "SELECT COUNT(*) as cnt FROM sylion_rate_events "
                    "WHERE scope = ? AND identifier = ? AND timestamp > ? "
                    "AND action != 'throttle_cooldown'",
                    (scope, identifier, cutoff),
                ).fetchone()
                if count_row and count_row["cnt"] >= policy_row["max_calls"]:
                    is_violation = 1

            cursor = self._conn.execute("""
                INSERT INTO sylion_rate_events
                    (scope, identifier, action, result, is_violation, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (scope, identifier, action, result, is_violation, "{}", now))
            self._conn.commit()
            event_id = cursor.lastrowid

        if is_violation:
            self._emit("aeis.self_limitation.action_violation", {
                "event_id": event_id,
                "scope": scope,
                "identifier": identifier,
                "action": action,
                "result": result,
            })
            log.warning("rate violation: scope=%s id=%s action=%s",
                        scope, identifier, action)

        return {
            "event_id": event_id,
            "scope": scope,
            "identifier": identifier,
            "is_violation": bool(is_violation),
        }

    # ------------------------------------------------------------------
    # Get usage
    # ------------------------------------------------------------------

    def get_usage(self, scope: str, identifier: str,
                  window_seconds: float) -> int:
        """Get current usage count for scope/identifier within a window.

        Args:
            scope: Domain scope.
            identifier: Entity identifier.
            window_seconds: Lookback window in seconds.

        Returns:
            Count of recorded events in the window.
        """
        with self._lock:
            now = time.time()
            cutoff = now - window_seconds
            row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sylion_rate_events "
                "WHERE scope = ? AND identifier = ? AND timestamp > ? "
                "AND action != 'throttle_cooldown'",
                (scope, identifier, cutoff),
            ).fetchone()
            return row["cnt"] if row else 0

    # ------------------------------------------------------------------
    # Get violations
    # ------------------------------------------------------------------

    def get_violations(self, scope: str | None = None,
                       identifier: str | None = None,
                       policy_id: str | None = None,
                       limit: int = 100) -> list[dict]:
        """List violations.

        - If policy_id is given, queries the named-policy violations
          plane (sylion_named_violations).
        - Otherwise queries the rate-limit violations plane
          (sylion_rate_events WHERE is_violation = 1) with optional
          scope/identifier filters.
        """
        if policy_id is not None:
            rows = self._conn.execute(
                "SELECT * FROM sylion_named_violations "
                "WHERE policy_id = ? ORDER BY recorded_at DESC LIMIT ?",
                (policy_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        q = "SELECT * FROM sylion_rate_events WHERE is_violation = 1"
        params: list[Any] = []
        if scope:
            q += " AND scope = ?"
            params.append(scope)
        if identifier:
            q += " AND identifier = ?"
            params.append(identifier)
        q += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    # ------------------------------------------------------------------
    # Named-policy plane (used by /api/v1/aeis/limitations/*)
    # ------------------------------------------------------------------

    def _register_named_policy(self, policy_id: str, name: str,
                               description: str, category: str,
                               threshold: float, unit: str) -> dict:
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO sylion_named_policies
                    (policy_id, name, description, category, threshold,
                     unit, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (policy_id, name, description, category, threshold, unit,
                   now, now))
            self._conn.commit()
        self._emit("aeis.self_limitation.named_policy_registered", {
            "policy_id": policy_id, "name": name, "category": category,
        })
        return self.get_policy(policy_id) or {
            "policy_id": policy_id, "name": name, "category": category,
        }

    def list_policies(self, category: str | None = None,
                      enabled_only: bool = True) -> list[dict]:
        """List named policies (NOT rate policies). Use list_rate_policies
        for the rate-limit plane.
        """
        q = "SELECT * FROM sylion_named_policies WHERE 1=1"
        params: list[Any] = []
        if category:
            q += " AND category = ?"
            params.append(category)
        if enabled_only:
            q += " AND enabled = 1"
        q += " ORDER BY created_at DESC"
        rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def get_policy(self, policy_id: str) -> dict | None:
        """Return one named policy by id, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM sylion_named_policies WHERE policy_id = ?",
            (policy_id,),
        ).fetchone()
        return dict(row) if row else None

    def check(self, policy_id: str, value: float) -> dict:
        """Compare a numeric value against a named-policy threshold.

        If the policy doesn't exist, returns {found: False, allowed: True}.
        If the value exceeds the threshold, records a violation.
        """
        policy = self.get_policy(policy_id)
        if policy is None:
            return {"found": False, "allowed": True, "policy_id": policy_id}
        if not policy.get("enabled", 1):
            return {
                "found": True, "enabled": False, "allowed": True,
                "policy_id": policy_id,
            }
        threshold = float(policy.get("threshold", 0.0))
        violated = value > threshold
        if violated:
            self.record_violation(
                policy_id, value, severity="warning",
                details={"reason": "value_exceeds_threshold",
                         "threshold": threshold, "value": value},
            )
        return {
            "found": True, "enabled": True,
            "allowed": not violated, "policy_id": policy_id,
            "value": value, "threshold": threshold,
        }

    def record_violation(self, policy_id: str, value: float,
                         severity: str = "warning",
                         details: dict | None = None) -> dict:
        """Append a named-policy violation row."""
        now = time.time()
        details_json = json.dumps(details or {}, default=str)
        with self._lock:
            cur = self._conn.execute("""
                INSERT INTO sylion_named_violations
                    (policy_id, value, severity, details, recorded_at)
                VALUES (?, ?, ?, ?, ?)
            """, (policy_id, float(value), severity, details_json, now))
            self._conn.commit()
            vid = cur.lastrowid
        self._emit("aeis.self_limitation.named_violation_recorded", {
            "violation_id": vid, "policy_id": policy_id,
            "value": value, "severity": severity,
        })
        return {
            "violation_id": vid, "policy_id": policy_id,
            "value": value, "severity": severity,
            "recorded_at": now,
        }

    def list_rate_policies(self, scope: str | None = None) -> list[dict]:
        """List rate-limit policies (the OG plane)."""
        if scope:
            rows = self._conn.execute(
                "SELECT * FROM sylion_rate_policies WHERE scope = ? "
                "ORDER BY created_at DESC", (scope,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM sylion_rate_policies ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Throttle (explicit cooldown)
    # ------------------------------------------------------------------

    def throttle(self, scope: str, identifier: str,
                 cooldown_seconds: float) -> dict:
        """Apply an explicit throttle cooldown to a scope/identifier.

        During the cooldown period, check_rate will return allowed=False.

        Args:
            scope: Domain scope.
            identifier: Entity identifier.
            cooldown_seconds: Duration of the cooldown.

        Returns:
            Dict with cooldown metadata.
        """
        now = time.time()
        cooldown_until = now + cooldown_seconds
        details = json.dumps({"cooldown_until": cooldown_until})

        with self._lock:
            self._conn.execute("""
                INSERT INTO sylion_rate_events
                    (scope, identifier, action, result, is_violation, details, timestamp)
                VALUES (?, ?, 'throttle_cooldown', 'active', 0, ?, ?)
            """, (scope, identifier, details, now))
            self._conn.commit()

        self._emit("aeis.self_limitation.throttle_applied", {
            "scope": scope,
            "identifier": identifier,
            "cooldown_seconds": cooldown_seconds,
            "cooldown_until": cooldown_until,
        })
        log.info("throttled scope=%s id=%s for %.1fs (until %.1f)",
                 scope, identifier, cooldown_seconds, cooldown_until)
        return {
            "scope": scope,
            "identifier": identifier,
            "cooldown_until": cooldown_until,
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate rate-limiting statistics.

        Returns:
            Dict with total_policies, total_actions, violation_count, top_scopes.
        """
        total_policies = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sylion_rate_policies"
        ).fetchone()["cnt"]

        total_actions = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sylion_rate_events"
        ).fetchone()["cnt"]

        violation_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sylion_rate_events WHERE is_violation = 1"
        ).fetchone()["cnt"]

        top_scopes_rows = self._conn.execute(
            "SELECT scope, COUNT(*) as cnt FROM sylion_rate_events "
            "GROUP BY scope ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        top_scopes = {r["scope"]: r["cnt"] for r in top_scopes_rows}

        return {
            "total_policies": total_policies,
            "total_actions": total_actions,
            "violation_count": violation_count,
            "top_scopes": top_scopes,
        }

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset_all(self) -> dict:
        """Clear all rate events. Policies are preserved.

        Returns:
            Dict confirming the reset.
        """
        with self._lock:
            deleted = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sylion_rate_events"
            ).fetchone()["cnt"]
            self._conn.execute("DELETE FROM sylion_rate_events")
            self._conn.commit()

        self._emit("aeis.self_limitation.reset", {
            "deleted_events": deleted,
        })
        log.info("reset all rate events (%d deleted)", deleted)
        return {"deleted_events": deleted}

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.self_limitation",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: SelfLimitationEngine | None = None


def get_self_limitation_engine(db_path: str | Path | None = None,
                               event_bus: EventBus | None = None) -> SelfLimitationEngine:
    """Return the global SelfLimitationEngine singleton."""
    global _engine
    if _engine is None:
        _engine = SelfLimitationEngine(db_path, event_bus)
    return _engine
