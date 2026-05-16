"""Performance benchmarks for AEIS Advisor — Kimi modules.

Measures latency percentiles (p50/p95/p99) and QPS under concurrent load.
Uses manual timing (time.perf_counter_ns) — no pytest-benchmark dependency.
"""

from __future__ import annotations

import concurrent.futures
import statistics
import time
from typing import Any, Callable

import pytest

from sylion.aeis.advisor.preferences import (
    get_preferences as get_pref_resolver,
    reset_preferences_service as reset_pref_resolver,
)
from sylion.aeis.advisor.pricing import (
    get_pricing as get_pricing_estimator,
    reset_pricing as reset_pricing_estimator,
)
from sylion.aeis.advisor.role_resolver.service import (
    get_role_resolver_service,
    reset_role_resolver_service,
)
from sylion.aeis.advisor.variants.service import (
    get_variants_service,
    reset_variants_service,
)
from sylion.aeis.advisor.subscription.service import (
    get_subscription_service,
    reset_subscription_service,
)
from sylion.aeis.advisor.scaling.service import (
    get_scaling_service,
    reset_scaling_service,
)

# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------

def _percentile(sorted_ns: list[int], pct: float) -> float:
    idx = int(len(sorted_ns) * pct / 100.0)
    idx = min(idx, len(sorted_ns) - 1)
    return sorted_ns[idx] / 1_000_000.0  # ms


def _latency_benchmark(fn: Callable[[], Any], iterations: int = 1000) -> dict[str, float]:
    """Run fn iterations times and return latency stats in ms."""
    times: list[int] = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        fn()
        t1 = time.perf_counter_ns()
        times.append(t1 - t0)
    times.sort()
    return {
        "p50_ms": _percentile(times, 50),
        "p95_ms": _percentile(times, 95),
        "p99_ms": _percentile(times, 99),
        "mean_ms": statistics.mean(times) / 1_000_000.0,
        "min_ms": times[0] / 1_000_000.0,
        "max_ms": times[-1] / 1_000_000.0,
    }


def _qps_benchmark(fn: Callable[[], Any], workers: int, total_calls: int) -> float:
    """Run total_calls spread across workers threads; return QPS."""
    barrier = concurrent.futures.ThreadPoolExecutor(max_workers=workers)

    def worker(n: int):
        for _ in range(n):
            fn()

    calls_per_worker = total_calls // workers
    t0 = time.perf_counter_ns()
    futures = [barrier.submit(worker, calls_per_worker) for _ in range(workers)]
    for f in futures:
        f.result()
    t1 = time.perf_counter_ns()
    elapsed_sec = (t1 - t0) / 1_000_000_000.0
    return total_calls / elapsed_sec


# ---------------------------------------------------------------------------
# Module-level fixtures (reset once, warm up once)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def warm_role_resolver():
    reset_pref_resolver()
    reset_pricing_estimator()
    reset_role_resolver_service()
    svc = get_role_resolver_service()
    # warm-up
    svc.resolve_role("bench_op", "planner", "high")
    return svc


@pytest.fixture(scope="module")
def warm_variants():
    reset_variants_service()
    svc = get_variants_service()
    svc.generate_variants({"context_id": "warm"})
    return svc


@pytest.fixture(scope="module")
def warm_subscription():
    reset_subscription_service()
    svc = get_subscription_service()
    # seed some usage
    for _ in range(10):
        svc.record_usage("bench_sub", "anthropic", "claude-sonnet-4-6", 1000, 500, 0.5)
    return svc


@pytest.fixture(scope="module")
def warm_scaling():
    reset_scaling_service()
    svc = get_scaling_service()
    svc.register_env({
        "env_id": "bench_env",
        "operator_id": "bench_op",
        "name": "bench",
        "kind": "vps",
        "capacity_tokens_per_day": 500_000,
    })
    return svc


# ---------------------------------------------------------------------------
# Role Resolver benchmarks
# ---------------------------------------------------------------------------

class TestBenchRoleResolver:
    def test_latency_resolve_role(self, warm_role_resolver):
        stats = _latency_benchmark(
            lambda: warm_role_resolver.resolve_role("bench_op", "planner", "high"),
            iterations=1000,
        )
        print(f"\n[role_resolver] resolve_role latency: {stats}")
        assert stats["p99_ms"] < 25.0, f"p99 too high: {stats['p99_ms']} ms"

    def test_latency_resolve_judge(self, warm_role_resolver):
        stats = _latency_benchmark(
            lambda: warm_role_resolver.resolve_judge("bench_op", "risk_assessment", "medium"),
            iterations=1000,
        )
        print(f"\n[role_resolver] resolve_judge latency: {stats}")
        assert stats["p99_ms"] < 100.0, f"p99 too high: {stats['p99_ms']} ms"

    def test_latency_preview_routing(self, warm_role_resolver):
        stats = _latency_benchmark(
            lambda: warm_role_resolver.preview_routing("bench_op", "planner low risk"),
            iterations=1000,
        )
        print(f"\n[role_resolver] preview_routing latency: {stats}")
        assert stats["p99_ms"] < 40.0, f"p99 too high: {stats['p99_ms']} ms"

    def test_qps_resolve_role_concurrent(self, warm_role_resolver):
        for workers in (10, 100):
            qps = _qps_benchmark(
                lambda: warm_role_resolver.resolve_role("bench_op", "planner", "high"),
                workers=workers,
                total_calls=workers * 50,
            )
            print(f"\n[role_resolver] resolve_role QPS (workers={workers}): {qps:.1f}")
            assert qps > 100, f"QPS too low: {qps}"


# ---------------------------------------------------------------------------
# Variants benchmarks
# ---------------------------------------------------------------------------

class TestBenchVariants:
    def test_latency_generate_variants(self, warm_variants):
        stats = _latency_benchmark(
            lambda: warm_variants.generate_variants({"context_id": "bench"}),
            iterations=500,
        )
        print(f"\n[variants] generate_variants latency: {stats}")
        assert stats["p99_ms"] < 120.0, f"p99 too high: {stats['p99_ms']} ms"

    def test_qps_generate_variants_concurrent(self, warm_variants):
        for workers in (10, 100):
            qps = _qps_benchmark(
                lambda: warm_variants.generate_variants({"context_id": "bench"}),
                workers=workers,
                total_calls=workers * 20,
            )
            print(f"\n[variants] generate_variants QPS (workers={workers}): {qps:.1f}")
            assert qps > 15, f"QPS too low: {qps}"


# ---------------------------------------------------------------------------
# Subscription benchmarks
# ---------------------------------------------------------------------------

class TestBenchSubscription:
    def test_latency_record_usage(self, warm_subscription):
        stats = _latency_benchmark(
            lambda: warm_subscription.record_usage(
                "bench_sub", "anthropic", "claude-sonnet-4-6", 1000, 500, 0.5
            ),
            iterations=1000,
        )
        print(f"\n[subscription] record_usage latency: {stats}")
        assert stats["p99_ms"] < 10.0

    def test_latency_compute_roi(self, warm_subscription):
        stats = _latency_benchmark(
            lambda: warm_subscription.compute_roi("bench_sub", "anthropic_pro", 30),
            iterations=500,
        )
        print(f"\n[subscription] compute_roi latency: {stats}")
        assert stats["p99_ms"] < 15.0

    def test_qps_record_usage_concurrent(self, warm_subscription):
        for workers in (10, 100):
            qps = _qps_benchmark(
                lambda: warm_subscription.record_usage(
                    "bench_sub", "anthropic", "claude-sonnet-4-6", 1000, 500, 0.5
                ),
                workers=workers,
                total_calls=workers * 50,
            )
            print(f"\n[subscription] record_usage QPS (workers={workers}): {qps:.1f}")
            assert qps > 100


# ---------------------------------------------------------------------------
# Scaling benchmarks
# ---------------------------------------------------------------------------

class TestBenchScaling:
    def test_latency_recommend_topology(self, warm_scaling):
        stats = _latency_benchmark(
            lambda: warm_scaling.recommend_topology(
                "bench_op", "proj", {"estimated_tokens_per_day": 500_000, "parallelism": 2}
            ),
            iterations=1000,
        )
        print(f"\n[scaling] recommend_topology latency: {stats}")
        assert stats["p99_ms"] < 5.0

    def test_latency_propose_staging_plan(self, warm_scaling):
        stats = _latency_benchmark(
            lambda: warm_scaling.propose_staging_plan("local_only", "multi_vps"),
            iterations=1000,
        )
        print(f"\n[scaling] propose_staging_plan latency: {stats}")
        assert stats["p99_ms"] < 5.0

    def test_qps_recommend_topology_concurrent(self, warm_scaling):
        for workers in (10, 100):
            qps = _qps_benchmark(
                lambda: warm_scaling.recommend_topology(
                    "bench_op", "proj", {"estimated_tokens_per_day": 500_000, "parallelism": 2}
                ),
                workers=workers,
                total_calls=workers * 50,
            )
            print(f"\n[scaling] recommend_topology QPS (workers={workers}): {qps:.1f}")
            assert qps > 200
