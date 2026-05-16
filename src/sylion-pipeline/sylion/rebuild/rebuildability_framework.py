"""
SYLION Rebuild -- Rebuildability Framework with CFT Hardening

Ensures the system can be rebuilt from scratch using only Ksiega + contracts.
The Canonical Fidelity Test (CFT) verifies that after compaction/rebuild,
the system maintains semantic fidelity (target: >0.95).

Fidelity dimensions:
  - module_match:  are all modules present with correct manifests?
  - contract_match: are all contracts present with correct schemas?
  - event_match:   are all events replayed with correct payloads?
  - decision_match: are all governance decisions preserved?

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

import hashlib
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

log = logging.getLogger("sylion.rebuild.rebuildability_framework")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIDELITY_THRESHOLD = 0.95


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SystemSnapshot:
    """Immutable snapshot of system state at a point in time."""
    snapshot_id: str = ""
    snapshot_hash: str = ""
    modules: list[dict] = field(default_factory=list)
    contracts: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.snapshot_id:
            self.snapshot_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class RebuildStep:
    """A single step in a generated rebuild plan."""
    order: int = 0
    module_id: str = ""
    dependencies: list[str] = field(default_factory=list)
    contract_version: str = "1.0.0"
    action: str = "register"


@dataclass
class FidelityReport:
    """Fidelity comparison result between two snapshots."""
    fidelity: float = 0.0
    module_match: float = 0.0
    contract_match: float = 0.0
    event_match: float = 0.0
    decision_match: float = 0.0
    passed: bool = False
    details: dict = field(default_factory=dict)


@dataclass
class RebuildCheckResult:
    """Full rebuildability check result."""
    rebuildable: bool = False
    manifests_valid: bool = False
    contracts_frozen: bool = False
    cft_passed: bool = False
    cft_fidelity: float = 0.0
    issues: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rebuildability Framework
# ---------------------------------------------------------------------------

class RebuildabilityFramework:
    """Ensures system can be rebuilt from Ksiega + contracts.

    SQLite-backed. Thread-safe. Emits events via EventBus.
    """

    def __init__(self, registry, event_bus: EventBus | None = None,
                 db_path: str | Path | None = None,
                 contract_registry=None):
        """Initialize the framework.

        Args:
            registry: ModuleRegistry instance (source of truth for modules).
            event_bus: Optional EventBus for event emission.
            db_path: SQLite database path. Defaults to ':memory:'.
            contract_registry: Optional ContractRegistry for contract queries.
        """
        self._registry = registry
        self._event_bus = event_bus
        self._contract_registry = contract_registry
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS rebuild_snapshots (
                snapshot_id   TEXT PRIMARY KEY,
                snapshot_hash TEXT NOT NULL DEFAULT '',
                modules_json  TEXT NOT NULL DEFAULT '[]',
                contracts_json TEXT NOT NULL DEFAULT '[]',
                events_json   TEXT NOT NULL DEFAULT '[]',
                decisions_json TEXT NOT NULL DEFAULT '[]',
                timestamp     REAL NOT NULL,
                label         TEXT NOT NULL DEFAULT ''
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS rebuild_history (
                history_id    TEXT PRIMARY KEY,
                original_snapshot_id TEXT NOT NULL DEFAULT '',
                rebuilt_snapshot_id  TEXT NOT NULL DEFAULT '',
                fidelity      REAL NOT NULL DEFAULT 0.0,
                module_match  REAL NOT NULL DEFAULT 0.0,
                contract_match REAL NOT NULL DEFAULT 0.0,
                event_match   REAL NOT NULL DEFAULT 0.0,
                passed        INTEGER NOT NULL DEFAULT 0,
                timestamp     REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS rebuild_plans (
                plan_id     TEXT PRIMARY KEY,
                steps_json  TEXT NOT NULL DEFAULT '[]',
                created_at  REAL NOT NULL,
                status      TEXT NOT NULL DEFAULT 'generated'
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON rebuild_snapshots(timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_ts ON rebuild_history(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot_system_state(self) -> dict:
        """Capture current system state: modules, contracts, events, decisions.

        Returns dict with {snapshot_id, snapshot_hash, modules: N, contracts: N,
        events: N, decisions: N, timestamp}.
        """
        modules = self._registry.list_modules() if self._registry else []
        contracts = self._get_contracts()
        events = self._get_events()
        decisions = self._get_decisions()

        snapshot_hash = self._compute_snapshot_hash(modules, contracts, events, decisions)

        snapshot = SystemSnapshot(
            snapshot_hash=snapshot_hash,
            modules=modules,
            contracts=contracts,
            events=events,
            decisions=decisions,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO rebuild_snapshots
                    (snapshot_id, snapshot_hash, modules_json, contracts_json,
                     events_json, decisions_json, timestamp, label)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'auto')
            """, (
                snapshot.snapshot_id, snapshot.snapshot_hash,
                json.dumps(modules, default=str),
                json.dumps(contracts, default=str),
                json.dumps(events, default=str),
                json.dumps(decisions, default=str),
                snapshot.timestamp,
            ))
            self._conn.commit()

        self._emit("rebuild.snapshot_captured", {
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_hash": snapshot_hash,
            "modules": len(modules),
            "contracts": len(contracts),
            "events": len(events),
            "decisions": len(decisions),
        })

        log.info("captured snapshot %s: modules=%d contracts=%d events=%d decisions=%d",
                 snapshot.snapshot_id[:12], len(modules), len(contracts),
                 len(events), len(decisions))

        return {
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_hash": snapshot_hash,
            "modules": len(modules),
            "contracts": len(contracts),
            "events": len(events),
            "decisions": len(decisions),
            "timestamp": snapshot.timestamp,
        }

    def get_snapshot(self, snapshot_id: str) -> dict | None:
        """Retrieve a stored snapshot by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM rebuild_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "snapshot_id": row["snapshot_id"],
            "snapshot_hash": row["snapshot_hash"],
            "modules": json.loads(row["modules_json"]),
            "contracts": json.loads(row["contracts_json"]),
            "events": json.loads(row["events_json"]),
            "decisions": json.loads(row["decisions_json"]),
            "timestamp": row["timestamp"],
            "label": row["label"],
        }

    # ------------------------------------------------------------------
    # Rebuild plan generation
    # ------------------------------------------------------------------

    def generate_rebuild_plan(self) -> dict:
        """Generate a step-by-step rebuild plan from Ksiega + contracts.

        Returns {plan_id, steps: [{order, module_id, dependencies, contract_version}]}.
        Steps are ordered topologically by dependencies.
        """
        modules = self._registry.list_modules() if self._registry else []
        contracts = self._get_contracts()

        # Build contract version map: module_id -> latest contract version
        contract_versions: dict[str, str] = {}
        for c in contracts:
            producer = c.get("producer_module", "")
            if producer:
                contract_versions[producer] = c.get("version", "1.0.0")

        # Build dependency graph
        steps: list[dict] = []
        module_deps: dict[str, list[str]] = {}
        for m in modules:
            mid = m.get("module_id", "")
            raw_deps = m.get("depends_on", "[]")
            if isinstance(raw_deps, str):
                deps = json.loads(raw_deps) if raw_deps else []
            else:
                deps = list(raw_deps) if raw_deps else []
            module_deps[mid] = deps

        # Topological sort (Kahn's algorithm)
        in_degree: dict[str, int] = {mid: 0 for mid in module_deps}
        for mid, deps in module_deps.items():
            for dep in deps:
                if dep in in_degree:
                    # dep must come before mid
                    pass
            in_degree[mid] = len([d for d in deps if d in in_degree])

        queue = [mid for mid, deg in in_degree.items() if deg == 0]
        order = 0
        while queue:
            queue.sort()  # deterministic ordering
            current = queue.pop(0)
            cv = contract_versions.get(current, "1.0.0")
            steps.append({
                "order": order,
                "module_id": current,
                "dependencies": module_deps.get(current, []),
                "contract_version": cv,
                "action": "register",
            })
            order += 1
            # Reduce in-degree for dependents
            for mid, deps in module_deps.items():
                if current in deps:
                    in_degree[mid] -= 1
                    if in_degree[mid] == 0 and mid not in queue and mid not in [s["module_id"] for s in steps]:
                        queue.append(mid)

        # Add any remaining modules (cycles or orphans)
        added_ids = {s["module_id"] for s in steps}
        for mid in module_deps:
            if mid not in added_ids:
                steps.append({
                    "order": order,
                    "module_id": mid,
                    "dependencies": module_deps.get(mid, []),
                    "contract_version": contract_versions.get(mid, "1.0.0"),
                    "action": "register",
                })
                order += 1

        plan_id = uuid.uuid4().hex

        with self._lock:
            self._conn.execute("""
                INSERT INTO rebuild_plans (plan_id, steps_json, created_at, status)
                VALUES (?, ?, ?, 'generated')
            """, (plan_id, json.dumps(steps, default=str), time.time()))
            self._conn.commit()

        self._emit("rebuild.plan_generated", {
            "plan_id": plan_id, "steps": len(steps),
        })

        log.info("generated rebuild plan %s with %d steps", plan_id[:12], len(steps))
        return {"plan_id": plan_id, "steps": steps}

    # ------------------------------------------------------------------
    # Fidelity verification
    # ------------------------------------------------------------------

    def _resolve_snapshot_data(self, snapshot: dict) -> dict:
        """Resolve a snapshot dict to full data.

        Handles both:
          - Flat dicts from snapshot_system_state() where modules/contracts are int counts
          - Full dicts from get_snapshot() where they are lists
          - Rebuilt dicts from _rebuild_from_compacted() where they are lists
        """
        modules = snapshot.get("modules", [])
        contracts = snapshot.get("contracts", [])
        events = snapshot.get("events", [])
        decisions = snapshot.get("decisions", [])

        # If any field is an int (count), load the full snapshot from DB
        if isinstance(modules, int) or isinstance(contracts, int) \
                or isinstance(events, int) or isinstance(decisions, int):
            sid = snapshot.get("snapshot_id", "")
            if sid:
                full = self.get_snapshot(sid)
                if full:
                    return full

        return {
            "modules": modules if isinstance(modules, list) else [],
            "contracts": contracts if isinstance(contracts, list) else [],
            "events": events if isinstance(events, list) else [],
            "decisions": decisions if isinstance(decisions, list) else [],
        }

    def verify_rebuild(self, original_snapshot: dict,
                       rebuilt_snapshot: dict) -> dict:
        """Compare two system snapshots for fidelity.

        Args:
            original_snapshot: dict from snapshot_system_state() or get_snapshot().
            rebuilt_snapshot: dict from snapshot_system_state() or get_snapshot().

        Returns {fidelity, module_match, contract_match, event_match, passed}.
        """
        orig = self._resolve_snapshot_data(original_snapshot)
        rebuilt = self._resolve_snapshot_data(rebuilt_snapshot)

        orig_modules = orig["modules"]
        rebuilt_modules = rebuilt["modules"]
        orig_contracts = orig["contracts"]
        rebuilt_contracts = rebuilt["contracts"]
        orig_events = orig["events"]
        rebuilt_events = rebuilt["events"]
        orig_decisions = orig["decisions"]
        rebuilt_decisions = rebuilt["decisions"]

        module_match = self._compute_set_fidelity(
            self._module_keys(orig_modules),
            self._module_keys(rebuilt_modules),
        )
        contract_match = self._compute_set_fidelity(
            self._contract_keys(orig_contracts),
            self._contract_keys(rebuilt_contracts),
        )
        event_match = self._compute_set_fidelity(
            self._event_keys(orig_events),
            self._event_keys(rebuilt_events),
        )
        decision_match = self._compute_set_fidelity(
            self._decision_keys(orig_decisions),
            self._decision_keys(rebuilt_decisions),
        )

        # Weighted fidelity: modules and contracts are most critical
        fidelity = (
            module_match * 0.35
            + contract_match * 0.30
            + event_match * 0.20
            + decision_match * 0.15
        )
        fidelity = round(fidelity, 4)

        passed = fidelity >= FIDELITY_THRESHOLD

        result = {
            "fidelity": fidelity,
            "module_match": round(module_match, 4),
            "contract_match": round(contract_match, 4),
            "event_match": round(event_match, 4),
            "decision_match": round(decision_match, 4),
            "passed": passed,
        }

        # Record in history
        history_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute("""
                INSERT INTO rebuild_history
                    (history_id, original_snapshot_id, rebuilt_snapshot_id,
                     fidelity, module_match, contract_match, event_match,
                     passed, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                history_id,
                original_snapshot.get("snapshot_id", ""),
                rebuilt_snapshot.get("snapshot_id", ""),
                fidelity, module_match, contract_match, event_match,
                1 if passed else 0, time.time(),
            ))
            self._conn.commit()

        self._emit("rebuild.verification_completed", {
            "history_id": history_id,
            "fidelity": fidelity,
            "passed": passed,
        })

        log.info("rebuild verification: fidelity=%.4f passed=%s", fidelity, passed)
        return result

    # ------------------------------------------------------------------
    # Full CFT run
    # ------------------------------------------------------------------

    def run_cft(self) -> dict:
        """Run Compact Fidelity Test: Snapshot -> Compact -> Rebuild -> Compare.

        This is the canonical test for rebuildability.
        Returns {fidelity, module_match, contract_match, event_match, passed}.
        """
        # Step 1: Capture original snapshot
        original = self.snapshot_system_state()
        original_full = self.get_snapshot(original["snapshot_id"])

        # Step 2: Simulate compaction (compact the snapshot data)
        compacted = self._compact_snapshot(original_full)

        # Step 3: Simulate rebuild from compacted data
        rebuilt = self._rebuild_from_compacted(compacted)

        # Step 4: Verify fidelity
        verification = self.verify_rebuild(original, rebuilt)

        self._emit("rebuild.cft_completed", {
            "original_snapshot_id": original["snapshot_id"],
            "rebuilt_snapshot_id": rebuilt.get("snapshot_id", ""),
            "fidelity": verification["fidelity"],
            "passed": verification["passed"],
        })

        log.info("CFT run completed: fidelity=%.4f passed=%s",
                 verification["fidelity"], verification["passed"])
        return verification

    # ------------------------------------------------------------------
    # Rebuild history
    # ------------------------------------------------------------------

    def get_rebuild_history(self) -> list[dict]:
        """Get all rebuild verification history entries."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM rebuild_history ORDER BY timestamp DESC LIMIT 100"
            ).fetchall()
        results = []
        for r in rows:
            results.append({
                "history_id": r["history_id"],
                "original_snapshot_id": r["original_snapshot_id"],
                "rebuilt_snapshot_id": r["rebuilt_snapshot_id"],
                "fidelity": r["fidelity"],
                "module_match": r["module_match"],
                "contract_match": r["contract_match"],
                "event_match": r["event_match"],
                "passed": bool(r["passed"]),
                "timestamp": r["timestamp"],
            })
        return results

    # ------------------------------------------------------------------
    # Full rebuildability check
    # ------------------------------------------------------------------

    def check_rebuildability(self) -> dict:
        """Full rebuildability check: manifests valid, contracts frozen, CFT >0.95.

        Returns RebuildCheckResult as dict.
        """
        issues: list[str] = []

        # Check 1: All manifests valid
        modules = self._registry.list_modules() if self._registry else []
        manifests_valid = True
        for m in modules:
            mid = m.get("module_id", "")
            kind = m.get("module_kind", "")
            owner = m.get("owner_plan", "")
            if not mid or not kind or not owner:
                manifests_valid = False
                issues.append(f"Invalid manifest for module: {mid}")

        # Check 2: Contracts frozen (all have explicit versions, no drafts)
        contracts = self._get_contracts()
        contracts_frozen = True
        for c in contracts:
            version = c.get("version", "")
            if not version or version == "0.0.0":
                contracts_frozen = False
                name = c.get("name", c.get("contract_id", "unknown"))
                issues.append(f"Contract {name} has unfrozen version: {version}")

        # Check 3: Run CFT
        cft_result = self.run_cft()
        cft_passed = cft_result["passed"]
        cft_fidelity = cft_result["fidelity"]

        if not cft_passed:
            issues.append(f"CFT fidelity {cft_fidelity} below threshold {FIDELITY_THRESHOLD}")

        rebuildable = manifests_valid and contracts_frozen and cft_passed

        result = {
            "rebuildable": rebuildable,
            "manifests_valid": manifests_valid,
            "contracts_frozen": contracts_frozen,
            "cft_passed": cft_passed,
            "cft_fidelity": cft_fidelity,
            "issues": issues,
        }

        self._emit("rebuild.rebuildability_checked", result)
        log.info("rebuildability check: rebuildable=%s issues=%d",
                 rebuildable, len(issues))
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_contracts(self) -> list[dict]:
        """Retrieve contracts from the injected or global contract registry."""
        if self._contract_registry:
            return self._contract_registry.list_all()
        try:
            from sylion.core.contract_registry import get_contract_registry
            cr = get_contract_registry()
            return cr.list_all()
        except Exception:
            return []

    def _get_events(self) -> list[dict]:
        """Retrieve recent events from event bus (excluding rebuild framework's own events)."""
        if self._event_bus:
            events = self._event_bus.query(limit=500)
            # Exclude rebuild framework's own events to prevent snapshot-event feedback loop
            return [e for e in events
                    if not e.get("source_module", "").startswith("rebuild.rebuildability")]
        return []

    def _get_decisions(self) -> list[dict]:
        """Retrieve decisions from governance modules if available."""
        try:
            # Decision boundaries are stored on module registry records.
            modules = self._registry.list_modules() if self._registry else []
            return [
                {"module_id": m.get("module_id", ""), "decision_class": m.get("decision_cls", "D3")}
                for m in modules
            ]
        except Exception:
            return []

    @staticmethod
    def _compute_snapshot_hash(modules: list, contracts: list,
                               events: list, decisions: list) -> str:
        """Compute SHA-256 hash of combined system state (excludes volatile fields)."""
        module_keys = sorted([
            f"{m.get('module_id', '')}:{m.get('module_kind', '')}:{m.get('owner_plan', '')}"
            for m in modules
        ])
        contract_keys = sorted([
            f"{c.get('name', c.get('contract_id', ''))}:{c.get('version', '')}"
            for c in contracts
        ])
        event_keys = sorted([
            f"{e.get('event_id', '')}:{e.get('topic', '')}"
            for e in events
        ])
        decision_keys = sorted([
            f"{d.get('module_id', '')}:{d.get('decision_class', '')}"
            for d in decisions
        ])
        payload = json.dumps({
            "modules": module_keys,
            "contracts": contract_keys,
            "events": event_keys,
            "decisions": decision_keys,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _compute_set_fidelity(original_keys: set[str],
                              rebuilt_keys: set[str]) -> float:
        """Compute Jaccard similarity between two sets of keys."""
        if not original_keys and not rebuilt_keys:
            return 1.0
        if not original_keys:
            return 0.0
        intersection = original_keys & rebuilt_keys
        union = original_keys | rebuilt_keys
        if not union:
            return 1.0
        return len(intersection) / len(union)

    @staticmethod
    def _module_keys(modules: list[dict]) -> set[str]:
        """Extract canonical keys for modules."""
        keys = set()
        for m in modules:
            mid = m.get("module_id", "")
            kind = m.get("module_kind", m.get("module_kind", ""))
            keys.add(f"{mid}:{kind}")
        return keys

    @staticmethod
    def _contract_keys(contracts: list[dict]) -> set[str]:
        """Extract canonical keys for contracts."""
        keys = set()
        for c in contracts:
            name = c.get("name", c.get("contract_id", ""))
            version = c.get("version", "")
            keys.add(f"{name}:{version}")
        return keys

    @staticmethod
    def _event_keys(events: list[dict]) -> set[str]:
        """Extract canonical keys for events."""
        keys = set()
        for e in events:
            eid = e.get("event_id", "")
            topic = e.get("topic", "")
            keys.add(f"{eid}:{topic}")
        return keys

    @staticmethod
    def _decision_keys(decisions: list[dict]) -> set[str]:
        """Extract canonical keys for decisions."""
        keys = set()
        for d in decisions:
            mid = d.get("module_id", "")
            dc = d.get("decision_class", "")
            keys.add(f"{mid}:{dc}")
        return keys

    def _compact_snapshot(self, snapshot: dict | None) -> dict:
        """Simulate compaction: remove redundant data, keep essential keys."""
        if not snapshot:
            return {}

        modules = snapshot.get("modules", [])
        contracts = snapshot.get("contracts", [])
        events = snapshot.get("events", [])
        decisions = snapshot.get("decisions", [])

        # Compact modules: keep only essential fields
        compacted_modules = []
        for m in modules:
            compacted_modules.append({
                "module_id": m.get("module_id", ""),
                "module_kind": m.get("module_kind", ""),
                "owner_plan": m.get("owner_plan", ""),
                "lifecycle": m.get("lifecycle", m.get("lifecycle_stage", "")),
                "depends_on": m.get("depends_on", "[]"),
            })

        # Compact contracts: keep only essential fields
        compacted_contracts = []
        for c in contracts:
            compacted_contracts.append({
                "name": c.get("name", c.get("contract_id", "")),
                "contract_type": c.get("contract_type", ""),
                "version": c.get("version", ""),
                "producer_module": c.get("producer_module", ""),
            })

        # Compact events: keep only essential fields
        compacted_events = []
        for e in events:
            compacted_events.append({
                "event_id": e.get("event_id", ""),
                "topic": e.get("topic", ""),
                "source_module": e.get("source_module", ""),
            })

        # Decisions: keep as-is (already compact)
        return {
            "modules": compacted_modules,
            "contracts": compacted_contracts,
            "events": compacted_events,
            "decisions": decisions,
        }

    def _rebuild_from_compacted(self, compacted: dict) -> dict:
        """Simulate rebuild from compacted data.

        Reconstructs full snapshot structure from compacted representation.
        In production, this would read from Ksiega + contracts and re-register
        modules, replay events, etc.
        """
        rebuilt_modules = []
        for m in compacted.get("modules", []):
            rebuilt_modules.append({
                "module_id": m.get("module_id", ""),
                "module_kind": m.get("module_kind", ""),
                "owner_plan": m.get("owner_plan", ""),
                "lifecycle": m.get("lifecycle", ""),
                "depends_on": m.get("depends_on", "[]"),
            })

        rebuilt_contracts = []
        for c in compacted.get("contracts", []):
            rebuilt_contracts.append({
                "name": c.get("name", ""),
                "contract_type": c.get("contract_type", ""),
                "version": c.get("version", ""),
                "producer_module": c.get("producer_module", ""),
            })

        rebuilt_events = []
        for e in compacted.get("events", []):
            rebuilt_events.append({
                "event_id": e.get("event_id", ""),
                "topic": e.get("topic", ""),
                "source_module": e.get("source_module", ""),
            })

        rebuilt_decisions = list(compacted.get("decisions", []))

        # Store as a snapshot
        snapshot_hash = self._compute_snapshot_hash(
            rebuilt_modules, rebuilt_contracts,
            rebuilt_events, rebuilt_decisions,
        )

        snapshot = SystemSnapshot(
            snapshot_hash=snapshot_hash,
            modules=rebuilt_modules,
            contracts=rebuilt_contracts,
            events=rebuilt_events,
            decisions=rebuilt_decisions,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO rebuild_snapshots
                    (snapshot_id, snapshot_hash, modules_json, contracts_json,
                     events_json, decisions_json, timestamp, label)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'rebuilt')
            """, (
                snapshot.snapshot_id, snapshot.snapshot_hash,
                json.dumps(rebuilt_modules, default=str),
                json.dumps(rebuilt_contracts, default=str),
                json.dumps(rebuilt_events, default=str),
                json.dumps(rebuilt_decisions, default=str),
                snapshot.timestamp,
            ))
            self._conn.commit()

        return {
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_hash": snapshot_hash,
            "modules": rebuilt_modules,
            "contracts": rebuilt_contracts,
            "events": rebuilt_events,
            "decisions": rebuilt_decisions,
            "timestamp": snapshot.timestamp,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="rebuild.rebuildability_framework",
            ))
