"""
SYLION Worker -- Auto-Scaler

Monitors queue depth and worker load to make scaling decisions:
  - scale_up   when pending_assignments > target_queue_depth * active_workers
  - scale_down when pending_assignments < target_queue_depth * active_workers * 0.5
               and active_workers > min_workers
  - maintain   otherwise

Scaling policies are configurable per topology variant.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.worker.registry import WorkerRegistry


class AutoScaler:
    """Auto-scales worker fleet based on queue depth and load."""

    def __init__(
        self,
        registry: WorkerRegistry,
        min_workers: int = 2,
        max_workers: int = 10,
        target_queue_depth: int = 3,
        scale_up_threshold_ratio: float = 1.0,
        scale_down_threshold_ratio: float = 0.5,
        cooldown_sec: float = 60.0,
        state_path: str | Path | None = None,
    ):
        self._registry = registry
        self._min_workers = min_workers
        self._max_workers = max_workers
        self._target_queue_depth = target_queue_depth
        self._scale_up_ratio = scale_up_threshold_ratio
        self._scale_down_ratio = scale_down_threshold_ratio
        self._cooldown_sec = cooldown_sec
        self._state_path = Path(state_path) if state_path else None
        self._lock = threading.RLock()
        self._last_scale_action: float = 0.0
        self._last_decision: dict[str, Any] = {}
        self._history: list[dict] = []
        self._load_state()

    def _load_state(self) -> None:
        if self._state_path and self._state_path.exists():
            try:
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
                self._last_scale_action = data.get("last_scale_action", 0.0)
                self._history = data.get("history", [])
            except (json.JSONDecodeError, OSError):
                pass

    def _save_state(self) -> None:
        if self._state_path:
            data = {
                "last_scale_action": self._last_scale_action,
                "history": self._history[-50:],  # keep last 50
            }
            self._state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def evaluate(self) -> dict[str, Any]:
        """Evaluate current state and return scaling decision."""
        with self._lock:
            workers = self._registry.list_workers(status="active")
            active_count = len(workers)
            total_capacity = sum(w.get("capacity", 1) for w in workers)

            # Count pending assignments across all workers
            pending = 0
            for w in workers:
                asgs = self._registry.list_assignments(worker_id=w["worker_id"])
                pending += len([a for a in asgs if a.get("status") in ("pending", "assigned")])

            # Also count unassigned pending (not yet assigned to any worker)
            all_asgs = []
            try:
                all_asgs = self._registry.list_assignments(status="pending")
            except Exception:
                pass
            pending = max(pending, len(all_asgs))

            now = time.time()
            in_cooldown = (now - self._last_scale_action) < self._cooldown_sec

            target_capacity = active_count * self._target_queue_depth
            scale_up_trigger = target_capacity * self._scale_up_ratio
            scale_down_trigger = target_capacity * self._scale_down_ratio

            decision = "maintain"
            reason = f"pending={pending}, active={active_count}, capacity={total_capacity}"

            if not in_cooldown:
                if pending > scale_up_trigger and active_count < self._max_workers:
                    decision = "scale_up"
                    reason = f"Pending {pending} > threshold {scale_up_trigger:.0f}"
                elif pending < scale_down_trigger and active_count > self._min_workers:
                    decision = "scale_down"
                    reason = f"Pending {pending} < threshold {scale_down_trigger:.0f}"

            self._last_decision = {
                "timestamp": now,
                "decision": decision,
                "reason": reason,
                "pending_assignments": pending,
                "active_workers": active_count,
                "total_capacity": total_capacity,
                "in_cooldown": in_cooldown,
                "cooldown_remaining_sec": max(0, self._cooldown_sec - (now - self._last_scale_action)),
            }
            return self._last_decision

    def execute(self, decision: str | None = None) -> dict[str, Any]:
        """Execute a scaling decision. Returns result."""
        with self._lock:
            if decision is None:
                decision = self.evaluate()["decision"]

            now = time.time()
            if decision == "scale_up":
                # Register a new worker stub
                worker = self._registry.register_worker(
                    name=f"auto-worker-{uuid.uuid4().hex[:6]}",
                    host="auto-provisioned",
                    capacity=3,
                    tags=["auto-scaled"],
                )
                self._last_scale_action = now
                record = {
                    "timestamp": now,
                    "action": "scale_up",
                    "worker_id": worker["worker_id"],
                }
                self._history.append(record)
                self._save_state()
                return {**record, "worker": worker}

            if decision == "scale_down":
                # Find an auto-scaled worker with least assignments
                candidates = [
                    w for w in self._registry.list_workers(status="active")
                    if "auto-scaled" in w.get("tags", [])
                ]
                if not candidates:
                    return {"action": "scale_down", "result": "no_auto_scaled_workers", "timestamp": now}
                # Pick worker with least assignments
                def _load(w):
                    try:
                        return len(self._registry.list_assignments(worker_id=w["worker_id"]))
                    except Exception:
                        return 0
                victim = min(candidates, key=_load)
                self._registry.unregister_worker(victim["worker_id"])
                self._last_scale_action = now
                record = {
                    "timestamp": now,
                    "action": "scale_down",
                    "worker_id": victim["worker_id"],
                }
                self._history.append(record)
                self._save_state()
                return {**record, "result": "deleted"}

            return {"action": "maintain", "timestamp": now}

    def get_history(self, limit: int = 20) -> list[dict]:
        with self._lock:
            return self._history[-limit:]

    def get_policy(self) -> dict[str, Any]:
        return {
            "min_workers": self._min_workers,
            "max_workers": self._max_workers,
            "target_queue_depth": self._target_queue_depth,
            "scale_up_threshold_ratio": self._scale_up_ratio,
            "scale_down_threshold_ratio": self._scale_down_ratio,
            "cooldown_sec": self._cooldown_sec,
        }

    def update_policy(self, **kwargs: Any) -> dict[str, Any]:
        with self._lock:
            if "min_workers" in kwargs:
                self._min_workers = int(kwargs["min_workers"])
            if "max_workers" in kwargs:
                self._max_workers = int(kwargs["max_workers"])
            if "target_queue_depth" in kwargs:
                self._target_queue_depth = int(kwargs["target_queue_depth"])
            if "scale_up_threshold_ratio" in kwargs:
                self._scale_up_ratio = float(kwargs["scale_up_threshold_ratio"])
            if "scale_down_threshold_ratio" in kwargs:
                self._scale_down_ratio = float(kwargs["scale_down_threshold_ratio"])
            if "cooldown_sec" in kwargs:
                self._cooldown_sec = float(kwargs["cooldown_sec"])
            return self.get_policy()
