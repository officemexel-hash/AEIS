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
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.evidence_spine import EvidenceSpine, get_evidence_spine
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


@dataclass(frozen=True)
class AutoscalerSignal:
    at_sec: float
    queue_depth: int
    cpu_pct: float
    error_rate: float


@dataclass(frozen=True)
class AutoscalerSimulationProfile:
    name: str = "autoscaler_production_readiness"
    initial_workers: int = 2
    min_workers: int = 2
    max_workers: int = 6
    target_queue_depth: int = 3
    scale_up_threshold_ratio: float = 1.0
    scale_down_threshold_ratio: float = 0.5
    scale_up_cpu_pct: float = 75.0
    scale_down_cpu_pct: float = 25.0
    scale_up_error_rate: float = 0.05
    scale_down_error_rate: float = 0.01
    cooldown_sec: float = 60.0
    signals: list[AutoscalerSignal] = field(default_factory=list)

    def normalized_signals(self) -> list[AutoscalerSignal]:
        if self.signals:
            return sorted(self.signals, key=lambda item: item.at_sec)
        return [
            AutoscalerSignal(at_sec=0, queue_depth=12, cpu_pct=82.0, error_rate=0.01),
            AutoscalerSignal(at_sec=10, queue_depth=11, cpu_pct=84.0, error_rate=0.01),
            AutoscalerSignal(at_sec=70, queue_depth=1, cpu_pct=18.0, error_rate=0.0),
            AutoscalerSignal(at_sec=140, queue_depth=6, cpu_pct=45.0, error_rate=0.0),
        ]

    def validate(self) -> None:
        if self.initial_workers < 1:
            raise ValueError("initial_workers must be positive")
        if self.min_workers < 1:
            raise ValueError("min_workers must be positive")
        if self.max_workers < self.min_workers:
            raise ValueError("max_workers must be >= min_workers")
        if self.initial_workers < self.min_workers or self.initial_workers > self.max_workers:
            raise ValueError("initial_workers must be within min/max bounds")
        if self.target_queue_depth <= 0:
            raise ValueError("target_queue_depth must be positive")
        if self.cooldown_sec < 0:
            raise ValueError("cooldown_sec cannot be negative")


class AutoscalerSimulationRunner:
    """Runs autoscaler scale-up/down simulations with anti-flapping checks."""

    def __init__(self, evidence_spine: EvidenceSpine | None = None) -> None:
        self._evidence_spine = evidence_spine or get_evidence_spine()

    def run(self, profile: AutoscalerSimulationProfile | None = None) -> dict[str, Any]:
        profile = profile or AutoscalerSimulationProfile()
        profile.validate()
        active_workers = profile.initial_workers
        last_scale_at = -1 * (profile.cooldown_sec + 1)
        last_scale_action = ""
        direction_changes_inside_window = 0
        decisions: list[dict[str, Any]] = []

        for signal in profile.normalized_signals():
            in_cooldown = (signal.at_sec - last_scale_at) < profile.cooldown_sec
            action, reason = self._decide(profile, signal, active_workers, in_cooldown)
            before = active_workers
            if action == "scale_up":
                active_workers = min(profile.max_workers, active_workers + 1)
            elif action == "scale_down":
                active_workers = max(profile.min_workers, active_workers - 1)

            if action in {"scale_up", "scale_down"}:
                if (
                    last_scale_action
                    and last_scale_action != action
                    and (signal.at_sec - last_scale_at) < profile.cooldown_sec
                ):
                    direction_changes_inside_window += 1
                last_scale_action = action
                last_scale_at = signal.at_sec

            decisions.append({
                "at_sec": signal.at_sec,
                "queue_depth": signal.queue_depth,
                "cpu_pct": signal.cpu_pct,
                "error_rate": signal.error_rate,
                "action": action,
                "reason": reason,
                "in_cooldown": in_cooldown,
                "workers_before": before,
                "workers_after": active_workers,
            })

        actions = [item["action"] for item in decisions]
        checks = {
            "scale_up_seen": "scale_up" in actions,
            "scale_down_seen": "scale_down" in actions,
            "cooldown_block_seen": any(item["in_cooldown"] and item["action"] == "maintain" for item in decisions),
            "no_flapping": direction_changes_inside_window == 0,
            "within_worker_bounds": all(
                profile.min_workers <= item["workers_after"] <= profile.max_workers
                for item in decisions
            ),
        }
        status = "pass" if all(checks.values()) else "fail"
        payload = {
            "profile": asdict(profile),
            "decisions": decisions,
            "checks": checks,
            "status": status,
            "final_workers": active_workers,
        }
        evidence_id = self._evidence(payload)
        return {**payload, "evidence_id": evidence_id}

    @staticmethod
    def _decide(
        profile: AutoscalerSimulationProfile,
        signal: AutoscalerSignal,
        active_workers: int,
        in_cooldown: bool,
    ) -> tuple[str, str]:
        target_capacity = active_workers * profile.target_queue_depth
        scale_up_trigger = target_capacity * profile.scale_up_threshold_ratio
        scale_down_trigger = target_capacity * profile.scale_down_threshold_ratio
        if in_cooldown:
            return "maintain", "cooldown_active"
        if (
            active_workers < profile.max_workers
            and (
                signal.queue_depth > scale_up_trigger
                or signal.cpu_pct >= profile.scale_up_cpu_pct
                or signal.error_rate >= profile.scale_up_error_rate
            )
        ):
            return "scale_up", "high_queue_cpu_or_error_rate"
        if (
            active_workers > profile.min_workers
            and signal.queue_depth < scale_down_trigger
            and signal.cpu_pct <= profile.scale_down_cpu_pct
            and signal.error_rate <= profile.scale_down_error_rate
        ):
            return "scale_down", "low_queue_cpu_and_error_rate"
        return "maintain", "within_thresholds"

    def _evidence(self, payload: dict[str, Any]) -> str:
        artifact = self._evidence_spine.register_json_artifact(
            payload,
            source="worker.autoscaler",
            artifact_type="autoscaler_simulation",
            retention_policy="autoscaler-production-readiness",
            metadata={"name": payload.get("profile", {}).get("name", "")},
            actor_id="autoscaler-simulation-runner",
        )
        return str(artifact["evidence_id"])


_simulation_runner: AutoscalerSimulationRunner | None = None


def get_autoscaler_simulation_runner(
    evidence_spine: EvidenceSpine | None = None,
) -> AutoscalerSimulationRunner:
    global _simulation_runner
    if _simulation_runner is None:
        _simulation_runner = AutoscalerSimulationRunner(evidence_spine=evidence_spine)
    return _simulation_runner


def reset_autoscaler_simulation_runner(
    evidence_spine: EvidenceSpine | None = None,
) -> AutoscalerSimulationRunner | None:
    global _simulation_runner
    _simulation_runner = None
    if evidence_spine is not None:
        _simulation_runner = AutoscalerSimulationRunner(evidence_spine=evidence_spine)
    return _simulation_runner
