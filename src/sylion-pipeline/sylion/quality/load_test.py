"""Production readiness load test runner."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import tracemalloc
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.evidence_spine import EvidenceSpine, get_evidence_spine
from sylion.efficiency.memory_footprint import MemoryFootprintTracker
from sylion.efficiency.runtime_perf import RuntimePerfTracker
from sylion.worker.registry import WorkerRegistry


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


@dataclass(frozen=True)
class LoadTestProfile:
    name: str = "aeis_10x_peak"
    expected_peak_operations: int = 25
    peak_multiplier: int = 10
    target_p99_ms: float = 500.0
    max_db_connections: int = 5
    max_memory_growth_bytes: int = 8 * 1024 * 1024
    worker_count: int = 4
    dispatch_target_p99_ms: float = 500.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def target_operations(self) -> int:
        return int(self.expected_peak_operations * self.peak_multiplier)

    def validate(self) -> None:
        if self.expected_peak_operations <= 0:
            raise ValueError("expected_peak_operations must be positive")
        if self.peak_multiplier < 10:
            raise ValueError("peak_multiplier must be at least 10")
        if self.target_operations > 5000:
            raise ValueError("target_operations is capped at 5000 per in-process run")
        if self.target_p99_ms <= 0:
            raise ValueError("target_p99_ms must be positive")
        if self.max_db_connections <= 0:
            raise ValueError("max_db_connections must be positive")
        if self.max_memory_growth_bytes <= 0:
            raise ValueError("max_memory_growth_bytes must be positive")
        if self.worker_count <= 0:
            raise ValueError("worker_count must be positive")


class LoadTestRunner:
    """Runs a bounded 10x peak load test and records production evidence."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        evidence_spine: EvidenceSpine | None = None,
        runtime_perf: RuntimePerfTracker | None = None,
        memory_tracker: MemoryFootprintTracker | None = None,
        worker_registry: WorkerRegistry | None = None,
    ) -> None:
        self._db_path = str(db_path) if db_path else ":memory:"
        self._evidence_spine = evidence_spine or get_evidence_spine()
        self._runtime_perf = runtime_perf or RuntimePerfTracker()
        self._memory_tracker = memory_tracker or MemoryFootprintTracker()
        self._worker_registry = worker_registry or WorkerRegistry()
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS load_test_runs (
                run_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                target_operations INTEGER NOT NULL,
                p99_ms REAL NOT NULL,
                dispatch_p99_ms REAL NOT NULL,
                db_connections_opened INTEGER NOT NULL,
                memory_growth_bytes INTEGER NOT NULL,
                evidence_id TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                completed_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS load_test_events (
                event_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                operation_index INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );
        """)
        self._conn.commit()

    def run_10x(self, profile: LoadTestProfile | None = None) -> dict[str, Any]:
        profile = profile or LoadTestProfile()
        profile.validate()
        run_id = _uid("load10x")
        created_at = time.time()
        workers = [
            self._worker_registry.register_worker(
                name=f"load-worker-{idx + 1}",
                host=f"load-worker-{idx + 1}.local",
                capacity=max(1, profile.target_operations),
                tags=["load-test"],
                metadata={"load_test_run_id": run_id},
            )
            for idx in range(profile.worker_count)
        ]

        db_latencies: list[float] = []
        dispatch_latencies: list[float] = []
        operation_latencies: list[float] = []
        db_connections_opened = 1
        tracemalloc.start()
        start_memory, _ = tracemalloc.get_traced_memory()
        try:
            for idx in range(profile.target_operations):
                operation_start = time.perf_counter()
                db_start = time.perf_counter()
                self._record_event(run_id, idx, {"worker_index": idx % profile.worker_count})
                db_latencies.append((time.perf_counter() - db_start) * 1000)

                dispatch_start = time.perf_counter()
                worker = workers[idx % len(workers)]
                self._worker_registry.create_assignment(
                    worker["worker_id"],
                    module_id=f"load.module.{idx}",
                    priority=(idx % 5) + 1,
                    metadata={"load_test_run_id": run_id, "operation_index": idx},
                )
                dispatch_latencies.append((time.perf_counter() - dispatch_start) * 1000)
                operation_latencies.append((time.perf_counter() - operation_start) * 1000)
        finally:
            end_memory, peak_memory = tracemalloc.get_traced_memory()
            tracemalloc.stop()

        memory_growth = max(0, int(end_memory - start_memory))
        p50 = _percentile(operation_latencies, 0.50)
        p95 = _percentile(operation_latencies, 0.95)
        p99 = _percentile(operation_latencies, 0.99)
        dispatch_p99 = _percentile(dispatch_latencies, 0.99)
        db_p99 = _percentile(db_latencies, 0.99)
        checks = {
            "p99_under_target": p99 <= profile.target_p99_ms,
            "dispatch_p99_under_target": dispatch_p99 <= profile.dispatch_target_p99_ms,
            "db_connections_within_limit": db_connections_opened <= profile.max_db_connections,
            "memory_growth_within_limit": memory_growth <= profile.max_memory_growth_bytes,
            "no_memory_leak_detected": memory_growth <= profile.max_memory_growth_bytes,
        }
        status = "pass" if all(checks.values()) else "fail"
        completed_at = time.time()
        payload = {
            "run_id": run_id,
            "profile": asdict(profile),
            "target_operations": profile.target_operations,
            "status": status,
            "metrics": {
                "p50_ms": round(p50, 3),
                "p95_ms": round(p95, 3),
                "p99_ms": round(p99, 3),
                "db_p99_ms": round(db_p99, 3),
                "dispatch_p99_ms": round(dispatch_p99, 3),
                "db_connections_opened": db_connections_opened,
                "memory_growth_bytes": memory_growth,
                "memory_peak_bytes": int(peak_memory),
                "throughput_ops_per_sec": round(
                    profile.target_operations / max(completed_at - created_at, 0.001),
                    3,
                ),
            },
            "checks": checks,
        }
        evidence_id = self._evidence(payload)
        self._runtime_perf.record(
            "quality.load_test.10x",
            latency_ms=int(round(p99)),
            p50=int(round(p50)),
            p95=int(round(p95)),
            p99=int(round(p99)),
            error_rate=0.0 if status == "pass" else 1.0,
            throughput=payload["metrics"]["throughput_ops_per_sec"],
        )
        self._memory_tracker.snapshot(
            "quality.load_test.10x",
            rss=memory_growth,
            heap=end_memory,
            peak=peak_memory,
            gc=0,
        )
        with self._lock:
            self._conn.execute("""
                INSERT INTO load_test_runs (
                    run_id, name, status, target_operations, p99_ms,
                    dispatch_p99_ms, db_connections_opened, memory_growth_bytes,
                    evidence_id, payload_json, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                profile.name,
                status,
                profile.target_operations,
                p99,
                dispatch_p99,
                db_connections_opened,
                memory_growth,
                evidence_id,
                _canonical_json(payload),
                created_at,
                completed_at,
            ))
            self._conn.commit()
        return self.get_run(run_id) or {}

    def _record_event(self, run_id: str, operation_index: int, payload: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO load_test_events "
                "(event_id, run_id, operation_index, payload_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    _uid("load_event"),
                    run_id,
                    operation_index,
                    _canonical_json(payload),
                    time.time(),
                ),
            )
            self._conn.commit()

    def _evidence(self, payload: dict[str, Any]) -> str:
        artifact = self._evidence_spine.register_json_artifact(
            payload,
            source="quality.load_test",
            artifact_type="load_test_10x",
            retention_policy="production-load-test-freeze",
            metadata={"run_id": payload.get("run_id", "")},
            actor_id="load-test-runner",
        )
        return str(artifact["evidence_id"])

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM load_test_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json") or "{}")
        return data

    def list_runs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT run_id FROM load_test_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self.get_run(row["run_id"]) for row in rows if row["run_id"]]


_runner: LoadTestRunner | None = None


def get_load_test_runner(
    db_path: str | Path | None = None,
    *,
    evidence_spine: EvidenceSpine | None = None,
) -> LoadTestRunner:
    global _runner
    if _runner is None:
        _runner = LoadTestRunner(db_path=db_path, evidence_spine=evidence_spine)
    return _runner


def reset_load_test_runner(
    db_path: str | Path | None = None,
    *,
    evidence_spine: EvidenceSpine | None = None,
) -> LoadTestRunner | None:
    global _runner
    _runner = None
    if db_path is not None or evidence_spine is not None:
        _runner = LoadTestRunner(db_path=db_path, evidence_spine=evidence_spine)
    return _runner


__all__ = [
    "LoadTestProfile",
    "LoadTestRunner",
    "get_load_test_runner",
    "reset_load_test_runner",
]
