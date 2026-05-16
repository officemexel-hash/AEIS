"""
SYLION Contracts -- Contract Freeze Manager

Implements the Contract Freeze mechanism required before parallel build.
No worker may start independent implementation until contracts, event taxonomy,
dependency graph, ownership, decision boundaries, security profiles and
integration acceptance rules are frozen.

Frozen contracts may only be changed via D3+ governance.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


class ContractFreezeManager:
    """Manages contract freeze lifecycle for distributed builds."""

    def __init__(self, state_path: str | Path | None = None):
        self._state_path = Path(state_path) if state_path else None
        self._lock = threading.RLock()
        self._frozen = False
        self._frozen_at: float | None = None
        self._frozen_by = ""
        self._build_id = ""
        self._frozen_contracts: list[dict] = []
        self._frozen_events: list[dict] = []
        self._frozen_dependencies: list[dict] = []
        self._load_state()

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------
    def _load_state(self) -> None:
        if self._state_path and self._state_path.exists():
            try:
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
                self._frozen = data.get("frozen", False)
                self._frozen_at = data.get("frozen_at")
                self._frozen_by = data.get("frozen_by", "")
                self._build_id = data.get("build_id", "")
                self._frozen_contracts = data.get("contracts", [])
                self._frozen_events = data.get("events", [])
                self._frozen_dependencies = data.get("dependencies", [])
            except (json.JSONDecodeError, OSError):
                pass

    def _save_state(self) -> None:
        if self._state_path:
            data = {
                "frozen": self._frozen,
                "frozen_at": self._frozen_at,
                "frozen_by": self._frozen_by,
                "build_id": self._build_id,
                "contracts": self._frozen_contracts,
                "events": self._frozen_events,
                "dependencies": self._frozen_dependencies,
            }
            self._state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def freeze(
        self,
        build_id: str,
        frozen_by: str,
        contracts: list[dict],
        events: list[dict],
        dependencies: list[dict],
    ) -> dict:
        """Freeze contracts for a build. Idempotent if already frozen for same build."""
        with self._lock:
            if self._frozen and self._build_id == build_id:
                return self.status()
            if self._frozen and self._build_id != build_id:
                raise RuntimeError(
                    f"Contracts already frozen for build {self._build_id}. "
                    "Thaw or use governance D3+ to override."
                )
            self._frozen = True
            self._frozen_at = time.time()
            self._frozen_by = frozen_by
            self._build_id = build_id
            self._frozen_contracts = list(contracts)
            self._frozen_events = list(events)
            self._frozen_dependencies = list(dependencies)
            self._save_state()
            return self.status()

    def thaw(self, requested_by: str, force: bool = False) -> dict:
        """Thaw frozen contracts. Requires force=True if build is in progress."""
        with self._lock:
            if not self._frozen:
                return self.status()
            if not force:
                raise RuntimeError(
                    "Thawing frozen contracts requires force=True or D3+ governance approval."
                )
            self._frozen = False
            self._frozen_at = None
            self._frozen_by = ""
            self._build_id = ""
            self._frozen_contracts = []
            self._frozen_events = []
            self._frozen_dependencies = []
            self._save_state()
            return self.status()

    def status(self) -> dict:
        """Current freeze status."""
        with self._lock:
            return {
                "frozen": self._frozen,
                "frozen_at": self._frozen_at,
                "frozen_by": self._frozen_by,
                "build_id": self._build_id,
                "contract_count": len(self._frozen_contracts),
                "event_count": len(self._frozen_events),
                "dependency_count": len(self._frozen_dependencies),
            }

    def check_change_permission(self, module_id: str, change_type: str) -> dict:
        """Check if a proposed change is allowed under current freeze."""
        with self._lock:
            if not self._frozen:
                return {"allowed": True, "reason": "No active freeze."}

            # Public contract changes require D3+
            if change_type in ("contract", "event", "dependency_graph", "module_boundary"):
                return {
                    "allowed": False,
                    "reason": f"Change type '{change_type}' is frozen. Requires D3+ governance to modify.",
                    "required_decision_class": "D3",
                }

            # Internal implementation changes are allowed if module is assigned
            return {"allowed": True, "reason": "Internal implementation change permitted under freeze."}

    def get_frozen_snapshot(self) -> dict:
        """Full frozen snapshot for workers."""
        with self._lock:
            return {
                "frozen": self._frozen,
                "build_id": self._build_id,
                "contracts": list(self._frozen_contracts),
                "events": list(self._frozen_events),
                "dependencies": list(self._frozen_dependencies),
            }


# Singleton instance for shared state across routes
_freeze_manager_instance: ContractFreezeManager | None = None


def get_freeze_manager(state_path: str | Path | None = None) -> ContractFreezeManager:
    global _freeze_manager_instance
    if _freeze_manager_instance is None:
        _freeze_manager_instance = ContractFreezeManager(state_path)
    return _freeze_manager_instance
