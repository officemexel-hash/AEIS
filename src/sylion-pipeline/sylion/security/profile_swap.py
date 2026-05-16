"""
SYLION Security -- Profile Swap Manager (DEPRECATED)

DEPRECATED 2026-04-24 — use security.profile_unified
Backward-compatible shim re-exporting ProfileUnifiedManager.
"""

from __future__ import annotations

import warnings
import time
import uuid
from enum import Enum
from typing import Any

warnings.warn(
    "profile_swap is deprecated; use profile_unified",
    DeprecationWarning,
    stacklevel=2,
)

from sylion.security.profile_unified import (  # noqa: F401
    ProfileSwapManager as _UnifiedProfileSwapManager,
    VALID_STATUSES,
    get_profile_swap,
    get_profile_unified,
    reset_profile_swap,
    reset_profile_unified,
)


class SwapDirection(str, Enum):
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    LATERAL = "lateral"


class ProfileSwapManager(_UnifiedProfileSwapManager):
    """Backward-compatible profile swap facade used by integration flows."""

    _PROFILE_ORDER = {"dev-light": 0, "staging-strict": 1, "prod-locked": 2}

    def __init__(self, *args, registry=None, spine=None, **kwargs):
        self._registry = registry
        self._spine = spine
        self._current_profile = "dev-light"
        self._proposals: dict[str, dict[str, Any]] = {}
        self._history: list[dict[str, Any]] = []
        super().__init__(*args, **{k: v for k, v in kwargs.items() if k in {"db_path", "event_bus"}})

    def get_current_profile(self) -> str:
        return self._current_profile

    def validate_swap(self, from_profile: str, to_profile: str) -> dict[str, Any]:
        from_rank = self._PROFILE_ORDER.get(from_profile, 0)
        to_rank = self._PROFILE_ORDER.get(to_profile, 0)
        if to_rank > from_rank:
            direction = SwapDirection.UPGRADE.value
        elif to_rank < from_rank:
            direction = SwapDirection.DOWNGRADE.value
        else:
            direction = SwapDirection.LATERAL.value
        return {
            "valid": from_profile in self._PROFILE_ORDER and to_profile in self._PROFILE_ORDER and from_profile != to_profile,
            "from": from_profile,
            "to": to_profile,
            "direction": direction,
            "decision_class": "D4" if direction == SwapDirection.UPGRADE.value else "D3",
        }

    def propose_swap(self, to_profile: str, reason: str = "", requested_by: str = "") -> dict[str, Any]:
        validation = self.validate_swap(self._current_profile, to_profile)
        proposal_id = f"profile_swap_{uuid.uuid4().hex[:10]}"
        proposal = {
            "proposal_id": proposal_id,
            "proposed": bool(validation["valid"]),
            "from": self._current_profile,
            "to": to_profile,
            "reason": reason,
            "requested_by": requested_by,
            "created_at": time.time(),
            **validation,
        }
        self._proposals[proposal_id] = proposal
        return proposal

    def execute_swap(self, proposal_id: str, council_approval: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if council_approval is None:
            return super().execute_swap(proposal_id)
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return {"executed": False, "reason": "proposal_not_found"}
        votes = council_approval.get("votes") or []
        approved_votes = [vote for vote in votes if str(vote.get("value")) == "approve"]
        if len(approved_votes) < 4 or council_approval.get("human_gate") != "approved":
            return {"executed": False, "reason": "missing_council_or_human_gate_approval"}

        modules_updated = 0
        if self._registry is not None:
            for module in self._registry.list_modules():
                module_id = module.get("module_id")
                if not module_id:
                    continue
                with self._registry._lock:  # noqa: SLF001 - compatibility shim for legacy integration flow.
                    self._registry._conn.execute(  # noqa: SLF001
                        "UPDATE sylion_modules SET sec_profile = ?, last_heartbeat = ? WHERE module_id = ?",
                        (proposal["to"], time.time(), module_id),
                    )
                    self._registry._conn.commit()  # noqa: SLF001
                modules_updated += 1

        self._current_profile = proposal["to"]
        result = {
            "executed": True,
            "proposal_id": proposal_id,
            "from": proposal["from"],
            "to": proposal["to"],
            "modules_updated": modules_updated,
        }
        self._history.insert(0, {**result, "executed_at": time.time()})
        if self._spine is not None:
            try:
                from sylion.core.evidence_spine import EvidenceEntry

                self._spine.append(EvidenceEntry(
                    source_plan="profile_swap",
                    event_type="profile_swap.executed",
                    payload=result,
                ))
            except Exception:
                pass
        return result

    def get_swap_history(self) -> list[dict[str, Any]]:
        return list(self._history)
