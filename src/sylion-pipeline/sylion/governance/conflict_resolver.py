"""
SYLION Governance -- Decision Conflict Resolver

Detects and resolves conflicts between concurrent decisions that affect
overlapping code modules.  Prevents the "lost update" problem where two
pipeline runs modify the same code independently.

Conflict types:
  module_overlap      -- two decisions touch the same modules
  resource_contention -- decisions compete for exclusive resources
  contract_mismatch   -- decisions imply incompatible contracts
  cascade_collision   -- cascading impacts from two decisions collide

Resolution strategies:
  merge      -- both decisions kept, dependencies updated
  priority_a -- snapshot A wins, B marked superseded
  priority_b -- snapshot B wins, A marked superseded
  escalate   -- create HumanGate session for human decision
  split      -- affected modules partitioned between decisions

Tables:
  decision_conflicts -- detected conflicts and their resolution state

Singleton: get_conflict_resolver() / reset_conflict_resolver()
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

log = logging.getLogger("sylion.governance.conflict_resolver")

# Decision-class priority mapping (higher numeric value = higher priority)
_CLASS_PRIORITY: dict[str, int] = {
    "D0": 0,
    "D1": 1,
    "D2": 2,
    "D3": 3,
    "D4": 4,
    "D5": 5,
}

# Severity ordering for automatic classification
_SEVERITY_ORDER = ("low", "medium", "high", "critical")


class ConflictResolver:
    """Detects and resolves conflicts between concurrent decisions."""

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
            CREATE TABLE IF NOT EXISTS decision_conflicts (
                conflict_id       TEXT PRIMARY KEY,
                snapshot_id_a     TEXT NOT NULL,
                snapshot_id_b     TEXT NOT NULL,

                conflict_type     TEXT NOT NULL,
                affected_modules  TEXT NOT NULL,
                severity          TEXT DEFAULT 'medium',

                resolution        TEXT,
                resolved_by       TEXT,
                resolution_details TEXT,

                status            TEXT DEFAULT 'detected',
                detected_at       REAL NOT NULL,
                resolved_at       REAL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conflict_status "
            "ON decision_conflicts(status)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conflict_severity "
            "ON decision_conflicts(severity)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conflict_snap_a "
            "ON decision_conflicts(snapshot_id_a)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conflict_snap_b "
            "ON decision_conflicts(snapshot_id_b)")
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
                source_module="conflict_resolver",
            ))

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _parse_json(raw: str | None, default: Any = None) -> Any:
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    def _snapshot_store(self):
        """Lazy import of DecisionSnapshot singleton."""
        from sylion.governance.decision_snapshot import get_decision_snapshot
        return get_decision_snapshot()

    def _get_snapshot(self, snapshot_id: str) -> dict | None:
        """Read a snapshot through the decision_snapshot module."""
        store = self._snapshot_store()
        return store.get_snapshot(snapshot_id)

    def _get_active_snapshots(self) -> list[dict]:
        """Return all active snapshots from decision_snapshot store."""
        store = self._snapshot_store()
        return store.list_snapshots(is_active=True, limit=10000)

    def _classify_severity(self, overlap_count: int,
                           class_a: str, class_b: str) -> str:
        """Determine conflict severity from overlap and decision classes."""
        max_class = max(_CLASS_PRIORITY.get(class_a, 0),
                        _CLASS_PRIORITY.get(class_b, 0))
        if max_class >= 4 or overlap_count >= 5:
            return "critical"
        if max_class >= 3 or overlap_count >= 3:
            return "high"
        if max_class >= 2 or overlap_count >= 2:
            return "medium"
        return "low"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_conflicts(self, snapshot_id: str) -> list[dict]:
        """Check a new snapshot against all active snapshots for conflicts.

        Compares module_states overlaps, affected_decisions, and
        pipeline_run_id collisions.

        Returns list of detected conflict records.
        """
        snap = self._get_snapshot(snapshot_id)
        if not snap:
            return []

        my_modules_raw = snap.get("module_states", {})
        if isinstance(my_modules_raw, str):
            my_modules_raw = json.loads(my_modules_raw)
        my_modules = set(my_modules_raw.keys())
        if not my_modules:
            return []

        my_pipeline = snap.get("pipeline_run_id")
        my_affected = snap.get("affected_decisions") or []
        if isinstance(my_affected, str):
            my_affected = json.loads(my_affected)
        my_affected_set = set(my_affected)
        my_class = snap.get("decision_class", "D0")

        active = self._get_active_snapshots()
        conflicts: list[dict] = []

        for other in active:
            other_sid = other["snapshot_id"]
            if other_sid == snapshot_id:
                continue

            other_modules_raw = other.get("module_states", {})
            if isinstance(other_modules_raw, str):
                other_modules_raw = json.loads(other_modules_raw)
            other_modules = set(other_modules_raw.keys())

            overlap = sorted(my_modules & other_modules)
            if not overlap:
                continue

            other_class = other.get("decision_class", "D0")
            other_affected = other.get("affected_decisions") or []
            if isinstance(other_affected, str):
                other_affected = json.loads(other_affected)
            other_affected_set = set(other_affected)

            # Determine conflict type
            conflict_type = "module_overlap"
            if my_pipeline and other.get("pipeline_run_id") and \
               my_pipeline == other["pipeline_run_id"]:
                conflict_type = "resource_contention"
            elif my_affected_set & other_affected_set:
                conflict_type = "cascade_collision"

            # Check for contract mismatch (different module states on overlap)
            has_state_conflict = False
            for mod_id in overlap:
                my_state = my_modules_raw.get(mod_id, {})
                other_state = other_modules_raw.get(mod_id, {})
                if my_state != other_state:
                    has_state_conflict = True
                    break
            if has_state_conflict and conflict_type == "module_overlap":
                conflict_type = "contract_mismatch"

            severity = self._classify_severity(
                len(overlap), my_class, other_class)

            conflict_id = self._uid()
            now = time.time()

            with self._lock:
                # Check for existing conflict between these two snapshots
                existing = self._conn.execute(
                    "SELECT conflict_id FROM decision_conflicts "
                    "WHERE (snapshot_id_a = ? AND snapshot_id_b = ?) "
                    "   OR (snapshot_id_a = ? AND snapshot_id_b = ?)",
                    (snapshot_id, other_sid, other_sid, snapshot_id),
                ).fetchone()
                if existing:
                    continue

                self._conn.execute("""
                    INSERT INTO decision_conflicts
                    (conflict_id, snapshot_id_a, snapshot_id_b,
                     conflict_type, affected_modules, severity,
                     status, detected_at)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (
                    conflict_id, snapshot_id, other_sid,
                    conflict_type, json.dumps(overlap), severity,
                    "detected", now,
                ))
                self._conn.commit()

                row = self._conn.execute(
                    "SELECT * FROM decision_conflicts WHERE conflict_id = ?",
                    (conflict_id,),
                ).fetchone()

            conflict_dict = dict(row)
            conflict_dict["affected_modules"] = json.loads(
                conflict_dict["affected_modules"])
            conflicts.append(conflict_dict)

            self._emit("decision.conflict.detected", {
                "conflict_id": conflict_id,
                "snapshot_id_a": snapshot_id,
                "snapshot_id_b": other_sid,
                "conflict_type": conflict_type,
                "severity": severity,
            })

        return conflicts

    def analyze_conflict(self, conflict_id: str) -> dict | None:
        """Deep analysis of a conflict.

        Gets full cascade impact for both snapshots, determines
        compatibility, and suggests a resolution strategy.

        Returns {conflict_id, analysis, suggested_resolution, affected_modules}
        or None if conflict not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM decision_conflicts WHERE conflict_id = ?",
                (conflict_id,),
            ).fetchone()
        if not row:
            return None

        conflict = dict(row)
        sid_a = conflict["snapshot_id_a"]
        sid_b = conflict["snapshot_id_b"]

        snap_a = self._get_snapshot(sid_a)
        snap_b = self._get_snapshot(sid_b)

        # Update status to analyzing
        with self._lock:
            self._conn.execute(
                "UPDATE decision_conflicts SET status = 'analyzing' "
                "WHERE conflict_id = ?",
                (conflict_id,),
            )
            self._conn.commit()

        # Get cascade impacts
        store = self._snapshot_store()
        impact_a = store.get_cascade_impact(sid_a)
        impact_b = store.get_cascade_impact(sid_b)

        affected_a = impact_a.get("total_affected", 0)
        affected_b = impact_b.get("total_affected", 0)

        class_a = snap_a.get("decision_class", "D0") if snap_a else "D0"
        class_b = snap_b.get("decision_class", "D0") if snap_b else "D0"
        pri_a = _CLASS_PRIORITY.get(class_a, 0)
        pri_b = _CLASS_PRIORITY.get(class_b, 0)

        overlap = json.loads(conflict["affected_modules"])

        # Determine compatibility
        compatible = True
        if conflict["conflict_type"] == "contract_mismatch":
            compatible = False
        elif conflict["conflict_type"] == "cascade_collision":
            compatible = False
        elif conflict["conflict_type"] == "resource_contention":
            compatible = False
        elif conflict["severity"] in ("high", "critical"):
            compatible = False

        # Suggest resolution
        if compatible:
            suggested = "merge"
        elif pri_a > pri_b:
            suggested = "priority_a"
        elif pri_b > pri_a:
            suggested = "priority_b"
        elif affected_a < affected_b:
            suggested = "priority_a"
        elif affected_b < affected_a:
            suggested = "priority_b"
        else:
            suggested = "escalate"

        # For critical severity involving D3+, suggest council
        if conflict["severity"] == "critical" and max(pri_a, pri_b) >= 3:
            suggested = "escalate"

        analysis = {
            "conflict_id": conflict_id,
            "snapshot_a": {
                "id": sid_a,
                "decision_class": class_a,
                "cascade_affected": affected_a,
                "impact_radius": snap_a.get("impact_radius", "local") if snap_a else "local",
            },
            "snapshot_b": {
                "id": sid_b,
                "decision_class": class_b,
                "cascade_affected": affected_b,
                "impact_radius": snap_b.get("impact_radius", "local") if snap_b else "local",
            },
            "compatible": compatible,
            "overlap_size": len(overlap),
            "cascade_total": affected_a + affected_b,
        }

        result = {
            "conflict_id": conflict_id,
            "analysis": analysis,
            "suggested_resolution": suggested,
            "affected_modules": overlap,
        }

        self._emit("decision.conflict.analyzed", {
            "conflict_id": conflict_id,
            "suggested_resolution": suggested,
            "compatible": compatible,
        })

        return result

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
        resolved_by: str = "system",
        details: dict | None = None,
    ) -> dict | None:
        """Apply a resolution to a conflict.

        Strategies:
          merge      -- both decisions kept, dependencies updated
          priority_a -- snapshot B marked superseded
          priority_b -- snapshot A marked superseded
          escalate   -- creates HumanGate session for human decision
          split      -- affected modules partitioned between decisions

        Returns updated conflict record or None if not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM decision_conflicts WHERE conflict_id = ?",
                (conflict_id,),
            ).fetchone()
        if not row:
            return None

        conflict = dict(row)
        sid_a = conflict["snapshot_id_a"]
        sid_b = conflict["snapshot_id_b"]
        now = time.time()

        store = self._snapshot_store()
        details_out: dict[str, Any] = details or {}

        if resolution == "merge":
            # Both decisions kept; create a dependency between them
            store.add_dependency(sid_a, sid_b, "merged", "weak")
            details_out["action"] = "dependencies_updated"

        elif resolution == "priority_a":
            # Mark B superseded via change_decision
            store.change_decision(sid_b, new_choice="superseded_by_conflict_resolution")
            details_out["action"] = "snapshot_b_superseded"
            details_out["superseded_snapshot"] = sid_b

        elif resolution == "priority_b":
            # Mark A superseded via change_decision
            store.change_decision(sid_a, new_choice="superseded_by_conflict_resolution")
            details_out["action"] = "snapshot_a_superseded"
            details_out["superseded_snapshot"] = sid_a

        elif resolution == "escalate":
            # Create HumanGate session
            try:
                from sylion.governance.human_gate import HumanGate
                hg = HumanGate()
                session = hg.create_session(
                    title=f"Conflict Resolution: {conflict_id}",
                    description=f"Resolve conflict between {sid_a} and {sid_b}",
                )
                details_out["action"] = "escalated_to_human_gate"
                details_out["hg_session_id"] = session["session_id"]
            except Exception as exc:
                details_out["action"] = "escalation_failed"
                details_out["error"] = str(exc)

        elif resolution == "split":
            overlap = json.loads(conflict["affected_modules"])
            half = len(overlap) // 2
            modules_a = overlap[:half] if half > 0 else overlap
            modules_b = overlap[half:] if half > 0 else []
            if not modules_b:
                modules_a = overlap[:1]
                modules_b = overlap[1:] if len(overlap) > 1 else overlap
            details_out["action"] = "modules_split"
            details_out["modules_a"] = modules_a
            details_out["modules_b"] = modules_b

        else:
            return None

        status = "escalated" if resolution == "escalate" else "resolved"

        with self._lock:
            self._conn.execute("""
                UPDATE decision_conflicts
                SET resolution = ?,
                    resolved_by = ?,
                    resolution_details = ?,
                    status = ?,
                    resolved_at = ?
                WHERE conflict_id = ?
            """, (
                resolution,
                resolved_by,
                json.dumps(details_out),
                status,
                now,
                conflict_id,
            ))
            self._conn.commit()

            updated = self._conn.execute(
                "SELECT * FROM decision_conflicts WHERE conflict_id = ?",
                (conflict_id,),
            ).fetchone()

        result = dict(updated)
        result["affected_modules"] = json.loads(result["affected_modules"])
        result["resolution_details"] = self._parse_json(
            result.get("resolution_details"), {})

        self._emit("decision.conflict.resolved", {
            "conflict_id": conflict_id,
            "resolution": resolution,
            "resolved_by": resolved_by,
        })

        log.info("resolved conflict %s with %s (by %s)",
                 conflict_id, resolution, resolved_by)
        return result

    def get_conflict(self, conflict_id: str) -> dict | None:
        """Return a conflict record by ID, with JSON fields parsed."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM decision_conflicts WHERE conflict_id = ?",
                (conflict_id,),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["affected_modules"] = json.loads(result["affected_modules"])
        result["resolution_details"] = self._parse_json(
            result.get("resolution_details"))
        return result

    def list_conflicts(
        self,
        status: str | None = None,
        severity: str | None = None,
    ) -> list[dict]:
        """Filtered listing of conflicts."""
        with self._lock:
            q = "SELECT * FROM decision_conflicts WHERE 1=1"
            params: list[Any] = []
            if status:
                q += " AND status = ?"
                params.append(status)
            if severity:
                q += " AND severity = ?"
                params.append(severity)
            q += " ORDER BY detected_at DESC"
            rows = self._conn.execute(q, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["affected_modules"] = json.loads(d["affected_modules"])
            d["resolution_details"] = self._parse_json(d.get("resolution_details"))
            results.append(d)
        return results

    def get_unresolved(self) -> list[dict]:
        """Return all detected/analyzing conflicts (not yet resolved)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM decision_conflicts "
                "WHERE status IN ('detected', 'analyzing') "
                "ORDER BY detected_at ASC"
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["affected_modules"] = json.loads(d["affected_modules"])
            d["resolution_details"] = self._parse_json(d.get("resolution_details"))
            results.append(d)
        return results

    def auto_resolve(self, conflict_id: str) -> dict:
        """Attempt automatic resolution based on heuristics.

        Priority rules:
          1. Higher decision class wins (D3 > D2)
          2. Shallower cascade depth wins
          3. Smaller impact radius wins
          4. Equal priority -> escalate

        Returns {resolved: bool, resolution: str, reason: str}
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM decision_conflicts WHERE conflict_id = ?",
                (conflict_id,),
            ).fetchone()
        if not row:
            return {"resolved": False, "resolution": None,
                    "reason": "conflict not found"}

        conflict = dict(row)
        sid_a = conflict["snapshot_id_a"]
        sid_b = conflict["snapshot_id_b"]

        snap_a = self._get_snapshot(sid_a)
        snap_b = self._get_snapshot(sid_b)

        if not snap_a or not snap_b:
            return {"resolved": False, "resolution": None,
                    "reason": "snapshot not found"}

        class_a = snap_a.get("decision_class", "D0")
        class_b = snap_b.get("decision_class", "D0")
        pri_a = _CLASS_PRIORITY.get(class_a, 0)
        pri_b = _CLASS_PRIORITY.get(class_b, 0)

        # Rule 1: Higher decision class wins
        if pri_a > pri_b:
            self.resolve_conflict(conflict_id, "priority_a",
                                  resolved_by="system",
                                  details={"reason": "class_priority",
                                           "class_a": class_a,
                                           "class_b": class_b})
            return {"resolved": True, "resolution": "priority_a",
                    "reason": f"class priority: {class_a} > {class_b}"}

        if pri_b > pri_a:
            self.resolve_conflict(conflict_id, "priority_b",
                                  resolved_by="system",
                                  details={"reason": "class_priority",
                                           "class_a": class_a,
                                           "class_b": class_b})
            return {"resolved": True, "resolution": "priority_b",
                    "reason": f"class priority: {class_b} > {class_a}"}

        # Rule 2: Shallower cascade depth wins
        depth_a = snap_a.get("cascade_depth", 0)
        depth_b = snap_b.get("cascade_depth", 0)

        if depth_a < depth_b:
            self.resolve_conflict(conflict_id, "priority_a",
                                  resolved_by="system",
                                  details={"reason": "cascade_depth",
                                           "depth_a": depth_a,
                                           "depth_b": depth_b})
            return {"resolved": True, "resolution": "priority_a",
                    "reason": f"cascade depth: {depth_a} < {depth_b}"}

        if depth_b < depth_a:
            self.resolve_conflict(conflict_id, "priority_b",
                                  resolved_by="system",
                                  details={"reason": "cascade_depth",
                                           "depth_a": depth_a,
                                           "depth_b": depth_b})
            return {"resolved": True, "resolution": "priority_b",
                    "reason": f"cascade depth: {depth_b} < {depth_a}"}

        # Rule 3: Smaller impact radius
        radius_order = {"local": 0, "module": 1, "system": 2, "cross-system": 3}
        rad_a = radius_order.get(snap_a.get("impact_radius", "local"), 0)
        rad_b = radius_order.get(snap_b.get("impact_radius", "local"), 0)

        if rad_a < rad_b:
            self.resolve_conflict(conflict_id, "priority_a",
                                  resolved_by="system",
                                  details={"reason": "impact_radius",
                                           "radius_a": snap_a.get("impact_radius"),
                                           "radius_b": snap_b.get("impact_radius")})
            return {"resolved": True, "resolution": "priority_a",
                    "reason": f"impact radius: {snap_a.get('impact_radius')} < {snap_b.get('impact_radius')}"}

        if rad_b < rad_a:
            self.resolve_conflict(conflict_id, "priority_b",
                                  resolved_by="system",
                                  details={"reason": "impact_radius",
                                           "radius_a": snap_a.get("impact_radius"),
                                           "radius_b": snap_b.get("impact_radius")})
            return {"resolved": True, "resolution": "priority_b",
                    "reason": f"impact radius: {snap_b.get('impact_radius')} < {snap_a.get('impact_radius')}"}

        # Rule 4: Equal priority -> escalate
        self.resolve_conflict(conflict_id, "escalate",
                              resolved_by="system",
                              details={"reason": "equal_priority_cannot_auto_resolve"})
        return {"resolved": False, "resolution": "escalate",
                "reason": "equal priority, requires human decision"}

    def escalate_to_council(self, conflict_id: str) -> dict | None:
        """Create a council session for D3+ conflicts.

        Returns council session info or None if conflict not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM decision_conflicts WHERE conflict_id = ?",
                (conflict_id,),
            ).fetchone()
        if not row:
            return None

        conflict = dict(row)
        snap_a = self._get_snapshot(conflict["snapshot_id_a"])
        snap_b = self._get_snapshot(conflict["snapshot_id_b"])

        max_class = "D0"
        if snap_a:
            max_class = snap_a.get("decision_class", "D0")
        if snap_b:
            bc = snap_b.get("decision_class", "D0")
            if _CLASS_PRIORITY.get(bc, 0) > _CLASS_PRIORITY.get(max_class, 0):
                max_class = bc

        try:
            from sylion.governance.council_workflow import CouncilWorkflow
            council = CouncilWorkflow()
            session = council.open_session(
                proposal_id=conflict_id,
                decision_class=max_class,
                title=f"Conflict Resolution: {conflict_id}",
                description=(
                    f"Resolve conflict between {conflict['snapshot_id_a']} "
                    f"and {conflict['snapshot_id_b']}. "
                    f"Type: {conflict['conflict_type']}, "
                    f"Severity: {conflict['severity']}"
                ),
            )
        except Exception as exc:
            # Fallback to HumanGate if council not available
            try:
                from sylion.governance.human_gate import HumanGate
                hg = HumanGate()
                session = hg.create_session(
                    title=f"Council Conflict: {conflict_id}",
                    description=(
                        f"Resolve D3+ conflict between "
                        f"{conflict['snapshot_id_a']} and "
                        f"{conflict['snapshot_id_b']}"
                    ),
                )
                session["council_fallback"] = True
                session["fallback_reason"] = str(exc)
            except Exception as exc2:
                return {"error": f"Could not escalate: {exc2}"}

        # Update conflict record
        now = time.time()
        with self._lock:
            self._conn.execute("""
                UPDATE decision_conflicts
                SET status = 'escalated',
                    resolution = 'escalate',
                    resolved_by = 'council',
                    resolution_details = ?,
                    resolved_at = ?
                WHERE conflict_id = ?
            """, (
                json.dumps({
                    "action": "escalated_to_council",
                    "council_session_id": session.get("session_id"),
                }),
                now,
                conflict_id,
            ))
            self._conn.commit()

        self._emit("decision.conflict.escalated", {
            "conflict_id": conflict_id,
            "council_session_id": session.get("session_id"),
            "decision_class": max_class,
        })

        return session

    def get_conflict_stats(self) -> dict[str, Any]:
        """Return aggregate conflict statistics.

        Returns {total, by_status, by_severity, auto_resolved_rate}
        """
        with self._lock:
            total_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM decision_conflicts"
            ).fetchone()
            total = total_row["cnt"] if total_row else 0

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM decision_conflicts "
                "GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

            severity_rows = self._conn.execute(
                "SELECT severity, COUNT(*) as cnt FROM decision_conflicts "
                "GROUP BY severity"
            ).fetchall()
            by_severity = {r["severity"]: r["cnt"] for r in severity_rows}

            system_resolved = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM decision_conflicts "
                "WHERE resolved_by = 'system' AND status = 'resolved'"
            ).fetchone()
            system_count = system_resolved["cnt"] if system_resolved else 0

            all_resolved = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM decision_conflicts "
                "WHERE status = 'resolved'"
            ).fetchone()
            resolved_count = all_resolved["cnt"] if all_resolved else 0

        auto_rate = (system_count / resolved_count * 100) \
            if resolved_count > 0 else 0.0

        return {
            "total": total,
            "by_status": by_status,
            "by_severity": by_severity,
            "auto_resolved_rate": round(auto_rate, 1),
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_resolver: ConflictResolver | None = None


def get_conflict_resolver(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ConflictResolver:
    global _resolver
    if _resolver is None:
        _resolver = ConflictResolver(db_path, event_bus)
    return _resolver


def reset_conflict_resolver(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ConflictResolver:
    global _resolver
    _resolver = ConflictResolver(db_path, event_bus)
    return _resolver
